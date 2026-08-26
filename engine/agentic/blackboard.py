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
    source: str  # "prefetch" or "lead"
    entity_id: str = ""  # doc or parent entity_id
    parent_id: str = ""  # same as entity_id for doc-grouped items
    done: bool = False
    findings: str = ""
    fragment_ids: set[str] = field(default_factory=set)


class Blackboard:
    """Accumulates investigation state: visited items, findings, pending leads.

    When a ToolMessage is evicted from the LLM context, its key findings
    are recorded here. This keeps the context small while preserving what
    the agent learned.
    """

    def __init__(self) -> None:
        self._items: list[BlackboardItem] = []
        self._tool_calls: list[str] = []  # "tool_name(args)" strings for dedup display
        self._findings: list[str] = []  # persists across evictions

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
            self._items.append(
                BlackboardItem(
                    label=label,
                    source="prefetch",
                    entity_id=frag_id,
                    parent_id=parent,
                    findings=snippet,
                )
            )

    # ── LLM interface (called by the investigate tool) ────────────────────

    def add_lead(self, description: str, entity_id: str = "") -> str:
        """LLM flags a lead to investigate. Returns JSON confirmation."""
        for item in self._items:
            if item.label.lower() == description.lower():
                return json.dumps({"ok": True, "note": "Already tracked"})
        self._items.append(
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
        return any(item.entity_id == entity_id for item in self._items)

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
        if any(item.entity_id == fragment_id for item in self._items):
            return
        self._items.append(
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
        for item in self._items:
            if item.entity_id == fragment_id:
                item.done = True
                return
        # Not tracked yet — add as done
        self._items.append(
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
        for item in self._items:
            if item.entity_id == entity_id and not item.findings:
                item.findings = findings[:500]
                item.done = True
                return

    def clear_snippet(self, entity_id: str) -> None:
        """Clear the snippet of a fragment whose content was evicted."""
        for item in self._items:
            if item.entity_id == entity_id:
                item.findings = ""
                return

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
        for item in self._items:
            if item.entity_id == entity_id and item.done:
                item.done = False
                item.findings = ""
                return

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

    def render(self) -> str:
        """Render blackboard state for injection into LLM context."""
        if not self._items:
            return ""
        lines = [
            f"## Blackboard ({self.done_count}/{self.total_count} fragments checked)"
        ]
        for item in self._items:
            if item.done:
                findings = f" \u2014 {item.findings}" if item.findings else ""
                lines.append(f"  [\u2713] {item.label}{findings}")
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
