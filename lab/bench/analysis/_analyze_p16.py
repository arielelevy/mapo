"""Veredicto de P16 — CONGELADO ANTES DE CORRER (commiteado 2026-08-27).

Preregistrar la prediccion en prosa deja margen para elegir la valuacion despues de ver
los numeros. Congelar el CODIGO que juzga no lo deja: este archivo entra a la historia
git antes de que exista una sola fila de gold_p16, y el veredicto es lo que imprima.

QUE CORRIGE RESPECTO DE P15

  El eje.    theta se ajusta sobre regiones de 4 segmentos (regions/2-continuation).
             En P15 las tareas C5 caian en las mismas regiones que C2/C4 y el router
             no tenia como saber que estaba en el caso que lo castigaba.

  La accion. Se puntua lo que el producto HACE: una cascada escala peldano a peldano
             hasta que el oraculo acepta; un gate corre el fallback y no ejecuta el
             plan; una abstencion corre el fallback. Puntuar plan.paradigm valuaba
             solo el primer peldano de una escalera que el producto sube al fallar.

  EL COSTO.  Y esta es la salvedad que P15 no cerraba: escalar CUESTA. Una cascada
             que sube cuatro peldanos paga los cuatro. La utilidad neta cobra la suma
             de lo gastado en la escalera, no lo del peldano que acerto. Sin esto, la
             valuacion por accion regala la unica ventaja que el fijo tiene.

LOS DOS COHORTES, SEPARADOS ANTES DE VER NADA

  Las tareas C7 son irreversibles: el gate corre el fallback POR DISENO y el deficit
  que produce es el precio del gobierno, no un error de ruteo. En P15 el residuo
  entero era C7. Reportar un solo numero mezcla dos afirmaciones distintas, asi que
  se reportan las dos: el claim de RUTEO sobre el cohorte no gateado, y el PRECIO DEL
  GATE aparte. Ninguno de los dos se esconde detras del otro.

LAMBDA. La preferencia de costo no se elige despues: el veredicto primario es a
lambda = 0.05 (una preferencia modesta: un paradigma que cuesta el doble del mas
barato exitoso paga 0.05 de utilidad). Se reporta ademas el barrido completo, incluido
el lambda de cruce donde la ventaja desaparece — se publica aunque incomode.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.features import REGION_VOCABULARY, measure_continuation
from app.metrics import Study
from app.paradigms import COST_PRIORS, FALLBACK
from app.policy import Plasticity, PolicyBundle
from app.router import Router
from app.runner import Runner

CORPUS = "gold_p16"
TRAIN = ("gold_deep", "gold_holdout", "gold_v2", "gold_transfer")
LAMBDA_PRIMARY = 0.05
LAMBDA_SWEEP = (0.0, 0.02, 0.05, 0.1, 0.2, 0.4)
GATED_CELL_PREFIX = "C7"

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")


def continuation_of(corpus: str) -> dict[str, bool | None]:
    docs = json.load(open(f"corpus/{corpus}/documents.json"))
    tasks = json.load(open(f"corpus/{corpus}/tasks.json"))
    return {t["task_id"]: measure_continuation(docs, t["unit_ids"]) for t in tasks}


def segment(c: bool | None) -> str:
    return "c?" if c is None else ("chain" if c else "flat")


# ---- theta: registro previo, con el eje; gold_p16 jamas entra ----------------------
episodes = []
for corpus in TRAIN:
    runner = Runner(settings, corpus, retriever_arm="hybrid", surface_variant="basic")
    cont = continuation_of(corpus)
    for e in runner.episodes():
        episodes.append(
            replace(e, region=f"{e.region}/{segment(cont.get(e.task_id))}")
        )
theta = Plasticity.candidate(
    PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3), episodes, tau=0.3,
    notes=f"P16: {len(episodes)} cell episodes, {REGION_VOCABULARY}, {CORPUS} held out",
)
router = Router(theta, COST_PRIORS, FALLBACK)

target = Runner(settings, CORPUS, retriever_arm="hybrid", surface_variant="basic")
cont_target = continuation_of(CORPUS)
rows_by_task: dict[str, dict] = {}
for row in target.load_rows():
    rows_by_task.setdefault(row["task_id"], {})[row["paradigm"]] = row
cells = {t["task_id"]: t["cell"] for t in target._tasks}  # noqa: SLF001
tasks_by_id = {t["task_id"]: t for t in target._tasks}  # noqa: SLF001

plans: dict[str, object] = {}


def plan_for(task_id: str):
    if task_id not in plans:
        region = next(iter(rows_by_task[task_id].values()))["region"]
        plans[task_id] = router.plan(
            task=tasks_by_id[task_id],
            candidates=sorted(rows_by_task[task_id]),
            region=f"{region}/{segment(cont_target.get(task_id))}",
        )
    return plans[task_id]


def action_outcome(study: Study, task_id: str) -> tuple[float, int, str]:
    """(calidad obtenida, tokens gastados, accion) de lo que el producto HARIA."""
    plan = plan_for(task_id)
    row = rows_by_task[task_id]

    def cost_of(paradigm: str) -> int:
        return int(row[paradigm]["cost_tokens"]) if paradigm in row else 0

    if plan.action == "cascade" and len(plan.ladder) > 1:
        spent = 0
        for rung in plan.ladder:
            spent += cost_of(rung)
            if study.quality(task_id, rung) >= 1.0:
                return study.quality(task_id, rung), spent, plan.action
        return study.quality(task_id, plan.ladder[-1]), spent, plan.action

    paradigm = FALLBACK if plan.gated or plan.action == "defer_to_fallback" else plan.paradigm
    return study.quality(task_id, paradigm), cost_of(paradigm), plan.action


def net_utility(study: Study, task_id: str, quality: float, spent: int,
                lam: float) -> float:
    """Calidad menos la preferencia de costo, sobre lo REALMENTE gastado."""
    if lam == 0.0:
        return quality
    floor = study._min_cost[task_id]  # noqa: SLF001
    ratio = (spent / floor) if floor > 0 and spent > 0 else 1.0
    return quality - lam * (ratio - 1.0)


def evaluate(lam: float, task_ids: list[str]) -> dict:
    study = Study(
        [
            o for o in target.study()._obs  # noqa: SLF001
            if o.task_id in set(task_ids)
        ],
        lambda_cost=lam,
    )
    router_total = 0.0
    per_cell = defaultdict(list)
    actions = defaultdict(int)
    for task_id in task_ids:
        quality, spent, action = action_outcome(study, task_id)
        value = net_utility(study, task_id, quality, spent, lam)
        router_total += value
        actions[action] += 1
        per_cell[cells[task_id][:2]].append(value)
    router_value = router_total / len(task_ids)
    fixed = {p: study.mean_utility(p) for p in study.paradigms}
    best_fixed = max(fixed, key=fixed.get)
    return {
        "lambda": lam,
        "router": round(router_value, 5),
        "best_fixed": best_fixed,
        "best_fixed_value": round(fixed[best_fixed], 5),
        "always_react": round(fixed.get(FALLBACK, 0.0), 5),
        "net_vs_best_fixed": round(router_value - fixed[best_fixed], 5),
        "net_vs_always_react": round(router_value - fixed.get(FALLBACK, 0.0), 5),
        "actions": dict(actions),
        "per_cell": {c: round(sum(v) / len(v), 4) for c, v in sorted(per_cell.items())},
    }


# ---- piso de ruido POR CELDA, de las replicas del held-out -------------------------
raw = [
    json.loads(line)
    for line in (settings.results_dir / f"{CORPUS}_rows.jsonl")
    .read_text(encoding="utf-8").splitlines()
    if line.strip()
]
reps: dict[tuple[str, str], list[float]] = defaultdict(list)
for r in raw:
    if r.get("infra_error") or r.get("infeasible"):
        continue
    reps[(r["task_id"], r["paradigm"])].append(r["utility"])
floor_info = Study.noise_floor({f"{t}|{p}": u for (t, p), u in reps.items()})
noise = float(floor_info["noise_oracle_gap"])

all_tasks = sorted(target.study().complete_tasks)
routing_cohort = [t for t in all_tasks if not cells[t].startswith(GATED_CELL_PREFIX)]
gated_cohort = [t for t in all_tasks if cells[t].startswith(GATED_CELL_PREFIX)]

print(f"corpus: {CORPUS} (seed 61, nunca visto por theta)")
print(f"theta v{theta.version}: {len(episodes)} episodios de celda, {REGION_VOCABULARY}")
print(f"tareas: {len(all_tasks)} | cohorte de ruteo: {len(routing_cohort)} "
      f"| gateadas: {len(gated_cohort)}")
print(f"piso de ruido: {noise:.5f}\n")

primary = evaluate(LAMBDA_PRIMARY, routing_cohort)
print(f"--- P16a: cohorte de RUTEO, lambda={LAMBDA_PRIMARY} ---")
print(f"  ruteo={primary['router']:.4f} | mejor fijo ({primary['best_fixed']})="
      f"{primary['best_fixed_value']:.4f} | siempre-react={primary['always_react']:.4f}")
print(f"  neto vs mejor fijo: {primary['net_vs_best_fixed']:+.4f}")
print(f"  neto vs siempre-react: {primary['net_vs_always_react']:+.4f}")
print(f"  acciones: {primary['actions']}")
print(f"  por celda: {primary['per_cell']}")

beats_fixed = primary["net_vs_best_fixed"] > noise
beats_react = primary["net_vs_always_react"] > noise
verdict_a = (
    "CONFIRMADA" if (beats_fixed and beats_react)
    else ("REFUTADA (neta negativa mas alla del piso)"
          if min(primary["net_vs_best_fixed"], primary["net_vs_always_react"]) < -noise
          else "VACUA (dentro del piso)")
)
print(f"  P16a: {verdict_a}\n")

gate = evaluate(LAMBDA_PRIMARY, gated_cohort) if gated_cohort else None
if gate:
    print(f"--- P16b: PRECIO DEL GATE (cohorte irreversible, lambda={LAMBDA_PRIMARY}) ---")
    print(f"  gateado={gate['router']:.4f} vs mejor fijo={gate['best_fixed_value']:.4f} "
          f"| precio: {gate['net_vs_best_fixed']:+.4f}")
    print("  (deficit DELIBERADO: el gate corre el fallback en tareas irreversibles)\n")

print("--- P16c: barrido de lambda sobre el cohorte de ruteo ---")
crossover = None
for lam in LAMBDA_SWEEP:
    row = evaluate(lam, routing_cohort)
    mark = ""
    if crossover is None and row["net_vs_best_fixed"] <= noise:
        crossover = lam
        mark = "  <- la ventaja entra al ruido aca"
    print(f"  lambda={lam:<5} neto={row['net_vs_best_fixed']:+.4f} "
          f"(vs react {row['net_vs_always_react']:+.4f}){mark}")

print("\n--- P16d: reproducibilidad ---")
stable = 0
for task_id in all_tasks:
    first = plans[task_id] if task_id in plans else plan_for(task_id)
    region = next(iter(rows_by_task[task_id].values()))["region"]
    again = router.plan(
        task=tasks_by_id[task_id], candidates=sorted(rows_by_task[task_id]),
        region=f"{region}/{segment(cont_target.get(task_id))}",
    )
    if (again.paradigm == first.paradigm
            and again.verdict.get("belief_digest") == first.verdict.get("belief_digest")):
        stable += 1
print(f"  re-decision identica (paradigma + digest): {stable}/{len(all_tasks)}")

out = settings.results_dir / "p16_verdict.json"
out.write_text(json.dumps({
    "corpus": CORPUS,
    "region_vocabulary": REGION_VOCABULARY,
    "train_corpora": list(TRAIN),
    "cell_episodes": len(episodes),
    "noise_floor": floor_info,
    "lambda_primary": LAMBDA_PRIMARY,
    "routing_cohort": primary,
    "gate_price": gate,
    "sweep": [evaluate(lam, routing_cohort) for lam in LAMBDA_SWEEP],
    "lambda_crossover": crossover,
    "reproducible": f"{stable}/{len(all_tasks)}",
    "verdict_P16a": verdict_a,
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nveredicto: {out}")
