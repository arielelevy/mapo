"""El catalogo de modelos, instanciado: un cliente por modelo, y una huella del conjunto.

POR QUE UN CLIENTE POR MODELO Y NO UNO QUE CAMBIA DE DEPLOYMENT. La huella —
`Settings.fingerprint()`— es la IDENTIDAD DE DECODIFICACION, y va adentro de la clave de
cache y adentro de cada fila del registro. Un solo cliente que alternara deployment tendria
UNA huella y DOS identidades atras: dos respuestas de modelos distintos compartirian clave
de cache, y el registro no podria decir cual corrio. Un cliente por modelo hace la
correspondencia huella-modelo 1:1 por construccion, que es mas barato que sostenerla con
una regla.

LA HUELLA DEL CONJUNTO, Y POR QUE HACE FALTA UNA. `load_rows` se niega a leer un archivo
que mezcla decodificaciones, y esta bien: promediar entre modelos no mide un paradigma,
mide el modelo. Pero una corrida RUTEADA usa dos modelos a proposito — esa es toda su
tesis— asi que sus filas tendrian dos huellas y la guarda las rechazaria.

La salida no es debilitar la guarda: es que la unidad de analisis cambio. En una grilla
fija se mide un PARADIGMA y el modelo es constante; en una corrida ruteada se mide el
ROUTER, y el modelo es parte de lo que decide. Son dos experimentos distintos, van a
archivos distintos, y por eso el pool tiene su propia huella — que es la del conjunto, no
la de ninguno de sus miembros. Asi un archivo ruteado es internamente coherente y sigue
siendo incomparable con uno de grilla fija, que es exactamente lo que se quiere.

QUE NO HACE. No elige. Elegir es del router (`Router.plan(models=...)`), que aplica el
piso del dial y despues el presupuesto. Esto solo tiene los clientes listos.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace

from .config import Settings
from .llm import LLMClient
from . import models as _models
from .models import Model

# EL CATALOGO SE LEE AL LLAMAR, no al importar. `from .models import CATALOG` liga la tupla
# en tiempo de import, asi que cualquier cambio posterior al catalogo —un modelo nuevo, uno
# retirado— no llegaria nunca hasta que el proceso se reinicie. Es una trampa silenciosa: el
# sistema andaria con un catalogo viejo sin que nada avise.


@dataclass(frozen=True)
class PooledModel:
    """Un modelo del catalogo con su cliente y su deployment real."""

    model: Model
    deployment: str
    client: LLMClient
    fingerprint: str


class ModelPool:
    """Los clientes del catalogo, y la huella del conjunto.

    `deployments` mapea el nombre LOGICO del catalogo —`fast`, `deep`— al nombre del
    deployment real. La indireccion no es ceremonia: el catalogo declara CAPACIDAD y
    PRECIO, que son propiedades del modelo, y el deployment es donde esta desplegado, que
    es una propiedad de la infraestructura. Mezclarlas obligaria a tocar la capa de
    decision cada vez que alguien redespliega.
    """

    def __init__(
        self,
        base: Settings,
        deployments: dict[str, str],
        sealed: bool = False,
    ) -> None:
        catalogo = _models.CATALOG
        conocidos = {m.name for m in catalogo}
        desconocidos = sorted(set(deployments) - conocidos)
        if desconocidos:
            raise ValueError(
                f"{desconocidos} no estan en el catalogo de modelos ({sorted(conocidos)}). "
                f"Un deployment sin modelo declarado no tiene capacidad ni arancel, asi "
                f"que la decision no lo puede podar ni gatear: se levanta."
            )
        if not deployments:
            raise ValueError(
                "Un pool vacio no es un pool de un modelo: es una configuracion sin "
                "modelos. Se levanta en vez de caer al de la base."
            )

        self._miembros: dict[str, PooledModel] = {}
        # Modelos que razonan al default y NO dejan fijar el nivel junto con herramientas.
        # Van al `describe()`: es presupuesto que decide el modelo y no la configuracion,
        # y eso tiene que estar en el registro y no en la cabeza de quien configuro.
        self._sin_control_de_esfuerzo: list[str] = []
        for m in catalogo:
            if m.name not in deployments:
                continue
            ajustes = replace(base, chat_deployment=deployments[m.name])
            if not m.explicit_effort_with_tools:
                # NI SE LEVANTA NI ES UNA COMPRA DUDOSA — las dos versiones anteriores de
                # esta guarda estaban mal, y las dos por medir con un prompt trivial.
                #
                # Lo medido: estos modelos corren con herramientas Y RAZONANDO al default
                # (66 tokens de razonamiento). Lo que rechazan es que se les pase el nivel
                # explicito junto con tools. Asi que lo que se registra no es una carencia
                # sino una PERDIDA DE CONTROL: el nivel de razonamiento —y por lo tanto
                # parte del costo, porque esos tokens se facturan como salida— lo decide
                # el modelo y no la configuracion.
                self._sin_control_de_esfuerzo.append(m.name)
            self._miembros[m.name] = PooledModel(
                model=m,
                deployment=deployments[m.name],
                client=LLMClient(ajustes, sealed=sealed),
                fingerprint=ajustes.fingerprint(),
            )

    @property
    def models(self) -> tuple[Model, ...]:
        """El catalogo EFECTIVO: solo los que tienen deployment, en orden de capacidad.

        Ordenados de menor a mayor a proposito: el router recorre candidatos y el empate
        —misma utilidad esperada— cae del lado barato sin una regla extra que lo diga.
        """
        return tuple(
            self._miembros[n].model
            for n in sorted(self._miembros, key=lambda k: self._miembros[k].model.capability)
        )

    def client_for(self, name: str) -> LLMClient:
        """El cliente de ese modelo. Levanta si no esta desplegado.

        Sin default: caer al barato callado es como se rutea al modelo equivocado una
        accion que el dial mando al caro, y nadie se entera hasta la auditoria.
        """
        if name not in self._miembros:
            raise ValueError(
                f"El modelo {name!r} no tiene deployment en este pool "
                f"({sorted(self._miembros)}). Se levanta en vez de elegir otro: un plan "
                f"que dice `deep` y corre en `fast` es un registro que miente."
            )
        return self._miembros[name].client

    def deployment_for(self, name: str) -> str:
        if name not in self._miembros:
            raise ValueError(f"El modelo {name!r} no tiene deployment en este pool.")
        return self._miembros[name].deployment

    def fingerprint(self) -> str:
        """La identidad del CONJUNTO. No es la de ninguno de sus miembros.

        Se construye de las huellas ordenadas para que no dependa del orden de
        configuracion, y se acorta a 16 caracteres porque va en cada fila: lo que importa
        es que dos pools distintos den huellas distintas, no poder leerla a ojo.
        """
        partes = "|".join(
            f"{n}={self._miembros[n].fingerprint}" for n in sorted(self._miembros)
        )
        corto = hashlib.sha256(partes.encode("utf-8")).hexdigest()[:16]
        return f"pool[{','.join(sorted(self._miembros))}]#{corto}"

    def describe(self) -> dict[str, object]:
        """Lo que va al EXPLAIN y al reporte: que habia disponible cuando se decidio."""
        return {
            "fingerprint": self.fingerprint(),
            "effort_not_controllable_with_tools": sorted(self._sin_control_de_esfuerzo),
            "members": {
                n: {
                    "deployment": p.deployment,
                    "capability": p.model.capability.name,
                    "context_tokens": p.model.context_tokens,
                    "tariff": p.model.tariff.name,
                    "fingerprint": p.fingerprint,
                }
                for n, p in sorted(self._miembros.items())
            },
        }
