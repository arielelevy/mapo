"""EL CATÁLOGO DE CAPACIDADES: qué **puede hacer** cada brazo, declarado desde el código.

LA TESIS, Y ES LA QUE `P15` REFUTÓ POR EL LADO CONTRARIO. El catálogo nombra a sus brazos por
su estructura de control —«plan-ejecuta», «supervisor», «cadena»— y `P15` intentó mapear
**ontología de la pregunta → nombre de paradigma**. Perdió `−0,087` contra el mejor fijo. El
paso que faltaba es que **la ontología no selecciona un paradigma: selecciona CAPACIDADES**, y
un paradigma es un paquete de capacidades que puede tener o no tener.

    pregunta  →  qué capacidades EXIGE  →  qué brazos las tienen  →  el más barato de ésos

El eslabón del medio es el que no existía. Sin él, «cadena acoplada ⇒ usá `pointer_chase`» es
una asociación que el registro puede desmentir y nada explica; con él, «cadena acoplada ⇒
exige `RESOLVER_REFERENCIA` + `LARGO_GOBERNADO_POR_CODIGO`» es una afirmación **verificable
contra el código de cada brazo**, y sobrevive a que el brazo se reescriba.

POR QUÉ SE DECLARA Y NO SE MIDE. Una capacidad es una propiedad del código, no del registro:
se lee del paradigma y por eso **vale para un brazo que todavía no se corrió**. Una tabla de
utilidades sólo sabe de los que se midieron. Esto es lo que permite podar antes de gastar.

Y POR QUÉ ESO NO ES HACER TRAMPA. Declarar no es opinar: cada entrada dice **dónde** en el
código se ve, y `bench/audits/_audit_capacidades.py` contrasta las declaraciones contra el
registro — un brazo que declara `ABSTIENE_SIN_PRUEBA` y nunca se abstuvo tiene una declaración
falsa, y eso es un defecto que se ve.

LAS DIEZ, Y LAS CUATRO ÚLTIMAS SON DEL 2026-08-30. Las seis primeras estaban implícitas en el
espacio de capacidades de tres ejes; las cuatro últimas las destapó resolver `C3`, y ninguna
es visible desde la taxonomía de control de flujo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ── LAS CAPACIDADES ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Capacidad:
    """Una capacidad, con su definición y la medición que la justifica.

    `por_que_importa` no es documentación de cortesía: es el campo que impide que esto se
    convierta en una taxonomía inventada. Cada capacidad entra al catálogo porque hay un
    número que se explica con ella y no se explica sin ella, y ese número va acá adentro.
    Una capacidad sin ese campo lleno es vocabulario.
    """

    nombre: str
    que_es: str
    por_que_importa: str


CATALOGO: tuple[Capacidad, ...] = (
    Capacidad(
        "PAYLOAD_COMPLETO",
        "el modelo puede tener TODO el alcance en una sola llamada",
        "una contradicción entre dos unidades es invisible si ninguna llamada tiene el par: "
        "`handoff` LEE las dos y saca 0,067 porque cada sub-agente ve su mitad",
    ),
    Capacidad(
        "ADAPTA",
        "puede cambiar lo que pide DESPUÉS de ver un resultado",
        "`rewoo` puede tener dos unidades juntas y saca 0,133: le falta poder elegir CUÁLES "
        "dos, que exige ver un resultado antes de pedir el siguiente",
    ),
    Capacidad(
        "COSTO_NO_ESCALA_CON_ALCANCE",
        "su costo no es función de cuánto material hay",
        "es la única propiedad que predice quién sobrevive al ancho: `rewoo` es el único "
        "brazo que SUBE de 5 a 60 unidades (+0,06) mientras todos los demás caen",
    ),
    Capacidad(
        "LECTURA_SIN_PERDIDA",
        "lo que lee entra al modelo sin pasar por una representación más chica",
        "cada gist, ventana recortada o índice de entidades tira información ANTES de saber "
        "cuál hacía falta. Con el material a la vista `react` da 0,970 y `gist_reader` "
        "0,594 — peor que cuando no lo vio todo",
    ),
    Capacidad(
        "CONTEXT_VISION",
        "cada llamada ve TODO lo que el request leyó hasta ahí, en crudo o compactado: ninguna "
        "vuelta pierde lo que trajo la anterior",
        "es distinta de PAYLOAD_COMPLETO (una llamada puede tener todo el alcance) y de ADAPTA "
        "(puede cambiar lo que pide): `supervisor` adapta y no la tiene, porque cada sub-agente "
        "arranca con una ventana de 8; `rewoo` tiene el payload en el solver y no la tiene, "
        "porque sus pasos no se ven entre sí. Compactar el hilo NO la quita: una nota o un stub "
        "que apunta a lo leído sigue siendo visión del hilo entero, en otra forma. Es la "
        "propiedad que la ley de costo mide desde la factura: el costo POR LLAMADA de `react` "
        "sube 3,7-3,9× entre 3 y 12 llamadas porque reenvía el hilo entero (§6.4.3), y la que "
        "explica que el paradigma determine cuánta evidencia llega a la llamada que responde",
    ),
    Capacidad(
        "AUTOCOMPACTA",
        "el arnés reduce el hilo por su cuenta, de forma determinista, sin pedirle disciplina al "
        "modelo: lo ya leído y anotado se reemplaza por una referencia",
        "es la única forma medida de tener CONTEXT_VISION sin pagar el hilo entero en cada "
        "vuelta. Ofrecida como herramienta opcional (`cognitive`), el modelo escribió 1 nota, "
        "compactó una vez y nunca planificó en 28 filas: la disciplina voluntaria no ocurre. "
        "`manage_history` (`managed`) la hace incondicional desde el código. Está implementada "
        "y NO corrió en la campaña: ningún brazo del rectángulo la tiene, así que hoy es un "
        "hueco del catálogo del mismo tipo que `ausencia`, y el brazo que la tendría es "
        "`react` sobre la superficie `managed`",
    ),
    Capacidad(
        "COBERTURA_GARANTIZADA",
        "puede garantizar que tocó todas las unidades del alcance",
        "una pregunta con cobertura exhaustiva declarada no la puede contestar un brazo que "
        "sólo mira lo que la búsqueda le trajo",
    ),
    Capacidad(
        "VERIFICA_Y_REPLANIFICA",
        "chequea su propio estado y vuelve a planificar si no alcanza",
        "es lo que sostiene a `dag_strategy` en las cadenas: 12-19 iteraciones y hasta 3 "
        "replanificaciones donde los demás contestan a la primera",
    ),
    # ── las cuatro que destapó C3 (2026-08-30) ──────────────────────────────────
    Capacidad(
        "RESOLVER_REFERENCIA",
        "puede llevar una mención abreviada o variante hasta la unidad que la ancla",
        "el 100% de los saltos de C3 exige resolver una variante (`A. Vallejos` → `Agustina "
        "Vallejos`), y el 36,5% de las menciones del corpus son invisibles a una búsqueda "
        "del nombre completo. Sin esto, una cadena es un paseo",
    ),
    Capacidad(
        "LARGO_GOBERNADO_POR_CODIGO",
        "cuántas vueltas da lo decide el código a partir de la pregunta, no el modelo",
        "cuando la pregunta DECLARA el largo («upward 3 step(s)»), dejar que el modelo diga "
        "«ya está» es poner flujo de control en el sensor. El modo de falla dominante en C3 "
        "es cortar un escalón antes, no saltarse la cadena",
    ),
    Capacidad(
        "ELIGE_INDICE_POR_CONSULTA",
        "usa índice léxico para una entidad nombrada y híbrido para prosa",
        "un vector denso codifica *de qué habla* un texto, y sesenta memos con la misma "
        "plantilla hablan de lo mismo; el nombre propio es la parte que NO es semántica. "
        "Medido: la híbrida trae la unidad equivocada para `Ramiro Herrera`",
    ),
    Capacidad(
        "ABSTIENE_SIN_PRUEBA",
        "cuando no puede exhibir la evidencia que la respuesta exige, se niega",
        "es lo único que separa a `dag_strategy` en C3: 12 correctas, 3 abstenciones y CERO "
        "respuestas equivocadas. Los demás contestan igual. El banco puntúa las dos con "
        "0,000 y ahí es ciego",
    ),
    # ── la que NO tiene ningún brazo, y por eso vale declararla (2026-09-07) ────────
    Capacidad(
        "PERSISTE_ENTRE_REQUESTS",
        "lo que este pedido establece sobrevive a que se descargue el contexto, y cambia lo "
        "que hace un pedido POSTERIOR: no un hilo más largo, un trazo que otro request lee",
        "el número es EXTERNO y se declara como tal — `Memory Depth, Not Memory Access` "
        "(arXiv 2606.26806) mide el *depth flip*: recuperación 0,956-0,973 contra escritura "
        "selectiva 0,463-0,483 en recall factual corto, y 0,394-0,398 contra 0,812-0,904 en "
        "persistencia de meta tras descargar el contexto. Ningún lado gana los dos, así que "
        "el ganador lo decide un eje y no un brazo — que es la forma exacta de `P15`. "
        "**Cero de los doce brazos la tienen**: el banco es de turno único por construcción, "
        "y ésa es la afirmación, no una omisión",
    ),
)

NOMBRES = tuple(c.nombre for c in CATALOGO)

# ── QUÉ TIENE CADA BRAZO, y dónde se ve ─────────────────────────────────────────
#
# `None` en `PAYLOAD_COMPLETO` del espacio de tres ejes significaba «todas las unidades»; acá
# se vuelve un booleano explícito porque una capacidad se tiene o no se tiene.
TIENE: dict[str, set[str]] = {
    "direct": {"PAYLOAD_COMPLETO", "LECTURA_SIN_PERDIDA", "COBERTURA_GARANTIZADA",
               "CONTEXT_VISION"},                  # una sola llamada: trivialmente ve todo
    "react": {"PAYLOAD_COMPLETO", "ADAPTA", "LECTURA_SIN_PERDIDA", "CONTEXT_VISION"},
    "reflection": {"PAYLOAD_COMPLETO", "ADAPTA", "LECTURA_SIN_PERDIDA", "CONTEXT_VISION"},
    "dag_strategy": {"PAYLOAD_COMPLETO", "ADAPTA", "LECTURA_SIN_PERDIDA", "CONTEXT_VISION",
                     "VERIFICA_Y_REPLANIFICA", "ABSTIENE_SIN_PRUEBA"},   # via blackboard
    "rewoo": {"COSTO_NO_ESCALA_CON_ALCANCE", "LECTURA_SIN_PERDIDA"},
    "gist_reader": {"COBERTURA_GARANTIZADA"},          # el gist ES la pérdida
    "handoff": {"COBERTURA_GARANTIZADA"},              # cada sub-agente ve su mitad
    "supervisor": {"ADAPTA"},                          # ventana recortada de 8
    "pointer_chase": {"ADAPTA", "RESOLVER_REFERENCIA",
                      "LARGO_GOBERNADO_POR_CODIGO", "ELIGE_INDICE_POR_CONSULTA",
                      "ABSTIENE_SIN_PRUEBA"},          # las cuatro, desde 2026-08-30
    "graph_traverse": {"RESOLVER_REFERENCIA"},         # el índice de entidades, y nada más
    "extract_compute": {"COBERTURA_GARANTIZADA", "COSTO_NO_ESCALA_CON_ALCANCE"},
    "streaming_scan": {"COBERTURA_GARANTIZADA"},
}

# Dónde se ve cada declaración. Es lo que la vuelve auditable en vez de opinable.
EVIDENCIA: dict[tuple[str, str], str] = {
    ("pointer_chase", "RESOLVER_REFERENCIA"): "modern._primer_hit_que_nombra",
    ("pointer_chase", "LARGO_GOBERNADO_POR_CODIGO"): "modern.saltos_declarados",
    ("pointer_chase", "ELIGE_INDICE_POR_CONSULTA"): "features.indice_para",
    ("pointer_chase", "ABSTIENE_SIN_PRUEBA"): "modern: `sin_puntero_faltando_saltos`",
    ("dag_strategy", "VERIFICA_Y_REPLANIFICA"): "dag.DAG_MAX_REPLAN_ITERATIONS",
    ("dag_strategy", "ABSTIENE_SIN_PRUEBA"): "dag.DAG_READY_THRESHOLD",
    ("rewoo", "COSTO_NO_ESCALA_CON_ALCANCE"): "rewoo: dos llamadas, pase lo que pase",
    ("graph_traverse", "RESOLVER_REFERENCIA"): "modern: índice de entidades del grafo",
    ("supervisor", "ADAPTA"): "supervisor: despacha tras ver lo que volvió",
    ("react", "CONTEXT_VISION"): "paradigms.react: `messages.append` sin compactar en `basic`",
    ("reflection", "CONTEXT_VISION"): "paradigms.reflection: la revisión arrastra la conversación entera",
    ("dag_strategy", "CONTEXT_VISION"): "blackboard: cada hallazgo se renderiza en cada prompt",
    ("direct", "CONTEXT_VISION"): "paradigms.direct: una llamada con el material entero",
    # Y dónde se ve que NO la tienen los que adaptan o tienen payload: `supervisor` recorta a
    # 8 unidades por sub-agente en `_sub_surface`; `rewoo` fija el plan antes y sus pasos no
    # se ven entre sí. Van como comentario y no como entradas: EVIDENCIA declara lo que se tiene.
    # AUTOCOMPACTA no la tiene ningún brazo de la campaña: vive en `cognitive.manage_history`
    # y entra a TIENE cuando un brazo corra sobre la superficie `managed`.
}

# ── QUÉ EXIGE CADA EJE DE LA ONTOLOGÍA ──────────────────────────────────────────
#
# ES EL ESLABÓN QUE FALTABA, y va de la pregunta a la CAPACIDAD, nunca al nombre de un
# paradigma. Se declara por eje de `ONTOLOGIA_PREGUNTAS.es.md` y no por celda del corpus: una
# celda es un artefacto de este banco, un eje es una propiedad de la pregunta.
#
# **ES UNA HIPÓTESIS, NO UNA MEDICIÓN, Y EL REGISTRO YA LA CONTRADICE EN UN PUNTO.** Declara
# `cadena_acoplada ⇒ {RESOLVER_REFERENCIA, LARGO_GOBERNADO_POR_CODIGO, ADAPTA}`, y bajo esa
# regla el único candidato es `pointer_chase`. Pero `dag_strategy` saca **0,89** en C3 sin
# ninguna de las dos primeras. No es un error de la tabla: es que llega por **otra ruta** —
# `VERIFICA_Y_REPLANIFICA` le deja hacer hasta 17 búsquedas por celda y `ABSTIENE_SIN_PRUEBA`
# le impide contestar cuando no llegó (12 correctas, 3 abstenciones, cero equivocadas).
#
# O sea que a `EXIGE` le falta expresar **rutas alternativas**: hoy es una conjunción, y la
# realidad admite «A y B, o bien C y D». Se deja como conjunción y con la contradicción
# escrita, porque una tabla que se arregla sola para tapar su propio contraejemplo deja de
# ser falsable. `bench/audits/_audit_capacidades.py` es lo que falta para que esto se revise
# solo en vez de a mano.
#
# Y HAY UN HUECO QUE LA TABLA ENCUENTRA SIN CORRER NADA: `ausencia` no tiene NINGÚN brazo
# capaz — nadie junta `COBERTURA_GARANTIZADA` con `ABSTIENE_SIN_PRUEBA`. Eso es exactamente
# para lo que sirve declarar capacidades en vez de medir paradigmas: predice sobre un brazo
# que todavía no existe.
EXIGE: dict[str, set[str]] = {
    "cadena_acoplada": {"RESOLVER_REFERENCIA", "LARGO_GOBERNADO_POR_CODIGO", "ADAPTA"},
    "contradiccion": {"PAYLOAD_COMPLETO", "LECTURA_SIN_PERDIDA"},
    "cobertura_exhaustiva": {"COBERTURA_GARANTIZADA"},
    "ausencia": {"COBERTURA_GARANTIZADA", "ABSTIENE_SIN_PRUEBA"},
    "horizonte_desconocido": {"ADAPTA"},
    "entidad_nombrada": {"ELIGE_INDICE_POR_CONSULTA"},
    "material_mayor_que_ventana": {"COSTO_NO_ESCALA_CON_ALCANCE"},
    # EL SEGUNDO HUECO QUE LA TABLA ENCUENTRA SIN CORRER NADA (`C2`, 2026-09-07). Igual que
    # `ausencia`, `reuso_diferido` no tiene NINGÚN brazo capaz — y a diferencia de `ausencia`,
    # que necesita juntar dos capacidades que existen por separado, ésta no la tiene nadie
    # porque **ningún brazo del catálogo escribe nada que sobreviva al request**. Predice
    # sobre un brazo que todavía no existe, que es para lo que el catálogo se declaró.
    "reuso_diferido": {"PERSISTE_ENTRE_REQUESTS"},
}


def capaces(exigencias: set[str], plantel: Any = None) -> list[str]:
    """Los brazos que tienen TODAS las capacidades exigidas.

    Es una poda, no un ranking: entre los capaces decide el costo, la utilidad esperada o
    lo que la política diga. Devolver el conjunto y no un ganador es deliberado — mezclar
    «puede» con «conviene» es exactamente lo que `P15` hizo mal.
    """
    candidatos = plantel if plantel is not None else TIENE
    return sorted(p for p in candidatos if exigencias <= TIENE.get(p, set()))


def falta(paradigma: str, exigencias: set[str]) -> set[str]:
    """Qué le falta a este brazo para ser candidato. El EXPLAIN de una poda."""
    return exigencias - TIENE.get(paradigma, set())
