"""ContextLoader — first node of the execution pipeline.

Transforms the raw ChatRequest into structured OrchestratorState fields:
  - Parses add_entities / add_search_set messages → context_doc_ids
  - Expands search sets via OpenSearch queries
  - Converts user/assistant text messages to LangChain BaseMessages
  - Extracts entity links from prior assistant responses → followup_doc_ids
    (used to scope follow-up queries to cited documents only)
  - Builds per-document metadata previews and fetches NER entities
"""

import asyncio
import logging
import re
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.api.v1.ai.chat.chat_model import ChatRequest
from .state import OrchestratorState
from .utils import emit_ui_event
from .parse_entity_context import build_document_metadata
from .tools.opensearch_repository import (
    count_scope_entities,
    check_has_fragments,
    fetch_ner_entities,
    get_search_context,
    expand_search_set,
)

logger = logging.getLogger(__name__)


def _field(obj: object, name: str, default: object = None) -> object:
    """Read `name` off an object or a dict, whichever this is.

    The request can arrive as typed objects or as plain dicts depending on the caller,
    and this pair of accesses was written out eight times. Once, named, is the same
    behaviour with one place to fix.
    """
    value = getattr(obj, name, None)
    if value is None and isinstance(obj, dict):
        value = obj.get(name)
    return default if value is None else value

# Matches entity links in assistant responses: [label](entity:uuid/type)
_ENTITY_LINK_RE = re.compile(r"\]\(entity:([0-9a-f-]+)/(os_file|os_fragment)\)")

# How many recent assistant responses to scan for follow-up doc IDs
_FOLLOWUP_RESPONSE_WINDOW = 2


class ContextLoader:
    """LangGraph node: first step of the execution pipeline.

    Converts the raw ChatRequest into OrchestratorState fields:

    1. **Request parsing** (_extract_from_request):
       - Extracts query, workspace_id from the request.
       - Walks the message history to collect context_doc_ids from
         add_entities / add_search_set messages.
       - Converts user/assistant text messages to LangChain BaseMessages.
       - Parses entity links [label](entity:uuid/os_file|os_fragment) from
         prior assistant responses → followup_doc_ids (used to scope
         follow-up queries to only the documents the assistant cited).

    2. **Document context** (_build_document_context):
       - Counts total indexed chunks and detects os_fragment presence.
       - Builds entity_context: per-doc metadata previews for the LLM.
       - Fetches NER entities extracted by the ingestion pipeline.

    State fields produced:
        query, workspace_id, context_doc_ids, followup_doc_ids, messages,
        entity_context, doc_ner_entities, total_chunks, has_fragments,
        document_languages.
    """

    async def __call__(
        self,
        state: OrchestratorState,
        config: RunnableConfig | None = None,
    ) -> dict:
        request = state.get("request")

        if request is not None:
            (
                query,
                workspace_id,
                context_docs,
                followup_doc_ids,
                messages,
                scope_warnings,
            ) = await self._extract_from_request(request, state)
        else:
            query = state.get("query", "")
            workspace_id = state.get("workspace_id", "")
            context_docs = state.get("context_doc_ids", [])
            followup_doc_ids = state.get("followup_doc_ids", [])
            messages = state.get("messages", [])
            scope_warnings = []

        (
            entity_context,
            total_chunks,
            has_fragments,
            document_languages,
            doc_ner_entities,
        ) = await self._build_document_context(
            context_docs, workspace_id, query, config
        )

        logger.info(
            "load_context: %d docs, %d chunks, %d chars preview, %d followup docs",
            len(context_docs),
            total_chunks,
            len(entity_context),
            len(followup_doc_ids),
        )
        if context_docs:
            lang_str = ", ".join(document_languages) if document_languages else ""
            parts = [
                f"{len(context_docs)} documents in context ({total_chunks} chunks)"
            ]
            if followup_doc_ids:
                parts.append(f"{len(followup_doc_ids)} from prior responses")
            if lang_str:
                parts.append(lang_str)
            await emit_ui_event(config, " — ".join(parts))

        forced_strategy = ""
        if request is not None:
            forced_strategy = (getattr(request, "strategy", None) or "").strip()

        return {
            "query": query,
            "workspace_id": workspace_id,
            "context_doc_ids": context_docs,
            "followup_doc_ids": followup_doc_ids,
            "messages": messages,
            "entity_context": entity_context,
            "doc_ner_entities": doc_ner_entities,
            "total_chunks": total_chunks,
            "has_fragments": has_fragments,
            "document_languages": document_languages,
            "forced_strategy": forced_strategy,
            "scope_warnings": scope_warnings,
        }

    # ------------------------------------------------------------------
    # Extract from request
    # ------------------------------------------------------------------

    async def _extract_from_request(
        self, request: ChatRequest, state: OrchestratorState
    ) -> tuple[str, str, list[str], list[str], list, list[str]]:
        """Parse the request → (query, workspace_id, context_docs, followup_doc_ids,
        messages, scope_warnings)."""
        query = getattr(request, "prompt", "") or ""

        workspace_id = ""
        open_ws = getattr(request, "open_workspaces", None) or []
        if len(open_ws) == 1:
            # Only scope to a workspace when exactly one is open.
            # Multiple open workspaces means the user is working across
            # workspaces — picking one arbitrarily would miss relevant docs.
            # Discovery mode in pre_fetch handles the no-scope case.
            workspace_id = _field(open_ws[0], "entity_id", "")

        context_docs: list[str] = []
        # Search sets keyed by entity_id — add_search_set inserts,
        # remove_entities removes. Only sets remaining after the full
        # message sequence are expanded (user may add then remove a workspace).
        active_search_sets: dict[str, tuple[dict, str]] = {}
        messages_raw = getattr(request, "messages", None) or []

        for msg in messages_raw:
            msg_type = _field(msg, "type")
            content = _field(msg, "content")

            if msg_type == "add_entities":
                if isinstance(content, list):
                    for entity in content:
                        eid = _field(entity, "entity_id", "")
                        if eid:
                            context_docs.append(eid)

            elif msg_type == "remove_entities":
                if isinstance(content, list):
                    for entity in content:
                        eid = _field(entity, "entity_id", "")
                        if eid:
                            # Remove from explicit docs
                            context_docs = [d for d in context_docs if d != eid]
                            # Remove matching search set
                            active_search_sets.pop(eid, None)

            elif msg_type == "remove_search_set":
                if content is not None:
                    ss_id = _field(content, "entity_id", "")
                    if ss_id:
                        active_search_sets.pop(ss_id, None)

            elif msg_type == "add_search_set":
                if content is not None:
                    ss_query = _field(content, "query", {})
                    ss_label = _field(content, "entity_label", "")
                    ss_id = _field(content, "entity_id", "")
                    if ss_query:
                        active_search_sets[ss_id or ss_label] = (ss_query, ss_label)

        # Anything that silently shrinks the corpus is collected here and travels with
        # the state. A partial corpus that looks complete is the failure mode this
        # whole layer exists to avoid.
        scope_warnings: list[str] = []
        if active_search_sets:
            ontology = getattr(request, "ontology", "") or ""
            timbr_token = getattr(request, "timbr_token", "") or ""
            username = state.get("username", "")
            for ss_query, ss_label in active_search_sets.values():
                try:
                    expanded = await expand_search_set(
                        ss_query, ontology, timbr_token, username=username
                    )
                    expanded_ids = [e["entity_id"] for e in expanded]
                    logger.info(
                        "load_context: expanded search set '%s' → %d entities",
                        ss_label,
                        len(expanded_ids),
                    )
                    # dict.fromkeys, not set(): a set of strings iterates in an
                    # order that depends on the per-process hash seed, and this order
                    # reaches entity_context, which reaches the prompt. Two identical
                    # runs must not build two different prompts.
                    context_docs = list(dict.fromkeys(context_docs + expanded_ids))
                except Exception as e:
                    logger.error(
                        "load_context: failed to expand search set '%s': %s — "
                        "the answer will be built over a REDUCED corpus",
                        ss_label,
                        e,
                    )
                    scope_warnings.append(
                        f"search set '{ss_label}' could not be expanded: its documents "
                        "are NOT in scope for this answer"
                    )

        msg_types = [_field(m, "type") for m in messages_raw]
        logger.info(
            "load_context: %d messages, types=%s, %d context_docs, %d search_sets",
            len(messages_raw),
            msg_types,
            len(context_docs),
            len(active_search_sets),
        )

        # Build LangChain messages + extract follow-up doc IDs from the last 2
        # assistant responses (most recent context for drill-down follow-ups)
        messages = []
        assistant_contents: list[str] = []
        for msg in messages_raw:
            msg_role = _field(msg, "role")
            msg_content = _field(msg, "content")
            if isinstance(msg_content, str) and msg_content:
                if msg_role == "user":
                    messages.append(HumanMessage(content=msg_content))
                elif msg_role == "assistant":
                    messages.append(AIMessage(content=msg_content))
                    assistant_contents.append(msg_content)

        followup_doc_ids: list[str] = []
        for text in assistant_contents[-_FOLLOWUP_RESPONSE_WINDOW:]:
            for eid, _etype in _ENTITY_LINK_RE.findall(text):
                if eid not in followup_doc_ids:
                    followup_doc_ids.append(eid)

        if followup_doc_ids:
            logger.info(
                "load_context: %d docs referenced in last 2 responses",
                len(followup_doc_ids),
            )

        return (
            query,
            workspace_id,
            context_docs,
            followup_doc_ids,
            messages,
            scope_warnings,
        )

    # ------------------------------------------------------------------
    # Build document context
    # ------------------------------------------------------------------

    async def _build_document_context(
        self,
        context_docs: list[str],
        workspace_id: str,
        query: str,
        config: RunnableConfig | None,
    ) -> tuple[str, int, bool, list[str], dict]:
        """Build entity_context, count chunks, fetch NER.

        Returns (entity_context, total_chunks, has_fragments, document_languages, doc_ner_entities).
        """
        entity_context = ""
        total_chunks = 0
        has_fragments = False
        document_languages: list[str] = []

        if context_docs or workspace_id:
            try:
                total_chunks, has_fragments = await asyncio.gather(
                    count_scope_entities(
                        entity_ids=context_docs or None,
                        workspace_id=workspace_id,
                        config=config,
                    ),
                    check_has_fragments(
                        entity_ids=context_docs or None,
                        workspace_id=workspace_id,
                        config=config,
                    ),
                )
                get_search_context(config).has_fragments = has_fragments
            except Exception as e:
                logger.warning("load_context: scope check failed: %s", e)
                total_chunks = 0

        if context_docs:
            doc_metadata, doc_labels, document_languages = (
                await build_document_metadata(context_docs, config)
            )
            get_search_context(config).doc_labels = doc_labels
            parts = [
                f"--- [{doc_labels.get(did, did)}](entity:{did}/os_file) ---\n"
                + f"{doc_metadata.get(did, '[Metadata unavailable]')}"
                for did in context_docs
            ]
            entity_context = "\n".join(parts)

        doc_ner_entities: dict = {}
        if context_docs:
            try:
                doc_ner_entities = await fetch_ner_entities(context_docs, config)
                if doc_ner_entities:
                    ner_summary = {k: len(v) for k, v in doc_ner_entities.items()}
                    logger.debug("load_context: NER entities: %s", ner_summary)
            except Exception as e:
                logger.warning("load_context: NER extraction failed: %s", e)

        return (
            entity_context,
            total_chunks,
            has_fragments,
            document_languages,
            doc_ner_entities,
        )
