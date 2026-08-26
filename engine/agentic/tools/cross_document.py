"""Cross-document analysis logic — find recurring entities across documents.

Pure business logic: NER candidate extraction, name normalization, variant merging.
All OpenSearch queries are in opensearch_repository.py.
"""

import logging
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig

from .opensearch_repository import (
    fetch_doc_labels,
    fetch_ner_per_doc,
)

logger = logging.getLogger(__name__)


async def do_find_recurring_names(
    doc_ids: List[str],
    config: RunnableConfig | None,
    workspace_id: str = "",
    extra_names: List[str] | None = None,
    entity_types: List[str] | None = None,
    ner_entities: dict | None = None,
) -> List[Dict[str, Any]]:
    """Find entity names recurring across multiple documents.

    Steps:
      1. Fetch doc labels from DAO for display
      2. Build candidate name set from NER entities + extra_names
      3. Fetch NER per doc from DAO
      4. Count which candidates appear in which docs
      5. Return names found in >1 document, sorted by frequency
    """
    # Step 1: Get doc_labels for display
    doc_labels = await fetch_doc_labels(doc_ids, config)

    # Step 2: Build candidate names from NER entities (loaded in load_context)
    candidates: set[str] = set()

    if ner_entities:
        ner_keys = entity_types if entity_types else list(ner_entities.keys())
        logger.info(
            "do_find_recurring_names: using NER types: %s (from %s available)",
            ner_keys,
            list(ner_entities.keys()),
        )
        for ner_type in ner_keys:
            names = ner_entities.get(ner_type, [])
            if isinstance(names, list):
                for name in names:
                    if isinstance(name, str) and len(name) >= 3:
                        candidates.add(name)

    logger.info(
        "do_find_recurring_names: %d NER candidates from context docs",
        len(candidates),
    )

    # Add extra names if provided (e.g. from user query)
    if extra_names:
        for name in extra_names:
            if len(name) >= 3:
                candidates.add(name)
                # Also add reversed form for name/surname matching
                words = name.split()
                if len(words) == 2:
                    candidates.add(f"{words[1]} {words[0]}")

    all_candidates = sorted(candidates)
    if not all_candidates:
        return []

    logger.info(
        "do_find_recurring_names: %d entity candidates from index", len(all_candidates)
    )

    # Step 3: Fetch NER per doc from DAO
    ner_hits = await fetch_ner_per_doc(doc_ids, config)

    # Step 4: Count which candidates appear in which docs
    def _norm(n: str) -> str:
        """Normalize name for comparison — sort 2-word names alphabetically."""
        words = n.lower().split()
        return " ".join(sorted(words)) if len(words) == 2 else n.lower()

    candidate_norms = {_norm(c): c for c in all_candidates}
    name_to_docs: Dict[str, set] = {}

    for hit in ner_hits:
        src = hit.get("_source", {})
        doc_id = src.get("document_fields", {}).get("entity_id", "")
        ner_data = src.get("annotations", {}).get("ner:entities", {})
        for names in ner_data.values():
            if not isinstance(names, list):
                continue
            for name in names:
                if not isinstance(name, str) or len(name) < 3:
                    continue
                normed = _norm(name.strip().title())
                if normed in candidate_norms:
                    display = candidate_norms[normed]
                    name_to_docs.setdefault(display, set()).add(doc_id)

    # Step 5: Return names found in >1 document
    recurring: List[Dict[str, Any]] = [
        {
            "name": name,
            "document_count": len(docs),
            "documents": [doc_labels.get(d, d) for d in sorted(docs)],
        }
        for name, docs in name_to_docs.items()
        if len(docs) > 1
    ]

    recurring.sort(key=lambda x: x["document_count"], reverse=True)
    recurring = _merge_name_variants(recurring)

    logger.info(
        "do_find_recurring_names: %d candidates → %d recurring | top: %s",
        len(all_candidates),
        len(recurring),
        [(r["name"], r["document_count"]) for r in recurring[:5]],
    )
    return recurring


def _merge_name_variants(
    recurring: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge reversed name/surname variants (e.g. 'SURNAME NAME' + 'NAME SURNAME').

    If "Poggi Chiara" and "Chiara Poggi" both appear, merge into one entry
    keeping the first form and combining document lists.
    """
    merged: List[Dict[str, Any]] = []
    consumed: set[int] = set()

    for i, entry in enumerate(recurring):
        if i in consumed:
            continue
        parts = entry["name"].lower().split()
        if len(parts) != 2:
            merged.append(entry)
            continue

        reversed_name = f"{parts[1]} {parts[0]}"
        match_idx = None
        for j in range(i + 1, len(recurring)):
            if j in consumed:
                continue
            if recurring[j]["name"].lower() == reversed_name:
                match_idx = j
                break

        if match_idx is not None:
            other = recurring[match_idx]
            consumed.add(match_idx)
            all_docs = list(dict.fromkeys(entry["documents"] + other["documents"]))
            merged.append(
                {
                    "name": entry["name"],
                    "document_count": len(all_docs),
                    "documents": all_docs,
                }
            )
        else:
            merged.append(entry)

    return merged
