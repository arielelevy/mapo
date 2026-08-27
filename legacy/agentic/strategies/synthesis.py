"""Shared final-answer assembly for the fan-out strategies.

`dag_synthesize` and `pe_aggregate` were the same function twice: collect the
sub-results, cap each one, glue the blackboard on the end, and make one streaming call
that merges everything. The two copies had already drifted in their caps and in what
they pasted onto the context, so the same query answered through two strategies got two
different amounts of evidence for reasons nobody chose.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from ..blackboard import Blackboard
from ..config import TEMP_FORMAT, get_chat_model
from ..utils import build_aggregate_messages

logger = logging.getLogger(__name__)


def build_sections(
    items: list[tuple[str, str]],
    per_item_chars: int,
    tool_context_chars: int,
) -> tuple[str, str]:
    """(combined prose, tool_context) from (label, text) pairs.

    `tool_context` is the material the faithfulness check reads afterwards, so it is
    built from the same text the synthesiser sees and never from a different slice.
    """
    sections = []
    context_parts = []
    for label, text in items:
        body = (text or "")[:per_item_chars]
        sections.append(f"### {label}\n{body}")
        context_parts.append(body)
    return "\n\n".join(sections), "\n---\n".join(context_parts)[:tool_context_chars]


def append_coverage(combined: str, board: Blackboard | None) -> str:
    """Attach what was and was not covered — and nothing else.

    Both strategies used to paste `board.render()` here, which carries the operating
    record: the tool calls already executed, the "do NOT repeat these" instruction, the
    per-item checkmarks. That is bookkeeping for an agent mid-investigation, and it was
    being handed to the model that writes the user's answer as if it were evidence.
    What the synthesiser needs from the board is coverage, which is one paragraph.
    """
    if board is None or board.total_count == 0:
        return combined
    return combined + "\n\n" + board.coverage_summary()


def append_scope_warnings(combined: str, state: Any) -> str:
    """Surface anything that narrowed the corpus, so the answer can say it."""
    warnings = state.get("scope_warnings", []) if hasattr(state, "get") else []
    if not warnings:
        return combined
    return (
        combined
        + "\n\n## Coverage warnings (state these in the answer)\n"
        + "\n".join(f"- {w}" for w in warnings)
    )


async def final_answer(
    system_prompt: str,
    query: str,
    state: Any,
    combined: str,
    config: RunnableConfig | None,
) -> Any:
    """The one streaming merge call both strategies end with."""
    llm = await get_chat_model(
        config, temperature=TEMP_FORMAT, streaming=True, mini=False
    )
    return await llm.ainvoke(
        build_aggregate_messages(system_prompt, query, state, context=combined)
    )
