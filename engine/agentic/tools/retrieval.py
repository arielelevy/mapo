"""Retrieval — hybrid semantic search orchestration (FTS + Entity + KNN + HyDE → RRF).

Invokes the semantic_search LangGraph subgraph (4 parallel branches + RRF fusion)
and formats results as JSON for LLM consumption.

Used by: retrieval agent tool, pre_fetch node, strategy sub-agents.

Chunk architecture
==================
Each OpenSearch document has nested ``annotations.rag:chunks[]``.  Every chunk
carries ``metadata.field_name`` that declares its role:

  field_name                  | content
  ----------------------------+-------------------------------------------------
  annotations.extract:txt     | Actual document text (split into sized pieces).
  annotations.summary:txt     | AI-generated summary of the full page/entity.
  annotations.ner:entities    | Named entities extracted from the text.
  annotations.extract:metadata| File metadata (PDF props, EXIF, etc.).

Search strategy — content branches query **nested chunks**, not rag:fulltext:

  Branch   | Searches on                              | In RRF?
  ---------+------------------------------------------+--------
  FTS      | nested BM25 on chunks.metadata.text      | Yes (2x weight)
  KNN      | vector similarity on chunks.embedding    | Yes
  Entity   | flat entity_label (keyword + phrase)      | No
  HyDE KNN | KNN with hypothetical document embeddings | Yes

FTS and KNN search all chunks (field_name is not indexed, so no
query-time filter).  The field_name filter (extract:txt only) is
applied at parse time in extract_chunks_by_field().  This yields
~4 KB per result instead of ~24 KB, cutting token usage by ~6×.

Entity returns lightweight pointers (entity_id, label, page) as a
separate ``entity_matches`` list — it does NOT participate in RRF
fusion because document-name matching is a different signal from
content relevance.

HyDE (Hypothetical Document Embeddings)
========================================
For react_agent_exhaustive strategy, the ``hyde`` node generates
hypothetical document excerpts in each detected document language.
These are embedded and used as additional KNN queries, bridging the
semantic gap between the user's query language and the document content
(e.g. "addresses of Valerio Simoni" → Italian hypothetical with
"Via Roma 45, Milano" matches real Italian addresses by KNN similarity).

Summary recovery
================
Summaries (``field_name=summary:txt``) are **not** searched or ranked.
After dedup + score-gap filtering, summaries are fetched only for the
chunks that survived.  They travel as a separate ``summary`` field in
the output JSON, useful for downstream grounding/citation but never
influencing retrieval ranking.
"""

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from ..subgraphs.semantic_search import semantic_subgraph, RetrievedEntity, EntityMatch
from ..config import (
    MAX_RETRIEVAL_CONTEXT_RESULTS,
    MAX_RETRIEVAL_RESULT_CHARS,
    MIN_RETRIEVAL_RESULTS,
    SCORE_GAP_MIN_FRACTION,
)

logger = logging.getLogger(__name__)


async def semantic_retrieval(
    query: str,
    entity_names: list[str] | None = None,
    context_entity_ids: list[str] | None = None,
    workspace_id: str = "",
    config: RunnableConfig | None = None,
    key_terms: list[str] | None = None,
    max_results: int = MAX_RETRIEVAL_CONTEXT_RESULTS,
    include_summaries: bool = False,
    max_text_chars: int = MAX_RETRIEVAL_RESULT_CHARS,
    hyde_queries: list[str] | None = None,
) -> dict[str, Any]:
    """Run the semantic subgraph and return structured results.

    Steps:
      1. Invokes semantic_search subgraph with 3 parallel branches:
         - FTS: nested BM25 on chunk text (field_name=extract:txt) → RRF
         - KNN: vector similarity on chunk embeddings → RRF
         - Entity: flat entity_label lookup → separate entity_matches (not in RRF)
      2. Fuses FTS + KNN with RRF (Reciprocal Rank Fusion) + density rerank
      3. Score-gap detection drops the low-relevance tail
      4. Summaries (field_name=summary:txt) travel with surviving results
      5. Formats top results as JSON with text + summary + entity_matches
    """
    sub_result = await semantic_subgraph.ainvoke(
        {
            "rewritten_query": query,
            "entity_names": entity_names,
            "key_terms": key_terms or [],
            "context_entity_ids": context_entity_ids or [],
            "workspace_id": workspace_id,
            "hyde_queries": hyde_queries or [],
        },
        config=config,
    )

    fused: list[RetrievedEntity] = sub_result.get("fused_entities", [])
    entity_matches: list[EntityMatch] = sub_result.get("entity_matches", [])
    provenance = sub_result.get("provenance", "")

    # Score gap detection: scan consecutive scores for the largest drop.
    # If the drop exceeds SCORE_GAP_MIN_FRACTION * max_score, cut there.
    # This adapts naturally to any score scale (RRF, BM25, cosine) and
    # filters the long tail of low-relevance results that inflate tokens.
    candidates = fused[:max_results]
    if len(candidates) > MIN_RETRIEVAL_RESULTS:
        max_score = candidates[0].score or 0.0
        gap_threshold = max_score * SCORE_GAP_MIN_FRACTION
        scores = [e.score or 0.0 for e in candidates]
        best_gap_idx = None
        best_gap_val = 0.0
        for i in range(MIN_RETRIEVAL_RESULTS, len(scores)):
            gap = scores[i - 1] - scores[i]
            if gap >= gap_threshold and gap > best_gap_val:
                best_gap_val = gap
                best_gap_idx = i
        if best_gap_idx is not None:
            logger.info(
                "semantic_retrieval: score gap %.4f at position %d "
                + "(scores %.4f→%.4f), dropping %d/%d results",
                best_gap_val,
                best_gap_idx,
                scores[best_gap_idx - 1],
                scores[best_gap_idx],
                len(candidates) - best_gap_idx,
                len(candidates),
            )
            candidates = candidates[:best_gap_idx]

    results = []
    for e in candidates:
        doc_label = e.entity_label or e.entity_id
        text = e.content[:max_text_chars]

        entry = {
            "entity_id": e.entity_id,
            "entity_type": e.entity_type,
            "document": doc_label,
            "score": round(e.score, 4),
            "text": text,
        }
        if e.source_entity_uid:
            entry["source_file_id"] = e.source_entity_uid
            if e.fragment_page_number is not None:
                entry["page"] = e.fragment_page_number
            if e.fragment_count is not None:
                entry["total_pages"] = e.fragment_count
        results.append(entry)

    # Entity matches — lightweight pointers, separate from content results
    em_list = [
        {
            "entity_id": m.entity_id,
            "entity_label": m.entity_label,
            "entity_type": m.entity_type,
            "page": m.fragment_page_number,
        }
        for m in entity_matches
    ]

    logger.info(
        "semantic_retrieval: %s → %d/%d results (gap cut %d), %d entity matches",
        provenance,
        len(results),
        len(fused),
        len(fused) - len(results),
        len(em_list),
    )
    output: dict[str, Any] = {
        "query": query,
        "provenance": provenance,
        "total_results": len(fused),
        "results": results,
    }
    if em_list:
        output["entity_matches"] = em_list
    if include_summaries:
        doc_summaries: dict[str, str] = {}
        for e in candidates:
            if e.summary:
                doc_id = e.source_entity_uid or e.entity_id
                if doc_id not in doc_summaries:
                    doc_summaries[doc_id] = e.summary
        if doc_summaries:
            output["doc_summaries"] = doc_summaries
    return output


async def knn_search(
    query: str,
    context_entity_ids: list[str] | None = None,
    workspace_id: str = "",
    config: RunnableConfig | None = None,
    max_results: int = 10,
) -> dict[str, Any]:
    """Standalone KNN vector search — returns matching chunk text (not full page).

    Embeds the query and runs k-NN on rag:chunks embeddings. Returns the
    inner_hit chunk text that matched the vector, plus summary and metadata.
    """
    from ..subgraphs.semantic_search import (
        _build_knn_query,
        _extract_inner_hit_text,
        os_search,
        extract_chunks_by_field,
        KNN_MIN_SCORE,
    )
    from ..utils import get_embedding

    query_vector = await get_embedding(query)
    if not query_vector:
        return {"query": query, "results": [], "error": "no embedding service"}

    os_query = _build_knn_query(
        query_vector,
        context_entity_ids=context_entity_ids,
        workspace_id=workspace_id,
        size=max_results,
    )
    raw = await os_search(os_query, config)
    hits = raw.get("hits", {}).get("hits", [])

    results = []
    for hit in hits:
        score = float(hit.get("_score", 0))
        if score < KNN_MIN_SCORE:
            continue
        src = hit.get("_source", {})
        doc_fields = src.get("document_fields", {})

        # Inner hit = the specific chunk that matched the vector
        chunk_text = _extract_inner_hit_text(hit)
        # Fallback to full page text if no inner_hit
        if not chunk_text:
            chunk_text, _ = extract_chunks_by_field(hit)
        if not chunk_text:
            continue

        _, summary = extract_chunks_by_field(hit, max_chars=0)

        entry: dict[str, Any] = {
            "entity_id": doc_fields.get("entity_id", ""),
            "entity_type": doc_fields.get("entity_type", ""),
            "document": doc_fields.get("entity_label", ""),
            "score": round(score, 4),
            "text": chunk_text,
        }
        if summary:
            entry["summary"] = summary
        if doc_fields.get("source_entity_uid"):
            entry["source_file_id"] = doc_fields["source_entity_uid"]
        if doc_fields.get("fragment_page_number") is not None:
            entry["page"] = doc_fields["fragment_page_number"]
        if doc_fields.get("fragment_count") is not None:
            entry["total_pages"] = doc_fields["fragment_count"]
        results.append(entry)

    logger.info("knn_search: %d results for '%s'", len(results), query[:50])
    return {"query": query, "results": results}
