"""The reconnaissance slice: one cheap read that turns an opinion into an observation.

WHY THIS EXISTS. `router.plan()` has always been able to say `needs_probe`, and the rule
`probe_before_deciding_on_bulk` has always been able to demand it, and nothing ever ran
one. That was survivable while every floor admitted ELICITED evidence. It stopped being
survivable when the assurance floor learned to raise itself (§6.2): a rule that demands
OBSERVED provenance in a region where nothing can ever produce OBSERVED provenance is not
strict, it is unsatisfiable, and the request falls to the fallback for a reason that has
nothing to do with the request.

WHAT IT MEASURES. Coupling: whether answering needs a value that is not in the unit you
are holding. One unit is read — locally, for free — and the model is asked, as a SENSOR,
to emit two typed facts about it: does the question need something this unit does not
contain, and does the unit NAME where that something lives.

WHY THE ANSWER CAN BE OBSERVED. Because the code checks it. A named dependency is
verified against the unit ids actually in scope: if the model says "this points at
memo-014" and memo-014 is in scope, the pointer is real and the coupling is measured, not
asserted. That check is what separates this from asking the model for a number and
believing it.

WHY A NEGATIVE STAYS ELICITED. The asymmetry is not an oversight. From one unit, code can
confirm that a dependency EXISTS -- the pointer resolves -- but it cannot confirm that no
dependency exists anywhere in the other forty-seven units it did not read. "I saw the
link" is an observation; "I saw no link" is one unit's worth of silence. Recording the
second as OBSERVED would be the layer lying to itself in exactly the direction that
costs the most: it would let a coupled task be routed as if it were independent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .beliefs import Provenance

# The threshold `rules.sense` uses to call coupling tight is 0.66. A verified pointer is
# evidence of tightness, and one that the model named but could not be resolved is not
# evidence of anything -- it is the sensor being wrong, which is the case this layer was
# built to survive.
COUPLED = 0.85
UNCOUPLED = 0.15

PROBE_PROMPT = """You are a sensor, not a decision maker. Report what you observe.

Question: {question}

You are holding ONE unit of the material. There are {n_units} units in total; you cannot
see the others.

Unit {unit_id}:
{unit_text}

Answer with JSON only, no prose:
{{"self_contained": true|false,
  "references": ["exact identifiers this unit names that live in OTHER units, verbatim"]}}

`self_contained` is true when this unit alone contains what the question asks for.
`references` lists identifiers written IN THIS UNIT that point elsewhere -- an account
number, a memo id, a person named as the holder of something described elsewhere. Copy
them exactly as they appear. Empty list if there are none."""


@dataclass(frozen=True)
class ProbeResult:
    """What the probe measured, and how much it is worth believing."""

    coupling: float
    provenance: Provenance
    credence: float
    evidence: str
    unit_id: str
    resolved: list[str]
    claimed: list[str]
    cost_tokens: int = 0
    calls: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "coupling": round(self.coupling, 3),
            "provenance": self.provenance.value,
            "credence": round(self.credence, 3),
            "evidence": self.evidence,
            "unit_id": self.unit_id,
            "resolved_references": self.resolved,
            "claimed_references": self.claimed,
            "cost_tokens": self.cost_tokens,
            "calls": self.calls,
        }


def _extract_json(raw: str) -> dict[str, Any]:
    """The sensor's payload, or an empty reading.

    A sensor that returns something unparseable has not reported; it has failed. That is
    a reading of nothing, not a reading of zero.
    """
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
    except ValueError:
        return {}
    try:
        payload = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


# Un puente tiene que ser especifico. Una cadena que aparece en casi todas las unidades
# —un encabezado, un apellido compartido por medio corpus— conecta cualquier cosa con
# cualquier cosa, asi que conectar deja de significar nada. Misma disciplina que
# `measure_continuation` usa para excluir boilerplate, y por la misma razon.
MIN_BRIDGE_CHARS = 4
MAX_BRIDGE_SHARE = 0.5


def _resolve(
    references: list[str],
    scope: list[str],
    unit_text: str,
    source: str,
    documents: dict[str, str] | None = None,
) -> list[tuple[str, int]]:
    """Which named references verify: (target, span offset) pairs, checked by code.

    QUE CAMBIO, Y POR QUE ESTABA MAL. Esto exigia que la referencia fuera un ID DE UNIDAD
    en alcance. Medido en P17: la sonda corrio en las 14 tareas que la pedian y resolvio
    CERO — «the sensor named 2 reference(s), none of which resolve to a unit in scope».

    El motivo no era el piso de procedencia: era que el prompt y el verificador no pedian
    lo mismo. El prompt invita —correctamente— a nombrar «an account number, a memo id, a
    person named as the holder of something described elsewhere», y los documentos SE
    REFERENCIAN ASI. La cadena de `c3-000-h1` es `memo-002` diciendo «Reports to Ignacio
    Arrieta» y `memo-001` diciendo «Ignacio Arrieta serves as director»: el puente es un
    NOMBRE, y no hay ningun id de unidad escrito en el texto. El verificador rechazaba
    lecturas correctas del sensor y las puntuaba como punteros inventados.

    LO QUE NO CAMBIA, PORQUE ES LO QUE HACE QUE ESTO VALGA. Sigue verificando por codigo y
    sigue guardando el span. Una referencia resuelve cuando es un PUENTE LITERAL:

      - aparece literalmente en la unidad que se esta sosteniendo (con su offset), y
      - aparece literalmente en al menos otra unidad EN ALCANCE — eso es la dependencia:
        esta unidad nombra algo que vive en otra, y el codigo puede ir a verlo, y
      - es lo bastante especifica: ni una cadena de tres caracteres ni algo que aparece en
        mas de la mitad del alcance, porque un puente que conecta todo no conecta nada.

    Sin `documents` se conserva la conducta vieja —solo ids de unidad—, que es lo correcto
    para un llamador que no puede ofrecer el material: no se puede verificar un puente
    contra un corpus que no se tiene.
    """
    in_scope = set(scope)
    resolved: dict[str, int] = {}
    others = [u for u in scope if u != source]
    limit = max(1, int(len(scope) * MAX_BRIDGE_SHARE))

    for reference in references:
        if not isinstance(reference, str):
            continue
        candidate = reference.strip()
        if not candidate or candidate == source:
            continue
        offset = unit_text.find(candidate)
        if offset < 0:
            # No esta escrito en la unidad que el modelo dice estar leyendo. Eso es el
            # caso que esta funcion existia para atrapar y se sigue atrapando.
            continue

        if candidate in in_scope:
            resolved.setdefault(candidate, offset)
            continue

        if documents is None or len(candidate) < MIN_BRIDGE_CHARS:
            continue

        needle = candidate.lower()
        elsewhere = [
            u for u in others if needle in (documents.get(u) or "").lower()
        ]
        if elsewhere and len(elsewhere) <= limit:
            # El objetivo es la unidad puente: la que tambien lo nombra. Se toma la
            # primera en orden de alcance para que la lectura sea determinista.
            resolved.setdefault(elsewhere[0], offset)

    return sorted(resolved.items())


def _select_unit(surface: Any, task: dict[str, Any], scope: list[str]) -> str:
    """The unit the probe reads: top of the lexical ranking, or the first in scope."""
    lexical = getattr(surface, "lexical", None)
    view = getattr(surface, "view", None)
    if lexical is not None and view is not None:
        # SIN RED. Un fallo de ranking hacia caer a `scope[0]` en silencio: la sonda leia
        # OTRA unidad, la creencia salia con la procedencia de una lectura correcta, y
        # nada en el registro decia que el ranking se habia caido. La medida de la sonda
        # es exactamente "que unidad leyo", asi que ese fallback falsificaba lo medido.
        #
        # Que no haya ranking util —lista vacia, o un id fuera de alcance— NO es un error:
        # es un resultado, y ahi si corresponde el primero en alcance.
        ranked = lexical.rank(view, task.get("question", ""), 1)
        if ranked and ranked[0] in set(scope):
            return ranked[0]
    return scope[0]


def probe_coupling(
    client: Any,
    surface: Any,
    task: dict[str, Any],
    unit_id: str | None = None,
) -> ProbeResult:
    """Read one unit, ask the sensor, verify the answer against the scope.

    The unit is chosen by deterministic lexical retrieval over the question (falling
    back to the first in scope), so two runs of the same task probe the same unit: a
    probe that sampled would make the decision it feeds unreproducible, which is the
    one thing this layer promises.
    """
    scope = list(surface.unit_ids())
    if not scope:
        return ProbeResult(
            coupling=UNCOUPLED,
            provenance=Provenance.ASSUMED,
            credence=0.0,
            evidence="nothing in scope to probe",
            unit_id="",
            resolved=[],
            claimed=[],
        )

    # F2.2: the unit is chosen by DETERMINISTIC retrieval over the question, not by
    # position. The first unit was a fixed guess; the lexical ranking is free, needs no
    # network, and is reproducible for a fixed corpus and question — which keeps the
    # promise that two runs of the same task probe the same unit, while probing the
    # unit most likely to bear on the question instead of whichever came first.
    target = unit_id or _select_unit(surface, task, scope)
    unit_text = surface.read_one(target)

    completion = client.complete(
        messages=[
            {
                "role": "user",
                "content": PROBE_PROMPT.format(
                    question=task["question"],
                    n_units=len(scope),
                    unit_id=target,
                    unit_text=unit_text,
                ),
            }
        ]
    )
    payload = _extract_json(completion.text)
    usage = completion.usage

    if not payload:
        return ProbeResult(
            coupling=UNCOUPLED,
            provenance=Provenance.ASSUMED,
            credence=0.0,
            evidence="the sensor returned nothing parseable: no reading",
            unit_id=target,
            resolved=[],
            claimed=[],
            cost_tokens=usage.total_tokens,
            calls=usage.calls,
        )

    claimed = payload.get("references") or []
    claimed = [r for r in claimed if isinstance(r, str)]
    # El material CRUDO de la vista, no `surface.read_one`: leer por la superficie
    # incrementaria `units_read` y la traza diria que la sonda leyo el corpus entero,
    # cuando lo unico que hace el codigo es buscar una subcadena. La contabilidad tiene
    # que describir lo que el MODELO vio, no lo que el verificador miro.
    view = getattr(surface, "view", None)
    material = getattr(view, "documents", None) if view is not None else None
    resolved_spans = _resolve(
        claimed, scope, unit_text, source=target, documents=material
    )
    resolved = [name for name, _ in resolved_spans]

    self_contained = bool(payload.get("self_contained"))

    if resolved and not self_contained:
        # DOS CONDICIONES, Y HACEN FALTA LAS DOS. El codigo verifico que el puente existe
        # —la unidad nombra literalmente algo que vive en otra, con su offset— y el sensor
        # dijo que esta unidad NO alcanza para contestar. La primera sola no sirve: en un
        # corpus de memos sobre personas que se repiten, casi toda unidad nombra algo que
        # esta en otra, asi que "hay puente" seria verdadero en todos lados y no
        # discriminaria nada.
        #
        # Medido: con la sola verificacion del puente, la sonda daba COUPLED en tareas
        # cuya `truth_coupling` declarada es 0,00 y 0,20 — 2 falsos positivos sobre 6
        # revisadas. El puente prueba que el VINCULO EXISTE; que la PREGUNTA lo necesite
        # es un juicio sobre la tarea, y ese lo aporta el sensor.
        #
        # Es la division de trabajo del producto aplicada adentro de la sonda: el modelo
        # propone —"esto no se contesta solo"— y el codigo verifica —"y ese puente es
        # real, aca esta el span"—. Ninguna de las dos gobierna sola.
        return ProbeResult(
            coupling=COUPLED,
            provenance=Provenance.OBSERVED,
            credence=1.0,
            evidence=(
                f"unit {target} is not self-contained and names {len(resolved)} "
                "identifier(s) that resolve elsewhere in scope ("
                + ", ".join(f"{n}@{off}" for n, off in resolved_spans[:3])
                + "): dependency verified at those literal spans, not asserted"
            ),
            unit_id=target,
            resolved=resolved,
            claimed=claimed,
            cost_tokens=usage.total_tokens,
            calls=usage.calls,
        )

    if resolved and self_contained:
        # El puente es real y el sensor dice que igual no hace falta seguirlo. Eso NO es
        # "sin acoplamiento": es una unidad que basta para esta pregunta y ademas menciona
        # a otras. Se registra como desacoplado, pero ELICITED — la parte que decide es un
        # juicio del modelo, y no puede viajar como observacion.
        return ProbeResult(
            coupling=UNCOUPLED,
            provenance=Provenance.ELICITED,
            credence=0.6,
            evidence=(
                f"unit {target} names {len(resolved)} identifier(s) that resolve "
                "elsewhere, but the sensor reports the unit answers the question on its "
                "own: the link exists and the question does not need it"
            ),
            unit_id=target,
            resolved=resolved,
            claimed=claimed,
            cost_tokens=usage.total_tokens,
            calls=usage.calls,
        )

    if claimed and not resolved:
        # The sensor named pointers and none of them exist. That is not evidence of
        # coupling and it is not evidence of independence either -- it is a sensor
        # reading that failed verification, and it is recorded as such.
        return ProbeResult(
            coupling=UNCOUPLED,
            provenance=Provenance.ELICITED,
            credence=0.2,
            evidence=(
                f"unit {target}: the sensor named {len(claimed)} reference(s), none of "
                "which resolve to a unit in scope — the reading did not verify"
            ),
            unit_id=target,
            resolved=[],
            claimed=claimed,
            cost_tokens=usage.total_tokens,
            calls=usage.calls,
        )

    return ProbeResult(
        coupling=UNCOUPLED if self_contained else COUPLED,
        provenance=Provenance.ELICITED,
        credence=0.6,
        evidence=(
            f"unit {target} was reported {'self-contained' if self_contained else 'incomplete'} "
            "and named no resolvable pointer: one unit of silence is not a measurement "
            "of the other units, so this stays elicited"
        ),
        unit_id=target,
        resolved=[],
        claimed=claimed,
        cost_tokens=usage.total_tokens,
        calls=usage.calls,
    )
