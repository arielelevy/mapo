"""The belief layer: the LLM as a sensor, symbolic rules as the decider.

WHY THIS REPLACED THE EARLIER DESIGN.

An earlier version of this harness chased determinism by keeping the model out of the
decision: features that needed an LLM were refused, and the router abstained. That was
wrong twice over. It threw away information the model genuinely has, and it framed the
LLM as a contaminant rather than as an instrument. Worse, it implied a guarantee that
cannot exist — an LLM is probabilistic, and no amount of pinning makes it otherwise.

The inversion: the LLM is a SENSOR that emits beliefs. A deterministic symbolic layer
reasons over the belief base and decides. The guarantee changes shape accordingly:

    NOT   "the same prompt yields the same answer"          (false, always)
    BUT   "the same belief base yields the same decision"    (true, and auditable)

and the belief base is a recorded artifact, so an auditor never has to replay the
model. They inspect what it asserted, with what confidence and on what evidence, and
they replay the rules over it.

PROVENANCE IS THE LOAD-BEARING FIELD. A belief is not just a value plus a number; what
matters for governance is how it was obtained:

    COMPUTED  a pure function of the payload. Credence 1.0 by construction.
    OBSERVED  measured by executing a probe. Evidence, not opinion.
    ELICITED  the model asserted it. Credence as stated, subject to calibration.
    ASSUMED   a prior, held only until something better arrives.

Rules may demand a minimum provenance. An irreversible action can require COMPUTED or
OBSERVED beliefs only, which is a governance gate expressed in epistemic terms rather
than as a special case in the routing code.

THE OPEN RISK, STATED UP FRONT. Elicited credences may be miscalibrated — a model that
says 0.8 and is right half the time is worse than useless, because the number invites
trust it has not earned. See `Calibration`: the harness measures the reliability
diagram rather than assuming it, and a rule may be configured to distrust elicited
credence entirely until calibration data exists.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


class Provenance(str, Enum):
    """How a belief was obtained, ordered by epistemic strength."""

    COMPUTED = "computed"
    OBSERVED = "observed"
    ELICITED = "elicited"
    ASSUMED = "assumed"

    @property
    def rank(self) -> int:
        return {
            Provenance.COMPUTED: 3,
            Provenance.OBSERVED: 2,
            Provenance.ELICITED: 1,
            Provenance.ASSUMED: 0,
        }[self]

    def at_least(self, floor: "Provenance") -> bool:
        return self.rank >= floor.rank


def admissible_for_action(belief: "Belief", floor: "Provenance") -> bool:
    """Si una creencia puede sostener una ACCION, no solo una estimacion.

    DOS CONDICIONES, y son independientes. La procedencia tiene que llegar al piso — eso
    es lo que ya se exigia — y el alcance tiene que ser **este request**. Un prior sobre
    la poblacion puede ser aritmetica perfecta y aun asi no ser evidencia sobre lo que
    esta por pasar: «en casos parecidos esto funciono» no es «acá esto es cierto».

    Es la unica forma de que una asociacion aprendida entre a la base con su procedencia
    honesta —`COMPUTED`, porque lo es— sin que eso la habilite a gatear lo irreversible.
    """
    return (
        belief.provenance.at_least(floor)
        and belief.scope is Scope.REQUEST
    )


class Scope(str, Enum):
    """SOBRE QUE es la creencia: este request, o la poblacion de requests parecidos.

    POR QUE HACE FALTA UN SEGUNDO EJE. `Provenance` ordena **como** se obtuvo una
    creencia, y ese orden alcanzaba mientras todo lo que entraba a la base fuera sobre el
    request de adelante. Una asociacion APRENDIDA rompe eso: es aritmetica exacta sobre un
    ledger —o sea que por procedencia *parece* `COMPUTED`— y sin embargo no dice nada
    sobre este pedido. Dice que en pedidos parecidos, antes, tal transicion acompaño al
    exito.

    Meterla como `COMPUTED` dejaria que una **regularidad estadistica gatee una accion
    irreversible**, que es exactamente lo que el piso existe para impedir. Meterla como
    `ELICITED` mentiria en el otro sentido: no es la opinion de un modelo, es una
    frecuencia medida y reproducible.

    El problema no era que faltara un casillero en la escala: era que la escala mide una
    cosa y hacian falta dos. Con el alcance separado, una asociacion aprendida se declara
    honesta en los dos ejes —`COMPUTED` sobre `POPULATION`— y queda estructuralmente fuera
    de lo irreversible sin necesidad de degradar su procedencia.
    """

    REQUEST = "request"
    POPULATION = "population"


class Rejection(str, Enum):
    """Why a requirement was not met — as a value, not as a sentence.

    The whole point of §6.2 is to consume rejection statistics, and a statistic built
    by matching substrings of an explanation measures the explanation. These are the
    five ways a requirement can fail, and they are distinguishable by construction.
    """

    ABSENT = "absent"  # nothing is believed about the proposition at all
    PROVENANCE = "provenance"  # believed, but not on strong enough evidence
    CREDENCE = "credence"  # believed on good evidence, but not confidently enough
    VALUE = "value"  # believed and confident, but the value is not the one required
    MAGNITUDE = "magnitude"  # the value is numeric and below the threshold


@dataclass(frozen=True)
class Check:
    """One requirement, evaluated. The reason is for humans; the rest is for counting."""

    proposition: str
    met: bool
    reason: str
    rejection: Rejection | None = None
    held: Provenance | None = None  # the provenance actually held
    needed: Provenance | None = None  # the provenance the rule demanded

    def as_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "proposition": self.proposition,
            "met": self.met,
            "reason": self.reason,
        }
        if self.rejection is not None:
            body["rejection"] = self.rejection.value
        if self.held is not None:
            body["held"] = self.held.value
        if self.needed is not None:
            body["needed"] = self.needed.value
        return body


@dataclass(frozen=True)
class Belief:
    """A typed proposition with a credence and a provenance.

    Frozen: a belief is a record of what was held at a point in time. Revising it
    means adding a new belief, never mutating the old one, so the audit trail keeps
    the superseded value.
    """

    proposition: str
    value: Any
    credence: float
    provenance: Provenance
    evidence: str = ""
    # SOBRE QUE es. Por defecto, sobre este request — que es lo que era todo hasta que
    # entraron las asociaciones aprendidas. Ver `Scope`.
    scope: Scope = Scope.REQUEST

    def __post_init__(self) -> None:
        if not 0.0 <= self.credence <= 1.0:
            raise ValueError(
                f"Credence for {self.proposition} must be in [0,1], got {self.credence}"
            )
        if self.provenance is Provenance.COMPUTED and self.credence != 1.0:
            # A computed belief with credence below 1 means the computation is not
            # actually a pure function of the payload, and the provenance is a lie.
            raise ValueError(
                f"{self.proposition} claims COMPUTED provenance but credence "
                f"{self.credence} != 1.0. Reclassify it as OBSERVED or ELICITED."
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "proposition": self.proposition,
            "value": self.value,
            "credence": round(self.credence, 5),
            "provenance": self.provenance.value,
            "evidence": self.evidence[:300],
        }


def belief_from_dict(raw: dict[str, Any]) -> Belief:
    """A Belief back from its recorded form.

    Needed so a request's SECOND decision can start from the history of its first: the
    plan records the base as dicts, and without this constructor the replan built a
    fresh base and the ELICITED->OBSERVED story was split across two objects with two
    digests and no lineage.
    """
    return Belief(
        proposition=str(raw["proposition"]),
        value=raw.get("value"),
        credence=float(raw["credence"]),
        provenance=Provenance(raw["provenance"]),
        evidence=str(raw.get("evidence", "")),
    )


class BeliefBase:
    """The set of beliefs a decision rests on, plus its own identity.

    Superseded beliefs are retained. The base is append-only so that `digest()`
    identifies the whole epistemic history of a decision, not just its final state.
    """

    def __init__(self) -> None:
        self._beliefs: list[Belief] = []

    @classmethod
    def from_dicts(cls, records: list[dict[str, Any]]) -> "BeliefBase":
        """Rebuild a base from recorded beliefs, order preserved (it is history)."""
        base = cls()
        for raw in records:
            base.assert_(belief_from_dict(raw))
        return base

    def assert_(self, belief: Belief) -> "BeliefBase":
        self._beliefs.append(belief)
        return self

    def all(self) -> list[Belief]:
        return list(self._beliefs)

    def current(self, proposition: str) -> Belief | None:
        """The strongest belief held about a proposition.

        Ordered by provenance first, then credence. A probe's observation therefore
        overrides a model's assertion even if the model claimed to be more confident,
        which is the correct precedence: evidence beats opinion.
        """
        candidates = [
            (i, b) for i, b in enumerate(self._beliefs) if b.proposition == proposition
        ]
        if not candidates:
            return None
        # Recency breaks ties. With equal provenance and equal credence the OLD belief
        # used to win (max keeps the first), so a re-measurement that produced the same
        # confidence could never supersede what it re-measured. Position in the
        # append-only history is the tiebreaker because it IS the order of knowing.
        return max(candidates, key=lambda ib: (ib[1].provenance.rank, ib[1].credence, ib[0]))[1]

    def value(self, proposition: str, default: Any = None) -> Any:
        belief = self.current(proposition)
        return default if belief is None else belief.value

    def credence(self, proposition: str) -> float:
        """Credence, or 0.0 for a proposition nothing is believed about.

        Absence of belief is zero confidence, never a neutral 0.5: a rule must not be
        able to fire on a proposition no one has any evidence about.
        """
        belief = self.current(proposition)
        return 0.0 if belief is None else belief.credence

    def provenance(self, proposition: str) -> Provenance:
        belief = self.current(proposition)
        return Provenance.ASSUMED if belief is None else belief.provenance

    def satisfies(
        self, proposition: str, min_credence: float, min_provenance: Provenance
    ) -> bool:
        belief = self.current(proposition)
        if belief is None:
            return False
        return (
            belief.credence >= min_credence
            and belief.provenance.at_least(min_provenance)
        )

    def digest(self) -> str:
        """Content hash of the belief base — the replay key.

        Two runs with the same digest must produce the same decision. This is the
        actual determinism guarantee, and it does not require the model to be
        deterministic.
        """
        blob = json.dumps(
            [b.as_dict() for b in self._beliefs], sort_keys=True, ensure_ascii=False
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            "digest": self.digest(),
            "beliefs": [b.as_dict() for b in self._beliefs],
            "provenance_mix": {
                p.value: sum(1 for b in self._beliefs if b.provenance is p)
                for p in Provenance
            },
        }

    def render(self) -> str:
        lines = [f"belief base {self.digest()[:16]}"]
        for b in self._beliefs:
            lines.append(
                f"  {b.proposition:<24} = {str(b.value):<12} "
                f"c={b.credence:.2f} [{b.provenance.value}] {b.evidence[:60]}"
            )
        return "\n".join(lines)


# -- governance rules ----------------------------------------------------------


@dataclass
class Requirement:
    """A precondition on the belief base, in epistemic terms.

    `min_credence` and `min_value` are different questions and must not be conflated.
    Credence is how sure we are that the proposition holds. `min_value` is a threshold
    on the proposition's magnitude. A learned statistic with a large margin is a
    CERTAIN belief about a LARGE effect — credence 1.0, value 0.9 — and encoding the
    effect size as credence would misreport a computed fact as an uncertain one.
    """

    proposition: str
    min_credence: float
    min_provenance: Provenance = Provenance.ASSUMED
    expected: Any = None
    min_value: float | None = None

    def met_by(self, base: BeliefBase) -> Check:
        belief = base.current(self.proposition)
        if belief is None:
            return Check(
                proposition=self.proposition,
                met=False,
                reason=f"nothing believed about {self.proposition}",
                rejection=Rejection.ABSENT,
                needed=self.min_provenance,
            )
        if not belief.provenance.at_least(self.min_provenance):
            return Check(
                proposition=self.proposition,
                met=False,
                reason=(
                    f"{self.proposition} is {belief.provenance.value}, "
                    f"rule needs at least {self.min_provenance.value}"
                ),
                rejection=Rejection.PROVENANCE,
                held=belief.provenance,
                needed=self.min_provenance,
            )
        if belief.credence < self.min_credence:
            return Check(
                proposition=self.proposition,
                met=False,
                reason=(
                    f"{self.proposition} credence {belief.credence:.2f} "
                    f"< required {self.min_credence:.2f}"
                ),
                rejection=Rejection.CREDENCE,
                held=belief.provenance,
                needed=self.min_provenance,
            )
        if self.expected is not None and belief.value != self.expected:
            return Check(
                proposition=self.proposition,
                met=False,
                reason=(
                    f"{self.proposition} is {belief.value!r}, "
                    f"rule needs {self.expected!r}"
                ),
                rejection=Rejection.VALUE,
                held=belief.provenance,
                needed=self.min_provenance,
            )
        if self.min_value is not None:
            try:
                magnitude = float(belief.value)
            except (TypeError, ValueError):
                return Check(
                    proposition=self.proposition,
                    met=False,
                    reason=(
                        f"{self.proposition} value {belief.value!r} is not numeric, "
                        "so a magnitude threshold cannot apply"
                    ),
                    rejection=Rejection.MAGNITUDE,
                    held=belief.provenance,
                    needed=self.min_provenance,
                )
            if magnitude < self.min_value:
                return Check(
                    proposition=self.proposition,
                    met=False,
                    reason=(
                        f"{self.proposition} = {magnitude:.3f} < "
                        f"required {self.min_value:.3f}"
                    ),
                    rejection=Rejection.MAGNITUDE,
                    held=belief.provenance,
                    needed=self.min_provenance,
                )
        return Check(
            proposition=self.proposition,
            met=True,
            reason="met",
            held=belief.provenance,
            needed=self.min_provenance,
        )


@dataclass
class Rule:
    """A named, deterministic implication over the belief base.

    Rules are data, not code branches, so the whole policy can be serialised,
    diffed, signed and read by someone who does not read Python.
    """

    name: str
    requires: list[Requirement]
    then: str
    rationale: str = ""
    priority: int = 0

    def evaluate(self, base: BeliefBase) -> tuple[bool, list[Check]]:
        checks = [requirement.met_by(base) for requirement in self.requires]
        return all(check.met for check in checks), checks

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "then": self.then,
            "priority": self.priority,
            "rationale": self.rationale,
            "requires": [
                {
                    "proposition": r.proposition,
                    "min_credence": r.min_credence,
                    "min_provenance": r.min_provenance.value,
                    "expected": r.expected,
                    "min_value": r.min_value,
                }
                for r in self.requires
            ],
        }


@dataclass
class Verdict:
    """What the governance layer decided, and everything it decided it from."""

    action: str
    fired_rule: str | None
    belief_digest: str
    trace: list[dict[str, Any]] = field(default_factory=list)
    beliefs: dict[str, Any] = field(default_factory=dict)
    # Every requirement that was not met, typed. This is the raw material §6.2 learns
    # from: which propositions the gate refuses, and on what grounds.
    rejections: list[Check] = field(default_factory=list)

    def gate_rejections(self, floor: Provenance = Provenance.OBSERVED) -> list[Check]:
        """Assertions refused because their PROVENANCE was below what a rule demanded.

        Narrow on purpose. A belief refused for low credence, or for holding the wrong
        value, says nothing about the evidence regime of this request class: it is the
        system working. A belief refused because a model asserted it and the rule would
        only act on something measured is exactly the event §6.2 counts.
        """
        return [
            check
            for check in self.rejections
            if check.rejection is Rejection.PROVENANCE
            and check.held is not None
            and not check.held.at_least(floor)
        ]

    def as_dict(self) -> dict[str, Any]:
        body = {
            "action": self.action,
            "fired_rule": self.fired_rule,
            "belief_digest": self.belief_digest,
            "trace": self.trace,
            "beliefs": self.beliefs,
            "gate_rejections": [c.as_dict() for c in self.gate_rejections()],
        }
        body["verdict_digest"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return body


class Governance:
    """Deterministic rule evaluation over a belief base.

    Pure: same belief base and same rule set, same verdict. The LLM's stochasticity
    lives entirely upstream, in how the beliefs came to be, and is recorded there.
    """

    def __init__(self, rules: Iterable[Rule], default_action: str) -> None:
        # Sorted once, descending priority then name, so evaluation order is total and
        # does not depend on how the rules happened to be listed.
        self._rules = sorted(rules, key=lambda r: (-r.priority, r.name))
        self._default = default_action

    def decide(self, base: BeliefBase) -> Verdict:
        trace: list[dict[str, Any]] = []
        rejections: list[Check] = []
        for rule in self._rules:
            fired, checks = rule.evaluate(base)
            trace.append(
                {
                    "rule": rule.name,
                    "fired": fired,
                    "checks": [check.as_dict() for check in checks],
                }
            )
            rejections.extend(check for check in checks if not check.met)
            if fired:
                return Verdict(
                    action=rule.then,
                    fired_rule=rule.name,
                    belief_digest=base.digest(),
                    trace=trace,
                    beliefs=base.as_dict(),
                    rejections=rejections,
                )

        trace.append({
            "rule": "<default>",
            "fired": True,
            "checks": [
                Check(
                    proposition="<none>",
                    met=True,
                    reason="no rule was satisfied by the belief base",
                ).as_dict()
            ],
        })
        return Verdict(
            action=self._default,
            fired_rule=None,
            belief_digest=base.digest(),
            trace=trace,
            beliefs=base.as_dict(),
            rejections=rejections,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "default_action": self._default,
            "rules": [r.as_dict() for r in self._rules],
        }


# -- calibration ---------------------------------------------------------------


def score_calibration(
    belief_log: "Iterable[dict[str, Any]]",
) -> tuple[dict[str, "Calibration"], dict[str, int]]:
    """Puntua la credencia ELICITADA contra lo que despues se OBSERVO, por proposicion.

    POR QUE ES UNA FUNCION. Este loop existia dos veces —en `store.py` y en
    `consolidation.py`— y **ya habia divergido**: una de las dos contaba
    contradicciones y la otra no. Nadie lo noto, porque dos copias de un calculo no
    fallan cuando se separan: siguen dando numeros, sólo que distintos.

    LA ASIMETRIA QUE HACE QUE ESTO SIGNIFIQUE ALGO. Sólo se puntua una creencia
    `ELICITED` cuando existe una `OBSERVED` sobre la MISMA proposicion en la misma
    base. Evidencia adjudicando opinion — que es exactamente para lo que existe el
    orden de procedencia. Una opinion que nadie fue a verificar no cuenta ni a favor ni
    en contra.

    Devuelve tambien las CONTRADICCIONES por proposicion —cuantas veces la opinion dijo
    lo contrario de lo observado— porque «mal calibrado» y «equivocado» no son lo mismo:
    un sensor que dice 0,9 y acierta el 50% esta mal calibrado; uno que afirma lo
    contrario de lo que se observa esta roto, y conviene poder distinguirlos.
    """
    per_prop: dict[str, Calibration] = {}
    contradictions: dict[str, int] = {}

    for record in belief_log:
        beliefs = record.get("beliefs", [])
        observed = {
            b["proposition"]: b["value"]
            for b in beliefs
            if b["provenance"] == Provenance.OBSERVED.value
        }
        for b in beliefs:
            if b["provenance"] != Provenance.ELICITED.value:
                continue
            name = b["proposition"]
            if name not in observed:
                continue
            correct = b["value"] == observed[name]
            per_prop.setdefault(name, Calibration()).record(
                float(b["credence"]), correct
            )
            if not correct:
                contradictions[name] = contradictions.get(name, 0) + 1

    return per_prop, contradictions


class Calibration:
    """Reliability of elicited credence: does 0.8 mean 0.8?

    Elicited beliefs are only usable to the extent their stated confidence tracks
    observed correctness. This measures that rather than assuming it, and the result
    is a publishable object in its own right: a model whose stated 0.8 is right half
    the time is a finding, not a nuisance.
    """

    def __init__(self, bins: int = 5) -> None:
        if bins < 2:
            raise ValueError("Need at least 2 bins for a reliability diagram.")
        self._bins = bins
        self._observations: list[tuple[float, bool]] = []

    def record(self, stated_credence: float, was_correct: bool) -> None:
        self._observations.append((stated_credence, was_correct))

    def diagram(self) -> list[dict[str, Any]]:
        width = 1.0 / self._bins
        rows: list[dict[str, Any]] = []
        for i in range(self._bins):
            low, high = i * width, (i + 1) * width
            # Upper edge inclusive on the last bin so credence 1.0 is counted.
            bucket = [
                (credence, correct) for credence, correct in self._observations
                if low <= credence < high or (i == self._bins - 1 and credence == 1.0)
            ]
            if not bucket:
                continue
            rows.append({
                "bin": f"[{low:.1f},{high:.1f})",
                "n": len(bucket),
                # La MEDIA de lo declarado en el bin, no el centro del bin. Con cinco
                # bins de ancho 0,2 el centro se equivoca hasta 0,1 de forma sistematica
                # — y 0,1 es exactamente `max_ece`, el umbral que decide si la credencia
                # elicitada puede gobernar una decision. O sea que el error del
                # estimador alcanzaba solo para dar vuelta el veredicto que estima.
                "stated_mean": round(sum(c for c, _ in bucket) / len(bucket), 4),
                "observed_accuracy": round(sum(k for _, k in bucket) / len(bucket), 4),
            })
        return rows

    def expected_calibration_error(self) -> float | None:
        """ECE: mean |stated - observed| weighted by bin population."""
        rows = self.diagram()
        if not rows:
            return None
        total = sum(r["n"] for r in rows)
        return round(
            sum(r["n"] * abs(r["stated_mean"] - r["observed_accuracy"]) for r in rows)
            / total,
            5,
        )

    def is_trustworthy(self, max_ece: float = 0.1, min_observations: int = 30) -> bool:
        """Whether elicited credence has earned the right to drive a decision.

        Below `min_observations` the answer is no regardless of the error: an ECE
        computed on a handful of cases is itself noise.
        """
        if len(self._observations) < min_observations:
            return False
        ece = self.expected_calibration_error()
        return ece is not None and ece <= max_ece

    def as_dict(self) -> dict[str, Any]:
        return {
            "observations": len(self._observations),
            "ece": self.expected_calibration_error(),
            "trustworthy": self.is_trustworthy(),
            "diagram": self.diagram(),
        }
