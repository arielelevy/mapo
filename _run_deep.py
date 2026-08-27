"""gold_deep, las mismas 4 celdas que gold_v2, para que la comparacion sea legitima.

Es el regimen que el paper declara como su amenaza de validez mas grande: aca leer todo
no es caro, es NO DISPONIBLE. direct/cot quedan podados por aritmetica antes de gastar un
token, y esas filas se registran como infactibles y no como respuestas equivocadas.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner

TASKS = ["c2-000-w4", "c3-000-h1", "c4-000-w4", "c5-000-w4"]
PARAS = ["direct", "cot", "map_reduce", "react", "reflection", "plan_execute", "dag_strategy"]

s = Settings.from_env()
print(f"modelo: {s.fingerprint()}", flush=True)
r = Runner(s, "gold_deep", retriever_arm="hybrid", surface_variant="basic")
rows = r.run_cross_product(paradigms=PARAS, task_ids=TASKS, repeat=1, workers=2)

print(f"\n{len(rows)} filas", flush=True)
inf = [x for x in rows if getattr(x, "infeasible", False)]
print(f"infactibles (gratis): {len(inf)}", flush=True)
for x in sorted(rows, key=lambda z: (z.paradigm, z.task_id)):
    flag = "INFACTIBLE" if getattr(x, "infeasible", False) else f"u={x.utility:.3f}"
    print(f"  {x.paradigm:13s} {x.task_id:12s} {flag:12s} tok={x.cost_tokens:7d} calls={x.calls:3d}", flush=True)
