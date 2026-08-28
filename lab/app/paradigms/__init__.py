"""The seven paradigms under comparison, over a differentiated tool surface.

Five mirror Select-then-Solve (Direct, CoT, ReAct, Plan-Execute, Reflection). Keeping the
set comparable to a published grid matters more than having the "best" set: it is what
lets these numbers be checked against theirs. Two are added: Map-Reduce, which their grid
omits and which should win on high cardinality; and the DAG with verify-replan over a
blackboard (`dag.py`), the most elaborate topology available, included so the comparison
is not stacked in favour of the simple ones.

Each paradigm is deliberately thin. The experiment measures the CONTROL STRUCTURE, so
every paradigm shares the same tools, the same model, the same decoding and the same
answer format. Any prompt cleverness that helped one paradigm and not another would be a
confound, not a result.

The tools come from `app.tools`: four of them, at three granularities, with lexical and
dense exposed separately alongside the fused entry point. That matters because choosing
the modality, the granularity, the sequence and the batching IS the topology — and while
the harness offered one blunt search returning a fixed excerpt, none of those choices
existed to be measured.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from ..contracts import OBLIGATIONS_CONTRACT
from ..llm import Completion, LLMClient, Usage
from ..cognitive import compact_history, manage_history
from ..tools import ToolFailure, ToolSurface, specs_for

def answer_contract(surface: Any = None) -> str:
    """El contrato de respuesta, mas las obligaciones si la corrida las exige.

    UNA SOLA FUNCION Y NO UNA CONSTANTE POR VARIANTE. El addendum de obligaciones es un
    FACTOR: cambia el prompt de TODOS los brazos por igual, asi que se enciende en un solo
    lugar y ningun paradigma decide si lo lleva. Un paradigma que pudiera optar convertiria
    al factor en parte de la topologia, que es justo lo que separa factor de patron.
    """
    if surface is not None and getattr(surface, "demand_obligations", False):
        return ANSWER_CONTRACT + "\n\n" + OBLIGATIONS_CONTRACT
    return ANSWER_CONTRACT


ANSWER_CONTRACT = (
    "End your reply with a single line of the form:\nANSWER: <answer>\n"
    "For a set-valued answer, separate items with '; '. Nothing after that line."
)


def parse_answer(text: str) -> str:
    matches = re.findall(r"^ANSWER:\s*(.+)$", text, flags=re.MULTILINE)
    # Last wins: a paradigm that revises its answer (Reflection) emits the contract
    # line more than once, and the final one is the one it stands behind.
    return matches[-1].strip() if matches else text.strip()


# QUE PARADIGMAS RECORREN EL ALCANCE ENTERO POR CONSTRUCCION.
#
# ES UNA PROPIEDAD A PRIORI, NO UN RESULTADO APRENDIDO. No dice «react pierde en C2» —eso
# lo mide theta y cambia con el corpus—. Dice que `react` **lee una muestra**, y una
# muestra no puede establecer una afirmacion sobre un dominio entero. Es la misma
# asimetria de `C-ABSENCE`, del lado del request en vez del enunciado.
#
#   map_reduce      una llamada POR UNIDAD. Cubre el alcance porque su forma lo obliga
#   direct          todo el material en un prompt. Cubre cuando la factibilidad lo admite,
#                   y cuando no lo admite ya esta podado antes de llegar aca
#   react           busca y lee lo que decide leer. Puede cubrir; nada lo obliga
#   rewoo           un plan y evidencia por paso. Mismo caso
#   dag_strategy    ramas sobre sub-preguntas. Cubre lo que las sub-preguntas alcanzan
#   gist_reader     resume y despues lee lo elegido. Por diseno NO cubre
#   handoff         alcances disjuntos que suman el total, pero cada agente ve el suyo y
#                   la transferencia es condicional: la union no esta garantizada
#
# LA DUDA SE RESUELVE HACIA `False`. Un paradigma que no esta en el mapa no recorre: si
# no se sabe, no se puede prometer. Y prometerlo de mas es justo la falla que la
# precondicion existe para impedir.
TRAVERSES_SCOPE: frozenset[str] = frozenset({"map_reduce", "direct"})


def traverses_scope(paradigm: str) -> bool:
    """Si este paradigma recorre el alcance entero por su ESTRUCTURA, no por suerte."""
    return paradigm in TRAVERSES_SCOPE


@dataclass
class Result:
    answer: str
    usage: Usage
    transcript: list[dict[str, Any]]
    # EL TEXTO ANTES DE PARSEAR. Las declaraciones tipadas de obligaciones —`POLARITY`,
    # `PRESUPPOSES`— viven ANTES de la linea `ANSWER:`, asi que `answer` ya las descarto.
    # Verificarlas sobre `answer` daria «no declarada» SIEMPRE, y eso se leeria como
    # incumplimiento del modelo cuando seria un defecto de plomeria — el mismo error que
    # `retained_units` cometio contando el id en vez del texto.
    #
    # Vacio significa que el paradigma NO lo lleva, y el verificador LEVANTA en vez de
    # reportar un incumplimiento inventado. Un paradigma que no lo carga es deuda visible.
    raw_text: str = ""
    iterations: int = 0
    # The observable trace of the topology: which modality it reached for, whether it
    # summarised before reading, whether it batched. Two paradigms with the same answer
    # and the same token count can have used the surface completely differently, and
    # that difference is the object of study.
    tool_usage: dict[str, Any] = field(default_factory=dict)

    @property
    def cross_unit_lookups(self) -> int:
        return max(0, int(self.tool_usage.get("units_read", 0)) - 1)

    @property
    def hallucinated_units(self) -> int:
        return int(self.tool_usage.get("hallucinated_units", 0))


# -- helpers -------------------------------------------------------------------


def _run_tool_loop(
    client: LLMClient,
    surface: ToolSurface,
    messages: list[dict[str, Any]],
    max_iterations: int,
) -> tuple[Completion | None, Usage, list[dict[str, Any]], int]:
    """Shared tool loop. Usage accounting lives on the surface, not here."""
    usage = Usage()
    iterations = 0
    completion = None

    for _ in range(max_iterations):
        iterations += 1
        # Se cuenta ACA porque este es el unico sitio del repo que manda la declaracion:
        # los otros 26 sitios que llaman al modelo lo hacen sin `tools`.
        surface.tooled_calls += 1
        completion = client.complete(
            messages=messages,
            tools=specs_for(
                surface.variant,
                getattr(surface, "offer_read_all", False),
                # Lo retirado no se ofrece. Rechazar una llamada no le quita la decision
                # al modelo — P20 lo midio: la re-emite con otras palabras el 69% de las
                # veces. No ofrecerla si.
                drop=surface.withdrawn() if hasattr(surface, "withdrawn") else (),
            ),
        )
        usage.merge(completion.usage)

        if not completion.tool_calls:
            break

        messages.append({
            "role": "assistant",
            "content": completion.text or None,
            "tool_calls": completion.tool_calls,
        })
        for call in completion.tool_calls:
            fn = call["function"]
            args = json.loads(fn["arguments"] or "{}")
            try:
                output = surface.dispatch(fn["name"], args)
            except ToolFailure as failure:
                # A tool call the model got wrong returns to it, recoverable, as it
                # would in a real system. Raising here scored the whole task zero and
                # conflated "invented one citation" with "got the answer wrong".
                output = json.dumps({
                    "error": str(failure),
                    "hint": "Use only unit ids returned by a search.",
                })
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": output,
            })

        # Compaction happens after the batch of calls, not inside it, so a note written
        # in this turn can compact a read from the same turn. This is where the cost
        # saving lives: a tool result stays in history and is resent every subsequent
        # turn, so text read on turn 2 is paid for again on turn 12.
        if surface.variant == "cognitive":
            compact_history(messages, surface.state.noted_units, surface.state)
        elif surface.variant == "managed":
            # Unconditional and deterministic: the environment does the bookkeeping the
            # cognitive arm measured the model will not do voluntarily.
            manage_history(messages)

    # M-2, EL SEGUNDO ESLABON. El recall mide si la evidencia se LEYO; esto mide si
    # SOBREVIVIO hasta la llamada que responde. No son lo mismo: un resultado de tool
    # queda en la historia y se re-envia cada vuelta, salvo que la compactacion lo saque.
    #
    # Se cuenta por CONTENCION de ids declarados —una lista cerrada— adentro de los
    # resultados que quedaron en la historia. No es parsear prosa: la direccion es buscar
    # una lista conocida en un texto, no extraer del texto que ids hay.
    #
    # Y UNA SALVEDAD QUE ES EL HALLAZGO. En `basic` no hay compactacion, asi que la
    # retencion es 1,0 POR CONSTRUCCION — y `basic` es la variante de todos los estudios
    # medidos. La medida solo dice algo donde algo puede sacar evidencia de la historia.
    surface.note_retention(messages)

    return completion, usage, messages, iterations


class Infeasible(Exception):
    """The material does not fit; no answer was possible at any quality.

    Distinct from a wrong answer on purpose. Above a certain corpus size,
    read-everything is not expensive — it is unavailable, and reporting that as a
    quality failure would describe the wrong thing.
    """


def _units_block(surface: ToolSurface) -> str:
    """Every unit, in full — if the task budget allows it.

    The read-everything paradigms pay for this by construction, and above a size they
    cannot pay at all. Raising here rather than sending the call is what keeps
    "could not run" from being recorded as "answered incorrectly".
    """
    if not surface.bulk_read_fits():
        raise Infeasible(
            f"reading all {len(surface.unit_ids())} units is about "
            f"{surface.bulk_read_tokens()} tokens against a budget of "
            f"{surface.budget_tokens}"
        )
    return "\n\n".join(f"[{u}]\n{surface.read_one(u)}" for u in surface.unit_ids())


def _finish(
    answer_text: str,
    usage: Usage,
    surface: ToolSurface,
    transcript: list[dict[str, Any]],
    iterations: int,
) -> Result:
    return Result(
        answer=parse_answer(answer_text),
        raw_text=answer_text,
        usage=usage,
        transcript=transcript,
        iterations=iterations,
        tool_usage=surface.usage(),
    )


# -- the paradigms -------------------------------------------------------------


def direct(client: LLMClient, surface: ToolSurface, task: dict[str, Any]) -> Result:
    """One call, no tools, no reasoning scaffold."""
    prompt = (
        f"{task['question']}\n\n"
        f"Material:\n{_units_block(surface)}\n\n{answer_contract(surface)}"
    )
    completion = client.complete(messages=[{"role": "user", "content": prompt}])
    return _finish(
        completion.text, completion.usage, surface,
        [{"role": "user", "content": prompt}], 1,
    )


def cot(client: LLMClient, surface: ToolSurface, task: dict[str, Any]) -> Result:
    """One call with an explicit reasoning instruction."""
    prompt = (
        f"{task['question']}\n\n"
        f"Material:\n{_units_block(surface)}\n\n"
        f"Reason step by step before answering.\n\n{answer_contract(surface)}"
    )
    completion = client.complete(messages=[{"role": "user", "content": prompt}])
    return _finish(
        completion.text, completion.usage, surface,
        [{"role": "user", "content": prompt}], 1,
    )


def react(client: LLMClient, surface: ToolSurface, task: dict[str, Any]) -> Result:
    """Interleaved reasoning and tool use. The fallback paradigm."""
    messages = [{
        "role": "user",
        "content": (
            f"{task['question']}\n\n"
            f"There are {len(surface.unit_ids())} units available. Use the search and "
            f"read tools to gather what you need, then answer.\n\n{answer_contract(surface)}"
        ),
    }]
    completion, usage, transcript, iterations = _run_tool_loop(
        client, surface, messages, max_iterations=20
    )
    return _finish(
        completion.text if completion else "", usage, surface, transcript, iterations
    )


def map_reduce(client: LLMClient, surface: ToolSurface, task: dict[str, Any]) -> Result:
    """Extract from every unit independently, then combine. No cross-unit context."""
    usage = Usage()
    partials: list[str] = []
    unit_ids = surface.unit_ids()

    for unit_id in unit_ids:
        prompt = (
            f"Task: {task['question']}\n\n"
            f"Consider ONLY this unit. Report what it contributes, or 'NOTHING'.\n\n"
            f"[{unit_id}]\n{surface.read_one(unit_id)}"
        )
        completion = client.complete(
            messages=[{"role": "user", "content": prompt}], max_tokens=800
        )
        usage.merge(completion.usage)
        # Equality, not substring: 'says nothing about X, but names Y as director'
        # is a real finding, and a substring test silently discarded it.
        if completion.text.strip().rstrip(".").strip().upper() != "NOTHING":
            partials.append(f"[{unit_id}] {completion.text.strip()}")

    reduce_prompt = (
        f"Task: {task['question']}\n\n"
        f"Per-unit findings:\n" + "\n".join(partials) +
        f"\n\nCombine them into one answer. De-duplicate.\n\n{answer_contract(surface)}"
    )
    final = client.complete(messages=[{"role": "user", "content": reduce_prompt}])
    usage.merge(final.usage)

    return _finish(
        final.text, usage, surface,
        [{"role": "user", "content": reduce_prompt}], len(unit_ids) + 1,
    )


def plan_execute(client: LLMClient, surface: ToolSurface, task: dict[str, Any]) -> Result:
    """Decompose into sub-questions, answer each with tools, then synthesise."""
    usage = Usage()

    plan_prompt = (
        f"Task: {task['question']}\n\n"
        f"{len(surface.unit_ids())} units are available. Break this into at most 5 "
        f"independent sub-questions. Return JSON: {{\"sub_questions\": [\"...\"]}}. "
        f"JSON only."
    )
    plan = client.complete(
        messages=[{"role": "user", "content": plan_prompt}], max_tokens=600
    )
    usage.merge(plan.usage)

    try:
        sub_questions = json.loads(plan.text.strip())["sub_questions"][:5]
    except (json.JSONDecodeError, KeyError, TypeError):
        # A malformed plan is a real failure of this paradigm on this task. Recording it
        # as such is the point; substituting the original question would hide it.
        sub_questions = []

    findings: list[str] = []
    for sub in sub_questions:
        messages = [{
            "role": "user",
            "content": f"{sub}\n\nUse the search and read tools to answer concisely.",
        }]
        completion, sub_usage, _, _ = _run_tool_loop(
            client, surface, messages, max_iterations=4
        )
        usage.merge(sub_usage)
        findings.append(f"Q: {sub}\nA: {completion.text if completion else ''}")

    synth_prompt = (
        f"Task: {task['question']}\n\nSub-findings:\n" + "\n\n".join(findings) +
        f"\n\n{answer_contract(surface)}"
    )
    final = client.complete(messages=[{"role": "user", "content": synth_prompt}])
    usage.merge(final.usage)

    return _finish(
        final.text, usage, surface,
        [{"role": "user", "content": synth_prompt}], len(sub_questions) + 2,
    )


def reflection(client: LLMClient, surface: ToolSurface, task: dict[str, Any]) -> Result:
    """Answer with tools, critique that answer, then revise once."""
    usage = Usage()

    messages = [{
        "role": "user",
        "content": (
            f"{task['question']}\n\nUse the search and read tools as needed.\n\n"
            f"{answer_contract(surface)}"
        ),
    }]
    first, first_usage, transcript, iterations = _run_tool_loop(
        client, surface, messages, max_iterations=10
    )
    usage.merge(first_usage)
    draft = first.text if first else ""

    critique_prompt = (
        f"Task: {task['question']}\n\nProposed answer:\n{draft}\n\n"
        f"List concrete defects: omissions, unsupported claims, wrong scope. "
        f"If it is correct and complete, reply exactly 'NO DEFECTS'."
    )
    critique = client.complete(
        messages=[{"role": "user", "content": critique_prompt}], max_tokens=800
    )
    usage.merge(critique.usage)

    # Equality, not substring: 'there are no defects of scope, but two omissions'
    # is a critique, and the substring test took it as approval.
    if critique.text.strip().rstrip(".").strip().upper() == "NO DEFECTS":
        return _finish(draft, usage, surface, transcript, iterations + 1)

    revise_messages = transcript + [
        {"role": "assistant", "content": draft},
        {
            "role": "user",
            "content": (
                f"A reviewer raised these defects:\n{critique.text}\n\n"
                f"Address them. You may use the tools again.\n\n{answer_contract(surface)}"
            ),
        },
    ]
    revised, revise_usage, _, revise_iters = _run_tool_loop(
        client, surface, revise_messages, max_iterations=8
    )
    usage.merge(revise_usage)

    return _finish(
        revised.text if revised else draft, usage, surface,
        revise_messages, iterations + revise_iters + 1,
    )


ParadigmFn = Callable[[LLMClient, ToolSurface, dict[str, Any]], Result]

# -- estado del catalogo -------------------------------------------------------------
#
# POR QUE ESTO ES CODIGO Y NO UN DOCUMENTO. Habia decisiones tomadas y registradas que
# el ejecutable no conocia: dos brazos falsificados por prediccion registrada seguian
# disponibles en el default, y el unico bloqueo por codigo cubria uno solo. Una decision
# que vive en prosa y no en el programa se deriva sola — es la misma falla que este
# proyecto viene cerrando en cada capa.
#
# Y NO ES UN SOLO BALDE. Un brazo puede estar afuera por razones que no son la misma, y
# tratarlas igual pierde justamente lo que hace falta para revivir uno: la CONDICION.
# `graph_traverse` no esta retirado — esta en espera, y lo que lo revive esta escrito.
#
# Todos siguen en el REGISTRY: las filas ya pagadas hay que poder leerlas, y borrar la
# funcion volveria irreproducible el registro que la midio.


class Status(str, Enum):
    ACTIVE = "active"
    RETIRED = "retired"
    STANDBY = "standby"
    INFEASIBLE = "infeasible"
    UNDER_REVIEW = "under_review"


@dataclass(frozen=True)
class CatalogEntry:
    """Por que un brazo esta donde esta, y que lo movería."""

    status: Status
    reason: str
    revives_when: str = ""

    @property
    def runnable(self) -> bool:
        # INFEASIBLE no se bloquea: la aritmetica de factibilidad ya lo poda a costo
        # cero y REGISTRA la exclusion con su razon, que es mas informativo que negarse
        # a correrlo. La infactibilidad ES el resultado.
        return self.status in (Status.ACTIVE, Status.INFEASIBLE, Status.UNDER_REVIEW)


CATALOG: dict[str, CatalogEntry] = {
    "react": CatalogEntry(Status.ACTIVE, "fallback general del catalogo"),
    "dag_strategy": CatalogEntry(Status.ACTIVE, "unico mejor en 8 celdas de 96"),
    "rewoo": CatalogEntry(Status.ACTIVE, "unico mejor en 10, y el mas barato al empatar en 46"),
    "gist_reader": CatalogEntry(Status.ACTIVE, "unico mejor en 9"),
    "map_reduce": CatalogEntry(
        Status.STANDBY,
        "DESPRIORIZADO por decision del autor (2026-08-28): no se le gasta mas cuota de "
        "medicion. La evidencia lo acompana — gana UNA celda de 33 en las que compite, y "
        "la aritmetica de factibilidad lo poda en 180 filas de 270, asi que la mayor "
        "parte de lo que se pagaria por el ya se sabe que no va a correr. Y en P20 su "
        "reduccion fue 0,0%: su fan-out lo fija el codigo, asi que no tiene nada que "
        "ahorrar donde el resto ahorra",
        revives_when="una celda donde sea unico mejor Y factible bajo presupuesto de "
                     "produccion; su dato historico se replaya igual",
    ),
    "reflection": CatalogEntry(Status.ACTIVE, "unico mejor en 1 de 14: delgado, no dominado"),
    "handoff": CatalogEntry(
        Status.ACTIVE,
        "CANDIDATO NUEVO (2026-08-28), sin medir. Alcances independientes y transferencia "
        "AUTORIZADA POR CODIGO, no por una herramienta que el modelo llama — que es como "
        "lo hacen los tres frameworks consultados y es flujo de control decidido por el "
        "modelo. Entra con prediccion falsable registrada antes de correr, como todos",
        revives_when="no aplica: esta activo y sin medir. Si P23 lo refuta, pasa a "
                     "retirado con el veredicto adentro",
    ),
    "direct": CatalogEntry(
        Status.ACTIVE,
        "caso degenerado que la factibilidad elige sola cuando la evidencia entra en "
        "ventana; fuera de ventana se poda a costo cero",
    ),
    "cot": CatalogEntry(
        Status.RETIRED,
        "dominado en toda celda medida: misma utilidad que direct, nunca mas barato. "
        "La ingenieria de prompts no es un patron",
        revives_when="nunca por diseno: los patrones se distinguen por estructura de "
                     "control de flujo, jamas por fraseo",
    ),
    "pointer_chase": CatalogEntry(
        Status.RETIRED,
        "FALSIFICADO por prediccion registrada (P14a): nunca toco una unidad relevante, "
        "la semilla de recuperacion es el eslabon debil. Sus frenos P14b si se "
        "confirmaron y el mecanismo sobrevive: un loop guiado por codigo elimina la "
        "loteria de costo",
        revives_when="un anclaje que no dependa de una sola semilla lexica",
    ),
    "graph_traverse": CatalogEntry(
        Status.STANDBY,
        "u=0,000 en las dos celdas acopladas (P10a), y la falsacion sobrevivio su "
        "objecion mas seria — el indice estaba 100% anclado y las cadenas conectadas. "
        "Pero corrio donde resolver entidades es GRATIS: el corpus tiene cero "
        "abreviaturas, cero anafora, una forma canonica por entidad",
        revives_when="(a) un corpus con resolucion de entidades real y (b) un indice "
                     "con la disciplina de la sonda: aceptar una entidad solo donde "
                     "aparece literal, y guardar el span",
    ),
    "extract_compute": CatalogEntry(
        Status.INFEASIBLE,
        "infactible bajo presupuesto de produccion; la infactibilidad ES el resultado "
        "(P11 no-evaluable). No se bloquea: la aritmetica lo poda y lo registra",
    ),
    "streaming_scan": CatalogEntry(
        Status.INFEASIBLE,
        "infactible bajo presupuesto de produccion (P12 no-evaluable). Idem",
    ),
    "plan_execute": CatalogEntry(
        Status.RETIRED,
        "DOMINADO: 0 unicos mejores y 0 veces el mas barato al empatar, sobre las 14 "
        "celdas en que compitio. Retirado por decision del autor (2026-08-28) con el "
        "mismo criterio que el control nulo por prompting. La salvedad queda en el "
        "registro y no se borra: aquel cayo sobre TODA celda medida y este sobre 14, "
        "asi que es la misma regla aplicada con menos evidencia — dicho, no escondido",
        revives_when="una sola celda donde sea unico mejor, o donde empate siendo el "
                     "mas barato",
    ),
}

# Compatibilidad: lo que ninguna corrida nueva puede incluir.
RETIRED: frozenset[str] = frozenset(
    name for name, entry in CATALOG.items() if not entry.runnable
)

REGISTRY: dict[str, ParadigmFn] = {
    "direct": direct,
    "cot": cot,
    "react": react,
    "map_reduce": map_reduce,
    "plan_execute": plan_execute,
    "reflection": reflection,
}

# Relative cost priors. Only the ORDER matters: they seed the cascade ladder before any
# episodes exist, and are superseded by measured mean_cost once theta has data.
COST_PRIORS: dict[str, float] = {
    "direct": 1.0,
    "cot": 1.3,
    "react": 3.0,
    "reflection": 5.0,
    "plan_execute": 6.0,
    "map_reduce": 8.0,
}

FALLBACK = "react"


# The DAG paradigm is registered from the bottom of this module rather than imported at
# the top: `dag.py` needs ANSWER_CONTRACT, Result, parse_answer and _run_tool_loop from
# here, so importing it any earlier is a circular import.
from .dag import dag_strategy  # noqa: E402

REGISTRY["dag_strategy"] = dag_strategy

# Mismo motivo que `dag.py`: `handoff.py` necesita `_run_tool_loop` y `parse_answer` de
# aca, asi que se importa desde abajo.
from .handoff import handoff  # noqa: E402

REGISTRY["handoff"] = handoff
# Costo: SCOPES agentes, cada uno con su bucle acotado. Mas caro que un fan-out fijo
# —hay dos bucles— y mas barato que `dag_strategy`, que ademas replanifica.
COST_PRIORS["handoff"] = 5.0
# Costliest by a distance: plan + waves + verify + up to 3 replans + synthesise. The
# prior puts it last on any cascade ladder, which is where its measured cost belongs.
COST_PRIORS["dag_strategy"] = 12.0

# The modern paradigms (2026-08-26) live in modern.py for the same circular-import
# reason as dag.py: they need ANSWER_CONTRACT, Result and _finish from here.
from .modern import (  # noqa: E402
    extract_compute, gist_reader, graph_traverse, pointer_chase, rewoo,
    streaming_scan,
)

REGISTRY["rewoo"] = rewoo
REGISTRY["gist_reader"] = gist_reader
REGISTRY["graph_traverse"] = graph_traverse
REGISTRY["extract_compute"] = extract_compute
REGISTRY["streaming_scan"] = streaming_scan
REGISTRY["pointer_chase"] = pointer_chase
# rewoo/gist_reader/graph_traverse are cheap by construction (2 LLM calls, no history
# resend; the graph index is amortised across the corpus). extract_compute and
# streaming_scan pay the corpus once, in short bounded calls.
COST_PRIORS["rewoo"] = 2.0
COST_PRIORS["gist_reader"] = 2.5
COST_PRIORS["graph_traverse"] = 2.5
COST_PRIORS["extract_compute"] = 7.0
COST_PRIORS["streaming_scan"] = 6.0
# Anchor pick + at most 6 one-unit sensor hops + solve, no history resend: bounded by
# arithmetic, cheaper than react wherever the chain is short.
COST_PRIORS["pointer_chase"] = 2.5
