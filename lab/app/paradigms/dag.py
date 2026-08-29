"""DAG with verify-replan over a shared blackboard.

The seventh and most elaborate paradigm in the harness. It is the composition that
production RAG-agent systems converge on when a single reasoning loop stops covering the
task, and it is included because a comparison that omits the most sophisticated
available topology is not a fair comparison — it stacks the deck for the simple ones.

Structure:

  plan -> assign waves (topological, cycle-detected) -> execute each wave against a
  shared blackboard -> verify on 4 dimensions -> replan or synthesise

It composes three patterns from the catalogue: Blackboard (v1 whitepaper section 2.2.8),
Chain where the dependency graph forces order, and Barrier Fan-Out within each wave.

The parameterisation is deliberately kept as a block of named constants rather than
tuned inline, because the count itself is a finding. A topology with a dozen thresholds
— replan depth, readiness, diminishing returns, per-agent iteration caps, tool-call caps
— is a topology whose behaviour is set by hand rather than derived, and the harness
exists partly to measure whether that hand-tuning generalises. The catalogue records the
smell under Constant Soup.

Two honest departures from how such a strategy runs in production, both recorded because
they bound what a measurement here proves:

1. EXECUTION IS SEQUENTIAL. A wave would normally run concurrently under a concurrency
   cap. Concurrency changes wall-clock but not utility and not token count, which are
   the quantities under study. So answer quality and token economics are comparable;
   measured latency is NOT, and must not be reported as such.

2. NO PRE-FETCH, HyDE OR ENTITY RESOLUTION. Real deployments seed the blackboard from a
   retrieval subgraph. Those are retrieval-quality components shared across every
   strategy in such a system, not part of the DAG control structure. Including them here
   would hand this paradigm a retrieval advantage the other six do not have, which would
   measure the pre-fetch rather than the topology.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .parsing import extract_json, well_formed
from .blackboard import Blackboard
from ..llm import LLMClient, Usage
from ..feasibility import MAX_ORCHESTRATION_CALLS
from ..tools import ToolSurface
from . import ANSWER_CONTRACT, answer_contract, Result, _run_tool_loop, parse_answer

# Typical production values for this topology. Held fixed across the study so the
# paradigm is measured at one configuration rather than at whichever one happened to
# suit each task.
DAG_MAX_SUB_QUESTIONS = 4
DAG_MAX_REPLAN_ITERATIONS = 3
DAG_READY_THRESHOLD = 0.8
DAG_DIMINISHING_RETURNS = 0.05
DAG_SUB_AGENT_ITERATIONS = 10



@dataclass(frozen=True)
class DagShape:
    """La forma del grafo de control, DERIVADA del request y no propuesta por el modelo."""

    max_sub_questions: int
    max_replans: int
    reason: str
    governed_by_coupling: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_sub_questions": self.max_sub_questions,
            "max_replans": self.max_replans,
            "reason": self.reason,
            "governed_by_coupling": self.governed_by_coupling,
        }


def projected_calls(ramas: int, replans: int) -> int:
    """Las llamadas que una forma cuesta en el peor caso. LA MISMA formula que factibilidad.

    `feasibility.check("dag_strategy")` proyecta `4 * 10 * 4 + 4 + 1` con los topes fijos.
    Esta funcion es esa cuenta parametrizada, y existe para que las dos no puedan
    discrepar: si la forma se derivara con una aritmetica propia, podria elegir un grafo
    que la factibilidad declara infactible, y el registro tendria un paradigma admitido
    corriendo una forma que su propia cota prohibe.
    """
    return ramas * DAG_SUB_AGENT_ITERATIONS * (replans + 1) + ramas + 1


def dag_shape(task: dict[str, Any], coupling: float | None = None) -> DagShape:
    """Cuantos nodos y cuanta profundidad de replan, por aritmetica sobre el request.

    EL PROBLEMA QUE CIERRA (`D-3`). Hasta hoy el MODELO dibujaba el grafo de control: el
    planificador proponia `sub_questions` con sus dependencias y `_assign_waves` solo
    topologizaba lo que el modelo dijo. Los topes eran dos constantes fijas —4 y 3— iguales
    para una tarea de 3 unidades y para una de 400. Es la version estructural de `D-1`: el
    invariante del producto dice que el modelo es SENSOR y no maneja flujo de control, y un
    grafo de control es flujo de control.

    LAS TRES COTAS, y ninguna necesita una constante nueva:

      material    mas de una rama por unidad no descompone nada: reparte la misma unidad
                  en dos preguntas. El tope natural es `n_units`
      llamadas    `MAX_ORCHESTRATION_CALLS`, la MISMA cota que la factibilidad impone, con
                  la misma formula. Un replan MULTIPLICA porque re-corre todas las olas
      piso        una rama sin replan es el caso degenerado y sigue siendo un DAG valido
                  —de un nodo—. Se dice, no se finge que hubo descomposicion

    SE BUSCA DE MAYOR A MENOR y no se resuelve en cerrado a proposito: el espacio tiene
    a lo sumo `4 x 4` puntos, asi que enumerarlo es exacto y no hay redondeo que discuta
    con la cota. Una formula cerrada ahorraria dieciseis comparaciones y podria diferir
    de `projected_calls` en el borde, que es donde importa.

    LO QUE NO GOBIERNA, Y ES LO QUE MAS IMPORTARIA. El acoplamiento decide si las ramas
    pueden correr independientes: con acoplamiento alto, descomponer en paralelo mide
    cualquier cosa menos la cadena. **La sonda lo mide y esa lectura no llega hasta aca**
    —ni el `ToolSurface` ni la tarea la transportan— asi que `governed_by_coupling` es
    `False` y se REGISTRA. Es la misma forma que el barrido de la 7.17 busca: una creencia
    completa, medida, que no llega a donde se decide.
    """
    n_units = max(1, len(task.get("unit_ids") or []))
    tope_ramas = max(1, min(DAG_MAX_SUB_QUESTIONS, n_units))

    # EL ACOPLAMIENTO ACOTA LAS RAMAS, y es la cota que faltaba. Con acoplamiento alto las
    # unidades dependen unas de otras: descomponer en paralelo mide cualquier cosa menos
    # la cadena, porque cada rama ve un pedazo que no se explica solo. La cota es lineal y
    # no un interruptor —el acoplamiento es continuo— y nunca baja de una rama, que sigue
    # siendo un DAG valido.
    #
    # `None` NO es cero. Sin sondeo no hay con que acotar y se deja el tope del material;
    # tratarlo como cero haria que la forma mas paralela sea el default silencioso justo
    # donde nadie midio.
    if coupling is not None:
        if not 0.0 <= coupling <= 1.0:
            raise ValueError(
                f"acoplamiento {coupling}: es una fraccion y tiene que estar en [0, 1]. "
                f"Un valor fuera de rango no acota nada — invierte la cota."
            )
        tope_ramas = max(1, min(tope_ramas, round(DAG_MAX_SUB_QUESTIONS * (1 - coupling))))

    mejor = (1, 0)
    for ramas in range(tope_ramas, 0, -1):
        for replans in range(DAG_MAX_REPLAN_ITERATIONS, -1, -1):
            if projected_calls(ramas, replans) <= MAX_ORCHESTRATION_CALLS:
                mejor = (ramas, replans)
                break
        else:
            continue
        break
    ramas, replans = mejor

    if ramas == 1:
        motivo = (
            f"una sola rama: {n_units} unidad(es) y la cota de {MAX_ORCHESTRATION_CALLS} "
            f"llamadas. Es un DAG de un nodo, y se dice en vez de fingir descomposicion"
        )
    elif ramas < DAG_MAX_SUB_QUESTIONS:
        limita = "el material" if n_units < DAG_MAX_SUB_QUESTIONS else "la cota de llamadas"
        motivo = (
            f"{ramas} ramas y {replans} replan(s) = {projected_calls(ramas, replans)} "
            f"llamadas: {limita} acota por debajo del tope fijo de "
            f"{DAG_MAX_SUB_QUESTIONS}"
        )
    else:
        motivo = (
            f"{ramas} ramas y {replans} replan(s) = {projected_calls(ramas, replans)} "
            f"llamadas: el tope fijo manda, el material ({n_units} unidades) alcanza"
        )
    if coupling is not None:
        motivo += f"; acoplamiento {coupling:.2f} acota a {tope_ramas} rama(s)"
    return DagShape(ramas, replans, motivo,
                    governed_by_coupling=coupling is not None)


# El blackboard vive en `blackboard.py`: es una DIMENSION (estado compartido), no una
# propiedad de esta topologia. Mientras estuvo definido aca, la pregunta "¿react mejora
# con estado compartido?" no se podia ni formular, y "el efecto dag_strategy" quedaba
# siendo la conjuncion de la topologia de olas y el blackboard, sin nada que las separe.


# -- planning ------------------------------------------------------------------

PLANNER_PROMPT = """\
You are a query parser for an investigative platform.

Your job: EXTRACT the questions that are ALREADY in the user's query. \
Do NOT invent new questions. Do NOT rephrase. Do NOT add search strategies.

RULES:
1. If the query contains ONE question -> return it as 1 sub-question, unchanged.
2. If the query contains MULTIPLE distinct questions -> separate them (max {max_sub}).
3. If one question depends on another's answer -> set dependencies.
4. Keep the EXACT wording of the original questions as much as possible.
5. NEVER add questions the user didn't ask.

IMPORTANT: When in doubt, use FEWER sub-questions. A single agent with many \
iterations is better than splitting a coherent question into pieces.

Query: {query}
Units available: {n_units}

Return JSON only:
{{"sub_questions": [{{"id": "sq_001", "question": "...", "depends_on": []}}]}}"""

EXECUTE_PROMPT = """\
EXHAUSTIVE EXTRACTION agent — you MUST find EVERY matching item, not just the first.

You are one of several agents running in parallel. Each covers different aspects. \
A shared blackboard tracks overall progress.

WORKFLOW:
1. Search EVERY unit relevant to YOUR sub-question — do NOT stop at first match
2. Extract: exact names, roles, dates, amounts, addresses — be precise

TOOLS:
- search: keyword search across units. Start here.
- read: read one unit in full.

CRITICAL: check the blackboard — if other agents already found items, \
focus on what's STILL MISSING. Do not duplicate work.

{blackboard}

YOUR SUB-QUESTION: {sub_question}"""

VERIFY_PROMPT = """\
Evaluate each sub-question result for completeness and quality.

For each result, assess these 4 dimensions:
1. **Completeness**: Does it fully answer the sub-question?
2. **Evidence quality**: Are there specific facts with unit citations?
3. **Specificity**: Concrete data (names, dates, amounts) vs vague claims?
4. **Contradictions**: Any conflicts between pieces of evidence?

Original query: {query}

Results:
{results}

Output a JSON array with one entry per sub-question, JSON only:
[{{"sub_question_id": "...", "status": "complete|partial|incomplete", \
"completeness_score": 0.0, "missing_aspects": [], "contradictions": [], \
"recommendation": "accept|retry"}}]"""

REPLAN_PROMPT = """\
Some sub-questions have gaps or contradictions. Generate corrective actions.

For each incomplete/partial result:
- If partially answered: focus retry on MISSING aspects only
- If not answered: rephrase the question or target different units
- If contradictions found: add a sub-question that searches different sources \
to resolve the conflict

Preserve all "complete" results — do NOT re-execute them.
Give retry sub-questions NEW IDs (append _r1, _r2 to original ID).

Original query: {query}
Verification: {verification}

Return JSON only:
{{"sub_questions": [{{"id": "sq_001_r1", "question": "...", "depends_on": []}}]}}"""

SYNTHESIZE_PROMPT = """\
Combine exhaustive extraction results from parallel agents into a COMPLETE answer.

RULES:
- COMPLETENESS is the priority — include EVERY item found by any agent
- Consolidate duplicates: same person with reversed name counts as ONE entry
- Merge same entity from multiple agents into ONE entry with ALL units
- Preserve ALL details: names, roles, dates, amounts, addresses
- If the question asks "how many", give an EXACT count

Original query: {query}

Agent results:
{results}

{answer_contract}"""


def _assign_waves(sub_questions: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Topological wave assignment with cycle detection.

    A cycle collapses to one wave rather than raising. Tolerating a malformed plan and
    proceeding is the production behaviour; aborting would measure a different
    strategy from the one under test.
    """
    by_id = {sq["id"]: sq for sq in sub_questions}
    depth: dict[str, int] = {}
    visiting: set[str] = set()

    def wave_for(node_id: str) -> int:
        if node_id in depth:
            return depth[node_id]
        if node_id in visiting:
            return 0  # cycle: break it by treating the node as root
        visiting.add(node_id)
        deps = [d for d in by_id.get(node_id, {}).get("depends_on", []) if d in by_id]
        depth[node_id] = 0 if not deps else 1 + max(wave_for(d) for d in deps)
        visiting.discard(node_id)
        return depth[node_id]

    for sq in sub_questions:
        wave_for(sq["id"])

    waves: dict[int, list[dict[str, Any]]] = {}
    for sq in sub_questions:
        waves.setdefault(depth[sq["id"]], []).append(sq)
    return [waves[k] for k in sorted(waves)]


def _parse_json(text: str, key: str | None = None) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        cleaned = cleaned[4:] if cleaned.startswith("json") else cleaned
    parsed = json.loads(cleaned)
    return parsed[key] if key else parsed


def dag_strategy(
    client: LLMClient, surface: ToolSurface, task: dict[str, Any]
) -> Result:
    """Plan -> waves -> verify -> replan (<=3) -> synthesise, over a blackboard."""
    usage = Usage()
    # EL MISMO OBJETO que la tool escribe. Dos boards serian dos «estados
    # compartidos» a la vez, y un sub-agente que postea no veria lo que el codigo
    # asento en las olas anteriores.
    board = surface.board_state
    query = task["question"]
    unit_ids = surface.unit_ids()
    iterations = 0
    # The blackboard renders every finding into every sub-agent prompt, so its
    # size is a context cost that grows with the number of sub-questions. Capped
    # for the same reason map_reduce's reduce step is: accumulation scales until
    # it does not.
    max_board_chars = int(task["budget_tokens"]) * 4 // 3

    # LA FORMA SE DERIVA ANTES DE PREGUNTAR. El planificador recibe el tope ya calculado,
    # asi que el modelo propone DENTRO de una forma que el codigo fijo — en vez de proponer
    # la forma y que el codigo la acepte.
    shape = dag_shape(task, getattr(surface, "coupling", None))

    # EL ESTADO COMPARTIDO ES UN FACTOR, y apagarlo deja la topologia intacta: siguen las
    # mismas olas, el mismo verify y los mismos replans. Lo unico que cambia es si cada
    # sub-agente ve lo que los anteriores encontraron. Esa es exactamente la separacion
    # que `F-2` pide, y sin ella «el efecto dag_strategy» no se puede atribuir.
    usa_board = getattr(surface, "shared_state", None)
    usa_board = True if usa_board is None else usa_board

    # ---- Phase 1: plan
    plan_completion = client.complete(
        messages=[{
            "role": "user",
            "content": PLANNER_PROMPT.format(
                max_sub=shape.max_sub_questions, query=query, n_units=len(unit_ids)
            ),
        }],
        max_tokens=800,
    )
    usage.merge(plan_completion.usage)
    iterations += 1

    # `well_formed` filtra ademas la FORMA, no solo el parseo: un plan que parsea pero
    # trae elementos sin `id` explotaba dos lineas mas abajo, en `_assign_waves`, FUERA
    # de este try — o sea que el paradigma degradaba con un JSON roto y moria con un JSON
    # valido de forma equivocada, que son incoherentes entre si.
    sub_questions = well_formed(
        extract_json(plan_completion.text, "sub_questions", sink=surface),
        "id", "question", sink=surface,
    )[:shape.max_sub_questions]
    if not sub_questions:
        # A malformed plan degrades to a single sub-question equal to the query. This
        # is how such strategies behave in practice, and removing it would measure a
        # tidier paradigm than anyone actually runs.
        sub_questions = [{"id": "sq_001", "question": query, "depends_on": []}]

    extractions: dict[str, str] = {}
    previous_avg = -1.0

    for iteration in range(shape.max_replans + 1):
        # ---- Phase 2: execute waves
        for wave in _assign_waves(sub_questions):
            for sub in wave:
                if sub["id"] in extractions:
                    continue  # a "complete" result is never re-executed
                messages = [{
                    "role": "user",
                    "content": EXECUTE_PROMPT.format(
                        blackboard=board.render() if usa_board else "(sin estado compartido)",
                        sub_question=sub["question"],
                    ),
                }]
                completion, sub_usage, transcript, sub_iters = _run_tool_loop(
                    client, surface, messages, max_iterations=DAG_SUB_AGENT_ITERATIONS
                )
                usage.merge(sub_usage)
                iterations += sub_iters

                text = completion.text if completion else ""
                extractions[sub["id"]] = text
                if usa_board and len(board.render()) < max_board_chars:
                    board.add_finding(sub["id"], text[:600])
                # Units actually read come from the surface, which tracks them.
                # This used to add `tool_call_id` values, which are call identifiers
                # and never unit ids — so the blackboard advertised a list of units
                # that did not exist.
                board.visited_units.update(surface.units_read)

        results_block = "\n\n".join(
            f"{sid}: {text[:900]}" for sid, text in extractions.items()
        )

        # ---- Phase 3: verify
        verify_completion = client.complete(
            messages=[{
                "role": "user",
                "content": VERIFY_PROMPT.format(query=query, results=results_block),
            }],
            max_tokens=1200,
        )
        usage.merge(verify_completion.usage)
        iterations += 1

        try:
            verification = _parse_json(verify_completion.text)
            scores = [float(v["completeness_score"]) for v in verification]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            all_accept = all(v["recommendation"] == "accept" for v in verification)
            has_retries = any(v["recommendation"] == "retry" for v in verification)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            # Unparseable verification means the loop cannot judge itself, so it
            # synthesises best-effort rather than looping blind.
            break

        # ---- Phase 4: the verify router (dag_verify_router)
        if all_accept or avg_score >= DAG_READY_THRESHOLD:
            break
        if iteration >= shape.max_replans:
            break
        if previous_avg >= 0 and (avg_score - previous_avg) < DAG_DIMINISHING_RETURNS:
            break
        if not has_retries:
            break
        previous_avg = avg_score

        # ---- Phase 5: replan
        replan_completion = client.complete(
            messages=[{
                "role": "user",
                "content": REPLAN_PROMPT.format(
                    query=query, verification=json.dumps(verification)
                ),
            }],
            max_tokens=800,
        )
        usage.merge(replan_completion.usage)
        iterations += 1

        # Antes el filtro de abajo quedaba FUERA del try: `r["id"]` sobre un elemento
        # sin `id` mataba la tarea entera, justo despues de que el `except` de arriba
        # decidiera que un replan malformado sólo corta el bucle.
        retries = well_formed(
            extract_json(replan_completion.text, "sub_questions", sink=surface),
            "id", "question", sink=surface,
        )
        if not retries:
            break
        retries = [r for r in retries if r["id"] not in extractions]
        if not retries:
            break
        sub_questions = retries[:DAG_MAX_SUB_QUESTIONS]

    # ---- Phase 6: synthesise
    final = client.complete(
        messages=[{
            "role": "user",
            "content": SYNTHESIZE_PROMPT.format(
                query=query,
                results="\n\n".join(
                    f"{sid}: {text}" for sid, text in extractions.items()
                ),
                answer_contract=ANSWER_CONTRACT,
            ),
        }]
    )
    usage.merge(final.usage)
    iterations += 1

    return Result(
        answer=parse_answer(final.text),
        raw_text=final.text,
        usage=usage,
        transcript=[{"role": "system", "content": board.render()}],
        iterations=iterations,
        tool_usage=surface.usage(),
    )
