"""Emparejar la celda C3 por dificultad, y de paso medir el gradiente de acoplamiento.

gold_deep solo tiene cadenas de 1 y 2 saltos; la corrida previa de gold_v2 uso 3. Sin
estas dos filas la comparacion entre corpus compara profundidades distintas y se la puede
leer como un efecto del corpus cuando es un efecto de la tarea.

Bonus: con h1, h2 y h3 en el mismo corpus queda medido si la profundidad del acoplamiento
predice el fallo, que es la hipotesis estructural del 8.1.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner

TASKS = ["c3-000-h1", "c3-001-h2"]
PARAS = ["direct", "cot", "map_reduce", "react", "reflection", "plan_execute", "dag_strategy"]

r = Runner(Settings.from_env(), "gold_v2", retriever_arm="hybrid", surface_variant="basic")
rows = r.run_cross_product(paradigms=PARAS, task_ids=TASKS, repeat=1, workers=4)
print(f"\n{len(rows)} filas", flush=True)
for x in sorted(rows, key=lambda z: (z.task_id, z.paradigm)):
    print(f"  {x.task_id:12s} {x.paradigm:13s} u={x.utility:.3f} tok={x.cost_tokens:7d}", flush=True)
