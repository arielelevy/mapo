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
from dataclasses import dataclass, field
from typing import Any

from .cognitive import COGNITIVE_TOOL_SPECS, WorkingState
from .retrieval import CorpusView, LexicalRetriever, Retriever, tokenise

SUMMARY_CHARS = 180
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


def specs_for(variant: str, offer_read_all: bool = False) -> list[dict[str, Any]]:
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
    read_all_spec = [
        t for t in ACCOUNTING_TOOL_SPECS if t["function"]["name"] == "read_all"
    ] if offer_read_all else []

    if variant == "basic":
        return list(TOOL_SPECS) + read_all_spec
    if variant == "accounting":
        return list(TOOL_SPECS) + list(ACCOUNTING_TOOL_SPECS)
    if variant == "cognitive":
        return (
            list(TOOL_SPECS)
            + list(ACCOUNTING_TOOL_SPECS)
            + list(COGNITIVE_TOOL_SPECS)
        )
    if variant == "managed":
        # Same tools as basic, deliberately: the difference under test is not what the
        # model CAN call but what the harness DOES to the history. The cognitive arm
        # measured that voluntary self-management does not happen (1 note, 1 compaction,
        # 0 plans in 28 rows); `managed` moves the bookkeeping to the environment.
        return list(TOOL_SPECS) + read_all_spec
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
AVAILABLE_IN: dict[str, tuple[str, ...]] = {
    "read_all": ACCOUNTING_VARIANTS,
    "coverage": ACCOUNTING_VARIANTS,
    "note": ("cognitive",),
    "notes": ("cognitive",),
    "plan": ("cognitive",),
    "advance": ("cognitive",),
}


def available(name: str, variant: str, offer_read_all: bool = False) -> bool:
    """Si `name` esta disponible en `variant`. Lo no listado esta en todas.

    El factor `offer_read_all` entra ACA tambien y no solo en `specs_for`: si la
    disponibilidad no siguiera a la oferta, encender el factor le ofreceria al modelo una
    tool que dispatch despues rechaza — que es exactamente la separacion que §31 impide.
    """
    if name == "read_all" and offer_read_all:
        return True
    return variant in AVAILABLE_IN.get(name, VARIANTS)


class ToolFailure(Exception):
    """A tool call the model got wrong, as opposed to a bug in the harness."""


def _summarise(text: str) -> str:
    """First substantive line plus a length hint.

    A summary has to be genuinely cheaper than the unit or the granularity ladder is
    decoration. The length hint is what lets an agent decide whether reading is worth it.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    body = next((line for line in lines[1:] if len(line) > 30), lines[0] if lines else "")
    return f"{body[:SUMMARY_CHARS]} … [{len(text)} chars]"


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


@dataclass
class ToolSurface:
    """The four retrieval tools over one task's units, plus usage accounting."""

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
    calls: dict[str, int] = field(default_factory=dict)
    units_read: set[str] = field(default_factory=set)
    hallucinated: int = 0
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
    barren_searches: int = 0
    barren_peak: int = 0
    barren_total: int = 0
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
    # Shared across every agent working on the task: a note written by one sub-agent is
    # readable by the next. That persistence is the point — a synthesis prompt cannot
    # recover what a sub-agent knew and did not write down.
    state: WorkingState = field(default_factory=WorkingState)

    def note_malformed(self) -> None:
        """El modelo no entrego la forma pedida. Lo llama `parsing.py`, no el paradigma."""
        self.malformed_json += 1

    def note_dropped(self, n: int) -> None:
        """Elementos que llegaron incompletos adentro de una forma correcta."""
        self.dropped_items += n

    def unit_ids(self) -> list[str]:
        return list(self.view.unit_ids)

    def read_one(self, unit_id: str) -> str:
        if unit_id not in self.view.unit_ids:
            raise ToolFailure(f"Unit {unit_id} is not part of this task.")
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
        self.barren_searches += 1
        self.barren_total += 1
        self.barren_peak = max(self.barren_peak, self.barren_searches)
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
                {"unit_id": u, "summary": _summarise(self.view.documents[u])}
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
                f"{tool}: falta el argumento obligatorio '{key}'."
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
                f"{tool}: '{key}' tiene que ser un entero, llego {raw!r}."
            ) from None

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

    def dispatch(self, name: str, args: dict[str, Any]) -> str:
        self.calls[name] = self.calls.get(name, 0) + 1
        # Se registra ANTES de despachar, a proposito: una llamada que falla igual fue
        # una decision del modelo, y una secuencia que solo guarda los aciertos describe
        # una politica que nadie ejecuto.
        self.sequence.append(name)

        # UNA sola comprobacion, y levanta `ToolFailure` y no `ValueError`. Llamar a una
        # tool que no se ofrecio es un error DEL MODELO —igual que omitir un argumento
        # obligatorio— y `ToolFailure` es lo que el loop compartido atrapa. Con
        # `ValueError` la misma llamada mataba la tarea en unos paradigmas y degradaba en
        # otros, asi que dos brazos se puntuaban distinto por el mismo error del modelo.
        if not available(name, self.variant, self.offer_read_all):
            raise ToolFailure(
                f"{name} no esta disponible en la superficie {self.variant}. "
                f"Disponibles: {sorted(t['function']['name'] for t in specs_for(self.variant, self.offer_read_all))}"
            )

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
                    {"unit_id": u, "summary": _summarise(self.view.documents[u])}
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
            self.units_read.update(ranked)
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
                    f"got {len(requested)}."
                )
            out = []
            missing = []
            for unit_id in requested:
                if unit_id not in self.view.unit_ids:
                    missing.append(unit_id)
                    continue
                self.units_read.add(unit_id)
                out.append({"unit_id": unit_id, "text": self.view.documents[unit_id]})
            if missing:
                self.hallucinated += len(missing)
                if not out:
                    # Every id invented. Reported as a recoverable tool error rather
                    # than raised, so one bad citation does not zero the whole task.
                    raise ToolFailure(
                        f"No such units: {missing}. Use only ids returned by a search."
                    )
                out.append({"error": f"no such units: {missing}"})
            return json.dumps(out)

        # An unknown tool is a bug in the paradigm, not something to paper over with a
        # plausible-looking empty result.
        raise ValueError(f"Unknown tool: {name}")

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
            "batched_reads": self.batched_reads,
            "hallucinated_units": self.hallucinated,
            "relevant_units_read": len(self.units_read & self.view.relevant),
            # La racha final, el pico y el total. El primero es casi siempre 0 y se
            # guarda igual para que no parezca que la definicion cambio; los otros dos son
            # los que sobreviven al request y pueden gobernar una regla de parada.
            "barren_searches": self.barren_searches,
            "barren_peak": self.barren_peak,
            "barren_total": self.barren_total,
            "barren_refusals": self.barren_refusals,
            "tooled_calls": self.tooled_calls,
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
