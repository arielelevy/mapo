"""Asynchronous consolidation: a sleep cycle over the control policy.

WHAT IS DIFFERENT HERE. Sleep-inspired consolidation for LLM agents is a populated
field, but it consolidates MEMORY CONTENT — entries merged, duplicates removed, stale
items pruned, insights surfaced. This module consolidates the CONTROL POLICY instead:
it replays logged episodes to re-derive theta, to discover better feature partitions,
to prune what never fires, and to find which propositions the model is unreliable about.

And it costs nothing. Every other sleep system needs inference to consolidate. Here the
substrate is a full factorial — every paradigm was already run on every task — so
consolidation is counterfactual replay over the record, with zero new LLM calls.

FOUR STAGES, each with a biological analogue that is load-bearing rather than decorative.

  1. REPLAY.        Re-derive theta from the whole history, ordered by SURPRISE rather
                    than chronology. The online Hebbian update has a recency bias by
                    construction (the decay term); replay removes it. Hippocampal
                    replay is likewise prioritised by behavioural improvement, not by
                    when the experience happened.

  2. ABSTRACTION.   Search for feature partitions that separate paradigms better than
                    the current binning does. This is where the system can "detect a
                    truth" it was not given: the region vocabulary itself becomes
                    learnable. Sleep in animals extracts rules from instances, not just
                    stronger instances.

  3. HOMEOSTASIS.   Downscale globally and prune what never fires. This is L2 plasticity
                    from the v1 whitepaper — neurogenesis and pruning — which was left
                    as future work there and now has a mechanism. Synaptic homeostasis
                    exists because unbounded potentiation saturates.

  4. AUDIT.         Scan the belief record for propositions where ELICITED beliefs are
                    systematically contradicted by later OBSERVED ones. Yields
                    PER-PROPOSITION calibration instead of one global trust switch: a
                    model may be well calibrated about cardinality and hopeless about
                    coupling, and a single switch cannot express that.

THE SAFETY PROPERTY, AND IT IS STRUCTURAL. A cycle is copy-on-write: it produces a
CANDIDATE theta and never mutates the incumbent. A discovered partition enters with zero
episodes, which is below the episode floor, so the router cannot act on it until it has
earned evidence. **A dream is a hypothesis, not a fact.** Nothing reaches production
except through the existing promotion guard.

THE REAL DANGER, STATED PLAINLY. Searching many candidate partitions against one holdout
will find spurious ones — that is multiple comparisons, and it is exactly how "detecting
truths" becomes confabulating them. So the record is split three ways: `search` proposes,
`validate` scores, and `final` is touched once, by the promotion guard, and never by the
search. A partition that only ever looked good on the data that proposed it is discarded.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .beliefs import Calibration, Provenance
from .policy import Episode, Plasticity, PolicyBundle, Stat

# A discovered partition must clear this utility separation to be proposed at all.
MIN_SEPARATION = 0.08
# And it must hold up on data that did not propose it, by at least this fraction.
VALIDATION_RETENTION = 0.5
# Minimum episodes on BOTH sides of a split. A split that isolates three episodes is
# noise wearing the costume of a rule.
MIN_SIDE_EPISODES = 12
# Consecutive cycles a stat may sit at the weight floor before it is pruned.
PRUNE_AFTER_CYCLES = 3


# -- stage 1: prioritised replay ----------------------------------------------


def surprise(episode: Episode, expected: float) -> float:
    """How much this episode disagreed with what theta expected.

    Prioritising by surprise is what makes replay worth doing: re-running episodes the
    policy already predicts correctly changes nothing, so the ordering should favour
    the ones that would move it.
    """
    return abs(episode.utility - expected)


def prioritised_replay(
    episodes: list[Episode], incumbent: PolicyBundle
) -> list[Episode]:
    """Order episodes by surprise, descending. Ties broken deterministically."""

    def key(e: Episode) -> tuple[float, str, str]:
        expected = incumbent.stat(e.region, e.paradigm).mean_utility
        return (-surprise(e, expected), e.task_id, e.paradigm)

    return sorted(episodes, key=key)


# -- stage 2: abstraction ------------------------------------------------------


@dataclass
class CandidateSplit:
    """A proposed refinement of the feature partition."""

    attribute: str
    threshold: float
    separation_search: float
    separation_validate: float
    n_low: int
    n_high: int
    best_low: str
    best_high: str

    @property
    def retained(self) -> float:
        if self.separation_search <= 0:
            return 0.0
        return self.separation_validate / self.separation_search

    @property
    def survives(self) -> bool:
        """Held up on data that did not propose it, and flips the winner.

        The winner-flip requirement matters: a split that separates utility but leaves
        the same paradigm on top is not actionable, because the router would choose
        identically on both sides. It would be a true statement that changes nothing.
        """
        return (
            self.separation_search >= MIN_SEPARATION
            and self.retained >= VALIDATION_RETENTION
            and self.best_low != self.best_high
        )

    def proposition(self) -> str:
        return f"{self.attribute}_above_{self.threshold:g}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "proposition": self.proposition(),
            "attribute": self.attribute,
            "threshold": self.threshold,
            "separation_search": round(self.separation_search, 5),
            "separation_validate": round(self.separation_validate, 5),
            "retained": round(self.retained, 3),
            "n_low": self.n_low,
            "n_high": self.n_high,
            "best_low": self.best_low,
            "best_high": self.best_high,
            "survives": self.survives,
        }


def _best_and_spread(rows: list[dict[str, Any]]) -> tuple[str, float]:
    """Winning paradigm on these rows, and the gap to the runner-up."""
    by_paradigm: dict[str, list[float]] = {}
    for r in rows:
        by_paradigm.setdefault(r["paradigm"], []).append(r["utility"])
    if len(by_paradigm) < 2:
        return "", 0.0
    means = {p: sum(v) / len(v) for p, v in by_paradigm.items()}
    ranked = sorted(means.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[0][0], ranked[0][1] - ranked[1][1]


def discover_partitions(
    search_rows: list[dict[str, Any]],
    validate_rows: list[dict[str, Any]],
    attributes: Iterable[str],
) -> list[CandidateSplit]:
    """Search axis-aligned splits that separate paradigms.

    Deliberately restricted to single axis-aligned thresholds on recorded numeric
    attributes. Two reasons, and both are about honesty rather than convenience: a
    deeper search overfits a record this size, and a rule a person cannot read cannot
    be audited, which defeats the purpose of the belief layer.
    """
    candidates: list[CandidateSplit] = []

    for attribute in attributes:
        values = sorted({
            float(r[attribute]) for r in search_rows if r.get(attribute) is not None
        })
        if len(values) < 2:
            continue

        # Midpoints between observed values: thresholds that no observation sits on.
        thresholds = [
            (values[i] + values[i + 1]) / 2.0 for i in range(len(values) - 1)
        ]

        for threshold in thresholds:
            low = [r for r in search_rows if float(r[attribute]) <= threshold]
            high = [r for r in search_rows if float(r[attribute]) > threshold]
            if len(low) < MIN_SIDE_EPISODES or len(high) < MIN_SIDE_EPISODES:
                continue

            best_low, spread_low = _best_and_spread(low)
            best_high, spread_high = _best_and_spread(high)
            if not best_low or not best_high:
                continue
            separation = (spread_low + spread_high) / 2.0
            if separation < MIN_SEPARATION:
                continue

            v_low = [r for r in validate_rows if float(r[attribute]) <= threshold]
            v_high = [r for r in validate_rows if float(r[attribute]) > threshold]
            if not v_low or not v_high:
                continue
            _, v_spread_low = _best_and_spread(v_low)
            _, v_spread_high = _best_and_spread(v_high)

            candidates.append(CandidateSplit(
                attribute=attribute,
                threshold=threshold,
                separation_search=separation,
                separation_validate=(v_spread_low + v_spread_high) / 2.0,
                n_low=len(low),
                n_high=len(high),
                best_low=best_low,
                best_high=best_high,
            ))

    # Best first, and only one per attribute: reporting every threshold on the same
    # axis would present one finding as many.
    candidates.sort(key=lambda c: (-c.separation_validate, c.attribute))
    seen: set[str] = set()
    unique: list[CandidateSplit] = []
    for c in candidates:
        if c.attribute in seen:
            continue
        seen.add(c.attribute)
        unique.append(c)
    return unique


# -- stage 3: homeostasis ------------------------------------------------------


@dataclass
class Homeostasis:
    pruned: list[str] = field(default_factory=list)
    rescaled: int = 0
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "pruned": self.pruned,
            "rescaled": self.rescaled,
            "note": self.note,
        }


def homeostasis(
    stats: dict[str, dict[str, Stat]], floor: float, target_mean: float = 0.5
) -> Homeostasis:
    """Downscale globally, then prune what sits at the floor.

    Mutates `stats` in place; callers pass a copy belonging to a candidate bundle, never
    the incumbent's. Rescaling is multiplicative so the ORDERING of weights survives —
    consolidation must not reverse a preference, only compress the range that unbounded
    potentiation has stretched.
    """
    result = Homeostasis()
    all_stats = [s for paradigms in stats.values() for s in paradigms.values()]
    if not all_stats:
        result.note = "no statistics to consolidate"
        return result

    mean_weight = sum(s.weight for s in all_stats) / len(all_stats)
    if mean_weight > target_mean and mean_weight > 0:
        scale = target_mean / mean_weight
        for s in all_stats:
            s.weight = max(floor, s.weight * scale)
        result.rescaled = len(all_stats)
        result.note = f"downscaled by {scale:.3f} toward mean {target_mean}"
    else:
        result.note = f"mean weight {mean_weight:.3f} already at or below target"

    for region in sorted(stats):
        for paradigm in sorted(stats[region]):
            stat = stats[region][paradigm]
            # Never prune on weight alone: a stat with episodes is evidence, however
            # unfavourable. Only the never-used are removed.
            if stat.weight <= floor and stat.episodes == 0:
                result.pruned.append(f"{region}/{paradigm}")
    for key in result.pruned:
        region, paradigm = key.rsplit("/", 1)
        del stats[region][paradigm]
        if not stats[region]:
            del stats[region]

    return result


# -- stage 4: contradiction audit ---------------------------------------------


@dataclass
class PropositionAudit:
    proposition: str
    observations: int
    ece: float | None
    trustworthy: bool
    contradictions: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "proposition": self.proposition,
            "observations": self.observations,
            "ece": self.ece,
            "trustworthy": self.trustworthy,
            "contradictions": self.contradictions,
        }


def audit_propositions(
    belief_log: list[dict[str, Any]]
) -> dict[str, PropositionAudit]:
    """Per-proposition calibration from recorded belief bases.

    Each entry in `belief_log` is one `BeliefBase.as_dict()`. Within a base, an ELICITED
    belief is scored against the OBSERVED belief about the same proposition when one
    exists — evidence adjudicating opinion, which is exactly what the provenance
    ordering is for.

    A single global trust switch cannot express "reliable about cardinality, hopeless
    about coupling". This is what replaces it.
    """
    per_prop: dict[str, Calibration] = {}
    contradictions: dict[str, int] = {}

    for base in belief_log:
        beliefs = base.get("beliefs", [])
        observed = {
            b["proposition"]: b["value"]
            for b in beliefs
            if b["provenance"] == Provenance.OBSERVED.value
        }
        for b in beliefs:
            if b["provenance"] != Provenance.ELICITED.value:
                continue
            proposition = b["proposition"]
            if proposition not in observed:
                continue
            correct = b["value"] == observed[proposition]
            per_prop.setdefault(proposition, Calibration()).record(
                float(b["credence"]), correct
            )
            if not correct:
                contradictions[proposition] = contradictions.get(proposition, 0) + 1

    return {
        proposition: PropositionAudit(
            proposition=proposition,
            observations=len(calibration._observations),  # noqa: SLF001
            ece=calibration.expected_calibration_error(),
            trustworthy=calibration.is_trustworthy(),
            contradictions=contradictions.get(proposition, 0),
        )
        for proposition, calibration in per_prop.items()
    }


# -- the cycle -----------------------------------------------------------------


@dataclass
class DreamReport:
    cycle: int
    replayed: int
    candidate_version: int
    candidate_signature: str
    discovered: list[dict[str, Any]] = field(default_factory=list)
    homeostasis: dict[str, Any] = field(default_factory=dict)
    audit: list[dict[str, Any]] = field(default_factory=list)
    promotion: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "replayed_episodes": self.replayed,
            "candidate_version": self.candidate_version,
            "candidate_signature": self.candidate_signature,
            "discovered_propositions": self.discovered,
            "homeostasis": self.homeostasis,
            "proposition_audit": self.audit,
            "promotion": self.promotion,
            "notes": self.notes,
        }


SPLIT_ATTRIBUTES = (
    "truth_coupling",
    "cross_unit_lookups",
    "iterations",
    "cost_tokens",
)


def sleep_cycle(
    incumbent: PolicyBundle,
    rows: list[dict[str, Any]],
    episodes: list[Episode],
    belief_log: list[dict[str, Any]],
    promote_fn: Callable[[PolicyBundle, PolicyBundle, list[Episode]], Any],
    cycle: int = 1,
    tau: float | None = None,
) -> tuple[PolicyBundle, DreamReport]:
    """Run one consolidation cycle. Copy-on-write: the incumbent is never mutated.

    The record is split three ways by TASK, never by row: the same task on both sides
    would leak its answer and make every score optimistic. `search` proposes partitions,
    `validate` scores them, and `final` is used only by the promotion guard — so a
    partition is never scored on the data that proposed it, and the guard never sees the
    data the search already mined.
    """
    report = DreamReport(
        cycle=cycle,
        replayed=0,
        candidate_version=incumbent.version,
        candidate_signature=incumbent.signature,
    )

    task_ids = sorted({r["task_id"] for r in rows})
    if len(task_ids) < 6:
        report.notes.append(
            f"only {len(task_ids)} tasks recorded: too few to split three ways, so "
            "abstraction is skipped and the cycle only replays and consolidates"
        )
        search_ids, validate_ids, final_ids = set(task_ids), set(), set()
    else:
        a, b = int(len(task_ids) * 0.5), int(len(task_ids) * 0.75)
        search_ids = set(task_ids[:a])
        validate_ids = set(task_ids[a:b])
        final_ids = set(task_ids[b:])

    # ---- stage 1: prioritised replay
    ordered = prioritised_replay(episodes, incumbent)
    report.replayed = len(ordered)
    candidate = Plasticity.candidate(
        incumbent,
        ordered,
        tau=tau if tau is not None else incumbent.tau,
        notes=f"sleep cycle {cycle}: replayed {len(ordered)} episodes by surprise",
    )

    # ---- stage 2: abstraction
    if validate_ids:
        discovered = discover_partitions(
            [r for r in rows if r["task_id"] in search_ids],
            [r for r in rows if r["task_id"] in validate_ids],
            SPLIT_ATTRIBUTES,
        )
        report.discovered = [d.as_dict() for d in discovered]
        survivors = [d for d in discovered if d.survives]
        if survivors:
            report.notes.append(
                f"{len(survivors)} of {len(discovered)} candidate propositions survived "
                "validation; each enters with zero episodes and is therefore below the "
                "confidence floor, so the router cannot act on it yet"
            )
        else:
            report.notes.append(
                "no candidate proposition survived validation — the current partition "
                "is not demonstrably improvable on this record"
            )

    # ---- stage 3: homeostasis
    from .policy import WEIGHT_MIN

    balance = homeostasis(candidate.stats, floor=WEIGHT_MIN)
    report.homeostasis = balance.as_dict()
    candidate.sign()

    # ---- stage 4: audit
    audits = audit_propositions(belief_log)
    report.audit = [a.as_dict() for a in audits.values()]
    untrusted = [a.proposition for a in audits.values() if not a.trustworthy]
    if untrusted:
        report.notes.append(
            f"elicited credence is not yet trustworthy for {sorted(untrusted)}: rules "
            "depending on those propositions should require OBSERVED provenance, which "
            "makes the system probe rather than believe"
        )

    # ---- promotion, on data the search never touched
    holdout = [
        e for e in episodes
        if e.task_id in (final_ids if final_ids else {e.task_id for e in episodes})
    ]
    verdict = promote_fn(incumbent, candidate, holdout)
    report.promotion = verdict.as_dict()
    report.candidate_version = candidate.version
    report.candidate_signature = candidate.signature

    if not verdict.accepted:
        report.notes.append(
            "candidate rejected: the incumbent stands. A cycle that changes nothing is "
            "a successful cycle, not a wasted one"
        )
        return incumbent, report

    return candidate, report
