"""Transferencia a mundo held-out (seed 23): ¿las conclusiones eran del mundo o de la
estructura?

5 paradigmas informativos x 4 tareas discriminantes x repeat=2, workers=1. direct/cot
quedan afuera (la factibilidad los poda gratis en este regimen); plan_execute queda
afuera del screening (perdedor confirmado en dos corpus — sumarlo no discrimina nada).

Prediccion P8 registrada en README.md ANTES de esta corrida (2026-08-26).
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from app.config import Settings
from app.runner import Runner

PARAS = ["react", "dag_strategy", "map_reduce", "rewoo", "gist_reader"]
TASKS = ["c2-000-w48", "c3-001-h2", "c4-000-w48", "c5-000-w48"]

s = Settings.from_env()
print(f"modelo: {s.fingerprint()}", flush=True)
r = Runner(s, "gold_holdout", retriever_arm="hybrid", surface_variant="basic")
t0 = time.perf_counter()
rows = r.run_cross_product(paradigms=PARAS, task_ids=TASKS, repeat=2, workers=1)
inf = sum(1 for x in rows if getattr(x, "infeasible", False))
err = sum(1 for x in rows if getattr(x, "infra_error", False))
tok = sum(x.cost_tokens for x in rows)
print(f"\n{len(rows)} filas, {inf} infactibles (gratis), {err} infra_error, "
      f"{tok:,} tokens, {(time.perf_counter()-t0)/60:.1f} min\nFIN", flush=True)
