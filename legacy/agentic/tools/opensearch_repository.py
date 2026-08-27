"""
OpenSearch Repository — central module for ALL OpenSearch queries and search logic.

Data model (OpenSearch index = ontology name, e.g. "os_ontology_v1"):

  os_workspace
  └── os_file (document: PDF, etc.)
      ├── document_fields
      │   ├── entity_id            — UUID. Used by: all queries.
      │   ├── entity_label         — human-readable name. Used by: entity search, display.
      │   ├── entity_type          — "os_file". Used by: type filtering.
      │   └── os_workspace         — workspace UUID. Used by: workspace scope filter.
      │
      │── annotations.rag:fulltext — full text (text + shingles). Used by: BM25 search.
      │     Present on BOTH os_file and os_fragment. Queries search both via
      │     build_context_filter (entity_id OR source_entity_uid match).
      │
      │── annotations.ner:entities — {type: [names]}.
      │     Present on BOTH os_file and os_fragment. Queries search both via
      │     build_context_filter. When has_fragments=True, os_file is excluded.
      │     Used by: fetch_ner_entities, fetch_content_ner_by_type, fetch_ner_per_doc.
      │
      └── os_fragment[] (one per PAGE, linked via source_entity_uid)
          │   Not all files have fragments. Files without fragments are
          │   searchable only via the os_file's own rag:fulltext and ner:entities.
          │
          ├── document_fields
          │   ├── entity_id             — UUID (unique per page). Used by: all queries.
          │   ├── source_entity_uid     — parent os_file UUID. Used by: build_context_filter.
          │   ├── entity_type           — "os_fragment". Used by: type filtering.
          │   ├── fragment_page_number  — 1-based. Used by: format_hit, LLM context.
          │   ├── fragment_index        — 0-based. Used by: format_hit.
          │   ├── fragment_count        — total pages. Used by: format_hit, LLM context.
          │   ├── previous_entity_uid   — prev page UUID. Used by: fetch_fragment_content.
          │   └── next_entity_uid       — next page UUID. Used by: fetch_fragment_content.
          │
          ├── annotations.rag:fulltext  — full text of this page (text + shingles).
          │     Used by: BM25 search (build_text_query, _build_fts_query, full_text_search).
          │     PRIMARY search field — flat, fast, cached. No nested overhead.
          │
          ├── annotations.rag:chunks[]  — nested array (page text split for embedding).
          │   │   May not be populated in all environments.
          │   │
          │   ├── metadata.text         — chunk text (text + keyword).
          │   │     NOT used by: BM25 (redundant with fulltext).
          │   │     Used by: inner_hits in parse_entity_context (extract matching passage).
          │   ├── metadata.type         — "record" | "other" (keyword). Not used by queries.
          │   ├── metadata.chunk_id     — position within page (integer). Not used by queries.
          │   │
          │   └── embedding
          │       ├── vector_text_embedding_3_small_1536_1
          │       │   └── value         — knn_vector (1536-dim, FAISS HNSW, L2)
          │       └── vector_sentence_transformers_all_mpnet_base_v2_768_1
          │           └── value         — knn_vector (768-dim, FAISS HNSW, L2)
          │     Used by: _build_knn_query (semantic_search KNN branch).
          │     The ONLY reason chunks exist — embeddings need small text pieces.
          │
          └── annotations.ner:entities  — {type: [names]}. NER per page.
                Same field as on os_file. Queries search both levels.

Query design:
  - BM25 (keyword search): rag:fulltext ONLY — flat field, fast, cached.
    Chunks contain the same text split, so BM25 on both is redundant.
  - KNN (vector search): rag:chunks[].embedding — MUST use chunks because
    embeddings exist only at chunk level. If chunks are not indexed (dev env),
    KNN branch returns 0 results and FTS/entity branches handle retrieval.
  - Scope filters (build_context_filter) match BOTH file entity_id AND its
    fragments via source_entity_uid — covers files WITH and WITHOUT fragments.
    Files without fragments are matched by entity_id directly.
  - Listing functions (fetch_entities_by_ids, list_workspace_docs_agg) EXCLUDE
    fragments — return only top-level entities (files, folders, etc.).

No LangChain tools here — those live in agent_tools.py.

SearchContext is stored in RunnableConfig["configurable"]["search_context"].
No global state — fully concurrent-safe.
"""

import copy
import json
import logging
from dataclasses import dataclass, field
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langsmith import traceable

from app.api.v1.search.search_helpers import apply_standard_search_filters
from app.api.v1.search.search_service import SearchService, init_search_service
from ..cache import cache_get, cache_set
from ..config import MAX_HIT_TEXT_CHARS, MAX_DOC_TEXT_CHARS
from ..utils import sanitize_text

logger = logging.getLogger(__name__)


class ExpandedEntity(TypedDict):
    entity_id: str
    entity_type: str


async def expand_search_set(
    query: dict,
    ontology: str,
    timbr_token: str,
    username: str,
    max_entities: int = 500,
) -> list[ExpandedEntity]:
    """Resolve a search-set query to individual entity IDs.

    Takes the raw OpenSearch query dict (as stored in lastFiredQuery by the
    frontend when a folder/set is added to context) and returns matching
    entity identifiers.  Used by load_context to expand folder selections
    into document-level context_doc_ids.

    Follows the same pattern as the sets API's SearchSetHandler: treats the
    stored lastFiredQuery as a complete search body, patches size/from/_source,
    and applies server-side workspace + standard filters before executing.
    """
    # TODO: TEAM-5422 - There should be a service to handle expansion rather than individual API handlers so
    # it can be used anywhere instead of copying code.
    search_query: dict[str, Any] = copy.deepcopy(query)

    if "query" not in search_query:
        search_query = {"query": search_query}

    if "bool" not in search_query.get("query", {}):
        search_query["query"] = {"bool": {"must": [search_query["query"]]}}

    search_query["size"] = max_entities
    search_query["from"] = 0
    search_query["_source"] = [
        "document_fields.entity_id",
        "document_fields.entity_type",
    ]

    apply_standard_search_filters(search_query)

    search_service = init_search_service(
        ontology=ontology, timbr_token=timbr_token, username=username
    )
    payload = (
        json.dumps({"preference": "results"}) + "\n" + json.dumps(search_query) + "\n"
    )

    result = await search_service.proxy_search(
        ontology=ontology,
        raw_payload=payload.encode("utf-8"),
        need_workspace_filter=True,
        timbr_token=timbr_token,
    )
    if result.status_code != 200:
        raise RuntimeError(
            f"expand_search_set: HTTP {result.status_code}: {result.content}"
        )

    response = json.loads(result.content.decode("utf-8"))["responses"][0]
    hits = response.get("hits", {}).get("hits", [])

    entities: list[ExpandedEntity] = []
    for hit in hits:
        doc_fields = hit.get("_source", {}).get("document_fields", {})
        entity_id = doc_fields.get("entity_id")
        entity_type = doc_fields.get("entity_type")
        if entity_id and entity_type:
            entities.append(
                ExpandedEntity(entity_id=entity_id, entity_type=entity_type)
            )
    return entities


# ---------------------------------------------------------------------------
# DAO constants
# ---------------------------------------------------------------------------

# Max hits (pages/docs) per OpenSearch query. Shared by NER + fragment fetches.
# 2000 covers ~10 large docs (200 pages each) or 1 huge doc (914 pages).
MAX_OS_HITS = 2000

# Max NER entries returned to caller by fetch_content_ner_by_type.
MAX_NER_ENTRIES = 100


# Max unique documents returned by workspace aggregation.
MAX_AGG_BUCKETS = 200

# Nested query: max children scored per nested doc (rag:chunks).
# Caps scoring work from O(all_chunks) to O(N). A 500-page doc may have ~5000 chunks.
MAX_NESTED_CHILDREN = 50


# ---------------------------------------------------------------------------
# SearchContext — per-request credentials, stored in RunnableConfig.
# ---------------------------------------------------------------------------

SEARCH_CONTEXT_KEY = "search_context"


@dataclass
class SearchContext:
    """Per-request OpenSearch credentials, propagated via RunnableConfig."""

    search_service: SearchService | None = None
    ontology: str = ""  # Index name (e.g. "os_ontology_v1")
    timbr_token: str = ""  # Auth token for Timbr workspace filtering
    username: str = ""  # For Redis cache keying
    # None or empty = not established, filter server-side. Non-empty = filter locally.
    cached_workspaces: list[str] | None = None
    has_fragments: bool = False  # True if index has os_fragment entities (pages).
    doc_labels: dict[str, str] = field(
        default_factory=dict
    )  # entity_id → label (from load_context)
    # When True: BM25 and NER queries skip os_file (content is in fragments).
    # When False: queries search os_file directly (old index without fragments).


def get_search_context(config: RunnableConfig | None) -> SearchContext:
    """Extract SearchContext from RunnableConfig. Raises if not initialized."""
    if config is None:
        raise RuntimeError("config is None — cannot get SearchContext")
    ctx = config.get("configurable", {}).get(SEARCH_CONTEXT_KEY)  # type: ignore[arg-type]
    if ctx is not None:
        return ctx
    raise RuntimeError(
        "SearchContext not in config — call init_opensearch_tools() first"
    )


async def init_opensearch_tools(
    search_service: SearchService,
    ontology: str,
    timbr_token: str,
    username: str,
    config: RunnableConfig | None,
) -> None:
    """Initialize SearchContext and store in config. Called once per request.

    Tries Redis cache for workspace filter. If cache miss, the first query
    will use Timbr server-side filtering, then cache the result.
    """
    if not username:
        raise ValueError("username is required for workspace cache security")
    if config is None:
        raise RuntimeError("config is required to store SearchContext")

    ctx = SearchContext(
        search_service=search_service,
        ontology=ontology,
        timbr_token=timbr_token,
        username=username,
    )

    try:
        cached = await cache_get(username, "workspace_filter", ontology)
        if cached:
            ctx.cached_workspaces = cached
            logger.info(
                "init_opensearch_tools: workspace filter from Redis cache (%d ws)",
                len(cached),
            )
    except Exception as e:
        logger.warning("Redis cache unavailable for workspace_filter: %s", e)

    config.setdefault("configurable", {})[SEARCH_CONTEXT_KEY] = ctx  # type: ignore[typeddict-item]


# ---------------------------------------------------------------------------
# Source fields — returned by _source in every search query.
# Includes fragment navigation fields for page-level results.
# ---------------------------------------------------------------------------

SRC_FIELDS = [
    "document_fields.entity_id",  # UUID of this entity
    "document_fields.entity_type",  # os_file, os_fragment, os_folder, etc.
    "document_fields.entity_label",  # Human-readable name
    "document_fields.source_entity_uid",  # Parent file UUID (only on os_fragment)
    "document_fields.fragment_page_number",  # 1-based page number (only on os_fragment)
    "document_fields.fragment_index",  # 0-based page index (only on os_fragment)
    "document_fields.fragment_count",  # Total pages in parent file (only on os_fragment)
    "annotations.rag:chunks.metadata.text",  # Chunk text (per-chunk, not full page)
    "annotations.rag:chunks.metadata.field_name",  # Chunk role: extract:txt, summary:txt, etc.
]

# Extended fields — for fetch_entity_content / fetch_fragment_content.
# Includes rag:fulltext (needed for full-document reads in map_reduce)
# and prev/next UIDs for page navigation.
SRC_FIELDS_NAV = SRC_FIELDS + [
    "annotations.rag:fulltext",
    "document_fields.previous_entity_uid",
    "document_fields.next_entity_uid",
]


def truncate_vectors(obj: object) -> object:
    """Recursively replace any list of 50+ floats with a short placeholder."""
    if isinstance(obj, dict):
        return {k: truncate_vectors(v) for k, v in obj.items()}
    if isinstance(obj, list):
        if len(obj) > 50 and all(isinstance(x, (int, float)) for x in obj[:5]):
            return f"[{len(obj)} dims]"
        return [truncate_vectors(v) for v in obj]
    return obj


# ---------------------------------------------------------------------------
# Low-level search — all queries go through _proxy_search
# ---------------------------------------------------------------------------


async def _proxy_search(ctx: SearchContext, raw_payload: bytes) -> Any:
    """Execute msearch via SearchService with workspace filter optimization.

    Two states of cached_workspaces:
      empty/None → filtering happens server-side (need_workspace_filter=True)
      [ids]      → apply the filter locally before sending to OpenSearch

    There used to be a third: `[]` meaning "fetched, and no filter is needed". That
    reading turned an ambiguous answer into a permission decision, and cached it.
    """
    if ctx.search_service is None:
        raise RuntimeError("SearchContext.search_service not initialized")
    # A cached list only counts when it has entries. See the note on caching below: an
    # empty list must never be the reason a query goes out unfiltered.
    has_cache = bool(ctx.cached_workspaces)

    # Parse ndjson payload, inject standard filters (exclude chat entities, require
    # os_entity_uid). FAIL CLOSED: if the payload is not the ndjson shape this expects,
    # the filters cannot be injected, and the previous code sent the query anyway --
    # unfiltered, silently, on the path that enforces access scope.
    lines = raw_payload.decode("utf-8").strip().split("\n")
    if len(lines) < 2 or len(lines) % 2 != 0:
        raise RuntimeError(
            f"_proxy_search: malformed msearch payload ({len(lines)} lines); refusing "
            "to send a query whose mandatory filters could not be applied"
        )
    modified = []
    for i in range(0, len(lines), 2):
        header = lines[i]
        query = json.loads(lines[i + 1])
        # Exclude chat entities (content_type = chat+json) and require os_entity_uid
        apply_standard_search_filters(query)
        # With cached workspace IDs, apply the workspace filter locally
        if has_cache:
            ctx.search_service.add_workspaces_filter(query, ctx.cached_workspaces)
        modified.append(header)
        modified.append(json.dumps(query))
    raw_payload = ("\n".join(modified) + "\n").encode("utf-8")

    result = await ctx.search_service.proxy_search(
        ontology=ctx.ontology,
        raw_payload=raw_payload,
        need_workspace_filter=not has_cache,
        timbr_token=ctx.timbr_token,
    )

    # After the first uncached call, fetch the workspace list for future queries.
    #
    # An EMPTY result is never cached and never stored. "No workspaces" is ambiguous at
    # this boundary -- it can mean "this user is scoped to none", or a transient failure
    # upstream -- and the local optimisation used to read it as "no filter needed" and
    # keep that reading for the whole TTL. Left unset, the next query goes out with
    # need_workspace_filter=True and the filtering happens where the answer is known.
    if not has_cache and ctx.username:
        try:
            workspaces = await ctx.search_service.get_filter_workspaces(
                ctx.ontology, ctx.timbr_token
            )
            if workspaces:
                ctx.cached_workspaces = workspaces
                await cache_set(
                    ctx.username, "workspace_filter", ctx.ontology, value=workspaces
                )
                logger.info("_proxy_search: cached %d workspaces", len(workspaces))
            else:
                logger.info(
                    "_proxy_search: empty workspace list — not cached, filtering stays "
                    "server-side"
                )
        except Exception as e:
            logger.warning("_proxy_search: workspace lookup failed: %s", e)

    return result


def _trace_search_inputs(inputs: dict) -> dict:
    """Prepare os_search inputs for LangSmith traces (truncate vectors)."""
    body = inputs.get("body", {})
    return {"query": truncate_vectors(body)}


@traceable(
    run_type="retriever", name="opensearch_query", process_inputs=_trace_search_inputs
)
async def os_search(body: dict, config: RunnableConfig | None) -> dict:
    """Execute a single search query via msearch protocol. Returns the first response."""
    ctx = get_search_context(config)
    # Safety timeout — prevent runaway queries from blocking users
    body.setdefault("timeout", "30s")
    # msearch requires ndjson: header line + query line
    pref = json.dumps({"preference": "results"})
    payload = pref + "\n" + json.dumps(body) + "\n"

    result = await _proxy_search(ctx, payload.encode("utf-8"))
    if result.status_code != 200:
        raise RuntimeError(
            f"OpenSearch HTTP {result.status_code}: {result.content[:200]}"
        )

    parsed = json.loads(result.content.decode("utf-8"))
    responses = parsed.get("responses", [])
    if not responses:
        raise RuntimeError("OpenSearch msearch returned empty responses array")
    return responses[0]


async def os_msearch(raw_payload: bytes, config: RunnableConfig | None) -> Any:
    """Execute a raw msearch (multi-search) with multiple queries. Returns raw response.

    Used by parse_entity_context for batch document preview fetching.
    """
    ctx = get_search_context(config)
    return await _proxy_search(ctx, raw_payload)


# ---------------------------------------------------------------------------
# Hit parsing helpers
# ---------------------------------------------------------------------------


def extract_chunks_by_field(
    hit: dict, max_chars: int = MAX_HIT_TEXT_CHARS
) -> tuple[str, str]:
    """Extract content text and summary from a search hit's chunks.

    Reads ``rag:chunks[].metadata`` and splits by ``field_name``:
      - ``annotations.extract:txt`` → concatenated as content text
      - ``annotations.summary:txt`` → returned as summary

    Returns (content, summary).  Falls back to entity_label when no
    extract:txt chunks exist (images, non-PDF files).
    max_chars: truncation limit for content (0 = no limit).
    """
    src = hit.get("_source", {})
    chunks = src.get("annotations", {}).get("rag:chunks", [])

    content_parts: list[str] = []
    summary = ""
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        field_name = meta.get("field_name", "")
        text = meta.get("text", "")
        if not text:
            continue
        if field_name == "annotations.extract:txt":
            content_parts.append(text)
        elif field_name == "annotations.summary:txt":
            summary = text

    content = "\n".join(content_parts)
    if not content:
        content = src.get("document_fields", {}).get("entity_label", "")
    if max_chars:
        content = content[:max_chars]
    return sanitize_text(content), sanitize_text(summary)


def extract_text(hit: dict) -> str:
    """Extract text from a search hit (content only, no summary).

    Convenience wrapper over extract_chunks_by_field for callers that
    only need the content text.
    """
    content, _ = extract_chunks_by_field(hit)
    return content


def format_hit(hit: dict) -> dict:
    """Format a search hit for LLM consumption.

    Returns basic fields (id, label, type, score, text) plus fragment metadata
    (page number, parent file, position) when the hit is an os_fragment.
    """
    src = hit.get("_source", {})
    doc = src.get("document_fields", {})
    result = {
        "entity_id": doc.get("entity_id", ""),
        "entity_label": doc.get("entity_label", ""),
        "entity_type": doc.get("entity_type", ""),
        "score": hit.get("_score", 0),
        "text": extract_text(hit),
    }
    # Add fragment metadata if this hit is a page (os_fragment)
    if doc.get("source_entity_uid"):
        result["source_entity_uid"] = doc["source_entity_uid"]
        result["fragment_page_number"] = doc.get("fragment_page_number")
        result["fragment_index"] = doc.get("fragment_index")
        result["fragment_count"] = doc.get("fragment_count")
    return result


# ---------------------------------------------------------------------------
# Query builders — used by semantic_search and agent_tools
# ---------------------------------------------------------------------------


def build_text_query(query: str, fuzzy: bool = True) -> dict:
    """BM25 match on annotations.rag:fulltext — the concatenated full text of the entity.

    fuzzy=True uses fuzziness=AUTO for typo tolerance (1 edit for 3-5 char terms, 2 for 6+).
    fuzzy=False for exact keyword matching (phone numbers, IDs, case numbers).
    """
    q: dict = {"query": query}
    if fuzzy:
        q["fuzziness"] = "AUTO"
    return {"match": {"annotations.rag:fulltext": q}}


# ---------------------------------------------------------------------------
# Filter builders
# ---------------------------------------------------------------------------


def build_workspace_filter(workspace_id: str) -> list[dict]:
    """Filter results to a specific workspace by UUID."""
    if not workspace_id:
        return []
    return [{"term": {"document_fields.os_workspace.keyword": workspace_id}}]


def build_context_filter(entity_ids: list[str]) -> list[dict]:
    """Filter to specific entities AND their fragments (pages).

    Matches documents where:
      - entity_id is in the list (the entity itself), OR
      - source_entity_uid is in the list (a fragment/page belonging to that entity)

    This ensures that when the frontend sends a file UUID, we search
    both the file record and all its individual page fragments.
    """
    if not entity_ids:
        return []
    return [
        {
            "bool": {
                "should": [
                    {"terms": {"document_fields.entity_id.keyword": entity_ids}},
                    {
                        "terms": {
                            "document_fields.source_entity_uid.keyword": entity_ids
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        }
    ]


def build_scope_filter(
    entity_ids: list[str] | None = None, workspace_id: str = ""
) -> list[dict]:
    """Build the appropriate filter for the current scope.

    If context entity_ids are provided (user opened specific files), filter to those + fragments.
    Otherwise fall back to workspace filter (user is in a workspace without specific files open).
    """
    if entity_ids:
        return build_context_filter(entity_ids)
    return build_workspace_filter(workspace_id)


def build_doc_type_filter() -> list[dict]:
    """Return filter clause restricting to document entity types.

    Always includes both os_file and os_fragment — a workspace may have
    PDFs with fragments AND images without fragments. Excluding os_file
    when has_fragments=True drops images and other non-fragmented files.
    Filters out non-document entities (screenshots, XML, app files).
    """
    # TODO: evaluate if we need per-doc fragment detection instead of global.
    # Previously excluded os_file when has_fragments=True, but that drops
    # images/non-PDF files that have no fragments. RRF ranking naturally
    # prefers fragments (more text) over os_file for text-heavy docs.
    return [
        {"terms": {"document_fields.entity_type.keyword": ["os_file", "os_fragment"]}}
    ]


# ---------------------------------------------------------------------------
# Query functions — high-level data access used by graph nodes
# ---------------------------------------------------------------------------


async def count_scope_entities(
    entity_ids: list[str] | None = None,
    workspace_id: str = "",
    config: RunnableConfig | None = None,
) -> int:
    """Count total entities + fragments in scope.

    Used by understand_query to decide if map_reduce is feasible:
    each LLM call handles ~100 chunks, budget is 20 calls = 2000 chunks max.
    If count exceeds budget, strategy switches from map_reduce to plan_execute.

    Counts ALL entity types including fragments (pages) — that's the point,
    we need to know how many chunks the LLM would need to process.
    """
    filters = build_scope_filter(entity_ids, workspace_id)
    query = (
        {"bool": {"filter": filters}}
        if filters
        else {"bool": {"must": [{"match_all": {}}]}}
    )
    # Query: count-only (size=0), no hits returned.
    # track_total_hits=True: required here — this is the one query that needs exact count.
    # filter context: no scoring, just counting. Cached by OpenSearch.
    result = await os_search(
        {"size": 0, "track_total_hits": True, "query": query}, config
    )
    return result.get("hits", {}).get("total", {}).get("value", 0)


async def check_has_fragments(
    entity_ids: list[str] | None = None,
    workspace_id: str = "",
    config: RunnableConfig | None = None,
) -> bool:
    """Check if scope has os_fragment entities (pages).

    Returns True if at least one os_fragment exists in scope.
    Used by load_context to decide BM25 strategy:
      - True  → BM25 searches fragments only (skip os_file, content is in pages).
      - False → BM25 searches os_file directly (old index without fragments).
    terminate_after=1: stops after first match — near-instant.
    """
    filters = build_scope_filter(entity_ids, workspace_id)
    filter_clauses = [{"term": {"document_fields.entity_type.keyword": "os_fragment"}}]
    if filters:
        filter_clauses.extend(filters)
    result = await os_search(
        {
            "size": 1,
            "track_total_hits": False,
            "terminate_after": 1,
            "_source": False,
            "query": {"bool": {"filter": filter_clauses}},
        },
        config,
    )
    return len(result.get("hits", {}).get("hits", [])) > 0


async def fetch_ner_entities(
    entity_ids: list[str],
    config: RunnableConfig | None = None,
) -> dict[str, list[str]]:
    """Fetch NER (Named Entity Recognition) annotations from context entities.

    Returns {ner_type: [names]} e.g. {"person": ["Chiara Poggi", "Alberto Stasi"], "org": ["Carabinieri"]}.

    NER is populated on os_fragment (per-page) by the ingestion pipeline. When has_fragments=True,
    os_file is excluded (its NER is just metadata YAML noise).
    Names are title-cased and deduplicated.

    Used by load_context to provide NER data for understand_query (entity type filtering)
    and cross_document strategies (recurring name detection).

    """
    if not entity_ids:
        return {}
    # Query: bulk NER fetch — up to 5000 docs.
    # _source: only ner:entities — minimal payload (no fulltext).
    # filter context: all clauses are binary (cached, no scoring overhead).
    #   - build_context_filter: entity_id OR source_entity_uid match (file + its pages).
    #   - exists: skip docs without NER annotations.
    #   - build_doc_type_filter: only os_fragment (or os_file if no fragments).
    # sort: _doc — filter-only query, skip scoring entirely (saves CPU).
    # track_total_hits=False: we fetch everything, don't need the count.
    bool_q: dict[str, Any] = {
        "filter": [
            *build_context_filter(entity_ids),
            {"exists": {"field": "annotations.ner:entities"}},
            *build_doc_type_filter(),
        ]
    }
    result = await os_search(
        {
            "size": MAX_OS_HITS,
            "track_total_hits": False,
            "sort": ["_doc"],
            "_source": ["annotations.ner:entities"],
            "query": {"bool": bool_q},
        },
        config,
    )
    ner_entities: dict[str, list[str]] = {}
    for hit in result.get("hits", {}).get("hits", []):
        ner_data = hit.get("_source", {}).get("annotations", {}).get("ner:entities", {})
        for ner_type, names in ner_data.items():
            if isinstance(names, list):
                existing = ner_entities.get(ner_type, [])
                existing.extend(
                    n.strip().title()
                    for n in names
                    if isinstance(n, str) and len(n) >= 3
                )
                ner_entities[ner_type] = existing
    # Deduplicate and sort
    for k in ner_entities:
        ner_entities[k] = sorted(set(ner_entities[k]))
    return ner_entities


async def fetch_content_ner_by_type(
    entity_type: str,
    entity_ids: list[str] | None = None,
    workspace_id: str = "",
    config: RunnableConfig | None = None,
) -> list[dict]:
    """Fetch ALL values of a specific NER entity type (e.g. phone_number, person, loc).

    Returns list of {value, document_label, page_number} for every occurrence.
    Searches os_fragment when has_fragments=True (NER is per-page), os_file otherwise.

    Used by the list_all_entities_by_type agent tool to answer
    "list all phone numbers" / "list all addresses" type questions.

    """
    # Query: fetch NER values of a specific type across all entities in scope.
    # filter context only: exists + scope filter — no scoring needed (cached).
    #   - exists: skip docs without NER annotations.
    #   - scope filter: context_entity_ids (files+pages) OR workspace_id.
    # _source: metadata + ner:entities only — NO rag:fulltext (saves ~600MB on large scopes).
    # build_doc_type_filter: only os_fragment (or os_file if no fragments).
    # track_total_hits=False: fetching all matches, count not needed.
    filters = build_scope_filter(entity_ids, workspace_id)
    filter_clauses = [
        {"exists": {"field": "annotations.ner:entities"}},
        *build_doc_type_filter(),
    ]
    if filters:
        filter_clauses.extend(filters)
    query: dict = {"bool": {"filter": filter_clauses}}

    result = await os_search(
        {
            "size": MAX_OS_HITS,
            "track_total_hits": False,
            "sort": ["_doc"],  # filter-only query, skip scoring
            "_source": [
                "document_fields.entity_id",
                "document_fields.entity_label",
                "document_fields.source_entity_uid",
                "document_fields.fragment_page_number",
                "annotations.ner:entities",
            ],
            "query": query,
        },
        config,
    )

    entries: list[dict] = []
    seen: set[str] = set()
    for hit in result.get("hits", {}).get("hits", []):
        src = hit.get("_source", {})
        doc = src.get("document_fields", {})
        ner_data = src.get("annotations", {}).get("ner:entities", {})
        values = ner_data.get(entity_type, [])
        if not isinstance(values, list):
            continue
        doc_label = doc.get("entity_label", doc.get("entity_id", ""))
        page = doc.get("fragment_page_number")
        for val in values:
            if not isinstance(val, str) or len(val) < 2:
                continue
            # Dedup by value+doc to avoid repeating same entity from same doc
            key = (
                f"{val.lower()}|{doc.get('source_entity_uid') or doc.get('entity_id')}"
            )
            if key in seen:
                continue
            seen.add(key)
            entry: dict = {
                "value": val,
                "document": doc_label,
                "entity_id": doc.get("entity_id", ""),
            }
            if page is not None:
                entry["page"] = page
            entries.append(entry)
            if len(entries) >= MAX_NER_ENTRIES:
                break
        if len(entries) >= MAX_NER_ENTRIES:
            break

    return entries


async def batch_search_entity_by_label(
    names: list[str],
    workspace_id: str = "",
    config: RunnableConfig | None = None,
) -> dict[str, dict | None]:
    """Resolve entity names to IDs — one msearch for all names.

    The LLM writes **bold names** in its answer (e.g. **Chiara Poggi**).
    resolve_entity_links extracts those names and calls this function to
    find their entity_id + entity_type in OpenSearch, then replaces
    **name** with [name](entity:uuid/type) — a clickable link in the UI.

    We don't have the entity_id — only the name the LLM wrote. So we do
    match_phrase on entity_label to find the best match.

    Returns {name: {entity_id, entity_type, entity_label} | None}.
    """
    if not names:
        return {}
    # Batch msearch: N match_phrase queries in ONE HTTP roundtrip.
    # Each sub-query: match_phrase on entity_label (must) + workspace term (filter).
    # preference="results": consistent shard routing for cache hits.
    # timeout=10s per sub-query: safety net for slow shards.
    # _source: only 3 fields for entity link construction.
    ctx = get_search_context(config)
    lines: list[str] = []
    for name in names:
        lines.append(json.dumps({"preference": "results"}))
        bool_q: dict[str, Any] = {
            "must": [{"match_phrase": {"document_fields.entity_label": name}}],
        }
        if workspace_id:
            bool_q["filter"] = build_workspace_filter(workspace_id)
        body = {
            "size": 1,
            "track_total_hits": False,
            "timeout": "10s",
            "query": {"bool": bool_q},
            "_source": [
                "document_fields.entity_id",
                "document_fields.entity_type",
                "document_fields.entity_label",
            ],
        }
        lines.append(json.dumps(body))
    payload = "\n".join(lines) + "\n"
    result = await _proxy_search(ctx, payload.encode("utf-8"))
    if result.status_code != 200:
        logger.error("batch_search_entity_by_label HTTP %d", result.status_code)
        return {}
    parsed = json.loads(result.content.decode("utf-8"))
    responses = parsed.get("responses", [])
    results: dict[str, dict | None] = {}
    for name, resp in zip(names, responses):
        hits = resp.get("hits", {}).get("hits", [])
        if hits:
            doc = hits[0].get("_source", {}).get("document_fields", {})
            results[name] = {
                "entity_id": doc.get("entity_id", ""),
                "entity_type": doc.get("entity_type", ""),
                "entity_label": doc.get("entity_label", ""),
            }
        else:
            results[name] = None
    return results


async def batch_verify_entity_types(
    entity_ids: list[str], config: RunnableConfig | None = None
) -> dict[str, str]:
    """entity_id → entity_type, for the ids that exist.

    Thin wrapper so callers stop choosing between two return SHAPES with a boolean and
    casting the result: `include_label` made this function return dict[str, str] or
    dict[str, dict] depending on an argument, which is two functions wearing one name.
    """
    return await batch_verify_entity_ids(entity_ids, config, include_label=False)


async def batch_verify_entity_details(
    entity_ids: list[str], config: RunnableConfig | None = None
) -> dict[str, dict[str, str]]:
    """entity_id → {"type": ..., "label": ...}, for the ids that exist."""
    return await batch_verify_entity_ids(entity_ids, config, include_label=True)


async def batch_verify_entity_ids(
    entity_ids: list[str],
    config: RunnableConfig | None = None,
    include_label: bool = False,
) -> dict[str, str] | dict[str, dict[str, str]]:
    """Verify which entity_ids exist in OpenSearch.

    Returns {entity_id: entity_type} by default.
    With include_label=True, returns {entity_id: {"type": ..., "label": ...}}.

    Prevents hallucinations: the LLM may write entity links with invented UUIDs
    or wrong entity_types. This check validates the LLM response against OS
    in a single terms query — no LLM calls, just one OS roundtrip.
    Used by resolve_entity_links to strip fake links and fix wrong types.
    """
    if not entity_ids:
        return {}
    ids = list(set(entity_ids))
    ctx = get_search_context(config)
    body = {
        "size": len(ids),
        "track_total_hits": False,
        "_source": [
            "document_fields.entity_id",
            "document_fields.entity_type",
            "document_fields.entity_label",
        ],
        "query": {
            "bool": {"filter": [{"terms": {"document_fields.entity_id.keyword": ids}}]}
        },
    }
    payload = json.dumps({"preference": "results"}) + "\n" + json.dumps(body) + "\n"
    result = await _proxy_search(ctx, payload.encode("utf-8"))
    if result.status_code != 200:
        logger.error("batch_verify_entity_ids HTTP %d", result.status_code)
        if include_label:
            return {eid: {"type": "", "label": ""} for eid in ids}
        return {eid: "" for eid in ids}  # on error, assume all valid — don't strip
    parsed = json.loads(result.content.decode("utf-8"))
    hits = parsed.get("responses", [{}])[0].get("hits", {}).get("hits", [])
    verified: dict = {}
    for hit in hits:
        df = hit.get("_source", {}).get("document_fields", {})
        eid = df.get("entity_id", "")
        etype = df.get("entity_type", "")
        if eid:
            if include_label:
                verified[eid] = {
                    "type": etype,
                    "label": df.get("entity_label", ""),
                }
            else:
                verified[eid] = etype
    return verified


async def fetch_entities_by_ids(
    entity_ids: list[str],
    config: RunnableConfig | None = None,
) -> list[dict]:
    """Fetch entity summaries (id, label, type) by their IDs.

    EXCLUDES fragments — filters by exact entity_id only (not source_entity_uid).
    Used by list_documents tool to show the user what files are in scope.
    """
    if not entity_ids:
        return []
    # Query: fetch entity summaries by exact IDs (no fragments).
    # filter context: terms on entity_id.keyword — cached, no scoring.
    #   NOT build_context_filter — we want files only, not their 200 page fragments.
    # _source: only 3 metadata fields — minimal payload.
    # track_total_hits=False: we know how many we asked for.
    result = await os_search(
        {
            "size": len(entity_ids),
            "track_total_hits": False,
            "sort": ["_doc"],  # filter-only, skip scoring
            "query": {
                "bool": {
                    "filter": [
                        {"terms": {"document_fields.entity_id.keyword": entity_ids}},
                    ]
                }
            },
            "_source": [
                "document_fields.entity_id",
                "document_fields.entity_label",
                "document_fields.entity_type",
            ],
        },
        config,
    )
    docs = []
    seen: set[str] = set()
    for h in result.get("hits", {}).get("hits", []):
        df = h.get("_source", {}).get("document_fields", {})
        eid = df.get("entity_id", "")
        if eid and eid not in seen:
            seen.add(eid)
            docs.append(
                {
                    "entity_id": eid,
                    "entity_label": df.get("entity_label", eid),
                    "entity_type": df.get("entity_type", ""),
                }
            )
    return docs


async def _read_all_fragments_text(
    parent_id: str, config: RunnableConfig | None
) -> str:
    """Read all fragments of a document and concatenate text, sorted by page number.

    Used by fetch_entity_content when the entity is an os_file with fragments.
    One query fetches all pages, sorted by fragment_index for correct order.
    """
    result = await os_search(
        {
            "size": MAX_OS_HITS,
            "track_total_hits": False,
            "sort": [{"document_fields.fragment_index": "asc"}],
            "_source": [
                "annotations.rag:chunks.metadata.text",
                "annotations.rag:chunks.metadata.field_name",
                "annotations.rag:fulltext",
            ],
            "query": {
                "bool": {
                    "filter": [
                        {
                            "term": {
                                "document_fields.source_entity_uid.keyword": parent_id
                            }
                        },
                        {
                            "term": {
                                "document_fields.entity_type.keyword": "os_fragment"
                            }
                        },
                    ]
                }
            },
        },
        config,
    )
    parts = []
    for hit in result.get("hits", {}).get("hits", []):
        text, _ = extract_chunks_by_field(hit, max_chars=0)
        if not text:
            text = hit.get("_source", {}).get("annotations", {}).get("rag:fulltext", "")
        if text:
            parts.append(text)
    return "\n".join(parts)


async def fetch_entity_content(
    doc_id: str,
    config: RunnableConfig | None = None,
) -> dict:
    """Fetch full content of a single entity by exact ID.

    Returns {entity_id, entity_label, entity_type, text} or {error: ...}.
    Used by read_document tool and map_reduce to read full document text.

    When the entity is an os_file with fragments (has_fragments=True), reads all
    fragments (pages) via source_entity_uid and concatenates their text.
    """
    # Query: fetch one entity by ID or label.
    # filter context (no scoring): this is a lookup, not a relevance search.
    #   - should[0]: exact term match on entity_id.keyword (normal UUID lookup).
    #   - should[1]: exact term match on entity_label.keyword (fallback when LLM passes name).
    #   - minimum_should_match=1: either match suffices.
    # _source: SRC_FIELDS_NAV (includes prev/next for page navigation).
    result = await os_search(
        {
            "size": 1,
            "track_total_hits": False,
            "_source": SRC_FIELDS_NAV,
            "query": {
                "bool": {
                    "filter": [
                        {
                            "bool": {
                                "should": [
                                    {
                                        "term": {
                                            "document_fields.entity_id.keyword": doc_id
                                        }
                                    },
                                    {
                                        "term": {
                                            "document_fields.entity_label.keyword": doc_id
                                        }
                                    },
                                ],
                                "minimum_should_match": 1,
                            }
                        }
                    ]
                }
            },
        },
        config,
    )
    hits = result.get("hits", {}).get("hits", [])
    if not hits:
        return {"error": f"Document not found: {doc_id}"}
    src = hits[0].get("_source", {})
    doc = src.get("document_fields", {})
    text, _ = extract_chunks_by_field(hits[0], max_chars=0)
    if not text:
        text = src.get("annotations", {}).get("rag:fulltext", "")
    entity_type = doc.get("entity_type", "")
    entity_id = doc.get("entity_id", "")

    # If this is an os_file with fragments, the file's own rag:fulltext is just
    # metadata YAML. Read all fragments (pages) and concatenate their text instead.
    # Only replace if fragments actually exist — images/non-PDF files have no fragments
    # and their rag:fulltext is the only content available.
    ctx = config.get("configurable", {}).get(SEARCH_CONTEXT_KEY) if config else None
    if entity_type == "os_file" and ctx and ctx.has_fragments:
        fragment_text = await _read_all_fragments_text(entity_id, config)
        if fragment_text:
            text = fragment_text

    result_dict = {
        "entity_id": entity_id,
        "entity_label": doc.get("entity_label", ""),
        "entity_type": entity_type,
        "text": sanitize_text(text[:MAX_DOC_TEXT_CHARS]),
    }
    # Include fragment metadata when the entity is a page (os_fragment)
    if doc.get("source_entity_uid"):
        result_dict["source_entity_uid"] = doc["source_entity_uid"]
        result_dict["fragment_page_number"] = doc.get("fragment_page_number")
        result_dict["fragment_index"] = doc.get("fragment_index")
        result_dict["fragment_count"] = doc.get("fragment_count")
        result_dict["previous_entity_uid"] = doc.get("previous_entity_uid") or ""
        result_dict["next_entity_uid"] = doc.get("next_entity_uid") or ""
    return result_dict


async def fetch_fragment_content(
    fragment_id: str,
    config: RunnableConfig | None = None,
    neighbor_pages: int = 1,
) -> dict:
    """Fetch a single fragment (page) plus surrounding pages for context.

    Args:
        fragment_id: UUID of the target fragment.
        config: RunnableConfig with SearchContext.
        neighbor_pages: how many pages to fetch before AND after the target (default 1).
            0 = target only, 1 = prev+next, 2 = prev2+prev1+next1+next2, etc.

    Returns {entity_id, entity_label, page, total_pages, source_file, text,
             prev_text, next_text} or {error: ...}.

    Used when the LLM already knows which page it wants — avoids reading
    the entire document just to get one page. More neighbor_pages = more
    cross-page context for questions spanning page boundaries.

    IMPORTANT: prev_text and next_text are READING CONTEXT ONLY.
    The entity_id, page, source_file in the result are always from the TARGET
    page (the one that matched BM25/KNN). The LLM should cite/reference the
    target page, not the neighbors. Neighbors help the LLM understand the
    content around the match, but are not the source of the answer.
    """
    # Step 1: Fetch the target fragment
    target = await fetch_entity_content(fragment_id, config)
    if "error" in target:
        return target
    if target.get("entity_type") != "os_fragment":
        return target  # Not a fragment, return as-is

    # Result always references the TARGET page — neighbors are context only.
    result_dict = {
        "entity_id": target["entity_id"],
        "entity_label": target.get("entity_label", ""),
        "page": target.get("fragment_page_number"),
        "total_pages": target.get("fragment_count"),
        "source_file": target.get("source_entity_uid", ""),
        "text": target.get("text", ""),
    }

    if neighbor_pages <= 0:
        return result_dict

    # Step 2: Fetch neighbor pages by fragment_index range.
    # One query: filter by source_entity_uid (same parent file) + range on fragment_index.
    # Much simpler than walking the linked list hop by hop.
    page_idx = target.get("fragment_index")
    parent_id = target.get("source_entity_uid", "")
    if page_idx is not None and parent_id:
        range_start = max(0, page_idx - neighbor_pages)
        range_end = page_idx + neighbor_pages
        neighbors = await os_search(
            {
                "size": neighbor_pages * 2,
                "track_total_hits": False,
                "sort": [{"document_fields.fragment_index": "asc"}],
                "_source": [
                    "document_fields.fragment_index",
                    "annotations.rag:fulltext",
                ],
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "document_fields.source_entity_uid.keyword": parent_id
                                }
                            },
                            {
                                "term": {
                                    "document_fields.entity_type.keyword": "os_fragment"
                                }
                            },
                            {
                                "range": {
                                    "document_fields.fragment_index": {
                                        "gte": range_start,
                                        "lte": range_end,
                                    }
                                }
                            },
                        ],
                        "must_not": [
                            {"term": {"document_fields.fragment_index": page_idx}},
                        ],
                    }
                },
            },
            config,
        )
        prev_parts = []
        next_parts = []
        for hit in neighbors.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            idx = src.get("document_fields", {}).get("fragment_index")
            text = sanitize_text(
                src.get("annotations", {}).get("rag:fulltext", "")[:MAX_DOC_TEXT_CHARS]
            )
            if idx is not None and text:
                if idx < page_idx:
                    prev_parts.append(text)
                else:
                    next_parts.append(text)
        if prev_parts:
            result_dict["prev_text"] = "\n".join(prev_parts)
        if next_parts:
            result_dict["next_text"] = "\n".join(next_parts)

    return result_dict


async def full_text_search(
    query_text: str,
    entity_ids: list[str] | None = None,
    workspace_id: str = "",
    size: int = 10,
    config: RunnableConfig | None = None,
) -> list[dict]:
    """BM25 keyword search on rag:fulltext only. Returns formatted hits.

    Searches annotations.rag:fulltext (flat field, no nested overhead).
    Does NOT search rag:chunks — same text split into pieces, redundant for BM25.
    Excludes os_file hits when has_fragments (content is in fragments).

    Used by the full_text_search agent tool for exact keyword matching
    (names, phone numbers, IDs) as opposed to semantic/vector search.
    """
    # Query: BM25 exact keyword search (no fuzziness — precision over recall).
    # BM25 on rag:fulltext only — chunks contain the same text split into pieces,
    # so searching both is redundant. Chunks are only needed for KNN (embeddings).
    # filter: scope filter (context_entity_ids or workspace_id) + doc type — cached, no scoring.
    q: dict = {"bool": {"must": [build_text_query(query_text, fuzzy=False)]}}
    scope = build_scope_filter(entity_ids, workspace_id)
    doc_type = build_doc_type_filter()
    filters = [*scope, *doc_type]
    if filters:
        q["bool"]["filter"] = filters
    body: dict = {
        "size": size,
        "track_total_hits": False,
        "query": q,
        "_source": SRC_FIELDS,
        "highlight": {
            "fields": {
                "annotations.rag:fulltext": {
                    "fragment_size": 200,
                    "number_of_fragments": 3,
                }
            },
            "pre_tags": ["<<"],
            "post_tags": [">>"],
        },
    }
    result = await os_search(body, config)
    return [
        _format_hit_with_highlights(h) for h in result.get("hits", {}).get("hits", [])
    ]


def _format_hit_with_highlights(hit: dict) -> dict:
    """Format a search hit using highlights (snippets) instead of full page text."""
    src = hit.get("_source", {})
    doc = src.get("document_fields", {})

    # Use highlights if available, otherwise fall back to full text
    highlights = hit.get("highlight", {}).get("annotations.rag:fulltext", [])
    if highlights:
        text = " ... ".join(highlights)
    else:
        text = extract_text(hit)

    result = {
        "entity_id": doc.get("entity_id", ""),
        "entity_label": doc.get("entity_label", ""),
        "entity_type": doc.get("entity_type", ""),
        "score": hit.get("_score", 0),
        "text": text,
    }
    if doc.get("source_entity_uid"):
        result["source_entity_uid"] = doc["source_entity_uid"]
        result["fragment_page_number"] = doc.get("fragment_page_number")
        result["fragment_count"] = doc.get("fragment_count")
    return result


async def list_workspace_docs_agg(
    workspace_id: str,
    config: RunnableConfig | None = None,
) -> list[dict]:
    """List unique documents in a workspace using aggregation. Returns [{entity_id, entity_label, entity_type}].

    EXCLUDES fragments (os_fragment) — we want top-level documents only,
    not every individual page. Without this filter, a workspace with 13 files
    and 4817 fragments would return fragment IDs instead of file IDs.

    Uses terms aggregation on entity_id.keyword with a sub-aggregation
    on entity_label.keyword to get the human-readable name.
    """
    filters = build_workspace_filter(workspace_id)
    # Exclude fragments — they are individual pages, not top-level documents
    must_not = [{"term": {"document_fields.entity_type.keyword": "os_fragment"}}]
    query: dict = {"bool": {}}
    if filters:
        query["bool"]["filter"] = filters
    query["bool"]["must_not"] = must_not
    # Query: aggregation-only (size=0) — list unique documents in workspace.
    # No hits returned, only agg buckets.
    # track_total_hits=False: agg-only, count not needed.
    # terms agg on entity_id.keyword:
    #   - shard_size=2x: extra candidates per shard for accuracy on distributed index.
    #   - execution_hint=global_ordinals: fastest for high-cardinality keyword fields.
    # Sub-agg on entity_label.keyword (size=1): one label per doc bucket.
    # filter: workspace_id term filter (cached).
    # must_not: exclude os_fragment — only top-level files/folders.
    body = {
        "size": 0,
        "track_total_hits": False,
        "query": query,
        "aggs": {
            "documents": {
                "terms": {
                    "field": "document_fields.entity_id.keyword",
                    "size": MAX_AGG_BUCKETS,
                    "shard_size": MAX_AGG_BUCKETS * 2,
                    "execution_hint": "global_ordinals",
                },
                "aggs": {
                    "label": {
                        "terms": {
                            "field": "document_fields.entity_label.keyword",
                            "size": 1,
                        }
                    },
                },
            }
        },
    }
    result = await os_search(body, config)
    docs = []
    for bucket in (
        result.get("aggregations", {}).get("documents", {}).get("buckets", [])
    ):
        labels = bucket.get("label", {}).get("buckets", [])
        docs.append(
            {
                "entity_id": bucket["key"],
                "entity_label": labels[0]["key"] if labels else bucket["key"],
                "entity_type": "os_file",
            }
        )
    return docs


# ---------------------------------------------------------------------------
# Cross-document queries — used by cross_document_tools logic
# ---------------------------------------------------------------------------


async def search_term_across_docs(
    term: str,
    doc_ids: list[str],
    config: RunnableConfig | None,
) -> dict[str, int] | None:
    """Search for a term across multiple documents, return {doc_id: hit_count}.

    BM25 on rag:fulltext + entity_label only (no chunks — redundant).
    Aggregates by entity_id to see which docs contain the term.
    Excludes os_file when has_fragments (content is in fragments).
    Returns None if the term appears in 0 or 1 documents (not cross-doc).
    """
    # Query: cross-document term frequency — agg-only (size=0).
    # must: BM25 match on fulltext + entity_label (OR).
    #   - rag:fulltext: full page text BM25 match (operator=and: all words must appear).
    #   - entity_label: document name match.
    #   No nested chunk BM25 — fulltext already contains the same text.
    # filter: terms on entity_id.keyword — restrict to specific doc set (cached).
    # agg: per_doc terms — count how many docs contain the term.
    # track_total_hits=False: agg-only, no count needed.
    text_match = {
        "bool": {
            "should": [
                {
                    "match": {
                        "annotations.rag:fulltext": {"query": term, "operator": "and"}
                    }
                },
                {
                    "match": {
                        "document_fields.entity_label": {
                            "query": term,
                            "operator": "and",
                        }
                    }
                },
            ],
            "minimum_should_match": 1,
        }
    }
    bool_q: dict[str, Any] = {
        "filter": [
            {"terms": {"document_fields.entity_id.keyword": doc_ids}},
            *build_doc_type_filter(),
        ],
        "must": [text_match],
    }
    body = {
        "size": 0,
        "track_total_hits": False,
        "query": {"bool": bool_q},
        "aggs": {
            "per_doc": {
                "terms": {
                    "field": "document_fields.entity_id.keyword",
                    "size": len(doc_ids),
                    "shard_size": len(doc_ids) * 2,
                    "execution_hint": "global_ordinals",
                },
            },
        },
    }
    result = await os_search(body, config)
    buckets = result.get("aggregations", {}).get("per_doc", {}).get("buckets", [])
    if len(buckets) > 1:
        return {b["key"]: b["doc_count"] for b in buckets}
    return None


async def get_unique_doc_ids(
    workspace_id: str,
    config: RunnableConfig | None,
) -> list[str]:
    """Get all unique document entity_ids in a workspace via terms aggregation."""
    filters = build_workspace_filter(workspace_id)
    query = (
        {"bool": {"filter": filters}}
        if filters
        else {"bool": {"must": [{"match_all": {}}]}}
    )
    # Query: aggregation-only (size=0) — unique entity IDs in workspace.
    # track_total_hits=False: agg-only, no count needed.
    # terms agg: shard_size=2x for accuracy, global_ordinals for speed.
    # filter: workspace_id term filter (cached) or match_all.
    body = {
        "size": 0,
        "track_total_hits": False,
        "query": query,
        "aggs": {
            "docs_by_id": {
                "terms": {
                    "field": "document_fields.entity_id.keyword",
                    "size": MAX_AGG_BUCKETS,
                    "shard_size": MAX_AGG_BUCKETS * 2,
                    "execution_hint": "global_ordinals",
                },
            },
        },
    }
    result = await os_search(body, config)
    buckets = result.get("aggregations", {}).get("docs_by_id", {}).get("buckets", [])
    return [b["key"] for b in buckets]


async def fetch_doc_labels(
    doc_ids: list[str],
    config: RunnableConfig | None,
) -> dict[str, str]:
    """Fetch {entity_id: entity_label} mapping for a list of doc IDs."""
    if not doc_ids:
        return {}
    # Query: fetch id→label mapping for display.
    # filter context: terms on entity_id.keyword — exact ID lookup, cached.
    # _source: only 2 fields — minimal payload.
    # track_total_hits=False: known result count.
    result = await os_search(
        {
            "size": len(doc_ids),
            "track_total_hits": False,
            "sort": ["_doc"],  # filter-only, skip scoring
            "_source": ["document_fields.entity_id", "document_fields.entity_label"],
            "query": {
                "bool": {
                    "filter": [
                        {"terms": {"document_fields.entity_id.keyword": doc_ids}}
                    ]
                }
            },
        },
        config,
    )
    labels: dict[str, str] = {}
    for hit in result.get("hits", {}).get("hits", []):
        doc = hit.get("_source", {}).get("document_fields", {})
        eid = doc.get("entity_id", "")
        label = doc.get("entity_label", "")
        if eid and label:
            labels[eid] = label
    return labels


async def fetch_ner_per_doc(
    doc_ids: list[str],
    config: RunnableConfig | None,
) -> list[dict]:
    """Fetch NER annotations per document. Returns raw hits [{entity_id, ner:entities}].

    Used by cross-document analysis to count which entity names appear in which docs.
    Only returns docs that have NER annotations.
    """
    if not doc_ids:
        return []
    # Query: fetch NER annotations per doc for cross-document name counting.
    # filter context: terms (exact IDs) + exists (has NER) — both cached, no scoring.
    # _source: entity_id + ner:entities only — minimal payload.
    # track_total_hits=False: known max result count.
    result = await os_search(
        {
            "size": len(doc_ids),
            "track_total_hits": False,
            "sort": ["_doc"],  # filter-only, skip scoring
            "_source": ["document_fields.entity_id", "annotations.ner:entities"],
            "query": {
                "bool": {
                    "filter": [
                        {"terms": {"document_fields.entity_id.keyword": doc_ids}},
                        {"exists": {"field": "annotations.ner:entities"}},
                    ]
                }
            },
        },
        config,
    )
    return result.get("hits", {}).get("hits", [])
