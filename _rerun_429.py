"""Re-corre solo las celdas que quedaron en infra_error (429 agotado) en gold_deep.

Las filas infra_error fueron podadas del JSONL (backup en .bak); resume salta todo lo
completado. workers=1: estas son las tareas pesadas que saturaron la cuota.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from app.config import Settings
from app.runner import Runner

s = Settings.from_env()
print(f"modelo: {s.fingerprint()}", flush=True)
r = Runner(s, "gold_deep", retriever_arm="hybrid", surface_variant="basic")
rows = r.run_cross_product(
    paradigms=["react", "reflection", "dag_strategy"],
    task_ids=["c2-000-w48", "c5-000-w48"],
    repeat=3, workers=1,
)
err = sum(1 for x in rows if getattr(x, "infra_error", False))
tok = sum(x.cost_tokens for x in rows)
print(f"\n{len(rows)} filas nuevas, {err} infra_error, {tok:,} tokens\nFIN", flush=True)
