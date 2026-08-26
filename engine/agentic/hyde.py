"""HyDE — Hypothetical Document Embeddings.

Generates synthetic answers to the user's query in each document language.
These hypothetical answers are used as KNN queries in prefetch, bridging
the semantic gap between the query ("addresses of Valerio Simoni") and
the actual document content ("Via Carlo Farini 58, piano 4, Milano").

Runs after understand (which detects document_languages) and before prefetch.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from .config import get_chat_model
from .state import OrchestratorState
from .utils import emit_ui_event

logger = logging.getLogger(__name__)

HYDE_PROMPT = (
    "The user asked a question about documents. "
    "For EACH language listed below, generate exactly ONE short paragraph showing "
    "what the ANSWER would look like as printed in a document in that language.\n"
    "Include: the entity name, the specific value, and the role/context. "
    "Use realistic but fictitious values in each language's format.\n"
    "Separate each language block with a blank line. "
    "Output ONLY the paragraphs, no explanation. ONE per language.\n\n"
    "Languages: {languages}"
)


async def generate_hyde(
    state: OrchestratorState, config: RunnableConfig | None = None
) -> dict:
    """Generate hypothetical document embeddings and run KNN with them."""
    if state.get("complexity") != "complex":
        return {"hyde_queries": []}

    query = state.get("rewritten_query") or state.get("query", "")
    languages = state.get("document_languages", [])

    if not query or not languages:
        return {"hyde_queries": []}

    seen = set()
    unique_langs = []
    for lang in languages:
        key = lang.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique_langs.append(lang)
    unique_langs = unique_langs[:3]

    llm = await get_chat_model(config, temperature=0.7, mini=True)

    try:
        resp = await llm.ainvoke(
            [
                SystemMessage(
                    content=HYDE_PROMPT.format(languages=", ".join(unique_langs))
                ),
                HumanMessage(content=query),
            ]
        )
        raw = str(resp.content).strip()
    except Exception as e:
        # HyDE is an optional optimization — failures should not crash the
        # pipeline. Log and continue without hypothetical queries.
        logger.warning("hyde: LLM call failed, continuing without HyDE: %s", e)
        return {"hyde_queries": []}

    # Split by blank lines — each block is one language's hypothetical
    hypotheticals = [
        block.strip()
        for block in raw.split("\n\n")
        if block.strip() and len(block.strip()) > 20
    ]

    for h in hypotheticals:
        logger.info("hyde: %s", h[:100])
        await emit_ui_event(config, f"HyDE: {h[:80]}")

    logger.info("hyde: %d hypothetical answers from 1 LLM call", len(hypotheticals))
    return {"hyde_queries": hypotheticals}
