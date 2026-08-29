"""El modelo como ACCION: parte de lo que se elige, no de lo que se observa.

LA DECISION Y POR QUE ES ASI. El espacio de decision pasa de `paradigma` al par
`(modelo, paradigma)`. Meter el modelo en el VOCABULARIO DE REGION seria el error
opuesto, y ya esta medido lo que cuesta: agregar un cuarto segmento al vocabulario le
costo a theta toda su confianza —cada episodio cayo en un bin demasiado chico para cruzar
el piso de evidencia— y ese fue el mecanismo de `P15`.

  region      lo que la tarea ES. Se observa, y theta aprende POR region
  accion      lo que el motor HACE. Se elige, y theta aprende ENTRE acciones

El modelo se elige. Va del lado de la accion.

QUE APORTA UN MODELO A LA ARITMETICA, y son tres cosas distintas que se confundian en una:

  ventana     un techo DURO de contexto. Un modelo de ventana chica vuelve infactible a
              `direct` aunque el presupuesto del request lo permita: son dos cotas, y la
              factibilidad tiene que respetar la menor
  arancel     el precio, que convierte tokens proyectados en plata proyectada. Es lo que
              permite preguntar «este par entra en el presupuesto?» sin suponer que un
              token vale lo mismo en los dos modelos
  capacidad   un piso ORDINAL, y no es presupuesto: es una precondicion. Una accion
              irreversible no puede rutearse al modelo mas barato porque salga la cuenta

ESA TERCERA ES LA QUE RESUELVE «TOKEN Y CALIDAD». La calidad no entra al costo —seria
mezclar lo que se paga con lo que se compra—. Entra como restriccion, y el lugar donde
vive ya existe: el dial. A2/A3 ya restringen los paradigmas admisibles; ahora restringen
tambien los modelos.

LOS NUMEROS SON REFERENCIA. La ventana y el arancel son declaraciones del proveedor, no
mediciones nuestras: valen para preguntar «entra o no entra», no para publicar. La misma
advertencia que `tariffs.py`, por la misma razon.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .metrics import Tariff
from .tariffs import DETAILS, DEEP as ARANCEL_DEEP, NANO as ARANCEL_NANO


class Capability(IntEnum):
    """Piso ordinal de capacidad. ORDINAL y no cardinal a proposito.

    Un numero cardinal invitaria a promediarlo, a meterlo en una utilidad o a compensarlo
    con costo — «este modelo es 0,7 de bueno pero sale la mitad»— y eso es exactamente
    meter la calidad adentro del presupuesto. Un orden solo permite comparar contra un
    piso, que es la unica pregunta que el dial hace.
    """

    FAST = 1
    DEEP = 2


@dataclass(frozen=True)
class Model:
    """Un modelo como candidato de ruteo.

    `context_tokens` es la ventana declarada. `tariff` convierte tokens a plata.
    `capability` es el piso ordinal que el dial compara.
    """

    name: str
    # Ventana de ENTRADA. La total incluye 128.000 de salida que el prompt no puede usar.
    context_tokens: int
    tariff: Tariff
    capability: Capability
    # SI PUEDE LLAMAR HERRAMIENTAS SOBRE CHAT COMPLETIONS, que no es una obviedad y es lo
    # que decide si un modelo sirve para este producto.
    #
    # Los `gpt-5.6` son modelos de RAZONAMIENTO y la documentacion es explicita: soportan
    # Chat Completions y function tools, **pero no las dos a la vez** salvo con
    # `reasoning_effort='none'`. Para herramientas hay que usar la Responses API.
    #
    # Los trece paradigmas de este producto son bucles de herramientas sobre Chat
    # Completions. O sea que un `5.6` NO es reemplazo directo: o se apaga el razonamiento
    # —y entonces para que se paga— o se reescribe el cliente.
    tools_on_chat_completions: bool = True

    def __post_init__(self) -> None:
        if self.context_tokens <= 0:
            raise ValueError("Una ventana de contexto no puede ser <= 0.")

    def money_for(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Plata de una proyeccion. Se usa ANTES de correr, sobre tokens proyectados."""
        return (
            prompt_tokens * self.tariff.prompt_per_mtok
            + completion_tokens * self.tariff.completion_per_mtok
        ) / 1_000_000


# LOS DOS DEL CATALOGO. El precio ya NO es referencia: sale de `config/tariffs.json`,
# verificado contra la API de precios de Azure y contra la pagina, 2026-08-28. La VENTANA
# sigue siendo una declaracion del proveedor que no verifique — esta puesta a mano.
# `context_tokens` es la ventana de ENTRADA, no la total. La cota de `check_pair` compara
# contra `projected_tokens`, que son tokens de prompt: usar la total —400.000 y 1.050.000—
# admitiria planes que no entran, porque la salida ocupa 128.000 de esa cifra.
#
# Estaban las DOS mal: tenia 400.000 para los dos, que es la TOTAL de nano y ni siquiera la
# de terra. Verificado en la tabla de capacidades de Foundry, 2026-08-28.
FAST = Model(
    name="fast", context_tokens=272_000, tariff=ARANCEL_NANO, capability=Capability.FAST
)
DEEP = Model(
    name="deep", context_tokens=922_000, tariff=ARANCEL_DEEP,
    capability=Capability.DEEP,
    # FALSE, y esto BLOQUEA el ruteo de dos modelos tal como esta cableado hoy. No es un
    # detalle de configuracion: los paradigmas son bucles de herramientas sobre Chat
    # Completions, y este modelo no puede hacer las dos cosas a la vez.
    tools_on_chat_completions=False,
)

# El catalogo. Una lista y no un dict de nombre a modelo porque el orden importa: el
# ruteo recorre candidatos, y recorrerlos del mas barato al mas caro hace que el empate
# —misma utilidad esperada— caiga del lado barato sin necesidad de una regla extra.
CATALOG: tuple[Model, ...] = (FAST, DEEP)


def by_name(name: str) -> Model:
    """El modelo declarado con ese nombre. Levanta si no existe.

    Sin default: un nombre que no esta en el catalogo es un error de configuracion, y
    caer al mas barato callado es como se rutea una accion irreversible al modelo
    equivocado sin que nadie se entere.
    """
    for m in CATALOG:
        if m.name == name:
            return m
    raise ValueError(
        f"{name!r} no esta en el catalogo de modelos ({[m.name for m in CATALOG]}). "
        f"Se levanta en vez de elegir uno: el modelo es una ACCION, y elegirla por "
        f"omision es la que nadie audita."
    )
