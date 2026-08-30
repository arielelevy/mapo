"""REC F3: the counterfactual solver — what minimal belief change would alter the plan.

WHAT THIS IS. P15's failure had a precise shape: the decision was reproducible 26/26, the
explanation was complete, and none of it fed a repair. The router applied its C2/C4
winner to C5 because nothing in its state could express what made C5 different. This
module turns the recorded decision trace into the question the record can actually
answer: WHICH belief, if it were different or better evidenced, would have changed the
plan — and what bounded observation could resolve it.

THE TWO INVARIANTS THAT MAKE IT SAFE (PATRON_REC §9):

  A hypothesis never enters the factual base. Every simulation builds its own base from
  the recorded dicts and discards it; the factual digest before and after a diagnosis is
  byte-identical, and the tests assert exactly that.

  Diagnosis is replay, not inference. It needs the recorded beliefs, the rules and the
  fallback — never the model, never the corpus, never the network. An auditor can run it
  on the log alone.

WHAT "MINIMAL" MEANS HERE (declared order, PATRON_REC §3): fewest propositions
intervened, then cheapest estimated acquisition, then the WEAKEST provenance that still
flips the plan, then a stable lexicographic tiebreak. Minimality explains the decision,
not the outcome: that a belief flips the route does not prove the other route would have
answered better — that second claim needs the bench.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .beliefs import Belief, BeliefBase, Provenance, Verdict
from .rules import ACTION_SPECIALISE, BeliefPolicy, standard_rules

# ---------------------------------------------------------------------------------
# The intervention schema: which propositions a bounded observation could change.
#
# SIGNED VOCABULARY, not an open set. Only propositions that an acquisition could in
# principle resolve are admitted; COMPUTED facts (cardinality, oracle presence,
# declared irreversibility) are functions of the payload and no probe changes them.
# Each entry declares the CLOSURE that keeps a simulated base consistent: coupling has
# a computed complement (`coupling_unmeasured`) that sense() derives, and a hypothesis
# that touched one without the other would simulate a base sense() can never produce.
# ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class SchemaEntry:
    """UNA proposición que una intervención contrafáctica tiene permitido tocar.

    El esquema es CERRADO Y FIRMADO a propósito: el diagnóstico contrafáctico pregunta
    «¿qué creencia, de haber sido distinta, habría cambiado la decisión?», y sin un esquema
    cerrado esa pregunta se contesta inventando la creencia que convenga. Lo que se puede
    hipotetizar está declarado de antemano.

    `reachable` es la restricción que impide prometer de más: es la procedencia MÁS FUERTE
    que una adquisición real de esta proposición puede alcanzar. Una lectura acotada puede
    **verificar que una continuación existe** (`OBSERVED`); no puede verificar una negación
    global, así que una entrada no puede prometer lo que ninguna sonda sostiene.

    `recompute_unmeasured` existe por un error cometido dos veces: el complemento
    `coupling_unmeasured` tiene que **recomputarse** después de la hipótesis, exactamente
    como lo computa `sense()` —desde si la creencia satisface el piso—. Una clausura
    estática hacía que una hipótesis `ELICITED` diera vuelta una regla que exige
    `OBSERVED`, afirmando un hecho computado que `sense()` nunca habría derivado.
    """

    proposition: str
    alternatives: tuple[Any, ...]
    # The strongest provenance a real acquisition of this proposition can reach —
    # PATRON_REC §5: a bounded read can VERIFY a continuation exists (OBSERVED); it
    # cannot verify a global negation, so entries must not promise what no probe keeps.
    reachable: Provenance
    # Rough acquisition cost in tokens, for the minimality order. An estimate is fine:
    # it ranks candidate repairs, it never enters utility.
    cost_estimate_tokens: int
    # Whether the complement `coupling_unmeasured` must be RECOMPUTED after the
    # hypothesis, exactly the way sense() computes it: from whether the belief
    # satisfies the policy floor. A static closure was wrong twice over — it made an
    # ELICITED hypothesis flip a rule that demands OBSERVED, by asserting a computed
    # fact sense() would never have derived.
    recompute_unmeasured: bool = False


SCHEMA: tuple[SchemaEntry, ...] = (
    SchemaEntry(
        proposition="coupling_tight",
        alternatives=(True, False),
        reachable=Provenance.OBSERVED,
        cost_estimate_tokens=2_500,  # one probe read: prompt + one unit
        recompute_unmeasured=True,
    ),
    SchemaEntry(
        proposition="horizon_unknown",
        alternatives=(True, False),
        # §5 is explicit: no bounded read proves the GLOBAL claim "the number of steps
        # is not knowable". Key recurrence proves a continuation exists, and relevance
        # stays elicited. The schema must not promise OBSERVED for this one.
        reachable=Provenance.ELICITED,
        cost_estimate_tokens=2_500,
    ),
)


# ---------------------------------------------------------------------------------
# The decision function, pure over a base.
# ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanLabel:
    """What the rules decided, compressed to what a repair could change."""

    action: str
    fired_rule: str
    paradigm: str

    def as_dict(self) -> dict[str, str]:
        return {"action": self.action, "fired_rule": self.fired_rule, "paradigm": self.paradigm}


def decide_label(base: BeliefBase, policy: BeliefPolicy, fallback: str) -> PlanLabel:
    """The governance outcome for one base: pure, no model, no theta consultation.

    Paradigm resolution mirrors the router's materialisation: a specialise action goes
    to whatever `best_paradigm` the base carries (theta's assertion IS a belief), and
    everything else resolves structurally. This is the D of PATRON_REC §3.
    """
    verdict: Verdict = standard_rules(policy).decide(base)
    if verdict.action == ACTION_SPECIALISE:
        paradigm = str(base.value("best_paradigm", fallback))
    elif verdict.action == "gate_then_fallback":
        paradigm = f"gated:{fallback}"
    elif verdict.action == "cascade":
        paradigm = "ladder"
    elif verdict.action == "probe_then_decide":
        paradigm = "probe-placeholder"
    else:
        paradigm = fallback
    return PlanLabel(
        action=verdict.action,
        fired_rule=verdict.fired_rule or "<default>",
        paradigm=paradigm,
    )


# ---------------------------------------------------------------------------------
# Deficits and the diagnosis
# ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Intervention:
    """La hipótesis: «si esta proposición hubiera valido esto, con esta procedencia».

    Es el `do()` del diagnóstico contrafáctico, y lleva **procedencia y credencia** porque
    sin ellas no es una hipótesis sino un deseo: cambiar un valor sin decir con qué calidad
    de evidencia se lo habría sabido permite reparar cualquier decisión postulando
    conocimiento que nadie podría haber tenido.

    Una intervención sólo puede proponer una procedencia que su `SchemaEntry` declare
    alcanzable. Esa es la única barrera entre reparar una decisión y racionalizarla.
    """

    proposition: str
    value: Any
    provenance: Provenance
    credence: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "proposition": self.proposition,
            "value": self.value,
            "provenance": self.provenance.value,
            "credence": self.credence,
        }


@dataclass(frozen=True)
class Deficit:
    """One hypothetical change that flips the plan, with the exact requirement."""

    interventions: tuple[Intervention, ...]
    label_before: PlanLabel
    label_after: PlanLabel
    # The WEAKEST provenance at which the flip still happens: the actual requirement.
    required_provenance: Provenance
    cost_estimate_tokens: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "interventions": [i.as_dict() for i in self.interventions],
            "before": self.label_before.as_dict(),
            "after": self.label_after.as_dict(),
            "required_provenance": self.required_provenance.value,
            "cost_estimate_tokens": self.cost_estimate_tokens,
        }

    def sort_key(self) -> tuple:
        return (
            len(self.interventions),
            self.cost_estimate_tokens,
            -self.required_provenance.rank,  # weaker requirement first
            tuple(i.proposition for i in self.interventions),
            tuple(str(i.value) for i in self.interventions),
        )


@dataclass
class Diagnosis:
    """The counterfactual reading of one recorded decision. Replayable from the log."""

    original: PlanLabel
    deficits: list[Deficit] = field(default_factory=list)

    @property
    def minimal(self) -> Deficit | None:
        return min(self.deficits, key=Deficit.sort_key) if self.deficits else None

    def as_dict(self) -> dict[str, Any]:
        minimal = self.minimal
        return {
            "original": self.original.as_dict(),
            "deficits": [d.as_dict() for d in self.deficits],
            "minimal": minimal.as_dict() if minimal else None,
            "decision_is_belief_sensitive": bool(self.deficits),
        }


def _simulate(
    records: list[dict[str, Any]],
    interventions: list[Intervention],
    schema_by_prop: dict[str, SchemaEntry],
    policy: BeliefPolicy,
    fallback: str,
) -> PlanLabel:
    """One counterfactual: a FRESH base from the record, plus the hypothesis.

    The hypothesis and its closure are appended LAST, so they supersede by provenance
    rank — or, at equal rank, by recency, which is the supersession the factual path
    itself uses. The base is discarded on return: nothing here can touch the record.
    """
    base = BeliefBase.from_dicts(records)
    for iv in interventions:
        base.assert_(Belief(
            proposition=iv.proposition,
            value=iv.value,
            credence=iv.credence,
            provenance=iv.provenance,
            evidence="[counterfactual hypothesis] never part of the factual record",
        ))
        entry = schema_by_prop[iv.proposition]
        if entry.recompute_unmeasured:
            # The complement is DERIVED, never assumed: same computation as sense().
            # Under an OBSERVED floor an ELICITED hypothesis leaves the coupling
            # unmeasured — and therefore leaves the probe rule standing, which is
            # precisely the requirement the deficit has to report.
            measured = base.satisfies("coupling_tight", 0.0, policy.derived_floor)
            base.assert_(Belief(
                proposition="coupling_unmeasured",
                value=not measured,
                credence=1.0,
                provenance=Provenance.COMPUTED,
                evidence="[counterfactual closure] recomputed against the policy floor",
            ))
    return decide_label(base, policy, fallback)


@dataclass(frozen=True)
class ContractDeficit:
    """Lo que un contrato rechazado dice que falta, sin buscarlo.

    LA ASIMETRIA QUE HACE QUE ESTO NO SEA `diagnose`. `diagnose` BUSCA: prueba
    intervenciones de a una y de a pares hasta encontrar la mas barata que cambie la
    decision, porque el registro no dice que le falto. Un contrato rechazado **ya lo
    dice** — `C-COMPLETE` nombra las claves ausentes y `C-NUM` nombra la ranura cuya
    proposicion no llego al piso.

    Buscar donde ya hay respuesta no es redundante: es peor. La busqueda esta acotada a
    un esquema chico —una enumeracion abierta seria una busqueda de HISTORIAS y esto es
    una busqueda de EVIDENCIA— asi que un deficit real que no este en el esquema **no se
    encontraria**, y el resultado diria «no hay intervencion que lo cambie» cuando la
    hay y el contrato la nombro.

    Por eso el rechazo entra como un hecho, no como una hipotesis.
    """

    contract: str
    missing: tuple[str, ...]
    reason: str
    # Que procedencia haria falta para que lo que falta CUENTE. El contrato la conoce:
    # es su propio piso, no una estimacion.
    required_provenance: Provenance

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "missing": list(self.missing),
            "reason": self.reason,
            "required_provenance": self.required_provenance.value,
            "searched": False,
        }


def deficit_from_contract(
    verdict: Any,
    contract: str,
    floor: Provenance = Provenance.COMPUTED,
) -> ContractDeficit | None:
    """El deficit que un veredicto de contrato ya declara. `None` si emitio.

    Acepta los dos veredictos que hoy existen —`CompletenessVerdict` y `NumericVerdict`—
    por lo que TIENEN, no por lo que son: uno nombra claves ausentes, el otro ranuras
    rechazadas. Tipar contra las clases ataria esta capa al modulo de contratos en la
    direccion equivocada.
    """
    if getattr(verdict, "emitted", False):
        return None

    missing: tuple[str, ...] = ()
    reason = ""

    if hasattr(verdict, "missing"):  # C-COMPLETE
        extra = tuple(getattr(verdict, "extraneous", ()) or ())
        missing = tuple(verdict.missing) + tuple(f"sobra:{k}" for k in extra)
        reason = getattr(verdict, "refused", "") or "cobertura incompleta"
    elif hasattr(verdict, "refused"):  # C-NUM
        missing = tuple(slot for slot, _, _ in verdict.refused)
        reason = "; ".join(f"{slot}: {why}" for slot, _, why in verdict.refused)

    if not missing:
        # Rechazo sin nada nombrado: eso NO es un deficit, es un contrato que no puede
        # decir que le falto. Devolverlo vacio lo haria pasar por «no falta nada».
        return None

    return ContractDeficit(
        contract=contract,
        missing=missing,
        reason=reason,
        required_provenance=floor,
    )


def diagnose(
    belief_records: list[dict[str, Any]],
    policy: BeliefPolicy,
    fallback: str,
    schema: tuple[SchemaEntry, ...] = SCHEMA,
) -> Diagnosis:
    """What minimal admitted intervention would change this recorded decision.

    Singletons first; pairs only when no single proposition flips anything. The schema
    is tiny by design — an open enumeration would be a search for stories, and this is
    a search for the cheapest EVIDENCE.
    """
    schema_by_prop = {e.proposition: e for e in schema}
    original = decide_label(BeliefBase.from_dicts(belief_records), policy, fallback)
    diagnosis = Diagnosis(original=original)

    def probe_strengths(entry: SchemaEntry) -> list[tuple[Provenance, float]]:
        # Weakest-first, capped at what an acquisition can actually reach: the deficit
        # records the MINIMUM evidence strength that flips, which is what a clause
        # would have to buy.
        ladder = [(Provenance.ELICITED, 0.8), (Provenance.OBSERVED, 1.0)]
        return [(p, c) for p, c in ladder if p.rank <= entry.reachable.rank]

    def try_set(entries_values: list[tuple[SchemaEntry, Any]]) -> None:
        for strength, credence in probe_strengths(entries_values[0][0]):
            interventions = [
                Intervention(
                    proposition=entry.proposition,
                    value=value,
                    provenance=min(strength, entry.reachable, key=lambda p: p.rank),
                    credence=credence,
                )
                for entry, value in entries_values
            ]
            label = _simulate(belief_records, interventions, schema_by_prop, policy, fallback)
            if label != original:
                diagnosis.deficits.append(Deficit(
                    interventions=tuple(interventions),
                    label_before=original,
                    label_after=label,
                    required_provenance=strength,
                    cost_estimate_tokens=sum(e.cost_estimate_tokens for e, _ in entries_values),
                ))
                return  # weakest flipping strength found: that IS the requirement

    for entry in schema:
        for value in entry.alternatives:
            try_set([(entry, value)])

    if not diagnosis.deficits:
        for i, first in enumerate(schema):
            for second in schema[i + 1:]:
                for v1 in first.alternatives:
                    for v2 in second.alternatives:
                        try_set([(first, v1), (second, v2)])

    return diagnosis


# ---------------------------------------------------------------------------------
# Acquisition clauses (PATRON_REC §4.2): serialisable, digestible, gated on promotion
# ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class AcquisitionClause:
    """A promoted answer to a recurring deficit: what evidence to buy, and how to stop.

    The LLM may propose a span, a key or a relation. It does not decide whether the
    probe runs, whether the evidence verifies, when to stop, or which route follows —
    those are this clause's fields, and the clause only runs at all if `certificate`
    names the promotion that authorised it. An empty certificate is a DRAFT: the
    factual path must refuse to execute it (PATRON_REC §4.2, invariant 7 of §9).
    """

    clause_id: str
    # Applicability: the deficit this clause answers, and where.
    target_proposition: str
    region_prefixes: tuple[str, ...]  # e.g. ("many/", "few/") — "" matches everywhere
    # The probe: what bounded acquisition to run and what may verify it.
    probe_kind: str  # "unit_read_pointer" | "key_recurrence"
    verifier: str  # e.g. "key-recurrence/1"
    reachable: Provenance
    # Budget and stopping.
    max_reads: int
    max_calls: int
    max_tokens: int
    # Safe exit when the evidence does not verify or the budget runs out.
    safe_exit: str  # "defer" | "gate"
    # The promotion that authorised this clause. Empty = draft = must not execute.
    certificate: str = ""

    def applies_to(self, deficit: Deficit, region: str) -> bool:
        if not any(region.startswith(p) for p in self.region_prefixes):
            return False
        return any(
            iv.proposition == self.target_proposition for iv in deficit.interventions
        )

    @property
    def promoted(self) -> bool:
        return bool(self.certificate)

    def as_dict(self) -> dict[str, Any]:
        return {
            "clause_id": self.clause_id,
            "target_proposition": self.target_proposition,
            "region_prefixes": list(self.region_prefixes),
            "probe_kind": self.probe_kind,
            "verifier": self.verifier,
            "reachable": self.reachable.value,
            "max_reads": self.max_reads,
            "max_calls": self.max_calls,
            "max_tokens": self.max_tokens,
            "safe_exit": self.safe_exit,
            "certificate": self.certificate,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AcquisitionClause":
        return cls(
            clause_id=str(raw["clause_id"]),
            target_proposition=str(raw["target_proposition"]),
            region_prefixes=tuple(raw["region_prefixes"]),
            probe_kind=str(raw["probe_kind"]),
            verifier=str(raw["verifier"]),
            reachable=Provenance(raw["reachable"]),
            max_reads=int(raw["max_reads"]),
            max_calls=int(raw["max_calls"]),
            max_tokens=int(raw["max_tokens"]),
            safe_exit=str(raw["safe_exit"]),
            certificate=str(raw.get("certificate", "")),
        )

    def digest(self) -> str:
        """Content identity of the clause. The certificate is EXCLUDED on purpose: the
        certificate signs the clause, so the clause's digest cannot contain it — and a
        date never enters either (PATRON_REC §7)."""
        body = {k: v for k, v in self.as_dict().items() if k != "certificate"}
        blob = json.dumps(body, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------
# The key-recurrence verifier (PATRON_REC §5): the honest observable for continuation
# ---------------------------------------------------------------------------------

KEY_RECURRENCE_VERIFIER = "key-recurrence/1"


def verify_key_recurrence(
    key: str,
    source_id: str,
    documents: dict[str, str],
    scope: list[str],
) -> dict[str, Any] | None:
    """Does a literal key in `source_id` recur in a DIFFERENT unit in scope?

    Everything checked by code, nothing taken from the sensor's word: literal span in
    the source, source and target distinct and both in scope, the same literal key in
    the target, deterministic resolution (first match in sorted order), and content
    hashes plus verifier version so the observation can be audited byte-for-byte.

    Returns the evidence record, or None. None is NOT a negative observation: a key
    that fails to recur in this scope says nothing global (§9, invariant 4) — the
    caller must leave the belief where it was, never demote it.
    """
    key = (key or "").strip()
    if not key or source_id not in documents or source_id not in set(scope):
        return None
    source_text = documents[source_id]
    source_offset = source_text.find(key)
    if source_offset < 0:
        return None

    for target_id in sorted(set(scope)):
        if target_id == source_id or target_id not in documents:
            continue
        target_offset = documents[target_id].find(key)
        if target_offset < 0:
            continue
        return {
            "proposition": "key_recurrence",
            "value": True,
            "provenance": Provenance.OBSERVED.value,
            "credence": 1.0,
            "key": key,
            "source": {
                "unit_id": source_id,
                "span_offset": source_offset,
                "content_sha256": hashlib.sha256(
                    source_text.encode("utf-8")
                ).hexdigest(),
            },
            "target": {
                "unit_id": target_id,
                "span_offset": target_offset,
                "content_sha256": hashlib.sha256(
                    documents[target_id].encode("utf-8")
                ).hexdigest(),
            },
            "verifier": KEY_RECURRENCE_VERIFIER,
            "note": (
                "proves a continuation EXISTS between two units; whether the key is "
                "semantically decisive stays ELICITED (PATRON_REC §5)"
            ),
        }
    return None
