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
from .tariffs import role_detail


class Capability(IntEnum):
    """Piso ordinal de capacidad. ORDINAL y no cardinal a proposito.

    Un numero cardinal invitaria a promediarlo, a meterlo en una utilidad o a compensarlo
    con costo — «este modelo es 0,7 de bueno pero sale la mitad»— y eso es exactamente
    meter la calidad adentro del presupuesto. Un orden solo permite comparar contra un
    piso, que es la unica pregunta que el dial hace.

    TRES NIVELES Y NO DOS (decision del autor, 2026-08-28). Y agregar el tercero NO
    multiplica los bins de theta, que es la trampa de `P15`: theta aprende por REGION sobre
    PARADIGMAS, y el modelo se elige por REGLA —piso del dial, despues presupuesto—. Nada
    aprende por modelo, asi que el espacio de aprendizaje no cambia. Si algun dia theta
    aprendiera pares `(modelo, paradigma)`, esto pasaria a multiplicar y habria que
    volver a mirarlo.

    `MAX` NO ESTA EN EL CATALOGO POR DEFECTO. Ese es el sentido de «excepcional»: no es un
    escalon mas caro al que se llega subiendo, es uno que hay que PEDIR. Ver `EXCEPTIONAL`.
    """

    FAST = 1
    DEEP = 2
    MAX = 3


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
    # RAZONA POR SU CUENTA al default, sin que nadie se lo pida. Medido, no leido:
    #
    #   prompt dificil, sin tools    nano 0 tokens de razonamiento · terra 70
    #   prompt dificil, CON tools    nano 0                        · terra 66
    #   prompt trivial               los dos 0
    #
    # O sea que en los `5.6` el razonamiento es INTERNO Y ADAPTATIVO: el modelo decide
    # cuando hacerlo, y lo hace tambien mientras usa herramientas. Y esos tokens se
    # facturan como SALIDA, asi que comparar «precio por token» contra un modelo que no
    # razona compara dos unidades distintas.
    reasons_by_default: bool = False

    # SI ACEPTA `reasoning_effort` EXPLICITO JUNTO CON HERRAMIENTAS. Esta es la
    # restriccion real, y no es la que la documentacion sugiere a primera lectura: los
    # `5.6` corren con tools y RAZONANDO al default. Lo que rechazan —HTTP 400, incluso
    # con `low`— es que se les pase el nivel explicito al mismo tiempo que las tools.
    #
    # La consecuencia practica es una asimetria util: en `nano` el nivel de razonamiento
    # es un FACTOR medible hoy sobre el regimen del producto (con tools, `low` da 35
    # tokens de razonamiento y funciona); en los `5.6` no se puede tocar sin la Responses
    # API — hay que aceptar el que el modelo elija.
    explicit_effort_with_tools: bool = True

    def __post_init__(self) -> None:
        if self.context_tokens <= 0:
            raise ValueError("Una ventana de contexto no puede ser <= 0.")

    def money_for(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Plata de una proyeccion. Se usa ANTES de correr, sobre tokens proyectados."""
        return (
            prompt_tokens * self.tariff.prompt_per_mtok
            + completion_tokens * self.tariff.completion_per_mtok
        ) / 1_000_000


# EL CATALOGO SE DERIVA DEL JSON, no se escribe aca. La ventana, si razona solo y si
# acepta el nivel explicito con herramientas son propiedades del MODELO, y que modelo
# juega cada papel lo decide `config/tariffs.json`. Hardcodearlas por papel hacia que
# cambiar `fast: nano` por `fast: luna` heredara las propiedades de nano y mintiera.
def _from_role(papel: str, capability: Capability) -> Model:
    d = role_detail(papel)
    if d.context_input_tokens is None:
        raise ValueError(
            f"El modelo {d.name!r} no declara `context_input_tokens`. La cota de ventana "
            f"de `check_pair` la consume: sin ella, o se inventa un numero o se admite "
            f"cualquier plan. Se levanta."
        )
    return Model(
        name=papel,
        context_tokens=d.context_input_tokens,
        tariff=d.tariff,
        capability=capability,
        reasons_by_default=d.reasons_by_default,
        explicit_effort_with_tools=d.explicit_effort_with_tools,
    )


FAST = _from_role("fast", Capability.FAST)
DEEP = _from_role("deep", Capability.DEEP)
# EXCEPCIONAL: 25x el barato, y fuera del catalogo por defecto.
#
# POR QUE FUERA Y NO COMO TERCER ESCALON. Un escalon al que se llega subiendo se alcanza
# solo: basta una tarea que el dial mande a A3 y que el presupuesto tolere. «Excepcional»
# significa que alguien lo PIDE, y eso es una propiedad del request, no del catalogo.
#
# Y la regla del repo es no comprar mas garantia de la que la medicion justifica: hoy NO
# HAY NINGUNA MEDICION que distinga `sol` de `terra`.
MAX = _from_role("max", Capability.MAX)


# El catalogo POR DEFECTO. Una lista y no un dict porque el orden importa: el ruteo
# recorre candidatos, y recorrerlos del mas barato al mas caro hace que el empate —misma
# utilidad esperada— caiga del lado barato sin una regla extra.
CATALOG: tuple[Model, ...] = (FAST, DEEP)

# Los que existen pero hay que PEDIR. `by_name` los encuentra —asi un pool puede armarlos
# si la configuracion los declara— y el ruteo no los ve salvo que el request los habilite.
EXCEPTIONAL: tuple[Model, ...] = (MAX,)

# Todo lo declarado, para que `by_name` no mienta sobre lo que existe.
ALL_MODELS: tuple[Model, ...] = CATALOG + EXCEPTIONAL


def by_name(name: str) -> Model:
    """El modelo declarado con ese nombre. Levanta si no existe.

    Sin default: un nombre que no esta en el catalogo es un error de configuracion, y
    caer al mas barato callado es como se rutea una accion irreversible al modelo
    equivocado sin que nadie se entere.
    """
    for m in ALL_MODELS:
        if m.name == name:
            return m
    raise ValueError(
        f"{name!r} no esta declarado ({[m.name for m in ALL_MODELS]}). "
        f"Se levanta en vez de elegir uno: el modelo es una ACCION, y elegirla por "
        f"omision es la que nadie audita."
    )
