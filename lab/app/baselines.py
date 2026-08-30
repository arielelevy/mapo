"""The prose router, as a measured baseline instead of an assertion.

WHY THIS IS THE MOST IMPORTANT MISSING NUMBER. The product's premise is that routing
written as prose rules, evaluated by a model, is fragile — and that a deterministic
decision layer replaces it. Every measurement so far is about PARADIGMS. Nobody ever
measured the thing being replaced. `Study.selection_terms(decide)` has always accepted
any decision function, and its own docstring names "a prose prompt" as one of them; the
socket was there and nothing was ever plugged into it.

WHAT WOULD MAKE THE COMPARISON DISHONEST, and how each is avoided:

  Writing the prompt myself. The prose classifier here is PORTED from the one that ran
  in production (recovered from git, commit 947daff) — its shape, its first-match-wins
  rules, its default. A router I invented to lose is not evidence about anything.

  Letting the two see different things. `informed` gets exactly what phi carries — unit
  count, content size, budget, whether a cheap detector exists — expressed in prose.
  If the deterministic layer only wins because it is the one holding the numbers, then
  the finding is "give the router the numbers", not "replace prose with arithmetic", and
  those are different papers.

  Hiding the asymmetry that favours us. A prose router costs a model call per request;
  Pi(phi, theta) costs zero. That is a real advantage of the deterministic layer and it
  is reported as a separate number rather than folded into utility, because folding it
  in would let a cost argument dress up as a quality argument.

  Sampling. Temperature 0, fixed seed, content-addressed cache: the baseline is as
  replayable as the thing it is compared against. A baseline that cannot be replayed
  cannot be checked.

TWO VARIANTS, and both are reported. `naive` is the incumbent as it actually ran: the
question and how many documents there are. `informed` is the strongest prose router that
can be built on the same information the deterministic layer uses. Beating `naive` is
worth little; beating `informed` is the claim.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .llm import LLMClient, Usage

# One line per paradigm, describing its CONTROL STRUCTURE and nothing else. No hints
# about which cells it wins: that would be leaking the answer into the baseline's
# prompt, which is the mirror image of writing a strawman.
PARADIGM_SHEET = {
    "direct": "one call containing all the material; no tools, no loop",
    "cot": "one call, asked to reason step by step first",
    "react": "an open loop: the model searches, reads, and decides when to stop",
    "reflection": "a draft, a critique of the draft, then a revision",
    "map_reduce": "one call per unit, then one call merging every partial result",
    "plan_execute": "a plan of sub-questions, each answered by its own sub-agent",
    "dag_strategy": "sub-questions as a dependency graph, run in waves, verified and replanned",
    "rewoo": "a plan written up front with placeholders, executed without re-planning",
    "gist_reader": "a table of one-line gists over all units, then targeted full reads",
    "graph_traverse": "an entity graph over the corpus, walked from the question's entities",
    "extract_compute": "structured extraction per unit, then the aggregate computed in code",
    "streaming_scan": "a single pass over the units carrying a bounded running state",
    "pointer_chase": "a code loop following explicit pointers, one unit per call",
}

NAIVE_PROMPT = """You are a query router for an investigative intelligence platform.

CONSTRAINTS:
- Pick exactly ONE strategy

## Strategy Selection

{default} is the DEFAULT — it handles most queries well with multi-pass search.

Rules (first match wins):
1. "extract ALL [people/addresses/locations/identifiers/entities] connected to X" where \
the answer requires scanning MANY documents exhaustively → a decomposing strategy
2. "how many [people/victims/subjects] did X" when counting across MANY documents → a \
decomposing strategy
3. "who are the most [contacted/frequent/common]" requiring aggregation across \
documents → a decomposing strategy
4. NEVER a decomposing strategy for: "compare", "for each", \
"gaps/weaknesses/contradictions", single-document extraction, summarize, timeline → \
{default}
5. Everything else → {default}

Available strategies:
{sheet}

Reply with JSON only: {{"strategy": "<name>", "reasoning": "<one sentence>"}}"""

INFORMED_PROMPT = """You are a query router. Pick the strategy that will answer the \
question best for the least cost.

Available strategies:
{sheet}

What is known about this request:
- documents in scope: {n_units}
- total content: about {content_tokens} tokens
- the budget for answering: {budget_tokens} tokens
- a cheap exact-match check on the final answer: {oracle}

Judge for yourself whether the material fits the budget, whether the question needs one
document or many, and whether the answer to one part is needed before another part can
be asked at all.

Reply with JSON only: {{"strategy": "<name>", "reasoning": "<one sentence>"}}"""


@dataclass
class RoutingDecision:
    """Lo que un router RIVAL eligió para una tarea, y si eligió algo que existe.

    Es el registro de los baselines contra los que se compara θ: routers de prosa que le
    piden al modelo que nombre un paradigma. `raw` guarda lo que dijo textual, antes de
    normalizar, porque un router que contesta «yo usaría react o quizá rewoo» no eligió y
    hay que poder verlo.

    `fell_back` es el campo que decide: el modelo nombró algo que **no está en el
    catálogo**. No es un error del harness — es el resultado. Un router que inventa brazos
    no se puede evaluar por su utilidad, porque la mitad de sus decisiones no son
    ejecutables, y colapsarlo con «eligió mal» borraría la diferencia entre elegir peor y
    no elegir.
    """

    task_id: str
    paradigm: str
    raw: str
    reasoning: str = ""
    fell_back: bool = False  # the model named something that is not a candidate
    usage: Usage = field(default_factory=Usage)


class ProseRouter:
    """Routes by asking a model, and records what that costs.

    `decide(task_id)` is the signature `Study.selection_terms` expects, so this drops
    straight into the same measurement the deterministic router is scored by — same
    tasks, same recorded rows, same oracle. Only the decision procedure differs, which
    is the entire point of the comparison.
    """

    def __init__(
        self,
        client: LLMClient,
        tasks: list[dict[str, Any]],
        documents: dict[str, str],
        candidates: list[str],
        fallback: str,
        variant: str = "informed",
    ) -> None:
        if variant not in ("naive", "informed"):
            raise ValueError(f"Unknown variant {variant!r}. Use 'naive' or 'informed'.")
        unknown = [p for p in candidates if p not in PARADIGM_SHEET]
        if unknown:
            raise ValueError(
                f"No description for {unknown}. A router cannot choose what the prompt "
                "does not name, and adding it silently would change the comparison."
            )
        self._client = client
        self._tasks = {t["task_id"]: t for t in tasks}
        self._documents = documents
        self._candidates = list(candidates)
        self._fallback = fallback
        self._variant = variant
        self.decisions: dict[str, RoutingDecision] = {}

    # -- the routing cost, reported separately -----------------------------

    @property
    def usage(self) -> Usage:
        total = Usage()
        for decision in self.decisions.values():
            total.merge(decision.usage)
        return total

    @property
    def invalid_choices(self) -> int:
        """How often the model named a strategy that was not on the list.

        Reported, not hidden: a router that cannot stay inside its own option set is
        telling you something about prose routing, and silently mapping it to the
        fallback would erase exactly that signal.
        """
        return sum(1 for d in self.decisions.values() if d.fell_back)

    # -- the decision function -------------------------------------------

    def decide(self, task_id: str) -> str:
        cached = self.decisions.get(task_id)
        if cached is not None:
            return cached.paradigm
        decision = self._route(task_id)
        self.decisions[task_id] = decision
        return decision.paradigm

    def _prompt(self, task: dict[str, Any]) -> str:
        sheet = "\n".join(
            f"- {name}: {PARADIGM_SHEET[name]}" for name in self._candidates
        )
        if self._variant == "naive":
            return NAIVE_PROMPT.format(default=self._fallback, sheet=sheet)
        unit_ids = task.get("unit_ids") or []
        content = sum(len(self._documents.get(u, "")) for u in unit_ids) // 4
        return INFORMED_PROMPT.format(
            sheet=sheet,
            n_units=len(unit_ids),
            content_tokens=f"{content:,}",
            budget_tokens=f"{int(task['budget_tokens']):,}",
            oracle="yes" if task.get("oracle") else "no",
        )

    def _route(self, task_id: str) -> RoutingDecision:
        task = self._tasks[task_id]
        completion = self._client.complete(
            messages=[
                {"role": "system", "content": self._prompt(task)},
                {"role": "user", "content": f"Question: {task['question']}"},
            ]
        )
        raw = completion.text or ""
        chosen, reasoning = _parse_choice(raw)
        if chosen not in self._candidates:
            return RoutingDecision(
                task_id=task_id,
                paradigm=self._fallback,
                raw=raw[:300],
                reasoning=reasoning,
                fell_back=True,
                usage=completion.usage,
            )
        return RoutingDecision(
            task_id=task_id,
            paradigm=chosen,
            raw=raw[:300],
            reasoning=reasoning,
            usage=completion.usage,
        )


def _parse_choice(raw: str) -> tuple[str, str]:
    """The strategy the model named, from JSON if it produced JSON.

    A bare-name fallback is allowed only against the CLOSED set of paradigm names —
    matching a known vocabulary is not the same thing as reading prose for intent, and
    the distinction is the one this project keeps making. If the model wrote something
    the option set does not contain, that is recorded as an invalid choice rather than
    guessed at.
    """
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        payload = json.loads(raw[start:end])
        if isinstance(payload, dict) and isinstance(payload.get("strategy"), str):
            return payload["strategy"].strip(), str(payload.get("reasoning", ""))[:200]
    except (ValueError, json.JSONDecodeError):
        pass

    for name in PARADIGM_SHEET:
        if re.search(rf"\b{re.escape(name)}\b", raw):
            return name, "named outside JSON"
    return "", ""
