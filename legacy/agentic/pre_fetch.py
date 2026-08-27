"""Pre-fetch node — runs retrieval before the strategy.

Responsibilities:
1. Run semantic retrieval (FTS + Entity + KNN → RRF) using the rewritten query.
2. Discovery mode (no scope): extract doc IDs from results to scope downstream.
3. Enrich entity_context: mark prefetched docs as relevant, append summaries.
"""

import logging

from langchain_core.runnables import RunnableConfig

from .state import OrchestratorState, get_scoped_doc_ids
from .tools.retrieval import semantic_retrieval
from .utils import emit_ui_event

logger = logging.getLogger(__name__)


async def pre_fetch(
    state: OrchestratorState, config: RunnableConfig | None = None
) -> dict:
    """Run retrieval subgraph before the strategy.

    When no documents are in scope (no context_doc_ids, no workspace_id),
    this acts as a **discovery** step: extracts unique parent doc IDs from
    the retrieval results and sets context_doc_ids so all downstream
    strategies are properly scoped instead of searching everything.
    """

    query = state.get("rewritten_query") or state.get("query", "")
    key_terms = state.get("key_terms", [])
    context_docs = get_scoped_doc_ids(state)
    ws = state.get("workspace_id", "")
    no_scope = not context_docs and not ws

    await emit_ui_event(config, "Searching documents...")

    hyde_queries = state.get("hyde_queries", [])
    prefetch_data = await semantic_retrieval(
        query,
        None,
        context_docs or None,
        ws,
        config,
        key_terms=list(key_terms) or None,
        include_summaries=True,
        hyde_queries=hyde_queries,
    )
    if prefetch_data.get("total_results", 0) > 0:
        result_count = len(prefetch_data.get("results", []))
        logger.info("pre_fetch: %d results", result_count)
        await emit_ui_event(
            config,
            f"Found {result_count} relevant sections",
        )
        update: dict = {"prefetch_results": prefetch_data}

        if no_scope:
            _discover_docs(prefetch_data, update)
            if update.get("context_doc_ids"):
                await emit_ui_event(
                    config,
                    f"Discovered {len(update['context_doc_ids'])} relevant documents",
                )

        _enrich_entity_context(prefetch_data, state, update)

        return update

    # No relevant results found — let the strategy know
    logger.warning("pre_fetch: no relevant results found")
    await emit_ui_event(config, "No relevant documents found for this query")
    return {"prefetch_results": {}}


def _discover_docs(prefetch_data: dict, update: dict) -> None:
    """Discovery mode: extract doc IDs from results, scope downstream."""
    discovered: list[str] = []
    doc_labels: dict[str, str] = {}
    for r in prefetch_data.get("results", []):
        doc_id = r.get("source_file_id") or r.get("entity_id", "")
        if doc_id and doc_id not in discovered:
            discovered.append(doc_id)
            label = r.get("document", doc_id)
            if " (page " in label:
                label = label.rsplit(" (page ", 1)[0]
            doc_labels[doc_id] = label

    if not discovered:
        return

    update["context_doc_ids"] = discovered
    has_frags = any(r.get("source_file_id") for r in prefetch_data.get("results", []))
    if has_frags:
        update["has_fragments"] = True

    # No entity_context here: _enrich_entity_context runs right after and rebuilds
    # it from the same results with more detail. This branch used to write one too,
    # and it was overwritten every single time -- dead work that read as a fallback.
    logger.info(
        "pre_fetch: discovery mode — scoped to %d docs from results",
        len(discovered),
    )


def _enrich_entity_context(
    prefetch_data: dict,
    state: OrchestratorState,
    update: dict,
) -> None:
    """Rebuild entity_context with only relevant docs/pages from prefetch.

    Groups results by parent doc (source_file_id), shows the doc header
    with relevant pages and their summaries underneath.
    """
    doc_summaries = prefetch_data.get("doc_summaries", {})
    results = prefetch_data.get("results", [])
    if not results:
        return

    # Group results by parent doc
    # {parent_doc_id: [{entity_id, label, page, summary}, ...]}
    doc_pages: dict[str, list[dict]] = {}
    doc_labels: dict[str, str] = {}
    for r in results:
        parent_id = r.get("source_file_id") or r.get("entity_id", "")
        if not parent_id:
            continue
        page_label = r.get("document", "")
        page_num = r.get("page")
        entity_id = r.get("entity_id", "")
        entity_type = r.get("entity_type", "os_fragment")

        # Track parent doc label (strip page suffix)
        if parent_id not in doc_labels:
            label = page_label
            if " (page " in label:
                label = label.rsplit(" (page ", 1)[0]
            # For fragments, remove _pageNNN suffix from label
            for suffix in (".pdf", ".tiff", ".jpg", ".png"):
                if "_page" in label and label.endswith(suffix):
                    parts = label.rsplit("_page", 1)
                    if len(parts) == 2:
                        label = parts[0] + suffix
                        break
            doc_labels[parent_id] = label

        if parent_id not in doc_pages:
            doc_pages[parent_id] = []

        summary = doc_summaries.get(entity_id, "") or doc_summaries.get(parent_id, "")
        doc_pages[parent_id].append(
            {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "label": page_label,
                "page": page_num,
                "summary": summary,
            }
        )

    # Build entity_context grouped by parent doc
    lines = []
    for parent_id, pages in doc_pages.items():
        label = doc_labels.get(parent_id, parent_id)
        lines.append(f"--- [{label}](entity:{parent_id}/os_file) ---")
        for p in pages:
            page_info = (
                f"  - [{p['label']}](entity:{p['entity_id']}/{p['entity_type']})"
            )
            if p.get("page"):
                page_info += f" (page {p['page']})"
            if p.get("summary"):
                page_info += f"\n    Summary: {p['summary']}"
            lines.append(page_info)

    if lines:
        # The hints understand() appended (its key_terms) are carried over rather
        # than discarded. Rebuilding entity_context from scratch used to delete them
        # before any strategy saw them: the whole point of extracting search terms
        # was lost between two nodes.
        rebuilt = "\n".join(lines)
        previous = state.get("entity_context", "")
        marker = "\n\n## Search hints\n"
        if marker in previous:
            rebuilt += marker + previous.split(marker, 1)[1]
        update["entity_context"] = rebuilt
        logger.info(
            "pre_fetch: entity_context rebuilt with %d docs, %d relevant pages",
            len(doc_pages),
            sum(len(p) for p in doc_pages.values()),
        )
