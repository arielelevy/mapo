"""Parse entity context — extract context_doc_ids + build previews.

Uses ONE msearch to fetch doc metadata (label, size, language) for classification.
"""

import json
import logging

from langchain_core.runnables import RunnableConfig

from .tools.opensearch_repository import os_msearch

logger = logging.getLogger(__name__)


async def build_document_metadata(
    doc_ids: list[str],
    config: RunnableConfig | None = None,
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Batch-fetch doc metadata for classification in ONE msearch request.

    Fetches label, fragment_count, and language per doc — no BM25 scoring.
    Returns: (previews, doc_labels, document_languages)

    The old signature took a `user_query` it never read, and returned nothing when that
    argument was empty: the document metadata — labels, page counts, languages, all of
    it independent of the question — disappeared because of a parameter the function
    did not use.
    """
    if not doc_ids:
        return {}, {}, []

    msearch_lines = []
    for did in doc_ids:
        msearch_lines.append(json.dumps({"preference": "results"}))
        doc_filter = {
            "bool": {
                "should": [
                    {"match_phrase": {"document_fields.entity_label": did}},
                    {"term": {"document_fields.entity_id.keyword": did}},
                    {"term": {"document_fields.source_entity_uid.keyword": did}},
                ],
                "minimum_should_match": 1,
            }
        }
        msearch_lines.append(
            json.dumps(
                {
                    "size": 1,
                    "timeout": "10s",
                    "query": {"bool": {"filter": [doc_filter]}},
                    "_source": [
                        "document_fields.entity_label",
                        "document_fields.entity_type",
                        "document_fields.fragment_count",
                        "annotations.extract:txtLang",
                        "annotations.rag:fulltext",
                    ],
                    "track_total_hits": True,
                }
            )
        )

    msearch_body = "\n".join(msearch_lines) + "\n"
    resp = await os_msearch(msearch_body.encode("utf-8"), config)
    if resp is None or resp.status_code != 200:
        status = resp.status_code if resp else "None"
        body = resp.content[:500] if resp else b""
        raise RuntimeError(f"build_document_metadata: msearch HTTP {status}: {body}")
    msearch_result = json.loads(resp.content.decode("utf-8"))

    doc_metadata: dict[str, str] = {}
    doc_labels: dict[str, str] = {}
    document_languages: list[str] = []
    responses = msearch_result.get("responses", [])

    for i, did in enumerate(doc_ids):
        if i >= len(responses):
            break

        resp_i = responses[i]
        total = resp_i.get("hits", {}).get("total", {}).get("value", 0)
        hits = resp_i.get("hits", {}).get("hits", [])

        label = ""
        lang = ""
        entity_type = ""
        fragment_count = 0

        if hits:
            src = hits[0].get("_source", {})
            doc_fields = src.get("document_fields", {})
            label = doc_fields.get("entity_label", "")
            entity_type = doc_fields.get("entity_type", "")
            fragment_count = doc_fields.get("fragment_count") or 0
            lang = src.get("annotations", {}).get("extract:txtLang", "")

        if label and did not in doc_labels:
            doc_labels[did] = label
        if lang and lang not in document_languages:
            document_languages.append(lang)

        parts = []
        parts.append(f"type: {entity_type or 'unknown'}")
        if fragment_count:
            parts.append(f"pages: {fragment_count}")
        parts.append(f"indexed_chunks: {total}")
        if lang:
            parts.append(f"language: {lang}")
        doc_metadata[did] = " | ".join(parts)

    logger.info(
        "build_document_metadata: %d docs, 1 msearch, labels=%s",
        len(doc_ids),
        list(doc_labels.values()),
    )
    if document_languages:
        logger.info(
            "build_document_metadata: detected languages: %s", document_languages
        )
    return doc_metadata, doc_labels, document_languages
