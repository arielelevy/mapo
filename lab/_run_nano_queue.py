"""TODO el pendiente sobre gpt-5.4-nano (decision del autor 2026-08-26: nano en
adelante). t=0 + seed = determinismo casi al token (verificado en smoke: replicas de
direct identicas), cuota propia de 2,5M+ TPM, costo tier-nano.

Fases secuenciales, resultados en results/nano/ (fingerprint separa el modelo):
  A. Grillas emparejadas baseline: gold_v2 + gold_deep, 8 paradigmas activos, repeat=2
     (con determinismo, la segunda replica CONFIRMA la identidad en vez de estimar
     varianza; si difiere, eso ES el hallazgo).
  B. Held-out P8 (gold_holdout, seed 23).
  C. Superficie managed P9 (react + dag sobre gold_deep).
  D. Candidatos P10-P12 (graph_traverse / extract_compute / streaming_scan).

NOTA DE REGISTRO: P8/P9 fueron registradas cuando el modelo era gpt-5-chat; el cambio a
nano es una decision posterior y queda declarado. La grilla gpt-5-chat queda congelada
como primer modelo, con sus celdas + pendientes documentadas.
"""
import os
import sys
import time
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from app.config import Settings
from app.runner import Runner

base = Settings.from_env()
nano_results = base.results_dir / "nano"
nano_results.mkdir(parents=True, exist_ok=True)
S = replace(
    base,
    endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
    api_key=os.environ["MAPO_NANO_KEY"],
    chat_deployment="gpt-5.4-nano",
    temperature=0.0,
    results_dir=nano_results,
)
print(f"modelo: {S.fingerprint()}", flush=True)

PARAS = ["direct", "react", "map_reduce", "plan_execute", "reflection",
         "dag_strategy", "rewoo", "gist_reader"]
V2_TASKS = ["c2-000-w48", "c3-000-h1", "c3-001-h2", "c3-002-h3", "c4-000-w48", "c5-000-w48"]
DEEP_TASKS = ["c2-000-w4", "c2-000-w48", "c3-000-h1", "c3-001-h2",
              "c4-000-w4", "c4-000-w48", "c5-000-w4", "c5-000-w48"]
DISC = ["c2-000-w48", "c3-001-h2", "c4-000-w48", "c5-000-w48"]


def report(tag, rows):
    inf = sum(1 for x in rows if getattr(x, "infeasible", False))
    err = sum(1 for x in rows if getattr(x, "infra_error", False))
    tok = sum(x.cost_tokens for x in rows)
    print(f"{tag}: {len(rows)} filas, {inf} infactibles, {err} infra_error, "
          f"{tok:,} tokens", flush=True)


t0 = time.perf_counter()

print("\n== A. grilla gold_v2 ==", flush=True)
r = Runner(S, "gold_v2", retriever_arm="hybrid", surface_variant="basic")
report("gold_v2", r.run_cross_product(paradigms=PARAS, task_ids=V2_TASKS, repeat=2, workers=2))

print("\n== A. grilla gold_deep ==", flush=True)
r = Runner(S, "gold_deep", retriever_arm="hybrid", surface_variant="basic")
report("gold_deep", r.run_cross_product(paradigms=PARAS, task_ids=DEEP_TASKS, repeat=2, workers=2))

print("\n== B. held-out P8 ==", flush=True)
r = Runner(S, "gold_holdout", retriever_arm="hybrid", surface_variant="basic")
report("holdout", r.run_cross_product(
    paradigms=["react", "dag_strategy", "map_reduce", "rewoo", "gist_reader"],
    task_ids=DISC, repeat=2, workers=2))

print("\n== C. managed P9 ==", flush=True)
r = Runner(S, "gold_deep", retriever_arm="hybrid", surface_variant="managed")
report("managed", r.run_cross_product(
    paradigms=["react", "dag_strategy"], task_ids=DISC, repeat=2, workers=2))

print("\n== D. candidatos P10-P12 ==", flush=True)
r = Runner(S, "gold_deep", retriever_arm="hybrid", surface_variant="basic")
for paradigm, tasks, rep in [
    ("graph_traverse", ["c3-000-h1", "c3-001-h2", "c5-000-w48"], 2),
    ("extract_compute", ["c2-000-w48", "c4-000-w48", "c3-001-h2"], 1),
    ("streaming_scan", ["c5-000-w48", "c2-000-w48"], 1),
]:
    report(paradigm, r.run_cross_product(
        paradigms=[paradigm], task_ids=tasks, repeat=rep, workers=2))

print(f"\nTOTAL: {(time.perf_counter()-t0)/60:.1f} min\nFIN", flush=True)
