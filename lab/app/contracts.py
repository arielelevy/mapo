"""Contratos de afirmacion: el proyector que el codigo decide, y su residuo.

Implementa la clase C-NUM de `CONTRATOS.es.md` §2, que es la mas barata de las tres y la
unica que se puede cerrar sin parsear prosa.

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

from .beliefs import BeliefBase, Provenance

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
