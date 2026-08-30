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
from collections import defaultdict
from typing import Any

from .parsing import extract_json, well_formed
from .. import guards
from ..llm import LLMClient, Usage
from ..tools import MAX_BATCH_READ, ToolFailure, ToolSurface, _summarise
from . import ANSWER_CONTRACT, answer_contract, Result, _finish

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

    ESTA RETIRADO por `P14a`: **nunca toco una unidad relevante** en el corpus donde se lo
    midio. Y sus frenos SI se confirmaron, asi que el mecanismo sobrevive a la muerte del
    patron — lo que fallo fue la caminata, no la disciplina de control.
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

    hits: list[dict[str, Any]] = json.loads(
        surface.dispatch("search", {"query": task["question"], "limit": 5})
    ).get("results", [])

    ledger: list[str] = []
    visited: list[str] = []
    stalls = 0
    pointer_hallucinations = 0
    outcome = "no_anchor"
    iterations = 0

    if hits:
        menu = "\n".join(f"[{h['unit_id']}] {h['summary']}" for h in hits)
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
        if picked is not None:
            start = str(picked).strip()
        else:
            start = ""
        # An anchor outside the offered hits is a proposition the code does not
        # accept: fall back to the retriever's top hit, deterministically.
        current = start if start in {h["unit_id"] for h in hits} else hits[0]["unit_id"]
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
            if not nxt or upper == "DONE":
                outcome = "done" if upper == "DONE" else "no_pointer"
                break
            if upper == "DEAD_END":
                outcome = "dead_end"
                break
            if upper.startswith("SEARCH:"):
                found = json.loads(
                    surface.dispatch(
                        "keyword_search", {"query": nxt[7:].strip(), "limit": 3}
                    )
                ).get("results", [])
                candidate = next(
                    (h["unit_id"] for h in found if h["unit_id"] not in visited), None
                )
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
    solve = (
        f"Task: {task['question']}\n\n"
        f"Facts gathered by following the document trail "
        f"({' -> '.join(visited) or 'no units reached'}; chase ended: {outcome}):\n"
        f"{facts}\n\n"
        f"Answer strictly from these facts. If they do not contain the answer, say "
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
    }
    return result
