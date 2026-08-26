"""Utility functions for the AgenticIntel pipeline.

TODO: get_embedding uses OpenAI embeddings API.
Could not find a platform embedding service in the cluster.
Replace when available on-premise.
"""

import logging
import os

from collections.abc import Mapping
from typing import Any, List, Optional

from .state import OrchestratorState

from langchain_core.callbacks import adispatch_custom_event
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")

_openai_client: Optional[AsyncOpenAI] = None


def _get_openai_client() -> AsyncOpenAI:
    """Lazy singleton — reuses client instance across calls."""
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI()
    return _openai_client


def sanitize_text(text: str) -> str:
    """Clean text before sending to LLM context.

    Removes null bytes, invalid UTF-8, and collapses broken OCR output
    (single characters separated by newlines) into readable text.
    """
    text = text.replace("\x00", "").encode("utf-8", errors="replace").decode("utf-8")
    # Collapse broken OCR: lines with 1-2 chars separated by blank lines
    # e.g. "T\n\n  M\n\n  M\n\n  G" → "T M M G"
    lines = text.split("\n")
    if len(lines) > 20:
        short_lines = sum(1 for l in lines if len(l.strip()) <= 2)
        if short_lines > len(lines) * 0.5:
            # More than half are single chars → broken OCR, collapse
            text = " ".join(l.strip() for l in lines if l.strip())
    return text


def build_aggregate_messages(
    system_content: str,
    human_content: str,
    state: OrchestratorState | Mapping[str, Any],
    context: str = "",
) -> list[BaseMessage]:
    """Build message list for aggregate/merge LLM calls with optional multi-turn history.

    Context (retrieved data) goes at the end of SystemMessage.
    HumanMessage contains only the user's question.
    """
    messages: list[BaseMessage] = [SystemMessage(content=system_content)]
    history_text = state.get("history_text", "")
    if history_text:
        messages.append(HumanMessage(content=f"<history>\n{history_text}\n</history>"))
    human = human_content
    if context:
        human = f"<context>\n{context}\n</context>\n\nQuestion: {human_content}"
    messages.append(HumanMessage(content=human))
    return messages


async def scratchpad_compress(
    extract_llm: BaseChatModel,
    query: str,
    tool_name: str,
    raw_result: str,
    threshold_chars: int,
    input_chars: int,
    target_chars: int,
    margin_chars: int,
    extract_prompt: str,
) -> str:
    """Compress a large tool result via LLM extraction.

    Returns the raw result unchanged if it's under threshold_chars.
    Otherwise, sends it to the extract LLM and caps the output.
    """
    if len(raw_result) <= threshold_chars:
        return raw_result

    extract_response = await extract_llm.ainvoke(
        [
            SystemMessage(content=extract_prompt),
            HumanMessage(
                content=(
                    f"## Question\n{query}\n\n"
                    f"## Tool: {tool_name}\n\n"
                    f"## Output ({len(raw_result)} chars)\n{raw_result[:input_chars]}"
                )
            ),
        ]
    )
    extracted = str(extract_response.content)
    cap = target_chars + margin_chars
    if len(extracted) > cap:
        extracted = extracted[:cap]
    logger.info(
        "scratchpad: %s %d → %d chars", tool_name, len(raw_result), len(extracted)
    )
    return extracted


async def emit_ui_event(
    config: RunnableConfig | None,
    message: str,
    tooltip: str | None = None,
) -> None:
    """Dispatch a UI event to the agentic channel."""
    if config is None:
        return
    data: dict[str, Any] = {"channel": "agentic", "content": message}
    if tooltip:
        data["tooltip"] = tooltip
    await adispatch_custom_event(name="on_ui_event", data=data, config=config)


async def get_embedding(text: str) -> List[float]:
    """Get embedding vector for KNN search.

    Uses OpenAI embeddings API. Returns empty list if unavailable,
    causing KNN branch to skip (FTS + Entity branches still work).
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.info("get_embedding: no OPENAI_API_KEY, KNN disabled")
        return []

    try:
        client = _get_openai_client()
        resp = await client.embeddings.create(model=EMBEDDING_MODEL, input=text[:32000])
        if not resp.data:
            logger.error("get_embedding: empty response data")
            return []
        return resp.data[0].embedding
    except Exception as e:
        logger.error("get_embedding: failed: %s", e)
        return []
