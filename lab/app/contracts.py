"""Contratos de afirmacion: el proyector que el codigo decide, y su residuo.

Implementa DOS de las tres clases de `CONTRATOS.es.md` §2 — las dos que se pueden cerrar
sin parsear prosa:

  C-NUM       ningun numeral emitido puede ser inventado          `fill()`
  C-COMPLETE  una enumeracion cubre el dominio que declara        `complete()`

C-CITE queda afuera a proposito: verificar una cita contra el indice necesita el indice,
que es infraestructura de producto y no de esta capa.

LA FORMA. El modelo NO escribe digitos. Escribe una plantilla con ranuras nombradas y una
asignacion ranura -> proposicion; el codigo sustituye desde la base de creencias. Asi el
proyector `pi_NUM` no tiene que extraer numeros de un texto —nada que parsear— porque las
ranuras ya vienen enumeradas.

LO QUE GARANTIZA. Ningun numeral de la salida puede ser inventado: cada uno es el
renderizado de un valor sostenido en la base a procedencia >= `floor`. Una ranura cuya
proposicion no llega al piso NO se renderiza — la afirmacion no se emite.

LO QUE NO GARANTIZA, Y ESTA IMPLEMENTADO PARA PODER MEDIRLO. Que la ranura este en el
lugar correcto de la oracion. La asociacion ranura -> posicion la elige el modelo, y eso
queda FUERA de `pi_NUM`. Ese es el residuo, y `redteam.py` lo ataca.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .beliefs import Belief, BeliefBase, Provenance

# Vocabulario CERRADO de ranuras: identificadores, no prosa. Se listan y se buscan por
# nombre exacto — no se infiere nada de texto libre.
SLOT = re.compile(r"\{([a-z][a-z0-9_]*)\}")


@dataclass(frozen=True)
class SlotBinding:
    """Una ranura de la plantilla y la proposicion que el modelo le asigno."""

    slot: str
    proposition: str


@dataclass
class NumericVerdict:
    """Que paso con cada ranura, y por que."""

    rendered: str | None
    checked: list[tuple[str, str, Any]] = field(default_factory=list)
    refused: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def emitted(self) -> bool:
        return self.rendered is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "emitted": self.emitted,
            "rendered": self.rendered,
            "checked": [
                {"slot": s, "proposition": p, "value": v} for s, p, v in self.checked
            ],
            "refused": [
                {"slot": s, "proposition": p, "reason": r} for s, p, r in self.refused
            ],
        }


def slots_of(template: str) -> list[str]:
    """Las ranuras que la plantilla declara, en orden de aparicion."""
    return SLOT.findall(template)


def fill(
    template: str,
    bindings: list[SlotBinding],
    base: BeliefBase,
    floor: Provenance = Provenance.COMPUTED,
) -> NumericVerdict:
    """Sustituir cada ranura por el valor de su proposicion, o no emitir nada.

    FALLA CERRADA Y ENTERA. Si una sola ranura no llega al piso, no se emite una version
    parcial: la salida entera se retiene. Emitir la oracion con un hueco —o peor, con el
    nombre de la ranura visible— seria dejar que el lector complete lo que el contrato
    rechazo, que es la version tipografica de afirmar sin evidencia.
    """
    verdict = NumericVerdict(rendered=None)
    declared = {b.slot: b.proposition for b in bindings}
    values: dict[str, Any] = {}

    for slot in slots_of(template):
        proposition = declared.get(slot)
        if proposition is None:
            verdict.refused.append((slot, "", "la plantilla usa una ranura sin asignar"))
            continue
        belief = base.current(proposition)
        if belief is None:
            verdict.refused.append((slot, proposition, "no hay creencia sobre eso"))
            continue
        if belief.provenance.rank < floor.rank:
            verdict.refused.append((
                slot, proposition,
                f"procedencia {belief.provenance.value} por debajo de {floor.value}",
            ))
            continue
        values[slot] = belief.value
        verdict.checked.append((slot, proposition, belief.value))

    if verdict.refused:
        return verdict

    verdict.rendered = SLOT.sub(lambda m: str(values[m.group(1)]), template)
    return verdict


# --- C-COMPLETE ---------------------------------------------------------------------
#
# POR QUE ESTA CLASE, Y POR QUE RECIEN AHORA. Estaba escrita en `CONTRATOS.es.md` §2 desde
# el principio y no implementada, porque no habia nada que dijera que hacia falta. Lo hay
# desde el 2026-08-28 (`_analyze_demands2.py`, leccion 8.6):
#
#   sobre celdas de cobertura EXIGIDA, leer mas NO mejora la utilidad
#   (corr +0,018, mediana -0,055, contra +0,259 donde la cobertura no se exige)
#
# El arreglo intuitivo frente a una enumeracion incompleta es "que lea todo", y el registro
# dice que no funciona: lo dificil no es haber visto, es COMPONER lo visto. Entonces la
# completitud no se compra con presupuesto de lectura — hace falta verificarla, y
# verificarla es aritmetica sobre un dominio declarado.
#
# LA FORMA, Y ES LA MISMA DISCIPLINA QUE C-NUM. El modelo NO escribe una lista en prosa
# para que alguien despues la parsee. Escribe CLAVES de un vocabulario que el codigo ya
# enumero, mas la proposicion que define el dominio. Entonces `pi_COMPLETE` no extrae nada
# de un texto: compara dos conjuntos.
#
# LO QUE GARANTIZA. Que los items enumerados cubren EXACTAMENTE el dominio declarado —
# nada falta y nada sobra. Las dos mitades importan y son distintas: lo que falta es una
# respuesta incompleta que parece bien formada; lo que sobra es un item que el dominio no
# admite.
#
# LO QUE NO GARANTIZA, Y SE REPORTA EN EL VEREDICTO. Que el dominio coincida con el mundo.
# Completitud sobre lo recuperado no es completitud sobre lo que existe, y la unica forma
# honesta de manejarlo es que el veredicto lleve la procedencia del dominio encima en vez
# de que el llamador la suponga.
#
# EL RESIDUO, que es el mismo hallazgo que el de C-NUM. Una enumeracion puede cubrir su
# dominio entero y estar mal: alcanza con que la ORACION que la envuelve diga otra cosa
# ("ninguno de estos", "todos menos", "los que quedan"). La prosa conectiva sigue sin
# ocupar ninguna ranura, asi que C-COMPLETE tampoco puede contradecirla. No es un defecto
# de esta implementacion — es la frontera de la familia entera, medida en `redteam.py`.


@dataclass
class CompletenessVerdict:
    """Que se enumero, contra que dominio, y que falto o sobro."""

    emitted: bool
    domain_proposition: str
    domain_provenance: str | None = None
    covered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    extraneous: list[str] = field(default_factory=list)
    refused: str | None = None

    @property
    def scope_is_declared_not_world(self) -> bool:
        """SIEMPRE cierto, y por eso es una propiedad y no un flag opcional.

        La garantia es relativa al dominio que la tarea declara. Que ese dominio sea el
        mundo es una afirmacion sobre la ingesta y la recuperacion, no sobre el contrato,
        y esta capa no tiene con que sostenerla.
        """
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "emitted": self.emitted,
            "domain": self.domain_proposition,
            "domain_provenance": self.domain_provenance,
            "covered": list(self.covered),
            "missing": list(self.missing),
            "extraneous": list(self.extraneous),
            "refused": self.refused,
            "scope": "dominio declarado, no el mundo",
        }


def complete(
    items: list[str],
    domain_proposition: str,
    base: BeliefBase,
    floor: Provenance = Provenance.COMPUTED,
) -> CompletenessVerdict:
    """Verificar que `items` cubre el dominio que `domain_proposition` sostiene.

    FALLA CERRADA Y ENTERA, como C-NUM. Una enumeracion a la que le falta un item no se
    emite recortada ni con una advertencia al lado: no se emite. Emitirla con una nota
    seria dejarle al lector la decision que el contrato existe para tomar — y el modo de
    falla de una enumeracion incompleta es justamente que PARECE completa.
    """
    verdict = CompletenessVerdict(emitted=False, domain_proposition=domain_proposition)

    belief = base.current(domain_proposition)
    if belief is None:
        verdict.refused = "no hay creencia que defina el dominio"
        return verdict

    verdict.domain_provenance = belief.provenance.value
    if belief.provenance.rank < floor.rank:
        verdict.refused = (
            f"el dominio se sostiene a {belief.provenance.value}, por debajo de "
            f"{floor.value}: una completitud sobre un dominio supuesto no es completitud"
        )
        return verdict

    if not isinstance(belief.value, (list, tuple, set, frozenset)):
        verdict.refused = (
            f"el dominio no es enumerable: {type(belief.value).__name__}. La cardinalidad "
            f"es aritmetica y no hay aritmetica sobre un valor que no se puede recorrer"
        )
        return verdict

    domain = list(dict.fromkeys(str(v) for v in belief.value))
    seen = list(dict.fromkeys(str(v) for v in items))

    verdict.covered = [k for k in domain if k in seen]
    verdict.missing = [k for k in domain if k not in seen]
    verdict.extraneous = [k for k in seen if k not in domain]

    if verdict.missing or verdict.extraneous:
        parts = []
        if verdict.missing:
            parts.append(f"faltan {len(verdict.missing)}")
        if verdict.extraneous:
            parts.append(f"sobran {len(verdict.extraneous)}")
        verdict.refused = " y ".join(parts)
        return verdict

    verdict.emitted = True
    return verdict


def addressed(answer: str, domain_keys: list[str]) -> list[str]:
    """Las claves del dominio que la respuesta MENCIONA, en orden de dominio.

    POR QUE ESTO NO ES PARSEAR PROSA, que es lo que este proyecto no acepta como sensor.
    No se extrae nada del texto: se toma un vocabulario CERRADO Y DECLARADO —las claves
    que el caller enuncio— y se pregunta por cada una si esta presente. La direccion
    importa: buscar una lista conocida adentro de un texto es contencion sobre un conjunto
    finito; extraer entidades de un texto para ver cuales hay es lo otro, y no se hace.

    LO QUE VERIFICA Y LO QUE NO. Verifica que la respuesta ATIENDA a cada elemento del
    dominio. NO verifica que lo que dice de cada uno sea correcto — eso es `C-CITE`, y
    necesita el indice. Un enunciado que nombra a los cinco y le erra a cuatro cuentas
    pasa esta verificacion y falla la otra: son contratos distintos a proposito.

    Y NO VE LO QUE SOBRA, que es una asimetria estructural y no una omision. Esta funcion
    busca las claves DECLARADAS adentro del texto, asi que un nombre que el dominio no
    contiene nunca entra en `items` y la pertenencia no es observable desde aca. Detectarlo
    exigiria extraer entidades de la prosa — justo lo que este proyecto no acepta como
    sensor. `complete()`, que recibe el conjunto ya enumerado, si la ve.
    """
    lowered = " ".join(answer.lower().split())
    return [k for k in domain_keys if " ".join(str(k).lower().split()) in lowered]


def complete_answer(
    answer: str,
    domain_keys: list[str],
    base: BeliefBase | None = None,
    proposition: str = "el dominio declarado por el caller",
) -> CompletenessVerdict:
    """`C-COMPLETE` sobre una respuesta en prosa contra un dominio declarado.

    Atajo sobre `complete()` para el caso `from_question`: el dominio viene enunciado, asi
    que se asienta como `COMPUTED` —el caller lo declaro, igual que declara `irreversible`,
    y credencia 1.0 porque no hay nada que estimar— y se compara contra lo que la respuesta
    atiende.
    """
    if base is None:
        base = BeliefBase()
        base.assert_(Belief(proposition, list(domain_keys), 1.0, Provenance.COMPUTED))
    return complete(addressed(answer, domain_keys), proposition, base)


def verify_coverage(task: dict[str, Any], answer: str) -> dict[str, Any] | None:
    """`C-COMPLETE` sobre una tarea, cuando corresponde. `None` cuando NO corresponde.

    EL DISPARADOR, TIPADO. Son DOS condiciones y ninguna alcanza sola:

      la tarea EXIGE cobertura        `coverage_demanded == "exhaustive"`
      y su dominio es ENUMERABLE      `completeness_domain == "from_question"`

    La primera sin la segunda es el caso que la leccion 8.7 midio y que no tiene salida:
    en una celda de dominio `semantic` —«listame todos los que tienen el rol R»— enumerar
    el dominio ES la extraccion, asi que el contrato no verificaria al paradigma, lo
    reemplazaria. Y en una de dominio `from_scope` el dominio barato son las unidades,
    que se midio que NO predice correccion (`+0,018`).

    La segunda sin la primera es una tarea que enumera algo y no pide exhaustividad: ahi
    exigir cobertura es pagar de mas por nada.

    `None` significa **sin contrato**, y se distingue de un contrato cumplido: un
    booleano las volveria indistinguibles y son opuestas — «nadie verifico» contra «se
    verifico y paso».

    RETROCOMPATIBLE POR DISENO. Una tarea de un corpus anterior a `REQUEST_DEMANDS` no
    declara los ejes; ahi el disparador se cae a la presencia de `domain_keys`, que es lo
    unico que se puede saber de ella, y NO se supone la demanda.
    """
    domain = task.get("domain_keys") or []
    if not domain:
        return None

    demanded = task.get("coverage_demanded")
    enumerable = task.get("completeness_domain")
    if demanded and enumerable:
        if demanded != "exhaustive" or enumerable != "from_question":
            return None

    return complete_answer(answer, list(domain)).as_dict()
