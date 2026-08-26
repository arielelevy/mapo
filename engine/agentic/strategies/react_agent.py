"""ReAct agent strategy — iterative tool-calling with blackboard.

Flow:
  1. Build tools + seed blackboard with context docs
  2. Tool-calling loop: LLM calls tools, blackboard auto-tracks visited docs
  3. After each tool result, evict old tool messages to keep context small
  4. Post-loop nudge if blackboard has unchecked items
  5. Grounding search with the answer to find missed evidence
  6. Final refinement with citations (streaming)

The blackboard (blackboard pattern) is the agent's shared knowledge structure:
  - Auto-seeded: context docs (marked done when tool results touch them)
  - LLM-added: leads discovered via the `investigate` tool
  - Findings: compact summaries attached when tool results are evicted
Rendered and injected before each LLM call so the agent sees what's done
and what remains.
"""

import json
import logging
from typing import Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig

from ..config import (
    TEMP_EXTRACT,
    SCRATCHPAD_THRESHOLD_CHARS,
    SCRATCHPAD_INPUT_CHARS,
    SCRATCHPAD_TARGET_CHARS,
    SCRATCHPAD_MARGIN_CHARS,
    GROUNDING_CONTEXT_CHARS,
    get_ai_client,
    get_chat_model,
    get_request_model,
)
from ..agent_config import (
    AGENT_CONFIGS,
    REACT_OUTPUT_FORMAT,
    SCRATCHPAD_EXTRACT_PROMPT,
)
from ..blackboard import Blackboard
from ..context_guard import ContextGuard
from ..tools.agent_tools import build_agent_tools
from ..tools.retrieval import semantic_retrieval
from ..utils import scratchpad_compress, emit_ui_event
from ..state import OrchestratorState, get_scoped_doc_ids

logger = logging.getLogger(__name__)


AGENT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "{system_prompt}"),
        MessagesPlaceholder("history", optional=True),
        (
            "human",
            "## Pre-fetched retrieval results\n{prefetch}\n\n" + "## Question\n{query}",
        ),
    ]
)


# ── Tool loop ─────────────────────────────────────────────────────────────────


def _extract_entity_ids(raw_result: str) -> set[str]:
    """Extract entity_ids from tool result JSON."""
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


async def _run_tool_loop(
    llm_with_tools: BaseChatModel,
    tools: list[BaseTool],
    messages: list[BaseMessage],
    scratchpad: dict[str, str],
    extract_fn: Callable,
    max_iter: int,
    config: RunnableConfig | None = None,
    tracker: Blackboard | None = None,
    query: str = "",
) -> AIMessage | None:
    """Execute the ReAct tool-calling loop with blackboard + context guard."""
    guard = ContextGuard()
    response = None
    for _iteration in range(max_iter):
        # Inject tracker state before each LLM call
        if tracker and tracker.total_count > 0:
            tracker.inject_into_messages(messages)

        # Context guard: evict old tool results if context is too large
        if guard.needs_eviction(messages):
            await guard.evict(messages, tracker, config, query=query)

        # Log context size before LLM call
        total_chars = sum(len(str(m.content)) for m in messages)
        logger.info(
            "llm_invoke iter=%d | %d messages | %d chars",
            _iteration,
            len(messages),
            total_chars,
        )

        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        for tool_call in response.tool_calls:
            tool_fn = next((t for t in tools if t.name == tool_call["name"]), None)
            tool_call_id: str = tool_call.get("id") or ""
            if not tool_fn:
                messages.append(
                    ToolMessage(
                        content=f"Error: unknown tool '{tool_call['name']}'",
                        tool_call_id=tool_call_id,
                    )
                )
                continue

            args_summary = ", ".join(
                f"{k}={str(v)[:80]}" for k, v in sorted(tool_call["args"].items())
            )

            # Dedup: skip if exact same tool+args already executed
            if tracker and tracker.was_tool_called(tool_call["name"], args_summary):
                messages.append(
                    ToolMessage(
                        content='{"already_executed": true, "next_step": "This exact call was already made. Try different parameters."}',
                        tool_call_id=tool_call_id,
                    )
                )
                continue

            if tracker:
                tracker.record_tool_call(tool_call["name"], args_summary)

            await emit_ui_event(
                config,
                f"Calling: {tool_call['name']}({args_summary})",
            )

            logger.info(
                "tool_call iter=%d | %s(%s)",
                _iteration,
                tool_call["name"],
                args_summary,
            )

            try:
                raw_result = str(await tool_fn.ainvoke(tool_call["args"]))
            except Exception as e:
                logger.error("tool %s failed: %s", tool_call["name"], e, exc_info=True)
                messages.append(
                    ToolMessage(
                        content=f"Error: tool '{tool_call['name']}' failed: {e}",
                        tool_call_id=tool_call_id,
                    )
                )
                continue

            # Log tool result details
            result_len = len(raw_result)
            result_preview = raw_result[:500].replace("\n", " ")
            num_results = 0
            if '"results"' in raw_result[:200]:
                num_results = raw_result.count('"entity_id"')
            logger.info(
                "tool_result iter=%d | %s | %d chars | %d entities | %s",
                _iteration,
                tool_call["name"],
                result_len,
                num_results,
                result_preview,
            )

            # Auto-mark blackboard items visited ONLY for read operations
            # (not for search results — highlights/summaries are not "reading")
            if tracker and tool_call["name"] == "read_fragment":
                touched_ids = _extract_entity_ids(raw_result)
                tracker.mark_visited(touched_ids)

            scratchpad[tool_call_id] = raw_result
            extracted = await extract_fn(
                tool_call["name"], tool_call["args"], raw_result
            )
            logger.info(
                "tool_extracted iter=%d | %s | %d->%d chars",
                _iteration,
                tool_call["name"],
                result_len,
                len(extracted),
            )
            messages.append(ToolMessage(content=extracted, tool_call_id=tool_call_id))

    return response


# ── Grounding search ─────────────────────────────────────────────────────────


async def _grounding_search(
    response: AIMessage | None,
    ctx_docs: list[str],
    ws: str,
    config: RunnableConfig | None,
    scratchpad: dict[str, str],
) -> str:
    """Search with the answer to find supporting/contradicting evidence."""
    answer_text = str(response.content or "") if response else ""
    if not answer_text or len(answer_text) <= 30:
        return ""
    try:
        ground_data = await semantic_retrieval(
            answer_text[:500], None, ctx_docs or None, ws, config
        )
    except Exception as e:
        logger.warning("react_agent: grounding search failed: %s", e)
        return ""
    ground_results = ground_data.get("results", [])
    if not ground_results:
        return ""
    grounding_context = "\n\n".join(
        f"[{r.get('document', '')}] {r.get('text', '')[:800]}"
        for r in ground_results[:5]
    )
    scratchpad["_grounding"] = grounding_context
    logger.info("react_agent: grounding search found %d results", len(ground_results))
    return grounding_context


# ── Main strategy ─────────────────────────────────────────────────────────────


async def react_agent(
    state: OrchestratorState, config: RunnableConfig | None = None
) -> dict:
    """ReAct agent with investigation tracker and scratchpad."""
    agent_config = AGENT_CONFIGS.get("react_agent", AGENT_CONFIGS["react_agent"])
    llm = await get_chat_model(config, None, 0)

    ws = state.get("workspace_id", "")
    suite = state.get("suite", "")
    ctx_docs = get_scoped_doc_ids(state)
    key_terms = state.get("key_terms", [])

    # Exhaustive mode: when the query demands a COMPLETE list/count.
    # Activates: seed=20, 2x iterations, context guard, chunked summarize.
    is_exhaustive = (
        state.get("strategy") == "react_agent_exhaustive"
        or state.get("complexity") == "complex"
    )
    logger.info(
        "react_agent: is_exhaustive=%s (strategy=%s, complexity=%s)",
        is_exhaustive,
        state.get("strategy"),
        state.get("complexity"),
    )

    # Build blackboard: seed from prefetch results.
    # Exhaustive: seed top 20 fragments. Normal: seed top 5.
    board = Blackboard()
    prefetch_data = state.get("prefetch_results", {})
    if prefetch_data:
        seed_count = 20 if is_exhaustive else 10
        board.seed_prefetch(prefetch_data, max_items=seed_count)

    # Exhaustive mode: blackboard seeded by prefetch (top 20 fragments by score)

    tools = await build_agent_tools(
        ws,
        suite,
        ctx_docs or None,
        key_terms=key_terms,
        config=config,
        investigation_queue=board if board.total_count > 0 else None,
    )

    llm_with_tools = llm.bind_tools(tools)

    history = list(state.get("messages", []))

    # Retry context (from verify_answer)
    previous_answer = state.get("answer", "")
    unsupported = state.get("unsupported_claims", [])
    retry_context = ""
    if previous_answer and unsupported:
        retry_context = (
            "\n\n## RETRY — Previous answer had issues\n"
            + f"Previous answer:\n{previous_answer[:2000]}\n\n"
            + "Unsupported claims (fix or remove these):\n"
            + "\n".join(f"- {c}" for c in unsupported)
            + "\n\nSearch again for evidence or remove unsupported claims."
        )

    query_with_retry = state["query"] + retry_context

    # Build system prompt with blackboard instruction
    blackboard_instruction = ""
    if board.total_count > 0:
        if is_exhaustive:
            blackboard_instruction = (
                "\n\n## EXHAUSTIVE EXTRACTION MODE\n"
                "The user demands a COMPLETE list. Missing items = WRONG answer.\n"
                "REQUIREMENTS:\n"
                "1. The blackboard has one item per document in scope. "
                "You MUST visit EVERY document (read fragments) before writing your answer.\n"
                "2. Use `investigate` to note items found in each document.\n"
                "3. Do NOT stop at the first match — keep searching across all docs.\n"
                "4. Do NOT write your answer until the blackboard shows >80% items checked.\n"
                "5. Use multiple search strategies: keyword + semantic + entity-based.\n"
            )
        else:
            blackboard_instruction = (
                "\n\nYou have a blackboard tracking your investigation. "
                "Use `investigate` to note important discoveries or flag leads "
                "for later — but prioritize searching and reading over note-taking. "
                "If you already have a complete answer, you may stop. "
                "But if the question asks for exhaustive results (all, every, list, extract), "
                "check all blackboard items before answering."
            )

    # Depth guidance based on domain + complexity
    domain = state.get("document_domain", "general")
    complexity = state.get("complexity", "moderate")
    if domain == "legal":
        complexity = "complex"  # legal is always complex
    depth_instruction = ""
    if complexity == "complex":
        depth_instruction = (
            "\n\nCOMPLEX QUERY: Read at least 5 different fragments before answering. "
            "Search for exact values, specific terms, and precise language. "
            "Do not generalize — cite exact wording from the documents."
        )
    elif complexity == "moderate":
        depth_instruction = (
            "\n\nRead at least 2 fragments to verify before answering. "
            "Do not answer from pre-fetched results alone."
        )

    # Slim prefetch: only metadata for context, no full text (saves ~35K chars)
    if prefetch_data and prefetch_data.get("results"):
        slim_results = []
        for r in prefetch_data["results"]:
            slim = {
                "entity_id": r.get("entity_id", ""),
                "document": r.get("document", ""),
                "score": r.get("score", 0),
            }
            if r.get("source_file_id"):
                slim["source_file_id"] = r["source_file_id"]
            if r.get("page") is not None:
                slim["page"] = r["page"]
            if r.get("total_pages") is not None:
                slim["total_pages"] = r["total_pages"]
            # Include a brief text hint (first 150 chars only)
            text = r.get("text", "")
            if text:
                slim["hint"] = text[:150]
            slim_results.append(slim)
        prefetch = json.dumps(
            {
                "query": prefetch_data.get("query", ""),
                "total_results": prefetch_data.get("total_results", 0),
                "results": slim_results,
            }
        )
    else:
        prefetch = "(no pre-fetched results)"

    # HyDE: additional search queries from hypothetical document answers
    hyde_instruction = ""
    hyde_queries = state.get("hyde_queries", [])
    if hyde_queries:
        hyde_lines = "\n".join(f"- {hq}" for hq in hyde_queries)
        hyde_instruction = (
            "\n\nADDITIONAL SEARCH QUERIES — use these with semantic_search"
            " in addition to your own queries:\n"
        ) + hyde_lines

    initial_messages = AGENT_PROMPT.format_messages(
        system_prompt=agent_config.system_prompt
        + "\n\n"
        + REACT_OUTPUT_FORMAT.format(
            query_language=state.get("query_language", "English")
        )
        + blackboard_instruction
        + depth_instruction
        + hyde_instruction,
        history=history,
        prefetch=prefetch,
        query=query_with_retry,
    )

    messages = list(initial_messages)

    # Scratchpad for context compression
    extract_llm = await get_chat_model(config, temperature=TEMP_EXTRACT)
    scratchpad: dict[str, str] = {}

    async def _extract_relevant(
        tool_name: str, tool_args: dict, raw_result: str
    ) -> str:
        return await scratchpad_compress(
            extract_llm,
            state["query"],
            tool_name,
            raw_result,
            SCRATCHPAD_THRESHOLD_CHARS,
            SCRATCHPAD_INPUT_CHARS,
            SCRATCHPAD_TARGET_CHARS,
            SCRATCHPAD_MARGIN_CHARS,
            SCRATCHPAD_EXTRACT_PROMPT,
        )

    # Main agent loop — exhaustive mode gets more iterations to scan all docs
    max_iterations = agent_config.max_iterations
    if is_exhaustive:
        max_iterations = max_iterations * 2
    response = await _run_tool_loop(
        llm_with_tools,
        tools,
        messages,
        scratchpad,
        _extract_relevant,
        max_iterations,
        config,
        board,
        query=state["query"],
    )

    # Post-loop nudge: in exhaustive mode, nudge even if has_answer
    # (force more searching when items remain), otherwise only if no answer.
    has_answer = response and response.content and len(str(response.content)) > 50
    pending = board.pending_items()
    nudge_threshold = 50 if is_exhaustive else 15
    should_nudge = (
        pending
        and len(pending) <= nudge_threshold
        and (not has_answer or is_exhaustive)
    )
    if should_nudge:
        logger.info(
            "react_agent: blackboard %d/%d done — nudging for %d pending",
            board.done_count,
            board.total_count,
            len(pending),
        )
        await emit_ui_event(
            config,
            f"Checking {len(pending)} remaining investigation items",
        )
        nudge_lines = [f"- {item.label}" for item in pending]
        nudge = (
            f"Your investigation tracker still has {len(pending)} unchecked items:\n"
            + "\n".join(nudge_lines)
            + "\n\nSearch for information about these items before writing your answer."
        )
        messages.append(
            HumanMessage(
                content=f"<system-instruction>\n{nudge}\n</system-instruction>"
            )
        )
        response = await _run_tool_loop(
            llm_with_tools,
            tools,
            messages,
            scratchpad,
            _extract_relevant,
            min(len(pending) + 2, 5),
            config,
            board,
            query=state["query"],
        )

    logger.info(
        "react_agent: blackboard %d/%d fragments done, %d docs covered",
        board.done_count,
        board.total_count,
        board.docs_covered,
    )

    # Grounding search
    grounding_context = await _grounding_search(
        response, ctx_docs, ws, config, scratchpad
    )

    # Final refinement with citations — use GPT-5 for exhaustive to extract all findings
    refine_model = None
    refine_llm = await get_chat_model(config, refine_model, 0, streaming=True)
    agent_answer = str(response.content) if response else ""
    if is_exhaustive:
        refine_msg = (
            "IMPROVE the initial answer by finding items it MISSED in the raw data.\n"
            "Rules:\n"
            "- Keep everything from the initial answer.\n"
            "- Scan the ENTIRE raw data for additional items.\n"
            "- Deduplicate: same value from multiple docs → list ONCE, cite all sources.\n"
            "- Each item: [document](entity:entity_id/entity_type).\n"
            "- Missing even one = WRONG.\n"
            f"- Answer in {state.get('query_language', 'English')}."
        )
        if grounding_context:
            refine_msg += f"\n\n## Additional evidence\n{grounding_context[:GROUNDING_CONTEXT_CHARS]}"
    elif grounding_context:
        refine_msg = (
            "Additional evidence found. Improve your answer with this evidence — "
            "keep your existing [document](entity:id/type) citations and add new ones.\n\n"
            f"## Additional evidence\n{grounding_context[:GROUNDING_CONTEXT_CHARS]}"
        )
    else:
        refine_msg = (
            "Rewrite your answer with EXACT citations. For EVERY fact, look at the "
            "tool results above, find the entity_id and entity_type, and write: "
            "[document_name](entity:entity_id/entity_type). "
            "NEVER write 'documento' or 'document' without the entity link."
        )
    if is_exhaustive:
        # Refine: clean LLM call with tool results as plain text context
        # Tool results + short AI notes (investigate findings).
        # Exclude long AI answers (>500ch) to prevent the LLM from
        # copying its own partial response instead of re-extracting.
        context_parts = []
        for m in messages:
            content = str(m.content)
            if (
                isinstance(m, ToolMessage)
                and len(content) > 200
                and "already" not in content[:50]
            ):
                context_parts.append(content)
            elif (
                isinstance(m, AIMessage)
                and 50 < len(content) < 500
                and not m.tool_calls
            ):
                context_parts.append(content)
        context = "\n---\n".join(context_parts)

        # Adaptive context limit: use 60% of model's context window.
        # ~4 chars per token. Remaining 40% for prompt + initial answer + output.
        try:
            ai_client = get_ai_client(config)
            model_name = get_request_model(config)
            max_tokens = await ai_client.get_max_context_window(model_name)
            max_context_chars = int(max_tokens * 4 * 0.6)
        except Exception:
            max_context_chars = 70_000  # safe default
        max_context_chars = min(max_context_chars, 70_000)  # hard cap

        if len(context) > max_context_chars and context_parts:
            # Summarize each part to fit within budget
            summarize_llm = await get_chat_model(config, temperature=0)
            max_per_part = max_context_chars // len(context_parts)
            summarized_parts = []
            for part in context_parts:
                if len(part) <= max_per_part:
                    summarized_parts.append(part)
                    continue
                summary_resp = await summarize_llm.ainvoke(
                    [
                        HumanMessage(
                            content=(
                                f"Question: {state['query']}\n\n"
                                "Extract ALL specific data from this document: names, addresses, "
                                "locations, values, dates, amounts, roles, relationships.\n"
                                "For each item, include its meaning in context "
                                "(e.g. 'Via Montello 6 — property being purchased — Proposta acquisto').\n"
                                "Preserve entity_ids and source document names exactly.\n"
                                f"Keep under {max_per_part} characters.\n\n"
                                f"Data:\n{part}"
                            )
                        ),
                    ]
                )
                summarized_parts.append(str(summary_resp.content).strip())
            context = "\n---\n".join(summarized_parts)
            logger.info(
                "react_agent: summarized refine context to %dch (budget %dch, %d parts)",
                len(context),
                max_context_chars,
                len(summarized_parts),
            )

        logger.info(
            "react_agent: refine context %dch from %d parts",
            len(context),
            len(context_parts),
        )

        refine_messages = [
            SystemMessage(content=refine_msg),
            HumanMessage(
                content=(
                    f"## Question\n{state['query']}\n\n"
                    f"## Initial answer\n{agent_answer}\n\n"
                    f"## Raw data\n{context}"
                )
            ),
        ]
        response = await refine_llm.ainvoke(refine_messages)
    else:
        messages.append(
            HumanMessage(
                content=f"<system-instruction>\n{refine_msg}\n</system-instruction>"
            )
        )
        response = await refine_llm.ainvoke(messages)

    # Collect tool context for faithfulness verification
    prefetch_str = json.dumps(prefetch_data)[:4000] if prefetch_data else ""
    tool_context_parts = [prefetch_str] if prefetch_str else []
    for _tid, raw in scratchpad.items():
        tool_context_parts.append(raw[:4000])
    tool_context = "\n---\n".join(tool_context_parts)[:20000]

    return {
        "answer": response.content if response else "No answer generated.",
        "tool_context": tool_context,
    }
