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

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .parsing import extract_json, well_formed
from ..fsio import write_atomic
from ..llm import LLMClient, Usage
from ..tools import MAX_BATCH_READ, ToolFailure, ToolSurface, _summarise
from . import ANSWER_CONTRACT, Result, _finish

# Evidence caps. Substituting a full 8k-token unit into a search query would be
# nonsense; and the solver prompt must stay bounded by construction, not by hope.
SUBSTITUTION_CHARS = 800
EVIDENCE_ITEM_CHARS = 32_000
MAX_PLAN_STEPS = 8

REWOO_TOOLS = (
    "- search(query, limit): fused ranking, returns unit_id + summary per hit\n"
    "- keyword_search(query, limit): exact-term ranking, returns unit_id + highlight\n"
    "- read(unit_ids): full text of up to {batch} comma-separated unit ids"
)


def rewoo(client: LLMClient, surface: ToolSurface, task: dict[str, Any]) -> Result:
    """Plan every tool call up front, execute without the LLM, solve once."""
    usage = Usage()

    plan_prompt = (
        f"Task: {task['question']}\n\n"
        f"There are {len(surface.unit_ids())} document units. You will NOT see tool "
        f"results before answering, so plan ALL tool calls now.\n"
        f"Tools:\n{REWOO_TOOLS.format(batch=MAX_BATCH_READ)}\n\n"
        f"Return JSON only:\n"
        f'{{"steps": [{{"tool": "search", "args": {{"query": "..."}}, "out": "E1"}}, ...]}}\n'
        f"A later step may reference earlier evidence by writing #E1, #E2... inside an "
        f"argument string. At most {MAX_PLAN_STEPS} steps."
    )
    plan = client.complete(
        messages=[{"role": "user", "content": plan_prompt}], max_tokens=800
    )
    usage.merge(plan.usage)

    # A malformed plan is a real failure of this paradigm on this task: degrada a cero
    # pasos, no explota.
    declared = extract_json(plan.text, "steps")
    steps = declared[:MAX_PLAN_STEPS] if isinstance(declared, list) else []

    # La forma, no sólo el parseo: `steps` podia ser una lista de strings y `step.get`
    # levantaba AttributeError fuera de todo try.
    steps = well_formed(steps, "tool")

    evidence: dict[str, str] = {}
    for i, step in enumerate(steps, start=1):
        out_key = str(step.get("out") or f"E{i}")
        args = dict(step.get("args") or {})
        for k, v in args.items():
            if isinstance(v, str):
                for key, val in evidence.items():
                    v = v.replace(f"#{key}", val[:SUBSTITUTION_CHARS])
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
        f"Evidence collected by your plan:\n{evidence_block}\n\n{ANSWER_CONTRACT}"
    )
    final = client.complete(messages=[{"role": "user", "content": solve_prompt}])
    usage.merge(final.usage)

    return _finish(
        final.text, usage, surface,
        [{"role": "user", "content": solve_prompt}], 2,
    )


def gist_reader(client: LLMClient, surface: ToolSurface, task: dict[str, Any]) -> Result:
    """One prompt over per-unit gists; targeted batched full reads only where named."""
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
    decision = extract_json(triage.text, default={})
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
        cost = len(surface.read_one(u)) // 4 if u in unit_ids else 0
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
        f"\n\n{ANSWER_CONTRACT}"
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
GRAPH_CACHE_SUBDIR = "graph"
GRAPH_INDEX_MAX_TOKENS = 500
WALK_DEPTH = 2


def _corpus_digest(surface: ToolSurface, fingerprint: str = "") -> str:
    """Identity of the index: the corpus it describes AND the decode that produced it.

    The corpus alone was not enough. The index is extracted by the model, so an index
    built by one model was being served to a run of another -- a silent cross-model
    contamination in exactly the arm that depends on the index being faithful.
    """
    key = json.dumps(
        [fingerprint, sorted((u, len(surface.read_one(u))) for u in surface.unit_ids())]
    ).encode()
    return hashlib.sha256(key).hexdigest()[:16]


def _entity_graph(
    client: LLMClient, surface: ToolSurface, usage: Usage
) -> dict[str, Any]:
    """Entity graph over the corpus: built once, memoised on disk per world.

    The index is the amortised half of the pattern: one short extraction call per unit,
    paid by the FIRST task that needs it (recorded in that row's usage, honestly) and
    free for every task after — plus the content-addressed LLM cache makes replicate
    runs cheap even when this file is deleted.
    """
    cache_dir = client.cache_root / GRAPH_CACHE_SUBDIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{_corpus_digest(surface, client.fingerprint)}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # A truncated index (crash or write race) is rebuilt, not served forever.
            path.unlink(missing_ok=True)

    entity_units: dict[str, list[str]] = defaultdict(list)
    edges: dict[str, list[str]] = defaultdict(list)
    for unit_id in surface.unit_ids():
        prompt = (
            "List the entities (people, document ids, projects, addresses, dates) "
            "mentioned in this text, and directed relations between them.\n"
            'JSON only: {"entities": ["..."], "relations": [["a","b"], ...]}\n\n'
            f"[{unit_id}]\n{surface.read_one(unit_id)}"
        )
        completion = client.complete(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=GRAPH_INDEX_MAX_TOKENS,
        )
        usage.merge(completion.usage)
        payload = extract_json(completion.text)
        if not isinstance(payload, dict):
            continue
        ents = [
            str(e).strip().lower()
            for e in payload.get("entities", []) if str(e).strip()
        ]
        for e in ents:
            entity_units[e].append(unit_id)
        for pair in payload.get("relations", []):
            if isinstance(pair, list) and len(pair) >= 2:
                a, b = str(pair[0]).lower(), str(pair[1]).lower()
                edges[a].append(b)
                edges[b].append(a)
        # Co-mention is an edge too: HippoRAG's co-occurrence backbone.
        for i, a in enumerate(ents):
            for b in ents[i + 1:]:
                edges[a].append(b)
                edges[b].append(a)

    graph = {
        "entity_units": {k: sorted(set(v)) for k, v in entity_units.items()},
        "edges": {k: sorted(set(v)) for k, v in edges.items()},
    }
    write_atomic(path, json.dumps(graph, ensure_ascii=False))
    return graph


def graph_traverse(
    client: LLMClient, surface: ToolSurface, task: dict[str, Any]
) -> Result:
    """Chains as graph walks: extract question entities, walk, read the hits, answer.

    The coupled hop A->B is resolved because A and B are already connected nodes: the
    chain is a deterministic traversal, not an iterated search, so the per-question
    cost is fixed by construction (2 LLM calls + a walk that costs nothing).
    """
    usage = Usage()
    graph = _entity_graph(client, surface, usage)
    entity_units: dict[str, list[str]] = graph["entity_units"]
    edges: dict[str, list[str]] = graph["edges"]

    q_prompt = (
        f"Task: {task['question']}\n\n"
        "List the entities (names, ids, addresses, dates) this task is about.\n"
        'JSON only: {"entities": ["..."]}'
    )
    q = client.complete(
        messages=[{"role": "user", "content": q_prompt}], max_tokens=300
    )
    usage.merge(q.usage)
    entities = extract_json(q.text, "entities")
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
        cost = len(surface.read_one(u)) // 4
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
        f"entities:\n" + "\n".join(texts) + f"\n\n{ANSWER_CONTRACT}"
    )
    final = client.complete(messages=[{"role": "user", "content": solve}])
    usage.merge(final.usage)
    return _finish(final.text, usage, surface, [{"role": "user", "content": solve}], 2)


def extract_compute(
    client: LLMClient, surface: ToolSurface, task: dict[str, Any]
) -> Result:
    """Map to structured rows, aggregate in code, phrase once.

    map_reduce fails two ways: its reduce is prose (lossy) and context-bounded. Here
    the reduce is a computation — dedupe and counts happen in code, exactly, at zero
    LLM cost and with no context bound. The model phrases a computed table; it never
    does arithmetic in tokens.
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
    declared = extract_json(schema.text, "fields")
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
        try:
            payload = extract_json(completion.text, default={})
            for row in payload["rows"]:
                if isinstance(row, dict):
                    row["_unit"] = unit_id
                    rows.append(row)
        except (ValueError, KeyError, TypeError):
            continue

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
        f"Answer strictly from this table.\n\n{ANSWER_CONTRACT}"
    )
    final = client.complete(messages=[{"role": "user", "content": solve}])
    usage.merge(final.usage)
    return _finish(
        final.text, usage, surface,
        [{"role": "user", "content": solve}], len(surface.unit_ids()) + 2,
    )


CHUNK_TOKENS = 6_000
CARRY_MAX_CHARS = 6_000


def streaming_scan(
    client: LLMClient, surface: ToolSurface, task: dict[str, Any]
) -> Result:
    """One sequential pass with carried state: the corpus is paid exactly once.

    The unknown horizon stops mattering: the carry (a structured registry of findings
    and open candidates) grows with the FINDINGS, not with the steps, and each chunk is
    checked against it. No retrieval, no history resend, no lottery.
    """
    usage = Usage()

    chunks: list[list[str]] = [[]]
    spent = 0
    for unit_id in surface.unit_ids():
        cost = len(surface.read_one(unit_id)) // 4
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
        f"once:\n{carry}\n\n{ANSWER_CONTRACT}"
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

LEDGER_FACT_CHARS = 400


def pointer_chase(
    client: LLMClient, surface: ToolSurface, task: dict[str, Any]
) -> Result:
    """Follow the chain one unit at a time; the loop is code, the LLM is a sensor.

    Every hop the model sees the question, a small typed ledger of facts, and the
    full text of the CURRENT unit only. It emits a proposition — the fact this unit
    contributes and where the trail points next — and code does everything else:
    validates the pointer, fetches, counts stalls and hallucinated pointers, and
    stops at the arithmetic hop cap. Decoding is deterministic, so a revisit or a
    barren search can never resolve differently on a retry — both break immediately.
    """
    usage = Usage()
    unit_ids = surface.unit_ids()
    mean_unit = max(
        1, sum(len(surface.read_one(u)) for u in unit_ids) // max(1, len(unit_ids)) // 4
    )
    # Same arithmetic as app.feasibility: the cap is a guarantee, shared by both
    # layers, tested against the BUDGET — the chase holds no conversation (nothing is
    # resent; the solve reads a small ledger), so the conversation share is not owed.
    hop_cap = min(6, max(2, surface.budget_tokens // mean_unit))

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
        picked = extract_json(pick.text, "start")
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
                payload = extract_json(raw, default={})
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
        f"so.\n\n{ANSWER_CONTRACT}"
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
