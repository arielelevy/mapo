"""Datos para los graficos de area de las corridas relevantes. Cero tokens.

TRES PREGUNTAS QUE SON DE AREA DE VERDAD. Un area apilada afirma "partes de un todo
sobre un eje ordenado"; usarla para otra cosa miente con la forma antes de mentir con
los numeros. Las tres de aca cumplen:

1. RIESGO-COBERTURA. Cuanta brecha de oraculo captura el ruteo a cada nivel de
   cobertura. El area BAJO la curva es la medida estandar de un predictor selectivo, y
   el eje x es cobertura de 0 a 1: continuo y ordenado.

2. DE DONDE SALE LA UTILIDAD EN LA ESCALERA. La cascada prueba peldanos en orden y se
   queda con el primero que resuelve. Cuanta utilidad aporta CADA peldano es una
   descomposicion de un total sobre un eje ordenado por construccion — la profundidad.
   Es la unica figura que muestra por que el peldano inicial no puede mover la calidad.

3. QUE PAGO LA CORRIDA. Tokens acumulados por paradigma a lo largo de la grilla. El
   costo se suma, y la pregunta es que fraccion se lleva cada paradigma: composicion
   sobre un eje ordenado.

Lo que NO se grafica como area: utilidad por celda entre paradigmas. Cinco paradigmas
sobre una tarea no son partes de un todo — son cinco mediciones alternativas de la misma
cosa, y apilarlas inventa una suma que no existe.
"""

import json
import sys
from collections import defaultdict
from dataclasses import replace

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.features import measure_continuation
from app.paradigms import COST_PRIORS, FALLBACK
from app.policy import Plasticity, PolicyBundle
from app.router import Router
from app.runner import Runner

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")
CORPUS = "gold_transfer"


def continuation_of(corpus):
    docs = json.load(open(f"corpus/{corpus}/documents.json", encoding="utf-8"))
    tasks = json.load(open(f"corpus/{corpus}/tasks.json", encoding="utf-8"))
    return {t["task_id"]: measure_continuation(docs, t["unit_ids"]) for t in tasks}


def segment(c):
    return "c?" if c is None else ("chain" if c else "flat")


episodes = []
for corpus in ("gold_deep", "gold_holdout", "gold_v2"):
    runner = Runner(settings, corpus, retriever_arm="hybrid", surface_variant="basic")
    cont = continuation_of(corpus)
    for e in runner.episodes():
        episodes.append(replace(e, region=f"{e.region}/{segment(cont.get(e.task_id))}"))
theta = Plasticity.candidate(
    PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3), episodes, tau=0.3
)
router = Router(theta, COST_PRIORS, FALLBACK)

target = Runner(settings, CORPUS, retriever_arm="hybrid", surface_variant="basic")
study = target.study()
cont_t = continuation_of(CORPUS)
rows = list(target.load_rows())
rows_by_task = defaultdict(dict)
for row in rows:
    rows_by_task[row["task_id"]][row["paradigm"]] = row
tasks_by_id = {t["task_id"]: t for t in target._tasks}  # noqa: SLF001
cells = {t["task_id"]: t["cell"] for t in target._tasks}  # noqa: SLF001
docs = json.load(open(f"corpus/{CORPUS}/documents.json", encoding="utf-8"))
complete = sorted(study.complete_tasks)
best_fixed = study.best_fixed()


def region_of(task_id):
    region = next(iter(rows_by_task[task_id].values()))["region"]
    return f"{region}/{segment(cont_t.get(task_id))}"


def plan_for(task_id):
    return router.plan(
        task=tasks_by_id[task_id],
        candidates=sorted(rows_by_task[task_id]),
        region=region_of(task_id),
        documents=docs,
    )


def rank(task_id):
    _, margin = router.theta_assertions(region_of(task_id), sorted(rows_by_task[task_id]))
    return margin


# --- 1. riesgo-cobertura ------------------------------------------------------------
# Dos rankings sobre LAS MISMAS propuestas, y la diferencia entre los dos separa dos
# fallas que se confunden todo el tiempo: "la propuesta es mala" y "el orden de
# confianza es malo". Si el techo tambien es plano, ranquear mejor no compra nada y el
# problema esta en que se propone.
def rank_oracle(task_id):
    """TECHO, calculado con gold. No es una politica: nadie puede rankear asi."""
    proposed = plan_for(task_id).paradigm
    return study.quality(task_id, proposed) - study.quality(task_id, best_fixed)


def sweep(rank_fn):
    curve = study.risk_coverage(rank=rank_fn, propose=lambda t: plan_for(t).paradigm)
    if not curve:
        return [], 0.0
    cov = np.array([p["coverage"] for p in curve])
    cap = np.array([p["captured"] for p in curve])
    order = np.argsort(cov)
    area = float(np.trapezoid(cap[order], cov[order]))
    points = [
        {"coverage": round(float(cov[i]), 4), "captured": round(float(cap[i]), 5)}
        for i in order
    ]
    return points, area


risk_coverage, aurc = sweep(rank)
ceiling, aurc_ceiling = sweep(rank_oracle)
degenerate = len({(p["coverage"], p["captured"]) for p in risk_coverage}) <= 1

# --- 2. de donde sale la utilidad en la escalera ------------------------------------
# Por cada tarea que cascadea, cual peldano fue el primero en resolver. La utilidad se
# le atribuye a ESE peldano; los anteriores aportaron cero y su costo igual se pago.
ladder = defaultdict(lambda: {"solved": 0.0, "tasks": 0})
max_depth = 0
cascading = 0
for t in complete:
    plan = plan_for(t)
    if plan.action != "cascade" or len(plan.ladder) < 2:
        continue
    cascading += 1
    max_depth = max(max_depth, len(plan.ladder))
    for depth, rung in enumerate(plan.ladder, start=1):
        q = study.quality(t, rung)
        ladder[depth]["tasks"] += 1
        if q >= 1.0:
            ladder[depth]["solved"] += q
            break
        if depth == len(plan.ladder):
            ladder[depth]["solved"] += q

ladder_area = [
    {
        "depth": d,
        "utility": round(ladder[d]["solved"], 4),
        "attempted": ladder[d]["tasks"],
    }
    for d in range(1, max_depth + 1)
]

# --- 3. que pago la corrida ---------------------------------------------------------
# Tokens acumulados por paradigma, con las tareas ordenadas por costo total: la curva
# muestra donde se concentra el gasto, no el orden accidental del archivo.
paradigms = sorted({r["paradigm"] for r in rows})
per_task = defaultdict(lambda: defaultdict(float))
for r in rows:
    if r.get("infra_error"):
        continue
    per_task[r["task_id"]][r["paradigm"]] += r["cost_tokens"]

task_order = sorted(per_task, key=lambda t: -sum(per_task[t].values()))
running = {p: 0.0 for p in paradigms}
cost_area = []
for i, t in enumerate(task_order, start=1):
    for p in paradigms:
        running[p] += per_task[t].get(p, 0.0)
    cost_area.append({
        "tasks": i,
        "cell": cells[t][:2],
        **{p: round(running[p]) for p in paradigms},
    })

out = {
    "corpus": CORPUS,
    "tasks": len(complete),
    "best_fixed": best_fixed,
    "aurc": round(aurc, 5),
    "aurc_ceiling": round(aurc_ceiling, 5),
    "risk_coverage": risk_coverage,
    "risk_coverage_degenerate": degenerate,
    "risk_coverage_ceiling": ceiling,
    "ladder": ladder_area,
    "cascading_tasks": cascading,
    "paradigms": paradigms,
    "cost": cost_area,
    "total_tokens": round(sum(running.values())),
}
path = settings.results_dir / "area_plots.json"
path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"corpus {CORPUS} | {len(complete)} tareas | mejor fijo {best_fixed}")
print(f"AURC theta {aurc:+.5f}" + ("   [DEGENERADA: un solo punto]" if degenerate else ""))
print(f"AURC techo {aurc_ceiling:+.5f}   (ranking con gold, no es una politica)")
print(f"escalera: {cascading} tareas cascadean, profundidad max {max_depth}")
for row in ladder_area:
    print(f"  peldano {row['depth']}: resuelve u={row['utility']:.2f} "
          f"sobre {row['attempted']} intentos")
print(f"costo total {out['total_tokens']:,} tokens en {len(paradigms)} paradigmas")
print(f"escrito: {path}")
