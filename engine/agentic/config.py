"""Centralized AI configuration for the AgenticIntel pipeline.

All knobs (models, thresholds, token budgets, limits) are constants.
If any need to be configurable, expose them via helm values and settings_definitions.py.
"""

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.api.v1.ai.ai_client import get_model_info

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AI Client — passed via RunnableConfig["configurable"]["ai_client"]
# ---------------------------------------------------------------------------

AI_CLIENT_KEY = "ai_client"
MODEL_NAME_KEY = "model_name"


def get_ai_client(config: RunnableConfig | None) -> Any:
    """Extract the AI client from LangGraph RunnableConfig."""
    if config is None:
        raise RuntimeError(
            "ai_client requires a RunnableConfig — pass it when invoking the graph"
        )
    configurable = config.get("configurable") or {}
    client = configurable.get(AI_CLIENT_KEY)
    if client is None:
        raise RuntimeError("ai_client not found in config['configurable']")
    return client


def get_request_model(config: RunnableConfig | None) -> str:
    """Get model name from RunnableConfig (injected from the user's request).

    ChatService always sets model_name on the request before invoking
    the graph, so this should never fail in normal operation.
    """
    if config is not None:
        configurable = config.get("configurable") or {}
        model = configurable.get(MODEL_NAME_KEY)
        if model:
            return model
    raise RuntimeError(
        "model_name not found in config — ChatService should always set it on the request"
    )


def get_mini_model_name(config: RunnableConfig | None) -> str:
    """Get the mini sibling of the request model, falling back to the request model itself.

    Used for lightweight tasks (classification, planning, formatting) where a
    smaller model is sufficient.  If the selected model has no mini_model
    declared in MODEL_INFO the request model is returned unchanged.
    """
    model_name = get_request_model(config)
    info = get_model_info(model_name)
    return info.get("mini_model", model_name)


async def get_chat_model(
    config: RunnableConfig | None,
    model_name: str | None = None,
    temperature: float = 0.0,
    streaming: bool = False,
    max_tokens: int | None = None,
    mini: bool = False,
) -> Any:
    """Get a chat model via AIClient from RunnableConfig.

    When mini=True, resolves the mini sibling model name and merges any
    mini specific overrides declared in MODEL_INFO["mini_model_kwargs"].

    When model_name is None (and mini=False), uses the request model.
    """
    extra_kwargs: dict[str, Any] = {}
    if mini:
        request_model = get_request_model(config)
        info = get_model_info(request_model)
        model_name = info.get("mini_model", request_model)
        extra_kwargs = dict(info.get("mini_model_kwargs", {}))
    elif model_name is None:
        model_name = get_request_model(config)
    client = get_ai_client(config)
    kwargs: dict[str, Any] = {
        "model_name": model_name,
        "streaming": streaming,
        "temperature": temperature,
        "include_response_headers": False,
        **extra_kwargs,
    }
    if max_tokens is not None:
        kwargs["max_length"] = max_tokens
    return await client.get_chat_agent(**kwargs)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

MAX_STRATEGY_RESULTS = 80  # per branch (FTS/Entity/KNN). RRF fuses 3×50=150 → top 20
MAX_ENTITY_CONTENT_CHARS = 3000
MAX_HIT_TEXT_CHARS = 3000
MAX_DOC_TEXT_CHARS = 120000
MAX_RETRIEVAL_CONTEXT_RESULTS = 40  # pre-fetch (discovery): broad context
MAX_RETRIEVAL_TOOL_RESULTS = 20  # tool calls from react_agent / plan_execute
MAX_RETRIEVAL_RESULT_CHARS = 5000
MIN_RETRIEVAL_RESULTS = 3  # Always return at least this many results
SCORE_GAP_MIN_FRACTION = 0.25  # Gap must be >= 25% of max_score to trigger cut
MAX_KNN_K_MULTIPLIER = 3
GROUNDING_CONTEXT_CHARS = (
    20000  # max chars for grounding evidence in react_agent refine
)

# ---------------------------------------------------------------------------
# Map-Reduce
# ---------------------------------------------------------------------------

MAX_CHUNKS_PER_LLM_CALL = 80  # ~4K chars/chunk × 80 ≈ 320K chars ≈ 80K tokens
MAX_MAP_REDUCE_LLM_CALLS = 20  # global budget: total LLM calls across all docs

# ---------------------------------------------------------------------------
# Plan-Execute
# ---------------------------------------------------------------------------

PE_MAX_SUB_QUERIES = 6  # max sub-queries for plan_execute decomposition
PE_CONTEXT_CHARS = 10000  # entity_context + prefetch per sub-agent
PE_SUB_ANSWER_CHARS = 5000  # target answer length per sub-agent
PE_TOOL_CONTEXT_CHARS = 25000  # total tool_context in aggregate

# ---------------------------------------------------------------------------
# Scratchpad compression
# ---------------------------------------------------------------------------

SCRATCHPAD_THRESHOLD_CHARS = 50000  # compress only if tool result exceeds this
SCRATCHPAD_INPUT_CHARS = 80000  # max chars sent to extraction LLM for compression
SCRATCHPAD_TARGET_CHARS = 2000  # what the prompt asks the LLM to produce
SCRATCHPAD_MARGIN_CHARS = 1000  # tolerance above target before hard truncation

# ---------------------------------------------------------------------------
# Agent iterations (tool-calling loops)
# ---------------------------------------------------------------------------

MAX_AGENT_ITERATIONS = 20  # react_agent main loop
PE_SUB_AGENT_ITERATIONS = 3  # plan_execute sub-agents: focused sub-query
PE_CONTEXT_CHAR_LIMIT = 30_000  # ~7.5K tokens — smaller window for sub-agents
PE_KEEP_RECENT_MESSAGES = 4  # sub-agents have fewer iterations

# ---------------------------------------------------------------------------
# DAG strategy (VMAO-inspired) — verify-replan loop with shared blackboard
# ---------------------------------------------------------------------------

DAG_MAX_SUB_QUESTIONS = 4
DAG_MAX_REPLAN_ITERATIONS = 3
DAG_READY_THRESHOLD = 0.8
DAG_DIMINISHING_RETURNS = 0.05
DAG_SUB_AGENT_ITERATIONS = 10
DAG_MAX_SAME_TOOL_CALLS = 10
DAG_MAX_TOTAL_TOOL_CALLS = 30
DAG_AGENT_TIMEOUT = 120
DAG_CONTEXT_CHAR_LIMIT = 30_000
DAG_KEEP_RECENT_MESSAGES = 4
DAG_DEP_CONTEXT_CHARS = 3_000
DAG_MAX_CONCURRENT = 4
DAG_HIERARCHICAL_THRESHOLD = 15_000

# ---------------------------------------------------------------------------
# Temperatures — precision-first for investigative analysis
# ---------------------------------------------------------------------------

TEMP_CLASSIFY = 0.0
TEMP_AGENT = 0.1
TEMP_EXTRACT = 0.0
TEMP_PLAN = 0.1
TEMP_FORMAT = 0.0

# ---------------------------------------------------------------------------
# Cross-Document
# ---------------------------------------------------------------------------

MAX_CROSS_DOC_TERMS = 20
