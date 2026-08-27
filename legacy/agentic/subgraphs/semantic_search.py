"""SemanticSearch SubGraph — 4 parallel OpenSearch branches + RRF fuse + density rerank.

 document_fields.*, annotations.rag:chunks, nested KNN.

LangGraph subgraph with parallel edges:
  START → [semantic_fts ∥ semantic_entity ∥ semantic_knn ∥ semantic_hyde]
        → semantic_fuse_rerank (RRF + density + coverage) → END

HyDE branch runs only when hyde_queries are provided (react_agent_exhaustive).
FTS has 2x weight in RRF fusion. Entity does not participate in RRF.
"""

import asyncio
import logging
import math
import operator

from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from ..tools.opensearch_repository import (
    os_search,
    extract_chunks_by_field,
    build_scope_filter,
    build_doc_type_filter,
    SRC_FIELDS,
)
from ..utils import get_embedding
from ..config import (
    MAX_STRATEGY_RESULTS,
    MAX_ENTITY_CONTENT_CHARS,
    MAX_KNN_K_MULTIPLIER,
)

logger = logging.getLogger(__name__)

# CI vector field name (text-embedding-3-small, 1536 dims)
KNN_VECTOR_NAME = "vector_text_embedding_3_small_1536_1"

MAX_CHUNKS_PER_DOC = 5
KNN_MIN_SCORE = 0.3  # filter out low-quality vector matches from RRF input
MAX_ENTITY_NAMES = 10  # cap entity_names to limit should clauses

# RRF constant. With k=60 and the FTS weight below, a top-ranked result scores
# 2/(60+1) = 0.033 per branch: the whole fused scale lives under ~0.05.
RRF_K = 60
FTS_WEIGHT = 2.0  # keyword matches are more precise for factual extraction

# How much the density rerank may move a result, as a FRACTION of the top fused score.
# This used to be an unnormalised `matches/sqrt(len)`, which reaches ~0.18 on a 3000-char
# chunk with ten hits -- four to five times the ENTIRE range of the RRF scores it was
# supposed to adjust. The rerank was not adjusting the fusion, it was replacing it with
# term frequency. Expressed as a fraction of the top score, it breaks ties and nudges
# neighbours, which is what a rerank is for.
DENSITY_WEIGHT = 0.25


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RetrievedEntity(BaseModel):
    """Normalized entity returned by any search branch."""

    entity_id: str
    entity_label: str = ""
    entity_type: str = ""
    content: str = ""  # chunk text (field_name=extract:txt)
    summary: str = ""  # AI summary (field_name=summary:txt), recovered post-dedup
    score: float = 0.0
    source: str = "opensearch_fts"
    # Fragment metadata (populated when hit is os_fragment)
    source_entity_uid: str = ""  # parent os_file entity_id
    fragment_page_number: int | None = None
    fragment_index: int | None = None
    fragment_count: int | None = None
    previous_entity_uid: str = ""
    next_entity_uid: str = ""


class EntityMatch(BaseModel):
    """Lightweight pointer returned by the Entity branch (not fused with content)."""

    entity_id: str
    entity_label: str = ""
    entity_type: str = ""
    score: float = 0.0
    source_entity_uid: str = ""
    fragment_page_number: int | None = None


class SemanticSearchSubState(TypedDict, total=False):
    """Isolated state for the SemanticSearch subgraph."""

    # Inputs
    rewritten_query: str
    entity_names: list[str]
    key_terms: list[str]  # translated search terms for cross-language FTS
    context_entity_ids: list[str]
    workspace_id: str
    hyde_queries: list[str]  # hypothetical document answers per language

    # Reducer: each content branch appends [list[RetrievedEntity]]
    branch_results: Annotated[list, operator.add]
    # Reducer: each branch appends one BranchStatus. Provenance is built from these,
    # so a branch that failed or was skipped is visible downstream instead of being
    # absorbed into an empty list that looks like "no matches".
    branch_status: Annotated[list, operator.add]

    # Output — content results (FTS + KNN fused)
    fused_entities: list[RetrievedEntity]
    # Output — entity lookup results (separate, NOT fused)
    entity_matches: list[EntityMatch]
    provenance: str  # built from branch_status, never a literal
    branch_report: list[dict]  # per-branch outcome, for the caller's record
    degraded: list[str]  # branches that failed or were skipped, named
    note: str


# ---------------------------------------------------------------------------
# Query builders —
# ---------------------------------------------------------------------------


def _build_chunk_nested_query(
    query_text: str,
    boost: float = 2.0,
) -> dict:
    """Build a nested BM25 query on rag:chunks.metadata.text.

    Searches ALL chunks — no query-time filter on field_name.
    Filtering by field_name (extract:txt, summary:txt) happens at
    parse time in extract_chunks_by_field(), so this works whether
    or not field_name is indexed in the mapping.
    """
    return {
        "nested": {
            "path": "annotations.rag:chunks",
            "query": {
                "match": {
                    "annotations.rag:chunks.metadata.text": {
                        "query": query_text,
                        "operator": "or",
                        "boost": boost,
                    }
                }
            },
            "score_mode": "max",
            "inner_hits": {
                "name": "fts_chunks",
                "size": 1,
                "_source": False,
                "fields": ["annotations.rag:chunks.metadata.text"],
            },
        }
    }


def _build_fts_query(
    query_text: str,
    context_entity_ids: list[str] | None = None,
    workspace_id: str = "",
    size: int = MAX_STRATEGY_RESULTS,
    key_terms: list[str] | None = None,
) -> dict:
    """Full-text search (BM25) on nested chunks (field_name=extract:txt).

    Searches chunk text via nested query filtered to content chunks only.
    entity_label is still searched as a flat field for document name matching.
    key_terms adds cross-language coverage as separate nested clauses.
    """
    should_clauses: list[dict] = [
        # Flat: document name (highest priority)
        {
            "match": {
                "document_fields.entity_label": {
                    "query": query_text,
                    "boost": 4,
                    "operator": "or",
                    "analyzer": "whitespace",
                }
            }
        },
        # Nested: BM25 on chunk text
        _build_chunk_nested_query(query_text, boost=2.0),
    ]

    # Cross-language: add key_terms as separate nested clause
    if key_terms:
        terms_text = " ".join(
            t for t in key_terms if t.lower() not in query_text.lower()
        )
        if terms_text:
            should_clauses.append(_build_chunk_nested_query(terms_text, boost=1.5))

    filters = (
        build_scope_filter(context_entity_ids or None, workspace_id)
        + build_doc_type_filter()
    )

    bool_query: dict[str, Any] = {
        "should": should_clauses,
        "minimum_should_match": 1,
    }
    if filters:
        bool_query["filter"] = filters

    return {
        "size": size,
        "track_total_hits": False,
        "_source": SRC_FIELDS,
        "query": {"bool": bool_query},
    }


def _build_entity_query(
    entity_names: list[str],
    context_entity_ids: list[str] | None = None,
    workspace_id: str = "",
    size: int = MAX_STRATEGY_RESULTS,
) -> dict:
    """Entity lookup: find documents by entity name (flat fields only).

    Returns lightweight pointers (entity_id, label, page#), NOT content.
    Does NOT participate in RRF fusion — it's a separate signal.

    Per entity name:
      - term on entity_label.keyword (boost=10): exact keyword match.
      - match_phrase on entity_label (boost=5): analyzed phrase match.
    """
    # Minimal _source — we only need pointers, not chunk text
    entity_src_fields = [
        "document_fields.entity_id",
        "document_fields.entity_type",
        "document_fields.entity_label",
        "document_fields.source_entity_uid",
        "document_fields.fragment_page_number",
    ]

    should_clauses: list[dict] = []
    for name in entity_names[:MAX_ENTITY_NAMES]:
        should_clauses.append(
            {
                "term": {
                    "document_fields.entity_label.keyword": {
                        "value": name,
                        "boost": 10,
                    }
                }
            }
        )
        should_clauses.append(
            {
                "match_phrase": {
                    "document_fields.entity_label": {"query": name, "boost": 5}
                }
            }
        )

    filters = (
        build_scope_filter(context_entity_ids or None, workspace_id)
        + build_doc_type_filter()
    )

    bool_query: dict[str, Any] = {
        "should": should_clauses,
        "minimum_should_match": 1,
    }
    if filters:
        bool_query["filter"] = filters

    return {
        "size": size,
        "track_total_hits": False,
        "_source": entity_src_fields,
        "query": {"bool": bool_query},
    }


def _build_knn_query(
    query_vector: list[float],
    context_entity_ids: list[str] | None = None,
    workspace_id: str = "",
    size: int = MAX_STRATEGY_RESULTS,
) -> dict:
    """Nested KNN vector search on CI RAG chunk embeddings."""
    field_path = f"annotations.rag:chunks.embedding.{KNN_VECTOR_NAME}.value"

    # KNN query: approximate nearest neighbor on chunk embeddings.
    #
    # k = size * MAX_KNN_K_MULTIPLIER (3x): over-retrieve then let RRF pick best.
    #
    # Pre-filter (INSIDE knn spec): reduces search space BEFORE vector traversal.
    #   - With context_entity_ids: filter to file + its page fragments.
    #   - With workspace_id only: filter to workspace (avoids scanning full index).
    #   Pre-filter is critical — post-filtering (outside knn) would search the entire
    #   index and then discard non-matching results, wasting 50-80% of compute.
    #
    # nested on rag:chunks: each chunk has its own embedding vector.
    #   - inner_hits: return top chunk texts for LLM context.
    #     - _source=False + fields: faster for nested doc retrieval.
    #
    # No outer filter needed — pre-filter handles scoping.
    knn_spec: dict[str, Any] = {
        "vector": query_vector,
        "k": size * MAX_KNN_K_MULTIPLIER,
    }
    if context_entity_ids:
        knn_spec["filter"] = {
            "bool": {
                "should": [
                    {
                        "terms": {
                            "document_fields.entity_id.keyword": context_entity_ids
                        }
                    },
                    {
                        "terms": {
                            "document_fields.source_entity_uid.keyword": context_entity_ids
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        }
    elif workspace_id:
        knn_spec["filter"] = {
            "term": {"document_fields.os_workspace.keyword": workspace_id}
        }

    knn_clause = {
        "nested": {
            "path": "annotations.rag:chunks",
            "query": {"knn": {field_path: knn_spec}},
            "inner_hits": {
                "name": "knn_chunks",
                "size": MAX_CHUNKS_PER_DOC,
                "_source": False,
                "fields": ["annotations.rag:chunks.metadata.text"],
            },
        }
    }

    return {
        "size": size,
        "track_total_hits": False,
        "_source": SRC_FIELDS,
        "query": {"bool": {"should": [knn_clause], "minimum_should_match": 1}},
    }


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _extract_inner_hit_text(hit: dict) -> str:
    """Extract the best matching chunk text from inner_hits (FTS or KNN)."""
    for name in ("fts_chunks", "knn_chunks"):
        inner = hit.get("inner_hits", {}).get(name, {}).get("hits", {}).get("hits", [])
        if inner:
            fields = inner[0].get("fields", {})
            texts = fields.get("annotations.rag:chunks.metadata.text", [])
            if texts:
                return texts[0]
    return ""


def _hits_to_entities(
    hits: list[dict], source: str, min_score: float = 0.0
) -> list[RetrievedEntity]:
    """Convert OpenSearch hits to RetrievedEntity list. Filters by min_score."""
    entities = []
    for hit in hits:
        if min_score and float(hit.get("_score", 0)) < min_score:
            continue
        src = hit.get("_source", {})
        doc_fields = src.get("document_fields", {})

        # Prefer inner_hit text (the specific chunk that matched) over full page
        inner_text = _extract_inner_hit_text(hit)
        content, summary = extract_chunks_by_field(hit)

        # Use inner_hit as content when available (more precise, smaller)
        if inner_text:
            content = inner_text
        elif not content:
            continue

        content = content[:MAX_ENTITY_CONTENT_CHARS]
        entity_id = doc_fields.get("entity_id") or hit.get("_id", "")
        label = doc_fields.get("entity_label") or ""
        entity_type = doc_fields.get("entity_type") or ""

        entities.append(
            RetrievedEntity(
                entity_id=entity_id,
                entity_label=label,
                entity_type=entity_type,
                content=content,
                summary=summary,
                score=float(hit.get("_score", 0)),
                source=source,
                source_entity_uid=doc_fields.get("source_entity_uid") or "",
                fragment_page_number=doc_fields.get("fragment_page_number"),
                fragment_index=doc_fields.get("fragment_index"),
                fragment_count=doc_fields.get("fragment_count"),
                previous_entity_uid=doc_fields.get("previous_entity_uid") or "",
                next_entity_uid=doc_fields.get("next_entity_uid") or "",
            )
        )
    if entities:
        logger.info("  %s: %d hits -> %d entities", source, len(hits), len(entities))
    return entities


# ---------------------------------------------------------------------------
# SubGraph nodes
# ---------------------------------------------------------------------------


def _status(branch: str, state: str, results: int = 0, detail: str = "") -> dict:
    """One branch's own report, so provenance can be assembled from what happened.

    `provenance` used to be the constant "semantic_search+rrf+density": when the FTS
    branch threw, its `except` returned an empty list and every downstream consumer was
    still told the answer came from an FTS+KNN fusion. A claim about how evidence was
    obtained cannot be a literal.
    """
    return {"branch": branch, "status": state, "results": results, "detail": detail[:200]}


async def _node_semantic_fts(
    state: SemanticSearchSubState, config: RunnableConfig
) -> dict:
    """Branch 1: Full-text search by rewritten_query."""
    try:
        query = _build_fts_query(
            state.get("rewritten_query", ""),
            context_entity_ids=state.get("context_entity_ids") or None,
            key_terms=state.get("key_terms") or None,
            workspace_id=state.get("workspace_id", ""),
        )
        results = await os_search(query, config)
        hits = results.get("hits", {}).get("hits", [])
        entities = _hits_to_entities(hits, "opensearch_fts")
        return {
            "branch_results": [entities],
            "branch_status": [
                _status("fts", "ok" if entities else "empty", len(entities))
            ],
        }
    except Exception as e:
        logger.error("semantic_fts failed: %s", e, exc_info=True)
        return {
            "branch_results": [[]],
            "branch_status": [_status("fts", "failed", 0, str(e))],
        }


async def _node_semantic_entity(
    state: SemanticSearchSubState, config: RunnableConfig
) -> dict:
    """Entity lookup: find documents by name. Returns pointers, NOT in RRF."""
    if not state.get("entity_names", []):
        return {"entity_matches": [], "branch_status": [_status("entity", "skipped")]}
    try:
        query = _build_entity_query(
            state.get("entity_names", []),
            context_entity_ids=state.get("context_entity_ids") or None,
            workspace_id=state.get("workspace_id", ""),
        )
        results = await os_search(query, config)
        hits = results.get("hits", {}).get("hits", [])
        matches = []
        for hit in hits:
            src = hit.get("_source", {})
            doc = src.get("document_fields", {})
            matches.append(
                EntityMatch(
                    entity_id=doc.get("entity_id") or hit.get("_id", ""),
                    entity_label=doc.get("entity_label") or "",
                    entity_type=doc.get("entity_type") or "",
                    score=float(hit.get("_score", 0)),
                    source_entity_uid=doc.get("source_entity_uid") or "",
                    fragment_page_number=doc.get("fragment_page_number"),
                )
            )
        if matches:
            logger.info("  entity_lookup: %d matches", len(matches))
        return {
            "entity_matches": matches,
            "branch_status": [
                _status("entity", "ok" if matches else "empty", len(matches))
            ],
        }
    except Exception as e:
        logger.error("semantic_entity failed: %s", e, exc_info=True)
        return {
            "entity_matches": [],
            "branch_status": [_status("entity", "failed", 0, str(e))],
        }


async def knn_entities(
    query_vector: list[float],
    context_entity_ids: list[str] | None = None,
    workspace_id: str = "",
    config: RunnableConfig | None = None,
    size: int = MAX_STRATEGY_RESULTS,
    source: str = "opensearch_knn",
) -> list[RetrievedEntity]:
    """The KNN branch as a plain callable: build, search, normalise.

    Public because `tools.retrieval.knn_search` needs exactly this and used to reach
    into this module for five private helpers to rebuild it by hand -- two
    implementations of one query, free to drift apart. It takes the vector rather than
    the text so that each caller can report "no embedding service" in its own terms.
    """
    query = _build_knn_query(
        query_vector,
        context_entity_ids=context_entity_ids,
        workspace_id=workspace_id,
        size=size,
    )
    raw = await os_search(query, config)
    hits = raw.get("hits", {}).get("hits", [])
    return _hits_to_entities(hits, source, min_score=KNN_MIN_SCORE)


async def _node_semantic_knn(
    state: SemanticSearchSubState, config: RunnableConfig
) -> dict:
    """Branch 3: KNN vector search (embed query + nested k-NN on CI RAG chunks)."""
    try:
        query_vector = await get_embedding(state.get("rewritten_query", ""))
        if not query_vector:
            logger.warning("  semantic_knn  |  SKIPPED: no embedding service")
            return {
                "branch_results": [[]],
                "branch_status": [
                    _status("knn", "skipped", 0, "no embedding service")
                ],
            }
        entities = await knn_entities(
            query_vector,
            context_entity_ids=state.get("context_entity_ids") or None,
            workspace_id=state.get("workspace_id", ""),
            config=config,
        )
        return {
            "branch_results": [entities],
            "branch_status": [
                _status("knn", "ok" if entities else "empty", len(entities))
            ],
        }
    except Exception as e:
        logger.error("semantic_knn failed: %s", e, exc_info=True)
        return {
            "branch_results": [[]],
            "branch_status": [_status("knn", "failed", 0, str(e))],
        }


async def _node_semantic_hyde(
    state: SemanticSearchSubState, config: RunnableConfig
) -> dict:
    """Branch 4: HyDE KNN — one KNN per hypothetical answer (parallel embeds)."""
    hyde_queries = state.get("hyde_queries", [])
    if not hyde_queries:
        return {
            "branch_results": [[]],
            "branch_status": [_status("hyde", "skipped")],
        }

    try:

        async def run_one(hq: str) -> list[RetrievedEntity]:
            vec = await get_embedding(hq)
            if not vec:
                return []
            return await knn_entities(
                vec,
                context_entity_ids=state.get("context_entity_ids") or None,
                workspace_id=state.get("workspace_id", ""),
                config=config,
                source="opensearch_hyde",
            )

        results = await asyncio.gather(*[run_one(hq) for hq in hyde_queries[:3]])
        all_entities = [e for batch in results for e in batch]
        logger.info(
            "  semantic_hyde: %d entities from %d HyDE queries",
            len(all_entities),
            len(hyde_queries),
        )
        return {
            "branch_results": [all_entities],
            "branch_status": [
                _status("hyde", "ok" if all_entities else "empty", len(all_entities))
            ],
        }
    except Exception as e:
        logger.error("semantic_hyde failed: %s", e, exc_info=True)
        return {
            "branch_results": [[]],
            "branch_status": [_status("hyde", "failed", 0, str(e))],
        }


# ---------------------------------------------------------------------------
# Fusion & Reranking
# ---------------------------------------------------------------------------


def _content_key(entity: RetrievedEntity) -> str:
    """Generate a dedup key for a fragment based on content, or entity_id for non-fragments.

    Fragments from different source files (e.g. perizia page019 vs merged_docs page019)
    have different entity_ids but identical content. This key merges their RRF scores
    so unique content ranks higher instead of duplicates competing for slots.
    """
    if entity.source_entity_uid and entity.fragment_page_number is not None:
        return f"{entity.fragment_page_number}|{entity.content[:200]}"
    return entity.entity_id


def _rrf_fuse(
    branches: list[list[RetrievedEntity]], k: int = RRF_K
) -> list[RetrievedEntity]:
    """Reciprocal Rank Fusion, keyed by CONTENT.

    The key is the content key, not the entity_id, and that is the whole point: the same
    page reached through two different source files carries two entity_ids, and keying by
    id made the two copies compete for slots with half the evidence each. Their ranks now
    add, so content that several branches agree on rises -- which is what fusion means.

    One contribution per branch per unique content: a branch that returns the same page
    twice under two ids is one branch's opinion, not two, and its best rank is the one
    that counts.
    """
    scores: dict[str, float] = {}
    best: dict[str, tuple[RetrievedEntity, int]] = {}

    for branch in branches:
        weight = FTS_WEIGHT if _branch_is_fts(branch) else 1.0
        seen_in_branch: set[str] = set()
        for rank, entity in enumerate(branch):
            key = _content_key(entity)
            if key in seen_in_branch:
                continue
            seen_in_branch.add(key)
            scores[key] = scores.get(key, 0.0) + weight / (k + rank + 1)
            previous = best.get(key)
            if previous is None or rank < previous[1]:
                best[key] = (entity, rank)

    results = []
    for key in sorted(scores, key=lambda c: scores[c], reverse=True):
        copy = best[key][0].model_copy()
        copy.score = scores[key]
        results.append(copy)
    return results


def _branch_is_fts(branch: list[RetrievedEntity]) -> bool:
    """Whether a branch came from full-text search, and so carries the FTS weight."""
    return bool(branch) and getattr(branch[0], "source", "") == "opensearch_fts"


def _density_rerank(
    entities: list[RetrievedEntity], query: str
) -> list[RetrievedEntity]:
    """Rerank by query-term density, bounded to a fraction of the fused score.

    Density is normalised twice before it is allowed to move anything: by the maximum
    density in this result set (so it is a relative signal, not an absolute one that
    depends on chunk length conventions), and by the top fused score (so its magnitude
    lives on the same scale as the thing it adjusts). Unbounded, it decided the order
    outright -- see DENSITY_WEIGHT.
    """
    query_lower = (query or "").lower()
    terms = [t for t in query_lower.split() if len(t) > 2]
    if not terms or not entities:
        return entities

    densities: list[float] = []
    for e in entities:
        content_lower = (e.content or "").lower()
        content_len = max(len(content_lower), 1)
        matches = sum(content_lower.count(t) for t in terms)
        densities.append(matches / math.sqrt(content_len))

    top_density = max(densities)
    if top_density <= 0.0:
        return entities
    top_score = max((e.score or 0.0) for e in entities)
    budget = DENSITY_WEIGHT * top_score

    for e, density in zip(entities, densities):
        e.score = (e.score or 0.0) + budget * (density / top_density)

    entities.sort(key=lambda e: e.score, reverse=True)
    return entities


def _parent_doc(entity: RetrievedEntity) -> str:
    """The document a chunk belongs to. For a fragment that is its parent file."""
    return entity.source_entity_uid or entity.entity_id


def _ensure_coverage(
    entities: list[RetrievedEntity], max_results: int = MAX_STRATEGY_RESULTS
) -> list[RetrievedEntity]:
    """Ensure at least one chunk per unique DOCUMENT survives the cut.

    Grouping used to be by `entity_id`, which is unique per result after fusion: every
    count was 1, the "more than one chunk from this document" test could never be true,
    and the function replaced nothing -- it was `entities[:max_results]` with extra
    steps. Grouping by the parent file is what the docstring always claimed and what
    makes the guarantee real: a document represented twice in the cut gives up its
    weakest chunk so a document represented zero times can get in.
    """
    if not entities:
        return entities

    included = entities[:max_results]
    overflow = entities[max_results:]

    docs_in = {_parent_doc(e) for e in included}

    missing_best: dict[str, RetrievedEntity] = {}
    for e in overflow:
        doc = _parent_doc(e)
        if doc not in docs_in and doc not in missing_best:
            missing_best[doc] = e

    if not missing_best:
        return included

    doc_counts: dict[str, int] = {}
    for e in included:
        doc = _parent_doc(e)
        doc_counts[doc] = doc_counts.get(doc, 0) + 1

    result = list(included)
    for replacement in missing_best.values():
        worst_idx = None
        worst_score = float("inf")
        for i, e in enumerate(result):
            doc = _parent_doc(e)
            if doc_counts.get(doc, 0) > 1 and e.score < worst_score:
                worst_idx = i
                worst_score = e.score
        if worst_idx is None:
            # Nothing left to give up: every document in the cut is there exactly once,
            # and evicting one to admit another would trade coverage for coverage.
            break
        evicted = result[worst_idx]
        doc_counts[_parent_doc(evicted)] -= 1
        result[worst_idx] = replacement
        doc_counts[_parent_doc(replacement)] = 1

    return result


def _describe_provenance(status: list[dict]) -> tuple[str, list[str]]:
    """Build the provenance string from what the branches actually reported.

    Returns (provenance, degraded) where `degraded` names the branches that failed or
    were skipped. A consumer that reads "rrf(fts:20)" knows the vector branch did not
    contribute; before, every answer claimed the full fusion regardless.
    """
    contributing = [
        f"{s['branch']}:{s['results']}"
        for s in status
        if s.get("status") == "ok" and s.get("branch") != "entity"
    ]
    degraded = [
        f"{s['branch']}({s['status']}{': ' + s['detail'] if s.get('detail') else ''})"
        for s in status
        if s.get("status") in ("failed", "skipped")
    ]
    if not contributing:
        return "semantic_search: no branch contributed", degraded
    return f"rrf({'+'.join(sorted(contributing))})+density", degraded


def _node_semantic_fuse_and_rerank(state: SemanticSearchSubState) -> dict:
    """RRF fusion + density rerank + document coverage in one step."""
    status = list(state.get("branch_status", []))
    provenance, degraded = _describe_provenance(status)
    branches = [b for b in state.get("branch_results", []) if b]
    if not branches:
        return {
            "fused_entities": [],
            "provenance": provenance,
            "branch_report": status,
            "degraded": degraded,
        }

    fused = _rrf_fuse(branches)
    fused = _density_rerank(fused, state.get("rewritten_query", ""))
    fused = _ensure_coverage(fused, max_results=MAX_STRATEGY_RESULTS)
    if degraded:
        logger.warning("semantic_search DEGRADED: %s", ", ".join(degraded))
    return {
        "fused_entities": fused,
        "provenance": provenance,
        "branch_report": status,
        "degraded": degraded,
    }


# ---------------------------------------------------------------------------
# SubGraph builder + compiled singleton
# ---------------------------------------------------------------------------


def build_semantic_subgraph() -> CompiledStateGraph:
    """Build the SemanticSearch subgraph with parallel branches + fuse + rerank.

    Branches: FTS, Entity, KNN, HyDE KNN (if hyde_queries provided).
    All run in parallel → RRF fusion.
    """
    builder = StateGraph(SemanticSearchSubState)

    builder.add_node("semantic_fts", _node_semantic_fts)
    builder.add_node("semantic_entity", _node_semantic_entity)
    builder.add_node("semantic_knn", _node_semantic_knn)
    builder.add_node("semantic_hyde", _node_semantic_hyde)
    builder.add_node("semantic_fuse_rerank", _node_semantic_fuse_and_rerank)

    builder.add_edge(START, "semantic_fts")
    builder.add_edge(START, "semantic_entity")
    builder.add_edge(START, "semantic_knn")
    builder.add_edge(START, "semantic_hyde")
    builder.add_edge("semantic_fts", "semantic_fuse_rerank")
    builder.add_edge("semantic_entity", "semantic_fuse_rerank")
    builder.add_edge("semantic_knn", "semantic_fuse_rerank")
    builder.add_edge("semantic_hyde", "semantic_fuse_rerank")
    builder.add_edge("semantic_fuse_rerank", END)

    return builder.compile()


semantic_subgraph = build_semantic_subgraph()
