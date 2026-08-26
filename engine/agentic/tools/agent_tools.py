"""Agent tools factory — builds LangChain tools with workspace/context scope in closures.

The LLM does NOT need to pass workspace_id — it's forced at code level.
When context_doc_ids is set, ALL tools filter by those entity_ids + their fragments.

Tools:
  - retrieval          — hybrid search (FTS + KNN → RRF), returns summaries
  - full_text_search   — BM25 keyword search, returns highlights
  - semantic_search    — KNN vector search, returns full page text (snowball)
  - read_fragment      — read a specific page by entity_id
  - list_documents     — list all documents in scope
  - find_recurring_names       — names appearing across multiple documents
  - find_cross_document_patterns — search terms across documents (frequency matrix)
  - investigate                — flag a lead for the blackboard
"""

import asyncio
import json
import logging

from ..blackboard import Blackboard

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool as lc_tool

from .retrieval import semantic_retrieval, knn_search
from ..config import MAX_RETRIEVAL_TOOL_RESULTS
from .opensearch_repository import (
    full_text_search as dao_full_text_search,
    fetch_entity_content,
    fetch_fragment_content,
    fetch_entities_by_ids,
    list_workspace_docs_agg,
    get_unique_doc_ids,
    search_term_across_docs,
)
from .cross_document import do_find_recurring_names
from ..config import MAX_CROSS_DOC_TERMS

logger = logging.getLogger(__name__)


# TODO(NER): list_all_entities_by_type tool removed — NER quality from NiFi is
# too poor to be useful (false positives: "egualmente"→person, "famiglia"→loc).
# The LLM fallback was a reimplementation of map_reduce. Instead, understand_query
# should route "list all X" queries to map_reduce strategy which reads each doc
# and extracts entities with full document context.
# When NiFi NER improves, re-add this tool reading from the NER index directly.


async def build_agent_tools(
    workspace_id: str = "",
    suite: str = "",
    context_doc_ids: list[str] | None = None,
    key_terms: list[str] | None = None,
    config: RunnableConfig | None = None,
    investigation_queue: Blackboard | None = None,
) -> list:
    """Build all agent tools with scope hardcoded in closures."""
    _ws = workspace_id
    _ctx_docs = context_doc_ids or []
    _key_terms = key_terms or []
    _cfg = config
    _board = investigation_queue
    _read_fragments: set[str] = set()
    _seen_summaries: set[str] = set()
    _executed_searches: set[str] = set()
    _executed_reads: set[str] = set()  # exact read_fragment call keys

    @lc_tool(
        description=(
            "Broad hybrid search combining keywords + semantic similarity. "
            "Returns SUMMARIES of matching pages — not the full text. "
            "Searches ALL documents in scope by default. "
            "entity_names narrows to specific documents — pass MULTIPLE names in one call, "
            "NEVER call once per document. "
            "For targeted lookups, prefer full_text_search or semantic_search. "
            "Use read_fragment with entity_id from results to get full page content."
        )
    )
    async def retrieval(query: str, entity_names: list[str] | None = None) -> str:  # type: ignore[assignment]
        """Semantic search scoped to context docs or workspace."""
        scope = "|".join(sorted(entity_names)) if entity_names else ""
        search_key = f"retrieval|{query.lower().strip()}|{scope}"
        if search_key in _executed_searches:
            return json.dumps(
                {
                    "already_executed": True,
                    "next_step": (
                        "This exact search was already done. "
                        "Use semantic_search with specific values from your findings "
                        "to discover similar content in other documents."
                    ),
                }
            )
        _executed_searches.add(search_key)
        result = await semantic_retrieval(
            query,
            entity_names or None,
            _ctx_docs or None,
            _ws,
            _cfg,
            key_terms=_key_terms or None,
            max_results=MAX_RETRIEVAL_TOOL_RESULTS,
        )
        # Retrieval returns summaries — dedup summaries already seen,
        # but do NOT mark fragments as "read" (summary != full text).
        if result.get("results"):
            new_results = []
            for r in result["results"]:
                frag_id = r.get("entity_id", "")
                if frag_id in _seen_summaries:
                    continue
                _seen_summaries.add(frag_id)
                new_results.append(r)
            skipped = len(result["results"]) - len(new_results)
            if skipped > 0:
                result["results"] = new_results
                result["skipped_already_summarized"] = skipped
                if not new_results:
                    result["note"] = (
                        f"All {skipped} results already seen. "
                        "Use semantic_search with specific values from your findings "
                        "to discover similar content in other documents."
                    )
        # Mark found on blackboard (not read — agent must read_fragment)
        if _board and result.get("results"):
            for r in result["results"]:
                parent = r.get("source_file_id") or r.get("entity_id", "")
                frag_id = r.get("entity_id", "")
                label = r.get("document", "")
                if parent and frag_id:
                    _board.mark_fragment_found(parent, frag_id, label=label)
        if result.get("results"):
            result["next_step"] = (
                "These are summaries. Use read_fragment to read relevant pages in full. "
                "After extracting values, use semantic_search with those values "
                "to find similar content in other documents."
            )
        return json.dumps(result)

    @lc_tool(
        description=(
            "Keyword search (BM25) — finds pages containing EXACT terms. "
            "PRIMARY tool for factual extraction. Search in the DOCUMENT LANGUAGE. "
            "Returns HIGHLIGHTS (snippets around matches) with << >> markers. "
            "Use read_fragment to get the full page content. "
            "When highlights contain specific values, use semantic_search with those "
            "values to find similar content in other documents."
        )
    )
    async def full_text_search(query: str, size: int = 20) -> str:
        search_key = f"fts|{query.lower().strip()}"
        if search_key in _executed_searches:
            return json.dumps(
                {
                    "already_executed": True,
                    "next_step": (
                        "This exact search was already done. "
                        "Use semantic_search with specific values from your findings "
                        "to discover similar content."
                    ),
                }
            )
        _executed_searches.add(search_key)
        hits = await dao_full_text_search(
            query,
            entity_ids=_ctx_docs or None,
            workspace_id=_ws,
            size=size,
            config=_cfg,
        )
        # FTS returns highlights (snippets), not full text — mark as found, not read
        if _board and hits:
            for h in hits:
                parent = h.get("source_entity_uid") or h.get("entity_id", "")
                frag_id = h.get("entity_id", "")
                label = h.get("entity_label", "")
                if parent and frag_id:
                    _board.mark_fragment_found(parent, frag_id, label=label)
        output: dict = {"query": query, "results": hits}
        if hits:
            output["next_step"] = (
                "These are HIGHLIGHTS (snippets around matches). "
                "Use read_fragment to get the full page, then use semantic_search "
                "with specific values you find to discover similar content."
            )
        return json.dumps(output)

    @lc_tool(
        description=(
            "Semantic vector search — finds content by MEANING even when exact words differ. "
            "Returns FULL PAGE TEXT of matching pages — this IS reading the content. "
            "USE THIS FOR SNOWBALL: after finding a specific value, call semantic_search "
            "with that value to find other pages with similar content. "
            "Complements full_text_search — run both in parallel for best coverage."
        )
    )
    async def semantic_search(query: str, max_results: int = 10) -> str:
        search_key = f"semantic|{query.lower().strip()}"
        if search_key in _executed_searches:
            return json.dumps(
                {
                    "already_executed": True,
                    "next_step": (
                        "This exact search was already done. "
                        "Call semantic_search with a DIFFERENT value you extracted — "
                        "each new value finds different similar pages."
                    ),
                }
            )
        _executed_searches.add(search_key)
        result = await knn_search(
            query,
            context_entity_ids=_ctx_docs or None,
            workspace_id=_ws,
            config=_cfg,
            max_results=max_results,
        )
        # KNN returns chunk text = page content — mark as read
        if result.get("results"):
            for r in result["results"]:
                frag_id = r.get("entity_id", "")
                if frag_id:
                    _read_fragments.add(frag_id)
                if _board:
                    parent = r.get("source_file_id") or r.get("entity_id", "")
                    label = r.get("document", "")
                    if parent and frag_id:
                        _board.mark_fragment_read(parent, frag_id, label=label)
        if result.get("results"):
            result["next_step"] = (
                "This is page content found by meaning. "
                "To find MORE similar content, call semantic_search again "
                "with a specific value you extracted as the query — "
                "KNN will find other pages with similar content."
            )
        return json.dumps(result)

    @lc_tool(
        description=(
            "Read the full text of pages by entity_id. "
            "Pass MULTIPLE IDs comma-separated to read in batch (up to 10). "
            "Returns page text — this IS reading the content. "
            "After reading, call semantic_search with a sentence you found "
            "to discover similar content in other documents."
        )
    )
    async def read_fragment(fragment_ids: str) -> str:
        """Read one or more pages by entity_id. Comma-separated for batch reads."""
        # Dedup: block exact same call
        read_key = fragment_ids.strip()
        if read_key in _executed_reads:
            return json.dumps(
                {
                    "already_read": True,
                    "next_step": (
                        "You already tried reading these exact fragments. "
                        "Use semantic_search with a DIFFERENT query to find new content."
                    ),
                }
            )
        _executed_reads.add(read_key)
        ids = [fid.strip() for fid in fragment_ids.split(",") if fid.strip()]

        results = []
        skipped = 0
        for fid in ids[:5]:
            # Only allow reading fragments found by search tools
            if _board and not _board.has_entity(fid) and fid not in _read_fragments:
                skipped += 1
                continue
            if fid in _read_fragments:
                skipped += 1
                continue
            _read_fragments.add(fid)
            result = await fetch_fragment_content(fid, _cfg, neighbor_pages=0)
            if _board:
                parent_id = ""
                label = ""
                if isinstance(result, dict):
                    parent_id = result.get("source_file_id") or result.get(
                        "parent_entity_id", ""
                    )
                    label = result.get("entity_label", "")
                _board.mark_fragment_read(parent_id or fid, fid, label=label)
            results.append(result)

        if not results and skipped > 0:
            return json.dumps(
                {
                    "already_read": True,
                    "skipped": skipped,
                    "next_step": (
                        "All requested fragments already read. "
                        "Use semantic_search with a DIFFERENT query to find new content."
                    ),
                }
            )
        if len(results) == 1:
            return json.dumps(results[0])
        return json.dumps({"fragments_read": len(results), "results": results})

    @lc_tool(
        description=(
            "Read a FULL document by its entity_id (the os_file ID, not fragment ID). "
            "USE WHEN: you need ≥50% of the fragments of a document — cheaper than "
            "multiple read_fragment calls. Check `total_pages` from prior retrieval "
            "results: if you'd need to read more than half of them, call read_document "
            "once instead of many read_fragment calls. "
            "For few scattered pages (<50% of total), use read_fragment instead."
        )
    )
    async def read_document(doc_id: str) -> str:
        """Read full document content by entity_id."""
        result = await fetch_entity_content(doc_id.strip(), _cfg)
        return json.dumps(result)

    @lc_tool(
        description=(
            "List all documents in scope with their entity_id and label. "
            "Use to see what files are available before searching."
        )
    )
    async def list_documents() -> str:
        docs = (
            await fetch_entities_by_ids(_ctx_docs, _cfg)
            if _ctx_docs
            else await list_workspace_docs_agg(_ws, _cfg)
        )
        return json.dumps(docs)

    @lc_tool(
        description=(
            "Find names (persons, orgs, places) that appear in 2 OR MORE documents. "
            "USE FOR: 'recurring name', 'common name', 'shared name', 'name that appears "
            "in multiple/all/several documents', 'who is mentioned across documents', "
            "'entity in common', 'repeated across files', 'central figure', 'main person "
            "in the case', 'who appears everywhere', or ANY question asking which name/person "
            "connects multiple documents. Similar queries: 'nombre recurrente', 'persona "
            "en comun', 'que nombre aparece en todos', 'protagonista', 'figura central'. "
            "Returns ranked list of names with the count of documents each appears in. "
            "Fast — uses pre-indexed NER, zero retrieval calls. "
            "CALL THIS FIRST for any cross-document name/entity question, BEFORE retrieval "
            "or read_fragment. Do NOT try to piece this together from individual doc reads."
        )
    )
    async def find_recurring_names() -> str:
        ids = _ctx_docs or await get_unique_doc_ids(_ws, _cfg)
        if not ids:
            return json.dumps({"error": "No documents found"})
        results = await do_find_recurring_names(ids, _cfg)
        return json.dumps(
            {
                "recurring_names": results,
                "documents_analyzed": len(ids),
                "total_recurring": len(results),
            }
        )

    @lc_tool(
        description=(
            "Search specific terms across documents — returns frequency matrix. "
            "ONLY use when user asks to compare term frequency across docs. "
            "For finding info about a term, use retrieval or full_text_search instead."
        )
    )
    async def find_cross_document_patterns(search_terms: list[str]) -> str:
        if not search_terms:
            return json.dumps({"error": "search_terms required"})
        ids = _ctx_docs or await get_unique_doc_ids(_ws, _cfg)
        if not ids:
            return json.dumps({"error": "No documents found"})
        # Parallel search for all terms
        tasks = [
            search_term_across_docs(term, ids, _cfg)
            for term in search_terms[:MAX_CROSS_DOC_TERMS]
        ]
        found_list = await asyncio.gather(*tasks)
        results = {}
        for term, found in zip(search_terms[:MAX_CROSS_DOC_TERMS], found_list):
            if found:
                results[term] = found
        cross_doc = {t: docs for t, docs in results.items() if len(docs) >= 2}
        return json.dumps(
            {
                "patterns": results,
                "cross_document_matches": cross_doc,
                "documents_searched": len(ids),
                "terms_searched": len(search_terms),
            }
        )

    @lc_tool(
        description=(
            "Note an important discovery or flag something to check later. "
            "Use sparingly — only for key findings or new leads, not every tool result."
        )
    )
    async def investigate(note: str) -> str:
        """Record a finding or lead on the blackboard."""
        if _board is None:
            return json.dumps({"ok": False, "note": "No blackboard active"})
        _board.add_finding(note)
        return _board.add_lead(note)

    @lc_tool(
        description=(
            "Analyze tabular data with pandas. You MUST first extract the data "
            "from the document (via read_fragment or retrieval) and format it as "
            "CSV text. Pass the CSV and an optional filter query.\n"
            "The tool always returns: row_count, columns, sample rows, and "
            "per-column stats — value_counts (top 10) for text columns, "
            "sum/mean/min/max for numeric columns. These stats cover most needs "
            "(counts per category come from value_counts).\n"
            "The optional `query` argument is a pandas .query() boolean filter "
            "expression — NOT arbitrary Python. It selects rows; the tool then "
            "returns the filtered sample + query_matched_rows (use this for "
            "counts). Column names with spaces must be wrapped in backticks.\n"
            "Examples:\n"
            '  analyze_table(csv_text="Name,Class\\nJohn,First\\nJane,Economy", '
            "query='Class == \"First\"')  # query_matched_rows = count\n"
            '  analyze_table(csv_text="Amount,Currency\\n500,USD\\n1200,EUR", '
            "query='Amount > 1000')"
        )
    )
    async def analyze_table(csv_text: str, query: str = "") -> str:
        """Parse CSV into pandas DataFrame, return stats or run a query."""
        import io

        import pandas as pd  # type: ignore[import-untyped]

        try:
            df = pd.read_csv(io.StringIO(csv_text.strip()))
        except Exception as exc:
            return json.dumps({"error": f"Failed to parse CSV: {exc}"})

        result: dict = {
            "row_count": len(df),
            "columns": list(df.columns),
            "sample_rows": json.loads(df.head(5).to_json(orient="records") or "[]"),
        }

        # Per-column stats
        col_stats = {}
        for col in df.columns:
            series = df[col]
            if pd.api.types.is_numeric_dtype(series):
                col_stats[col] = {
                    "type": "numeric",
                    "sum": float(series.sum()),  # type: ignore[arg-type]
                    "mean": float(series.mean()),  # type: ignore[arg-type]
                    "min": float(series.min()),  # type: ignore[arg-type]
                    "max": float(series.max()),  # type: ignore[arg-type]
                }
            else:
                vc = series.value_counts().head(10)
                col_stats[col] = {
                    "type": "text",
                    "unique": int(series.nunique()),  # type: ignore[arg-type]
                    "top_values": vc.to_dict(),
                }
        result["column_stats"] = col_stats

        # Run custom filter if provided (pandas query syntax, safe subset — no arbitrary code)
        if query:
            try:
                filtered = df.query(query)
                result["query_result"] = json.loads(
                    filtered.head(50).to_json(orient="records") or "[]"
                )
                result["query_matched_rows"] = len(filtered)
            except Exception as exc:
                result["query_error"] = (
                    f"{exc}. Use pandas .query() syntax, e.g. \"col > 5 and name == 'foo'\"."
                )

        return json.dumps(result, default=str)

    all_tools = [
        retrieval,
        full_text_search,
        semantic_search,
        read_fragment,
        read_document,
        list_documents,
        find_recurring_names,
        find_cross_document_patterns,
        analyze_table,
    ]
    if _board is not None:
        all_tools.append(investigate)

    return all_tools
