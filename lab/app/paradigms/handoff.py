"""Agentes con alcance propio y transferencia AUTORIZADA POR CODIGO.

QUE LO HACE UN PATRON Y NO FRASEO. Las cuatro preguntas de `PATRON_O_FACTOR.es.md`:

  cuantas llamadas y quien las decide   acotadas por la cantidad de alcances, las fija el
                                        codigo — no un bucle que el modelo corta
  quien elige la proxima accion         el CODIGO decide si hay transferencia
  estado compartido y quien lo escribe  el CONTRATO, escrito por el codigo desde una
                                        proposicion tipada del agente
  un paso puede cambiar el plan         si, acotado: una transferencia re-alcanza

Difiere de `dag_strategy` —ahi el MODELO dibuja el grafo proponiendo sub-preguntas— y de
un fan-out fijo, que no tiene transferencia. Es otro grafo de control, no otro prompt.

Y DIFIERE DEL HANDOFF DE LA INDUSTRIA EN LO QUE IMPORTA. Los tres frameworks consultados
—Microsoft Agent Framework, OpenAI Agents SDK, Google ADK— hacen lo mismo: **el handoff ES
una herramienta que el modelo llama**, `transfer_to_<agente>()`. O sea, flujo de control
decidido por el modelo, que es exactamente lo que el invariante de este producto prohibe.

Aca el modelo puede PROPONER la transferencia como proposicion tipada; la autoriza una
regla determinista sobre lo que el agente declaro. Tres consecuencias medibles y no
retoricas:

  reproducible  misma base de creencias => mismo handoff. Con `transfer_to_agent()` la
                transferencia hereda toda la varianza del modelo
  gateable      un handoff hacia capacidad irreversible puede exigir procedencia; una
                llamada a herramienta no puede exigirsela a si misma
  auditable     la transferencia entra al registro como cualquier otra decision

Y HAY UNA LECCION DE HOY ADENTRO. `P20` midio que rechazar una llamada NO le quita la
decision al modelo: la re-emite con otras palabras el 69% de las veces. Por eso aca el
agente **no tiene** una herramienta de transferencia que se le pueda rechazar. La accion
no existe: el agente termina su turno declarando lo que le falta, y quien transfiere es el
codigo. Quitar la decision es no ofrecer la accion.
"""

from __future__ import annotations

from typing import Any

from ..beliefs import Belief, BeliefBase, Provenance
from .. import guards
from ..llm import LLMClient, Usage
from ..tools import ToolSurface
from . import ANSWER_CONTRACT, answer_contract, Result, _run_tool_loop, parse_answer
from .parsing import extract_json

# Cuantos alcances. Dos es el minimo que tiene transferencia; mas alcances multiplican el
# costo fijo sin cambiar la estructura, y la estructura es lo que se mide.
SCOPES = guards.HANDOFF_SCOPES
# Vueltas por agente. Acotado por el codigo, no por el modelo.
MAX_TURNS_PER_AGENT = guards.HANDOFF_TURNS_PER_AGENT
# Piso para autorizar la transferencia. El agente la PROPONE —eso es su opinion, asi que
# ELICITED— y la regla exige que lo que pide exista LITERAL en otro alcance, que es un
# hecho computable sobre el material. Sin eso, un agente podria pedir transferencia
# indefinidamente y el patron degeneraria en un bucle con otro nombre.
# El agente PROPONE a su procedencia —es su lectura— y el codigo AUTORIZA a la suya.
# Declararlas y no usarlas era la misma falla que este barrido busca, cometida acá.
HANDOFF_FLOOR_PROPOSAL = Provenance.ELICITED
HANDOFF_FLOOR_AUTHORISATION = Provenance.COMPUTED

# EL FORMATO DE `answer` VA ADENTRO DEL CONTRATO, y no al lado.
#
# Antes se concatenaba `answer_contract` —«responde con una linea ANSWER: <x>»— a este
# contrato, que pide JSON y nada mas. Los dos no se pueden cumplir, y CUAL OBEDECIA ERA UNA
# MONEDA AL AIRE: en `c7-000-neg` la replica t0 obedecio el `ANSWER:` y salio «no
# escalation» (correcto), y t1 y t2 obedecieron el JSON. Tres replicas de la misma celda con
# formatos de salida distintos — no por temperatura, por contratos en conflicto.
#
# Sacar el segundo contrato quito la ambiguedad y dejo al campo `answer` SIN FORMA: el
# agente empezo a escribir prosa ahi («Marta Arrieta is identified as cus...»), que contra un
# veredicto corto puntua cero igual. La correccion completa no es elegir uno de los dos
# contratos: es que el que queda LLEVE ADENTRO lo que el otro pedia.
AGENT_CONTRACT = """You own ONLY the units listed below. You cannot see any others.

Work your units. Then answer with JSON only:
{"status": "resolved", "answer": "<your answer>"}
  — you can answer from your units alone; or
{"status": "needs", "missing": "<the exact literal string you could not resolve>",
 "partial": "<what you did establish>"}
  — your units mention something they do not define.

`answer` must be the VALUE ALONE and nothing else: a name, a number, a verdict. No sentence,
no explanation, no restating of the question. If several values are required, separate them
with '; '. A sentence in `answer` is a wrong answer even when it contains the right value.

`missing` must be a string that appears VERBATIM in your units. Do not paraphrase it and
do not invent one: it is looked up literally in the other scopes, and a paraphrase finds
nothing."""


def _scopes(unit_ids: list[str], n: int) -> list[list[str]]:
    """Reparto deterministico por indice. El mismo request da el mismo reparto.

    Con paso y no en bloques contiguos, por la misma razon que el roster de `C9`: un
    bloque contiguo agrupa unidades vecinas del corpus, y ahi el reparto mediria
    localidad del indice en vez de alcance.
    """
    return [sorted(unit_ids[i::n]) for i in range(n)] if unit_ids else []


# `_sub_surface` VIVIA ACA y se movio a `ToolSurface.scoped` (2026-08-29). No por
# prolijidad: no propagaba `terse_tools`, `offer_board`, `demand_obligations` ni
# `shared_state`, asi que adentro de un sub-agente esos factores no existian. Un olvido de
# campo en una copia hecha a mano es invisible; en la clase, `replace` los lleva todos.


def _authorises(base: BeliefBase, missing: str, scope: list[str],
                documents: dict[str, str]) -> bool:
    """La regla. El agente propone; esto decide.

    DOS CONDICIONES, y la segunda es la que hace determinista al patron:

      el agente declaro que le falta algo   proposicion `ELICITED` — es su lectura
      y ese algo esta LITERAL en otro       hecho `COMPUTED` sobre el material

    La segunda no es parseo de prosa: es contencion de una cadena que el agente ya
    enuncio, contra un texto. La direccion importa — buscar una cadena conocida adentro
    de un documento es finito; extraer del documento que cadenas hay es lo otro.
    """
    if not base.satisfies("handoff_requested", 0.0, HANDOFF_FLOOR_PROPOSAL):
        return False
    needle = " ".join(missing.lower().split())
    if len(needle) < 4:
        # Guarda de especificidad, la misma que la sonda: una cadena de tres caracteres
        # aparece en cualquier lado y autorizaria siempre.
        return False
    presente = any(needle in " ".join(documents[u].lower().split()) for u in scope)
    if not presente:
        return False
    # La AUTORIZACION es un hecho computable sobre el material, no la lectura del agente.
    # Se asienta a su propio piso para que el registro diga con que procedencia se
    # transfirio — y no herede la del que la pidio, que es el error que P-4 costo.
    base.assert_(Belief(
        proposition="handoff_authorised",
        value=missing,
        credence=1.0,
        provenance=HANDOFF_FLOOR_AUTHORISATION,
        evidence=f"{missing!r} aparece literal en un alcance posterior",
    ))
    return True


def handoff(client: LLMClient, surface: ToolSurface, task: dict[str, Any]) -> Result:
    """Alcances INDEPENDIENTES, y una transferencia que autoriza el codigo.

    QUE HACE: parte el alcance en `SCOPES` porciones disjuntas, le da una a cada
    sub-agente, y el codigo —no el modelo— decide cuando pasa de uno al siguiente. Cada
    sub-agente ve **solo sus unidades**: no puede leer afuera porque las unidades no estan,
    no porque se le haya pedido que no lo haga.

    GUARDAS QUE LO GOBIERNAN:
      · `SCOPES = 2` porciones; `MAX_TURNS_PER_AGENT = 6` vueltas por sub-agente
      · el reparto es un **paso por indice**, fijo: no se aprende ni se adapta al contenido
      · **la particion es la limitacion y la virtud**: garantiza cobertura y destruye
        cualquier relacion que cruce la costura

    CUANDO ES EL CAMINO CORRECTO: cuando hay que probar algo sobre TODO el alcance y las
    unidades son independientes entre si — una ausencia («ninguno cumple»), una
    enumeracion exhaustiva, una lista de lookups dada de antemano. Medido: gana 3 de las 5
    tareas del corpus que tienen un unico mejor brazo, y las tres son de ausencia.

    CUANDO NO: cuando la respuesta cruza unidades. Si la contradiccion esta entre la unidad
    3 y la 15, y el corte cae en el medio, **ningun sub-agente la ve** y los dos contestan
    con confianza.
    """
    usage = Usage()
    base = BeliefBase()
    units = surface.unit_ids()
    scopes = _scopes(units, SCOPES)
    transcript: list[dict[str, Any]] = []
    iterations = 0

    if len(scopes) < 2:
        # Un solo alcance no tiene transferencia que autorizar: el patron degenera en
        # una sola pasada, y se dice en vez de fingir que hubo handoff.
        scopes = [units]

    partials: list[str] = []
    # LA RESPUESTA DEL ULTIMO AGENTE QUE RESOLVIO. Se guarda al declararla y no se
    # reconstruye del texto: el texto del ultimo agente puede ser un `needs`, y el que
    # resolvio puede haber sido el anterior.
    resuelto: str = ""
    handed: dict[str, Any] | None = None

    for index, scope in enumerate(scopes):
        if not scope:
            continue
        contract = AGENT_CONTRACT + "\n\nYour units: " + ", ".join(scope)
        if handed is not None:
            # EL CONTRATO QUE VIAJA. No es "contexto que se arrastra": es lo que el
            # agente anterior DECLARO que le faltaba, mas lo que si establecio.
            contract += (
                f"\n\nA previous agent handed this to you.\n"
                f"It could not resolve: {handed['missing']!r}\n"
                f"It did establish: {handed['partial']}"
            )
        # UN SOLO CONTRATO DE SALIDA, y esto era un bug que costo una corrida.
        #
        # Aca iba tambien `answer_contract(surface)`, que pide una linea `ANSWER: <x>`,
        # mientras `AGENT_CONTRACT` pide **JSON y nada mas**. El sub-agente recibia las dos
        # instrucciones y no podia cumplir las dos: obedecia al JSON —que es el que su rol
        # necesita, porque tiene que poder decir «me falta esto»— y despues el ensamblado
        # leia ese JSON con `parse_answer`, que no encuentra `ANSWER:` y devuelve el texto
        # entero. La respuesta calificada terminaba siendo la palabra `needs`.
        #
        # El F1 de «needs» contra un numero de cuenta es cero POR CONSTRUCCION, asi que
        # `handoff` no estaba fallando la tarea: estaba fallando al decir su respuesta. Se
        # midio en 11 celdas de `luna` antes de encontrarlo.
        #
        # El contrato de formato del banco lo aplica el ENSAMBLADO, una sola vez y al final
        # — que es donde vive la respuesta del patron, no en cada sub-agente.
        messages = [{
            "role": "user",
            "content": f"Task: {task['question']}\n\n{contract}",
        }]

        completion, sub_usage, sub_transcript, turns = _run_tool_loop(
            client, surface.scoped(scope), messages,
            max_iterations=MAX_TURNS_PER_AGENT,
        )
        usage.merge(sub_usage)
        transcript.extend(sub_transcript)
        iterations += turns

        payload = extract_json(completion.text if completion else "", default={},
                               sink=surface)
        status = payload.get("status") if isinstance(payload, dict) else None
        partial = str(payload.get("partial") or payload.get("answer") or "")
        if partial:
            partials.append(partial)

        if status == "resolved":
            # LO QUE EL AGENTE DECLARO COMO RESPUESTA, tomado de su campo y no del texto.
            # Si un agente posterior tambien resuelve, gana el suyo: es el que tuvo la
            # transferencia y por lo tanto mas evidencia.
            declarado = str(payload.get("answer") or "").strip()
            if declarado:
                resuelto = declarado
            handed = None
            continue

        missing = str(payload.get("missing") or "")
        if not missing:
            continue

        # EL AGENTE PROPONE. Entra como su lectura, no como un hecho.
        base.assert_(Belief(
            proposition="handoff_requested",
            value=missing,
            credence=0.8,
            provenance=Provenance.ELICITED,
            evidence=f"el agente {index} declaro que no puede resolver {missing!r}",
        ))

        # EL CODIGO DECIDE. Se autoriza contra los alcances que TODAVIA no corrieron:
        # transferir hacia atras seria un bucle, no un handoff.
        adelante = [u for s in scopes[index + 1:] for u in s]
        if adelante and _authorises(base, missing, adelante, surface.view.documents):
            # La autorizacion ya quedo asentada por la regla, con su propia
            # procedencia. Asentarla otra vez aca duplicaria el hecho.
            handed = {"missing": missing, "partial": partial}
        else:
            handed = None

    # EL ENSAMBLADO SALE DE LO QUE LOS AGENTES DECLARARON, no del texto crudo del ultimo.
    #
    # Antes era `parse_answer(crudo) or " ".join(partials)`, y el `or` no rescataba nunca:
    # `parse_answer` devuelve el texto ENTERO cuando no encuentra `ANSWER:`, asi que nunca
    # da vacio y `partials` era codigo muerto. Sobre un JSON eso devolvia `needs`.
    #
    # Ahora se lee el campo que el contrato del sub-agente define, en el orden que importa:
    # la respuesta del ULTIMO agente que resolvio —que es el que tuvo la transferencia si
    # hubo— y si ninguno resolvio, lo que los agentes SI establecieron. Que ninguno resuelva
    # es un resultado del patron y tiene que llegar como respuesta pobre, no como la palabra
    # `needs`.
    answer = resuelto or " ".join(p for p in partials if p)
    crudo = completion.text if completion else ""
    return Result(
        answer=answer,
        raw_text=crudo,
        usage=usage,
        transcript=transcript,
        iterations=iterations,
        tool_usage=surface.usage(),
    )
