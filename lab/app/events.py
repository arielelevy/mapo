"""Los eventos que el motor emite mientras decide. Tipados, y con `yield`.

LA IDEA (autor, 2026-08-28): el codigo puede emitir sus PROPIAS acciones de razonamiento,
con `yield`, lo mas amigable posible para quien espera. Y no es una comodidad de interfaz:
es lo unico que este producto tiene y el modelo no.

POR QUE. El proveedor **esconde** el razonamiento del modelo — los tokens de razonamiento
se facturan y no aparecen en el contenido, y la documentacion dice explicitamente que
intentar extraerlos por otra via no esta soportado. O sea que de la deliberacion del modelo
no se puede mostrar nada.

El razonamiento de MAPO es lo contrario: **poda de factibilidad, creencias tipadas con
procedencia, resolucion del dial, veredictos de contrato**. Todo computado, todo
enunciable, y todo ANTES de que exista un token. Emitirlo mientras ocurre no es adornar la
espera — es mostrar la unica deliberacion auditable que hay en el sistema.

Y HAY UN ARGUMENTO DE LATENCIA MEDIDO. El TTFT del modelo es de cientos de milisegundos y
`dag_strategy` tarda 30 segundos por celda. La escalera de decision corre en microsegundos
y **sin gastar un token**: los primeros eventos salen antes de que el proveedor haya
recibido la primera llamada. Lo que el usuario ve primero es exactamente lo que el producto
sabe explicar mejor.

QUE NO ES. No es un log. Un log describe lo que paso para quien depure; esto es el
ARTEFACTO DE DECISION emitido en orden, y su union tipada es la misma que la consola ya
declara en `ui/src/types.ts`. Que el contrato ya existiera del lado del cliente y el motor
devolviera un bloque era la misma falla que este repo se pasa el dia encontrando.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# EL VOCABULARIO, CERRADO. Un tipo de evento que no este aca es un error, no un evento
# nuevo: la consola hace `switch` sobre esta union y un valor desconocido cae en el caso
# por defecto —o sea, se pierde en silencio, que es la falla que este proyecto no acepta.
#
# Estan en el orden en que ocurren, y ese orden es parte del contrato: `decision` no puede
# llegar despues de `token`, porque entonces lo que se mostro primero no fue una decision.
EVENT_TYPES: tuple[str, ...] = (
    "feasibility",     # que se podo por aritmetica, ANTES de cualquier inferencia
    "belief",          # una proposicion tipada, con su procedencia
    "assurance",       # el dial resuelto, y quien lo impuso
    "decision",        # el plan: paradigma, modelo, escalera, EXPLAIN
    "probe",           # una lectura pagada que supersede un estimado
    "paradigm.step",   # el patron avanzo un paso observable
    "token",           # texto de la respuesta
    "contract",        # un veredicto de contrato: emite, o no emite y por que
    "citation",        # una cita verificada contra el indice
    "usage",           # lo gastado hasta aca
    "retained",        # se produjo algo y NO se emite: el contrato lo retuvo
    "done",            # terminal: hay respuesta
    "gated",           # terminal: hace falta revision
    "deferred",        # terminal: no se contesta, y se dice por que
)

TERMINAL: frozenset[str] = frozenset({"done", "gated", "deferred"})


@dataclass(frozen=True)
class Event:
    """Un evento del stream. `type` sale del vocabulario cerrado; `data` es su carga.

    ES INMUTABLE a proposito. Un evento emitido es un hecho del registro: si un consumidor
    pudiera editarlo, el artefacto de decision dejaria de ser el mismo que se emitio.
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in EVENT_TYPES:
            raise ValueError(
                f"Tipo de evento {self.type!r} fuera del vocabulario. Es un enum cerrado: "
                f"un tipo nuevo que la consola no conoce cae en su caso por defecto y se "
                f"pierde en silencio. Agregalo a `EVENT_TYPES` y a `ui/src/types.ts`, o no "
                f"lo emitas. Conocidos: {list(EVENT_TYPES)}"
            )

    @property
    def is_terminal(self) -> bool:
        return self.type in TERMINAL

    def as_sse(self) -> str:
        """El evento en formato SSE. Una sola forma de serializarlo, y vive aca."""
        import json

        return (
            f"event: {self.type}\n"
            f"data: {json.dumps(self.data, ensure_ascii=False, default=str)}\n\n"
        )


def check_stream(eventos: list[Event]) -> None:
    """El contrato de ORDEN, verificado sobre un stream completo.

    TRES REGLAS, y cada una bloquea una forma distinta de que el stream mienta:

      1. termina en UN terminal, y exactamente uno. Cero significa que se corto sin
         decir como; dos, que se dijo dos veces cosas distintas
      2. nada despues del terminal. Un evento posterior describe trabajo que el
         consumidor ya dio por cerrado
      3. `decision` antes que cualquier `token`. Si el texto empieza antes de que la
         decision este emitida, lo que el usuario vio primero no fue una decision — y
         toda la tesis de este producto es que la decision viene primero

    Se levanta en vez de advertir: un stream mal ordenado se ve bien en pantalla, y esa
    es exactamente la clase de falla que no se detecta mirando.
    """
    terminales = [i for i, e in enumerate(eventos) if e.is_terminal]
    if len(terminales) != 1:
        raise ValueError(
            f"El stream tiene {len(terminales)} eventos terminales y tiene que tener uno. "
            f"Cero es cortarse sin decir como; dos es decir dos cosas distintas."
        )
    if terminales[0] != len(eventos) - 1:
        sobran = [e.type for e in eventos[terminales[0] + 1:]]
        raise ValueError(
            f"Hay eventos despues del terminal: {sobran}. Describen trabajo que el "
            f"consumidor ya dio por cerrado."
        )
    tipos = [e.type for e in eventos]
    if "token" in tipos:
        if "decision" not in tipos or tipos.index("decision") > tipos.index("token"):
            raise ValueError(
                "Salio texto antes de que la decision estuviera emitida. Lo que el "
                "usuario ve primero tiene que ser la decision: es la tesis entera del "
                "producto, y un stream que la invierte la desmiente en pantalla."
            )
