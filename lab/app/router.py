"""The control plane: theta as a sensor, beliefs as the substrate, rules as the decider.

This module is the integration point. It owns none of the logic:

    rules.sense        turns a task plus whatever is known into a belief base
    assurance.resolve  picks the operating level, floored by beliefs about the request
    beliefs.Governance evaluates the rule set over the belief base, deterministically
    assurance.restrict narrows the pattern space to what the level admits

and this file only wires them together and turns the resulting action into a concrete
plan. Keeping the policy out of here is the point: an if/elif chain cannot be
serialised, diffed, signed or read by someone who does not read Python.

theta's role has also changed shape. It no longer decides; it ASSERTS. `best_paradigm`
and `theta_margin` enter the belief base as COMPUTED beliefs — facts about the bundle,
each with credence 1.0 — and a rule decides whether the margin is large enough to act
on. That separation is what stopped the earlier confusion between a credence (how sure
we are) and an effect size (how big the thing is).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .assurance import (
    Assurance,
    AssuranceDecision,
    AssuranceProfile,
    resolve,
    restrict,
)
from . import feasibility
from .beliefs import BeliefBase, Calibration, Provenance, Verdict
from .policy import MIN_EPISODES_FOR_CONFIDENCE, PolicyBundle
from .rules import (
    ACTION_CASCADE,
    ACTION_DEFER,
    ACTION_GATE,
    ACTION_PROBE,
    ACTION_SPECIALISE,
    BeliefPolicy,
    sense,
    standard_rules,
)


@dataclass
class Plan:
    """A concrete plan plus the full derivation that produced it."""

    action: str
    paradigm: str
    ladder: list[str] = field(default_factory=list)
    gated: bool = False
    needs_probe: bool = False
    excluded_patterns: list[str] = field(default_factory=list)
    assurance: dict[str, Any] = field(default_factory=dict)
    verdict: dict[str, Any] = field(default_factory=dict)
    theta_version: int = -1
    theta_signature: str = ""
    notes: list[str] = field(default_factory=list)

    def explain(self) -> dict[str, Any]:
        """The audit artifact: everything needed to replay this decision."""
        body = {
            "action": self.action,
            "paradigm": self.paradigm,
            "ladder": self.ladder,
            "gated": self.gated,
            "needs_probe": self.needs_probe,
            "excluded_patterns": self.excluded_patterns,
            "assurance": self.assurance,
            "verdict": self.verdict,
            "theta_version": self.theta_version,
            "theta_signature": self.theta_signature,
            "notes": self.notes,
        }
        body["plan_digest"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return body


class Router:
    """Wires the belief layer, the assurance dial and the rule set into a plan."""

    def __init__(
        self,
        bundle: PolicyBundle,
        paradigm_costs: dict[str, float],
        fallback: str,
        calibration: Calibration | None = None,
    ) -> None:
        if not bundle.verify():
            raise ValueError("Refusing to route with an unverified policy bundle.")
        self._theta = bundle
        # Relative priors only: they order a cascade ladder cheapest-first before any
        # episodes exist, and measured mean_cost supersedes them once theta has data.
        self._costs = paradigm_costs
        self._fallback = fallback
        self._calibration = calibration

    # -- theta as a sensor -------------------------------------------------

    def theta_assertions(
        self, region: str, candidates: list[str]
    ) -> tuple[str | None, float]:
        """What theta asserts about this region: the best paradigm and its margin.

        The margin saturates on evidence, so eight episodes is not eighty. A region
        below the episode floor asserts nothing, which is the correct behaviour for a
        bundle that has not learned anything here yet: it leaves the rules with no
        reason to specialise and the request falls to the fallback.
        """
        peers = {
            p: s for p, s in self._theta.paradigms_for(region).items()
            if p in candidates
        }
        if len(peers) < 2:
            return None, 0.0

        best = max(peers, key=lambda p: peers[p].mean_utility)
        stat = peers[best]
        if stat.episodes < MIN_EPISODES_FOR_CONFIDENCE:
            return best, 0.0

        runner_up = max(
            (s.mean_utility for p, s in peers.items() if p != best), default=0.0
        )
        gap = stat.mean_utility - runner_up
        if gap <= 0.0:
            return best, 0.0

        evidence = min(1.0, stat.episodes / (4.0 * MIN_EPISODES_FOR_CONFIDENCE))
        margin = stat.win_rate * evidence * min(1.0, gap * 4.0)
        return best, max(0.0, min(1.0, margin))

    # -- the decision ------------------------------------------------------

    def plan(
        self,
        task: dict[str, Any],
        candidates: list[str],
        region: str,
        documents: dict[str, str] | None = None,
        requested: Assurance = Assurance.STANDARD,
        coupling: float | None = None,
        coupling_provenance: Provenance = Provenance.ELICITED,
        coupling_credence: float = 0.0,
        horizon_unknown: bool | None = None,
    ) -> Plan:
        if not candidates:
            raise ValueError("No candidate paradigms were supplied.")

        # Feasibility prunes first, and for free. A learned policy that spends episodes
        # discovering that map_reduce loses on 500-unit tasks is learning arithmetic the
        # hard way: the cap was computable from the task before any token was spent.
        infeasible: dict[str, str] = {}
        if documents is not None:
            runnable, verdicts = feasibility.admissible(candidates, documents, task)
            infeasible = {p: v.reason for p, v in verdicts.items() if not v.feasible}
            if not runnable:
                raise ValueError(
                    "No candidate can run this task: "
                    + "; ".join(f"{p}: {r}" for p, r in sorted(infeasible.items()))
                )
            candidates = runnable

        trustworthy = bool(self._calibration and self._calibration.is_trustworthy())

        # First pass: a provisional base, only to derive the assurance floor. The
        # floor depends on COMPUTED beliefs about the request, so a cheap policy is
        # sufficient here and the level it yields cannot be gamed by an estimate.
        floor_policy = BeliefPolicy.from_trust(trustworthy, self._theta.tau)
        provisional = sense(task, floor_policy)
        decision: AssuranceDecision = resolve(
            provisional,
            requested=requested,
            calibration_trustworthy=trustworthy,
            # The learned floor rides on the signed bundle, so a request cannot be
            # raised to a stricter level by anything that has not been promoted.
            learned={
                r: Assurance(level) for r, level in self._theta.floors.items()
            },
            region=region,
        )
        profile: AssuranceProfile = decision.profile

        admissible, excluded = restrict(candidates, profile)
        if not admissible:
            raise ValueError(
                f"Assurance level {decision.level.label} admits none of {candidates}."
            )

        # Second pass: the real base, built under the resolved profile so the sensors
        # and the rules agree on what provenance counts as known.
        # The profile's floor is carried through as-is. Projecting it onto a boolean
        # lost A0: its ASSUMED floor is looser than elicited, and the projection turned
        # it into OBSERVED -- the strictest floor of the four, at the least strict level.
        policy = BeliefPolicy(derived_floor=profile.derived_floor, tau=self._theta.tau)
        best, margin = self.theta_assertions(region, admissible)
        base: BeliefBase = sense(
            task,
            policy,
            theta_best=best,
            theta_confidence=margin,
            coupling=coupling,
            coupling_provenance=coupling_provenance,
            coupling_credence=coupling_credence,
            horizon_unknown=horizon_unknown,
        )

        verdict: Verdict = standard_rules(policy).decide(base)
        return self._materialise(
            verdict, decision, profile, admissible, excluded, best, infeasible
        )

    def _materialise(
        self,
        verdict: Verdict,
        decision: AssuranceDecision,
        profile: AssuranceProfile,
        admissible: list[str],
        excluded: list[str],
        theta_best: str | None,
        infeasible: dict[str, str] | None = None,
    ) -> Plan:
        """Turn a rule action into a concrete plan under the assurance profile."""
        notes: list[str] = []
        infeasible = infeasible or {}
        cheapest = min(admissible, key=lambda p: self._costs.get(p, 1.0))
        ladder = sorted(admissible, key=lambda p: self._costs.get(p, 1.0))

        fallback = self._fallback
        if fallback not in admissible:
            # The fallback must itself be admissible or there is nothing safe to defer
            # to. Substituting the cheapest is a real narrowing and is recorded.
            notes.append(
                f"fallback {fallback} is not admissible at {decision.level.label}; "
                f"using {cheapest} as the safe default instead"
            )
            fallback = cheapest

        action = verdict.action
        if action == ACTION_CASCADE:
            paradigm, plan_ladder, gated, probe = ladder[0], ladder, False, False
        elif action == ACTION_PROBE:
            paradigm, plan_ladder, gated, probe = cheapest, [cheapest], False, True
        elif action == ACTION_GATE:
            paradigm, plan_ladder, gated, probe = fallback, [fallback], True, False
        elif action == ACTION_SPECIALISE:
            if theta_best and theta_best in admissible:
                paradigm = theta_best
            else:
                paradigm = fallback
                notes.append(
                    "rule chose to specialise but theta named no admissible paradigm; "
                    "deferring to the safe default rather than picking arbitrarily"
                )
            plan_ladder, gated, probe = [paradigm], False, False
        elif action == ACTION_DEFER:
            paradigm, plan_ladder, gated, probe = fallback, [fallback], False, False
        else:
            raise ValueError(f"Unknown rule action: {action}")

        if infeasible:
            notes.append(
                "pruned as infeasible before any selection: "
                + "; ".join(f"{p} ({r})" for p, r in sorted(infeasible.items()))
            )
        if excluded:
            notes.append(
                f"{decision.level.label} excluded {sorted(excluded)} from the plan "
                "space — not because they are worse, but because their control flow "
                "is unbounded or their failure modes are not enumerable"
            )
        if len(plan_ladder) > profile.max_composition_depth:
            plan_ladder = plan_ladder[: profile.max_composition_depth]
            notes.append(
                f"ladder truncated to depth {profile.max_composition_depth} by "
                f"{decision.level.label}"
            )

        return Plan(
            action=action,
            paradigm=paradigm,
            ladder=plan_ladder,
            gated=gated,
            needs_probe=probe,
            excluded_patterns=sorted(excluded),
            assurance=decision.as_dict(),
            verdict=verdict.as_dict(),
            theta_version=self._theta.version,
            theta_signature=self._theta.signature,
            notes=notes,
        )

    # -- offline valuation -------------------------------------------------

    def value_on(
        self, episodes: list[Any], requested: Assurance = Assurance.STANDARD
    ) -> float:
        """Mean utility this router would have obtained on recorded episodes.

        Used by the promotion guard in `policy.py`. Episodes are grouped by task so the
        chosen paradigm is scored against what it actually achieved on that task rather
        than against a global average.
        """
        by_task: dict[str, dict[str, Any]] = {}
        for episode in episodes:
            by_task.setdefault(episode.task_id, {})[episode.paradigm] = episode

        total = 0.0
        counted = 0
        for observed in by_task.values():
            any_episode = next(iter(observed.values()))
            task = _task_from_region(any_episode.region)
            # The region records what coupling was measured; not passing it made every
            # tight region fall to the probe rule and pick the cheapest candidate, so
            # the guard was valuing a router that is not the one in production.
            coupling, credence = _coupling_from_region(any_episode.region)
            plan = self.plan(
                task=task,
                candidates=sorted(observed),
                region=any_episode.region,
                requested=requested,
                coupling=coupling,
                coupling_provenance=Provenance.OBSERVED,
                coupling_credence=credence,
            )
            # An unmeasured pick is still a pick. Skipping the task made `counted`
            # depend on WHICH paradigm each bundle chose, so incumbent and candidate
            # were averaged over different populations and the guard tilted toward
            # whichever bundle picked the rarely-run paradigm. Every task enters the
            # denominator now: an unmeasured pick is scored at what the fallback
            # actually achieved on that task, and at 0.0 when not even that was run.
            if plan.paradigm in observed:
                total += observed[plan.paradigm].utility
            elif self._fallback in observed:
                total += observed[self._fallback].utility
            counted += 1

        return total / counted if counted else 0.0


# Representative mid-bin coupling for each region label. The bins are the router's own
# (features.region), and the midpoint is the honest reconstruction: the label is all the
# episode kept. "unknown" stays unmeasured -- credence 0 -- because inventing a value
# there would assert a belief nothing backs.
_REGION_COUPLING = {"loose": 0.15, "mixed": 0.5, "tight": 0.85}


def _coupling_from_region(region: str) -> tuple[float | None, float]:
    label = region.split("/")[2]
    if label not in _REGION_COUPLING:
        return None, 0.0
    return _REGION_COUPLING[label], 1.0


def _task_from_region(region: str) -> dict[str, Any]:
    """Reconstruct a representative task payload from a region label.

    Lossy by construction: a region is a binning of the feature vector, so this
    recovers a representative point rather than the original task. Adequate for
    offline valuation, which only ever consults the region.
    """
    card, oracle, _coupling = region.split("/")
    n_units = {"single": 1, "few": 4, "many": 32, "bulk": 128}[card]
    return {
        "unit_ids": [f"u{i}" for i in range(n_units)],
        "oracle": ["x"] if oracle == "oracle" else [],
        "irreversible": False,
        "shared_writes": False,
        "budget_tokens": 100_000,
    }
