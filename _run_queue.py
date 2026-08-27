"""Cola diferida: todo lo pendiente en una pasada secuencial, workers=1.

Se lanza con una espera inicial para dejar que la cuota TPM del deployment se recupere
(hoy quedo agotada: los 429 sobrevivieron al presupuesto de reintento en las celdas de
~130k tokens). Orden: (0) podar filas infra_error para que el resume las retome,
(1) relleno de celdas 429 de gold_deep, (2) transferencia held-out (P8), (3) screening
de la superficie managed (P9).
"""
import json
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WAIT_MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0
print(f"esperando {WAIT_MINUTES:.0f} min para que la cuota se recupere...", flush=True)
time.sleep(WAIT_MINUTES * 60)

from app.config import Settings
from app.runner import Runner


def prune_infra(corpus: str) -> int:
    path = f"results/{corpus}_rows.jsonl"
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except FileNotFoundError:
        return 0
    keep = [l for l in lines if not json.loads(l).get("infra_error")]
    dropped = len(lines) - len(keep)
    if dropped:
        shutil.copy(path, path + ".bak")
        open(path, "w", encoding="utf-8").write("\n".join(keep) + "\n")
    print(f"{corpus}: {dropped} filas infra_error podadas", flush=True)
    return dropped


def report(tag: str, rows) -> None:
    inf = sum(1 for x in rows if getattr(x, "infeasible", False))
    err = sum(1 for x in rows if getattr(x, "infra_error", False))
    tok = sum(x.cost_tokens for x in rows)
    print(f"{tag}: {len(rows)} filas, {inf} infactibles, {err} infra_error, "
          f"{tok:,} tokens", flush=True)


s = Settings.from_env()
print(f"modelo: {s.fingerprint()}", flush=True)
TASKS = ["c2-000-w48", "c3-001-h2", "c4-000-w48", "c5-000-w48"]

# (1) relleno de las celdas 429 de gold_deep
prune_infra("gold_deep")
r = Runner(s, "gold_deep", retriever_arm="hybrid", surface_variant="basic")
report("relleno 429", r.run_cross_product(
    paradigms=["react", "reflection", "dag_strategy"],
    task_ids=["c2-000-w48", "c5-000-w48"], repeat=3, workers=1))

# (2) transferencia held-out (prediccion P8, registrada 2026-08-26)
rh = Runner(s, "gold_holdout", retriever_arm="hybrid", surface_variant="basic")
report("held-out P8", rh.run_cross_product(
    paradigms=["react", "dag_strategy", "map_reduce", "rewoo", "gist_reader"],
    task_ids=TASKS, repeat=2, workers=1))

# (3) screening de la superficie managed (prediccion P9, registrada 2026-08-26)
rm = Runner(s, "gold_deep", retriever_arm="hybrid", surface_variant="managed")
report("managed P9", rm.run_cross_product(
    paradigms=["react", "dag_strategy"], task_ids=TASKS, repeat=2, workers=1))

print("FIN", flush=True)
