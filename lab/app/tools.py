"""The retrieval tool surface.

WHAT THIS CORRECTS. The harness offered two tools: one blunt `search` and one `read`.
That flattens the decision the study exists to measure. Choosing WHICH retrieval
modality to use, at WHAT granularity, in WHAT sequence, and with how much BATCHING is
the agent's own business — it is the topology. A harness that pre-decides it by fusing
everything into one call has taken the decision away and then measures what is left.

Fusing BM25 and dense into a single hybrid tool was the specific mistake. Hybrid is the
right DEFAULT, but exposing only the fused view means the agent can never choose exact
matching when it needs an identifier, or meaning when it needs a paraphrase. Both are
exposed, plus the fused entry point, and the agent decides.

FOUR TOOLS, THREE GRANULARITIES. The granularity is the cost lever:

    search           hybrid, broad          -> SUMMARIES        cheapest per hit
    keyword_search   BM25, exact terms      -> HIGHLIGHTS       cheap, precise
    semantic_search  dense, by meaning      -> FULL TEXT        expensive, recall
    read             by id, batched         -> FULL TEXT        exact cost, no guessing

A paradigm that only ever calls `read` pays full price for everything. One that summarises
first and reads selectively pays less. That difference is a topology difference, and it
was invisible while every search returned the same fixed excerpt.

THE SEQUENCE IS TAUGHT, NOT ENFORCED. Descriptions state the snowball: find a value, then
search with that value to find where else it appears. Multi-hop questions are unanswerable
without it, and a tool surface that does not mention it measures whether the model
happens to invent it rather than whether the topology can exploit it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from typing import Any

from .board import Blackboard
from .cognitive import COGNITIVE_TOOL_SPECS, WorkingState
from .retrieval import CorpusView, LexicalRetriever, Retriever, tokenise

SUMMARY_CHARS = 180
# LA PODA DE MATERIAL, segundo brazo de `C-4`. `managed` compacta HISTORIA DE MENSAJES, asi
# que no toca a los paradigmas que arman un prompt grande de una sola vez — y ahi esta el
# mas caro por llamada de todo el catalogo: `gist_reader` mide 14.798 tokens por llamada y
# no lleva historia. Su contexto no crece con los turnos, crece con las UNIDADES.
#
# ES UN FACTOR Y NO UN PATRON, por la misma prueba que `terse_tools`: acorta lo que el
# modelo recibe sin cambiar quien decide la proxima accion ni cuantas llamadas hay. El
# grafo de control queda idéntico.
COMPACT_SUMMARY_CHARS = 60
HIGHLIGHT_WINDOW = 90
MAX_BATCH_READ = 10
# Rough chars-per-token. Only used to decide whether a bulk read fits, so an
# approximation is adequate and an exact tokeniser would be false precision.
CHARS_PER_TOKEN = 4
# Fraction of the task budget a single bulk read may consume. Leaves room for the
# rest of the conversation, which a read that used the entire budget would not.
BULK_READ_BUDGET_SHARE = 0.6

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": (
                "Broad hybrid search combining keywords and semantic similarity. "
                "Returns SUMMARIES of matching units, not their full text. "
                "Start here to find out which units exist and roughly what they say. "
                "For a targeted lookup prefer keyword_search or semantic_search. "
                "Use read with the unit_ids from these results to get full content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "description": "default 8"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "keyword_search",
            "description": (
                "Keyword search (BM25) — finds units containing EXACT terms. "
                "The right tool for identifiers, account numbers and proper names. "
                "Returns HIGHLIGHTS: short windows around each match, marked with "
                "<< >>. Cheaper than reading. When a highlight reveals a specific "
                "value, search again with THAT value to find where else it appears — "
                "this is how a chain of references is followed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "description": "default 8"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "semantic_search",
            "description": (
                "Semantic vector search — finds units by MEANING even when the exact "
                "words differ. Use it when the same fact may be phrased several ways. "
                "Returns FULL TEXT of matching units, so this IS reading them and costs "
                "accordingly. Complements keyword_search: running both covers more than "
                "either alone."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "description": "default 5"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": (
                "Read the full text of units by id. Pass MULTIPLE ids comma-separated "
                f"to read in one call, up to {MAX_BATCH_READ} — never call once per "
                "unit when several are needed. Use only ids returned by a search."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_ids": {
                        "type": "string",
                        "description": "one id, or several comma-separated",
                    }
                },
                "required": ["unit_ids"],
            },
        },
    },
]


# The accounting tools. Available under the variants that include them (`accounting` and,
# cumulatively, `cognitive`), so the conditions stay comparable.
ACCOUNTING_TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "coverage",
            "description": (
                "How much of the task you have actually seen: units read, units total, "
                "and which ids you have not touched. Call it before answering a "
                "question that asks for ALL of something or for a COUNT — an answer "
                "assembled from part of the units is wrong even when every part is "
                "right, and nothing else will tell you that."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_all",
            "description": (
                "Read every unit in the task in ONE call. Use it when you have decided "
                "you need most of them: reading the same units one call at a time costs "
                "several times more, because the whole conversation is resent each turn. "
                "If the full text does not fit the task budget it returns summaries of "
                "every unit instead, and tells you the real size — reading everything is "
                "not always available, and on a large task it is not."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


VARIANTS = ("basic", "accounting", "cognitive", "managed")

# The variants whose tool list includes the accounting tools. `cognitive` is cumulative
# (see specs_for), so anything gated on "has accounting" must name both or the model is
# offered a tool that dispatch then refuses.
ACCOUNTING_VARIANTS = ("accounting", "cognitive")


SEARCH_TOOLS = ("search", "keyword_search", "semantic_search")


# DESCRIPCIONES CORTAS: un FACTOR, no una limpieza.
#
# Las descripciones son 1.167 de los 2.135 caracteres de la spec — el 55% del payload.
# Acortarlas parece ahorro gratis y NO LO ES: es lo unico que el modelo lee para decidir
# QUE herramienta usar, asi que cambiarlas puede cambiar la eleccion. Entra cruzado, con
# prediccion registrada, y con la guarda de siempre: si baja la utilidad mas que el piso
# de ruido, ahorrar tokens eligiendo peor no es ahorrar.
#
# QUE SE CONSERVA Y QUE SE VA. Se conserva lo que DISCRIMINA —que devuelve cada una, y en
# que caso una gana a la otra— porque eso es la decision. Se va la prosa que instruye
# sobre como usarla bien, que es andamiaje por prompt, y este repo ya midio que el
# andamiaje por prompt no compra nada.
TERSE_DESCRIPTIONS: dict[str, str] = {
    "search": (
        "Hybrid search. Returns SUMMARIES, not full text. Use read for full content."
    ),
    "keyword_search": (
        "BM25. Finds EXACT terms: identifiers, numbers, proper names. Returns "
        "HIGHLIGHTS marked << >>."
    ),
    "semantic_search": (
        "Vector search. Finds by MEANING when wording differs. Returns FULL TEXT, so "
        "it costs like reading."
    ),
    "read": (
        "Full text of units by id. Pass MULTIPLE ids comma-separated, up to 10. Only "
        "ids returned by a search."
    ),
}


def _terse(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Las mismas specs con la descripcion corta, donde haya una declarada.

    Sin declarar, la spec pasa INTACTA. Recortar una descripcion que nadie escribio corta
    a ciegas justo el texto que discrimina, y eso no es el factor: es otro.
    """
    out = []
    for spec in specs:
        nombre = spec["function"]["name"]
        if nombre not in TERSE_DESCRIPTIONS:
            out.append(spec)
            continue
        copia = json.loads(json.dumps(spec))
        copia["function"]["description"] = TERSE_DESCRIPTIONS[nombre]
        out.append(copia)
    return out


def specs_for(
    variant: str,
    offer_read_all: bool = False,
    drop: tuple[str, ...] = (),
    terse: bool = False,
    offer_board: bool = False,
) -> list[dict[str, Any]]:
    """The tool list for a surface variant.

    `offer_read_all` es un FACTOR, apagado por defecto. `read_all` vive en las specs de
    contabilidad, asi que en `basic` —la variante de TODOS los estudios medidos— no
    existe: el modelo nunca pudo pedir el material entero aunque entrara comodo en su
    presupuesto. Eso no es una decision que alguien tomo midiendo; es una consecuencia de
    en que lista quedo la tool.

    Encenderlo lo ofrece SIN traer el resto de la contabilidad, para que lo que se mida
    sea `read_all` y no el paquete. La guarda de tamano no cambia: si el material no entra
    en su porcion del presupuesto, devuelve resumenes de todas las unidades y dice por que.
    

    Cumulative on purpose: `cognitive` includes the accounting tools, because the two
    address different failures and a variant that removed accounting to add notes would
    confound them. Each rung adds; none replaces.
    """
    # `drop` SACA herramientas de la lista, y esa es la diferencia con rechazarlas.
    #
    # P20 midio que rechazar una llamada NO le quita la decision al modelo: la re-emite
    # con otras palabras el 69% de las veces, asi que la regla le agrego una vuelta en vez
    # de quitar el desperdicio — y eso deja el flujo de control donde estaba, que es lo
    # que el invariante prohibe. Quitar la decision es NO OFRECER LA ACCION.
    def _keep(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        kept = [t for t in specs if t["function"]["name"] not in drop]
        return _terse(kept) if terse else kept

    read_all_spec = [
        t for t in ACCOUNTING_TOOL_SPECS if t["function"]["name"] == "read_all"
    ] if offer_read_all else []
    # EN TODAS LAS VARIANTES, no solo en una: el board es un factor cruzado contra los
    # patrones, y ofrecerlo en `cognitive` nada mas lo volveria una propiedad de esa
    # variante — que es exactamente el pliegue del que `F-2` queria salir.
    board_specs = list(BOARD_TOOL_SPECS) if offer_board else []

    if variant == "basic":
        return _keep(list(TOOL_SPECS) + read_all_spec + board_specs)
    if variant == "accounting":
        return _keep(list(TOOL_SPECS) + list(ACCOUNTING_TOOL_SPECS) + board_specs)
    if variant == "cognitive":
        return _keep(
            list(TOOL_SPECS)
            + list(ACCOUNTING_TOOL_SPECS)
            + list(COGNITIVE_TOOL_SPECS)
            + board_specs
        )
    if variant == "managed":
        # Same tools as basic, deliberately: the difference under test is not what the
        # model CAN call but what the harness DOES to the history. The cognitive arm
        # measured that voluntary self-management does not happen (1 note, 1 compaction,
        # 0 plans in 28 rows); `managed` moves the bookkeeping to the environment.
        return _keep(list(TOOL_SPECS) + read_all_spec + board_specs)
    raise ValueError(f"Unknown surface variant {variant!r}. Use one of {VARIANTS}.")


# QUE TOOL ESTA DISPONIBLE EN QUE VARIANTE — como funcion, y en UN solo lugar.
#
# Estaba decidido en tres `if self.variant ...` desparramados adentro de `dispatch`, cada
# uno con su forma —uno con `not in`, otro con `!=`, otro con `in`— y ninguno cerca de
# `specs_for`, que es quien decide que se le OFRECE al modelo. El propio comentario de
# `ACCOUNTING_VARIANTS` advertia el riesgo: «cualquier cosa gateada por "tiene
# contabilidad" tiene que nombrar a las dos o el modelo recibe una tool que dispatch
# despues rechaza». Una advertencia en prosa no lo impide; una tabla mas un test si.
#
# Y ADEMAS HAY GUARDA ARITMETICA, que es otra cosa y no la reemplaza. La disponibilidad
# dice si la tool EXISTE para esta variante; la guarda dice si la llamada CABE. `read_all`
# es el caso claro: existe donde se ofrece, y adentro decide granularidad segun el tamano
# contra el presupuesto declarado — texto completo si entra, resumenes de TODAS las
# unidades si no. Nunca trunca en silencio, que seria lo peor: el agente creeria haber
# visto todo y responderia desde un prefijo.

# EL BLACKBOARD COMO HERRAMIENTA, disponible para TODOS los patrones (decision del autor,
# 2026-08-28). Es la unica forma de que el estado compartido sea un FACTOR de verdad: un
# board que solo existe adentro de `dag_strategy` no se puede cruzar contra los demas, y
# entonces «el efecto dag_strategy» queda siendo la conjuncion de la topologia y el board.
#
# Y NO ES REDUNDANTE CON LA TRANSCRIPCION, que es lo que yo habia escrito y estaba mal. El
# registro lo desmiente: bajo presupuesto, el texto leido sobrevive al 28% hasta la llamada
# que responde (`note_retention`). Un apunte posteado al board sobrevive la compactacion;
# la transcripcion no. Para un agente solo, el board es DURABILIDAD, no repeticion.
#
# NO ES FLUJO DE CONTROL. Escribir y leer estado compartido es una ACCION, como buscar o
# leer. El invariante prohibe que el modelo decida que paradigma corre o si un gate pasa —
# no que tome notas.
BOARD_TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "post",
            "description": (
                "Post a finding to the shared board. It SURVIVES context compaction, "
                "so post anything you will need later and might lose. Keep it short "
                "and self-contained: a fact, not a reference to something above."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "finding": {
                        "type": "string",
                        "description": "One self-contained fact worth keeping.",
                    }
                },
                "required": ["finding"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "board",
            "description": (
                "Read everything posted to the shared board so far, including findings "
                "posted by other agents working on the same task."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


AVAILABLE_IN: dict[str, tuple[str, ...]] = {
    "read_all": ACCOUNTING_VARIANTS,
    "coverage": ACCOUNTING_VARIANTS,
    "note": ("cognitive",),
    "notes": ("cognitive",),
    "plan": ("cognitive",),
    "advance": ("cognitive",),
}


def available(
    name: str,
    variant: str,
    offer_read_all: bool = False,
    offer_board: bool = False,
) -> bool:
    """Si `name` esta disponible en `variant`. Lo no listado esta en todas.

    El factor `offer_read_all` entra ACA tambien y no solo en `specs_for`: si la
    disponibilidad no siguiera a la oferta, encender el factor le ofreceria al modelo una
    tool que dispatch despues rechaza — que es exactamente la separacion que §31 impide.
    """
    if name == "read_all" and offer_read_all:
        return True
    if name in ("post", "board"):
        # LA DISPONIBILIDAD SIGUE A LA OFERTA, igual que `read_all`. Si no la siguiera,
        # encender el factor ofreceria una tool que el dispatch despues rechaza — la
        # separacion que §31 impide.
        return offer_board
    return variant in AVAILABLE_IN.get(name, VARIANTS)


class ToolFailure(Exception):
    """Una llamada que el modelo hizo mal, distinta de un bug del harness — y de QUE TIPO.

    EL TIPO NO ES DECORACION: decide la pista (2026-08-30). El bucle compartido le pegaba
    a **toda** falla la misma pista —«usá sólo ids devueltos por una búsqueda»— que es
    correcta para una de las siete formas de fallar y desorienta en las otras seis. Un
    modelo al que le sobran ids en un batch, o que omitió un argumento, recibía un consejo
    que apunta al arreglo equivocado; y una pista equivocada es peor que ninguna, porque
    se sigue.

    Y ADEMAS SE CUENTA. Hasta hoy la superficie contaba **una** de las siete
    (`hallucinated`) y era ciega a las otras seis: no se podía preguntarle al registro con
    qué frecuencia el modelo erraba una llamada, ni de qué manera. Es la misma ceguera que
    dejó vivir 138 celdas de `rewoo` llamando a `read` sin leer nada — el efecto no lo
    miraba nadie.

    Los tipos son los que piden arreglos DISTINTOS, ni uno más:

      `id_inexistente`   un id que no está en el alcance -> el modelo inventó una cita
      `argumento`        falta un obligatorio, o vino con el tipo equivocado
      `batch`            pidió más ids de los que una llamada admite
      `no_ofrecida`      la herramienta existe pero no en esta superficie
      `desconocida`      el nombre no existe en ningún catálogo
      `fuera_de_alcance` una unidad que no es de esta tarea (lectura estructural)
    """

    def __init__(self, mensaje: str, kind: str = "otra") -> None:
        super().__init__(mensaje)
        self.kind = kind


# LA PISTA SALE DEL TIPO. Cada una nombra la accion que arregla ESA falla, y ninguna
# repite lo que el mensaje ya dice.
PISTA_POR_TIPO = {
    "id_inexistente": "Use only unit ids returned by a search.",
    "argumento": "Re-issue the call with every required argument, typed as declared.",
    "batch": "Split the ids across several calls.",
    "no_ofrecida": "Choose one of the tools listed as available.",
    "desconocida": "Choose one of the tools listed in the catalogue.",
    "fuera_de_alcance": "This unit belongs to another task; stay within the scope.",
}


def _summarise(text: str, compact: bool = False) -> str:
    """First substantive line plus a length hint.

    A summary has to be genuinely cheaper than the unit or the granularity ladder is
    decoration. The length hint is what lets an agent decide whether reading is worth it.

    LA PISTA DE LARGO SOBREVIVE A LA PODA, y eso no es un detalle: es lo unico que le
    permite al agente decidir si leer vale la pena. Podar el resumen hasta que deje de
    poder decidirlo no mediria poda de material, mediria ceguera.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    body = next((line for line in lines[1:] if len(line) > 30), lines[0] if lines else "")
    tope = COMPACT_SUMMARY_CHARS if compact else SUMMARY_CHARS
    return f"{body[:tope]} … [{len(text)} chars]"


def _highlight(text: str, terms: list[str]) -> str:
    """Windows around matches, marked, rather than the whole unit."""
    lowered = text.lower()
    spans: list[tuple[int, int]] = []
    for term in terms:
        for match in re.finditer(re.escape(term), lowered):
            spans.append((
                max(0, match.start() - HIGHLIGHT_WINDOW),
                min(len(text), match.end() + HIGHLIGHT_WINDOW),
            ))
    if not spans:
        return ""
    spans.sort()
    merged: list[list[int]] = [list(spans[0])]
    for start, end in spans[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return " … ".join(f"<<{text[a:b].strip()}>>" for a, b in merged[:3])


# LA SUPERFICIE ES PARTE DEL CONTRATO, igual que el analizador lexico (`ANALYZER_VERSION`).
#
# DE DONDE SALE (2026-08-29). `X-8` cambio COMPORTAMIENTO MEDIDO: `scoped()` no reataba
# `surfaced` ni los contadores de racha, asi que cada sub-agente arrancaba creyendo que
# nadie habia buscado nada. Arreglarlo hace que un sub-agente vea el agotamiento del
# retriever —y que el aviso de estancamiento pueda dispararse ahi, cosa que antes era
# imposible—, o sea que las filas de antes y las de despues NO son comparables.
#
# Y NINGUNA DE LAS CUATRO GUARDAS DE MEZCLA LO VE: miran decodificacion, brazo de
# recuperacion, analizador y vocabulario de region. Un cambio de codigo en la superficie
# no entra en ninguna, y la huella tampoco lo lleva —es modelo, api, esfuerzo, seed y
# max—. Sin esto, un `.jsonl` mezclaria dos regimenes en silencio.
SURFACE_VERSION = "v2-agotamiento-compartido"

# Y SOLO ESTOS DOS BRAZOS CAMBIARON, que es por que la guarda es por brazo y no por
# archivo. `scoped()` lo llaman `handoff` y `supervisor` y nadie mas: `dag_strategy` tiene
# sub-agentes pero les arma el alcance de otra forma, asi que su 62,5% de esterilidad ya
# era correcto. Levantar sobre el archivo entero convertiria un registro valido en
# inservible por un cambio que a diez de los doce brazos no los toca.
#
# NO SE BUMPEO POR EL ARREGLO DE `rewoo` (decision del autor, 2026-08-30). Se intento
# —`rewoo` cambio lo que HACE: RW-1 le devolvio la lectura, RW-2 le agrego la busqueda
# semantica— y romperia el invariante que este archivo declara y que `test_science.py` §64
# verifica: **los brazos sensibles son los que llaman a `scoped()`**, y `rewoo` no lo llama.
# Meterlo ahi mezclaria dos motivos distintos bajo una misma guarda.
#
# Queda anotado en `M-6`: las 138 celdas viejas de `rewoo` no miden el mismo brazo que las
# que se corran de ahora en mas, y **hay que separarlas por fecha a mano al analizar**.
SURFACE_SENSITIVE_ARMS = ("handoff", "supervisor")


@dataclass
class Barren:
    """El agotamiento del retriever, compartido por referencia con los sub-agentes.

    `streak` es un MEDIDOR —se reinicia en cuanto una busqueda trae algo nuevo, porque
    lo que interesa para avisar es la RACHA— y `peak`/`total` son acumuladores, que son
    los que sobreviven al registro.
    """

    streak: int = 0
    peak: int = 0
    total: int = 0


@dataclass
class Fallas:
    """Los errores de llamada, compartidos por referencia con los sub-agentes.

    ES EL MISMO DEFECTO QUE `Barren`, EN OTRO CONTADOR (2026-08-30). `hallucinated` era un
    `int`, y un `int` no se puede reatar: `scoped()` comparte por referencia todo lo que es
    de la TAREA, pero `replace` copia los enteros por valor, así que **lo que un sub-agente
    erraba no volvía nunca al padre**.

    El registro lo muestra con la misma firma que ya delató a `barren` — un cero que no es
    chico, es estructural:

        handoff       773 llamadas, **0** ids alucinados
        supervisor  1.583 llamadas, **0**
        react       3.466 llamadas,  5
        dag_strategy 6.769 llamadas,  9

    `handoff` y `supervisor` son los dos brazos que corren TODO adentro de sub-agentes vía
    `scoped()`. `dag_strategy` también descompone, y sí cuenta — porque le pasa a su
    sub-agente la superficie **del padre** en vez de una alcanzada. Ese contraste es la
    prueba: el cero no describe dos brazos que no se equivocan, describe dos brazos donde
    equivocarse no deja rastro.

    Y POR ESO SON DOS CAMPOS Y NO UNO. `por_tipo` cuenta LLAMADAS que fallaron, por forma
    de fallar; `unidades_alucinadas` cuenta IDS inexistentes, que es otra magnitud — una
    sola llamada puede inventar cinco. Colapsarlas perdería cuál de las dos creció.
    """

    por_tipo: dict[str, int] = field(default_factory=dict)
    unidades_alucinadas: int = 0


@dataclass
class ToolSurface:
    """LO QUE EL AGENTE PUEDE HACER, y la contabilidad de lo que hizo.

    ES LA FRONTERA ENTRE EL AGENTE Y EL MUNDO. Todo lo que un paradigma puede tocar pasa
    por acá: buscar, leer, anotar, postear al board, consultar su cobertura. Y por eso es
    también el único lugar donde se puede contar honestamente qué usó — un paradigma no
    puede reportar su propio consumo, porque entonces cada uno lo reportaría distinto.

    EL ALCANCE ES UNA PROPIEDAD DE LA VISTA, NO UNA INSTRUCCIÓN. `scoped()` le da a un
    sub-agente una `CorpusView` recortada: no puede leer afuera porque **las unidades no
    están**, no porque se le haya pedido que no lo haga. Un límite que se pide se puede
    desobedecer.

    Y `scoped()` REATA POR REFERENCIA lo que es de la TAREA y no del sub-agente: las
    llamadas, la secuencia, las unidades leídas, el board, y —desde el 2026-08-29— el
    conjunto `surfaced` y los contadores de agotamiento. Olvidar uno acá **es invisible**:
    ya pasó cuatro veces, y la última dejó a `handoff` y `supervisor` reportando 0%
    de búsquedas estériles sobre 528 búsquedas, contra 62,5% de `dag_strategy`.

    LOS FACTORES SON CAMPOS DE ACÁ, y esa es la razón de que la clase sea ancha. Cada uno
    es una dimensión que se cruza contra los patrones en vez de plegarse adentro de uno:

      `variant`             qué herramientas existen (`basic`, `accounting`, `cognitive`,
                            `managed`). **Todos los estudios medidos corrieron en `basic`**
      `offer_read_all`      ofrecer leer todo en UNA llamada. Apagado por defecto, así que
                            el modelo nunca pudo pedir el material entero aunque entrara
      `terse_tools`         descripciones cortas. Cambia lo que el modelo lee para decidir
                            QUÉ herramienta usar, así que puede cambiar la elección
      `compact_material`    resumir antes de servir
      `stop_on_barren`      dejar de buscar tras N búsquedas estériles. Es la señal que
                            midió 3,05× de reducción de costo
      `shared_state`        el board estructural que escribe el código
      `offer_board`         el board como HERRAMIENTA, ofrecida a todos por igual
      `board_queue`         que el board lleve lo que FALTA —cobertura, pendientes,
                            directiva— y no sólo lo que pasó
      `context_guard`       acotar la ventana por crecimiento y rescatar el hallazgo

    UN FACTOR QUE NO LLEGA AL MODELO NO EXISTE: no falla, **corre y mide su ausencia**, y
    el resultado se lee igual que un efecto nulo medido. Por eso hay un solo sitio en todo
    el repo que manda la declaración de herramientas, y `test_science.py` §59 prueba que
    cada factor booleano viaje hasta ahí.

    LA CONTABILIDAD SEPARA COSAS QUE SE VEN IGUALES desde el archivo: `units_read` es lo
    que el MODELO eligió leer y `units_read_structural` lo que le sirvió el código;
    `served_chars` contra `reread_chars` dice cuánto se pagó dos veces; `surfaced` y
    `Barren` dicen si el retriever se agotó; `hallucinated` cuenta ids que no existen.
    Juntar cualquiera de esos pares haría que un promedio no signifique nada, y nada lo
    denunciaría.
    """

    view: CorpusView
    hybrid: Retriever
    semantic: Retriever
    # The task's own declared budget. read_all refuses full text above a share of it
    # rather than inventing a separate limit.
    budget_tokens: int = 60_000
    lexical: Retriever = field(default_factory=LexicalRetriever)
    variant: str = "basic"
    # LA REGLA DE PARADA, COMO FACTOR Y NO COMO PATRON. `0` la apaga, que es el default.
    #
    # POR QUE EXISTE. Medido el 2026-08-28: entre replicas de la MISMA celda con la MISMA
    # utilidad, el 33% del gasto es evitable —49% en el brazo con mas autonomia de bucle,
    # 0% en el que tiene el fan-out fijado por codigo—. Y la senal discrimina: el pico de
    # busquedas esteriles da 1,17 en la replica barata contra 2,28 en la cara.
    #
    # POR QUE UN RECHAZO Y NO UNA NOTA. Hoy el estancamiento produce un NOTE al modelo:
    # «las ultimas 3 busquedas no trajeron nada, considera leer». Eso es persuasion, y el
    # invariante del producto dice que el LLM es sensor y no maneja flujo de control. Un
    # rechazo tipado SI es flujo de control decidido por codigo — y deja intactas las
    # acciones productivas: se puede seguir leyendo y se puede responder. Lo unico que se
    # quita es la accion que el registro muestra que no compra nada.
    #
    # POR QUE APAGADO POR DEFECTO. Es un FACTOR (`PATRON_O_FACTOR.es.md`): se aplica o no
    # a TODOS los brazos, asi que se mide cruzado `{con, sin} x {patrones}` y no plegado
    # adentro de uno. Y encendido por defecto invalidaria el replay sellado del registro
    # ya pagado, que es la unica verificacion de reproducibilidad que hay.
    stop_on_barren: int = 0
    # Factor: ofrecer `read_all` donde no vive. Ver `specs_for`.
    offer_read_all: bool = False
    # FACTOR: descripciones cortas. Cambia el payload que el modelo lee para decidir QUE
    # herramienta usar, asi que puede cambiar la eleccion — no es una limpieza.
    terse_tools: bool = False
    # EL BALANCE DE ESFUERZO, COMO FACTOR — y hasta hoy no existía (2026-08-30).
    #
    # `guards.ventana_sub_agente()` y `guards.presupuesto_de_esfuerzo()` estaban escritas,
    # documentadas y probadas por `test_science.py` §67 **y no las llamaba nadie**. El test
    # las ejercitaba directamente, así que pasaba; el runner nunca las tocaba y este campo
    # no existía, o sea que no había forma de encenderlas.
    #
    #     Es la forma exacta que este repo ya nombra como su falla recurrente: un factor
    #     que no llega no falla, **corre y mide su ausencia**. Y estaba anotado en
    #     `PENDIENTES.es.md` como «lo que queda es la corrida», que da por hecho que se
    #     puede correr. No se podía: no había qué encender.
    #
    # Qué cambia cuando está en `True`, y son las dos cosas que `guards.py` pide:
    #   · la ventana del sub-agente pasa a ser una FRACCIÓN del alcance en vez de un 8 fijo
    #     —medido, con el 8 el sub-agente ve el alcance entero en 28 de 78 tareas, o sea
    #     que el aislamiento no existe en el 36% del corpus—
    #   · los brazos iterativos paran al gastar su porción del presupuesto DECLARADO de la
    #     tarea, que es la misma cuenta con la que la factibilidad ya los admitió
    #
    # Apagado por defecto, como todo factor que cambia comportamiento: encenderlo vuelve
    # incomparable el registro ya pagado, y sus filas van a otro archivo.
    effort_balanced: bool = False
    # FACTOR: exigir las obligaciones tipadas (polaridad, presuposicion). Cambia el
    # contrato que todos los brazos leen, asi que sus filas van a otro archivo.
    demand_obligations: bool = False
    # FACTOR: estado compartido entre pasos. Es una DIMENSION, no una propiedad de una
    # topologia — mientras vivio adentro de `dag.py`, «el efecto dag_strategy» era la
    # conjuncion de la topologia de olas y el blackboard, sin nada que las separe, y la
    # pregunta «mejora react con estado compartido?» no se podia ni formular.
    #
    # `None` es «como cada patron venga de fabrica»: dag CON, react SIN. Es el regimen en
    # el que se midio todo hasta hoy, y decirlo `None` lo distingue de haberlo elegido.
    shared_state: bool | None = None
    # FACTOR: ofrecer el board COMO HERRAMIENTA a todos los patrones. Distinto de
    # `shared_state`, que gobierna el board ESTRUCTURAL de dag —el que escribe el codigo—.
    # Fundirlos mediria dos cosas con un interruptor.
    offer_board: bool = False
    # EL ACOPLAMIENTO MEDIDO, cuando la sonda corrio. `D-3b`.
    #
    # POR QUE VIAJA POR LA SUPERFICIE Y NO POR LA TAREA. La tarea es lo que el CALLER
    # declara; esto es lo que el sistema MIDIO pagando una unidad. Meterlo en la tarea los
    # volveria indistinguibles, y el piso de procedencia entero depende de distinguirlos.
    #
    # `None` es «no se sondeo», y NO es acoplamiento cero. Cero significa unidades
    # independientes —donde descomponer en paralelo es correcto— y no saber significa que
    # no hay con que decidir la forma. Confundirlos haria que la forma mas paralela sea el
    # default silencioso justo donde nadie midio.
    coupling: float | None = None
    # FACTOR: lo estable adelante y la pregunta al final (`X-4d`). Cambia el payload, asi
    # que sus filas van a otro archivo.
    stable_prefix_first: bool = False
    # EL ESTADO DERIVADO DEL CORPUS, YA CONSTRUIDO (G-4). Lo pone la etapa de ingesta, no
    # el request. `None` significa que la ingesta no corrio, y el paradigma que lo necesite
    # se declara infactible en vez de construirlo: construirlo aca le cobraria el indice
    # entero a una fila arbitraria y registraria la lectura del corpus como lectura de esta
    # pregunta. Es un `Any` para no importar `ingest` desde acá — `ingest` importa `llm` y
    # `parsing`, y el ciclo lo pagaria todo el que importe una tool.
    ingested: Any = None
    # LO QUE SE GASTO CONSTRUYENDO ESTADO DERIVADO EN ESTE REQUEST. Va aparte para que el
    # runner lo DESCUENTE de `cost_tokens`: la ingesta se amortiza sobre todas las
    # consultas futuras y cobrarsela a la fila que le toco construirla mezcla amortizar
    # con responder. Es su propia medicion, no un renglon de la de ejecucion.
    ingest_tokens: int = 0
    # RELECTURA: una unidad que se sirve DE NUEVO en el mismo request. No es un defecto en
    # si —un paradigma con ramas independientes no tiene por que saber lo que leyo otra— es
    # la medida de cuanto costaria de menos si no lo fuera.
    #
    # SE CUENTA, NO SE EVITA. Servir la segunda lectura de un cache cambiaria el gasto y
    # con eso el objeto de estudio, y hacerlo antes de saber cuanto vale seria optimizar a
    # ciegas. Primero el numero.
    reread_units: int = 0
    reread_chars: int = 0
    # TODO EL TEXTO QUE LA SUPERFICIE ENTREGO, por cualquier via. `read_chars` solo se
    # llena en `note_retention`, que recorre MENSAJES — asi que da 0 para todo paradigma
    # que no lleve historia, y ahi estan justo los que arman el prompt mas grande de una
    # sola vez: `gist_reader` mide 14.798 tokens por llamada, el mayor del catalogo, y su
    # contexto no crece con los turnos sino con las UNIDADES. Sin este contador, un factor
    # de poda de material no se puede medir aunque se corra.
    served_chars: int = 0
    # El factor: cuando esta encendido, todo resumen que la superficie emite va podado.
    compact_material: bool = False
    calls: dict[str, int] = field(default_factory=dict)
    board_posts: int = 0
    board_reads: int = 0
    units_read: set[str] = field(default_factory=set)
    # LECTURA ESTRUCTURAL: la que el CODIGO del paradigma hace por `read_one`, no la que
    # el modelo eligio llamando a una tool. Va a un set APARTE a proposito. Sumarla a
    # `units_read` moveria numeros ya publicados y, peor, borraria la distincion: ocho de
    # trece paradigmas leen el corpus entero desde su propio codigo —`gist_reader` para
    # armar sus gists, `direct` para volcar el material— y eso no es una decision del
    # modelo. Separadas, `units_read` sigue significando «lo que el modelo eligio leer» y
    # existe con que comparar. Juntas, ningun promedio de lectura entre paradigmas
    # significaria nada, y nada lo denunciaria.
    units_read_structural: set[str] = field(default_factory=set)
    # UN SOLO BOARD POR CELDA. `dag_strategy` escribe el suyo desde el codigo y la tool
    # escribe el mismo objeto: si fueran dos, un sub-agente que postea no veria los
    # hallazgos que el codigo asento, y habria dos «estados compartidos» a la vez.
    board_state: Blackboard = field(default_factory=Blackboard)
    # EL BOARD COMO COLA, y es un factor aparte de los otros dos. `shared_state` y
    # `offer_board` deciden QUIEN escribe el board; esto decide QUE renderiza — lo
    # acumulado, o lo que falta con su cobertura y su directiva. Son ortogonales: se
    # puede tener un board inyectado que solo lista hallazgos, y uno ofrecido como tool
    # que ademas lleva cola. La medicion que importa cruza los dos ejes.
    #
    # Apagado por defecto: con `False` el render es byte por byte el de antes, asi que
    # el registro medido hasta hoy sigue siendo comparable.
    board_queue: bool = False
    # EL GUARD DE CONTEXTO, y entra JUNTO con la cola y no despues. El guard acota la
    # ventana y **produce** el hallazgo; el board lo conserva y con eso dirige lo que
    # sigue. Las dos compactaciones que ya existen DEGRADAN —una a stub si el modelo
    # anoto, la otra a gist incondicional— y ninguna produce contenido nuevo, asi que sin
    # esto el board sostiene solo lo que el modelo se acuerde de postear: 1 de cada 125
    # llamadas.
    context_guard: bool = False
    # La pregunta de la tarea, que la extraccion necesita para saber que es relevante. La
    # pone el runner: un guard que resumiera SIN la pregunta produciria un resumen
    # generico, que es justo lo que la expulsion no puede permitirse.
    question: str = ""
    guard_stats: dict[str, int] = field(default_factory=dict)
    # LAS SIETE FORMAS DE FALLAR, CONTADAS, Y EN UN OBJETO COMPARTIDO. Antes habia UN
    # contador (`hallucinated`, un `int`) y las otras seis formas no dejaban rastro: el
    # registro no podia decir con que frecuencia el modelo erraba una llamada ni de que
    # manera. Es la misma ceguera que dejo vivir 138 celdas de `rewoo` llamando a `read`
    # sin leer nada — el efecto no lo miraba nadie.
    #
    # VA EN UN OBJETO Y NO COMO `int` POR EL MISMO MOTIVO QUE `Barren`: `scoped()` reata
    # por referencia lo que es de la tarea, y un `int` no se puede reatar. Medido, el cero
    # de `handoff` y `supervisor` no era conducta, era la copia por valor.
    #
    # Y se cuenta en `dispatch`, no en cada `raise`: asi una forma nueva de fallar no se
    # puede agregar sin quedar contada.
    fallas: "Fallas" = field(default_factory=lambda: Fallas())

    @property
    def hallucinated(self) -> int:
        return self.fallas.unidades_alucinadas

    @hallucinated.setter
    def hallucinated(self, v: int) -> None:
        self.fallas.unidades_alucinadas = v

    @property
    def tool_failures(self) -> dict[str, int]:
        return self.fallas.por_tipo

    batched_reads: int = 0
    # Units any search has ever surfaced, and how many consecutive searches surfaced
    # nothing new. A retriever that has stopped producing is the signal an iterative
    # topology needs and never gets: without it, a verify-replan loop reads a systematic
    # failure as bad luck and searches again.
    surfaced: set[str] = field(default_factory=set)
    # El ORDEN en que se llamo a cada herramienta, no solo cuantas veces. `calls` es un
    # conteo, y un conteo no distingue "busco, leyo, busco, leyo" de "busco, busco, leyo,
    # leyo" — que son dos estrategias distintas con el mismo histograma. La secuencia es
    # lo unico que permite aprender asociaciones (tool_i -> tool_j), que es donde el
    # aprendizaje Hebbiano tiene contenido propio: una asociacion entre PARES no se
    # reduce a una estadistica marginal de un brazo.
    sequence: list[str] = field(default_factory=list)
    # `barren_searches` es un MEDIDOR, no un contador: se reinicia en cuanto una busqueda
    # trae algo nuevo, porque lo que interesa para avisar es la RACHA. Pero la fila guarda
    # el valor final, y el valor final de un medidor que se reinicia es casi siempre 0 —
    # asi que la senal existe adentro del request y no sobrevive al registro.
    #
    # Medido (D-1, 2026-08-28): en 292 pares de replicas con la misma utilidad y distinto
    # gasto, `barren_searches` da 0,00 en las dos mitades. No es que no pase: es que no se
    # guarda. Por eso se acumulan ademas el PICO y el TOTAL, que si sobreviven.
    # LOS TRES VIVEN EN UN OBJETO Y NO COMO `int` (2026-08-29), y el motivo no es de
    # estilo: `_sub_surface` reata por REFERENCIA todo lo que es de la tarea y no del
    # sub-agente. Un `int` no se puede reatar —`replace` lo copia por valor— asi que los
    # contadores de racha arrancaban en cero en cada sub-agente y nunca volvian al padre.
    # Medido: `supervisor` 370 busquedas y `handoff` 158, las dos con **0 esteriles**,
    # contra 62,5% de `dag_strategy`. Ese cero no era chico: era estructural.
    barren: "Barren" = field(default_factory=lambda: Barren())

    @property
    def barren_searches(self) -> int:
        return self.barren.streak

    @barren_searches.setter
    def barren_searches(self, v: int) -> None:
        self.barren.streak = v

    @property
    def barren_peak(self) -> int:
        return self.barren.peak

    @property
    def barren_total(self) -> int:
        return self.barren.total
    # OJO: `stall_warnings` solo incrementa en las variantes de superficie con contabilidad,
    # y TODO estudio medido corrio en `basic`. Su cero en el registro no dice que el sistema
    # no se estanque — dice que en `basic` el aviso no existe. Son cosas distintas.
    stall_warnings: int = 0
    bulk_read_refusals: int = 0
    # QUE EL MODELO DEVUELVA ALGO INSERVIBLE ES UN DATO DEL EXPERIMENTO, no un error del
    # harness — `paradigms/parsing.py` lo declara y devuelve el default. Pero no se
    # anotaba, y sin eso la utilidad baja sin decir por que.
    #
    # Son dos hechos distintos y piden arreglos distintos:
    #   malformed_json  el modelo no entrego la FORMA pedida (ni JSON, o sin la clave)
    #   dropped_items   entrego la forma pero con elementos incompletos adentro
    #
    # Un paradigma con utilidad 0,4 y 40% de malformed no es "no sirve para esta tarea":
    # es "no le sale el formato", y eso se arregla en el prompt o en el esquema, no
    # retirando el brazo.
    malformed_json: int = 0
    dropped_items: int = 0
    # Cuantas busquedas rechazo la regla de parada. Sin esto, una corrida con la regla
    # encendida y una sin ella se distinguen solo por el costo, y no se podria decir si
    # la diferencia vino de la regla o de otra cosa.
    barren_refusals: int = 0
    # LLAMADAS QUE LLEVAN LA DECLARACION DE TOOLS ENCIMA, que NO son todas.
    #
    # De 27 sitios que llaman al modelo, UNO pasa `tools`: el bucle compartido. Los demas
    # —planificar, triar, sintetizar, criticar— llaman sin declaracion. Estimar el
    # sobrecosto como `calls x tokens_de_spec` lo infla por un factor grande, y en algunas
    # celdas da un numero IMPOSIBLE: mas declaracion que prompt entero.
    #
    # Sin este contador el sobrecosto no se puede atribuir, y `calls` no sirve de proxy.
    tooled_calls: int = 0
    # Unidades leidas que SIGUEN en la historia al responder. Ver
    # `note_retention`: el recall mide que se leyo, esto que sobrevivio.
    retained_chars: int = 0
    read_chars: int = 0
    # Shared across every agent working on the task: a note written by one sub-agent is
    # readable by the next. That persistence is the point — a synthesis prompt cannot
    # recover what a sub-agent knew and did not write down.
    state: WorkingState = field(default_factory=WorkingState)

    def note_malformed(self) -> None:
        """El modelo no entrego la forma pedida. Lo llama `parsing.py`, no el paradigma."""
        self.malformed_json += 1

    def note_retention(self, messages: list[dict[str, Any]]) -> None:
        """Cuantas de las unidades LEIDAS siguen en la historia al responder.

        El recall dice si la evidencia se leyo. Esto dice si sobrevivio hasta la llamada
        que responde, que es el segundo eslabon y nunca estuvo instrumentado.

        En `basic` no hay compactacion, asi que esto da 1,0 siempre — y `basic` es la
        variante de TODOS los estudios medidos. Que de 1,0 no es un resultado sobre la
        retencion: es que ahi nada puede sacar evidencia de la historia. La medida
        empieza a decir algo en `cognitive` y `managed`.
        """
        if not self.units_read:
            self.retained_chars = 0
            self.read_chars = 0
            return

        # SE MIDE EL TEXTO, NO LA MENCION, y la diferencia no es sutil.
        #
        # La compactacion NO borra: degrada el texto completo a un stub que CONSERVA EL
        # ID —«nothing is deleted, only demoted; the id makes it re-readable»—. Contar
        # ids presentes daba retencion 1,0 en la variante que compacta, o sea que medir
        # la mencion reportaba «todo sobrevivio» exactamente donde nada sobrevivio.
        #
        # Se cuenta cuanto del texto leido sigue en la historia, como RATIO y sin umbral:
        # elegir un corte seria otra constante a mano, y el ratio se puede cortar despues
        # con un numero derivado.
        historia = " ".join(
            str(m.get("content") or "") for m in messages if m.get("role") == "tool"
        )
        leido = sum(len(self.view.documents[u]) for u in self.units_read
                    if u in self.view.documents)
        # Cuanto de lo leido sigue presente: se acota por lo leido porque la historia
        # tambien lleva prompts y resultados de busqueda que no son texto de unidad.
        self.retained_chars = min(len(historia), leido)
        self.read_chars = leido

        # UNA MEDIDA HONESTA EN VEZ DE DOS, UNA DE LAS CUALES MIENTE. El primer intento
        # contaba UNIDADES cuyo texto seguia presente, buscando sus primeros caracteres.
        # El stub de compactacion conserva justamente los primeros ~220, asi que ese
        # conteo daba 4 de 4 mientras el texto real caia a un 28%.
        #
        # Queda el RATIO de caracteres, que no tiene ese punto ciego y ademas no necesita
        # umbral: cortar «retenido / no retenido» seria otra constante a mano, y el ratio
        # se puede cortar despues con un numero derivado.

    def note_dropped(self, n: int) -> None:
        """Elementos que llegaron incompletos adentro de una forma correcta."""
        self.dropped_items += n

    def scoped(self, unit_ids: list[str]) -> "ToolSurface":
        """La misma superficie restringida a un alcance, compartiendo la contabilidad.

        EL ALCANCE ES UNA PROPIEDAD DE LA VISTA, no una instruccion en el prompt: un
        sub-agente no puede leer afuera porque las unidades NO ESTAN, no porque se le haya
        pedido que no lo haga. Un limite que se pide se puede desobedecer.

        VIVE EN LA CLASE Y NO EN UN PARADIGMA porque olvidar un campo aca es invisible:
        `handoff` construia su sub-superficie a mano y no propagaba `terse_tools`,
        `offer_board`, `demand_obligations` ni `shared_state`, asi que esos factores
        simplemente no existian adentro de un sub-agente — y el brazo se habria corrido
        entero midiendo el factor apagado donde mas importa. Es la misma forma del defecto
        del bucle de herramientas, un nivel mas abajo.
        """
        from .retrieval import CorpusView

        alcance = set(unit_ids)
        sub = replace(
            self,
            view=CorpusView(
                task_id=self.view.task_id,
                documents=self.view.documents,
                unit_ids=list(unit_ids),
                relevant_units=[u for u in self.view.relevant_units if u in alcance],
            ),
        )
        # LOS CONTADORES SON DEL PADRE, compartidos por referencia: lo que se registra es
        # lo que la TAREA consumio, no lo que consumio cada sub-agente por su cuenta.
        # `replace` los copia como objetos nuevos, asi que hay que volver a atarlos.
        sub.calls = self.calls
        sub.sequence = self.sequence
        sub.units_read = self.units_read
        sub.board_queue = self.board_queue
        sub.context_guard = self.context_guard
        sub.question = self.question
        sub.units_read_structural = self.units_read_structural
        sub.board_state = self.board_state
        sub.state = self.state
        # EL AGOTAMIENTO DEL RETRIEVER ES DE LA TAREA, NO DEL SUB-AGENTE (2026-08-29).
        #
        # `surfaced` —lo que alguna búsqueda ya trajo— y los tres contadores de racha
        # NO se reataban, así que `replace` le daba a cada sub-agente un conjunto vacío:
        # **toda búsqueda suya parecía traer algo nuevo**, aunque el padre ya la hubiera
        # hecho. El registro lo delata con un cero que no es chico, es estructural:
        #
        #   supervisor   370 búsquedas, 0 estériles   (0,0%)
        #   handoff      158 búsquedas, 0 estériles   (0,0%)
        #   dag_strategy 661 búsquedas, 413 estériles (62,5%)
        #
        # Y no es sólo contabilidad perdida. El aviso «las últimas N búsquedas no
        # trajeron nada nuevo» —la señal que midió una reducción de costo de 3,05×, el
        # resultado más fuerte del banco— **no puede dispararse adentro de un
        # sub-agente**, porque su contador arranca en cero en cada uno. Así que ese
        # resultado está medido sólo sobre los brazos que NO descomponen, y los que
        # descomponen son justamente los que más buscan.
        #
        # Es la misma forma que este docstring ya advertía —olvidar un campo acá es
        # invisible— cometida en los campos que el docstring no enumeraba.
        sub.surfaced = self.surfaced
        sub.barren = self.barren
        # LOS ERRORES DE LLAMADA TAMBIEN SON DE LA TAREA. Mismo defecto que el de arriba,
        # en otro contador y descubierto un dia despues: `handoff` y `supervisor` —los dos
        # brazos que corren todo adentro de `scoped()`— daban **0 ids alucinados en 2.356
        # llamadas**, mientras `react` daba 5 en 3.466 y `dag_strategy` 9 en 6.769.
        # `dag_strategy` tambien descompone y si contaba, porque le pasa al sub-agente la
        # superficie del padre. Ese contraste es la prueba de que el cero era la copia por
        # valor y no la conducta.
        sub.fallas = self.fallas
        return sub

    def unit_ids(self) -> list[str]:
        return list(self.view.unit_ids)

    def unit_chars(self, unit_id: str) -> int:
        """El largo de una unidad, SIN leerla. Una regla no es una lectura.

        POR QUE EXISTE (2026-08-30). Cinco sitios de `paradigms/modern.py` llamaban a
        `read_one` para quedarse unicamente con `len(...)`, y `read_one` deja rastro: suma
        a `served_chars` y mete la unidad en `units_read_structural`. Medir el largo de
        algo contaba como haberlo leido.

        LO QUE ESO ROMPIA, medido sobre las filas que tienen el contador:

          · `pointer_chase` daba `units_read_structural == n_units` en **170 de 170
            celdas** — el alcance ENTERO— porque calculaba un promedio de largo sobre
            todas las unidades antes de dar el primer salto. Es el brazo que se define por
            seguir un puntero desde un ancla, y la unica metrica que mostraria si lo hace
            decia que abria el corpus completo
          · `streaming_scan` cobraba el corpus **dos veces** en `served_chars`: una para
            armar los trozos y otra para el prompt. Su docstring dice que cada token entra
            al modelo **exactamente una vez** y que es el unico brazo del catalogo con esa
            garantia — la garantia se cumplia y la contabilidad la desmentia
          · `gist_reader` cobraba cada unidad seleccionada **tres** veces: gist, estimacion
            y lectura

        Y NINGUNO CAMBIABA LO QUE EL MODELO VE, que es lo que lo hacia invisible: la
        topologia estaba bien y la medida estaba mal. Una metrica que dice «leyo todo»
        sobre el brazo cuya tesis es que no lee todo no se equivoca en un numero — invierte
        la conclusion.
        """
        if unit_id not in self.view.unit_ids:
            raise ToolFailure(f"Unit {unit_id} is not part of this task.",
                              kind="fuera_de_alcance")
        return len(self.view.documents[unit_id])

    def unit_tokens(self, unit_id: str) -> int:
        """El costo de una unidad en tokens, sin leerla y con la MISMA aritmetica que decide.

        `CHARS_PER_TOKEN` y no un `// 4` suelto: los cinco sitios que estimaban costo
        escribian el 4 a mano, asi que la constante que la factibilidad usa para PODAR y la
        que el paradigma usa para GASTAR eran dos cosas que coincidian por casualidad.
        Admitir un brazo con una cuenta y dejarlo gastar con otra es el defecto que
        `guards.py` ya nombra para el presupuesto.
        """
        return self.unit_chars(unit_id) // CHARS_PER_TOKEN

    def read_one(self, unit_id: str) -> str:
        """Lectura ESTRUCTURAL: la pide el codigo del paradigma, no el modelo.

        No pasa por `dispatch`, asi que no cuenta como llamada, no descuenta presupuesto y
        no dispara `stop_on_barren` — y esta bien que no lo haga, porque ninguna de esas
        tres cosas gobierna una linea de codigo. Lo que NO estaba bien es que no dejara
        rastro: una lectura invisible se lee igual que una lectura que no ocurrio.
        """
        if unit_id not in self.view.unit_ids:
            raise ToolFailure(f"Unit {unit_id} is not part of this task.",
                              kind="fuera_de_alcance")
        self.units_read_structural.add(unit_id)
        self.served_chars += len(self.view.documents[unit_id])
        return self.view.documents[unit_id]

    # -- dispatch ----------------------------------------------------------

    # -- accounting --------------------------------------------------------

    def _note_search(self, returned: list[str]) -> str:
        """Update the stall counter and return a warning when the retriever has dried up.

        Three consecutive searches that surface nothing new is not bad luck, it is a
        retriever that cannot find the thing. Saying so lets a loop escalate to reading
        instead of searching a fourth time.
        """
        fresh = [u for u in returned if u not in self.surfaced]
        self.surfaced.update(returned)
        if fresh:
            self.barren_searches = 0
            return ""
        self.barren.streak += 1
        self.barren.total += 1
        self.barren.peak = max(self.barren.peak, self.barren.streak)
        if self.barren_searches < 3 or self.variant not in ACCOUNTING_VARIANTS:
            return ""
        self.stall_warnings += 1
        unread = [u for u in self.view.unit_ids if u not in self.units_read]
        return (
            f"NOTE: the last {self.barren_searches} searches surfaced nothing new. "
            f"Searching again is unlikely to help. {len(unread)} units are still "
            f"unread — consider read_all or read on specific ids instead."
        )

    def bulk_read_tokens(self) -> int:
        return sum(len(self.view.documents[u]) for u in self.view.unit_ids) // CHARS_PER_TOKEN

    def bulk_read_fits(self) -> bool:
        """Whether the whole task fits a share of its own declared budget."""
        return self.bulk_read_tokens() <= int(self.budget_tokens * BULK_READ_BUDGET_SHARE)

    def _read_all(self) -> dict[str, Any]:
        """Everything, at the highest granularity that fits the task budget.

        Over budget this does NOT truncate silently. A silent cut is the worst outcome:
        the agent believes it has seen everything, answers from a prefix, and nothing in
        the transcript says otherwise. Returning summaries of ALL units keeps the map
        complete while making the constraint explicit.
        """
        total_chars = sum(len(self.view.documents[u]) for u in self.view.unit_ids)
        est_tokens = total_chars // CHARS_PER_TOKEN
        allowance = int(self.budget_tokens * BULK_READ_BUDGET_SHARE)

        if est_tokens <= allowance:
            self.units_read.update(self.view.unit_ids)
            # La cobertura se cierra ACA porque leer es el unico evento que significa
            # «esto ya lo mire». Una busqueda que DEVUELVE la unidad no es haberla
            # leido, y cerrarla ahi bajaria el pendiente sin que nadie mire nada.
            self._close_queue(self.view.unit_ids)
            self.batched_reads += 1
            return {
                "granularity": "full_text",
                "units": [
                    {"unit_id": u, "text": self.view.documents[u]}
                    for u in self.view.unit_ids
                ],
                "estimated_tokens": est_tokens,
            }

        self.bulk_read_refusals += 1
        return {
            "granularity": "summaries",
            "reason": (
                f"full text of {len(self.view.unit_ids)} units is about {est_tokens} "
                f"tokens against an allowance of {allowance}. Returning summaries of "
                f"all of them instead. Reading everything is not available on this "
                f"task — select what you need and read those."
            ),
            "units": [
                {"unit_id": u,
                 "summary": _summarise(self.view.documents[u], self.compact_material)}
                for u in self.view.unit_ids
            ],
            "estimated_tokens_if_full": est_tokens,
            "allowance": allowance,
        }

    def _coverage(self) -> dict[str, Any]:
        total = len(self.view.unit_ids)
        unread = [u for u in self.view.unit_ids if u not in self.units_read]
        return {
            "units_read": len(self.units_read),
            "board_posts": self.board_posts,
            "board_reads": self.board_reads,
            "units_total": total,
            "fraction_read": round(len(self.units_read) / total, 3) if total else 1.0,
            "unread_unit_ids": unread[:40],
            "unread_count": len(unread),
            "warning": (
                "You have not read every unit. An answer that must cover ALL units, or "
                "count them, cannot be complete from a subset."
                if unread else "Every unit has been read."
            ),
        }

    @staticmethod
    def _required(args: dict[str, Any], key: str, tool: str) -> Any:
        """Un argumento que falta es un error del MODELO, no del harness.

        POR QUE ESTO IMPORTA PARA LA COMPARACION. `args["query"]` crudo levanta
        `KeyError`, y `KeyError` no es `ToolFailure`. El loop compartido atrapa sólo
        `ToolFailure`, asi que ahi una llamada malformada mataba la tarea entera y la
        puntuaba cero; `modern.py` habia ampliado su catch a `(ToolFailure, ValueError,
        KeyError)`, asi que ahi la misma llamada degradaba y seguia.

        O sea: **el mismo output malformado del modelo era recuperable en un paradigma y
        fatal en otro**, y la diferencia entraba a la medicion como si fuera calidad del
        paradigma. Un paradigma que pide mas argumentos por llamada estaba mas expuesto,
        que es precisamente la clase de sesgo con direccion que un banco existe para no
        tener.
        """
        if key not in args or args[key] is None:
            raise ToolFailure(
                f"{tool}: falta el argumento obligatorio '{key}'.", kind="argumento"
            )
        return args[key]

    @staticmethod
    def _bounded_int(args: dict[str, Any], key: str, default: int, tool: str) -> int:
        """Un `limit` no numerico tampoco es una excepcion del harness."""
        raw = args.get(key, default)
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ToolFailure(
                f"{tool}: '{key}' tiene que ser un entero, llego {raw!r}.",
                kind="argumento",
            ) from None

    def withdrawn(self) -> tuple[str, ...]:
        """Herramientas que dejan de OFRECERSE, no de aceptarse.

        Es la correccion que P20 obligo. Rechazar la busqueda dejaba al modelo
        re-emitiendola con otras palabras el 69% de las veces: la regla agregaba una
        vuelta en vez de quitar el desperdicio, y el flujo de control seguia donde
        estaba. Sacarlas de la lista de specs es lo unico que se lo quita — el modelo no
        puede pedir una accion que no existe.

        Leer y responder quedan intactos, que es lo que hace segura la regla: `P20b`
        midio que cortar la busqueda NO cuesta utilidad (caida 0,0057 contra un piso de
        ruido de 0,0773).
        """
        if self.stop_on_barren and self.barren_searches >= self.stop_on_barren:
            return SEARCH_TOOLS
        return ()

    def _stopped(self, name: str) -> str | None:
        """El motivo tipado, si la regla de parada cierra la busqueda. `None` si no."""
        if not self.stop_on_barren or self.barren_searches < self.stop_on_barren:
            return None
        self.barren_refusals += 1
        unread = [u for u in self.view.unit_ids if u not in self.units_read]
        return json.dumps({
            "refused": name,
            "reason": (
                f"las ultimas {self.barren_searches} busquedas no trajeron ninguna "
                f"unidad nueva. Buscar de nuevo no esta disponible en esta tarea."
            ),
            # Lo que SI se puede hacer. Un rechazo que no dice la alternativa deja al
            # modelo reintentando lo mismo con otras palabras, que es el mismo gasto.
            "available": ["read", "answer"] + (["read_all"] if self.variant not in
                                               ("basic", "managed") else []),
            "unread_unit_ids": unread[:40],
            "unread_count": len(unread),
        })

    def _close_queue(self, units) -> None:
        """Cerrar en la cola las unidades que se acaban de leer. Sin cola, no hace nada."""
        if not self.board_state.queue_mode:
            return
        for u in units:
            self.board_state.close(u)

    def dispatch(self, name: str, args: dict[str, Any]) -> str:
        """Una llamada del MODELO. Envuelve al despacho real sólo para contar las fallas.

        SE CUENTA ACÁ Y NO EN CADA `raise`, y esa es toda la decisión: `_dispatch` tiene
        siete sitios que levantan y va a tener más. Contar en el cuello es lo único que
        hace que una forma nueva de fallar no se pueda agregar sin quedar contada — un
        contador que hay que acordarse de tocar deja de ser cierto en la primera prisa.

        Y la lectura ESTRUCTURAL no pasa por acá, así que su falla no se cuenta como error
        del modelo. Es correcto: un `read_one` sobre una unidad ajena es un bug del
        paradigma, no una llamada que el modelo hizo mal, y mezclarlos borraría justo la
        distinción que hace accionable al contador.
        """
        try:
            return self._dispatch(name, args)
        except ToolFailure as falla:
            tipo = getattr(falla, "kind", "otra")
            self.tool_failures[tipo] = self.tool_failures.get(tipo, 0) + 1
            raise

    def _dispatch(self, name: str, args: dict[str, Any]) -> str:
        self.calls[name] = self.calls.get(name, 0) + 1
        # EL LEDGER DE REPETIDAS. Se asienta ACA —antes de despachar y antes de la
        # comprobacion de disponibilidad— por la misma razon que `sequence`: una llamada
        # repetida que ademas falla sigue siendo una repeticion, y contar solo las que
        # salieron bien subestima justo el desperdicio que el board existe para mostrar.
        if self.board_state.queue_mode:
            self.board_state.record_tool_call(
                name, ",".join(f"{k}={v}" for k, v in sorted(args.items()))[:120]
            )
        # Se registra ANTES de despachar, a proposito: una llamada que falla igual fue
        # una decision del modelo, y una secuencia que solo guarda los aciertos describe
        # una politica que nadie ejecuto.
        self.sequence.append(name)

        # UNA sola comprobacion, y levanta `ToolFailure` y no `ValueError`. Llamar a una
        # tool que no se ofrecio es un error DEL MODELO —igual que omitir un argumento
        # obligatorio— y `ToolFailure` es lo que el loop compartido atrapa. Con
        # `ValueError` la misma llamada mataba la tarea en unos paradigmas y degradaba en
        # otros, asi que dos brazos se puntuaban distinto por el mismo error del modelo.
        if not available(name, self.variant, self.offer_read_all, self.offer_board):
            raise ToolFailure(
                f"{name} no esta disponible en la superficie {self.variant}. "
                f"Disponibles: {sorted(t['function']['name'] for t in specs_for(self.variant, self.offer_read_all, terse=self.terse_tools,
                          offer_board=self.offer_board))}",
                kind="no_ofrecida",
            )

        if name == "post":
            texto = self._required(args, "finding", "post").strip()
            # UN APUNTE VACIO NO SE GUARDA, y se dice: un board con entradas vacias hace
            # que `board()` devuelva ruido y que el conteo de apuntes mienta sobre cuanto
            # estado hay. Se rechaza la escritura, no la llamada.
            if not texto:
                return json.dumps({"posted": False, "reason": "apunte vacio"})
            self.board_state.add_finding("agent", texto[:600])
            self.board_posts += 1
            return json.dumps({"posted": True, "entries": len(self.board_state.findings)})

        if name == "board":
            self.board_reads += 1
            return json.dumps({
                "entries": len(self.board_state.findings),
                "board": self.board_state.render(),
            })

        if name == "coverage":
            return json.dumps(self._coverage())

        if name in ("note", "notes", "plan", "advance"):
            if name == "note":
                units = [
                    u.strip() for u in str(args.get("unit_ids", "")).split(",")
                    if u.strip() and u.strip() in self.view.unit_ids
                ]
                return json.dumps(
                    self.state.add_note(
                        self._required(args, "topic", "note"),
                        self._required(args, "finding", "note"),
                        units,
                    )
                )
            if name == "notes":
                return json.dumps(self.state.render_notes())
            if name == "plan":
                return json.dumps(
                    self.state.set_plan(self._required(args, "steps", "plan"))
                )
            return json.dumps(
                self.state.advance(self._required(args, "result", "advance"))
            )

        if name == "read_all":
            # La disponibilidad ya se resolvio arriba. Lo que queda es la GUARDA: si el
            # material entra en su porcion del presupuesto vuelve texto completo, y si no
            # vuelve resumenes de TODAS las unidades con el motivo dicho.
            return json.dumps(self._read_all())

        if name in ("search", "keyword_search", "semantic_search"):
            # La regla se evalua ANTES de gastar la busqueda, y despues de registrar la
            # llamada: el modelo la pidio, y una secuencia que solo guarda lo que se
            # ejecuto describe una politica que nadie tomo.
            stopped = self._stopped(name)
            if stopped is not None:
                return stopped

        if name == "search":
            ranked = self.hybrid.rank(
                self.view,
                self._required(args, "query", "search"),
                self._bounded_int(args, "limit", 8, "search"),
            )
            note = self._note_search(ranked)
            body: dict[str, Any] = {
                "results": [
                    {"unit_id": u,
                 "summary": _summarise(self.view.documents[u], self.compact_material)}
                    for u in ranked
                ]
            }
            if note:
                body["note"] = note
            return json.dumps(body)

        if name == "keyword_search":
            query = self._required(args, "query", name)
            ranked = self.lexical.rank(self.view, query, int(args.get("limit", 8)))
            terms = tokenise(query)
            out = []
            for unit_id in ranked:
                snippet = _highlight(self.view.documents[unit_id], terms)
                if snippet:
                    out.append({"unit_id": unit_id, "highlight": snippet})
            note = self._note_search([h["unit_id"] for h in out])
            body: dict[str, Any] = {"results": out}
            if note:
                body["note"] = note
            return json.dumps(body)

        if name == "semantic_search":
            ranked = self.semantic.rank(
                self.view,
                self._required(args, "query", "keyword_search"),
                self._bounded_int(args, "limit", 5, "keyword_search"),
            )
            for u in ranked:
                if u in self.units_read:
                    self.reread_units += 1
                    self.reread_chars += len(self.view.documents[u])
                self.served_chars += len(self.view.documents[u])
            self.units_read.update(ranked)
            # La cobertura se cierra ACA porque leer es el unico evento que significa
            # «esto ya lo mire». Una busqueda que DEVUELVE la unidad no es haberla
            # leido, y cerrarla ahi bajaria el pendiente sin que nadie mire nada.
            self._close_queue(ranked)
            return json.dumps([
                {"unit_id": u, "text": self.view.documents[u]} for u in ranked
            ])

        if name == "read":
            requested = [
                part.strip()
                for part in str(self._required(args, "unit_ids", name)).split(",")
                if part.strip()
            ]
            if len(requested) > 1:
                self.batched_reads += 1
            if len(requested) > MAX_BATCH_READ:
                raise ToolFailure(
                    f"read accepts at most {MAX_BATCH_READ} ids per call, "
                    f"got {len(requested)}.", kind="batch"
                )
            out = []
            missing = []
            for unit_id in requested:
                if unit_id not in self.view.unit_ids:
                    missing.append(unit_id)
                    continue
                if unit_id in self.units_read:
                    self.reread_units += 1
                    self.reread_chars += len(self.view.documents[unit_id])
                self.units_read.add(unit_id)
                # La cobertura se cierra ACA porque leer es el unico evento que significa
                # «esto ya lo mire». Una busqueda que DEVUELVE la unidad no es haberla
                # leido, y cerrarla ahi bajaria el pendiente sin que nadie mire nada.
                self._close_queue([unit_id])
                self.served_chars += len(self.view.documents[unit_id])
                out.append({"unit_id": unit_id, "text": self.view.documents[unit_id]})
            if missing:
                self.hallucinated += len(missing)
                if not out:
                    # Every id invented. Reported as a recoverable tool error rather
                    # than raised, so one bad citation does not zero the whole task.
                    raise ToolFailure(
                        f"No such units: {missing}.", kind="id_inexistente"
                    )
                out.append({"error": f"no such units: {missing}"})
            return json.dumps(out)

        # UN NOMBRE DESCONOCIDO ES `ToolFailure`, IGUAL QUE UNO NO OFRECIDO (2026-08-30).
        #
        # Levantaba `ValueError`, y el bucle compartido —como el de `rewoo`— atrapa sólo
        # `ToolFailure`. O sea que un nombre inventado MATABA la celda en unos paradigmas y
        # degradaba en otros: exactamente el defecto que ya se había corregido para las
        # herramientas no ofrecidas, y que quedó vivo un renglón más abajo.
        #
        # Y ESTE CAMINO ES ALCANZABLE DESDE EL MODELO. `rewoo` toma el nombre de
        # `step["tool"]`, que sale de un JSON que escribió el modelo: es texto libre, no un
        # nombre validado contra las specs. Medido, nunca pasó —cero filas con `error` y
        # ningún nombre raro en 1.656 filas— pero la diferencia entre «no pasó» y «no puede
        # pasar» es la que este repo cobra en otro lado.
        #
        # Un paradigma que despache un nombre equivocado por código no queda tapado: fallaría
        # en TODAS sus celdas, y `_audit_plomeria.py` lo levanta como desconexión entre
        # llamar y lograr.
        raise ToolFailure(
            f"{name} no existe. Herramientas del catalogo: "
            f"{sorted(t['function']['name'] for t in (TOOL_SPECS + ACCOUNTING_TOOL_SPECS + COGNITIVE_TOOL_SPECS + BOARD_TOOL_SPECS))}",
            kind="desconocida",
        )

    def usage(self) -> dict[str, Any]:
        """What the paradigm actually did with the surface.

        Recorded because it is the observable trace of the topology: which modality it
        reached for, whether it summarised before reading, whether it batched. Two
        paradigms with the same answer and the same token count can still have used the
        surface in completely different ways, and that difference is the object of study.
        """
        return {
            "variant": self.variant,
            "calls": dict(sorted(self.calls.items())),
            "sequence": list(self.sequence),
            "units_read": len(self.units_read),
            "ingest_tokens": self.ingest_tokens,
            # Cuanto texto se re-sirvio. `reread_chars / read_chars` es la fraccion del
            # gasto de lectura que un cache entre ramas ahorraria sin que ninguna rama vea
            # nada que no pidio — que es la unica optimizacion que NO cambia el grafo de
            # control, y por eso la unica que se puede hacer sin cambiar lo que se mide.
            "reread_units": self.reread_units,
            "reread_chars": self.reread_chars,
            "served_chars": self.served_chars,
            # LAS DOS LECTURAS, SEPARADAS. `units_read` es lo que el modelo eligio; esto es
            # lo que el codigo del paradigma leyo por su cuenta. La union NO es la suma:
            # un paradigma puede leer estructuralmente una unidad que despues el modelo
            # vuelve a pedir, y contarla dos veces inventaria lectura.
            "units_read_structural": len(self.units_read_structural),
            "units_read_any": len(self.units_read | self.units_read_structural),
            "relevant_units_read_any": len(
                (self.units_read | self.units_read_structural) & self.view.relevant
            ),
            "board_posts": self.board_posts,
            "board_reads": self.board_reads,
            # EL GUARD SE MIDE O NO EXISTE. Tres numeros y no uno, porque son tres cosas
            # distintas: cuantas veces expulso, cuantas de esas RESCATO un hallazgo, y
            # cuantas el texto expulsado no aportaba nada a la pregunta. La tercera es
            # informacion sobre la RECUPERACION —trajo 8k que no servian— y colapsarla
            # con las otras dos la perderia.
            **{f"guard_{k}": v for k, v in self.guard_stats.items()},
            "board_findings": len(self.board_state.findings),
            "board_pending": self.board_state.pending_count,
            "board_covered": self.board_state.done_count,
            "batched_reads": self.batched_reads,
            "hallucinated_units": self.hallucinated,
            # LAS SIETE FORMAS DE FALLAR, y no una. `hallucinated_units` es UNA de ellas y
            # era la unica que dejaba rastro; las otras seis pasaban sin registro, asi que
            # no habia forma de preguntarle al registro cuantas llamadas erro el modelo ni
            # de que manera. Se guardan como diccionario y no aplanadas para que agregar un
            # tipo no cambie el esquema de la fila.
            "tool_failures": dict(sorted(self.tool_failures.items())),
            "tool_failures_total": sum(self.tool_failures.values()),
            "relevant_units_read": len(self.units_read & self.view.relevant),
            # La racha final, el pico y el total. El primero es casi siempre 0 y se
            # guarda igual para que no parezca que la definicion cambio; los otros dos son
            # los que sobreviven al request y pueden gobernar una regla de parada.
            "barren_searches": self.barren_searches,
            "barren_peak": self.barren_peak,
            "barren_total": self.barren_total,
            "barren_refusals": self.barren_refusals,
            "tooled_calls": self.tooled_calls,
            # DOS medidas, y la segunda es la que dice algo donde hay compactacion:
            # cuantas unidades conservan su texto, y que fraccion del texto sobrevive.
            # Que FRACCION del texto leido sigue en la historia al responder.
            # `None` si no se leyo nada: sin denominador no hay fraccion.
            "retention": (round(self.retained_chars / self.read_chars, 3)
                          if self.read_chars else None),
            "retained_chars": self.retained_chars,
            "read_chars": self.read_chars,
            "stop_on_barren": self.stop_on_barren,
            "stall_warnings": self.stall_warnings,
            "bulk_read_refusals": self.bulk_read_refusals,
            "malformed_json": self.malformed_json,
            "dropped_items": self.dropped_items,
            "cognitive": self.state.as_dict(),
            "fraction_read": (
                round(len(self.units_read) / len(self.view.unit_ids), 3)
                if self.view.unit_ids else 1.0
            ),
        }
