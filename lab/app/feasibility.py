"""Feasibility as arithmetic, checked before anything runs.

THE GAP THIS CLOSES. `direct` already refuses when the material does not fit, but the
other paradigms had no cap at all, and two of them need one badly:

    map_reduce      one call per unit plus a reduce over every partial. At 500 units
                    that is 501 calls and a reduce prompt built from 500 findings. It
                    never puts the whole corpus in one context — which is why it looks
                    like it scales — but the REDUCE does, and the call count is a cost
                    ceiling regardless.

    dag_strategy    waves x sub-agents x iterations, with replans on top. The product
                    is knowable in advance and can exceed any budget.

WHY IT IS A SEPARATE LAYER, AND WHY IT MATTERS FOR THE THESIS. Every check here is
arithmetic over quantities the task already declares: how many units, how long they are,
what the budget is. No model call, no statistics, no learning. So the plan space can be
pruned deterministically BEFORE any selection happens, and a paradigm that cannot run is
never a candidate.

That makes feasibility the cheapest routing signal that exists, and it is upstream of
everything else in this harness. A learned policy that spends episodes discovering that
map_reduce loses on 500-unit tasks is learning arithmetic the hard way — the cap was
computable from the task before the first token was spent.

The corollary is the one that matters in production: knowing the length and declining is
not a degradation. It is the difference between a bounded system and a runaway.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CHARS_PER_TOKEN = 4

# One gist line per unit: SUMMARY_CHARS of body plus id and length hint (tools._summarise).
GIST_CHARS = 400

# A paradigm may consume this share of the task budget. The remainder is the
# conversation itself, which a paradigm using the entire budget would not leave room for.
BUDGET_SHARE = 0.6

# One model call per unit stops being a strategy and becomes a batch job. The cap is a
# cost ceiling, not a context limit: 500 calls will complete and should not be paid for.
MAX_MAP_CALLS = 80

# Projected size of a reduce prompt: one finding per unit, at roughly this size each.
EST_FINDING_CHARS = 220

# Worst-case call count for the DAG: sub-questions x sub-agent iterations x replans,
# plus plan, verify and synthesise per round.
MAX_ORCHESTRATION_CALLS = 200

# A paradigm whose GUARANTEED spend exceeds the declared budget by more than this is
# infeasible. Slightly above 1.0 because the projection is an estimate and refusing a
# paradigm that would have come in at 1.01x would be the check being wrong in the other
# direction. Overshoot beyond this is not an estimate error, it is a different plan.
BUDGET_OVERSHOOT_TOLERANCE = 1.15

# Hard ceiling on pointer_chase hops. The effective cap per task is the arithmetic
# min(this, allowance // mean unit): the chase reads ONE unit per hop, so its spend is
# hops x unit, knowable here and enforced identically at runtime.
POINTER_HOP_CAP = 6

# Paradigms that read every unit BY DEFINITION, so their spend is a guarantee and not a
# worst case. The distinction is what lets the check prune map_reduce without also
# pruning the selective paradigms, whose only advantage is that they may read less.
GUARANTEED_FULL_READ = frozenset({"direct", "cot", "map_reduce"})


@dataclass(frozen=True)
class Verdict:
    feasible: bool
    reason: str = ""
    projected_calls: int = 0
    projected_tokens: int = 0
    # Which limit was hit. Two paradigms can both be infeasible for opposite reasons and
    # conflating them is what made map_reduce look like it scaled: it passes CONTEXT by
    # construction, because it never holds the units together, and fails BUDGET, because
    # it still pays for every one of them.
    axis: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "feasible": self.feasible,
            "reason": self.reason,
            "projected_calls": self.projected_calls,
            "projected_tokens": self.projected_tokens,
            "axis": self.axis,
        }


FEASIBLE = Verdict(feasible=True)


def _content_tokens(documents: dict[str, str], unit_ids: list[str]) -> int:
    return sum(len(documents[u]) for u in unit_ids) // CHARS_PER_TOKEN


# The paradigms whose spend is a DECISION, not a guarantee: they read selectively and
# cap their own iterations, so `content` is a worst case and pruning on it would discard
# their only advantage. They are feasible here and bounded at runtime instead.
WORST_CASE_ONLY = frozenset({"react", "reflection"})

# Every name this layer has arithmetic for. Kept explicit so an unknown one raises
# instead of falling through the last branch as "feasible".
KNOWN_PARADIGMS = frozenset({
    "direct",
    "cot",
    "map_reduce",
    "dag_strategy",
    "plan_execute",
    "gist_reader",
    "rewoo",
    "pointer_chase",
    "graph_traverse",
    "extract_compute",
    "streaming_scan",
}) | WORST_CASE_ONLY


def check(
    paradigm: str, documents: dict[str, str], task: dict[str, Any]
) -> Verdict:
    """Whether `paradigm` can run this task at all. Pure arithmetic."""
    unit_ids = task["unit_ids"]
    units = len(unit_ids)
    budget = int(task["budget_tokens"])
    allowance = int(budget * BUDGET_SHARE)
    content = _content_tokens(documents, unit_ids)

    if paradigm in ("direct", "cot"):
        # One prompt containing every unit.
        if content > allowance:
            return Verdict(
                False,
                f"needs all {units} units in one prompt: about {content} tokens "
                f"against an allowance of {allowance}",
                projected_calls=1,
                projected_tokens=content,
                axis="context",
            )
        return Verdict(True, projected_calls=1, projected_tokens=content)

    if paradigm == "map_reduce":
        # One call per unit, then a reduce over every partial finding.
        if units > MAX_MAP_CALLS:
            return Verdict(
                False,
                f"one call per unit over {units} units exceeds the {MAX_MAP_CALLS}-call "
                f"cap; at this cardinality it is a batch job, not a strategy",
                projected_calls=units + 1,
                projected_tokens=content + units * EST_FINDING_CHARS // CHARS_PER_TOKEN,
                axis="cardinality",
            )
        reduce_tokens = units * EST_FINDING_CHARS // CHARS_PER_TOKEN
        if reduce_tokens > allowance:
            return Verdict(
                False,
                f"the reduce step would concatenate {units} findings, about "
                f"{reduce_tokens} tokens against an allowance of {allowance}. "
                f"Per-unit mapping scales; the reduce does not",
                projected_calls=units + 1,
                projected_tokens=content + reduce_tokens,
                axis="context",
            )
        # THE CHECK THAT WAS MISSING. Mapping never holds the units together, so it
        # passes the context axis at any size -- which is exactly why it looked like it
        # scaled. But it reads every one of them, so its spend is `content`, guaranteed,
        # and that has to be tested against the budget. Without this line the layer
        # computed 486,404 projected tokens against a 60,000 budget and returned
        # feasible; the paradigm then spent 5.7x the budget proving the point.
        projected = content + reduce_tokens
        if projected > budget * BUDGET_OVERSHOOT_TOLERANCE:
            return Verdict(
                False,
                f"maps over every unit, so it pays for all {units}: about {projected} "
                f"tokens against a declared budget of {budget}. Per-unit mapping keeps "
                f"the CONTEXT bounded and leaves the COST unbounded",
                projected_calls=units + 1,
                projected_tokens=projected,
                axis="budget",
            )
        return Verdict(
            True,
            projected_calls=units + 1,
            projected_tokens=projected,
        )

    if paradigm == "dag_strategy":
        # 4 sub-questions x 10 iterations x (1 + 3 replans), plus plan/verify/synthesise.
        projected = 4 * 10 * 4 + 4 + 1
        if projected > MAX_ORCHESTRATION_CALLS:
            return Verdict(
                False,
                f"worst-case orchestration is {projected} calls, above the "
                f"{MAX_ORCHESTRATION_CALLS} cap",
                projected_calls=projected,
                axis="cardinality",
            )
        return Verdict(True, projected_calls=projected)

    if paradigm == "plan_execute":
        return Verdict(True, projected_calls=5 * 4 + 2)

    if paradigm == "gist_reader":
        # Pays the gist table by construction: one truncated summary per unit in a
        # single prompt. That spend is a guarantee, so it is tested here; the targeted
        # full reads are a decision and are bounded at runtime by the allowance.
        gist_tokens = units * GIST_CHARS // CHARS_PER_TOKEN
        if gist_tokens > allowance:
            return Verdict(
                False,
                f"the gist table alone is about {gist_tokens} tokens for {units} units "
                f"against an allowance of {allowance}",
                projected_calls=2,
                projected_tokens=gist_tokens,
                axis="context",
            )
        return Verdict(True, projected_calls=2, projected_tokens=gist_tokens)

    if paradigm == "rewoo":
        # Two LLM calls plus at most MAX_PLAN_STEPS tool executions, none of which
        # involve the model. Its spend is bounded by construction.
        return Verdict(True, projected_calls=2)

    if paradigm == "pointer_chase":
        # Anchor pick + at most hop_cap sensor calls, ONE unit each, + solve. The hop
        # cap is the same arithmetic the paradigm applies at runtime, so the projection
        # is a guarantee, not a hope. Tested against the BUDGET like the other
        # guaranteed-spend paradigms, not against the conversation allowance: the chase
        # never resends history and solves from a small ledger, so BUDGET_SHARE would
        # reserve room for a conversation this paradigm structurally never holds. Its
        # per-call CONTEXT is one unit, bounded by construction.
        mean_unit = max(1, content // max(1, units))
        hop_cap = min(POINTER_HOP_CAP, max(2, budget // mean_unit))
        if 2 * mean_unit > budget * BUDGET_OVERSHOOT_TOLERANCE:
            return Verdict(
                False,
                f"even two hops of one unit each (~{2 * mean_unit} tokens) exceed the "
                f"declared budget of {budget}; a chain cannot be followed in under "
                f"two hops",
                projected_calls=4,
                projected_tokens=2 * mean_unit,
                axis="budget",
            )
        return Verdict(
            True,
            projected_calls=hop_cap + 2,
            projected_tokens=hop_cap * mean_unit,
        )

    if paradigm == "graph_traverse":
        # Per question: 2 LLM calls + a walk that costs nothing. The index (one short
        # call per unit, `content` read once) is amortised across every question on
        # the corpus and memoised on disk, so it is not charged per task here — the
        # first paying row records it honestly in its own usage.
        return Verdict(True, projected_calls=2)

    if paradigm in ("extract_compute", "streaming_scan"):
        # Both pay the corpus exactly once, in bounded calls; neither has a reduce
        # context bound (extract_compute reduces in code; streaming_scan carries a
        # capped registry). Their guaranteed spend is `content`, tested against budget
        # exactly like map_reduce's.
        if paradigm == "extract_compute" and units > MAX_MAP_CALLS:
            return Verdict(
                False,
                f"one extraction call per unit over {units} units exceeds the "
                f"{MAX_MAP_CALLS}-call cap",
                projected_calls=units + 2,
                axis="cardinality",
            )
        projected = int(content * 1.2)
        calls = (units + 2) if paradigm == "extract_compute" else (units // 3 + 2)
        if projected > budget * BUDGET_OVERSHOOT_TOLERANCE:
            return Verdict(
                False,
                f"scans every unit, so it pays for all {units}: about {projected} "
                f"tokens against a declared budget of {budget}",
                projected_calls=calls,
                projected_tokens=projected,
                axis="budget",
            )
        return Verdict(True, projected_calls=calls, projected_tokens=projected)

    # react and reflection read selectively and cap their own iterations, so `content`
    # is their WORST case and not a guarantee -- they may well answer after two units.
    # Pruning them on a worst case would discard their only advantage, so they stay
    # feasible and the budget has to be enforced at RUNTIME instead, by the tool surface
    # degrading a bulk read it cannot afford.
    #
    # Saying that plainly is the point. This layer bounds the paradigms whose spend is a
    # guarantee; it does not bound the ones whose spend is a decision, and a check that
    # claimed otherwise would be lying about which risk it retires.
    if paradigm not in WORST_CASE_ONLY:
        # A typo used to fall through to "feasible". The whole layer exists to say what
        # can run and why; answering that about a name it does not know is not an
        # answer, it is a guess with the shape of one.
        raise ValueError(
            f"Unknown paradigm {paradigm!r}: feasibility has no arithmetic for it. "
            f"Known: {sorted(KNOWN_PARADIGMS)}."
        )

    return Verdict(
        True,
        projected_tokens=content,
        axis="worst_case_only",
    )


def admissible(
    paradigms: list[str], documents: dict[str, str], task: dict[str, Any]
) -> tuple[list[str], dict[str, Verdict]]:
    """Split candidates into those that can run and the verdicts for all of them.

    Excluded paradigms are returned with their reason rather than dropped: a plan space
    that was narrowed has to say so, or a report reads as if the full space had been
    considered.
    """
    verdicts = {p: check(p, documents, task) for p in paradigms}
    return [p for p, v in verdicts.items() if v.feasible], verdicts
