"""Cognitive tools: tools that act on the agent's own working state.

The retrieval tools act on the world. These act on what the agent has figured out so far,
and the analysis pointed at all three of them without naming them.

WHY THEY ARE A COST MECHANISM, NOT A COMFORT. `react` on the two-hop cell read 49 units
and spent 79,335 tokens where reading the same 49 at once costs 10,474. Batching explains
part of that, but not the shape of it: everything read stays in the message history and is
resent on every subsequent turn, so the cost of reading unit 1 is paid again on turn 12.

A note is a compression: 1,100 characters of memo become 80 characters of finding, and the
raw text can then be dropped from history. That is the actual lever — not that the agent
remembers better, but that it stops paying rent on text it has already understood.

THREE TOOLS, EACH ANSWERING A MEASURED FAILURE:

    note / notes    plan_execute reported an incomplete answer because sub-agents had no
                    shared place to accumulate. A note is that place, and unlike a
                    synthesis prompt it survives the sub-agent that wrote it.

    plan / advance   dag_strategy had all four chain units and could not assemble them.
                    A chain is sequential and its structure needs somewhere to live; the
                    blackboard accumulated FINDINGS but never the ORDER between them.

    compaction      react paid for the same text a dozen times. Once a unit is noted, its
                    raw tool result is replaced by a stub.

WHAT IS NOT CLAIMED. None of this makes the model reason better. It gives the reasoning
somewhere to be written down, which is a different and smaller claim — and the one the
measurements support.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# A note longer than this is not a note, it is a copy of the source. The cap is what
# forces compression to actually happen rather than being nominal.
MAX_NOTE_CHARS = 400
MAX_NOTES = 60

COGNITIVE_TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "note",
            "description": (
                "Write down a finding under a short topic, so you do not have to keep "
                "the source text in view to remember it. Notes persist across every "
                "step of the task and are visible to any other agent working on it. "
                f"Keep each note under {MAX_NOTE_CHARS} characters: a note as long as "
                "the source is a copy, not a finding. Note as you go — this is what "
                "makes it safe to stop re-reading."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "short label"},
                    "finding": {"type": "string"},
                    "unit_ids": {
                        "type": "string",
                        "description": "comma-separated ids this came from, if any",
                    },
                },
                "required": ["topic", "finding"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notes",
            "description": (
                "Read back everything noted so far on this task, including notes written "
                "by other agents working on it. Call it before answering to see what has "
                "already been established."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan",
            "description": (
                "Record an ordered plan of steps. Use it when the task is SEQUENTIAL — "
                "when a later step cannot be formulated until an earlier one is answered, "
                "as in following a chain of references. Splitting such a task into "
                "independent parallel questions loses the order and the answer cannot be "
                "reassembled from the pieces."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "string",
                        "description": "the steps in order, one per line",
                    }
                },
                "required": ["steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "advance",
            "description": (
                "Record the result of the current plan step and move to the next. Returns "
                "the next step, with the results of all previous ones — which is what "
                "lets a later step be formulated from an earlier answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {"result": {"type": "string"}},
                "required": ["result"],
            },
        },
    },
]


@dataclass
class Note:
    topic: str
    finding: str
    unit_ids: list[str] = field(default_factory=list)

    def render(self) -> str:
        source = f" [{','.join(self.unit_ids)}]" if self.unit_ids else ""
        return f"- {self.topic}: {self.finding}{source}"


@dataclass
class WorkingState:
    """Notes and an ordered plan, shared across every agent on one task."""

    notes: list[Note] = field(default_factory=list)
    plan_steps: list[str] = field(default_factory=list)
    plan_results: list[str] = field(default_factory=list)
    noted_units: set[str] = field(default_factory=set)
    compactions: int = 0

    # -- notes -------------------------------------------------------------

    def add_note(self, topic: str, finding: str, unit_ids: list[str]) -> dict[str, Any]:
        if len(self.notes) >= MAX_NOTES:
            return {
                "error": f"note limit reached ({MAX_NOTES}). Consolidate existing notes "
                         "instead of adding more."
            }
        truncated = len(finding) > MAX_NOTE_CHARS
        note = Note(
            topic=topic.strip()[:80],
            finding=finding.strip()[:MAX_NOTE_CHARS],
            unit_ids=[u.strip() for u in unit_ids if u.strip()],
        )
        self.notes.append(note)
        self.noted_units.update(note.unit_ids)
        return {
            "recorded": note.render(),
            "notes_total": len(self.notes),
            "truncated": truncated,
            # Stated explicitly: the whole point is that the agent can now stop carrying
            # the source text, and it will not do that unless told it is safe to.
            "hint": (
                "The source text for the noted units has been compacted out of the "
                "conversation. This note is now your record of it."
                if note.unit_ids else
                "Noted. You can rely on this instead of re-reading."
            ),
        }

    def render_notes(self) -> dict[str, Any]:
        if not self.notes:
            return {"notes": [], "hint": "Nothing noted yet."}
        return {
            "notes": [n.render() for n in self.notes],
            "count": len(self.notes),
            "units_covered": sorted(self.noted_units),
        }

    # -- plan --------------------------------------------------------------

    def set_plan(self, steps_text: str) -> dict[str, Any]:
        steps = [s.strip(" -*\t") for s in steps_text.splitlines() if s.strip()]
        if not steps:
            return {"error": "no steps parsed; give one step per line"}
        self.plan_steps = steps
        self.plan_results = []
        return {
            "steps": steps,
            "current_step": 1,
            "current": steps[0],
            "hint": "Answer step 1, then call advance with its result.",
        }

    def advance(self, result: str) -> dict[str, Any]:
        if not self.plan_steps:
            return {"error": "no plan recorded; call plan first"}
        self.plan_results.append(result.strip()[:MAX_NOTE_CHARS])
        done = len(self.plan_results)
        if done >= len(self.plan_steps):
            return {
                "complete": True,
                "steps": self.plan_steps,
                "results": self.plan_results,
                "hint": "Every step is answered. Assemble the final answer from these.",
            }
        return {
            "complete": False,
            "current_step": done + 1,
            "current": self.plan_steps[done],
            "previous_results": self.plan_results,
            "hint": (
                "Use the previous results to formulate this step — that is what makes a "
                "chain resolvable."
            ),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "notes": len(self.notes),
            "noted_units": len(self.noted_units),
            "plan_steps": len(self.plan_steps),
            "plan_completed": len(self.plan_results),
            "compactions": self.compactions,
        }


def compact_history(
    messages: list[dict[str, Any]], noted_units: set[str], state: WorkingState
) -> int:
    """Replace raw tool results for noted units with a stub.

    This is where the cost saving is. A tool result stays in the history and is resent on
    every subsequent turn, so text read on turn 2 is paid for again on turn 12. Once its
    content is recorded as a note, the raw copy is redundant and is replaced by a marker
    pointing at the note.

    Conservative by design: only `read` and `semantic_search` results are compacted, only
    for units that are actually noted, and the stub names them so the agent can re-read
    if it decides the note was insufficient. Nothing is deleted that has not been
    summarised somewhere the agent can still see.

    That last sentence is the reason this works entry by entry rather than message by
    message. A batched read puts several units in ONE tool result; replacing the whole
    message because one of them is noted took the other N-1 with it -- unnoted, unstubbed
    and unmentioned, so the agent could not even know to re-read them. Only the noted
    entries are demoted; the rest stay verbatim, and the message is replaced wholesale
    only when every entry in it was noted.
    """
    if not noted_units:
        return 0

    compacted = 0
    for message in messages:
        if message.get("role") != "tool":
            continue
        content = message.get("content") or ""
        if content.startswith("[compacted"):
            continue
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            continue

        entries = payload if isinstance(payload, list) else payload.get("results")
        if not isinstance(entries, list):
            continue
        # Only full-text payloads are worth compacting; summaries and highlights are
        # already small and removing them would lose the map of what exists.
        def is_noted_full_text(entry: Any) -> bool:
            return (
                isinstance(entry, dict)
                and "text" in entry
                and entry.get("unit_id") in noted_units
            )

        ids = [e.get("unit_id") for e in entries if is_noted_full_text(e)]
        if not ids:
            continue

        if all(is_noted_full_text(e) for e in entries):
            message["content"] = (
                f"[compacted: full text of {', '.join(ids)} removed; "
                f"the findings are in notes]"
            )
        else:
            rewritten = [
                {
                    "unit_id": e.get("unit_id"),
                    "compacted": "full text removed; the findings are in notes",
                }
                if is_noted_full_text(e) else e
                for e in entries
            ]
            if isinstance(payload, list):
                message["content"] = json.dumps(rewritten, ensure_ascii=False)
            else:
                payload["results"] = rewritten
                message["content"] = json.dumps(payload, ensure_ascii=False)
        compacted += 1

    state.compactions += compacted
    return compacted


# The managed board: what a gist keeps of a demoted full text. Long enough to carry the
# entry's identity, short enough that keeping sixty of them costs less than one unit.
MANAGED_GIST_CHARS = 220


def manage_history(messages: list[dict[str, Any]]) -> int:
    """Deterministic, unconditional history management — the `managed` surface.

    The cognitive arm measured that voluntary self-management does not happen: exposed
    as optional tools, the model wrote 1 note, compacted once and never planned in 28
    rows. So this variant moves the bookkeeping to the environment, consistent with the
    thesis: the model is not asked to be disciplined; the harness is.

    Every full-text tool result from turns BEFORE the current batch is demoted to a
    gist stub carrying the unit id — nothing is deleted, only demoted down the
    granularity ladder, and the id makes it re-readable on demand. The model's next
    turn therefore sees: the question, the board of gists, and the current batch in
    full. Text read on turn 2 stops being paid for on turn 12.
    """
    # Everything after the LAST assistant message with tool calls is the current batch,
    # which the model has not reasoned over yet and must see in full.
    last_batch = 0
    for i, message in enumerate(messages):
        if message.get("role") == "assistant" and message.get("tool_calls"):
            last_batch = i

    demoted = 0
    for message in messages[:last_batch]:
        if message.get("role") != "tool":
            continue
        content = message.get("content") or ""
        if content.startswith("[board]"):
            continue
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            continue
        entries = payload if isinstance(payload, list) else payload.get("results")
        if not isinstance(entries, list):
            continue
        full = [e for e in entries if isinstance(e, dict) and "text" in e and "unit_id" in e]
        if not full:
            continue  # summaries and highlights are already small; keep the map intact
        stubs = "\n".join(
            f"[{e['unit_id']}] {' '.join(str(e['text']).split())[:MANAGED_GIST_CHARS]} "
            f"… [{len(str(e['text']))} chars; re-read with read('{e['unit_id']}')]"
            for e in full
        )
        message["content"] = f"[board] demoted to gists:\n{stubs}"
        demoted += 1
    return demoted
