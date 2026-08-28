"""Asociaciones entre pares ordenados, con el ciclo de vida del peso que ya existe.

POR QUE ESTO NO CAE BAJO LA DEMOSTRACION DE REDUNDANCIA. Esta probado que el peso
Hebbiano por `(region, paradigma)` no puede mejorar la seleccion: en el punto fijo es
`w* = 1,6p - 0,6`, monotona en la tasa de victorias, y el router ya ordena por esa tasa.
Una transformacion monotona no cambia un argmax.

Esa demostracion acota **un uso**, no la pieza. Depende de que el peso sea una estadistica
MARGINAL de un brazo, y una asociacion entre PARES no lo es: `(a -> b)` no se recupera de
las frecuencias de `a` y de `b` por separado. Justamente por eso el orden puede llevar
informacion que el conteo no lleva — «busco, leyo, busco, leyo» y «busco, busco, leyo,
leyo» tienen el mismo histograma y son dos politicas distintas.

QUE SE REFUERZA, Y POR QUE NO ES LA FRECUENCIA. Reforzar por frecuencia aprenderia los
HABITOS del modelo, que es exactamente lo que el modelo ya hace: no compra nada. Se
refuerza por RESULTADO — una transicion que aparecio en un episodio bueno sube, en uno
malo baja. La correlacion no es causalidad y no se afirma que lo sea: alcanza para un
prior, que es todo lo que se le va a pedir.

QUE NO ES, Y ESTO NO SE NEGOCIA. **No es una creencia.** El reticulo es
`ASSUMED < ELICITED < OBSERVED < COMPUTED` y las acciones irreversibles exigen los dos de
arriba precisamente para dejar afuera a la estadistica. Una asociacion aprendida es
aritmetica sobre un ledger, asi que PARECE `COMPUTED` — y con ese rango una regularidad
estadistica podria gatear una accion irreversible, que es lo que el piso existe para
impedir. No es una observacion sobre ESTE request: es un prior sobre requests parecidos.
Hasta que el reticulo tenga un rango por debajo de `OBSERVED` (pendiente P-2d), esto se
expone como ESTADISTICA y nada mas.

EL CICLO DE VIDA SE REUSA, NO SE REINVENTA. Los mismos hiperparametros que `policy.py`:
acotado, decae, con piso, y se poda lo que nunca se observo. Esa maquinaria ya esta
probada sobre `(region, paradigma)`; lo unico que cambia es la clave.
"""

from __future__ import annotations

from .beliefs import Belief, Provenance, Scope
from dataclasses import dataclass, field
from typing import Any, Iterable

from .policy import DECAY, LEARNING_RATE, PRIOR_WEIGHT, WEIGHT_MAX, WEIGHT_MIN

# Marca el borde de una secuencia. Que una herramienta abra o cierre es informacion — un
# paradigma que SIEMPRE arranca buscando es distinto de uno que a veces arranca leyendo.
START = "^"
END = "$"


@dataclass
class Link:
    """Lo aprendido sobre una transicion."""

    weight: float = PRIOR_WEIGHT
    observations: int = 0
    good: int = 0

    @property
    def success_rate(self) -> float:
        return self.good / self.observations if self.observations else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "weight": round(self.weight, 5),
            "observations": self.observations,
            "good": self.good,
            "success_rate": round(self.success_rate, 4),
        }


@dataclass
class AssociationTable:
    """Transiciones `(a -> b)` dentro de un contexto: una region, un paradigma, lo que sea.

    El contexto es parte de la clave y no un filtro posterior, porque «despues de buscar
    conviene leer» puede ser cierto en una region y falso en otra, y promediarlas
    esconderia justo la diferencia que hace util a la tabla.
    """

    links: dict[tuple[str, str, str], Link] = field(default_factory=dict)

    def observe(self, context: str, sequence: Iterable[str], was_good: bool) -> int:
        """Registrar una secuencia completa. Devuelve cuantas transiciones vio."""
        steps = [START, *sequence, END]
        seen = 0
        for a, b in zip(steps, steps[1:]):
            link = self.links.setdefault((context, a, b), Link())
            # Mismo delta que la regla de paradigmas: el exito refuerza mas de lo que el
            # fracaso castiga, porque una transicion buena en un episodio malo sigue
            # pudiendo ser buena y lo contrario es menos frecuente.
            delta = 0.5 if was_good else -0.3
            link.weight = max(
                WEIGHT_MIN, min(WEIGHT_MAX, (1.0 - DECAY) * link.weight + LEARNING_RATE * delta)
            )
            link.observations += 1
            link.good += 1 if was_good else 0
            seen += 1
        return seen

    def strength(self, context: str, a: str, b: str) -> float | None:
        """Cuanto sostiene el registro esta transicion, o `None` si no la vio nunca.

        `None` y `0.0` son cosas distintas y se distinguen a proposito: «nunca lo vi» no
        es «lo vi y sale mal». Colapsarlas es el mismo error que un piso que aplasta a
        todos los brazos debiles hasta volverlos indistinguibles.
        """
        link = self.links.get((context, a, b))
        return None if link is None else link.weight

    def successors(self, context: str, a: str) -> list[tuple[str, float]]:
        """Que sigue despues de `a` en este contexto, de mas a menos sostenido."""
        out = [
            (b, link.weight)
            for (ctx, src, b), link in self.links.items()
            if ctx == context and src == a
        ]
        return sorted(out, key=lambda pair: -pair[1])

    def as_beliefs(self, context: str, source: str, floor: float = 0.0) -> list[Belief]:
        """Lo aprendido sobre `source`, como creencias que la base puede recibir.

        POR QUE ESTO NO PODIA EXISTIR HASTA AHORA. Una asociacion aprendida es aritmetica
        exacta sobre un ledger, asi que por procedencia **es** `COMPUTED` — negarlo seria
        mentir en un eje. Pero entrar como `COMPUTED` a secas dejaria que una regularidad
        estadistica gatee una accion irreversible, que es lo que el piso existe para
        impedir. Y bajarla a `ELICITED` mentiria en el otro sentido: no es la opinion de
        un modelo, es una frecuencia medida y reproducible.

        El reticulo no tenia el casillero porque el problema no era un casillero: ordenaba
        **como** se obtuvo una creencia cuando ademas hacia falta **sobre que es**. Con
        `Scope.POPULATION` la asociacion se declara honesta en los dos ejes y queda
        estructuralmente fuera de lo irreversible sin degradar su procedencia.

        `floor` filtra: por debajo de el la transicion no se afirma. `0.0` deja pasar
        todo lo observado, que es distinto de lo nunca visto — eso no aparece.
        """
        out: list[Belief] = []
        for successor, weight in self.successors(context, source):
            if weight < floor:
                continue
            link = self.links[(context, source, successor)]
            # LA PROPOSICION ES LA MEDICION, NO LA RECOMENDACION, y el invariante de
            # `Belief` es lo que obligo a verlo: `COMPUTED` con credencia < 1 seria una
            # procedencia mentirosa —«esto es una funcion pura del payload» y a la vez
            # «no estoy seguro»—.
            #
            # Lo que el ledger sostiene con certeza no es que convenga `successor`: es
            # que su fuerza medida vale lo que vale. Eso SI es aritmetica exacta, asi que
            # entra a credencia 1,0 con su valor adentro. Quien quiera actuar lee el
            # valor y decide; la creencia no decide por el.
            out.append(Belief(
                proposition=f"fuerza medida de `{source}` -> `{successor}`",
                value=round(weight, 5),
                credence=1.0,
                provenance=Provenance.COMPUTED,
                evidence=(
                    f"{link.good} de {link.observations} episodios en `{context}` "
                    f"con esa transicion terminaron bien"
                ),
                # LA MITAD QUE HACE ADMISIBLE A LA OTRA: es un prior sobre pedidos
                # parecidos, no una observacion sobre este.
                scope=Scope.POPULATION,
            ))
        return out

    def prune(self) -> list[tuple[str, str, str]]:
        """Sacar lo que llego al piso SIN haberse observado nunca.

        La misma regla que la poda de stats, y por la misma razon: nunca se poda por peso
        solo, porque una transicion observada es evidencia por desfavorable que sea.
        """
        dead = [k for k, link in self.links.items()
                if link.weight <= WEIGHT_MIN and link.observations == 0]
        for key in dead:
            del self.links[key]
        return dead

    def as_dict(self) -> dict[str, Any]:
        return {
            "links": {
                f"{ctx}|{a}|{b}": link.as_dict()
                for (ctx, a, b), link in sorted(self.links.items())
            }
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AssociationTable":
        table = cls()
        for key, body in (raw.get("links") or {}).items():
            ctx, a, b = key.split("|", 2)
            table.links[(ctx, a, b)] = Link(
                weight=float(body["weight"]),
                observations=int(body["observations"]),
                good=int(body["good"]),
            )
        return table
