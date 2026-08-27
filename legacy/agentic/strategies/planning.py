"""Shared planner context for the two decomposing strategies.

`pe_plan` and `dag_plan` both open by telling the planner which documents exist and
which domain they are in. That preamble was written twice, from the same state, with
the same regex over entity_context — and the two copies had already diverged: only one
of them mentioned the document languages.
"""

from __future__ import annotations

import re
from typing import Any

from ..agent_config import DOMAIN_INSTRUCTIONS

# Document headers in entity_context look like: --- [label](entity:id/type) ---
_DOC_LABEL_RE = re.compile(r"--- \[(.+?)\] ---")


def planner_context(state: Any) -> str:
    """Available documents + domain hint + document languages, as prompt text."""
    entity_context = state.get("entity_context", "")
    labels = _DOC_LABEL_RE.findall(entity_context) if entity_context else []
    parts = []
    if labels:
        parts.append(
            "\nAvailable documents:\n" + "\n".join(f"- {label}" for label in labels)
        )

    domain = state.get("document_domain", "general")
    if domain != "general":
        extra = DOMAIN_INSTRUCTIONS.get(domain, "")
        if extra:
            parts.append(f"\n\nDocument domain: {domain}{extra}")
        languages = state.get("document_languages", [])
        if languages:
            parts.append(
                f"\nDocument languages: {', '.join(languages)}"
                "\nWrite the sub-questions in the DOCUMENT LANGUAGE: they become search "
                "queries."
            )
    return "".join(parts)
