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
    demands_exhaustive  bool   la celda declara cobertura total     COMPUTED
    has_oracle          bool   a cheap failure detector exists      COMPUTED
    irreversible        bool   the task commits an unsafe action    COMPUTED
    shared_writes       bool   units write shared state             COMPUTED
    literal_absent      bool   el literal que cita la pregunta no
                               esta en ninguna unidad del alcance   COMPUTED
    coupling_tight      bool   sub-results depend on each other     ELICITED or OBSERVED
    horizon_unknown     bool   step count not knowable in advance   ELICITED or OBSERVED
    best_paradigm       str    what theta says wins in this region  COMPUTED from theta
    theta_margin        float  size of theta's margin (vs tau)      COMPUTED from theta
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .features import has_runtime_detector
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

# El umbral de credencia sobre el acoplamiento, en UN solo lugar.
#
# POR QUE. La regla de sonda decidia "ya esta medido" con umbral 0,0 y la de especializar
# exigia 0,7. Entre los dos habia una ZONA MUERTA: una observacion de credencia 0,3
# suprimia la sonda —porque 0,3 > 0,0— y no alcanzaba para especializar —porque
# 0,3 < 0,7—. El request quedaba sin sondear y sin especializar, o sea peor que si el
# acoplamiento no se hubiera estimado nunca.
#
# Dos reglas que hablan de la misma proposicion y usan umbrales distintos no estan
# afinadas distinto: estan en desacuerdo sobre que significa "conocido".
COUPLING_CREDENCE_FLOOR = 0.7

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
                        min_credence=COUPLING_CREDENCE_FLOOR,
                        min_provenance=derived_floor,
                    ),
                ],
            ),
        ],
    )


# CREDENCIA DE UNA ESTIMACION ELICITADA SIN CONFIANZA DECLARADA.
#
# El extractor pide `{"coupling": float, "horizon_unknown": bool}` y NO pide una
# confianza, asi que el llamador tenia que poner una. Estaba puesta a mano —`0.8`— en el
# unico sitio que la usaba, que es la version silenciosa de inventar un numero.
#
# Se declara acá, con nombre, y con la unica cosa que la vuelve legitima: NO es una
# medicion, es un PRIOR, y existe exactamente la maquinaria para desmentirlo. La
# calibracion por proposicion mide si la credencia elicitada predice acierto, y
# `trusts_elicited` decide si se le permite gobernar. Un prior que su propia capa puede
# refutar no es lo mismo que un numero suelto.
ELICITED_PRIOR_CREDENCE = 0.8


def sense(
    task: dict[str, Any],
    policy: BeliefPolicy,
    theta_best: str | None = None,
    theta_confidence: float = 0.0,
    coupling: float | None = None,
    coupling_provenance: Provenance = Provenance.ELICITED,
    coupling_credence: float = 0.0,
    # EL LITERAL, COMO CREENCIA Y NO COMO DATO SUELTO (EP-4, 2026-08-30). Ver el bloque
    # donde se asienta, más abajo.
    literal: str | None = None,
    horizon_unknown: bool | None = None,
    horizon_provenance: Provenance = Provenance.ELICITED,
    horizon_credence: float = 0.0,
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
    # LA DEMANDA DE COBERTURA, y es del REQUEST, no del material. Viene declarada por
    # celda (`REQUEST_DEMANDS`) y NO se infiere de la prosa del enunciado: inferir «esta
    # pregunta pide todo» leyendo el texto es el parseo de prosa que no se acepta.
    #
    # AUSENTE NO ES `sufficient`. Un corpus anterior a `REQUEST_DEMANDS` no declara el eje,
    # y ahi la creencia NO se asienta: caer al valor laxo le regalaria la precondicion mas
    # facil justo a las tareas de las que menos se sabe.
    demanded = task.get("coverage_demanded")
    if demanded:
        base.assert_(Belief(
            proposition="demands_exhaustive",
            value=demanded == "exhaustive",
            credence=1.0,
            provenance=Provenance.COMPUTED,
            evidence=f"la celda declara coverage_demanded={demanded!r}",
        ))

    # ESTA es la que la cascada lee. La del segmento de region es la otra mitad, y las
    # dos salen de la misma funcion a proposito: eran la misma idea escrita dos veces.
    detector = has_runtime_detector(task)
    base.assert_(Belief(
        proposition="has_oracle",
        value=detector,
        credence=1.0,
        provenance=Provenance.COMPUTED,
        evidence="a cheap runtime detector is declared for this task" if detector
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
    # EL LITERAL DE LA PREGUNTA, COMO CREENCIA (EP-4, 2026-08-30)
    #
    # `measure_question_literal` ya existía y su valor ya entraba a la región, pero **no
    # estaba en el vocabulario de proposiciones**: ninguna regla podía razonar sobre él.
    # Tener la pieza no es tener el ciclo.
    #
    # ES `COMPUTED`, y ahí está lo que lo hace valioso: se establece por contención de una
    # cadena conocida contra el material —aritmética, sin modelo en el medio— así que
    # **satisface el piso más alto que cualquier regla puede pedir**, incluido el de una
    # acción irreversible. Es la misma clase que `term_absence` de `contracts.py`, que es de
    # donde salió: una creencia que no se podía establecer por el camino caro —leer el
    # dominio entero, insatisfacible en 9 de 9 tareas de `B2`— y que se establece barata.
    #
    #     Esto es exactamente lo que el producto promete: si falta una variable, ir a
    #     buscarla — y traerla con la procedencia más fuerte que hay, no con la del modelo.
    #
    # Se asienta y NINGUNA REGLA LA USA TODAVÍA. Es deliberado: agregar una creencia no
    # cambia comportamiento, agregar una regla sí, y una regla que cambia el ruteo se mide
    # antes de adoptarse. Lo que esto habilita hoy es que el descubrimiento de particiones
    # y el EXPLAIN la vean.
    if literal is not None:
        base.assert_(Belief(
            proposition="literal_absent",
            value=(literal == "lit_absent"),
            credence=1.0,
            provenance=Provenance.COMPUTED,
            evidence=(
                f"el literal que cita la pregunta {'NO aparece' if literal == 'lit_absent' else 'aparece'} "
                f"en ninguna unidad del alcance"
                if literal in ("lit_absent", "lit_present")
                else f"la pregunta no cita un literal verificable ({literal})"
            ),
        ))

    measured = base.satisfies(
        "coupling_tight", COUPLING_CREDENCE_FLOOR, policy.derived_floor
    )
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

    # EVIDENCIA PROPIA, Y ESA ES LA CORRECCION. `horizon_unknown` llevaba la credencia
    # Y la procedencia de `coupling` — el propio texto lo decia: «estimated alongside
    # coupling». Dos consecuencias, y la segunda es una violacion del reticulo:
    #
    # (1) El horizonte no tenia evidencia propia. La calibracion es POR PROPOSICION
    #     justamente porque un modelo puede ser confiable sobre una cosa y pesimo sobre
    #     otra, y compartir credencia hace esa distincion inexpresable.
    #
    # (2) Peor: tras una sonda, `coupling_provenance` es OBSERVED — y el horizonte lo
    #     heredaba. Asi que una proposicion que NADIE midio alcanzaba el piso que las
    #     acciones irreversibles exigen. La sonda lee una unidad para testear
    #     ACOPLAMIENTO; no toca el horizonte y no puede promoverlo.
    #
    # Ahora el horizonte declara lo suyo, y quien lo estima dice a que procedencia.
    if horizon_unknown is not None and horizon_credence > 0.0:
        base.assert_(Belief(
            proposition="horizon_unknown",
            value=horizon_unknown,
            credence=horizon_credence,
            provenance=horizon_provenance,
            evidence=f"horizonte estimado a {horizon_provenance.value}",
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
