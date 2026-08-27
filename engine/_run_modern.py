"""Screening de rewoo y gist_reader + relleno de las celdas 429 pendientes.

Fase 1 (nueva medicion): 2 paradigmas x 4 tareas discriminantes x repeat=2 en gold_deep.
Fase 2 (relleno): las celdas react/reflection/dag_strategy de c2/c5-w48 que quedaron en
infra_error por 429. workers=1 en ambas: la cuota del deployment demostro saturarse con 2.

Predicciones P6a-P7c registradas en README.md ANTES de esta corrida (2026-08-26).
"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from app.config import Settings
from app.runner import Runner

TASKS = ["c2-000-w48", "c3-001-h2", "c4-000-w48", "c5-000-w48"]

s = Settings.from_env()
print(f"modelo: {s.fingerprint()}", flush=True)
r = Runner(s, "gold_deep", retriever_arm="hybrid", surface_variant="basic")

t0 = time.perf_counter()
print("\n== FASE 1: screening rewoo + gist_reader ==", flush=True)
rows1 = r.run_cross_product(
    paradigms=["rewoo", "gist_reader"], task_ids=TASKS, repeat=2, workers=1
)
tok1 = sum(x.cost_tokens for x in rows1)
err1 = sum(1 for x in rows1 if getattr(x, "infra_error", False))
print(f"fase 1: {len(rows1)} filas, {err1} infra_error, {tok1:,} tokens", flush=True)

print("\n== FASE 2: relleno de celdas 429 ==", flush=True)
rows2 = r.run_cross_product(
    paradigms=["react", "reflection", "dag_strategy"],
    task_ids=["c2-000-w48", "c5-000-w48"], repeat=3, workers=1,
)
tok2 = sum(x.cost_tokens for x in rows2)
err2 = sum(1 for x in rows2 if getattr(x, "infra_error", False))
print(f"fase 2: {len(rows2)} filas, {err2} infra_error, {tok2:,} tokens", flush=True)

print(f"\nTOTAL: {tok1 + tok2:,} tokens, {(time.perf_counter()-t0)/60:.1f} min\nFIN", flush=True)
