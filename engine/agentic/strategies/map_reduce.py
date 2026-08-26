"""Map-reduce strategy — parallel per-document extraction + merge.

Flow:
  mr_list_docs → mr_fan_out → [mr_process_document × N] → mr_merge_and_answer

Each document is read via fetch_entity_content, which issues 2 OpenSearch
queries per document regardless of page count:
  1. Fetch the os_file metadata (1 query, size=1)
  2. Fetch all os_fragment texts sorted by page number (1 query, size=2000)
So a 1000-page document costs 2 OS queries, not 1000. The fragment texts
are concatenated in memory and passed to the LLM as a single string.

If the concatenated text exceeds MAX_CHUNKS_PER_LLM_CALL chars, it's split
into parts and each part gets its own LLM call (parallel).

Budget: MAX_MAP_REDUCE_LLM_CALLS (20) total documents processed.
"""

import logging
import re
from collections.abc import Mapping
from typing import Any

from langchain_core.callbacks import adispatch_custom_event
from langchain_core.language_models import BaseChatModel
from langgraph.types import Send
from langchain_core.runnables import RunnableConfig

import asyncio as _aio

from ..tools.opensearch_repository import list_workspace_docs_agg, fetch_entity_content
from ..config import (
    MAX_CHUNKS_PER_LLM_CALL,
    MAX_MAP_REDUCE_LLM_CALLS,
    TEMP_EXTRACT,
    TEMP_FORMAT,
    get_chat_model,
)
from ..agent_config import (
    OUTPUT_FORMAT_PROMPT,
    DOMAIN_INSTRUCTIONS,
    MAP_REDUCE_MAP_PROMPT,
    MAP_REDUCE_MERGE_PROMPT,
)
from ..state import OrchestratorState, DocProcessState, get_scoped_doc_ids
from ..utils import build_aggregate_messages

# Max chars per LLM call. ~4K chars per chunk × MAX_CHUNKS_PER_LLM_CALL (80) = 320K.
# Documents larger than this are split into parts.
_MAX_CHARS_PER_CALL = MAX_CHUNKS_PER_LLM_CALL * 4000

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 1: List documents to process
# ---------------------------------------------------------------------------


async def mr_list_docs(state: OrchestratorState, config: RunnableConfig) -> dict:
    """List documents to process — from context_doc_ids or workspace.

    When context_doc_ids are set (user opened specific files), use those.
    Otherwise list all top-level docs in the workspace via aggregation.
    Returns os_file IDs — fetch_entity_content reads their full content
    (concatenating all fragment pages when has_fragments=True).
    """
    context_docs = get_scoped_doc_ids(state)

    if context_docs:
        # Use the doc IDs the user has open (may be os_file or os_fragment IDs)
        docs = [{"doc_id": eid} for eid in context_docs]
        logger.info("mr_list_docs: %d docs from context_doc_ids", len(docs))
        return {"documents": docs}

    # Only list workspace docs when a single workspace_id is set.
    # Without it, the aggregation would scan the full index unscoped.
    ws = state.get("workspace_id", "")
    if not ws:
        logger.warning(
            "mr_list_docs: no context_doc_ids and no workspace_id — nothing to process"
        )
        return {"documents": []}

    raw = await list_workspace_docs_agg(ws, config)
    docs = [{**d, "doc_id": d["entity_id"]} for d in raw]
    logger.info("mr_list_docs: %d docs from workspace", len(docs))
    return {"documents": docs}


# ---------------------------------------------------------------------------
# Phase 2: Fan-out — one Send per document (parallel LangGraph execution)
# ---------------------------------------------------------------------------


def mr_fan_out(state: OrchestratorState) -> list[Send] | str:
    """Fan out: one Send per document, capped at MAX_MAP_REDUCE_LLM_CALLS.

    Each doc gets at least 1 LLM call (more if the doc is split into parts).
    If there are more docs than the budget allows, only the first N are processed.
    """
    docs = state.get("documents", [])
    if not docs:
        logger.warning("mr_fan_out: no documents — skipping to merge")
        return "mr_merge_and_answer"

    # Cap to budget — each doc costs at least 1 LLM call
    if len(docs) > MAX_MAP_REDUCE_LLM_CALLS:
        logger.warning(
            "mr_fan_out: capping %d docs to %d",
            len(docs),
            MAX_MAP_REDUCE_LLM_CALLS,
        )
        docs = docs[:MAX_MAP_REDUCE_LLM_CALLS]

    domain = state.get("document_domain", "general")
    query_language = state.get("query_language", "English")
    # Use rewritten_query (optimized for retrieval) or raw query as fallback
    query = state.get("rewritten_query") or state["query"]

    return [
        Send(
            "mr_process_document",
            {
                "query": query,
                "doc_id": doc["doc_id"],
                "document_domain": domain,
                "query_language": query_language,
                "extractions": [],  # accumulator for this doc's extractions
            },
        )
        for doc in docs
    ]


# ---------------------------------------------------------------------------
# Phase 3: Process one document — read full text, extract with LLM
# ---------------------------------------------------------------------------


async def _summarize_text(
    llm_base: BaseChatModel,
    state: Mapping[str, Any],
    doc_label: str,
    text: str,
    part_num: int,
    total_parts: int,
) -> tuple[bool, str]:
    """Extract relevant information from a text segment via LLM.

    Returns (relevant, content). The LLM appends <relevant>true/false</relevant>
    at the end of its response to signal whether it found useful information.
    """
    query = state.get("query", "")
    query_language = state.get("query_language", "English")
    domain_extra = DOMAIN_INSTRUCTIONS.get(state.get("document_domain", "general"), "")

    part_info = (
        f"Document: {doc_label} (part {part_num}/{total_parts})"
        if total_parts > 1
        else f"Document: {doc_label}"
    )

    system_prompt = (
        MAP_REDUCE_MAP_PROMPT
        + f"\nCite the document as **{doc_label}** for every fact.\n"
        + f"\nYou MUST answer in {query_language}, even if the document is in another language.\n"
        + domain_extra
    )

    response = await llm_base.ainvoke(
        build_aggregate_messages(
            system_prompt, query, state, context=f"{part_info}\n{text}"
        )
    )

    raw = str(response.content).strip()

    # Parse <relevant> tag from the end of the response (case-insensitive)
    relevant = True
    content = raw
    raw_lower = raw.lower()
    if "<relevant>false</relevant>" in raw_lower:
        relevant = False
        content = ""
    elif "<relevant>" in raw_lower:
        content = re.sub(
            r"\s*<relevant>\s*\w+\s*</relevant>\s*$", "", raw, flags=re.IGNORECASE
        ).strip()

    return relevant, content


async def mr_process_document(
    state: DocProcessState,
    config: RunnableConfig,
) -> dict:
    """Read full document content and extract information relevant to the query.

    fetch_entity_content reads the full document:
    - For os_file with fragments: concatenates all page texts via _read_all_fragments_text
    - For os_fragment: reads that single page
    - For os_file without fragments: reads the file's own rag:fulltext

    If the text exceeds _MAX_CHARS_PER_CALL (~320K), splits into parts and
    processes each in parallel. Results are combined into one extraction.
    """
    doc_id = state["doc_id"]
    query = state["query"]

    # Read full document content (including all pages if os_file with fragments)
    doc_result = await fetch_entity_content(doc_id, config)
    full_text = doc_result.get("text", "")
    doc_label = str(doc_result.get("entity_label", "") or doc_id)

    if not full_text:
        return {"extractions": []}

    llm = await get_chat_model(config, None, TEMP_EXTRACT)

    if len(full_text) <= _MAX_CHARS_PER_CALL:
        # Document fits in one LLM call — process in one shot
        relevant, content = await _summarize_text(
            llm, state, doc_label, full_text, 1, 1
        )
        summaries = [content] if relevant else []
    else:
        # Document too large — split into _MAX_CHARS_PER_CALL sized parts
        parts = []
        offset = 0
        while offset < len(full_text):
            end = min(offset + _MAX_CHARS_PER_CALL, len(full_text))
            parts.append(full_text[offset:end])
            offset = end

        total_parts = len(parts)
        logger.info(
            "mr_process_document: %s split into %d parts (%d chars)",
            doc_id,
            total_parts,
            len(full_text),
        )

        # Process all parts in parallel
        tasks = [
            _summarize_text(
                llm,
                state,
                doc_label,
                part,
                i + 1,
                total_parts,
            )
            for i, part in enumerate(parts)
        ]
        results = await _aio.gather(*tasks, return_exceptions=True)

        # Collect successful and relevant summaries, log failures
        summaries = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "mr_process_document: %s part %d failed: %s",
                    doc_id,
                    i + 1,
                    result,
                )
            elif isinstance(result, tuple) and result[0]:
                summaries.append(result[1])

    # Combine all part summaries into one extraction for this document
    combined = "\n\n".join(s for s in summaries if s)
    entity_type = doc_result.get("entity_type", "os_file")
    source_doc = f"[{doc_label}](entity:{doc_id}/{entity_type})"

    # Skip docs with no relevant info — don't pollute the accumulated list
    if not combined:
        logger.info(
            "mr_process_document: %s -> %d parts, 0 chars (NOT RELEVANT, skipping)",
            doc_id,
            len(summaries),
        )
        return {"extractions": []}

    extractions = [
        {
            "name": query[:80],
            "entity_type": "chunk_summary",
            "role": "evidence",
            "context": combined,
            "source_document": source_doc,
        }
    ]

    logger.info(
        "mr_process_document: %s -> %d parts, %d chars summary",
        doc_id,
        len(summaries),
        len(combined),
    )

    return {"extractions": extractions}


# ---------------------------------------------------------------------------
# Phase 4: Merge — combine per-document extractions into final answer
# ---------------------------------------------------------------------------


async def mr_merge_and_answer(
    state: OrchestratorState, config: RunnableConfig | None = None
) -> dict:
    """Combine per-document extractions into a single coherent answer.

    Each extraction has a context (the LLM's summary of that doc) and a
    source_document link. The merge LLM synthesizes all of these into
    the final answer, with proper citations and structured formatting.
    """
    extractions = state.get("extractions", [])

    # Build one section per document — non-relevant docs were already skipped
    # in mr_process_document (empty extractions list returned).
    doc_summaries = []
    for ext in extractions:
        ctx = ext.get("context", "")
        src = ext.get("source_document", "")
        if ctx:
            doc_summaries.append(f"### From {src}\n{ctx}")

    combined = "\n\n".join(doc_summaries)

    # No extractions — nothing relevant found in any document
    if not combined:
        fallback = "No relevant information found in the documents."
        if config:
            await adispatch_custom_event(
                name="on_ui_event",
                data={"channel": "text", "content": fallback},
                config=config,
            )
        return {"answer": fallback}

    # Final synthesis: merge all document summaries into one answer (streaming)
    llm = await get_chat_model(config, None, TEMP_FORMAT, streaming=True)
    response = await llm.ainvoke(
        build_aggregate_messages(
            MAP_REDUCE_MERGE_PROMPT
            + "\n\n"
            + OUTPUT_FORMAT_PROMPT.format(
                query_language=state.get("query_language", "English")
            ),
            state["query"],
            state,
            context=combined,
        )
    )

    return {"answer": response.content}
