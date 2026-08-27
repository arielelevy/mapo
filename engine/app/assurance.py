"""Assurance as a per-request dial, not a system-wide mode.

WHAT THIS CORRECTS.

An earlier version of this harness had a global determinism ladder: the whole system
ran at D0, D1, D2 or D3. That was the wrong shape. Pure determinism is rarely needed —
most requests want the system's full flexibility, online plasticity, and the cheapest
pattern that works. A global mode forces every request to pay for the strictest one.

So assurance becomes a property OF THE REQUEST. The default sits at the flexible end
and strictness is an escalation, priced and requested, not a permanent posture.

THE CENTRAL RELATION. An assurance level constrains the admissible plan space:

    A0 EXPLORATORY   full algebra, any composition. theta learns online. Elicited
                     beliefs trusted. Nothing is logged for audit. Cheapest, most
                     capable, unreproducible — correct for research and for
                     low-stakes traffic, which is most traffic.

    A1 STANDARD      theta frozen for the session so behaviour is stable within it.
                     Elicited beliefs still trusted. Catalogued patterns only.
                     The sensible production default.

    A2 ACCOUNTABLE   elicited beliefs admissible only once calibrated. Every decision
                     records its belief base and rule trace. Composition depth capped
                     so a plan stays explainable. Costs coverage: some requests that
                     A1 would specialise now defer.

    A3 CERTIFIED     COMPUTED and OBSERVED provenance only. theta pinned AND signed.
                     Replay sealed from cache. Plans restricted to a certified subset.
                     Expensive and narrow. Correct for the irreversible and the
                     regulated, wrong for everything else.

PLASTICITY LIVES INSIDE THE LEVEL. The system permutes patterns freely within the
admissible set and keeps learning; what the assurance level changes is the size of
that set and whether the learning is allowed to move during the request. Plasticity
and assurance are therefore orthogonal knobs rather than opposites, which is the point
that the global-mode design obscured.

AND THE LEVEL ITSELF IS DECIDED FROM BELIEFS. An irreversible action raises the floor
on its own; a caller may request more but never less than the floor its beliefs imply.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from .beliefs import BeliefBase, Provenance


class Assurance(IntEnum):
    """Ordered so `max()` composes floors and requests correctly."""

    EXPLORATORY = 0
    STANDARD = 1
    ACCOUNTABLE = 2
    CERTIFIED = 3

    @property
    def label(self) -> str:
        return f"A{int(self)}_{self.name}"


# Patterns admissible at A3. Restricted to those whose control flow is bounded and
# whose failure modes are enumerable: no unbounded loop, no replan, no emergent
# blackboard. This is a claim about certifiability, not about quality — the excluded
# patterns are often better, which is exactly why A3 is an escalation and not a default.
CERTIFIED_PATTERNS = frozenset({
    "direct",
    "cot",
    "map_reduce",
    "react",
})


@dataclass(frozen=True)
class AssuranceProfile:
    """What a level actually permits. Data, so it can be reviewed and signed."""

    level: Assurance
    derived_floor: Provenance
    theta_may_learn_online: bool
    require_signed_theta: bool
    seal_replay: bool
    log_belief_base: bool
    admissible_patterns: frozenset[str] | None
    max_composition_depth: int

    def permits(self, pattern: str) -> bool:
        return self.admissible_patterns is None or pattern in self.admissible_patterns

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.label,
            "derived_floor": self.derived_floor.value,
            "theta_may_learn_online": self.theta_may_learn_online,
            "require_signed_theta": self.require_signed_theta,
            "seal_replay": self.seal_replay,
            "log_belief_base": self.log_belief_base,
            "admissible_patterns": (
                sorted(self.admissible_patterns) if self.admissible_patterns else "all"
            ),
            "max_composition_depth": self.max_composition_depth,
        }


PROFILES: dict[Assurance, AssuranceProfile] = {
    Assurance.EXPLORATORY: AssuranceProfile(
        level=Assurance.EXPLORATORY,
        derived_floor=Provenance.ASSUMED,
        theta_may_learn_online=True,
        require_signed_theta=False,
        seal_replay=False,
        log_belief_base=False,
        admissible_patterns=None,
        max_composition_depth=8,
    ),
    Assurance.STANDARD: AssuranceProfile(
        level=Assurance.STANDARD,
        derived_floor=Provenance.ELICITED,
        theta_may_learn_online=False,
        require_signed_theta=False,
        seal_replay=False,
        log_belief_base=False,
        admissible_patterns=None,
        max_composition_depth=5,
    ),
    Assurance.ACCOUNTABLE: AssuranceProfile(
        level=Assurance.ACCOUNTABLE,
        derived_floor=Provenance.ELICITED,  # admissible, but only once calibrated
        theta_may_learn_online=False,
        require_signed_theta=True,
        seal_replay=False,
        log_belief_base=True,
        admissible_patterns=None,
        max_composition_depth=3,
    ),
    Assurance.CERTIFIED: AssuranceProfile(
        level=Assurance.CERTIFIED,
        derived_floor=Provenance.OBSERVED,
        theta_may_learn_online=False,
        require_signed_theta=True,
        seal_replay=True,
        log_belief_base=True,
        admissible_patterns=CERTIFIED_PATTERNS,
        max_composition_depth=2,
    ),
}


@dataclass
class AssuranceDecision:
    """The level chosen, the floor that forced it, and why."""

    level: Assurance
    profile: AssuranceProfile
    requested: Assurance
    floor: Assurance
    reasons: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.label,
            "requested": self.requested.label,
            "belief_floor": self.floor.label,
            "reasons": self.reasons,
            "profile": self.profile.as_dict(),
        }


def required_floor(base: BeliefBase) -> tuple[Assurance, list[str]]:
    """The minimum assurance the beliefs about this request imply.

    A caller may ask for more. A caller may never get less: the floor exists so a
    cheap default cannot be applied to a request whose own properties forbid it.
    """
    floor = Assurance.EXPLORATORY
    reasons: list[str] = []

    if base.value("irreversible") is True:
        floor = max(floor, Assurance.CERTIFIED)
        reasons.append(
            "irreversible action: certified assurance is the floor, because an "
            "unreproducible decision cannot be defended after the fact"
        )

    if base.value("shared_writes") is True:
        floor = max(floor, Assurance.ACCOUNTABLE)
        reasons.append(
            "writes shared state: a decision that mutates state others depend on has "
            "to be reconstructable"
        )

    if base.value("regulated") is True:
        floor = max(floor, Assurance.CERTIFIED)
        reasons.append("request is flagged regulated")

    if not reasons:
        reasons.append("no belief raises the floor above exploratory")

    return floor, reasons


def resolve(
    base: BeliefBase,
    requested: Assurance = Assurance.STANDARD,
    calibration_trustworthy: bool = False,
) -> AssuranceDecision:
    """Pick the operating level for one request.

    `calibration_trustworthy` is threaded in rather than assumed because an ACCOUNTABLE
    profile nominally admits elicited beliefs, but admitting them while their stated
    confidence is unverified would defeat the level's purpose. When calibration has not
    been earned, the effective floor rises to OBSERVED even at A2.
    """
    floor, reasons = required_floor(base)
    level = max(requested, floor)
    profile = PROFILES[level]

    if (
        profile.derived_floor is Provenance.ELICITED
        and level >= Assurance.ACCOUNTABLE
        and not calibration_trustworthy
    ):
        profile = AssuranceProfile(
            level=profile.level,
            derived_floor=Provenance.OBSERVED,
            theta_may_learn_online=profile.theta_may_learn_online,
            require_signed_theta=profile.require_signed_theta,
            seal_replay=profile.seal_replay,
            log_belief_base=profile.log_belief_base,
            admissible_patterns=profile.admissible_patterns,
            max_composition_depth=profile.max_composition_depth,
        )
        reasons.append(
            "elicited credence is not yet calibrated, so at this level the provenance "
            "floor rises to observed and the system probes instead of trusting"
        )

    if requested > floor:
        reasons.append(f"caller requested {requested.label}, above the belief floor")

    return AssuranceDecision(
        level=level,
        profile=profile,
        requested=requested,
        floor=floor,
        reasons=reasons,
    )


def restrict(patterns: list[str], profile: AssuranceProfile) -> tuple[list[str], list[str]]:
    """Split candidate patterns into admissible and excluded under a profile.

    Excluded patterns are returned rather than silently dropped: a plan space that was
    narrowed has to say so, or a report reads as if the full space had been considered.
    """
    admissible = [p for p in patterns if profile.permits(p)]
    excluded = [p for p in patterns if not profile.permits(p)]
    return admissible, excluded
