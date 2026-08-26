"""Query understanding: follow-up resolution, NER, rewrite, strategy classification."""

import asyncio as _aio
import logging
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from .agent_config import RESOLVE_FOLLOWUP_PROMPT, UNDERSTAND_PROMPT
from .config import (
    TEMP_CLASSIFY,
    get_chat_model,
)
from .state import OrchestratorState, format_history_turns
from .utils import emit_ui_event

logger = logging.getLogger(__name__)

STRATEGY_LABELS = {
    "react_agent": "Searching and analyzing",
    "react_agent_exhaustive": "Exhaustive search and analyzing",
    "map_reduce": "Summarizing all documents",
    "plan_execute": "Complex task execution",
    "dag": "Multi-query decomposition",
    "conversational": "Responding",
}


# ---------------------------------------------------------------------------
# Structured output schemas
# ---------------------------------------------------------------------------


class FollowupResult(BaseModel):
    """Structured output for follow-up resolution — classification only, no rewriting."""

    followup_type: Literal["standalone", "drill_down", "expansive"] = Field(
        default="standalone",
        description=(
            "standalone: new topic or generic command. "
            "drill_down: more detail on something already in the prior response. "
            "expansive: references conversation topic but asks about something NOT in the prior response."
        ),
    )


class ExtractedEntity(BaseModel):
    name: str = Field(description="Entity name, e.g. 'Valerio Simoni'")
    type: str = Field(
        default="", description="Entity type, e.g. 'person', 'location', 'document'"
    )


class UnderstandResult(BaseModel):
    extracted_entities: list[ExtractedEntity] = Field(
        default_factory=list,
        description="Named entities extracted from the query",
    )
    rewritten_query: str = Field(
        default="",
        description=(
            "Query rewritten for optimal retrieval. Keep it SHORT (1-2 sentences). "
            "Do NOT include document names, context, or metadata — only the question. "
            "MUST stay in the SAME language as the user's question — NEVER translate. "
            "If user asked in English, rewrite in English. Include key entity names. "
            "If chat history is provided (follow-up), resolve pronouns and references "
            "to actual names from the history, but keep the query language unchanged."
        ),
    )
    key_terms: list[str] = Field(
        default_factory=list,
        description=(
            "8-20 key search terms for retrieval. Include: "
            "1) terms in the document language AND English, "
            "2) specific numbers, article numbers, dates, and identifiers mentioned in the query, "
            "3) related concepts and synonyms the documents might use instead of the user's words. "
            "Think about what words the DOCUMENTS would use, not just the user's words."
        ),
    )
    entity_types_filter: list[str] = Field(
        default_factory=list,
        description=(
            "Which 1-2 NER entity types are MOST relevant to answering this query. "
            "Pick ONLY from the 'Available NER entity types' listed in the context. "
            "E.g. 'who is the victim' → ['person'], "
            "'when was he killed' → ['date'], "
            "'where did it happen' → ['loc'], "
            "'what address' → ['loc'], "
            "'recurring names across documents' → ['person'], "
            "'which organizations' → ['org'], "
            "'contact info' → ['phone', 'email']. "
            "Empty = no NER filtering needed."
        ),
    )
    document_domain: str = Field(
        default="general",
        description=(
            "Detected domain: legal, financial, forensic, criminology, intelligence, general. "
            "court/judgment/appeal → legal, SAR/bank/transaction → financial, "
            "victim/DNA/autopsy → forensic, trafficking/recruiter → criminology."
        ),
    )
    complexity: Literal["simple", "moderate", "complex"] = Field(
        default="moderate",
        description=(
            "Query complexity. simple: single fact lookup (name, date, yes/no). "
            "moderate: requires reading 1-3 documents. "
            "complex: requires comparing multiple documents, extracting exhaustive lists, "
            "or analyzing across multiple phases/years/subjects."
        ),
    )
    needs_decomposition: bool = Field(
        default=False,
        description=(
            "True when the query contains MULTIPLE INDEPENDENT sub-questions that "
            "benefit from being answered separately and then combined. Examples: "
            "'For each judgment from 2009 to 2016, state the outcome' (one sub-Q per year), "
            "'Compare X across documents A, B, C' (one sub-Q per document). "
            "False for single questions even if complex: 'extract all addresses of X' "
            "is ONE question answered by scanning documents, not multiple sub-questions."
        ),
    )
    exhaustive_extraction: bool = Field(
        default=False,
        description=(
            "True when the query demands COMPLETENESS — finding all items or "
            "covering all instances across the document set. Set True if ANY of: "
            "(1) 'extract ALL X', 'list ALL X', 'find ALL X' — exhaustive list of entities; "
            "(2) 'for each X', 'separately for each X' — iterate over multiple items/years/phases; "
            "(3) 'how many X' when X requires scanning multiple documents; "
            "(4) 'who are the most/all X', 'are there other X', 'are there names that appear both as A and B' — "
            "requires scanning many docs to compare/aggregate; "
            "(5) 'is X part of a larger ring/network' — requires gathering all evidence. "
            "Set False ONLY for: images/photos, single-document extraction, "
            "summaries, timelines, simple yes/no questions, specific fact lookups "
            "in 1-2 docs ('what is the victim's name')."
        ),
    )
    strategy: Literal[
        "react_agent",
        "map_reduce",
        "plan_execute",
        "conversational",
    ] = Field(
        default="react_agent",
        description="Best strategy for this query (used only for conversational detection)",
    )
    reasoning: str = Field(
        default="",
        description="One sentence explaining why this strategy was chosen",
    )


# ---------------------------------------------------------------------------
# QueryUnderstanding
# ---------------------------------------------------------------------------


class QueryUnderstanding:
    """LangGraph node: analyse the user query before strategy execution.

    Two-step process using lightweight (mini) LLM calls:

    1. **Follow-up classification** (_resolve_followup):
       - Classifies whether the query is standalone, drill_down, or expansive.
       - Does NOT rewrite the query — keeps the original language intact.
       - Sets followup_type so downstream nodes can scope searches correctly.

    2. **Strategy classification** (_classify):
       - Uses structured output (UnderstandResult) to produce in a single call:
         rewritten_query, key_terms, entity_types_filter, document_domain,
         query_language, and the chosen strategy.
       - For follow-ups, includes chat history so rewritten_query can resolve
         pronouns/references while preserving the original query language.
       - Guards: map_reduce on scopes >10 000 chunks or >20 docs falls back to plan_execute.

    State fields produced:
        strategy, rewritten_query, router_reasoning, document_domain,
        entity_context (with search hints appended), key_terms,
        entity_types_filter, doc_ner_entities, query, history_relevant,
        query_language.
    """

    async def __call__(
        self,
        state: OrchestratorState,
        config: RunnableConfig | None = None,
    ) -> dict:
        query = state.get("query", "")
        messages = state.get("messages", [])
        context_docs = state.get("context_doc_ids", [])
        entity_context = state.get("entity_context", "")
        followup_doc_ids = state.get("followup_doc_ids", [])

        # Forced strategy override (from ChatRequest.strategy) — bypass LLM classification.
        # Unknown values fall back to react_agent rather than crashing downstream.
        forced = (state.get("forced_strategy") or "").strip()
        if forced and forced not in STRATEGY_LABELS:
            logger.warning(
                "understand: unknown forced_strategy=%r, falling back to react_agent",
                forced,
            )
            forced = "react_agent"
        if forced:
            logger.info("understand: forced_strategy=%s (bypassing classifier)", forced)
            label = STRATEGY_LABELS.get(forced, forced)
            await emit_ui_event(config, label)
            return {
                "strategy": forced,
                "rewritten_query": query,
                "router_reasoning": f"forced via request.strategy={forced}",
                "key_terms": [],
                "entity_types_filter": [],
                "document_domain": "general",
                "complexity": "moderate",
                "history_relevant": False,
                "followup_type": "standalone",
                "query_language": "English",
                "history_text": "",
            }

        # Step 1: Detect query language + classify follow-up type (parallel, no doc context)
        query_language, followup_type = await _aio.gather(
            self._detect_language(query, config),
            self._resolve_followup(query, messages, followup_doc_ids, config),
        )
        history_relevant = followup_type != "standalone"
        history_text = format_history_turns(messages) if history_relevant else ""

        # Step 2: Classify strategy + extract key_terms, domain, entity_types
        result = await self._classify(
            query, state, context_docs, config, followup_type, history_text
        )

        # Routing:
        #   conversational → conversational
        #   multi-query (needs_decomposition) → dag (plan + waves + verify)
        #   single-query → react_agent (exhaustive mode if exhaustive_extraction)
        if result.strategy == "conversational":
            strategy = "conversational"
            reasoning = result.reasoning
        elif result.needs_decomposition:
            strategy = "dag"
            reasoning = (
                f"dag (needs_decomposition, {result.complexity}, {result.reasoning})"
            )
        elif result.complexity == "complex":
            strategy = "react_agent_exhaustive"
            reasoning = f"react_agent_exhaustive ({result.reasoning})"
        else:
            strategy = "react_agent"
            reasoning = f"react_agent ({result.complexity}, {result.reasoning})"

        # Strategy guards — currently inactive since strategy is always react_agent.
        # Kept for reference if specialized strategies are re-enabled.
        # total_chunks = state.get("total_chunks", 0)
        # workspace_id = state.get("workspace_id", "")
        # followup_docs = state.get("followup_doc_ids", [])
        # if (
        #     not context_docs and not workspace_id and not followup_docs
        #     and strategy in ("map_reduce", "plan_execute")
        # ):
        #     strategy = "react_agent"
        # elif strategy == "map_reduce" and total_chunks > 10000:
        #     strategy = "plan_execute"
        # effective_docs = (
        #     state.get("followup_doc_ids", []) if followup_type == "drill_down"
        #     else context_docs
        # )
        # if strategy == "map_reduce" and len(effective_docs) > MAX_MAP_REDUCE_LLM_CALLS:
        #     strategy = "plan_execute"

        # Follow-up emit
        if history_relevant:
            label = (
                f"Drill-down: {len(followup_doc_ids)} referenced documents"
                if followup_type == "drill_down" and followup_doc_ids
                else (
                    f"Expansive follow-up: searching all documents"
                    if followup_type == "expansive"
                    else "Follow-up"
                )
            )
            await emit_ui_event(config, label)

        if result.key_terms:
            entity_context += (
                f"\n\n## Search hints\n"
                f"Use these terms for better results: {', '.join(result.key_terms)}"
            )

        rewritten_query = result.rewritten_query or query
        document_domain = result.document_domain or "general"

        logger.info(
            "understand_query: strategy=%s | exhaustive=%s | complexity=%s | decompose=%s | domain=%s | lang=%s | docs=%d | followup=%d | terms=%s | ner_filter=%s | %s",
            strategy,
            result.complexity == "complex",
            result.complexity,
            result.needs_decomposition,
            document_domain,
            query_language,
            len(context_docs),
            len(followup_doc_ids),
            result.key_terms,
            result.entity_types_filter,
            reasoning,
        )

        # NER entities passed as-is
        ner_entities = state.get("doc_ner_entities", {})

        # UI events
        label = STRATEGY_LABELS.get(strategy, strategy)
        domain_suffix = f" ({document_domain})" if document_domain != "general" else ""
        await emit_ui_event(config, f"{label}{domain_suffix}", tooltip=reasoning)
        if rewritten_query and rewritten_query != query:
            await emit_ui_event(config, f"Refined query: {rewritten_query}")
        if result.key_terms:
            await emit_ui_event(config, f"Search terms: {', '.join(result.key_terms)}")
        if query_language:
            await emit_ui_event(config, f"Query language: {query_language}")

        return {
            "strategy": strategy,
            "rewritten_query": rewritten_query,
            "router_reasoning": reasoning,
            "document_domain": document_domain,
            "entity_context": entity_context,
            "key_terms": result.key_terms,
            "entity_types_filter": result.entity_types_filter,
            "doc_ner_entities": ner_entities,
            "query": query,
            "history_relevant": history_relevant,
            "history_text": history_text,
            "followup_type": followup_type,
            "query_language": query_language,
            "complexity": result.complexity,
        }

    # ------------------------------------------------------------------
    # Language detection — isolated from doc context to avoid contamination
    # ------------------------------------------------------------------

    @staticmethod
    async def _detect_language(query: str, config: RunnableConfig | None) -> str:
        """Detect the language of the user's query via a tiny LLM call.

        Runs with ONLY the query text — no document context, no entity names.
        This prevents the LLM from being confused by Italian/Hebrew/etc doc content.
        """
        try:
            llm = await get_chat_model(
                config,
                temperature=0,
                mini=True,
            )
            response = await llm.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "What language is the user writing in? "
                            "Ignore proper nouns, entity names, and foreign words — "
                            "detect the language of the SENTENCE STRUCTURE, not the names. "
                            "Reply with ONLY the language name (e.g. English, Spanish, Italian)."
                        )
                    ),
                    HumanMessage(content=query),
                ]
            )
            detected = str(response.content).strip().strip(".")
            logger.debug("_detect_language: '%s' → %s", query[:50], detected)
            return detected
        except Exception as e:
            logger.error("_detect_language failed: %s", e, exc_info=True)
            return "English"

    # ------------------------------------------------------------------
    # Step 1: Follow-up resolution
    # ------------------------------------------------------------------

    async def _resolve_followup(
        self,
        query: str,
        messages: list,
        followup_doc_ids: list[str],
        config: RunnableConfig | None,
    ) -> str:
        """Classify if query is a follow-up. Does NOT rewrite the query.

        Returns followup_type: "standalone" | "drill_down" | "expansive"
        The query stays untouched — _classify handles rewriting for retrieval.
        """
        if not messages:
            return "standalone"

        history_text = format_history_turns(messages, max_messages=4)

        doc_hint = ""
        if followup_doc_ids:
            doc_hint = "\n\nDocument IDs from prior responses:\n" + "\n".join(
                followup_doc_ids
            )

        try:
            resolve_llm = await get_chat_model(
                config,
                temperature=0,
                mini=True,
            )
            resolve_llm = resolve_llm.with_structured_output(FollowupResult)
            result: FollowupResult = await resolve_llm.ainvoke(  # type: ignore[assignment]
                [
                    SystemMessage(content=RESOLVE_FOLLOWUP_PROMPT),
                    HumanMessage(
                        content=f"History:\n{history_text}{doc_hint}\n\nQuery: {query}"
                    ),
                ]
            )

            followup_type = result.followup_type
            logger.debug(
                "understand_query: followup_type=%s for '%s'",
                followup_type,
                query[:50],
            )
            return followup_type
        except Exception as e:
            logger.error("_resolve_followup failed: %s", e, exc_info=True)
            return "standalone"

    # ------------------------------------------------------------------
    # Step 2: Classification
    # ------------------------------------------------------------------

    async def _classify(
        self,
        query: str,
        state: OrchestratorState,
        context_docs: list[str],
        config: RunnableConfig | None,
        followup_type: str = "standalone",
        history_text: str = "",
    ) -> UnderstandResult:
        """Classify the original query into strategy + metadata.

        When followup_type != "standalone", includes chat history so the LLM
        can resolve pronouns/references in rewritten_query while keeping
        the original query language intact.
        """
        llm = await get_chat_model(
            config,
            temperature=TEMP_CLASSIFY,
            mini=True,
        )
        llm = llm.with_structured_output(UnderstandResult)

        context_info = ""
        if state.get("workspace_id"):
            context_info += f"\nWorkspace: {state['workspace_id']}"
        if state.get("suite"):
            context_info += f"\nSuite: {state['suite']}"
        if context_docs:
            context_info += (
                f"\nContext docs ({len(context_docs)}): {', '.join(context_docs[:10])}"
            )

        ner_entities = state.get("doc_ner_entities", {})
        if ner_entities:
            ner_summary = ", ".join(f"{k} ({len(v)})" for k, v in ner_entities.items())
            context_info += f"\nAvailable NER entity types: {ner_summary}"

        # For follow-ups, include chat history so the LLM can resolve
        # pronouns and references in rewritten_query
        if history_text:
            context_info += f"\n\nChat history (this is a {followup_type} follow-up — resolve references in rewritten_query):\n{history_text}"

        result: UnderstandResult = await llm.ainvoke(  # type: ignore[assignment]
            [
                SystemMessage(
                    content=UNDERSTAND_PROMPT.replace(
                        "{document_languages}",
                        str(state.get("document_languages") or ["English"]),
                    )
                ),
                HumanMessage(content=f"Query: {query}{context_info}"),
            ]
        )
        return result
