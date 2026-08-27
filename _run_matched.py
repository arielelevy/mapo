"""La comparacion controlada: misma cardinalidad, 30x el contenido.

gold_v2  c2-000-w48: 60 unidades,  16.110 tokens
gold_deep c2-000-w48: 60 unidades, 483.104 tokens

Misma cantidad de unidades, mismo grafo, misma pregunta. Lo unico que cambia es cuanto
texto tiene cada unidad. Por eso es la comparacion que el paper necesita y no una entre
corpus distintos: aisla la variable en lugar de confundirla con la cardinalidad.

Y empareja la celda C3 por profundidad. gold_deep solo tiene h1 y h2, asi que la corrida
previa de gold_v2 con h3 no era comparable con nada.
"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from app.config import Settings
from app.runner import Runner

PARAS = ["direct", "cot", "map_reduce", "react", "reflection", "plan_execute", "dag_strategy"]
PLAN = [
    ("gold_v2",   ["c3-000-h1", "c3-001-h2"]),                              # emparejar C3
    ("gold_deep", ["c2-000-w48", "c4-000-w48", "c5-000-w48", "c3-001-h2"]),  # el regimen
]

s = Settings.from_env()
for corpus, tasks in PLAN:
    print(f"\n{'='*70}\n{corpus}: {tasks}\n{'='*70}", flush=True)
    t0 = time.perf_counter()
    r = Runner(s, corpus, retriever_arm="hybrid", surface_variant="basic")
    rows = r.run_cross_product(paradigms=PARAS, task_ids=tasks, repeat=1, workers=2)
    inf = sum(1 for x in rows if getattr(x, "infeasible", False))
    err = sum(1 for x in rows if getattr(x, "infra_error", False))
    tok = sum(x.cost_tokens for x in rows)
    print(f"\n{corpus}: {len(rows)} filas, {inf} infactibles (gratis), {err} fallos de "
          f"infraestructura, {tok:,} tokens, {time.perf_counter()-t0:.0f}s", flush=True)
print("\nFIN")
