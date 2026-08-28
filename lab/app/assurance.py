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

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from .models import Capability
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
    # PISO DE CAPACIDAD DEL MODELO, y es una PRECONDICION, no presupuesto.
    #
    # «El presupuesto es token y calidad del modelo» (planteo del autor, 2026-08-28). La
    # calidad NO entra al costo: seria mezclar lo que se paga con lo que se compra, y
    # entonces un descuento suficiente compraria permiso para rutear una accion
    # irreversible al modelo mas barato. Entra como restriccion, y el lugar donde vive ya
    # existia: el dial ya restringe PATRONES, ahora restringe tambien MODELOS.
    #
    # `None` es «cualquier modelo del catalogo», que es distinto de un piso bajo: un
    # perfil que no opina no es un perfil que exige el minimo.
    min_capability: "Capability | None" = None

    def permits(self, pattern: str) -> bool:
        return self.admissible_patterns is None or pattern in self.admissible_patterns

    def permits_model(self, capability: "Capability") -> bool:
        """Si el dial admite un modelo de esa capacidad. Piso ORDINAL, no puntaje."""
        return self.min_capability is None or capability >= self.min_capability

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
            "min_capability": (
                self.min_capability.name if self.min_capability else "any"
            ),
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
        # A2 NO EXIGE PISO, y no exigirlo es una decision. Puse `DEEP` primero por el
        # argumento de «rinde cuentas» y es una politica mia sin una sola medicion detras:
        # obligaria a pagar 25x en cada request contable. Si el modelo barato alcanza a
        # este nivel de procedencia es una pregunta EMPIRICA, y esta registrada.
        min_capability=None,
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
        # ACA EL ARGUMENTO ES ESTRUCTURAL Y NO HACE FALTA MEDIRLO. `decide_level` ya
        # eleva a A3 toda accion irreversible («certified assurance is the floor»), asi
        # que este piso ES el que impide rutear lo irreversible al modelo mas barato
        # porque salga la cuenta. No se agrego mecanismo nuevo: se completo el que habia.
        min_capability=Capability.DEEP,
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


# --- the floor that learns (paper §6.2) ------------------------------------------
#
# A request class whose ELICITED assertions are repeatedly refused by the gate is a
# class where the model's opinions are not usable evidence. Saying that once, per
# request, is the gate doing its job. Saying it in nine requests out of ten in the same
# feature region is a fact ABOUT THE REGION, and consuming it raises the floor there
# so the system probes instead of asking and being refused.
#
# Why this is safe to learn: it never adjusts anything INSIDE a request. It is computed
# offline, from a record, and installed as data on a signed bundle — the same path θ
# takes, under a guard that requires the evidence to replicate on data the search never
# saw (see consolidation.learn_assurance_floors).
#
# Why the raise is capped at ACCOUNTABLE and never reaches CERTIFIED: CERTIFIED also
# restricts which PATTERNS may run, and a statistic about evidence quality is not
# evidence about certifiability. A floor that learns must not be able to silently
# disqualify topologies.
MIN_REQUESTS_PER_REGION = 8
MIN_REJECTION_RATE = 0.5
LEARNED_FLOOR_CEILING = Assurance.ACCOUNTABLE


@dataclass(frozen=True)
class RegionRejectionStats:
    """What the record says about one feature region."""

    region: str
    requests: int  # requests in this region that carried an elicited assertion
    rejected: int  # of those, how many had at least one refused by the gate

    @property
    def rate(self) -> float:
        return self.rejected / self.requests if self.requests else 0.0

    @property
    def qualifies(self) -> bool:
        return (
            self.requests >= MIN_REQUESTS_PER_REGION
            and self.rate >= MIN_REJECTION_RATE
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "requests": self.requests,
            "rejected": self.rejected,
            "rate": round(self.rate, 4),
            "qualifies": self.qualifies,
        }


def rejection_stats(records: Iterable[dict[str, Any]]) -> dict[str, RegionRejectionStats]:
    """Count, per region, how often the gate refused an elicited assertion.

    `records` are belief-log entries. The counting is over TYPED fields written by the
    governance layer (`context.gate_rejections`, produced from `beliefs.Rejection`),
    never over the human-readable reason: a statistic assembled by matching substrings
    of an explanation measures the explanation, and the explanations get reworded.
    """
    requests: dict[str, int] = {}
    rejected: dict[str, int] = {}
    for record in records:
        context = record.get("context") or {}
        region = context.get("region")
        if not region:
            continue
        # Only requests that actually offered an elicited belief can have one refused;
        # counting the rest would dilute the rate with requests that never asked.
        if not context.get("elicited_offered"):
            continue
        requests[region] = requests.get(region, 0) + 1
        if context.get("gate_rejections"):
            rejected[region] = rejected.get(region, 0) + 1
    return {
        region: RegionRejectionStats(
            region=region, requests=count, rejected=rejected.get(region, 0)
        )
        for region, count in requests.items()
    }


def learn_floors(
    records: Iterable[dict[str, Any]],
    incumbent: Mapping[str, Assurance] | None = None,
) -> tuple[dict[str, Assurance], list[str]]:
    """Regions whose floor the record says should rise, and why.

    Monotone by construction: a learned floor is only ever raised, never lowered. The
    evidence that RAISED it is a history of refusals; the absence of refusals afterwards
    is what the raised floor was supposed to produce, so reading that absence as grounds
    to lower it again would be a loop that oscillates by design.
    """
    floors: dict[str, Assurance] = dict(incumbent or {})
    notes: list[str] = []
    for region, stats in sorted(rejection_stats(records).items()):
        if not stats.qualifies:
            continue
        current = floors.get(region, Assurance.EXPLORATORY)
        raised = max(current, LEARNED_FLOOR_CEILING)
        if raised == current:
            continue
        floors[region] = raised
        notes.append(
            f"{region}: {stats.rejected}/{stats.requests} requests had an elicited "
            f"assertion refused by the gate ({stats.rate:.0%}) — floor raised to "
            f"{raised.label}"
        )
    return floors, notes


def required_floor(
    base: BeliefBase,
    learned: Mapping[str, Assurance] | None = None,
    region: str = "",
) -> tuple[Assurance, list[str]]:
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

    learned_floor = (learned or {}).get(region)
    if learned_floor is not None and learned_floor > floor:
        floor = learned_floor
        reasons.append(
            f"region {region}: elicited assertions here are repeatedly refused by the "
            f"gate, so the learned floor is {learned_floor.label} (paper §6.2)"
        )

    if not reasons:
        reasons.append("no belief raises the floor above exploratory")

    return floor, reasons


def resolve(
    base: BeliefBase,
    requested: Assurance = Assurance.STANDARD,
    calibration_trustworthy: bool = False,
    learned: Mapping[str, Assurance] | None = None,
    region: str = "",
) -> AssuranceDecision:
    """Pick the operating level for one request.

    `calibration_trustworthy` is threaded in rather than assumed because an ACCOUNTABLE
    profile nominally admits elicited beliefs, but admitting them while their stated
    confidence is unverified would defeat the level's purpose. When calibration has not
    been earned, the effective floor rises to OBSERVED even at A2.
    """
    floor, reasons = required_floor(base, learned=learned, region=region)
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
            min_capability=profile.min_capability,
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
