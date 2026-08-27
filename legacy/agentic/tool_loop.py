"""The tool-calling loop. One implementation, used by every strategy.

WHY THIS FILE EXISTS. There were three copies of this loop — in `react_agent`, in
`dag_execute` and inline in `pe_execute_subquery` — and they had drifted:

    behaviour                react_agent   dag_execute   pe_execute_subquery
    -----------------------  ------------  ------------  -------------------
    blackboard injection     yes           yes           yes
    context guard            yes           yes           yes
    result compression       yes           yes           yes
    dedup of tool+args       yes           NO            NO
    mark read units visited  yes           NO            NO
    total tool-call ceiling  NO            yes           NO
    same-tool ceiling        NO            yes           NO
    timeout                  NO            yes           NO

None of those gaps was a decision. Each copy received the fix that its own incident
demanded and the other two never heard about it, so a sub-agent could loop on the same
search forever precisely where the loop is hardest to watch — inside a parallel fan-out.

The differences that ARE decisions live in `ToolLoopLimits`, where they are named,
per-caller, and visible in one table instead of implied by three bodies of code. That
also serves the thesis this engine belongs to: a paradigm is its control structure, and
a control structure that exists in three drifting copies is not a structure, it is an
accident.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from .blackboard import Blackboard
from .context_guard import ContextGuard
from .utils import emit_ui_event

logger = logging.getLogger(__name__)


@dataclass
class ToolLoopLimits:
    """The knobs each caller sets, and the only place they differ.

    `max_iterations` is the number of LLM turns. `max_total_calls` and
    `max_same_tool_calls` bound a single turn's appetite for tools; `timeout_seconds`
    bounds wall time, which matters when several of these run in parallel and one of
    them can strand the whole wave.
    """

    max_iterations: int
    max_total_calls: int | None = None
    max_same_tool_calls: int | None = None
    timeout_seconds: float | None = None
    # Refuse a call with exactly the arguments of one already made. The model that
    # repeats a search is not being thorough, it is stuck.
    dedup_calls: bool = True
    # Tools whose results count as having READ a unit (as opposed to having seen a
    # summary or a highlight of it).
    read_tools: tuple[str, ...] = ("read_fragment",)
    # UI progress per tool call. Off for fan-out sub-agents: four agents narrating
    # thirty calls each is noise, not progress.
    emit_progress: bool = True


@dataclass
class ToolLoopResult:
    """What the loop produced, and how it ended.

    `stopped_by` is recorded rather than inferred: an answer that came back because the
    agent finished and one that came back because it ran out of iterations are not the
    same answer, and every caller used to treat them identically.
    """

    response: AIMessage | None
    iterations: int = 0
    tool_calls: int = 0
    stopped_by: str = "completed"
    errors: list[str] = field(default_factory=list)

    @property
    def answer(self) -> str:
        return str(self.response.content) if self.response else ""

    @property
    def exhausted(self) -> bool:
        """True when the loop hit a ceiling rather than finishing on its own."""
        return self.stopped_by != "completed"


def _args_summary(args: dict) -> str:
    return ", ".join(f"{k}={str(v)[:80]}" for k, v in sorted(args.items()))


def _extract_entity_ids(raw_result: str) -> set[str]:
    """Every entity_id mentioned anywhere in a tool result."""
    ids: set[str] = set()
    try:
        data = json.loads(raw_result)
    except (json.JSONDecodeError, TypeError):
        return ids
    _collect_ids(ids, data)
    return ids


def _collect_ids(ids: set[str], obj: object) -> None:
    if isinstance(obj, dict):
        for key in ("entity_id", "source_entity_uid", "source_file_id"):
            val = obj.get(key)
            if isinstance(val, str) and len(val) > 8:
                ids.add(val)
        for v in obj.values():
            _collect_ids(ids, v)
    elif isinstance(obj, list):
        for item in obj:
            _collect_ids(ids, item)


async def run_tool_loop(
    llm_with_tools: BaseChatModel,
    tools: list[BaseTool],
    messages: list[BaseMessage],
    *,
    extract_fn: Callable,
    limits: ToolLoopLimits,
    config: RunnableConfig | None = None,
    board: Blackboard | None = None,
    guard: ContextGuard | None = None,
    query: str = "",
    scratchpad: dict[str, str] | None = None,
    label: str = "agent",
) -> ToolLoopResult:
    """Run the ReAct loop: inject the board, guard the context, call tools, compress.

    `messages` is mutated in place — the caller keeps the transcript, which the refine
    and synthesis steps read afterwards.
    """
    guard = guard if guard is not None else ContextGuard()
    result = ToolLoopResult(response=None)
    same_tool_count = 0
    last_tool_name = ""

    async def _loop() -> None:
        nonlocal same_tool_count, last_tool_name

        for iteration in range(limits.max_iterations):
            result.iterations = iteration + 1

            if board and board.total_count > 0:
                board.inject_into_messages(messages)

            if guard.needs_eviction(messages):
                await guard.evict(messages, board, config, query=query)

            logger.info(
                "%s: iter=%d | %d messages | %d chars",
                label,
                iteration,
                len(messages),
                sum(len(str(m.content)) for m in messages),
            )

            response = await llm_with_tools.ainvoke(messages)
            result.response = response
            messages.append(response)

            if not response.tool_calls:
                logger.info("%s: iter=%d no tool calls, finishing", label, iteration)
                return

            for tool_call in response.tool_calls:
                name = tool_call["name"]
                args = tool_call.get("args", {}) or {}
                tool_call_id: str = tool_call.get("id") or ""
                summary = _args_summary(args)

                result.tool_calls += 1
                if (
                    limits.max_total_calls is not None
                    and result.tool_calls > limits.max_total_calls
                ):
                    logger.warning(
                        "%s: hit total tool-call ceiling (%d)",
                        label,
                        limits.max_total_calls,
                    )
                    result.stopped_by = "max_total_calls"
                    messages.append(
                        ToolMessage(
                            content="Tool call limit reached. Write your answer now.",
                            tool_call_id=tool_call_id,
                        )
                    )
                    return

                if name == last_tool_name:
                    same_tool_count += 1
                else:
                    same_tool_count = 1
                    last_tool_name = name
                if (
                    limits.max_same_tool_calls is not None
                    and same_tool_count > limits.max_same_tool_calls
                ):
                    logger.warning("%s: hit same-tool ceiling for %s", label, name)
                    result.stopped_by = "max_same_tool_calls"
                    messages.append(
                        ToolMessage(
                            content=(
                                f"You have called {name} too many times in a row. "
                                "Use a different tool or write your answer."
                            ),
                            tool_call_id=tool_call_id,
                        )
                    )
                    continue

                tool_fn = next((t for t in tools if t.name == name), None)
                if not tool_fn:
                    messages.append(
                        ToolMessage(
                            content=f"Error: unknown tool '{name}'",
                            tool_call_id=tool_call_id,
                        )
                    )
                    continue

                if limits.dedup_calls and board and board.was_tool_called(name, summary):
                    messages.append(
                        ToolMessage(
                            content=json.dumps(
                                {
                                    "already_executed": True,
                                    "next_step": (
                                        "This exact call was already made. "
                                        "Try different parameters."
                                    ),
                                }
                            ),
                            tool_call_id=tool_call_id,
                        )
                    )
                    continue
                if board:
                    board.record_tool_call(name, summary)

                if limits.emit_progress:
                    await emit_ui_event(config, f"Calling: {name}({summary})")
                logger.info("%s: iter=%d tool=%s(%s)", label, iteration, name, summary)

                try:
                    raw_result = str(await tool_fn.ainvoke(args))
                except Exception as e:  # noqa: BLE001 — a tool failure is data
                    logger.error("%s: tool %s failed: %s", label, name, e, exc_info=True)
                    result.errors.append(f"{name}: {e}")
                    messages.append(
                        ToolMessage(
                            content=f"Error: tool '{name}' failed: {e}",
                            tool_call_id=tool_call_id,
                        )
                    )
                    continue

                if board and name in limits.read_tools:
                    board.mark_visited(_extract_entity_ids(raw_result))

                if scratchpad is not None:
                    scratchpad[tool_call_id] = raw_result

                extracted = await extract_fn(name, args, raw_result)
                logger.info(
                    "%s: iter=%d %s | %d -> %d chars",
                    label,
                    iteration,
                    name,
                    len(raw_result),
                    len(extracted),
                )
                messages.append(
                    ToolMessage(content=extracted, tool_call_id=tool_call_id)
                )

        result.stopped_by = "max_iterations"

    if limits.timeout_seconds is None:
        await _loop()
    else:
        try:
            await asyncio.wait_for(_loop(), timeout=limits.timeout_seconds)
        except asyncio.TimeoutError:
            result.stopped_by = "timeout"
            logger.warning(
                "%s: timed out after %ss (%d iterations, %d tool calls)",
                label,
                limits.timeout_seconds,
                result.iterations,
                result.tool_calls,
            )

    return result
