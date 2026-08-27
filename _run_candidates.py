"""Screening minimo de los 3 candidatos verificados, cada uno en su nicho.

graph_traverse: celdas acopladas (su tesis) + c5 (chequeo de fallo), repeat=2 (el costo
por pregunta es trivial tras el indice, que queda memoizado en disco y en el cache LLM).
extract_compute: cobertura/agregacion (su tesis) + c3 (chequeo de fallo), repeat=1.
streaming_scan: horizonte desconocido (su tesis) + c2 (riesgo de recall), repeat=1.

Predicciones P10a-P12b registradas en README.md ANTES de esta corrida (2026-08-26).
Lanzar SOLO cuando no haya otra corrida activa (cuota TPM compartida).
"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from app.config import Settings
from app.runner import Runner

PLAN = [
    ("graph_traverse", ["c3-000-h1", "c3-001-h2", "c5-000-w48"], 2),
    ("extract_compute", ["c2-000-w48", "c4-000-w48", "c3-001-h2"], 1),
    ("streaming_scan", ["c5-000-w48", "c2-000-w48"], 1),
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
    grand += tok
    print(f"{paradigm}: {len(rows)} filas, {err} infra_error, {tok:,} tokens", flush=True)
print(f"\nTOTAL: {grand:,} tokens, {(time.perf_counter()-t0)/60:.1f} min\nFIN", flush=True)
