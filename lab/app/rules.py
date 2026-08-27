"""The standard rule set, and the sensors that populate a belief base.

The routing logic that used to be an if/elif chain in `router.py` lives here as DATA.
That matters for three reasons beyond tidiness:

1. It can be serialised, diffed, signed and reviewed by someone who does not read
   Python — which is the actual requirement in a regulated deployment.
2. Rule order is explicit (priority), so precedence is a declared property rather than
   an accident of how the code was written.
3. Every rule states its epistemic preconditions, so "why did it do that" is answered
   by the trace instead of by reading the source.

PROPOSITION VOCABULARY. Kept small on purpose: a large vocabulary cannot accumulate
enough evidence per proposition to calibrate.

    n_units             int    how many independent work units      COMPUTED
    is_bulk             bool   n_units > 8                          COMPUTED
    has_oracle          bool   a cheap failure detector exists      COMPUTED
    irreversible        bool   the task commits an unsafe action    COMPUTED
    shared_writes       bool   units write shared state             COMPUTED
    coupling_tight      bool   sub-results depend on each other     ELICITED or OBSERVED
    horizon_unknown     bool   step count not knowable in advance   ELICITED or OBSERVED
    best_paradigm       str    what theta says wins in this region  COMPUTED from theta
    theta_margin        float  size of theta's margin (vs tau)      COMPUTED from theta
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .beliefs import (
    Belief,
    BeliefBase,
    Governance,
    Provenance,
    Requirement,
    Rule,
)

@dataclass(frozen=True)
class BeliefPolicy:
    """Shared configuration for the sensors and the rules.

    Both `sense` and `standard_rules` read the derived-provenance floor from here.
    They previously took it separately, and they drifted: the probe rule asked whether
    coupling was OBSERVED while the specialise rule was willing to accept ELICITED, so
    turning trust on changed one and not the other and the probe rule shadowed the
    specialise rule forever. A single source removes the possibility.

    The floor is a Provenance, not a boolean. A boolean has two states and there are
    four provenances, so the profiles could only ever project onto two of them: A0
    EXPLORATORY declares an ASSUMED floor -- LOOSER than elicited -- and encoding it as
    "does not trust elicited" turned the most permissive level into the STRICTEST one
    (OBSERVED), stricter than A1 and A2. The dial has to be able to say what it means.
    """

    derived_floor: Provenance
    tau: float

    @classmethod
    def from_trust(cls, trust_elicited: bool, tau: float) -> "BeliefPolicy":
        """The pre-profile pass, where the only thing known is whether elicited
        credence has earned trust. Once a profile is resolved, pass its floor directly.
        """
        return cls(
            derived_floor=(
                Provenance.ELICITED if trust_elicited else Provenance.OBSERVED
            ),
            tau=tau,
        )


ACTION_GATE = "gate_then_fallback"
ACTION_CASCADE = "cascade"
ACTION_PROBE = "probe_then_decide"
ACTION_SPECIALISE = "specialise"
ACTION_DEFER = "defer_to_fallback"

BULK_THRESHOLD = 8


def standard_rules(policy: BeliefPolicy) -> Governance:
    """The paper's decision logic, as rules.

    `policy.derived_floor` is the calibration dial. When elicited credence has not
    earned trust (see `beliefs.Calibration`), the floor is OBSERVED and rules that would
    act on a model-asserted belief force a probe rather than a guess. It is explicit
    because silently trusting an uncalibrated number is exactly the failure the belief
    layer exists to prevent -- and it is a provenance rather than a flag because A0
    deliberately sits BELOW elicited.
    """
    derived_floor = policy.derived_floor
    tau = policy.tau

    return Governance(
        default_action=ACTION_DEFER,
        rules=[
            Rule(
                name="irreversible_requires_gate",
                priority=100,
                then=ACTION_GATE,
                rationale=(
                    "An irreversible action is gated regardless of what the cost model "
                    "prefers. The requirement is COMPUTED-only: a model's opinion that "
                    "an action is safe is not admissible evidence for taking it."
                ),
                requires=[
                    Requirement(
                        proposition="irreversible",
                        expected=True,
                        min_credence=1.0,
                        min_provenance=Provenance.COMPUTED,
                    )
                ],
            ),
            Rule(
                name="verifiability_partition",
                priority=90,
                then=ACTION_CASCADE,
                rationale=(
                    "A cheap failure detector exists, so escalate on observed failure "
                    "rather than predicting which paradigm wins. Misrouting then costs "
                    "tokens instead of answer quality."
                ),
                requires=[
                    Requirement(
                        proposition="has_oracle",
                        expected=True,
                        min_credence=1.0,
                        min_provenance=Provenance.COMPUTED,
                    )
                ],
            ),
            Rule(
                name="probe_before_deciding_on_bulk",
                priority=80,
                then=ACTION_PROBE,
                rationale=(
                    "Many units and no trustworthy belief about coupling. Executing one "
                    "unit measures it, and that work was due anyway, so the probe costs "
                    "nothing that was not already owed."
                ),
                requires=[
                    Requirement(
                        proposition="is_bulk",
                        expected=True,
                        min_credence=1.0,
                        min_provenance=Provenance.COMPUTED,
                    ),
                    # Deliberately inverted: the rule fires when coupling is NOT yet
                    # believed at OBSERVED strength. Expressed as a requirement on the
                    # complementary proposition so it stays declarative.
                    Requirement(
                        proposition="coupling_unmeasured",
                        expected=True,
                        min_credence=1.0,
                        min_provenance=Provenance.COMPUTED,
                    ),
                ],
            ),
            Rule(
                name="specialise_when_theta_is_confident",
                priority=70,
                then=ACTION_SPECIALISE,
                rationale=(
                    "Learned statistics give a clear margin in this feature region, so "
                    "the specialised paradigm is inside the high-confidence region of "
                    "Theorem 1 and routing is expected to pay."
                ),
                requires=[
                    # A magnitude threshold, not a credence one: the margin is a fact
                    # computed from theta with certainty, and tau is how big that fact
                    # has to be before specialising is expected to pay.
                    Requirement(
                        proposition="theta_margin",
                        min_value=tau,
                        min_credence=1.0,
                        min_provenance=Provenance.COMPUTED,
                    ),
                ],
            ),
            Rule(
                name="specialise_on_tight_coupling",
                priority=60,
                then=ACTION_SPECIALISE,
                rationale=(
                    "Tight coupling is a structural reason to serialise, independent of "
                    "learned statistics. Requires OBSERVED provenance unless elicited "
                    "credence has been calibrated."
                ),
                requires=[
                    Requirement(
                        proposition="coupling_tight",
                        expected=True,
                        min_credence=0.7,
                        min_provenance=derived_floor,
                    ),
                ],
            ),
        ],
    )


def sense(
    task: dict[str, Any],
    policy: BeliefPolicy,
    theta_best: str | None = None,
    theta_confidence: float = 0.0,
    coupling: float | None = None,
    coupling_provenance: Provenance = Provenance.ELICITED,
    coupling_credence: float = 0.0,
    horizon_unknown: bool | None = None,
    base: BeliefBase | None = None,
) -> BeliefBase:
    """Populate a belief base from a task and whatever else is known.

    The computed beliefs are asserted unconditionally because they are functions of
    the payload. The derived ones are asserted only when something actually supports
    them: asserting a belief with credence 0 would let a rule see a proposition that
    nothing backs.

    `base` continues an existing history instead of opening a fresh one: a request
    that was sensed, probed, and sensed again is ONE epistemic story, and the digest
    must cover all of it. Supersession comes free from `current()` — an OBSERVED
    probe result outranks the ELICITED estimate it replaces, and recency breaks ties.
    """
    base = base if base is not None else BeliefBase()
    units = task.get("unit_ids") or []
    n_units = len(units) if units else 1

    base.assert_(Belief(
        proposition="n_units",
        value=n_units,
        credence=1.0,
        provenance=Provenance.COMPUTED,
        evidence=f"counted {n_units} unit ids in the task payload",
    ))
    base.assert_(Belief(
        proposition="is_bulk",
        value=n_units > BULK_THRESHOLD,
        credence=1.0,
        provenance=Provenance.COMPUTED,
        evidence=f"n_units={n_units} vs threshold {BULK_THRESHOLD}",
    ))
    base.assert_(Belief(
        proposition="has_oracle",
        value=bool(task.get("oracle")),
        credence=1.0,
        provenance=Provenance.COMPUTED,
        evidence="task carries an exact-match oracle" if task.get("oracle")
                 else "no cheap failure detector available",
    ))
    base.assert_(Belief(
        proposition="irreversible",
        value=bool(task.get("irreversible", False)),
        credence=1.0,
        provenance=Provenance.COMPUTED,
        evidence="declared on the task",
    ))
    base.assert_(Belief(
        proposition="shared_writes",
        value=bool(task.get("shared_writes", False)),
        credence=1.0,
        provenance=Provenance.COMPUTED,
        evidence="declared on the task",
    ))
    base.assert_(Belief(
        proposition="regulated",
        value=bool(task.get("regulated", False)),
        credence=1.0,
        provenance=Provenance.COMPUTED,
        evidence="declared on the task",
    ))

    if coupling is not None and coupling_credence > 0.0:
        base.assert_(Belief(
            proposition="coupling_tight",
            value=coupling >= 0.66,
            credence=coupling_credence,
            provenance=coupling_provenance,
            evidence=(
                f"coupling estimate {coupling:.2f} via {coupling_provenance.value}"
            ),
        ))

    # The complement is itself a computed fact about the belief base: either something
    # measured coupling or nothing did. Making it explicit keeps the probe rule
    # declarative instead of hiding a negation inside the engine.
    # "Unmeasured" means: no belief about coupling at the provenance floor the RULES
    # will accept. Reading the floor from the shared policy is what keeps the probe
    # rule and the specialise rule from disagreeing about what counts as known.
    measured = base.satisfies("coupling_tight", 0.0, policy.derived_floor)
    base.assert_(Belief(
        proposition="coupling_unmeasured",
        value=not measured,
        credence=1.0,
        provenance=Provenance.COMPUTED,
        evidence=(
            f"no belief about coupling at or above {policy.derived_floor.value}"
            if not measured
            else f"coupling known at {base.provenance('coupling_tight').value}"
        ),
    ))

    # Asserted only when the same estimate that produced coupling actually carries
    # credence. `coupling_credence or 0.5` invented a number out of nothing: a latent
    # belief nothing backs, at exactly the strength that decides rules.
    if horizon_unknown is not None and coupling_credence > 0.0:
        base.assert_(Belief(
            proposition="horizon_unknown",
            value=horizon_unknown,
            credence=coupling_credence,
            provenance=coupling_provenance,
            evidence="estimated alongside coupling",
        ))

    if theta_best:
        base.assert_(Belief(
            proposition="best_paradigm",
            value=theta_best,
            credence=1.0,
            provenance=Provenance.COMPUTED,
            evidence="argmax of learned mean utility in this feature region",
        ))
        base.assert_(Belief(
            proposition="theta_margin",
            value=theta_confidence,
            credence=1.0,
            provenance=Provenance.COMPUTED,
            evidence=(
                f"margin/evidence score {theta_confidence:.3f}, a deterministic "
                "function of the theta bundle"
            ),
        ))

    return base
