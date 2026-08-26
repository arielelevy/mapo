"""Context guard — growth-based eviction with CRAG-style finding extraction.

Monitors context growth between iterations. When context grows by more than
GROWTH_GAP_THRESHOLD (20K chars) in a single iteration, evicts the oldest
large ToolMessage and replaces it with a query-focused finding.

Evicts ONE message at a time. The finding extraction LLM call focuses
exclusively on facts relevant to the user's query — irrelevant details
(IDs, codes, emails) are discarded unless the query asks for them.

Never touches: system prompt, initial human message, blackboard messages,
or the most recent N messages.
"""

import logging

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from .blackboard import Blackboard

logger = logging.getLogger(__name__)

GROWTH_GAP_THRESHOLD = 20_000
KEEP_RECENT_MESSAGES = 6


class ContextGuard:
    """Monitors message context size and evicts old tool results when needed.

    Triggers eviction when context grows by more than GROWTH_GAP_THRESHOLD
    since the last check. This adapts naturally: big tool results (read_fragment
    returning 27K) trigger eviction, small ones (investigate returning 300ch) don't.
    """

    def __init__(
        self,
        growth_threshold: int = GROWTH_GAP_THRESHOLD,
        keep_recent: int = KEEP_RECENT_MESSAGES,
    ) -> None:
        self.growth_threshold = growth_threshold
        self.keep_recent = keep_recent
        self._last_size: int = 0

    def estimate_chars(self, messages: list[BaseMessage]) -> int:
        return sum(len(str(m.content)) for m in messages)

    def needs_eviction(self, messages: list[BaseMessage]) -> bool:
        # First call: set baseline to current size so we measure GROWTH, not
        # absolute size (otherwise a large initial context evicts immediately).
        # Later calls: peek at growth without updating baseline — baseline is
        # only updated after a successful eviction.
        current = self.estimate_chars(messages)
        if self._last_size == 0:
            self._last_size = current
            return False
        return (current - self._last_size) > self.growth_threshold

    async def evict(
        self,
        messages: list[BaseMessage],
        board: Blackboard | None = None,
        config: RunnableConfig | None = None,
        query: str = "",
    ) -> int:
        """Evict oldest large ToolMessage, replacing with query-relevant finding.

        Evicts ONE message at a time so the LLM sees focused content and
        produces a precise finding. Called repeatedly by the tool loop
        whenever needs_eviction() is True.
        """
        end = max(0, len(messages) - self.keep_recent)

        for i in range(3, end):
            msg = messages[i]
            if not isinstance(msg, ToolMessage):
                continue
            content = str(msg.content)
            if content.startswith("[Finding:") or content == "[Evicted]":
                continue
            if len(content) < 200:
                continue

            # Extract finding from this single message
            finding = await self._extract_finding(content, config, query)

            if finding:
                messages[i] = ToolMessage(
                    content=f"[Finding: {finding}]",
                    tool_call_id=getattr(msg, "tool_call_id", ""),
                )
                if board:
                    board.add_finding(finding)
                    # Clear snippets of fragments in this tool response —
                    # the raw content was evicted, the finding replaces it.
                    for eid in self._extract_entity_ids(content):
                        board.clear_snippet(eid)
            else:
                messages[i] = ToolMessage(
                    content="[Evicted]",
                    tool_call_id=getattr(msg, "tool_call_id", ""),
                )

            # Update _last_size to reflect post-eviction state so next growth
            # calc starts from the correct baseline (otherwise grew can go
            # negative and needs_eviction returns False forever).
            self._last_size = self.estimate_chars(messages)
            logger.info(
                "context_guard: evicted 1 message (%d chars now), finding: %dch",
                self._last_size,
                len(finding),
            )
            return 1

        # Nothing was evictable — reset baseline so needs_eviction doesn't
        # keep firing on the same context size.
        self._last_size = self.estimate_chars(messages)
        return 0

    async def _extract_finding(
        self,
        evicted_text: str,
        config: RunnableConfig | None,
        query: str,
    ) -> str:
        """One LLM call to extract query-relevant findings from evicted content."""
        if not config:
            return ""

        from .config import get_chat_model

        prompt = (
            f"Question: {query}\n\n"
            f"The following document content is being compressed. "
            f"Extract ONLY the facts that help answer the question above.\n\n"
            f"Rules:\n"
            f"- Focus EXCLUSIVELY on information relevant to the question.\n"
            f"- Ignore details unrelated to the question (IDs, codes, dates, "
            f"emails, etc. — unless the question asks for them).\n"
            f"- For each relevant fact, write:\n"
            f"  [specific value] — [role/context] — [source document name]\n"
            f"- Be exhaustive for ON-TOPIC facts. Missing a relevant value = failure.\n"
            f"- Do NOT pad with off-topic data.\n"
            f"- Keep your response under 4000 characters.\n\n"
            f"Content:\n{evicted_text[:70000]}"
        )

        try:
            llm = await get_chat_model(config, temperature=0, mini=True)
            resp = await llm.ainvoke([HumanMessage(content=prompt)])
            return str(resp.content).strip()
        except Exception as e:
            logger.warning("context_guard finding extraction failed: %s", e)
            return ""

    @staticmethod
    def _extract_entity_ids(text: str) -> list[str]:
        """Extract entity_id UUIDs from tool response text."""
        import re

        return re.findall(
            r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", text
        )
