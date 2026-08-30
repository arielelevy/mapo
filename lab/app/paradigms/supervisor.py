"""Supervisor dinamico: un orquestador que decide el proximo sub-agente DESPUES de ver el anterior.

QUE LO HACE UN PATRON Y NO OTRO PROMPT. Las cuatro preguntas de `PATRON_O_FACTOR.es.md`:

  cuantas llamadas y quien las decide   NO estan decididas de antemano. El supervisor mira
                                        lo que volvio y recien ahi despacha la siguiente,
                                        o para. `dag_strategy` fija su plan antes de
                                        ejecutar y `handoff` fija sus alcances en el codigo
  quien elige la proxima accion         el supervisor elige QUE sub-tarea despachar; el
                                        sub-agente elige sus herramientas adentro
  estado compartido y quien lo escribe   un resumen por sub-agente, escrito por el CODIGO
                                        desde lo que el sub-agente devolvio — nunca su
                                        transcripcion cruda
  un paso puede cambiar el plan         no hay plan que cambiar: se construye paso a paso,
                                        que es precisamente la diferencia

POR QUE FALTABA. El catalogo tenia los dos extremos de la familia —plan fijo con replan
(`dag_strategy`) y particion fija (`handoff`)— y no el del medio, que es justo el que hoy
se llama «subagentes» en la practica: un orquestador que despacha de a uno segun lo que
vaya encontrando. Sin el, la familia se mide en sus bordes y no donde vive.

NO VIOLA EL INVARIANTE, Y LA DISTINCION ES FINA. El invariante prohibe que el LLM maneje
FLUJO DE CONTROL DEL SISTEMA: que decida que paradigma corre o si un gate pasa. Elegir la
proxima sub-tarea es una ACCION, igual que `react` eligiendo su proxima herramienta. Lo
que el supervisor NO puede hacer —y por eso el corte de abajo lo impone el codigo— es
decidir cuando se le acaba el presupuesto.

DOS COTAS QUE LAS PONE EL CODIGO, no el modelo:
  - `MAX_DISPATCHES` acota cuantos sub-agentes se despachan en total. Sin eso el costo lo
    fija una decision del modelo y el brazo deja de ser proyectable — que es la razon por
    la que `react` y `reflection` proyectan llamadas desde sus propias `max_iterations`.
  - un despacho REPETIDO no se ejecuta. Que el supervisor pida dos veces lo mismo es un
    modo de falla observado en bucles de este tipo, y pagarlo dos veces mediria la falla
    en vez de la topologia.
"""

from __future__ import annotations

from typing import Any

from ..llm import LLMClient, Usage
from .. import guards
from ..tools import ToolSurface
from . import answer_contract, Result, _run_tool_loop, parse_answer
from .parsing import extract_json

# Cuantos sub-agentes como maximo. Lo fija el codigo: el gasto de un brazo no puede
# depender de cuando el modelo decida que ya esta.
MAX_DISPATCHES = guards.SUPERVISOR_DISPATCHES
# Turnos de herramienta por sub-agente. Acotado por la misma razon.
MAX_TURNS_PER_SUB = guards.SUPERVISOR_TURNS_PER_SUB
# CUANTAS UNIDADES VE UN SUB-AGENTE. Es la constante que hace que esto sea un patron de
# sub-agentes y no `react` con pasos: su contexto es una VENTANA sobre el material, no el
# material. Mas chica que esto y el sub-agente no puede resolver nada que cruce dos
# unidades; mas grande y deja de aislar.
SUB_SCOPE_UNITS = guards.SUPERVISOR_SCOPE_UNITS
SUPERVISOR_PROMPT = """You are coordinating specialists to answer a task.

Task: {question}

There are {n_units} document units available. Specialists can search and read them.

What has been established so far:
{state}

Return JSON only. Either dispatch ONE specialist:
  {{"dispatch": "a specific, self-contained sub-question"}}
or, if what is established already answers the task:
  {{"done": true}}

Dispatch the sub-question that most reduces what is still missing. Do not repeat a
sub-question that was already answered."""

SUB_PROMPT = """You are a specialist. Answer ONLY this sub-question, using the tools.

Sub-question: {sub}

Be specific and cite the unit ids you used. If the answer is not in the units, say so."""


def supervisor(client: LLMClient, surface: ToolSurface, task: dict[str, Any]) -> Result:
    """Despacha de a UN sub-agente, mirando lo que volvio antes de decidir el siguiente.

    QUE HACE: el tercero de la familia de sub-agentes, y el que no fija su plan. A
    diferencia de `dag_strategy` —que planifica antes de ejecutar— y de `handoff` —que fija
    sus alcances en el codigo—, este mira el resultado de cada despacho y recien ahi elige
    el proximo.

    GUARDAS QUE LO GOBIERNAN:
      · `MAX_DISPATCHES = 4` despachos; `MAX_TURNS_PER_SUB = 3` vueltas por sub-agente
      · `SUB_SCOPE_UNITS = 8`: el sub-agente recibe una **ventana de 8 unidades** recortada
        por el codigo mediante una busqueda sobre la sub-pregunta — **no el alcance
        entero**. El aislamiento de contexto no es una optimizacion del patron: es su
        definicion
      · esa ventana es tambien su techo: si la respuesta esta fuera de las 8 que la
        busqueda trajo, el sub-agente no la puede alcanzar

    CUANDO ES EL CAMINO CORRECTO: cuando las sub-preguntas dependen unas de otras pero cada
    una se resuelve local — se necesita adaptar el plan sin perder aislamiento.

    CUANDO NO: cuando hace falta cobertura garantizada. Medido: hace **1.114 busquedas con
    70% de esterilidad y rachas de 36** — es el brazo que mas busca en vano del plantel.
    """
    usage = Usage()
    iterations = 0
    establecido: list[tuple[str, str]] = []
    despachadas: set[str] = set()
    transcript: list[dict[str, Any]] = []

    for _ in range(MAX_DISPATCHES):
        estado = (
            "\n".join(f"- {q}\n  -> {a}" for q, a in establecido)
            if establecido else "(nothing yet)"
        )
        plan = client.complete(
            messages=[{
                "role": "user",
                "content": SUPERVISOR_PROMPT.format(
                    question=task["question"],
                    n_units=len(surface.unit_ids()),
                    state=estado,
                ),
            }],
            max_tokens=400,
        )
        usage.merge(plan.usage)
        iterations += 1

        decision = extract_json(plan.text, default={}, sink=surface)
        if not isinstance(decision, dict):
            decision = {}
        if decision.get("done") is True and establecido:
            # `and establecido`: un «done» antes de haber establecido NADA no es una
            # decision de parar, es un modelo que no entendio. Parar ahi mediria eso.
            break

        sub = str(decision.get("dispatch") or "").strip()
        if not sub:
            break
        clave = " ".join(sub.lower().split())
        if clave in despachadas:
            # UN DESPACHO REPETIDO NO SE EJECUTA. Pagarlo mediria el bucle degenerado en
            # vez de la topologia, y el supervisor ya tiene la respuesta en su estado.
            break
        despachadas.add(clave)

        # EL SUB-AGENTE RECIBE UN PEDAZO DE CONTEXTO, NO TODO — y eso ES el patron
        # (correccion del autor, 2026-08-29). Con la superficie completa cada sub-agente
        # ve las mismas unidades que el padre, y entonces esto no es un supervisor con
        # sub-agentes: es `react` con mas pasos y una llamada de coordinacion de mas. El
        # aislamiento de contexto no es una optimizacion del patron, es su definicion.
        #
        # QUIEN RECORTA ES EL CODIGO. El alcance sale de una busqueda sobre la sub-pregunta
        # —una funcion determinista del texto que el supervisor despacho— y no de que el
        # modelo enumere ids. Si el modelo eligiera las unidades, la frontera del
        # sub-agente la estaria dibujando el sensor, y ahi si se cruzaria el invariante.
        #
        # Y el recorte es de la VISTA: el sub-agente no puede leer afuera porque las
        # unidades no estan, no porque se le haya pedido que no lo haga.
        # LA VENTANA ESCALA CON EL ALCANCE cuando el balance esta encendido. Con el 8
        # fijo —el default historico— medido: en **28 de 78 tareas el sub-agente ve el
        # alcance ENTERO**, asi que el aislamiento que el docstring de arriba llama «no una
        # optimizacion sino su definicion» no existe en el 36% del corpus. Una ventana fija
        # sobre un alcance variable no es una ventana: es una constante que a veces resulta
        # ser todo.
        ventana = guards.ventana_sub_agente(
            len(surface.unit_ids()), surface.effort_balanced
        )
        alcance = surface.hybrid.rank(surface.view, sub, ventana)
        if not alcance:
            # Sin ningun candidato, un alcance vacio dejaria al sub-agente sin nada que
            # leer y su fracaso mediria la busqueda, no la topologia. Se le da el alcance
            # entero y queda registrado en la secuencia de herramientas lo que hizo con el.
            alcance = surface.unit_ids()
        completion, sub_usage, sub_transcript, turns = _run_tool_loop(
            client, surface.scoped(alcance),
            [{"role": "user", "content": SUB_PROMPT.format(sub=sub)}],
            max_iterations=MAX_TURNS_PER_SUB,
        )
        usage.merge(sub_usage)
        transcript.extend(sub_transcript)
        iterations += turns
        texto = (completion.text if completion else "") or ""
        # EL ESTADO LO ESCRIBE EL CODIGO, no el sub-agente: entra lo que devolvio, acotado,
        # y nunca su transcripcion cruda. Arrastrar transcripciones convertiria esto en un
        # solo agente con pasos, que es otro patron.
        establecido.append((sub, texto.strip()[:800]))

    if not establecido:
        # Sin nada establecido no hay sintesis que hacer, y fabricar una respuesta desde
        # cero seria otro paradigma (`direct`) escondido adentro de este.
        # `cross_unit_lookups` y `hallucinated_units` son PROPIEDADES derivadas de
        # `tool_usage`, no campos: pasarlos explicitamente explota. Y `raw_text` va porque
        # las obligaciones tipadas viven antes de la linea ANSWER, asi que verificarlas
        # sobre `answer` daria «no declarada» siempre.
        return Result(
            answer="", raw_text="", usage=usage, transcript=transcript,
            iterations=iterations, tool_usage=surface.usage(),
        )

    resumen = "\n\n".join(f"Sub-question: {q}\nFinding: {a}" for q, a in establecido)
    final = client.complete(
        messages=[{
            "role": "user",
            "content": (
                f"Task: {task['question']}\n\n"
                f"Findings from the specialists you dispatched:\n{resumen}\n\n"
                f"{answer_contract(surface)}"
            ),
        }],
    )
    usage.merge(final.usage)
    iterations += 1
    return Result(
        answer=parse_answer(final.text),
        raw_text=final.text or "",
        usage=usage,
        transcript=transcript,
        iterations=iterations,
        tool_usage=surface.usage(),
    )


def projected_calls(dispatches: int = MAX_DISPATCHES) -> int:
    """Cota de llamadas, para que la factibilidad pueda cotizarlo antes de gastar.

    Una decision del supervisor mas el bucle de su sub-agente, por despacho, mas la
    sintesis. Es COTA y no estimacion: el supervisor puede parar antes, y una cota que a
    veces se pasa no sirve para admitir un plan.
    """
    return dispatches * (1 + MAX_TURNS_PER_SUB) + 1
