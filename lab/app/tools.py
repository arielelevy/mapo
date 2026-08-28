"""The retrieval tool surface.

WHAT THIS CORRECTS. The harness offered two tools: one blunt `search` and one `read`.
That flattens the decision the study exists to measure. Choosing WHICH retrieval
modality to use, at WHAT granularity, in WHAT sequence, and with how much BATCHING is
the agent's own business — it is the topology. A harness that pre-decides it by fusing
everything into one call has taken the decision away and then measures what is left.

Fusing BM25 and dense into a single hybrid tool was the specific mistake. Hybrid is the
right DEFAULT, but exposing only the fused view means the agent can never choose exact
matching when it needs an identifier, or meaning when it needs a paraphrase. Both are
exposed, plus the fused entry point, and the agent decides.

FOUR TOOLS, THREE GRANULARITIES. The granularity is the cost lever:

    search           hybrid, broad          -> SUMMARIES        cheapest per hit
    keyword_search   BM25, exact terms      -> HIGHLIGHTS       cheap, precise
    semantic_search  dense, by meaning      -> FULL TEXT        expensive, recall
    read             by id, batched         -> FULL TEXT        exact cost, no guessing

A paradigm that only ever calls `read` pays full price for everything. One that summarises
first and reads selectively pays less. That difference is a topology difference, and it
was invisible while every search returned the same fixed excerpt.

THE SEQUENCE IS TAUGHT, NOT ENFORCED. Descriptions state the snowball: find a value, then
search with that value to find where else it appears. Multi-hop questions are unanswerable
without it, and a tool surface that does not mention it measures whether the model
happens to invent it rather than whether the topology can exploit it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .cognitive import COGNITIVE_TOOL_SPECS, WorkingState
from .retrieval import CorpusView, LexicalRetriever, Retriever, tokenise

SUMMARY_CHARS = 180
HIGHLIGHT_WINDOW = 90
MAX_BATCH_READ = 10
# Rough chars-per-token. Only used to decide whether a bulk read fits, so an
# approximation is adequate and an exact tokeniser would be false precision.
CHARS_PER_TOKEN = 4
# Fraction of the task budget a single bulk read may consume. Leaves room for the
# rest of the conversation, which a read that used the entire budget would not.
BULK_READ_BUDGET_SHARE = 0.6

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": (
                "Broad hybrid search combining keywords and semantic similarity. "
                "Returns SUMMARIES of matching units, not their full text. "
                "Start here to find out which units exist and roughly what they say. "
                "For a targeted lookup prefer keyword_search or semantic_search. "
                "Use read with the unit_ids from these results to get full content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "description": "default 8"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "keyword_search",
            "description": (
                "Keyword search (BM25) — finds units containing EXACT terms. "
                "The right tool for identifiers, account numbers and proper names. "
                "Returns HIGHLIGHTS: short windows around each match, marked with "
                "<< >>. Cheaper than reading. When a highlight reveals a specific "
                "value, search again with THAT value to find where else it appears — "
                "this is how a chain of references is followed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "description": "default 8"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "semantic_search",
            "description": (
                "Semantic vector search — finds units by MEANING even when the exact "
                "words differ. Use it when the same fact may be phrased several ways. "
                "Returns FULL TEXT of matching units, so this IS reading them and costs "
                "accordingly. Complements keyword_search: running both covers more than "
                "either alone."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "description": "default 5"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": (
                "Read the full text of units by id. Pass MULTIPLE ids comma-separated "
                f"to read in one call, up to {MAX_BATCH_READ} — never call once per "
                "unit when several are needed. Use only ids returned by a search."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_ids": {
                        "type": "string",
                        "description": "one id, or several comma-separated",
                    }
                },
                "required": ["unit_ids"],
            },
        },
    },
]


# The accounting tools. Available under the variants that include them (`accounting` and,
# cumulatively, `cognitive`), so the conditions stay comparable.
ACCOUNTING_TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "coverage",
            "description": (
                "How much of the task you have actually seen: units read, units total, "
                "and which ids you have not touched. Call it before answering a "
                "question that asks for ALL of something or for a COUNT — an answer "
                "assembled from part of the units is wrong even when every part is "
                "right, and nothing else will tell you that."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_all",
            "description": (
                "Read every unit in the task in ONE call. Use it when you have decided "
                "you need most of them: reading the same units one call at a time costs "
                "several times more, because the whole conversation is resent each turn. "
                "If the full text does not fit the task budget it returns summaries of "
                "every unit instead, and tells you the real size — reading everything is "
                "not always available, and on a large task it is not."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


VARIANTS = ("basic", "accounting", "cognitive", "managed")

# The variants whose tool list includes the accounting tools. `cognitive` is cumulative
# (see specs_for), so anything gated on "has accounting" must name both or the model is
# offered a tool that dispatch then refuses.
ACCOUNTING_VARIANTS = ("accounting", "cognitive")


def specs_for(variant: str) -> list[dict[str, Any]]:
    """The tool list for a surface variant.

    Cumulative on purpose: `cognitive` includes the accounting tools, because the two
    address different failures and a variant that removed accounting to add notes would
    confound them. Each rung adds; none replaces.
    """
    if variant == "basic":
        return list(TOOL_SPECS)
    if variant == "accounting":
        return list(TOOL_SPECS) + list(ACCOUNTING_TOOL_SPECS)
    if variant == "cognitive":
        return (
            list(TOOL_SPECS)
            + list(ACCOUNTING_TOOL_SPECS)
            + list(COGNITIVE_TOOL_SPECS)
        )
    if variant == "managed":
        # Same tools as basic, deliberately: the difference under test is not what the
        # model CAN call but what the harness DOES to the history. The cognitive arm
        # measured that voluntary self-management does not happen (1 note, 1 compaction,
        # 0 plans in 28 rows); `managed` moves the bookkeeping to the environment.
        return list(TOOL_SPECS)
    raise ValueError(f"Unknown surface variant {variant!r}. Use one of {VARIANTS}.")


class ToolFailure(Exception):
    """A tool call the model got wrong, as opposed to a bug in the harness."""


def _summarise(text: str) -> str:
    """First substantive line plus a length hint.

    A summary has to be genuinely cheaper than the unit or the granularity ladder is
    decoration. The length hint is what lets an agent decide whether reading is worth it.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    body = next((line for line in lines[1:] if len(line) > 30), lines[0] if lines else "")
    return f"{body[:SUMMARY_CHARS]} … [{len(text)} chars]"


def _highlight(text: str, terms: list[str]) -> str:
    """Windows around matches, marked, rather than the whole unit."""
    lowered = text.lower()
    spans: list[tuple[int, int]] = []
    for term in terms:
        for match in re.finditer(re.escape(term), lowered):
            spans.append((
                max(0, match.start() - HIGHLIGHT_WINDOW),
                min(len(text), match.end() + HIGHLIGHT_WINDOW),
            ))
    if not spans:
        return ""
    spans.sort()
    merged: list[list[int]] = [list(spans[0])]
    for start, end in spans[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return " … ".join(f"<<{text[a:b].strip()}>>" for a, b in merged[:3])


@dataclass
class ToolSurface:
    """The four retrieval tools over one task's units, plus usage accounting."""

    view: CorpusView
    hybrid: Retriever
    semantic: Retriever
    # The task's own declared budget. read_all refuses full text above a share of it
    # rather than inventing a separate limit.
    budget_tokens: int = 60_000
    lexical: Retriever = field(default_factory=LexicalRetriever)
    variant: str = "basic"
    calls: dict[str, int] = field(default_factory=dict)
    units_read: set[str] = field(default_factory=set)
    hallucinated: int = 0
    batched_reads: int = 0
    # Units any search has ever surfaced, and how many consecutive searches surfaced
    # nothing new. A retriever that has stopped producing is the signal an iterative
    # topology needs and never gets: without it, a verify-replan loop reads a systematic
    # failure as bad luck and searches again.
    surfaced: set[str] = field(default_factory=set)
    # El ORDEN en que se llamo a cada herramienta, no solo cuantas veces. `calls` es un
    # conteo, y un conteo no distingue "busco, leyo, busco, leyo" de "busco, busco, leyo,
    # leyo" — que son dos estrategias distintas con el mismo histograma. La secuencia es
    # lo unico que permite aprender asociaciones (tool_i -> tool_j), que es donde el
    # aprendizaje Hebbiano tiene contenido propio: una asociacion entre PARES no se
    # reduce a una estadistica marginal de un brazo.
    sequence: list[str] = field(default_factory=list)
    barren_searches: int = 0
    stall_warnings: int = 0
    bulk_read_refusals: int = 0
    # Shared across every agent working on the task: a note written by one sub-agent is
    # readable by the next. That persistence is the point — a synthesis prompt cannot
    # recover what a sub-agent knew and did not write down.
    state: WorkingState = field(default_factory=WorkingState)

    def unit_ids(self) -> list[str]:
        return list(self.view.unit_ids)

    def read_one(self, unit_id: str) -> str:
        if unit_id not in self.view.unit_ids:
            raise ToolFailure(f"Unit {unit_id} is not part of this task.")
        return self.view.documents[unit_id]

    # -- dispatch ----------------------------------------------------------

    # -- accounting --------------------------------------------------------

    def _note_search(self, returned: list[str]) -> str:
        """Update the stall counter and return a warning when the retriever has dried up.

        Three consecutive searches that surface nothing new is not bad luck, it is a
        retriever that cannot find the thing. Saying so lets a loop escalate to reading
        instead of searching a fourth time.
        """
        fresh = [u for u in returned if u not in self.surfaced]
        self.surfaced.update(returned)
        if fresh:
            self.barren_searches = 0
            return ""
        self.barren_searches += 1
        if self.barren_searches < 3 or self.variant not in ACCOUNTING_VARIANTS:
            return ""
        self.stall_warnings += 1
        unread = [u for u in self.view.unit_ids if u not in self.units_read]
        return (
            f"NOTE: the last {self.barren_searches} searches surfaced nothing new. "
            f"Searching again is unlikely to help. {len(unread)} units are still "
            f"unread — consider read_all or read on specific ids instead."
        )

    def bulk_read_tokens(self) -> int:
        return sum(len(self.view.documents[u]) for u in self.view.unit_ids) // CHARS_PER_TOKEN

    def bulk_read_fits(self) -> bool:
        """Whether the whole task fits a share of its own declared budget."""
        return self.bulk_read_tokens() <= int(self.budget_tokens * BULK_READ_BUDGET_SHARE)

    def _read_all(self) -> dict[str, Any]:
        """Everything, at the highest granularity that fits the task budget.

        Over budget this does NOT truncate silently. A silent cut is the worst outcome:
        the agent believes it has seen everything, answers from a prefix, and nothing in
        the transcript says otherwise. Returning summaries of ALL units keeps the map
        complete while making the constraint explicit.
        """
        total_chars = sum(len(self.view.documents[u]) for u in self.view.unit_ids)
        est_tokens = total_chars // CHARS_PER_TOKEN
        allowance = int(self.budget_tokens * BULK_READ_BUDGET_SHARE)

        if est_tokens <= allowance:
            self.units_read.update(self.view.unit_ids)
            self.batched_reads += 1
            return {
                "granularity": "full_text",
                "units": [
                    {"unit_id": u, "text": self.view.documents[u]}
                    for u in self.view.unit_ids
                ],
                "estimated_tokens": est_tokens,
            }

        self.bulk_read_refusals += 1
        return {
            "granularity": "summaries",
            "reason": (
                f"full text of {len(self.view.unit_ids)} units is about {est_tokens} "
                f"tokens against an allowance of {allowance}. Returning summaries of "
                f"all of them instead. Reading everything is not available on this "
                f"task — select what you need and read those."
            ),
            "units": [
                {"unit_id": u, "summary": _summarise(self.view.documents[u])}
                for u in self.view.unit_ids
            ],
            "estimated_tokens_if_full": est_tokens,
            "allowance": allowance,
        }

    def _coverage(self) -> dict[str, Any]:
        total = len(self.view.unit_ids)
        unread = [u for u in self.view.unit_ids if u not in self.units_read]
        return {
            "units_read": len(self.units_read),
            "units_total": total,
            "fraction_read": round(len(self.units_read) / total, 3) if total else 1.0,
            "unread_unit_ids": unread[:40],
            "unread_count": len(unread),
            "warning": (
                "You have not read every unit. An answer that must cover ALL units, or "
                "count them, cannot be complete from a subset."
                if unread else "Every unit has been read."
            ),
        }

    @staticmethod
    def _required(args: dict[str, Any], key: str, tool: str) -> Any:
        """Un argumento que falta es un error del MODELO, no del harness.

        POR QUE ESTO IMPORTA PARA LA COMPARACION. `args["query"]` crudo levanta
        `KeyError`, y `KeyError` no es `ToolFailure`. El loop compartido atrapa sólo
        `ToolFailure`, asi que ahi una llamada malformada mataba la tarea entera y la
        puntuaba cero; `modern.py` habia ampliado su catch a `(ToolFailure, ValueError,
        KeyError)`, asi que ahi la misma llamada degradaba y seguia.

        O sea: **el mismo output malformado del modelo era recuperable en un paradigma y
        fatal en otro**, y la diferencia entraba a la medicion como si fuera calidad del
        paradigma. Un paradigma que pide mas argumentos por llamada estaba mas expuesto,
        que es precisamente la clase de sesgo con direccion que un banco existe para no
        tener.
        """
        if key not in args or args[key] is None:
            raise ToolFailure(
                f"{tool}: falta el argumento obligatorio '{key}'."
            )
        return args[key]

    @staticmethod
    def _bounded_int(args: dict[str, Any], key: str, default: int, tool: str) -> int:
        """Un `limit` no numerico tampoco es una excepcion del harness."""
        raw = args.get(key, default)
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ToolFailure(
                f"{tool}: '{key}' tiene que ser un entero, llego {raw!r}."
            ) from None

    def dispatch(self, name: str, args: dict[str, Any]) -> str:
        self.calls[name] = self.calls.get(name, 0) + 1
        # Se registra ANTES de despachar, a proposito: una llamada que falla igual fue
        # una decision del modelo, y una secuencia que solo guarda los aciertos describe
        # una politica que nadie ejecuto.
        self.sequence.append(name)

        if name == "coverage":
            if self.variant not in ACCOUNTING_VARIANTS:
                raise ValueError(
                    f"coverage is not available on the {self.variant} surface."
                )
            return json.dumps(self._coverage())

        if name in ("note", "notes", "plan", "advance"):
            if self.variant != "cognitive":
                raise ValueError(f"{name} is not available on the {self.variant} surface.")
            if name == "note":
                units = [
                    u.strip() for u in str(args.get("unit_ids", "")).split(",")
                    if u.strip() and u.strip() in self.view.unit_ids
                ]
                return json.dumps(
                    self.state.add_note(
                        self._required(args, "topic", "note"),
                        self._required(args, "finding", "note"),
                        units,
                    )
                )
            if name == "notes":
                return json.dumps(self.state.render_notes())
            if name == "plan":
                return json.dumps(
                    self.state.set_plan(self._required(args, "steps", "plan"))
                )
            return json.dumps(
                self.state.advance(self._required(args, "result", "advance"))
            )

        if name == "read_all":
            if self.variant in ("basic", "managed"):
                raise ValueError(f"read_all is not available on the {self.variant} surface.")
            return json.dumps(self._read_all())

        if name == "search":
            ranked = self.hybrid.rank(
                self.view,
                self._required(args, "query", "search"),
                self._bounded_int(args, "limit", 8, "search"),
            )
            note = self._note_search(ranked)
            body: dict[str, Any] = {
                "results": [
                    {"unit_id": u, "summary": _summarise(self.view.documents[u])}
                    for u in ranked
                ]
            }
            if note:
                body["note"] = note
            return json.dumps(body)

        if name == "keyword_search":
            query = self._required(args, "query", name)
            ranked = self.lexical.rank(self.view, query, int(args.get("limit", 8)))
            terms = tokenise(query)
            out = []
            for unit_id in ranked:
                snippet = _highlight(self.view.documents[unit_id], terms)
                if snippet:
                    out.append({"unit_id": unit_id, "highlight": snippet})
            note = self._note_search([h["unit_id"] for h in out])
            body: dict[str, Any] = {"results": out}
            if note:
                body["note"] = note
            return json.dumps(body)

        if name == "semantic_search":
            ranked = self.semantic.rank(
                self.view,
                self._required(args, "query", "keyword_search"),
                self._bounded_int(args, "limit", 5, "keyword_search"),
            )
            self.units_read.update(ranked)
            return json.dumps([
                {"unit_id": u, "text": self.view.documents[u]} for u in ranked
            ])

        if name == "read":
            requested = [
                part.strip()
                for part in str(self._required(args, "unit_ids", name)).split(",")
                if part.strip()
            ]
            if len(requested) > 1:
                self.batched_reads += 1
            if len(requested) > MAX_BATCH_READ:
                raise ToolFailure(
                    f"read accepts at most {MAX_BATCH_READ} ids per call, "
                    f"got {len(requested)}."
                )
            out = []
            missing = []
            for unit_id in requested:
                if unit_id not in self.view.unit_ids:
                    missing.append(unit_id)
                    continue
                self.units_read.add(unit_id)
                out.append({"unit_id": unit_id, "text": self.view.documents[unit_id]})
            if missing:
                self.hallucinated += len(missing)
                if not out:
                    # Every id invented. Reported as a recoverable tool error rather
                    # than raised, so one bad citation does not zero the whole task.
                    raise ToolFailure(
                        f"No such units: {missing}. Use only ids returned by a search."
                    )
                out.append({"error": f"no such units: {missing}"})
            return json.dumps(out)

        # An unknown tool is a bug in the paradigm, not something to paper over with a
        # plausible-looking empty result.
        raise ValueError(f"Unknown tool: {name}")

    def usage(self) -> dict[str, Any]:
        """What the paradigm actually did with the surface.

        Recorded because it is the observable trace of the topology: which modality it
        reached for, whether it summarised before reading, whether it batched. Two
        paradigms with the same answer and the same token count can still have used the
        surface in completely different ways, and that difference is the object of study.
        """
        return {
            "variant": self.variant,
            "calls": dict(sorted(self.calls.items())),
            "sequence": list(self.sequence),
            "units_read": len(self.units_read),
            "batched_reads": self.batched_reads,
            "hallucinated_units": self.hallucinated,
            "relevant_units_read": len(self.units_read & self.view.relevant),
            "stall_warnings": self.stall_warnings,
            "bulk_read_refusals": self.bulk_read_refusals,
            "cognitive": self.state.as_dict(),
            "fraction_read": (
                round(len(self.units_read) / len(self.view.unit_ids), 3)
                if self.view.unit_ids else 1.0
            ),
        }
