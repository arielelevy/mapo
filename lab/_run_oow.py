"""El estudio fuera-de-ventana con repeat=3: gold_v2 (dentro) vs gold_deep (fuera).

Sets de tareas emparejados por celda y profundidad; repeat=3 para que el piso de ruido
sea estimable POR CELDA (addendum 8ter del gate: un piso agregado sobre una distribucion
donde una celda es bimodal describe mal a todas). resume=True: los trials ya corridos no
se repagan. Un 429 agotado queda como infra_error y fuera de toda estadistica.

Predicciones P1-P5 registradas en README el 2026-08-26, ANTES de esta corrida.
"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from app.config import Settings
from app.runner import Runner

PARAS = ["direct", "cot", "map_reduce", "react", "reflection", "plan_execute", "dag_strategy"]
PLAN = [
    ("gold_v2",   ["c2-000-w48", "c3-000-h1", "c3-001-h2", "c3-002-h3",
                   "c4-000-w48", "c5-000-w48"]),
    ("gold_deep", ["c2-000-w4", "c2-000-w48", "c3-000-h1", "c3-001-h2",
                   "c4-000-w4", "c4-000-w48", "c5-000-w4", "c5-000-w48"]),
]
REPEAT = 3

s = Settings.from_env()
print(f"modelo: {s.fingerprint()}", flush=True)
grand = 0
for corpus, tasks in PLAN:
    print(f"\n{'='*70}\n{corpus}: {len(tasks)} tareas x {len(PARAS)} paradigmas x repeat={REPEAT}\n{'='*70}", flush=True)
    t0 = time.perf_counter()
    r = Runner(s, corpus, retriever_arm="hybrid", surface_variant="basic")
    rows = r.run_cross_product(paradigms=PARAS, task_ids=tasks, repeat=REPEAT, workers=2)
    inf = sum(1 for x in rows if getattr(x, "infeasible", False))
    err = sum(1 for x in rows if getattr(x, "infra_error", False))
    tok = sum(x.cost_tokens for x in rows)
    grand += tok
    print(f"\n{corpus}: {len(rows)} filas nuevas, {inf} infactibles (gratis), "
          f"{err} infra_error (excluidas), {tok:,} tokens, "
          f"{(time.perf_counter()-t0)/60:.1f} min", flush=True)
print(f"\nTOTAL corrida: {grand:,} tokens\nFIN", flush=True)
