"""DAG strategy — VMAO-inspired verified multi-agent orchestration.

Flow:
  dag_plan → [dag_wave_router → dag_execute (×N) → dag_post_wave]* → dag_verify
    → dag_synthesize  OR  → dag_replan → [wave loop again]

Based on: VMAO (Zhang et al., ICLR 2026 MALGAI Workshop, arxiv 2603.11445).
Adds shared blackboard for real-time inter-agent coordination.

Best for: exhaustive extraction queries where missing an item = failure.
Examples: "extract ALL people connected to X", "how many victims named Y",
"who are the most contacted individuals".
"""

import asyncio
import logging
from collections import defaultdict

from langchain_core.callbacks import adispatch_custom_event
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Send
from pydantic import BaseModel, Field

from ..blackboard import Blackboard
from ..context_guard import ContextGuard
from ..config import (
    DAG_MAX_SUB_QUESTIONS,
    DAG_MAX_REPLAN_ITERATIONS,
    DAG_READY_THRESHOLD,
    DAG_DIMINISHING_RETURNS,
    DAG_SUB_AGENT_ITERATIONS,
    DAG_MAX_SAME_TOOL_CALLS,
    DAG_MAX_TOTAL_TOOL_CALLS,
    DAG_AGENT_TIMEOUT,
    DAG_CONTEXT_CHAR_LIMIT,
    DAG_KEEP_RECENT_MESSAGES,
    DAG_DEP_CONTEXT_CHARS,
    DAG_MAX_CONCURRENT,
    DAG_HIERARCHICAL_THRESHOLD,
    PE_SUB_ANSWER_CHARS,
    TEMP_PLAN,
    TEMP_AGENT,
    TEMP_EXTRACT,
    TEMP_FORMAT,
    SCRATCHPAD_THRESHOLD_CHARS,
    SCRATCHPAD_INPUT_CHARS,
    SCRATCHPAD_TARGET_CHARS,
    SCRATCHPAD_MARGIN_CHARS,
    get_chat_model,
)
from ..agent_config import (
    DAG_PLANNER_PROMPT,
    DAG_EXECUTE_PROMPT,
    DAG_VERIFY_PROMPT,
    DAG_SYNTHESIZE_PROMPT,
    OUTPUT_FORMAT_PROMPT,
    DOMAIN_INSTRUCTIONS,
    SCRATCHPAD_EXTRACT_PROMPT,
)
from ..utils import build_aggregate_messages, scratchpad_compress
from ..tools.agent_tools import build_agent_tools
from ..state import (
    DagExtraction,
    DagSubQueryState,
    OrchestratorState,
    SubQuestionDict,
    VerificationDict,
    get_scoped_doc_ids,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured output for the planner
# ---------------------------------------------------------------------------


class SubQuestion(BaseModel):
    id: str = Field(description="Unique ID like sq_001, sq_002")
    question: str = Field(description="Specific, answerable question")
    dependencies: list[str] = Field(
        default_factory=list,
        description="IDs of sub-questions that must complete first",
    )
    priority: int = Field(default=5, description="1-10, higher = more important")
    context_from_deps: bool = Field(
        default=False,
        description="Whether to inject dependency results into this agent's prompt",
    )
    verification_criteria: str = Field(
        default="",
        description="What 'complete' means for this sub-question",
    )


class DagPlan(BaseModel):
    sub_questions: list[SubQuestion] = Field(
        description=f"1-{DAG_MAX_SUB_QUESTIONS} sub-questions as a DAG"
    )


class VerificationResult(BaseModel):
    sub_question_id: str
    status: str = "incomplete"  # "complete" | "partial" | "incomplete"
    completeness_score: float = 0.0
    missing_aspects: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    recommendation: str = "retry"  # "accept" | "retry"


class VerificationOutput(BaseModel):
    results: list[VerificationResult]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assign_waves(sub_questions: list[SubQuestionDict]) -> list[SubQuestionDict]:
    """Topological sort and assign wave numbers. Break cycles by priority."""
    by_id = {sq["id"]: sq for sq in sub_questions}
    # Detect and break cycles
    visited: set[str] = set()
    in_stack: set[str] = set()

    def _has_cycle(node_id: str) -> bool:
        if node_id in in_stack:
            return True
        if node_id in visited:
            return False
        visited.add(node_id)
        in_stack.add(node_id)
        for dep in by_id.get(node_id, {}).get("dependencies", []):
            if dep in by_id and _has_cycle(dep):
                # Break cycle: remove this dependency
                by_id[node_id]["dependencies"] = [
                    d for d in by_id[node_id]["dependencies"] if d != dep
                ]
                logger.warning("dag_plan: broke cycle edge %s → %s", node_id, dep)
        in_stack.discard(node_id)
        return False

    # visited persists across calls (memoizes already-processed nodes);
    # only in_stack is per-call to detect cycles within a DFS path.
    for sq_id in list(by_id.keys()):
        in_stack.clear()
        _has_cycle(sq_id)

    # Assign waves via memoized DFS (handles out-of-order dependencies)
    waves: dict[str, int] = {}

    def _wave_for(node_id: str) -> int:
        if node_id in waves:
            return waves[node_id]
        node = by_id.get(node_id)
        if not node:
            return 0
        deps = [d for d in node.get("dependencies", []) if d in by_id]
        waves[node_id] = 0 if not deps else max(_wave_for(d) for d in deps) + 1
        return waves[node_id]

    for sq in sub_questions:
        _wave_for(sq["id"])

    for sq in sub_questions:
        sq["wave"] = waves.get(sq["id"], 0)

    return sub_questions


def _build_sub_state(
    sq: SubQuestionDict,
    state: OrchestratorState,
    extractions: list[DagExtraction],
) -> DagSubQueryState:
    """Build DagSubQueryState for a sub-question, injecting dependency context."""
    dep_context = ""
    if sq.get("context_from_deps") and sq.get("dependencies"):
        results_by_id = {e["id"]: e["result"] for e in extractions}
        dep_parts = []
        for dep_id in sq["dependencies"]:
            if dep_id in results_by_id:
                dep_parts.append(
                    f"### {dep_id}\n{results_by_id[dep_id][:DAG_DEP_CONTEXT_CHARS]}"
                )
        dep_context = "\n\n".join(dep_parts)

    return {
        "sub_question_id": sq["id"],
        "sub_question": sq["question"],
        "verification_criteria": sq.get("verification_criteria", ""),
        "dependency_context": dep_context,
        "workspace_id": state.get("workspace_id", ""),
        "suite": state.get("suite", ""),
        "context_doc_ids": get_scoped_doc_ids(state),
        "entity_context": state.get("entity_context", ""),
        "prefetch_results": state.get("prefetch_results", {}),
        "document_domain": state.get("document_domain", "general"),
        "query_language": state.get("query_language", "English"),
        "history_text": state.get("history_text", ""),
    }


# ---------------------------------------------------------------------------
# Phase 1: Plan — decompose query into DAG of sub-questions
# ---------------------------------------------------------------------------


async def dag_plan(
    state: OrchestratorState, config: RunnableConfig | None = None
) -> dict:
    """Decompose the user's query into a DAG of sub-questions."""
    import re as _re

    llm = await get_chat_model(config, temperature=TEMP_PLAN, mini=True)
    llm = llm.with_structured_output(DagPlan)

    entity_context = state.get("entity_context", "")
    doc_labels = (
        _re.findall(r"--- \[(.+?)\] ---", entity_context) if entity_context else []
    )
    docs_info = (
        "\nAvailable documents:\n" + "\n".join(f"- {lbl}" for lbl in doc_labels)
        if doc_labels
        else ""
    )

    domain = state.get("document_domain", "general")
    domain_hint = ""
    if domain != "general":
        domain_extra = DOMAIN_INSTRUCTIONS.get(domain, "")
        if domain_extra:
            domain_hint = f"\n\nDocument domain: {domain}{domain_extra}"

    result: DagPlan = await llm.ainvoke(  # type: ignore[assignment]
        [
            SystemMessage(
                content=DAG_PLANNER_PROMPT.format(
                    max_sub_questions=DAG_MAX_SUB_QUESTIONS
                )
            ),
            HumanMessage(
                content=f"{docs_info}{domain_hint}\n\nQuery: {state['query']}"
            ),
        ]
    )

    sub_questions: list[SubQuestionDict] = [
        sq.model_dump() for sq in result.sub_questions  # type: ignore[misc]
    ][:DAG_MAX_SUB_QUESTIONS]
    sub_questions = _assign_waves(sub_questions)

    # Cap concurrent per wave
    wave_groups: dict[int, list[SubQuestionDict]] = defaultdict(list)
    for sq in sub_questions:
        wave_groups[sq["wave"]].append(sq)
    for wave_num, group in wave_groups.items():
        if len(group) > DAG_MAX_CONCURRENT:
            for sq in group[DAG_MAX_CONCURRENT:]:
                sq["wave"] = wave_num + 1

    # Create shared blackboard
    board = Blackboard()
    for sq in sub_questions:
        board.add_lead(sq["question"], entity_id=sq["id"])
    if config:
        cfgable = config.get("configurable", {})
        cfgable["dag_blackboard"] = board
        wave_sizes = [len(g) for g in wave_groups.values()]
        max_wave_size = max(wave_sizes) if wave_sizes else 1
        cfgable["dag_char_limit"] = DAG_CONTEXT_CHAR_LIMIT // max(max_wave_size, 1)

    logger.info(
        "dag_plan: %d sub-questions, %d waves, blackboard seeded",
        len(sub_questions),
        len(wave_groups),
    )

    return {
        "dag": {
            "sub_questions": sub_questions,
            "current_wave": 0,
            "iteration": 0,
            "extractions": [],
        }
    }


# ---------------------------------------------------------------------------
# Phase 2: Wave router — conditional edge function
# ---------------------------------------------------------------------------


def dag_plan_router(state: OrchestratorState) -> list[Send] | str:
    """Route after dag_plan: single sub-question → react_agent direct (20 iters, streaming),
    multiple → Send() fan-out."""
    dag = state.get("dag", {})
    sub_questions = dag.get("sub_questions", [])
    if not sub_questions:
        return "dag_verify"
    if len(sub_questions) == 1:
        logger.info("dag_plan_router: single sub-question → dag_execute_single")
        return "dag_execute_single"
    return dag_wave_router(state)


def dag_wave_router(state: OrchestratorState) -> list[Send] | str:
    """Fan out current wave's sub-questions or proceed to verify.

    Skips empty waves: if current_wave has no pending items but a later wave
    does (e.g. overflow from DAG_MAX_CONCURRENT bumping), advance to the next
    wave with pending items instead of jumping straight to verify.
    """
    dag = state.get("dag", {})
    sub_questions = dag.get("sub_questions", [])
    if not sub_questions:
        return "dag_verify"

    current_wave = dag.get("current_wave", 0)
    extractions = dag.get("extractions", [])
    completed_ids = {e["id"] for e in extractions}
    max_wave = max((sq["wave"] for sq in sub_questions), default=0)

    # Scan from current_wave forward for the first wave with ready items.
    for wave in range(current_wave, max_wave + 1):
        ready = [
            sq
            for sq in sub_questions
            if sq["wave"] == wave and sq["id"] not in completed_ids
        ]
        if ready:
            if wave != current_wave:
                logger.info(
                    "dag_wave_router: skipping empty waves %d..%d, running wave %d",
                    current_wave,
                    wave - 1,
                    wave,
                )
            logger.info(
                "dag_wave_router: wave %d, %d sub-questions ready", wave, len(ready)
            )
            return [
                Send("dag_execute", _build_sub_state(sq, state, extractions))
                for sq in ready
            ]

    logger.info("dag_wave_router: all waves done, proceeding to verify")
    return "dag_verify"


# ---------------------------------------------------------------------------
# Phase 3: Execute — mini agent per sub-question
# ---------------------------------------------------------------------------


async def dag_execute(
    state: DagSubQueryState, config: RunnableConfig | None = None
) -> dict:
    """Execute a single sub-question with tools and shared blackboard."""
    llm = await get_chat_model(config, None, TEMP_AGENT)

    ws = state.get("workspace_id", "")
    suite = state.get("suite", "")
    ctx_docs = state.get("context_doc_ids", [])

    # Shared blackboard — fetched BEFORE build_agent_tools so the investigate
    # tool is wired to it and the agent can record findings/leads.
    board: Blackboard | None = (
        config.get("configurable", {}).get("dag_blackboard") if config else None
    )
    tools = await build_agent_tools(
        ws, suite, ctx_docs or None, config=config, investigation_queue=board
    )
    llm_with_tools = llm.bind_tools(tools)

    sq_id = state.get("sub_question_id", "")
    sub_question = state.get("sub_question", "")
    domain = state.get("document_domain", "general")
    query_language = state.get("query_language", "English")

    if config:
        await adispatch_custom_event(
            name="on_ui_event",
            data={
                "channel": "agentic",
                "content": f"Investigating: {sub_question[:100]}",
            },
            config=config,
        )

    # Build system prompt
    domain_extra = DOMAIN_INSTRUCTIONS.get(domain, "")
    system_prompt = DAG_EXECUTE_PROMPT
    if domain_extra:
        system_prompt += domain_extra
    system_prompt += (
        f"\n\nSTRICT LIMIT: answer MUST be under {PE_SUB_ANSWER_CHARS} characters. "
        "Only include facts. No filler."
        "\nCITATIONS: use **bold document names** for every fact."
        f"\nLANGUAGE: answer in {query_language}."
    )

    if board:
        board_state = board.render()
        if board_state:
            system_prompt += (
                "\n\n## Investigation tracker (shared with other agents)\n"
                + board_state
                + "\nFocus on YOUR sub-question. Other agents handle other items."
            )

    # Build messages
    entity_ctx = state.get("entity_context", "")
    dep_ctx = state.get("dependency_context", "")
    context_parts = []
    if dep_ctx:
        context_parts.append(f"## Dependency results\n{dep_ctx}")
    if entity_ctx:
        context_parts.append(entity_ctx[:10000])
    context = "\n\n".join(context_parts)

    messages: list = list(
        build_aggregate_messages(system_prompt, sub_question, state, context=context)
    )

    # Scratchpad compression
    extract_llm = await get_chat_model(config, temperature=TEMP_EXTRACT)

    async def _extract_relevant(tool_name: str, tool_args: dict, raw: str) -> str:
        return await scratchpad_compress(
            extract_llm,
            sub_question,
            tool_name,
            raw,
            SCRATCHPAD_THRESHOLD_CHARS,
            SCRATCHPAD_INPUT_CHARS,
            SCRATCHPAD_TARGET_CHARS,
            SCRATCHPAD_MARGIN_CHARS,
            SCRATCHPAD_EXTRACT_PROMPT,
        )

    # Context guard
    char_limit = (
        config.get("configurable", {}).get("dag_char_limit", DAG_CONTEXT_CHAR_LIMIT)
        if config
        else DAG_CONTEXT_CHAR_LIMIT
    )
    guard = ContextGuard(
        growth_threshold=char_limit, keep_recent=DAG_KEEP_RECENT_MESSAGES
    )

    # Tool-calling loop with safety limits
    response = None
    total_tool_calls = 0
    same_tool_count = 0
    last_tool_name = ""

    async def _run_loop() -> None:
        nonlocal response, total_tool_calls, same_tool_count, last_tool_name

        for iteration in range(DAG_SUB_AGENT_ITERATIONS):
            if board and board.total_count > 0:
                board.inject_into_messages(messages)

            if guard.needs_eviction(messages):
                await guard.evict(messages, board, config, query=sub_question)

            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)

            if not response.tool_calls:
                logger.info(
                    "dag_execute[%s] iter=%d no tool calls, finishing",
                    sq_id,
                    iteration,
                )
                break

            for tool_call in response.tool_calls:
                tool_fn = next((t for t in tools if t.name == tool_call["name"]), None)
                tool_call_id: str = tool_call.get("id") or ""

                # Safety limits
                total_tool_calls += 1
                if total_tool_calls > DAG_MAX_TOTAL_TOOL_CALLS:
                    logger.warning(
                        "dag_execute[%s] hit total tool call limit (%d)",
                        sq_id,
                        DAG_MAX_TOTAL_TOOL_CALLS,
                    )
                    messages.append(
                        ToolMessage(
                            content="Tool call limit reached. Write your answer now.",
                            tool_call_id=tool_call_id,
                        )
                    )
                    return

                if tool_call["name"] == last_tool_name:
                    same_tool_count += 1
                else:
                    same_tool_count = 1
                    last_tool_name = tool_call["name"]

                if same_tool_count > DAG_MAX_SAME_TOOL_CALLS:
                    logger.warning(
                        "dag_execute[%s] hit same-tool limit for %s",
                        sq_id,
                        tool_call["name"],
                    )
                    messages.append(
                        ToolMessage(
                            content=f"You've called {tool_call['name']} too many times. Try a different tool or write your answer.",
                            tool_call_id=tool_call_id,
                        )
                    )
                    continue

                if not tool_fn:
                    messages.append(
                        ToolMessage(
                            content=f"Error: unknown tool '{tool_call['name']}'",
                            tool_call_id=tool_call_id,
                        )
                    )
                    continue

                logger.info(
                    "dag_execute[%s] tool=%s args=%s",
                    sq_id,
                    tool_call["name"],
                    str(tool_call.get("args", {}))[:100],
                )

                try:
                    raw_result = str(await tool_fn.ainvoke(tool_call["args"]))
                except Exception as e:
                    logger.error(
                        "dag_execute: tool %s failed: %s",
                        tool_call["name"],
                        e,
                        exc_info=True,
                    )
                    messages.append(
                        ToolMessage(
                            content=f"Error: tool '{tool_call['name']}' failed: {e}",
                            tool_call_id=tool_call_id,
                        )
                    )
                    continue

                extracted = await _extract_relevant(
                    tool_call["name"], tool_call.get("args", {}), raw_result
                )
                messages.append(
                    ToolMessage(content=extracted, tool_call_id=tool_call_id)
                )

    # Run with timeout
    try:
        await asyncio.wait_for(_run_loop(), timeout=DAG_AGENT_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("dag_execute[%s] timed out after %ds", sq_id, DAG_AGENT_TIMEOUT)

    answer = response.content if response else ""
    if not answer:
        logger.warning(
            "dag_execute[%s] returned EMPTY — tool_calls=%d, iterations used up",
            sq_id,
            total_tool_calls,
        )
    logger.info("dag_execute: '%s' → %d chars", sq_id, len(answer))

    if board:
        board.mark_lead_done(sq_id, answer[:500])
        logger.info(
            "dag_execute[%s] done, blackboard %d/%d",
            sq_id,
            board.done_count,
            board.total_count,
        )

    return {"dag": {"extractions": [{"id": sq_id, "result": answer}]}}


# ---------------------------------------------------------------------------
# Phase 3-alt: Single sub-question — delegate to react_agent (20 iters, streaming)
# ---------------------------------------------------------------------------


async def dag_execute_single(
    state: OrchestratorState, config: RunnableConfig | None = None
) -> dict:
    """Single sub-question: delegate to react_agent (identical code path).

    Regular graph node (not Send), so streaming propagates to client.
    """
    from .react_agent import react_agent

    is_exhaustive = state.get("complexity") == "complex"
    final_strategy = "react_agent_exhaustive" if is_exhaustive else "react_agent"
    logger.info(
        "dag_execute_single: dag reduced to 1 sub-question → %s",
        final_strategy,
    )
    if config:
        label = "Exhaustive search" if is_exhaustive else "Searching and analyzing"
        await adispatch_custom_event(
            name="on_ui_event",
            data={"channel": "agentic", "content": label},
            config=config,
        )
    result = await react_agent(state, config)
    result["strategy"] = final_strategy
    return result


# ---------------------------------------------------------------------------
# Phase 3b: Post-wave — increment wave counter
# ---------------------------------------------------------------------------


async def dag_post_wave(
    state: OrchestratorState, config: RunnableConfig | None = None
) -> dict:
    """Increment wave counter after all sub-agents in a wave complete."""
    current_wave = state.get("dag", {}).get("current_wave", 0)
    logger.info("dag_post_wave: wave %d complete, advancing", current_wave)
    return {"dag": {"current_wave": current_wave + 1}}


# ---------------------------------------------------------------------------
# Phase 4: Verify — evaluate completeness
# ---------------------------------------------------------------------------


async def dag_verify(
    state: OrchestratorState, config: RunnableConfig | None = None
) -> dict:
    """Verify sub-question results for completeness."""
    dag = state.get("dag", {})
    extractions = dag.get("extractions", [])
    sub_questions = dag.get("sub_questions", [])
    results_by_id = {e["id"]: e["result"] for e in extractions}

    # Heuristic pre-check: skip LLM verify if all results look complete
    all_long = all(len(r) > 1500 for r in results_by_id.values())
    if all_long and results_by_id:
        logger.info(
            "dag_verify: heuristic pass — all results > 1500 chars, skipping LLM verify"
        )
        verification: list[VerificationDict] = [
            {
                "sub_question_id": sq["id"],
                "status": "complete",
                "completeness_score": 1.0,
                "missing_aspects": [],
                "contradictions": [],
                "recommendation": "accept",
            }
            for sq in sub_questions
            if sq["id"] in results_by_id
        ]
        return {"dag": {"verification": verification}}

    # LLM verification
    llm = await get_chat_model(config, temperature=0, mini=True)
    llm = llm.with_structured_output(VerificationOutput)

    verify_input = []
    for sq in sub_questions:
        result = results_by_id.get(sq["id"], "(no result)")
        verify_input.append(
            f"### {sq['id']}: {sq['question']}\nCriteria: {sq.get('verification_criteria', 'N/A')}\nResult: {result[:3000]}"
        )

    verify_text = "\n\n".join(verify_input)

    output: VerificationOutput = await llm.ainvoke(  # type: ignore[assignment]
        [
            SystemMessage(content=DAG_VERIFY_PROMPT),
            HumanMessage(content=verify_text),
        ]
    )

    verification: list[VerificationDict] = [
        v.model_dump() for v in output.results  # type: ignore[misc]
    ]
    avg_score = (
        sum(v["completeness_score"] for v in verification) / len(verification)
        if verification
        else 0
    )
    logger.info(
        "dag_verify: avg_score=%.2f, %d/%d accept",
        avg_score,
        sum(1 for v in verification if v["recommendation"] == "accept"),
        len(verification),
    )

    return {"dag": {"verification": verification}}


def dag_verify_router(state: OrchestratorState) -> str:
    """Route after verification: synthesize or replan."""
    dag = state.get("dag", {})
    verification = dag.get("verification", [])
    iteration = dag.get("iteration", 0)

    if not verification:
        return "dag_synthesize"

    all_accept = all(v["recommendation"] == "accept" for v in verification)
    avg_score = (
        sum(v["completeness_score"] for v in verification) / len(verification)
        if verification
        else 0
    )

    if all_accept or avg_score >= DAG_READY_THRESHOLD:
        logger.info(
            "dag_verify_router: all accept or avg >= %.1f, synthesizing",
            DAG_READY_THRESHOLD,
        )
        return "dag_synthesize"

    if iteration >= DAG_MAX_REPLAN_ITERATIONS:
        logger.info(
            "dag_verify_router: max iterations (%d), synthesizing best effort",
            DAG_MAX_REPLAN_ITERATIONS,
        )
        return "dag_synthesize"

    has_retries = any(v["recommendation"] == "retry" for v in verification)
    if has_retries:
        logger.info(
            "dag_verify_router: %d retries needed, replanning",
            sum(1 for v in verification if v["recommendation"] == "retry"),
        )
        return "dag_replan"

    return "dag_synthesize"


# ---------------------------------------------------------------------------
# Phase 5: Replan — create retry sub-questions for gaps
# ---------------------------------------------------------------------------


async def dag_replan(
    state: OrchestratorState, config: RunnableConfig | None = None
) -> dict:
    """Generate retry sub-questions for incomplete results."""
    dag = state.get("dag", {})
    verification = dag.get("verification", [])
    sub_questions = dag.get("sub_questions", [])
    extractions = dag.get("extractions", [])
    iteration = dag.get("iteration", 0)
    results_by_id = {e["id"]: e["result"] for e in extractions}
    sq_by_id = {sq["id"]: sq for sq in sub_questions}

    # Diminishing returns check
    prev_verification = dag.get("prev_verification_avg")
    avg_score = (
        sum(v["completeness_score"] for v in verification) / len(verification)
        if verification
        else 0.0
    )
    if (
        prev_verification is not None
        and avg_score - prev_verification < DAG_DIMINISHING_RETURNS
    ):
        logger.info(
            "dag_replan: diminishing returns (delta=%.3f), stopping",
            avg_score - prev_verification,
        )
        return {
            "dag": {
                "sub_questions": sub_questions,
                "iteration": iteration + 1,
                "prev_verification_avg": avg_score,
            }
        }

    # Build retry sub-questions
    complete_sqs: list[SubQuestionDict] = []
    retry_sqs: list[SubQuestionDict] = []

    board: Blackboard | None = (
        config.get("configurable", {}).get("dag_blackboard") if config else None
    )

    for v in verification:
        sq_id = v["sub_question_id"]
        orig_sq = sq_by_id.get(sq_id)
        if orig_sq is None:
            continue

        if v["recommendation"] == "accept":
            complete_sqs.append(orig_sq)
            continue

        # Create retry sub-question
        retry_id = f"{sq_id}_r{iteration + 1}"
        prior_result = results_by_id.get(sq_id, "")[:1000]
        missing = ", ".join(v.get("missing_aspects", []))

        if v["status"] == "incomplete":
            retry_q = (
                f"{orig_sq.get('question', '')} "
                f"Previous attempt found: {prior_result[:500]}. "
                f"Gaps: {missing}. Search more broadly."
            )
        else:  # partial
            retry_q = (
                f"Fill these gaps for: {orig_sq.get('question', '')} "
                f"Missing: {missing}."
            )

        retry_sqs.append(
            {
                "id": retry_id,
                "question": retry_q,
                "dependencies": [],
                "priority": orig_sq.get("priority", 5),
                "context_from_deps": False,
                "verification_criteria": orig_sq.get("verification_criteria", ""),
                "wave": 0,
            }
        )

        if board:
            board.mark_lead_retry(sq_id)
            board.add_lead(retry_q, entity_id=retry_id)

        # Handle contradictions
        for c_idx, contradiction in enumerate(v.get("contradictions", [])):
            contra_id = f"{sq_id}_c{iteration + 1}_{c_idx}"
            retry_sqs.append(
                {
                    "id": contra_id,
                    "question": f"Resolve contradiction: {contradiction}. Search different sources.",
                    "dependencies": [],
                    "priority": 7,
                    "context_from_deps": False,
                    "verification_criteria": "Must resolve the contradiction with evidence",
                    "wave": 0,
                }
            )
            if board:
                board.add_lead(f"Resolve: {contradiction[:80]}", entity_id=contra_id)

    if not retry_sqs:
        logger.info("dag_replan: no retries needed, proceeding to synthesize")
        return {
            "dag": {
                "sub_questions": sub_questions,
                "iteration": iteration + 1,
                "prev_verification_avg": avg_score,
            }
        }

    logger.info(
        "dag_replan: %d retries + %d complete preserved, iteration %d",
        len(retry_sqs),
        len(complete_sqs),
        iteration + 1,
    )

    if config:
        await adispatch_custom_event(
            name="on_ui_event",
            data={
                "channel": "agentic",
                "content": f"Filling {len(retry_sqs)} gaps (attempt {iteration + 2})",
            },
            config=config,
        )

    return {
        "dag": {
            "sub_questions": complete_sqs + retry_sqs,
            "current_wave": 0,
            "iteration": iteration + 1,
            "prev_verification_avg": avg_score,
        }
    }


# ---------------------------------------------------------------------------
# Phase 6: Synthesize — merge all results into final answer
# ---------------------------------------------------------------------------


async def dag_synthesize(
    state: OrchestratorState, config: RunnableConfig | None = None
) -> dict:
    """Combine all sub-question results into a single coherent answer."""
    dag = state.get("dag", {})
    extractions = dag.get("extractions", [])
    sub_questions = dag.get("sub_questions", [])
    sq_by_id = {sq["id"]: sq for sq in sub_questions}

    sub_results = []
    tool_context_parts = []
    for ext in extractions:
        sq = sq_by_id.get(ext["id"], {})
        label = sq.get("question", ext["id"]) if sq else ext["id"]
        ctx = ext.get("result", "")[: int(PE_SUB_ANSWER_CHARS * 1.2)]
        sub_results.append(f"### {label}\n{ctx}")
        tool_context_parts.append(ctx)

    combined = "\n\n".join(sub_results)
    tool_context = "\n---\n".join(tool_context_parts)[:25000]

    # Hierarchical synthesis for large result sets
    if len(combined) > DAG_HIERARCHICAL_THRESHOLD and len(sub_results) > 4:
        logger.info("dag_synthesize: hierarchical synthesis (%d chars)", len(combined))
        pre_llm = await get_chat_model(config, temperature=TEMP_EXTRACT, mini=True)
        # Pre-summarize in chunks of 3
        summaries = []
        for i in range(0, len(sub_results), 3):
            chunk = "\n\n".join(sub_results[i : i + 3])
            summary = await pre_llm.ainvoke(
                [
                    SystemMessage(
                        content="Summarize these investigation results. Preserve ALL facts, names, dates, citations."
                    ),
                    HumanMessage(content=chunk),
                ]
            )
            summaries.append(summary.content)
        combined = "\n\n".join(summaries)

    # Append blackboard coverage
    board: Blackboard | None = (
        config.get("configurable", {}).get("dag_blackboard") if config else None
    )
    if board and board.total_count > 0:
        combined += "\n\n" + board.render()
        logger.info(
            "dag_synthesize: blackboard %d/%d done",
            board.done_count,
            board.total_count,
        )

    # Final synthesis
    llm = await get_chat_model(
        config, temperature=TEMP_FORMAT, streaming=True, mini=False
    )
    response = await llm.ainvoke(
        build_aggregate_messages(
            DAG_SYNTHESIZE_PROMPT
            + "\n\n"
            + OUTPUT_FORMAT_PROMPT.format(
                query_language=state.get("query_language", "English")
            ),
            state["query"],
            state,
            context=combined,
        )
    )

    logger.info(
        "dag_synthesize: %d sub-results merged, answer=%d chars",
        len(sub_results),
        len(response.content) if response.content else 0,
    )

    return {"answer": response.content, "tool_context": tool_context}
