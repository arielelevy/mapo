"""Two modern paradigms, added 2026-08-26 against the measured failure roots.

`rewoo` attacks root (b) — paying O(history) per step: it plans EVERY tool call in one
pass (explicit dataflow via #E placeholders), executes them without the LLM in the loop,
and solves in a single final call. Two LLM calls total, no history resend. Its known
fragility is the mirror image: with no observation it cannot adapt when a hop's result
changes what the next hop should be.

`gist_reader` attacks root (d) — evidence larger than the window: a deterministic gist
table (one truncated summary per unit, built locally at zero LLM cost) goes into ONE
prompt; the model either answers from gists or names the units it must read in full,
which are fetched in batched reads bounded by the allowance. It is "direct over gists
plus targeted bulk read" — the read_all-done-right that the failure analysis asked for.

Both share the same surface, model, decoding and answer contract as the other seven.
No prompt cleverness: the difference under test is control structure.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from .parsing import extract_json, well_formed
from .. import guards
from ..llm import LLMClient, Usage
from ..features import entidad_en, indice_para
from ..tools import MAX_BATCH_READ, ToolFailure, ToolSurface, _summarise
from . import ANSWER_CONTRACT, Infeasible, answer_contract, Result, _finish

# Evidence caps. Substituting a full 8k-token unit into a search query would be
# nonsense; and the solver prompt must stay bounded by construction, not by hope.
SUBSTITUTION_CHARS = guards.REWOO_SUBSTITUTION_CHARS
EVIDENCE_ITEM_CHARS = guards.REWOO_EVIDENCE_ITEM_CHARS
MAX_PLAN_STEPS = guards.REWOO_PLAN_STEPS
# ARGUMENTOS QUE PIDEN UN IDENTIFICADOR, NO TEXTO. La sustitución de evidencia de ReWOO es
# textual —`#E1` se reemplaza por la salida del paso 1— y para una `query` eso está bien.
# Para `unit_ids` está mal, y ese error dejaba a `rewoo` estructuralmente impedido de leer.
ARGS_DE_ID = ("unit_ids", "unit_id", "entity_id", "ids")


def _ids_de(salida: str) -> str:
    """Los `unit_id` que trae la salida de una búsqueda, como lista separada por comas.

    POR QUÉ EXISTE (2026-08-30). El plan del modelo escribe `read(unit_ids="#E1")`, que es
    lo natural y lo que ReWOO significa en la literatura: un paso referencia el RESULTADO
    del anterior. Pero la sustitución reemplazaba `#E1` por el **JSON entero de la
    búsqueda** truncado, así que a `read` le llegaba un blob en vez de un id.

    Medido antes del arreglo: `rewoo` llamaba a `read` en **130 de 138 celdas y leía CERO
    unidades**, y era el único brazo del plantel con ids alucinados —36, contra 0 de todos
    los demás—. Contestaba desde los snippets y nunca abría un documento: ganaba donde el
    resumen alcanzaba y sacaba 0,00 donde la respuesta era un dato que el resumen no trae,
    como un número de cuenta sobre UNA sola unidad.

    Devuelve cadena vacía si la salida no tiene ids — un paso de lectura sin nada que leer
    tiene que fallar visible, no leer cualquier cosa.
    """
    try:
        cuerpo = json.loads(salida)
    except (ValueError, TypeError):
        return ""
    # EL ORDEN SE CONSERVA, y no es un detalle: los resultados de una búsqueda vienen
    # RANKEADOS, así que devolverlos al revés es leer primero el peor. La primera versión
    # de esto usaba una pila y los invertía — `memo-007` antes que `memo-003` — y con
    # `MAX_BATCH_READ` recortando, invertir no reordena: DESCARTA los mejores.
    vistos: list[str] = []

    def recorrer(nodo: Any) -> None:
        if isinstance(nodo, dict):
            uid = nodo.get("unit_id")
            if isinstance(uid, str) and uid not in vistos:
                vistos.append(uid)
            for v in nodo.values():
                recorrer(v)
        elif isinstance(nodo, list):
            for v in nodo:
                recorrer(v)

    recorrer(cuerpo)
    return ",".join(vistos[:MAX_BATCH_READ])


# LAS CUATRO, Y LA SEMANTICA ES LA QUE MAS FALTA (2026-08-30).
#
# Este prompt declaraba TRES de las cuatro herramientas de recuperacion disponibles, y la
# que faltaba era `semantic_search`. Medido sobre 138 celdas: `rewoo` llamo `search` 255
# veces y `keyword_search` 149 — y `semantic_search` **cero**, porque nunca se la
# ofrecieron.
#
# Y es justo la que su mecanismo mas necesita. `rewoo` planifica A CIEGAS: escribe el plan
# entero antes de ver un solo resultado, asi que **no puede corregir una consulta que no
# matcheo**. La busqueda lexica es la mas fragil ante el parafraseo —exige el termino
# exacto— y la semantica es la unica que tolera que la consulta planeada no use las
# palabras del documento.
#
#     Para un brazo que reacciona, que le falte una modalidad cuesta una vuelta mas.
#     Para uno que NO reacciona, cuesta la tarea entera.
#
# Se agrega en vez de sacar nada: antes de quitarle una herramienta a un patron hay que
# preguntarse si deberia usarla, y aca la respuesta era que le faltaba.
REWOO_TOOLS = (
    "- search(query, limit): fused ranking, returns unit_id + summary per hit\n"
    "- keyword_search(query, limit): exact-term ranking, returns unit_id + highlight\n"
    "- semantic_search(query, limit): meaning-based ranking, tolerates paraphrase — "
    "prefer it when the wording of the documents cannot be guessed\n"
    "- read(unit_ids): full text of up to {batch} comma-separated unit ids"
)


def rewoo(client: LLMClient, surface: ToolSurface, task: dict[str, Any]) -> Result:
    """Planifica TODAS las llamadas de antemano, las ejecuta sin el modelo, y responde una vez.

    QUE HACE, y el orden es el punto: (1) una llamada al modelo que produce un plan de
    hasta `MAX_PLAN_STEPS` pasos, (2) el CODIGO ejecuta esos pasos sin volver a consultar
    al modelo, (3) una llamada final que resuelve con la evidencia junta.

    LA CONSECUENCIA ESTRUCTURAL: **dos llamadas al modelo, pase lo que pase.** Por eso es
    el brazo mas barato del catalogo por lejos —1.050 tokens por celda contra 137.211 de
    `react`— y por eso gana 23 de 46 tareas bajo el criterio «maxima utilidad al menor
    costo»: donde todos empatan, gana el que cuesta menos.

    GUARDAS QUE LO GOBIERNAN:
      · `MAX_PLAN_STEPS = 8` pasos; `EVIDENCE_ITEM_CHARS = 32.000` por item;
        `SUBSTITUTION_CHARS = 800` al sustituir el resultado de un paso en el siguiente
      · **no puede reaccionar**: el plan se fija antes de ver un solo resultado. Si el paso
        uno devuelve algo inesperado, los pasos dos a ocho ya estaban escritos

    CUANDO ES EL CAMINO CORRECTO: cuando lo que hay que traer se puede enumerar ANTES de
    empezar — una lista de nombres dada en la pregunta, un conteo sobre un alcance
    declarado. La independencia entre pasos es su precondicion, no una preferencia.

    CUANDO NO: en cualquier cadena. Planificar de antemano un encadenamiento es planificar
    una busqueda cuyo termino todavia no se conoce.
    """
    usage = Usage()

    plan_prompt = (
        f"Task: {task['question']}\n\n"
        f"There are {len(surface.unit_ids())} document units. You will NOT see tool "
        f"results before answering, so plan ALL tool calls now.\n"
        f"Tools:\n{REWOO_TOOLS.format(batch=MAX_BATCH_READ)}\n\n"
        f"Return JSON only:\n"
        f'{{"steps": [{{"tool": "search", "args": {{"query": "..."}}, "out": "E1"}}, ...]}}\n'
        f"A later step may reference earlier evidence by writing #E1, #E2... inside an "
        f"argument string. In `unit_ids` the reference resolves to the unit ids that "
        f"step found, so `read(unit_ids=\"#E1\")` reads what the search returned. "
        f"At most {MAX_PLAN_STEPS} steps."
    )
    plan = client.complete(
        messages=[{"role": "user", "content": plan_prompt}], max_tokens=800
    )
    usage.merge(plan.usage)

    # A malformed plan is a real failure of this paradigm on this task: degrada a cero
    # pasos, no explota.
    declared = extract_json(plan.text, "steps", sink=surface)
    steps = declared[:MAX_PLAN_STEPS] if isinstance(declared, list) else []

    # La forma, no sólo el parseo: `steps` podia ser una lista de strings y `step.get`
    # levantaba AttributeError fuera de todo try.
    steps = well_formed(steps, "tool", sink=surface)

    evidence: dict[str, str] = {}
    for i, step in enumerate(steps, start=1):
        out_key = str(step.get("out") or f"E{i}")
        args = dict(step.get("args") or {})
        for k, v in args.items():
            if isinstance(v, str):
                # UN ARGUMENTO DE IDENTIFICADOR RECIBE IDS, NO TEXTO. Es el arreglo de
                # `RW-1`: la sustitución textual servía para una `query` y dejaba a `read`
                # con un blob JSON donde esperaba un id, así que este patrón llamaba a
                # `read` 130 veces y leía cero unidades. También se admite `#E1.ids`
                # explícito, que es lo que un plan bien escrito debería decir.
                for key, val in evidence.items():
                    v = v.replace(f"#{key}.ids", _ids_de(val))
                for key, val in evidence.items():
                    reemplazo = (_ids_de(val) if k in ARGS_DE_ID
                                 else val[:SUBSTITUTION_CHARS])
                    v = v.replace(f"#{key}", reemplazo)
                args[k] = v
        try:
            output = surface.dispatch(str(step.get("tool", "")), args)
        # Sólo `ToolFailure`, igual que el loop compartido. El catch ampliado a
        # `(ValueError, KeyError)` existia para tapar que `dispatch` levantaba
        # excepciones crudas; ahora valida y levanta `ToolFailure`, asi que taparlo aca
        # volveria a esconder un bug real del harness detras de una degradacion.
        except ToolFailure as failure:
            output = json.dumps({"error": str(failure)})
        evidence[out_key] = output[:EVIDENCE_ITEM_CHARS]

    evidence_block = "\n\n".join(f"#{k}:\n{v}" for k, v in evidence.items()) or "(none)"
    solve_prompt = (
        f"Task: {task['question']}\n\n"
        f"Evidence collected by your plan:\n{evidence_block}\n\n{answer_contract(surface)}"
    )
    final = client.complete(messages=[{"role": "user", "content": solve_prompt}])
    usage.merge(final.usage)

    return _finish(
        final.text, usage, surface,
        [{"role": "user", "content": solve_prompt}], 2,
    )


def gist_reader(client: LLMClient, surface: ToolSurface, task: dict[str, Any]) -> Result:
    """Un prompt sobre GISTS por unidad, y lecturas completas sólo donde el modelo las nombra.

    QUE HACE: sirve un resumen corto de cada unidad —todas— y deja que el modelo pida la
    lectura completa de las que le importan, en batch. Es una estrategia de dos
    granularidades: barato y ancho primero, caro y angosto despues.

    GUARDAS QUE LO GOBIERNAN:
      · `MAX_BATCH_READ` acota cuantas unidades entran en una lectura
      · el gist es una compresion con perdida: **lo que el resumen no menciona, el modelo
        no lo puede pedir**. Si la respuesta vive en un detalle que el gist descarto, el
        brazo no tiene forma de llegar

    CUANDO ES EL CAMINO CORRECTO: cuando la respuesta esta en pocas unidades pero **cuales**
    no se sabe de antemano, y el material no entra entero. Ve el alcance completo a costo
    de resumen y paga texto completo solo donde hace falta.

    CUANDO NO: cuando la respuesta depende de un detalle que un resumen borra —una fecha,
    un identificador, una diferencia menor entre dos registros que compiten.
    """
    usage = Usage()
    unit_ids = surface.unit_ids()

    # Deterministic, zero-LLM-cost gist table. Feasibility guarantees it fits.
    gists = "\n".join(f"[{u}] {_summarise(surface.read_one(u))}" for u in unit_ids)

    triage_prompt = (
        f"Task: {task['question']}\n\n"
        f"Below is a one-line gist of every one of the {len(unit_ids)} units.\n"
        f"If the gists alone answer the task, return JSON {{\"answer\": \"...\"}}.\n"
        f"Otherwise return JSON {{\"read\": [\"unit-id\", ...]}} naming ONLY the units "
        f"whose full text you need. JSON only.\n\n{gists}"
    )
    triage = client.complete(
        messages=[{"role": "user", "content": triage_prompt}], max_tokens=600
    )
    usage.merge(triage.usage)

    # `json.loads` puede devolver una lista y entonces `.get` explota fuera del try.
    decision = extract_json(triage.text, default={}, sink=surface)
    if not isinstance(decision, dict):
        decision = {}

    if isinstance(decision.get("answer"), str) and decision["answer"].strip():
        return _finish(
            f"ANSWER: {decision['answer'].strip()}", usage, surface,
            [{"role": "user", "content": triage_prompt}], 1,
        )

    wanted = [u for u in decision.get("read", []) if isinstance(u, str)]
    # Bounded selection, deterministically: fill until the allowance is spent.
    allowance = surface.budget_tokens
    selected: list[str] = []
    spent = 0
    for u in wanted:
        # `unit_tokens` y no `len(read_one(...)) // 4`: medir el largo de algo NO es
        # haberlo leido. `read_one` suma a `served_chars` y marca la unidad como leida
        # estructuralmente, asi que estimar el costo de una unidad la cobraba — y cada
        # unidad seleccionada terminaba contada TRES veces: gist, estimacion y lectura.
        cost = surface.unit_tokens(u) if u in unit_ids else 0
        if u in unit_ids and spent + cost <= allowance:
            selected.append(u)
            spent += cost
    truncated = len(wanted) - len(selected)

    texts: list[str] = []
    for i in range(0, len(selected), MAX_BATCH_READ):
        chunk = selected[i: i + MAX_BATCH_READ]
        try:
            texts.append(surface.dispatch("read", {"unit_ids": ", ".join(chunk)}))
        except ToolFailure as failure:
            texts.append(json.dumps({"error": str(failure)}))

    note = f"\n(NOTE: {truncated} requested units omitted for budget.)" if truncated else ""
    solve_prompt = (
        f"Task: {task['question']}\n\n"
        f"Gists of all units:\n{gists}\n\n"
        f"Full text of the units you selected:{note}\n" + "\n".join(texts) +
        f"\n\n{answer_contract(surface)}"
    )
    final = client.complete(messages=[{"role": "user", "content": solve_prompt}])
    usage.merge(final.usage)

    return _finish(
        final.text, usage, surface,
        [{"role": "user", "content": solve_prompt}], 2,
    )


# ---------------------------------------------------------------------------
# The three verified candidates (2026-08-26), one per remaining failure root.
# graph_traverse  <- HippoRAG 2405.14831 / GraphReader 2406.14550 / StepChain 2510.02827
# extract_compute <- LOTUS 2407.11418 / CodeAct 2402.01030 / DFA 2602.01355
# streaming_scan  <- Chain-of-Agents 2406.02818
# ---------------------------------------------------------------------------

# The graph index is MODEL OUTPUT (one extraction call per unit), so it lives under the
# client's own cache namespace rather than at a path hardcoded relative to this file.
# Two consequences, both intended: it follows MAPO_CACHE_DIR wherever that points, and an
# index extracted on one account is never served to a run on another.
# CUANTOS SALTOS RECORRE LA TRAVESIA. Vivia junto a las constantes del indice y al mover
# el indice a `app/ingest.py` se fue con ellas — el paradigma quedaba con un `NameError` en
# tiempo de ejecucion, no de import, asi que ningun test de importacion lo veia. Lo encontro
# el smoke de humo de los 13, que es exactamente para lo que existe.
WALK_DEPTH = guards.GRAPH_WALK_DEPTH
# `_entity_graph` VIVIA ACA y construia el indice adentro del request. Se movio entero a
# `app/ingest.py` por `G-4`, y no se dejo un envoltorio de compatibilidad a proposito: un
# envoltorio habria permitido que un paradigma nuevo lo llamara sin darse cuenta, que es
# exactamente el error que la mudanza corrige. Lo que queda del lado del paradigma es
# `require(...)`, que rechaza y explica.


def graph_traverse(
    client: LLMClient, surface: ToolSurface, task: dict[str, Any]
) -> Result:
    """Cadenas como caminatas de grafo: extrae entidades, camina, lee los aciertos, responde.

    QUE HACE: en vez de buscar por texto, arma un grafo de entidades desde la pregunta y
    camina `WALK_DEPTH` saltos, leyendo las unidades que el camino toca.

    GUARDAS QUE LO GOBIERNAN:
      · `WALK_DEPTH = 2` saltos; `MAX_BATCH_READ` en la lectura
      · **depende de que exista un grafo que caminar**. Si el corpus resuelve las entidades
        de antemano —una forma canonica por nombre, sin abreviaturas ni anafora— la parte
        dificil ya esta hecha y el patron no tiene nada que aportar

    ESTA EN STANDBY, no retirado, y la diferencia importa: fue **falsificado** por una
    prediccion registrada (`P10a`) con dos condiciones de revival escritas. La segunda de
    ellas —un corpus con variantes de superficie y anafora— ya se cumple desde `K-6`.

    CUANDO SERIA EL CAMINO CORRECTO: una cadena de referencias donde resolver **quien es
    quien** sea la dificultad, no encontrar el documento.
    """
    usage = Usage()
    # CONSUME, NO CONSTRUYE (G-4). El indice se arma en la etapa de ingesta, antes y
    # aparte: su costo se pagaba entero en la PRIMERA fila que lo necesitaba —una fila
    # arbitraria, la que el cross product puso primero— y su lectura del corpus entero
    # figuraba como lectura de esta pregunta. Si la ingesta no corrio, esto se declara
    # infactible en vez de construirla: un respaldo silencioso devolveria las dos cosas.
    from ..ingest import require
    graph = require(
        surface, client, surface.view.documents, surface.unit_ids(), "graph_traverse"
    ).entity_graph
    entity_units: dict[str, list[str]] = graph.get("entity_units", {})
    edges: dict[str, list[str]] = graph.get("edges", {})

    q_prompt = (
        f"Task: {task['question']}\n\n"
        "List the entities (names, ids, addresses, dates) this task is about.\n"
        'JSON only: {"entities": ["..."]}'
    )
    q = client.complete(
        messages=[{"role": "user", "content": q_prompt}], max_tokens=300
    )
    usage.merge(q.usage)
    entities = extract_json(q.text, "entities", sink=surface)
    if isinstance(entities, list):
        seeds = [str(e).strip().lower() for e in entities]
    else:
        seeds = []

    # Deterministic walk: BFS from the question's entities, units scored by how early
    # and how often the walk reaches them. Substring matching absorbs phrasing drift.
    known = list(entity_units)
    frontier = {k for s in seeds for k in known if s and (s in k or k in s)}
    scores: dict[str, float] = defaultdict(float)
    seen: set[str] = set()
    for depth in range(WALK_DEPTH + 1):
        weight = 1.0 / (1 + depth)
        next_frontier: set[str] = set()
        for ent in frontier:
            if ent in seen:
                continue
            seen.add(ent)
            for unit in entity_units.get(ent, []):
                scores[unit] += weight
            next_frontier.update(edges.get(ent, []))
        frontier = next_frontier - seen

    ranked = sorted(scores, key=lambda u: -scores[u])

    # LA CAMINATA NO ARRANCO: NO SE CONTESTA (GT-1, 2026-08-30)
    #
    # Si ningun termino de la pregunta matchea una entidad del grafo, `frontier` queda
    # vacia y con ella `scores` y `ranked`. Hasta hoy el codigo seguia igual: `selected`
    # vacio, cero lecturas, y la llamada de solve con `texts = []` — **el brazo contestaba
    # desde la nada**.
    #
    # MEDIDO SOBRE SUS 165 FILAS, y el histograma de llamadas tiene exactamente dos valores:
    #
    #     NO llama a ninguna herramienta    89 filas (54%)   u = 0,112
    #     lee al menos una unidad           76 filas         u = 0,525
    #
    # O sea que **la mitad de sus corridas midieron un indice inutilizable**, no el
    # paradigma. Y su veredicto `P10a` se calculo sobre esa poblacion.
    #
    # POR QUE `Infeasible` Y NO UNA RESPUESTA VACIA. Un grafo que no conecta con la pregunta
    # es un hecho COMPUTED sobre el material, y contestar igual es exactamente lo que fallar
    # cerrado prohibe. Marcarlo infactible tiene tres efectos, y los tres son correctos:
    #
    #   · **no se puntua** — una celda que no corrio no es una respuesta mala. Es la
    #     diferencia entre «no pudo» y «contesto mal», que este banco separa en todos lados
    #     menos aca
    #   · **no se gasta la llamada de solve** sobre evidencia que no existe
    #   · **queda el motivo en el registro**, asi que la fila dice por que
    #
    # La infactibilidad ES un resultado: es la misma decision que ya se tomo para
    # `extract_compute` y `streaming_scan` bajo presupuesto de produccion.
    if not ranked:
        raise Infeasible(
            f"la caminata no alcanzo ninguna unidad: de las {len(seeds)} entidades que la "
            f"pregunta nombra, ninguna matchea las {len(known)} del grafo. El mecanismo de "
            f"este brazo no puede arrancar sobre esta tarea"
        )

    allowance = surface.budget_tokens
    selected: list[str] = []
    spent = 0
    for u in ranked:
        # Estimar no es leer: `unit_tokens` mide sin dejar rastro de lectura.
        cost = surface.unit_tokens(u)
        if spent + cost > allowance:
            break
        selected.append(u)
        spent += cost

    texts = []
    for i in range(0, len(selected), MAX_BATCH_READ):
        chunk = selected[i: i + MAX_BATCH_READ]
        try:
            texts.append(surface.dispatch("read", {"unit_ids": ", ".join(chunk)}))
        except ToolFailure as failure:
            texts.append(json.dumps({"error": str(failure)}))

    solve = (
        f"Task: {task['question']}\n\n"
        f"Evidence reached by walking the corpus entity graph from the task's "
        f"entities:\n" + "\n".join(texts) + f"\n\n{answer_contract(surface)}"
    )
    final = client.complete(messages=[{"role": "user", "content": solve}])
    usage.merge(final.usage)
    return _finish(final.text, usage, surface, [{"role": "user", "content": solve}], 2)


def extract_compute(
    client: LLMClient, surface: ToolSurface, task: dict[str, Any]
) -> Result:
    """Mapea a filas estructuradas, agrega EN CODIGO, y redacta una vez.

    QUE HACE: por cada unidad, una extraccion a un esquema fijo; despues el codigo agrega
    —cuenta, suma, filtra— sin pedirle al modelo que haga aritmetica; despues una llamada
    que redacta.

    LA IDEA ES SACARLE AL MODELO LA PARTE QUE HACE MAL: contar. La agregacion es
    deterministica y auditable porque la hace el codigo.

    GUARDAS QUE LO GOBIERNAN:
      · una llamada por unidad, asi que el costo crece **lineal con el alcance** — y por
        eso la factibilidad lo poda en **66 de 78 tareas** bajo presupuesto de produccion
      · el esquema de extraccion es fijo: lo que no entra en el esquema se pierde

    SU INFACTIBILIDAD **ES** EL RESULTADO, no un hueco del registro: el patron es correcto
    y no entra en el presupuesto que produccion tiene. Eso se mide una vez y se declara.
    """
    usage = Usage()

    schema_prompt = (
        f"Task: {task['question']}\n\n"
        "Design the minimal extraction schema: which fields must be captured from each "
        "document unit to answer this by computation.\n"
        'JSON only: {"fields": ["..."]}'
    )
    schema = client.complete(
        messages=[{"role": "user", "content": schema_prompt}], max_tokens=300
    )
    usage.merge(schema.usage)
    declared = extract_json(schema.text, "fields", sink=surface)
    if isinstance(declared, list):
        fields = [str(f) for f in declared][:8] or ["value"]
    else:
        fields = ["value"]

    rows: list[dict[str, Any]] = []
    for unit_id in surface.unit_ids():
        prompt = (
            f"Task: {task['question']}\n"
            f"Extract every matching record from ONLY this unit as JSON rows with "
            f"fields {fields}. No prose.\n"
            f'JSON only: {{"rows": [...]}} — empty list if nothing matches.\n\n'
            f"[{unit_id}]\n{surface.read_one(unit_id)}"
        )
        completion = client.complete(
            messages=[{"role": "user", "content": prompt}], max_tokens=600
        )
        usage.merge(completion.usage)
        # `extract_json` YA devuelve {} ante cualquier malformacion — ese es su contrato.
        # El try que envolvia esto ademas tapaba el bucle: un TypeError del harness en
        # `rows.append` o en la asignacion caia en el mismo `continue` que un JSON roto
        # del modelo, y las dos cosas se leian igual en el registro. Son distintas: una es
        # un dato del experimento y la otra es un defecto.
        payload = extract_json(completion.text, default={}, sink=surface)
        emitted = payload.get("rows") if isinstance(payload, dict) else None
        for row in well_formed(emitted, sink=surface):
            row["_unit"] = unit_id
            rows.append(row)

    # The reduce, in code: exact dedupe over the declared fields, exact count.
    distinct: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = json.dumps(
            {f: str(row.get(f, "")).strip().lower() for f in fields}, sort_keys=True
        )
        distinct.setdefault(key, row)
    table = list(distinct.values())

    solve = (
        f"Task: {task['question']}\n\n"
        f"COMPUTED extraction table — {len(table)} distinct records (deduplicated in "
        f"code from {len(rows)} raw extractions over all {len(surface.unit_ids())} "
        f"units; the count {len(table)} is exact):\n"
        f"{json.dumps(table, ensure_ascii=False)}\n\n"
        f"Answer strictly from this table.\n\n{answer_contract(surface)}"
    )
    final = client.complete(messages=[{"role": "user", "content": solve}])
    usage.merge(final.usage)
    return _finish(
        final.text, usage, surface,
        [{"role": "user", "content": solve}], len(surface.unit_ids()) + 2,
    )


CHUNK_TOKENS = guards.SCAN_CHUNK_TOKENS
CARRY_MAX_CHARS = guards.SCAN_CARRY_CHARS
def streaming_scan(
    client: LLMClient, surface: ToolSurface, task: dict[str, Any]
) -> Result:
    """Una pasada secuencial con estado acarreado: el corpus se paga EXACTAMENTE una vez.

    QUE HACE: recorre las unidades en orden, en trozos de `CHUNK_TOKENS`, arrastrando un
    resumen de estado acotado a `CARRY_MAX_CHARS`. Nunca vuelve atras.

    LA PROPIEDAD QUE LO DEFINE: cada token de material entra al modelo **una sola vez**.
    Es el unico brazo del catalogo con esa garantia, y por eso es el contraejemplo del
    problema que §7.8 mide — el resto reenvia la conversacion en cada vuelta.

    GUARDAS QUE LO GOBIERNAN:
      · `CHUNK_TOKENS = 6.000` por trozo; `CARRY_MAX_CHARS = 6.000` de estado
      · **el acarreo es una compresion con perdida y sin vuelta atras**: lo que el estado
        no conserva al pasar de trozo, se perdio para siempre

    CUANDO SERIA EL CAMINO CORRECTO: alcances muy anchos donde la respuesta se puede
    construir incrementalmente — un conteo, un maximo, una acumulacion.

    CUANDO NO: cuando hace falta comparar dos unidades lejanas entre si. Podado por
    factibilidad en 66 de 78 tareas.
    """
    usage = Usage()

    chunks: list[list[str]] = [[]]
    spent = 0
    for unit_id in surface.unit_ids():
        # ACA SE JUGABA LA PROPIEDAD QUE DEFINE AL BRAZO. Armar los trozos con `read_one`
        # cobraba el corpus ENTERO una vez, y despues el prompt lo cobraba otra: el
        # docstring de arriba dice que cada token de material entra una sola vez y que es
        # el unico brazo del catalogo con esa garantia. La garantia se cumplia —el modelo
        # veia cada unidad una vez— y `served_chars` decia lo contrario, que es la unica
        # metrica donde se habria visto.
        cost = surface.unit_tokens(unit_id)
        if spent + cost > CHUNK_TOKENS and chunks[-1]:
            chunks.append([])
            spent = 0
        chunks[-1].append(unit_id)
        spent += cost

    carry = '{"findings": [], "open_questions": []}'
    for i, chunk in enumerate(chunks):
        block = "\n\n".join(f"[{u}]\n{surface.read_one(u)}" for u in chunk)
        prompt = (
            f"Task: {task['question']}\n\n"
            f"You are scanning the corpus in one pass, chunk {i + 1}/{len(chunks)}.\n"
            f"Registry so far (JSON):\n{carry}\n\n"
            f"New chunk:\n{block}\n\n"
            "Return the UPDATED registry as JSON with the same shape. Carry every "
            "prior finding forward unless this chunk disproves it; add what this "
            "chunk contributes. JSON only."
        )
        completion = client.complete(
            messages=[{"role": "user", "content": prompt}], max_tokens=1_000
        )
        usage.merge(completion.usage)
        text = completion.text.strip()
        try:
            updated = text[text.index("{"): text.rindex("}") + 1][:CARRY_MAX_CHARS]
            # Se valida el RECORTE, no el objeto entero: el corte a CARRY_MAX_CHARS
            # puede partir el JSON, y lo que se arrastra es el recorte.
            json.loads(updated)
            carry = updated
        except (ValueError, TypeError):
            pass  # a malformed update must not destroy the registry

    solve = (
        f"Task: {task['question']}\n\n"
        f"Final registry after scanning all {len(surface.unit_ids())} units exactly "
        f"once:\n{carry}\n\n{answer_contract(surface)}"
    )
    final = client.complete(messages=[{"role": "user", "content": solve}])
    usage.merge(final.usage)
    return _finish(
        final.text, usage, surface,
        [{"role": "user", "content": solve}], len(chunks) + 1,
    )


# ---------------------------------------------------------------------------
# pointer_chase (2026-08-26), designed against this harness's own falsifications.
# A coupled chain in this corpus is a sequence of pointers visible in the TEXT of
# the anchor unit, revealed one unit at a time. graph_traverse (global entity
# adjacency) was falsified on exactly those cells; plan/dag decomposition and the
# react tool-loop carry their own measured failure roots. What remains: anchor by
# retrieval, then a loop that lives in CODE, where the LLM is a sensor over ONE
# unit per call — no history resent, no tool choice, no self-assessed budget
# (BAGEN 2606.00198: agents are budget-optimists; the code stops, not the model).
# Structure trace on demand from the seed, never a corpus index (DocTrace 2606.10921).
# ---------------------------------------------------------------------------

LEDGER_FACT_CHARS = guards.CHASE_LEDGER_FACT_CHARS
# CUANTOS SALTOS PIDE LA PREGUNTA, si lo dice. Es una senal del ENTORNO —contable,
# determinista, sin modelo en el medio— del mismo tipo que `measure_continuation` y
# `measure_question_literal`: se lee del texto de la pregunta, nunca se le pregunta a nadie.
#
# POR QUE EXISTE (2026-08-30). `pointer_chase` declaraba en su docstring que «el modelo nunca
# decide cuando parar» y el codigo lo desmentia: `if upper == "DONE": break`. En C3 —una
# cadena de N escalones declarados— eso es exactamente el modo de falla medido: 5 de 15
# respuestas de `react` y 4 de 15 de `reflection` cortaron **un escalon antes** y devolvieron
# la cuenta de un intermedio, que esta a la vista y es plausible. Un `DONE` a mitad de camino
# no es una observacion del sensor: es una decision de flujo de control, y el invariante del
# producto la prohibe.
SALTOS_DECLARADOS = re.compile(r"\b(?:upward|upwards|up)\s+(\d+)\s+step", re.IGNORECASE)


SUJETO_DECLARADO = re.compile(
    r"\bstarting from\s+([A-Z][\w'.-]*(?:\s+[A-Z][\w'.-]*)*)", re.IGNORECASE)


def sujeto_declarado(pregunta: str) -> str | None:
    """El sujeto de arranque que la pregunta nombra, o `None`.

    Forma cerrada y verificable, hermana de `saltos_declarados`: sale del texto de la
    pregunta, no de una llamada al modelo.
    """
    m = SUJETO_DECLARADO.search(pregunta or "")
    return m.group(1).strip(" ,.") if m else None


def saltos_declarados(pregunta: str) -> int | None:
    """Los saltos que la pregunta EXIGE, o `None` si no declara ninguno.

    `None` y no `0`: no declarar un largo es distinto de declarar cero, y el codigo trata
    los dos casos distinto — sin declaracion, el modelo sigue decidiendo cuando parar, que
    es lo correcto cuando el largo genuinamente no se conoce (`C5_unknown_horizon`).
    """
    m = SALTOS_DECLARADOS.search(pregunta or "")
    return int(m.group(1)) if m else None


def _primer_hit_que_nombra(
    surface: ToolSurface, hits: list[dict[str, Any]], buscado: str, visitadas: list[str],
) -> str | None:
    """El primer hit NO visitado cuyo texto realmente menciona lo que se busca.

    POR QUE HACE FALTA. `keyword_search` ordena por relevancia lexica, y sobre un corpus de
    memos con la misma plantilla la relevancia de `M. Arrieta` la reparten muchos memos que
    NO la nombran. Tomar el hit 1 sin mirar convierte una cadena en un paseo.

    LA PRUEBA ES POR APELLIDO, no por el nombre completo, y esa es la unica parte fina: el
    corpus escribe el destino del salto abreviado —`A. Vallejos` apunta a `Agustina
    Vallejos`— asi que exigir la cadena entera fallaria SIEMPRE. El apellido es el token
    que sobrevive a la abreviatura, y la inicial —cuando esta— desempata.

    NO LEE: usa `surface.unit_mentions` / `unit_matches`, que son PREDICADOS. El texto no
    entra al contexto de nadie y el chequeo no cuesta un token ni deja rastro de lectura —
    es la misma pregunta que el indice lexico ya contesta para rankear.
    """
    partes = [p for p in buscado.replace(".", " ").split() if p]
    if not partes:
        return None
    apellido = partes[-1].lower()
    inicial = partes[0][0].lower() if len(partes) > 1 else None
    if inicial is None:
        rx_ancla = rx_menciona = re.compile(rf"\b{re.escape(apellido)}\b")
    else:
        # DOS PRUEBAS, Y LA DIFERENCIA ENTRE ELLAS ES EL DESAMBIGUADOR. La unidad que
        # ANCLA a una persona la escribe con nombre completo —«Agustina Vallejos serves as
        # auditor»—; la que solo la REFERENCIA la abrevia —«reports to A. Vallejos»—. Las
        # dos mencionan el apellido, y sin separarlas la caminata salta a la unidad que la
        # nombra de paso en vez de a la suya: en h1, persiguiendo `M. Arrieta`, los tres
        # primeros hits lexicos son memo-001 (que la referencia), memo-004 y memo-000 (la
        # suya). Preferir la forma completa es lo que las ordena, y es determinista.
        rx_ancla = re.compile(rf"\b{re.escape(inicial)}[a-z]{{2,}}\s+{re.escape(apellido)}\b")
        rx_menciona = re.compile(
            rf"\b{re.escape(inicial)}\w*\.?\s+{re.escape(apellido)}\b")
    anclas, menciones = [], []
    for h in hits:
        uid = h["unit_id"]
        if uid in visitadas:
            continue
        if not surface.unit_mentions(uid, apellido):
            continue
        if surface.unit_matches(uid, rx_ancla):
            anclas.append(uid)
        elif surface.unit_matches(uid, rx_menciona):
            menciones.append(uid)
    # SE PREFIERE UNA CLASE ENTERA SOBRE LA OTRA, no un puntaje mezclado: la distincion
    # ancla-o-referencia es categorica y promediarla la borraria.
    #
    # Y DENTRO DE LA CLASE MANDA LA POSICION, no el ranking lexico. Medido en h3: para
    # `A. Vallejos` los dos primeros candidatos —`memo-045` y `memo-056`— la nombran con
    # nombre completo, asi que la prueba de forma empata y el ranking pone primero al
    # equivocado. `memo-045` la menciona en un parrafo tardio («was formerly auditor…; the
    # position was vacated», un senuelo del corpus) y `memo-056` abre con ella. Un salto a
    # `memo-045` no rompe la cadena de golpe: la corre UN escalon, y el brazo termina
    # devolviendo la cuenta del anteultimo — el modo de falla `intermedia`, el dominante.
    clase = anclas or menciones
    if not clase:
        return None
    return min(clase, key=lambda uid: surface.unit_offset(uid, rx_ancla if anclas
                                                          else rx_menciona))


def pointer_chase(
    client: LLMClient, surface: ToolSurface, task: dict[str, Any]
) -> Result:
    """Sigue la cadena de a una unidad; el bucle lo lleva el CODIGO y el LLM es sensor.

    QUE HACE: el codigo mantiene el estado de la caminata —donde esta, que ya visito, que
    hechos junto en el ledger— y en cada paso le pregunta al modelo una sola cosa: cual es
    el proximo puntero. El modelo nunca decide cuando parar.

    ES EL CASO MAS PURO DEL INVARIANTE DEL PRODUCTO: el LLM emite una proposicion, el
    codigo maneja el flujo de control.

    GUARDAS QUE LO GOBIERNAN:
      · `LEDGER_FACT_CHARS = 400` por hecho acarreado; el presupuesto corta la caminata
      · el modelo puede devolver `DONE`, `DEAD_END` o `NONE`, y el codigo los distingue —
        no llegar y decidir que no hay camino son cosas distintas
      · **el largo declarado manda sobre el `DONE`** (2026-08-30): si la pregunta dice
        «upward N step(s)», el codigo exige N saltos antes de aceptar que la caminata
        termino, y el `solve` recibe cual unidad es el TERMINO

    EL DOCSTRING DECIA ESTO Y EL CODIGO NO LO HACIA, y el arreglo del 2026-08-30 cierra esa
    brecha. Decia «el modelo nunca decide cuando parar» y abajo tenia `if upper == "DONE":
    break` — o sea que el sensor cortaba el bucle. En C3, donde el largo de la cadena esta
    ESCRITO en la pregunta, ese `DONE` prematuro es el modo de falla dominante medido: los
    brazos cortan un escalon antes y devuelven la cuenta de un intermedio, que esta a la
    vista y es indistinguible de la correcta. Dos correcciones, las dos de flujo de control
    y ninguna de fraseo:

      1. mientras falten saltos declarados, `DONE` se ignora y la caminata sigue
      2. el `solve` recibe del CODIGO cual es la unidad terminal — el ledger trae N+1
         hechos del mismo tipo y elegir entre ellos era la decision que el bucle acababa
         de sacarle al sensor

    ESTABA RETIRADO por `P14a`: **nunca toco una unidad relevante** en el corpus donde se lo
    midio. Y sus frenos SI se confirmaron, asi que el mecanismo sobrevivio a la muerte del
    patron — lo que fallo fue la caminata, no la disciplina de control. Este arreglo ataca
    la caminata, que es lo que P14a habia falsificado.
    """
    usage = Usage()
    unit_ids = surface.unit_ids()
    # EL PROMEDIO NO SE PAGA LEYENDO. Esto llamaba a `read_one` sobre CADA unidad del
    # alcance para quedarse con un largo promedio, y `read_one` deja rastro: medido,
    # `pointer_chase` daba `units_read_structural == n_units` en **170 de 170 celdas**.
    #
    # O sea que el brazo que se define por seguir UN puntero desde UN ancla figuraba
    # abriendo el alcance completo, en la unica metrica que mostraria si lo hace. El
    # veredicto de P14a —que nunca toco una unidad relevante— sobrevive porque se calculo
    # sobre `units_read`, las lecturas del MODELO; pero `relevant_units_read_any`, que
    # incluye las estructurales, decia exactamente lo contrario. Dos metricas con lecturas
    # opuestas del mismo brazo, y la diferencia era un calculo de promedio.
    mean_unit = max(
        1, sum(surface.unit_tokens(u) for u in unit_ids) // max(1, len(unit_ids))
    )
    # Same arithmetic as app.feasibility: the cap is a guarantee, shared by both
    # layers, tested against the BUDGET — the chase holds no conversation (nothing is
    # resent; the solve reads a small ledger), so the conversation share is not owed.
    hop_cap = min(guards.CHASE_MAX_HOPS,
                  max(guards.CHASE_MIN_HOPS, surface.budget_tokens // mean_unit))

    # EL ANCLA SE BUSCA POR EL SUJETO, NO POR LA PREGUNTA ENTERA. Medido en C3: buscando con
    # la pregunta completa —«Starting from Renata Novoa, follow the reporting line upward 3
    # step(s). Report the settlement account on file…»— el ranking se lo llevan los memos que
    # hablan de cuentas de liquidacion, que son los SESENTA, y el ancla salio mal en 3 de 3
    # (`memo-054` en vez de `memo-058`). La pregunta trae la instruccion Y el sujeto, y la
    # instruccion es ruido lexico compartido por todo el corpus.
    #
    # El sujeto se saca del texto de la pregunta con una forma cerrada, sin modelo: es una
    # senal del entorno, igual que `saltos_declarados`.
    #
    # Y QUE INDICE LA SIRVE NO LO DECIDE ESTE BRAZO: lo decide `features.indice_para`, que
    # es una regla de creencias sobre la CLASE de la consulta. Para una entidad nombrada va
    # el lexico y no la hibrida, porque un vector denso codifica *de que habla* un texto y
    # sesenta memos con la misma plantilla hablan de lo mismo — el nombre propio es
    # justamente la parte que no es semantica. Medido: la hibrida trae la unidad equivocada
    # para `Ramiro Herrera` y deja a `M. Arrieta` fuera del top-5; el lexico las pone
    # primera y tercera.
    sujeto = sujeto_declarado(task["question"])
    consulta_ancla = sujeto or task["question"]
    herramienta_ancla = ("keyword_search"
                         if indice_para(consulta_ancla) == "lexical" else "search")
    hits: list[dict[str, Any]] = json.loads(
        surface.dispatch(herramienta_ancla, {"query": consulta_ancla, "limit": guards.CHASE_HITS})
    ).get("results", [])

    ledger: list[str] = []
    visited: list[str] = []
    stalls = 0
    pointer_hallucinations = 0
    outcome = "no_anchor"
    iterations = 0
    saltos = saltos_declarados(task["question"])
    done_prematuros = 0
    # QUE BUSCO EN CADA SALTO, Y QUE LE VOLVIO. Sin esto una caminata que se frena es
    # indiagnosticable desde la fila: no se distingue «el modelo pidio la cosa equivocada»
    # de «la pidio bien y el indice no la trajo» de «la trajo y la guarda la rechazo», y las
    # tres piden arreglos distintos. Es la misma leccion que `FEATURE_SENSOR`.
    consultas: list[dict[str, Any]] = []
    ancla_determinista = False
    # EL TOPE NO PUEDE SER MENOR QUE LO QUE LA PREGUNTA EXIGE. `hop_cap` sale del
    # presupuesto y de una constante; si la pregunta pide 3 saltos y el presupuesto da 2, la
    # caminata se corta por una razon que no tiene nada que ver con la cadena y el resultado
    # se lee como «no la encontro». Se levanta el piso al largo declarado, +1 por el ancla.
    if saltos is not None:
        hop_cap = max(hop_cap, saltos + 1)

    if hits:
        # `search` DEVUELVE `summary` Y `keyword_search` DEVUELVE `highlight`, y como ahora
        # la regla de creencias elige la herramienta segun la clase de la consulta, el menu
        # tiene que servir a las dos. Cablear `summary` hacia que el brazo explotara con
        # `KeyError` en cuanto la consulta fuera un nombre — que es justo el caso que el
        # arreglo vino a habilitar.
        # EL ANCLA ES EL SALTO CERO, Y SE RESUELVE COMO CUALQUIER OTRO SALTO.
        #
        # Era una llamada al modelo —«¿cuál de estos hits es el ancla?»— y ahí quedaba la
        # ultima decision de flujo en manos del sensor. Medido en h3: con la MISMA huella y
        # los MISMOS hits, la reptica 0 eligio `memo-058` (correcta, y la cadena salio
        # entera: 058→056→052→050) y las repticas 1 y 2 eligieron `memo-054`, que arranca
        # otra cadena. Utilidad 1,000 contra 0,000 por una eleccion que el codigo podia
        # hacer solo — y que ademas cuesta una llamada.
        #
        # Cuando la pregunta DECLARA el sujeto, resolverlo es exactamente el mismo problema
        # que resolver `A. Vallejos` en el salto dos: misma funcion, misma guarda de
        # contencion, mismo desempate por posicion. Que el ancla usara otro mecanismo que
        # los demas saltos era la incoherencia de fondo.
        #
        # Sin sujeto declarado el modelo sigue eligiendo, y esta bien: ahi no hay nada
        # que el codigo pueda derivar.
        deterministico = (
            _primer_hit_que_nombra(surface, hits, sujeto, []) if sujeto else None
        )
        if deterministico is not None:
            current = deterministico
            ancla_determinista = True
        else:
            menu = "\n".join(
                f"[{h['unit_id']}] {h.get('summary') or h.get('highlight') or ''}"
                for h in hits)
            anchor_prompt = (
                f"Task: {task['question']}\n\n"
                f"Search hits:\n{menu}\n\n"
                "Which ONE unit is the anchor — where this task's subject is most likely "
                'stated? JSON only: {"start": "<unit-id>"}'
            )
            pick = client.complete(
                messages=[{"role": "user", "content": anchor_prompt}], max_tokens=100
            )
            usage.merge(pick.usage)
            iterations += 1
            picked = extract_json(pick.text, "start", sink=surface)
            start = str(picked).strip() if picked is not None else ""
            # An anchor outside the offered hits is a proposition the code does not
            # accept: fall back to the retriever's top hit, deterministically.
            current = (start if start in {h["unit_id"] for h in hits}
                       else hits[0]["unit_id"])
            ancla_determinista = False
        outcome = "hop_cap"

        for _ in range(hop_cap):
            try:
                text = surface.dispatch("read", {"unit_ids": current})
            except ToolFailure:
                outcome = "read_failed"
                break
            visited.append(current)
            facts = "\n".join(f"- {f}" for f in ledger) or "(none yet)"
            sense_prompt = (
                f"Task: {task['question']}\n\n"
                f"Facts gathered so far:\n{facts}\n\n"
                f"Current unit (the ONLY text you can see):\n{text}\n\n"
                "Report (1) the fact this unit contributes to the task, if any, and "
                "(2) where the trail points next: a unit id this text references, or "
                "SEARCH:<short query> for the thing it names, or DONE if the facts "
                "now answer the task, or DEAD_END if this unit neither helps nor "
                'points anywhere.\n'
                'JSON only: {"fact": "...", "next": "<unit-id or SEARCH:... or DONE '
                'or DEAD_END>"}'
            )
            step = client.complete(
                messages=[{"role": "user", "content": sense_prompt}], max_tokens=300
            )
            usage.merge(step.usage)
            iterations += 1
            fact, nxt = "", ""
            try:
                raw = step.text.strip()
                payload = extract_json(raw, default={}, sink=surface)
                fact = str(payload.get("fact") or "").strip()
                nxt = str(payload.get("next") or "").strip()
            except (ValueError, TypeError):
                pass
            if fact and fact.upper() not in ("NONE", "N/A"):
                ledger.append(f"[{current}] {fact[:LEDGER_FACT_CHARS]}")

            upper = nxt.upper()
            # EL `DONE` PREMATURO SE RECHAZA, y esto es lo que hace cierto el docstring.
            # `saltos` viene de la PREGUNTA, no del modelo: mientras la caminata no haya
            # dado los que se le exigen, «ya esta» no es una observacion admisible sino una
            # decision de flujo, y el codigo la ignora y sigue. Se cuenta, porque un brazo
            # que quiere parar diez veces antes de tiempo esta diciendo algo.
            #
            # Y si no hay puntero, no se puede seguir aunque falten saltos: eso es una
            # caminata rota y se marca distinto de una completa. Confundirlas taparia
            # justo el caso que el arreglo existe para hacer visible.
            if upper == "DONE" and saltos is not None and len(visited) - 1 < saltos:
                done_prematuros += 1
                nxt, upper = "", ""
            if not nxt or upper == "DONE":
                if upper == "DONE":
                    outcome = "done"
                elif saltos is not None and len(visited) - 1 < saltos:
                    outcome = "sin_puntero_faltando_saltos"
                else:
                    outcome = "no_pointer"
                break
            if upper == "DEAD_END":
                outcome = "dead_end"
                break
            if upper.startswith("SEARCH:"):
                crudo = nxt[7:].strip()
                # LA SALIDA DEL SENSOR SE TIPA ANTES DE USARSE. El modelo escribe
                # `M. Arrieta settlement account`, y esa cola arrastra a `query_kind` a
                # llamarla prosa — con lo cual la consulta que ERA un nombre se va a la
                # hibrida, justo donde esta medida como peor. Se persigue la ENTIDAD.
                buscado = entidad_en(crudo) or crudo
                # EL LIMITE SUBE DE 3 A 8, y sube PORQUE ahora hay guarda. Con `[0]` a
                # ciegas, un limite ancho era peor: mas candidatos equivocados a los que
                # saltar. Con la verificacion de contencion, ancho es estrictamente mejor —
                # el codigo descarta lo que no nombra a quien perseguimos. Medido sobre los
                # nueve eslabones de C3: con 8 estan los nueve, y el peor —`S. Quiroga`—
                # aparece en el puesto 7.
                found = json.loads(
                    surface.dispatch(
                        ("keyword_search" if indice_para(buscado) == "lexical" else "search"),
                        {"query": buscado, "limit": guards.CHASE_HITS}
                    )
                ).get("results", [])
                # UN SALTO A UNA UNIDAD QUE NO NOMBRA A QUIEN PERSEGUIMOS NO ES UN SALTO.
                # Antes se tomaba el primer hit no visitado sin mirar nada mas, y en C3 eso
                # basto para descarrilar las tres cadenas: `M. Arrieta` sobre 60 memos que
                # comparten formato hace que BM25 devuelva vecinos plausibles, y el primero
                # no es el que la nombra. El brazo caminaba, contaba saltos, y llegaba a
                # cualquier lado con el contador en verde — que es peor que no caminar.
                #
                # La guarda es de CONTENCION y la resuelve el codigo: el apellido del
                # nombre buscado tiene que aparecer en la unidad. Es la misma prueba que
                # usa el verificador del corpus, y no cuesta una llamada.
                consultas.append({"crudo": crudo, "busco": buscado,
                                  "indice": indice_para(buscado),
                                  "hits": [h["unit_id"] for h in found]})
                candidate = _primer_hit_que_nombra(surface, found, buscado, visited)
                if candidate is None:
                    stalls += 1
                    outcome = "stall"
                    break
                current = candidate
                continue
            candidate = nxt.strip("[]")
            if candidate not in unit_ids:
                # A pointer to a unit that does not exist. One deterministic recovery:
                # treat the string as a query; a second miss is a broken trail.
                pointer_hallucinations += 1
                found = json.loads(
                    surface.dispatch("keyword_search", {"query": candidate, "limit": 3})
                ).get("results", [])
                recovered = next(
                    (h["unit_id"] for h in found if h["unit_id"] not in visited), None
                )
                if recovered is None:
                    outcome = "hallucinated_pointer"
                    break
                current = recovered
                continue
            if candidate in visited:
                # Deterministic decoding: asking again would point here again.
                outcome = "revisit"
                break
            current = candidate

    facts = "\n".join(f"- {f}" for f in ledger) or "(none)"
    # DE CUAL UNIDAD SALE LA RESPUESTA LO DECIDE EL CODIGO, no el modelo. En una cadena de N
    # escalones el ledger trae N+1 hechos y **cada uno es plausible**: en C3 cada unidad del
    # camino lleva su propia cuenta de liquidacion, pegada al nombre que la ancla. Pasarle
    # los N+1 sin decir cual es el termino le devuelve al sensor justo la decision que el
    # bucle acaba de sacarle — y el modo de falla medido es precisamente ese: contestar la
    # cuenta de un intermedio.
    #
    # Solo se afirma cuando la caminata LLEGO. Si dio menos saltos de los exigidos, la
    # ultima unidad visitada NO es el termino, y decir que si lo es seria fabricar la
    # premisa. En ese caso se dice cuantos faltaron, que es lo que habilita la abstencion.
    if saltos is not None and visited:
        completa = len(visited) - 1 >= saltos
        if completa:
            terminal = visited[saltos]
            gobierno = (
                f"The question asks for exactly {saltos} step(s) up the chain. The walk "
                f"was driven by code, one step at a time, and the unit reached after "
                f"{saltos} step(s) is [{terminal}]. **The answer is the value asked for as "
                f"stated in [{terminal}]** — the other units on the trail carry values of "
                f"the same shape for other people, and none of those is the answer."
            )
        else:
            gobierno = (
                f"The question asks for {saltos} step(s) up the chain, and the walk "
                f"completed only {len(visited) - 1} before the trail broke ({outcome}). "
                f"The final unit was never reached, so its value is NOT among these facts. "
                f"Say the answer cannot be determined."
            )
    else:
        gobierno = ""
    solve = (
        f"Task: {task['question']}\n\n"
        f"Facts gathered by following the document trail "
        f"({' -> '.join(visited) or 'no units reached'}; chase ended: {outcome}):\n"
        f"{facts}\n\n"
        + (gobierno + "\n\n" if gobierno else "")
        + f"Answer strictly from these facts. If they do not contain the answer, say "
        f"so.\n\n{answer_contract(surface)}"
    )
    final = client.complete(messages=[{"role": "user", "content": solve}])
    usage.merge(final.usage)

    result = _finish(
        final.text, usage, surface,
        [{"role": "user", "content": solve}], iterations + 1,
    )
    result.tool_usage["chase"] = {
        "hop_cap": hop_cap,
        "hops": len(visited),
        "path": visited,
        "outcome": outcome,
        "stalls": stalls,
        "pointer_hallucinations": pointer_hallucinations,
        "ledger_facts": len(ledger),
        # LOS TRES CAMPOS DEL ARREGLO, y estan en la fila porque sin ellos el efecto no se
        # puede atribuir: si sube la utilidad hay que poder decir si fue porque la caminata
        # llego mas lejos o porque el `solve` dejo de elegir mal entre los intermedios.
        "saltos_exigidos": saltos,
        "done_prematuros": done_prematuros,
        "consultas": consultas,
        "ancla_determinista": ancla_determinista,
        "cadena_completa": (None if saltos is None
                            else bool(visited) and len(visited) - 1 >= saltos),
    }
    return result
