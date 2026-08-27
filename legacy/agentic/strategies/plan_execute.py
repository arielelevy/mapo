"""Plan-execute strategy — decompose complex queries into parallel sub-queries.

Flow:
  pe_plan → pe_fan_out → [pe_execute_subquery × N] → pe_aggregate

The planner decomposes the query into 2-10 independent sub-queries. Each runs
as a mini react_agent with tools (retrieval, full_text_search, etc.) in parallel.
The aggregator merges all sub-query results into one coherent answer.

Best for: complex multi-faceted questions, "for each X from Y to Z" patterns,
comparisons, and exhaustive entity extraction ("list all addresses").
"""

import logging

from langchain_core.callbacks import adispatch_custom_event
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Send
from pydantic import BaseModel, Field

from ..blackboard import Blackboard
from ..context_guard import ContextGuard
from ..tool_loop import ToolLoopLimits, run_tool_loop
from ..config import (
    PE_AGENT_TIMEOUT,
    PE_MAX_TOTAL_TOOL_CALLS,
    PE_SUB_AGENT_ITERATIONS,
    PE_CONTEXT_GROWTH_LIMIT,
    PE_KEEP_RECENT_MESSAGES,
    TEMP_PLAN,
    TEMP_AGENT,
    TEMP_EXTRACT,
    PE_MAX_SUB_QUERIES,
    PE_CONTEXT_CHARS,
    SYNTHESIS_TOOL_CONTEXT_CHARS,
    SUB_ANSWER_CHARS,
    SCRATCHPAD_THRESHOLD_CHARS,
    SCRATCHPAD_INPUT_CHARS,
    SCRATCHPAD_TARGET_CHARS,
    SCRATCHPAD_MARGIN_CHARS,
    get_chat_model,
)
from ..agent_config import (
    OUTPUT_FORMAT_PROMPT,
    PLAN_EXECUTE_PLANNER_PROMPT,
    PLAN_EXECUTE_EXECUTE_PROMPT,
    PLAN_EXECUTE_AGGREGATE_PROMPT,
    SCRATCHPAD_EXTRACT_PROMPT,
    DOMAIN_INSTRUCTIONS,
)
from ..utils import build_aggregate_messages, scratchpad_compress
from .planning import planner_context
from .synthesis import (
    append_coverage,
    append_scope_warnings,
    build_sections,
    final_answer,
)
from ..tools.agent_tools import build_agent_tools
from ..state import OrchestratorState, SubQueryState, get_scoped_doc_ids

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured output for the planner
# ---------------------------------------------------------------------------


class PlanResult(BaseModel):
    sub_queries: list[str] = Field(
        description=f"2-{PE_MAX_SUB_QUERIES} independent sub-queries"
    )


# ---------------------------------------------------------------------------
# Phase 1: Plan — decompose query into sub-queries
# ---------------------------------------------------------------------------


async def pe_plan(
    state: OrchestratorState, config: RunnableConfig | None = None
) -> dict:
    """Decompose the user's query into independent sub-queries via LLM.

    Uses structured output (PlanResult) to get a clean list of sub-queries.
    Enriches the prompt with: available documents, domain info, document
    languages, and pre-fetched retrieval results for better planning.
    """
    llm = await get_chat_model(
        config,
        temperature=TEMP_PLAN,
        mini=True,
    )
    llm = llm.with_structured_output(PlanResult)

    # NOTE: prefetch is intentionally NOT passed to the planner — it was
    # causing scope expansion (planner saw unrelated topics and generated
    # sub-queries for them).  Sub-query agents already receive prefetch.
    result: PlanResult = await llm.ainvoke(  # type: ignore[assignment]
        [
            SystemMessage(
                content=PLAN_EXECUTE_PLANNER_PROMPT.format(
                    max_sub_queries=PE_MAX_SUB_QUERIES
                )
            ),
            HumanMessage(
                content=f"{planner_context(state)}\n\nQuery: {state['query']}"
            ),
        ]
    )

    # Cap to configured maximum
    sub_queries = result.sub_queries[:PE_MAX_SUB_QUERIES]
    logger.info("pe_plan: decomposed into %d sub-queries", len(sub_queries))

    # Create shared blackboard seeded with sub-queries as items to cover.
    # Stored in config so all parallel sub-agents share the same instance.
    board = Blackboard()
    for sq in sub_queries:
        board.add_lead(sq)
    if config:
        cfgable = config.get("configurable", {})
        cfgable["pe_blackboard"] = board
        # Divide context budget evenly across sub-agents
        cfgable["pe_growth_limit"] = PE_CONTEXT_GROWTH_LIMIT // max(
            len(sub_queries), 1
        )
    logger.info("pe_plan: blackboard seeded with %d items", board.total_count)

    return {"pe_sub_queries": sub_queries}


# ---------------------------------------------------------------------------
# Phase 2: Fan-out — one Send per sub-query (parallel LangGraph execution)
# ---------------------------------------------------------------------------


def pe_fan_out(state: OrchestratorState) -> list[Send] | str:
    """Fan out: one Send per sub-query for parallel execution."""
    sub_queries = state.get("pe_sub_queries", [])
    if not sub_queries:
        logger.warning("pe_fan_out: no sub-queries — skipping to aggregate")
        return "pe_aggregate"

    # Pass shared context to each sub-query agent
    ws = state.get("workspace_id", "")
    suite = state.get("suite", "")
    ctx_docs = get_scoped_doc_ids(state)
    entity_context = state.get("entity_context", "")
    prefetch = state.get("prefetch_results", {})
    domain = state.get("document_domain", "general")

    query_language = state.get("query_language", "English")
    history_text = state.get("history_text", "")
    ner_entities = state.get("doc_ner_entities", {})
    entity_types_filter = state.get("entity_types_filter", [])
    scope_warnings = state.get("scope_warnings", [])

    return [
        Send(
            "pe_execute_subquery",
            {
                "sub_query": sq,
                "workspace_id": ws,
                "suite": suite,
                "context_doc_ids": ctx_docs,
                "entity_context": entity_context,
                "prefetch_results": prefetch,
                "document_domain": domain,
                "query_language": query_language,
                "history_text": history_text,
                "doc_ner_entities": ner_entities,
                "entity_types_filter": entity_types_filter,
                "scope_warnings": scope_warnings,
                "result": "",
            },
        )
        for sq in sub_queries
    ]


# ---------------------------------------------------------------------------
# Phase 3: Execute — mini react_agent per sub-query with tools
# ---------------------------------------------------------------------------


async def pe_execute_subquery(
    state: SubQueryState, config: RunnableConfig | None = None
) -> dict:
    """Execute a single sub-query using a mini react_agent with tools.

    Same tools as react_agent (retrieval, full_text_search, semantic_search, ...) and
    the same tool loop, capped at PE_SUB_AGENT_ITERATIONS — the docstring used to name
    MAX_AGENT_ITERATIONS (20) while the code used 3.
    """
    llm = await get_chat_model(config, None, TEMP_AGENT)

    # Build scoped tools (same as react_agent)
    ws = state.get("workspace_id", "")
    suite = state.get("suite", "")
    ctx_docs = state.get("context_doc_ids", [])

    # Shared blackboard — fetched BEFORE build_agent_tools so the investigate
    # tool is wired to it and the sub-agent can record findings/leads.
    board: Blackboard | None = (
        config.get("configurable", {}).get("pe_blackboard") if config else None
    )
    all_tools = await build_agent_tools(
        ws,
        suite,
        ctx_docs or None,
        config=config,
        investigation_queue=board,
        ner_entities=state.get("doc_ner_entities", {}),
        entity_types=state.get("entity_types_filter", []),
    )
    llm_with_tools = llm.bind_tools(all_tools)

    sub_query = state.get("sub_query", "")
    domain = state.get("document_domain", "general")

    # Emit progress event to frontend
    if config:
        await adispatch_custom_event(
            name="on_ui_event",
            data={"channel": "agentic", "content": f"Researching: {sub_query[:100]}"},
            config=config,
        )

    # Build system prompt with domain instructions and answer size limit
    domain_extra = DOMAIN_INSTRUCTIONS.get(domain, "")
    query_language = state.get("query_language", "English")
    system_prompt = PLAN_EXECUTE_EXECUTE_PROMPT
    if domain_extra:
        system_prompt += domain_extra
    system_prompt += (
        f"\n\nSTRICT LIMIT: your answer MUST be under {SUB_ANSWER_CHARS} characters. "
        "Only include facts. No introductions, no summaries, no filler. "
        "If you have more data, prioritize the most relevant items."
        "\nCITATIONS: use **bold document names** for every fact."
        f"\nLANGUAGE: You MUST answer in {query_language}, even if documents are in another language."
    )

    if board:
        board_state = board.render()
        if board_state:
            system_prompt += (
                "\n\n## Investigation tracker (shared with other agents)\n"
                + board_state
                + "\nFocus on YOUR sub-query. Other agents handle other items."
            )

    entity_ctx = state.get("entity_context", "")
    context_data = entity_ctx[:PE_CONTEXT_CHARS] if entity_ctx else ""

    messages: list = list(
        build_aggregate_messages(system_prompt, sub_query, state, context=context_data)
    )

    # Scratchpad: compress large tool results (shared with react_agent)
    extract_llm = await get_chat_model(
        config,
        temperature=TEMP_EXTRACT,
    )

    async def _extract_relevant(tool_name: str, tool_args: dict, raw: str) -> str:
        return await scratchpad_compress(
            extract_llm,
            sub_query,
            tool_name,
            raw,
            SCRATCHPAD_THRESHOLD_CHARS,
            SCRATCHPAD_INPUT_CHARS,
            SCRATCHPAD_TARGET_CHARS,
            SCRATCHPAD_MARGIN_CHARS,
            SCRATCHPAD_EXTRACT_PROMPT,
        )

    # Tool-calling loop with scratchpad compression + shared blackboard
    growth_limit = (
        config.get("configurable", {}).get("pe_growth_limit", PE_CONTEXT_GROWTH_LIMIT)
        if config
        else PE_CONTEXT_GROWTH_LIMIT
    )
    guard = ContextGuard(
        growth_threshold=growth_limit, keep_recent=PE_KEEP_RECENT_MESSAGES
    )
    # Same loop as react_agent and dag_execute (agentic/tool_loop.py). Dedup and the
    # tool ceilings arrive here for the first time: this copy had neither, so a
    # sub-agent could repeat one search until its iterations ran out.
    loop_result = await run_tool_loop(
        llm_with_tools,
        all_tools,
        messages,
        extract_fn=_extract_relevant,
        limits=ToolLoopLimits(
            max_iterations=PE_SUB_AGENT_ITERATIONS,
            max_total_calls=PE_MAX_TOTAL_TOOL_CALLS,
            timeout_seconds=PE_AGENT_TIMEOUT,
            emit_progress=False,
        ),
        config=config,
        board=board,
        guard=guard,
        query=sub_query,
        label=f"pe_execute[{sub_query[:30]}]",
    )
    response = loop_result.response

    answer = loop_result.answer
    if loop_result.exhausted:
        answer = (
            f"{answer}\n\n[TRUNCATED: this sub-answer stopped early "
            f"({loop_result.stopped_by}) and may be incomplete.]"
        )
    logger.info("pe_execute: '%s' → %d chars", sub_query[:50], len(answer))

    # Mark this sub-query as done on the shared blackboard
    if board:
        board.mark_lead_done(sub_query, answer[:200])
        logger.info(
            "pe_execute[%s] marked done, blackboard %d/%d",
            sub_query[:30],
            board.done_count,
            board.total_count,
        )

    return {
        "extractions": [
            {
                "name": sub_query,
                "entity_type": "sub_query_result",
                "role": "answer",
                "context": answer,
                "source_document": "",
            }
        ]
    }


# ---------------------------------------------------------------------------
# Phase 4: Aggregate — merge sub-query results into final answer
# ---------------------------------------------------------------------------


async def pe_aggregate(
    state: OrchestratorState, config: RunnableConfig | None = None
) -> dict:
    """Combine sub-query results into a single coherent answer.

    Each sub-query produced an extraction with a context (the agent's answer).
    The aggregator LLM merges all of these, deduplicates entities, and produces
    the final answer with proper citations and formatting.
    """
    extractions = state.get("extractions", [])

    # Collect sub-query results and build tool_context for faithfulness check
    items = [
        (ext["name"], ext.get("context", ""))
        for ext in extractions
        if ext.get("entity_type") == "sub_query_result"
    ]
    combined, tool_context = build_sections(
        items,
        per_item_chars=int(SUB_ANSWER_CHARS * 1.2),
        tool_context_chars=SYNTHESIS_TOOL_CONTEXT_CHARS,
    )
    sub_results = items

    # Coverage, not the operating record (see synthesis.append_coverage).
    board: Blackboard | None = (
        config.get("configurable", {}).get("pe_blackboard") if config else None
    )
    combined = append_coverage(combined, board)
    combined = append_scope_warnings(combined, state)

    response = await final_answer(
        PLAN_EXECUTE_AGGREGATE_PROMPT
        + "\n\n"
        + OUTPUT_FORMAT_PROMPT.format(
            query_language=state.get("query_language", "English")
        ),
        state["query"],
        state,
        combined,
        config,
    )

    logger.info(
        "pe_aggregate: %d sub-results merged, answer=%d chars",
        len(sub_results),
        len(response.content) if response.content else 0,
    )
    return {"answer": response.content, "tool_context": tool_context}
