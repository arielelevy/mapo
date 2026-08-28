"""Veredicto de P15, con el protocolo registrado en README.md ANTES de la corrida.

El punto no negociable del protocolo: theta se ajusta SOLO con el registro previo
(gold_deep, gold_holdout, gold_v2 en nano). Ninguna fila de gold_transfer entra a theta
antes de la comparacion. Despues theta decide sobre las 26 tareas del corpus nuevo y se
la puntua contra lo que cada paradigma realmente hizo ahi.

P15a  brecha NETA positiva contra el mejor fijo (incluido siempre-react), mas alla del
      piso de ruido por celda
P15b  la ganancia se concentra en C3/C5; en C1/C2 queda dentro del ruido
      (addendum registrado: si C3 da oraculo 0, esa mitad se reporta VACUA)
P15c  la abstencion no dana: donde theta difiere, el fallback queda dentro del ruido
      del mejor fijo
P15d  re-decidir desde la misma base de creencias da el mismo paradigma en el 100%
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import pathlib
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.metrics import Study
from app.paradigms import COST_PRIORS, FALLBACK
from app.policy import Plasticity, PolicyBundle
from app.router import Router
from app.runner import Runner

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")

# ---- theta: SOLO el registro previo -------------------------------------------------
TRAIN_CORPORA = ["gold_deep", "gold_holdout", "gold_v2"]
episodes = []
for corpus in TRAIN_CORPORA:
    path = settings.results_dir / f"{corpus}_rows.jsonl"
    if not path.exists():
        continue
    runner = Runner(settings, corpus, retriever_arm="hybrid", surface_variant="basic")
    eps = runner.episodes()
    episodes.extend(eps)
    print(f"  registro previo: {corpus:14s} {len(eps)} episodios")

theta = Plasticity.candidate(
    PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3),
    episodes,
    tau=0.3,
    notes=f"P15: fitted on {len(episodes)} episodes, gold_transfer never seen",
)
router = Router(theta, COST_PRIORS, FALLBACK)
print(f"theta v{theta.version} sobre {len(episodes)} episodios previos\n")

# ---- el corpus held-out --------------------------------------------------------------
transfer = Runner(settings, "gold_transfer", retriever_arm="hybrid", surface_variant="basic")
study = transfer.study()
rows_by_task: dict[str, dict] = {}
for row in transfer.load_rows():
    rows_by_task.setdefault(row["task_id"], {})[row["paradigm"]] = row

tasks_by_id = {t["task_id"]: t for t in transfer._tasks}  # noqa: SLF001
cell_of = {t["task_id"]: t["cell"] for t in transfer._tasks}  # noqa: SLF001


def region_of(task_id: str) -> str:
    return next(iter(rows_by_task[task_id].values()))["region"]


plans = {}
def decide(task_id: str) -> str:
    if task_id not in plans:
        plans[task_id] = router.plan(
            task=tasks_by_id[task_id],
            candidates=sorted(rows_by_task[task_id]),
            region=region_of(task_id),
        )
    return plans[task_id].paradigm


# ---- piso de ruido POR CELDA, de las replicas del corpus held-out ---------------------
raw = [json.loads(l) for l in
       (settings.results_dir / "gold_transfer_rows.jsonl").read_text(encoding="utf-8").splitlines()
       if l.strip()]
reps: dict[tuple[str, str], list[float]] = defaultdict(list)
for r in raw:
    if r.get("infra_error") or r.get("infeasible"):
        continue
    reps[(r["task_id"], r["paradigm"])].append(r["utility"])
floor_info = Study.noise_floor({f"{t}|{p}": u for (t, p), u in reps.items()})
print("piso de ruido (replicas held-out):", json.dumps(floor_info, ensure_ascii=False))

# ---- P15a -----------------------------------------------------------------------------
best_fixed = study.best_fixed()
value_router = study.router_value(decide)
value_fixed = {p: study.mean_utility(p) for p in study.paradigms}
net = value_router - value_fixed[best_fixed]
# The floor is the ORACLE-GAP the replicates alone can fake: with repeat=3, picking
# the luckiest trial per task inflates a selection gap by this much with no signal at
# all. A net gap smaller than this is not a result in either direction.
noise = float(floor_info["noise_oracle_gap"])

print(f"\ntareas completas: {len(study.complete_tasks)}")
print(f"oraculo: {study.oracle_value():.4f} | brecha de oraculo: {study.oracle_gap():.4f}")
for p, v in sorted(value_fixed.items(), key=lambda kv: -kv[1]):
    print(f"  fijo {p:14s} {v:.4f}" + ("   <- mejor fijo" if p == best_fixed else ""))
print(f"  RUTEO theta       {value_router:.4f}")
print(f"\nP15a: neta = {net:+.4f} | piso de ruido = {noise:.4f} | "
      f"captura de la brecha = {study.captured_fraction(decide):+.3f}")
if net > noise:
    verdict_a = "CONFIRMADA"
elif net < -noise:
    verdict_a = "REFUTADA (neta negativa mas alla del piso)"
else:
    verdict_a = "VACUA (neta dentro del piso de ruido)"
print("P15a:", verdict_a)

# ---- P15b: por celda ------------------------------------------------------------------
print("\nP15b — por celda (u ruteo vs u mejor fijo, por tarea):")
by_cell: dict[str, list[tuple[float, float]]] = defaultdict(list)
for t in study.complete_tasks:
    chosen = decide(t)
    by_cell[cell_of[t]].append((study.utility(t, chosen), study.utility(t, best_fixed)))
for cell in sorted(by_cell):
    pares = by_cell[cell]
    d = sum(a - b for a, b in pares) / len(pares)
    ur = sum(a for a, _ in pares) / len(pares)
    uf = sum(b for _, b in pares) / len(pares)
    oracle_cell = sum(
        max(study.utility(t, p) for p in study.paradigms)
        for t in study.complete_tasks if cell_of[t] == cell
    ) / len(pares)
    tag = " [VACUA: oraculo 0]" if oracle_cell == 0 else ""
    print(f"  {cell:28s} ruteo={ur:.3f} fijo={uf:.3f} delta={d:+.3f} "
          f"oraculo={oracle_cell:.3f}{tag}")

# ---- P15c: abstencion -----------------------------------------------------------------
deferred = [t for t in study.complete_tasks
            if plans[t].action == "defer_to_fallback"]
print(f"\nP15c — abstenciones: {len(deferred)}/{len(study.complete_tasks)}")
if deferred:
    du = sum(study.utility(t, FALLBACK) for t in deferred) / len(deferred)
    db = sum(study.utility(t, best_fixed) for t in deferred) / len(deferred)
    print(f"  en abstencion: fallback={du:.3f} vs mejor fijo={db:.3f} "
          f"(delta {du-db:+.3f}, ruido {noise:.3f})")

# ---- P15d: reproducibilidad -----------------------------------------------------------
again = {}
for t in study.complete_tasks:
    p2 = router.plan(task=tasks_by_id[t], candidates=sorted(rows_by_task[t]),
                     region=region_of(t))
    again[t] = (p2.paradigm, p2.verdict.get("belief_digest"))
stable = sum(1 for t in study.complete_tasks
             if again[t][0] == plans[t].paradigm
             and again[t][1] == plans[t].verdict.get("belief_digest"))
print(f"\nP15d — re-decision identica (paradigma + digest): "
      f"{stable}/{len(study.complete_tasks)}")

# ---- elecciones, para el registro ------------------------------------------------------
print("\nelecciones de theta:")
for t in sorted(study.complete_tasks):
    print(f"  {t:16s} {cell_of[t]:28s} -> {decide(t):14s} "
          f"(u={study.utility(t, decide(t)):.3f}, fijo u={study.utility(t, best_fixed):.3f})")

out = settings.results_dir / "p15_verdict.json"
out.write_text(json.dumps({
    "protocol": "theta fitted on prior record only; gold_transfer held out",
    "train_corpora": TRAIN_CORPORA,
    "episodes": len(episodes),
    "tasks": len(study.complete_tasks),
    "best_fixed": best_fixed,
    "fixed_values": {p: round(v, 5) for p, v in value_fixed.items()},
    "router_value": round(value_router, 5),
    "net_gap": round(net, 5),
    "noise_floor": floor_info,
    "captured_fraction": round(study.captured_fraction(decide), 5),
    "deferred_tasks": deferred,
    "reproducible": stable,
    "choices": {t: decide(t) for t in sorted(study.complete_tasks)},
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nveredicto: {out}")
