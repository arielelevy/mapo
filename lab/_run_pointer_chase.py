"""Screening de pointer_chase (P14a/P14b, registradas en README.md 2026-08-27 ANTES
de esta corrida). Nicho: las celdas acopladas de gold_deep, repeat=2 (el bucle es
codigo — la dispersion entre replicas es parte de la prediccion). Anti-nicho:
c2 (cobertura) y c5 (contradiccion), repeat=1 — chequeo de freno, no de calidad.

Estimado antes de correr: nicho 2 tareas x 2 trials x ~35k + anti-nicho 2 x ~50k
=> ~240k tokens gpt-5-chat. Lanzar SOLO sin otra corrida gpt-5-chat activa.
"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from app.config import Settings
from app.runner import Runner

PLAN = [
    ("pointer_chase", ["c3-000-h1", "c3-001-h2"], 2),
    ("pointer_chase", ["c2-000-w48", "c5-000-w48"], 1),
]

s = Settings.from_env()
print(f"modelo: {s.fingerprint()}", flush=True)
r = Runner(s, "gold_deep", retriever_arm="hybrid", surface_variant="basic")
t0 = time.perf_counter()
grand = 0
for paradigm, tasks, repeat in PLAN:
    rows = r.run_cross_product(
        paradigms=[paradigm], task_ids=tasks, repeat=repeat, workers=1
    )
    tok = sum(x.cost_tokens for x in rows)
    err = sum(1 for x in rows if getattr(x, "infra_error", False))
    inf = sum(1 for x in rows if getattr(x, "infeasible", False))
    grand += tok
    print(f"{paradigm} {tasks}: {len(rows)} filas, {inf} infactibles, "
          f"{err} infra_error, {tok:,} tokens", flush=True)
print(f"\nTOTAL: {grand:,} tokens, {(time.perf_counter()-t0)/60:.1f} min\nFIN", flush=True)
