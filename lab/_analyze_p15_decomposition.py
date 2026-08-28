"""Descomposicion EXPLORATORIA del -0.087 de P15 (post-registro, mismo corpus).

El veredicto registrado de P15 queda en pie. Esto responde, gratis y sobre las filas ya
pagadas, POR QUE dio lo que dio — y que tiene que prerregistrar P16.

Tres valuaciones, en orden:

  1. P15 registrada        theta sin eje, puntuando plan.paradigm      -> -0.0874
  2. + eje de continuidad  la region gana el 4to segmento (chain/flat) -> -0.0874
                           El eje separa C5 PERFECTO en los tres corpus (6/6, sin
                           falsos positivos en C1/C2/C4). Necesario, no suficiente:
                           theta no tiene senal utilizable en esas regiones nuevas.
  3. por ACCION real       la cascada ESCALA cuando el oraculo rechaza -> -0.0112
                           (hallazgo 3.9.1 del handoff: puntuar plan.paradigm valua
                           solo el primer peldano de una escalera que el producto
                           subiria). Adentro del piso de ruido (0.0573).

El residuo es TODO C7 (-0.333): tareas irreversibles donde el gate corre el fallback
por diseno. El deficit restante es el PRECIO DEL GATE, no un error de ruteo.

Salvedad que P16 debe cerrar: la valuacion por accion no descuenta el costo de escalar
(la escalera completa midio 4.4x en el estudio de cascada) ni la sensibilidad del
detector (< 1.0 fue catastrofica en ese mismo estudio). P16 se prerregistra con
valuacion por accion CON costo.
"""

import json
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.features import measure_continuation
from app.paradigms import COST_PRIORS, FALLBACK
from app.policy import Plasticity, PolicyBundle
from app.router import Router
from app.runner import Runner

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")

NOISE = 0.05729  # piso de ruido de las replicas del held-out (ver _analyze_p15.py)


def continuation_of(corpus: str) -> dict[str, bool | None]:
    docs = json.load(open(f"corpus/{corpus}/documents.json"))
    tasks = json.load(open(f"corpus/{corpus}/tasks.json"))
    return {t["task_id"]: measure_continuation(docs, t["unit_ids"]) for t in tasks}


def segment(c: bool | None) -> str:
    return "c?" if c is None else ("chain" if c else "flat")


def fit_theta(with_axis: bool) -> Router:
    episodes = []
    for corpus in ("gold_deep", "gold_holdout", "gold_v2"):
        runner = Runner(settings, corpus, retriever_arm="hybrid", surface_variant="basic")
        cont = continuation_of(corpus) if with_axis else {}
        for e in runner.episodes():
            region = f"{e.region}/{segment(cont.get(e.task_id))}" if with_axis else e.region
            episodes.append(replace(e, region=region))
    theta = Plasticity.candidate(
        PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3), episodes, tau=0.3
    )
    return Router(theta, COST_PRIORS, FALLBACK)


transfer = Runner(settings, "gold_transfer", retriever_arm="hybrid", surface_variant="basic")
study = transfer.study()
cont_t = continuation_of("gold_transfer")
rows_by_task: dict[str, dict] = {}
for row in transfer.load_rows():
    rows_by_task.setdefault(row["task_id"], {})[row["paradigm"]] = row
cells = {t["task_id"]: t["cell"] for t in transfer._tasks}  # noqa: SLF001
tasks_by_id = {t["task_id"]: t for t in transfer._tasks}  # noqa: SLF001
best_fixed = study.best_fixed()
fixed_value = study.mean_utility(best_fixed)


def plan_for(router: Router, task_id: str, with_axis: bool):
    region = next(iter(rows_by_task[task_id].values()))["region"]
    if with_axis:
        region = f"{region}/{segment(cont_t.get(task_id))}"
    return router.plan(
        task=tasks_by_id[task_id],
        candidates=sorted(rows_by_task[task_id]),
        region=region,
    )


def value(router: Router, with_axis: bool, action_aware: bool):
    total, per_cell = 0.0, defaultdict(list)
    for task_id in study.complete_tasks:
        plan = plan_for(router, task_id, with_axis)
        if action_aware and plan.action == "cascade" and len(plan.ladder) > 1:
            utility = None
            for rung in plan.ladder:
                if study.utility(task_id, rung) >= 1.0:
                    utility = study.utility(task_id, rung)
                    break
            if utility is None:
                utility = study.utility(task_id, plan.ladder[-1])
        else:
            utility = study.utility(task_id, plan.paradigm)
        total += utility
        per_cell[cells[task_id][:2]].append(
            (utility, study.utility(task_id, best_fixed))
        )
    return total / len(study.complete_tasks), per_cell


print(f"mejor fijo ({best_fixed}): {fixed_value:.4f} | piso de ruido: {NOISE:.4f}\n")
router_plain = fit_theta(with_axis=False)
router_axis = fit_theta(with_axis=True)
for label, router, axis, aware in (
    ("1. P15 registrada (plan.paradigm)", router_plain, False, False),
    ("2. + eje de continuidad", router_axis, True, False),
    ("3. por ACCION real (cascada escala)", router_axis, True, True),
):
    v, per_cell = value(router, axis, aware)
    print(f"{label:38s} valor={v:.4f} neto={v - fixed_value:+.4f}")
    if aware:
        for cell in sorted(per_cell):
            pares = per_cell[cell]
            ur = sum(a for a, _ in pares) / len(pares)
            uf = sum(b for _, b in pares) / len(pares)
            print(f"    {cell}: ruteo={ur:.3f} fijo={uf:.3f} delta={ur - uf:+.3f}")
