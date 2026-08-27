"""Blackboard — shared knowledge structure for the agent's investigation.

Accumulates what was checked, what was found, and what remains. Rendered
as text and injected into the LLM context, replacing raw tool results
that get evicted to keep the context window small.

Two sources of items:
  - Auto-seeded from prefetch: fragments, entities, or docs found by initial retrieval
  - LLM-added: leads discovered via the `investigate` tool

Findings are attached when tool results are evicted — the blackboard accumulates
a compact summary of what the agent discovered.
"""

import json
from dataclasses import dataclass, field


@dataclass
class BlackboardItem:
    label: str
    source: str  # "prefetch", "lead" or "search"
    entity_id: str = ""  # doc or parent entity_id
    parent_id: str = ""  # same as entity_id for doc-grouped items
    done: bool = False
    # Two fields, because they are two different things. `snippet` is raw text the
    # retriever happened to return; `findings` is what an extraction concluded. They
    # shared one field, so a real finding could never overwrite a prefetch snippet (the
    # write was guarded by "only if empty"), and clear_snippet() existed to work around
    # that. Separated, both survive and neither shadows the other.
    snippet: str = ""
    findings: str = ""
    fragment_ids: set[str] = field(default_factory=set)

    def display(self) -> str:
        """What the rendered board shows: the conclusion if there is one, the raw
        snippet only while there is not."""
        return self.findings or self.snippet


class Blackboard:
    """Accumulates investigation state: visited items, findings, pending leads.

    When a ToolMessage is evicted from the LLM context, its key findings
    are recorded here. This keeps the context small while preserving what
    the agent learned.
    """

    def __init__(self) -> None:
        self._items: list[BlackboardItem] = []
        # Index by entity_id. Six methods used to scan the whole list to find one item;
        # the scans were identical and drifted in their tie-breaking.
        self._by_id: dict[str, BlackboardItem] = {}
        self._tool_calls: list[str] = []  # "tool_name(args)" strings for dedup display
        self._findings: list[str] = []  # persists across evictions

    def _add(self, item: BlackboardItem) -> None:
        """The only way an item enters the board, so the index cannot fall behind."""
        self._items.append(item)
        if item.entity_id and item.entity_id not in self._by_id:
            self._by_id[item.entity_id] = item

    # ── Seeding ───────────────────────────────────────────────────────────

    def seed_prefetch(self, prefetch_data: dict, max_items: int = 20) -> None:
        """Seed from pre-fetch results — top N fragments by score with snippets."""
        results = prefetch_data.get("results", [])
        if not results:
            return
        seen: set[str] = set()
        for r in results[:max_items]:
            frag_id = r.get("entity_id", "")
            if not frag_id or frag_id in seen:
                continue
            seen.add(frag_id)
            parent = r.get("source_file_id") or frag_id
            label = r.get("document", frag_id[:12])
            snippet = r.get("text", "")[:200]
            self._add(
                BlackboardItem(
                    label=label,
                    source="prefetch",
                    entity_id=frag_id,
                    parent_id=parent,
                    snippet=snippet,
                )
            )

    # ── LLM interface (called by the investigate tool) ────────────────────

    def add_lead(self, description: str, entity_id: str = "") -> str:
        """LLM flags a lead to investigate. Returns JSON confirmation."""
        for item in self._items:
            if item.label.lower() == description.lower():
                return json.dumps({"ok": True, "note": "Already tracked"})
        self._add(
            BlackboardItem(label=description, source="lead", entity_id=entity_id)
        )
        return json.dumps(
            {"ok": True, "added": description, "pending": self.pending_count}
        )

    # ── Findings store (persists across evictions) ─────────────────────────

    def add_finding(self, text: str) -> None:
        """Record a key fact. Survives context eviction."""
        text = text.strip()
        if text and text not in self._findings:
            self._findings.append(text)

    @property
    def findings_text(self) -> str:
        if not self._findings:
            return ""
        return "\n".join(f"- {f}" for f in self._findings)

    # ── Auto-tracking (called by tool loop) ───────────────────────────────

    def has_entity(self, entity_id: str) -> bool:
        """Check if an entity_id is tracked on the blackboard."""
        return entity_id in self._by_id

    def mark_visited(self, entity_ids: set[str]) -> None:
        """Mark items as done when tool results reference any of their known IDs."""
        for item in self._items:
            if item.entity_id in entity_ids:
                item.done = True
            elif item.fragment_ids and item.fragment_ids & entity_ids:
                item.done = True

    def mark_fragment_found(
        self, parent_id: str, fragment_id: str, score: float = 0.0, label: str = ""
    ) -> None:
        """Record a fragment discovered by search. Each fragment is its own item."""
        # Skip if already tracked
        if fragment_id in self._by_id:
            return
        self._add(
            BlackboardItem(
                label=label or fragment_id[:12],
                source="search",
                entity_id=fragment_id,
                parent_id=parent_id,
            )
        )

    def mark_fragment_read(
        self, parent_id: str, fragment_id: str, label: str = ""
    ) -> None:
        """Mark a specific fragment as read (done)."""
        tracked = self._by_id.get(fragment_id)
        if tracked is not None:
            tracked.done = True
            return
        # Not tracked yet — add as done
        self._add(
            BlackboardItem(
                label=label or fragment_id[:12],
                source="search",
                entity_id=fragment_id,
                parent_id=parent_id,
                done=True,
            )
        )

    def record_findings(self, entity_id: str, findings: str) -> None:
        """Attach findings to an item by entity_id (called when evicting)."""
        item = self._by_id.get(entity_id)
        if item is None:
            return
        # Overwrites: a conclusion drawn from the full text supersedes whatever was
        # there, which is the entire reason it was extracted.
        item.findings = findings[:500]
        item.done = True

    def clear_snippet(self, entity_id: str) -> None:
        """Drop the raw snippet of a fragment whose content was evicted. Findings are
        untouched: they are what replaced it."""
        item = self._by_id.get(entity_id)
        if item is not None:
            item.snippet = ""

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def pending_count(self) -> int:
        return sum(1 for item in self._items if not item.done)

    @property
    def total_count(self) -> int:
        return len(self._items)

    @property
    def done_count(self) -> int:
        return sum(1 for item in self._items if item.done)

    def pending_items(self) -> list[BlackboardItem]:
        return [item for item in self._items if not item.done]

    def mark_lead_done(self, label: str, findings: str = "") -> None:
        """Mark a lead as done by label or entity_id."""
        for item in self._items:
            if (item.label == label or item.entity_id == label) and not item.done:
                item.done = True
                item.findings = findings[:500]
                return

    def mark_lead_retry(self, entity_id: str) -> None:
        """Reset a previously-complete item to pending for DAG retry."""
        item = self._by_id.get(entity_id)
        if item is not None and item.done:
            item.done = False
            item.findings = ""

    # ── Tool call tracking ─────────────────────────────────────────────────

    def record_tool_call(self, tool_name: str, args_summary: str) -> None:
        """Record a tool call for dedup display in the blackboard."""
        key = f"{tool_name}({args_summary})"
        if key not in self._tool_calls:
            self._tool_calls.append(key)

    def was_tool_called(self, tool_name: str, args_summary: str) -> bool:
        """Check if this exact tool+args was already called."""
        return f"{tool_name}({args_summary})" in self._tool_calls

    # ── Render for LLM context ────────────────────────────────────────────

    @property
    def docs_covered(self) -> int:
        """Count unique parent documents that have at least one fragment read."""
        return len(
            set(item.parent_id for item in self._items if item.done and item.parent_id)
        )

    def coverage_summary(self) -> str:
        """Coverage only: what was checked, what was not, nothing operational.

        `render()` is for an agent that is still working — it carries the tool calls
        already made and the instruction not to repeat them. That belongs in an agent's
        context and not in the material a synthesiser turns into the user's answer.
        """
        if not self._items:
            return ""
        pending = [item.label for item in self._items if not item.done]
        lines = [
            f"## Investigation coverage: {self.done_count}/{self.total_count} items checked"
        ]
        if pending:
            lines.append(
                "NOT checked (say so if the answer depends on them): "
                + "; ".join(pending[:20])
                + (f" ... and {len(pending) - 20} more" if len(pending) > 20 else "")
            )
        if self._findings:
            lines.append(f"Findings recorded: {len(self._findings)}")
        return "\n".join(lines)

    def render(self) -> str:
        """Render blackboard state for injection into LLM context."""
        if not self._items:
            return ""
        lines = [
            f"## Blackboard ({self.done_count}/{self.total_count} fragments checked)"
        ]
        for item in self._items:
            if item.done:
                detail = item.display()
                suffix = f" \u2014 {detail}" if detail else ""
                lines.append(f"  [\u2713] {item.label}{suffix}")
            else:
                lines.append(f"  [ ] {item.label}")

        # Tool calls already executed (don't repeat these)
        if self._tool_calls:
            lines.append(
                f"\n## Queries already executed ({len(self._tool_calls)}) — do NOT repeat:"
            )
            for tc in self._tool_calls[-15:]:  # show last 15
                lines.append(f"  - {tc}")
            if len(self._tool_calls) > 15:
                lines.append(f"  ... and {len(self._tool_calls) - 15} more")

        # Findings — persists across evictions
        if self._findings:
            lines.append(f"\n## Key findings ({len(self._findings)}):")
            for f in self._findings:
                lines.append(f"  - {f}")

        pending = self.pending_count
        total = self.total_count
        done = self.done_count
        frag_pct = (done * 100 // total) if total > 0 else 0
        lines.append(
            f"\nRelevant content read: {done}/{total} fragments ({frag_pct}%)."
        )
        if pending > 0:
            lines.append(f"{pending} fragments remaining. Try DIFFERENT queries.")
        else:
            lines.append("All relevant fragments checked. Write your final answer.")
        return "\n".join(lines)

    def inject_into_messages(self, messages: list) -> None:
        """Replace or append blackboard state as a HumanMessage in the message list.

        Uses HumanMessage with <system-instruction> tags instead of SystemMessage
        because models like Qwen/Llama/Mistral (via vLLM) only allow system
        messages at position 0.  See langgraph#628.
        """
        from langchain_core.messages import HumanMessage

        board_text = self.render()
        if not board_text:
            return
        wrapped = f"<system-instruction>\n{board_text}\n</system-instruction>"
        # Replace existing blackboard message if present
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], HumanMessage) and "## Blackboard" in str(
                messages[i].content
            ):
                messages[i] = HumanMessage(content=wrapped)
                return
        messages.append(HumanMessage(content=wrapped))
