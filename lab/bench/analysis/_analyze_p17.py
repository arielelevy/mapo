"""Veredicto de P17 — CONGELADO ANTES DE CORRER (commiteado 2026-08-27).

Preregistrar la prediccion en prosa deja margen para elegir la valuacion despues de ver
los numeros. Congelar el CODIGO que juzga no lo deja: este archivo entra a la historia
git antes de que exista una sola fila de gold_p17, y el veredicto es lo que imprima.

QUE CORRIGE RESPECTO DE P15 Y P16, Y POR QUE ESTA VEZ LA PREGUNTA SE PUEDE HACER

  El detector.  Hasta ahora `has_oracle` se derivaba de `bool(task["oracle"])`, o sea del
                GOLD. Toda tarea corregible tenia detector — 25 de 26 en cada corpus — y
                con detector en todas, la cascada dispara en prioridad 90 y la seleccion,
                en 70, NO SE EVALUA NUNCA. El banco no podia medir seleccion porque ser
                corregible implicaba tener detector. En gold_p17 el detector se declara
                por celda segun si verificar es mas barato que resolver, y medido: la
                cascada cae de 22 a 2 de 26.

  Los dos pasos. `probe_then_decide` nombra DOS pasos y el banco daba uno: puntuaba el
                placeholder —el paradigma mas barato, elegido para probar DESPUES de
                sondear— como si fuera una decision. Aca el ciclo se corre entero
                (`app.decide.decide`), la sonda se ejecuta, el plan se re-deriva, y LO QUE
                CUESTA DECIDIR SE COBRA.

  Las regiones. Las que cada fila trae grabadas se computaron con el vocabulario de
                entonces (tres segmentos) y la regla de entonces. Se re-derivan
                conservando el acoplamiento MEDIDO, que es lo unico de esa etiqueta que
                costo una medicion.

  EL COSTO, DESDE EL NACIMIENTO. P16c midio que el ruteo captura +0,1211 sin cobrar nada
                y ya esta adentro del ruido en lambda=0,02. Asi que el barrido de lambda
                no es un chequeo posterior de robustez: es parte del veredicto, y esta
                escrito aca antes de ver un numero.

LAS PREDICCIONES, TAL COMO QUEDARON REGISTRADAS

  P17a  La cascada dispara en <= 6 de 26.               (ya CONFIRMADA offline: 2 de 26)
  P17b  La regla de seleccion DECIDE en >= 7 de las 14 tareas que esperan la sonda.
        Hoy decide en 0 de 26, y viene decidiendo en 0 toda la investigacion.
  P17c  La brecha de oraculo NETA de la accion ruteada contra el mejor fijo es positiva
        y afuera del piso de ruido por celda. Es el re-test de lo que P15a fallo.
  P17d  Utilidad de replica identica en 26/26.

LOS DOS COHORTES, SEPARADOS ANTES DE VER NADA. Igual que P16: las C7 son irreversibles y
el gate corre el fallback POR DISENO, asi que su deficit es el precio del gobierno y no
un error de ruteo. Se reportan aparte y ninguno se esconde detras del otro.
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

from _regions import continuation_segment, rederived_episodes
from app.config import Settings
from app.decide import decide
from app.llm import SeededClient
from app.features import Features, has_runtime_detector
from app.metrics import Study
from app.paradigms import COST_PRIORS, FALLBACK
from app.policy import Plasticity, PolicyBundle
from app.router import Router
from app.runner import Runner

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")

CORPUS = "gold_p17"
TRAIN = ("gold_deep", "gold_holdout", "gold_v2", "gold_transfer")
LAMBDA_PRIMARY = 0.05
LAMBDA_SWEEP = (0.0, 0.02, 0.05, 0.1, 0.2, 0.4)
TAU = 0.3

# --- theta, sobre regiones re-derivadas ----------------------------------------------
episodes = []
for corpus in TRAIN:
    runner = Runner(settings, corpus, retriever_arm="hybrid", surface_variant="basic")
    episodes += rederived_episodes(runner, corpus)

theta = Plasticity.candidate(
    PolicyBundle.cold_start(fallback=FALLBACK, tau=TAU), episodes, tau=TAU
)
router = Router(theta, COST_PRIORS, FALLBACK)

target = Runner(settings, CORPUS, retriever_arm="hybrid", surface_variant="basic")
rows_by_task: dict[str, dict] = {}
for row in target.load_rows():
    rows_by_task.setdefault(row["task_id"], {})[row["paradigm"]] = row
tasks_by_id = {t["task_id"]: t for t in target._tasks}  # noqa: SLF001
cells = {t["task_id"]: t["cell"] for t in target._tasks}  # noqa: SLF001
documents = json.load(open(f"corpus/{CORPUS}/documents.json", encoding="utf-8"))

print(f"corpus: {CORPUS} (seed 73, nunca visto por theta)")
print(f"theta: {len(episodes)} episodios re-derivados de {', '.join(TRAIN)}")

# --- la decision, con los DOS pasos ---------------------------------------------------
# FALLA RUIDOSA, a proposito. Si no se puede construir el cliente, la sonda no corre,
# P17b mide cero `specialise` y quedaria REFUTADA por la razon equivocada — el peor
# modo de falla posible para un veredicto congelado. Antes que eso, romper.
client = SeededClient(target._client, settings.seed)  # noqa: SLF001
decisions: dict[str, object] = {}
probe_tokens = 0


def decision_for(task_id: str):
    global probe_tokens
    if task_id not in decisions:
        task = tasks_by_id[task_id]
        features = Features(
            n_units=len(task["unit_ids"]),
            has_oracle=has_runtime_detector(task),
            irreversible=bool(task.get("irreversible", False)),
            shared_writes=bool(task.get("shared_writes", False)),
            budget_tokens=int(task["budget_tokens"]),
        )
        d = decide(
            task,
            router=router,
            features=features,
            candidates=sorted(rows_by_task[task_id]),
            documents=documents,
            client=client,
            surface=target.surface_for(task),
            probe=True,
        )
        probe_tokens += d.usage.total_tokens
        decisions[task_id] = d
    return decisions[task_id]


def action_outcome(study: Study, task_id: str) -> tuple[float, int, str]:
    """(calidad obtenida, tokens gastados, accion) de lo que el producto HARIA."""
    d = decision_for(task_id)
    plan = d.plan
    row = rows_by_task[task_id]
    deciding = d.usage.total_tokens

    def cost_of(paradigm: str) -> int:
        return int(row[paradigm]["cost_tokens"]) if paradigm in row else 0

    if plan.action == "cascade" and len(plan.ladder) > 1:
        spent = deciding
        for rung in plan.ladder:
            spent += cost_of(rung)
            if study.quality(task_id, rung) >= 1.0:
                return study.quality(task_id, rung), spent, plan.action
        return study.quality(task_id, plan.ladder[-1]), spent, plan.action

    if d.unresolved:
        # La sonda pidio evidencia que nadie produjo. Ejecutar el placeholder seria
        # actuar sobre evidencia que el gate acaba de declarar insuficiente.
        return study.quality(task_id, FALLBACK), deciding + cost_of(FALLBACK), "deferred_unresolved"

    paradigm = FALLBACK if plan.gated or plan.action == "defer_to_fallback" else plan.paradigm
    return study.quality(task_id, paradigm), deciding + cost_of(paradigm), plan.action


def net_utility(study: Study, task_id: str, quality: float, spent: int, lam: float) -> float:
    if lam == 0.0:
        return quality
    floor = study._min_cost[task_id]  # noqa: SLF001
    ratio = (spent / floor) if floor > 0 and spent > 0 else 1.0
    return quality - lam * (ratio - 1.0)


def evaluate(lam: float, task_ids: list[str]) -> dict:
    study = Study(
        [o for o in target.study()._obs if o.task_id in set(task_ids)],  # noqa: SLF001
        lambda_cost=lam,
    )
    router_total, per_cell, actions = 0.0, defaultdict(list), defaultdict(int)
    for task_id in task_ids:
        quality, spent, action = action_outcome(study, task_id)
        value = net_utility(study, task_id, quality, spent, lam)
        router_total += value
        per_cell[cells[task_id][:2]].append(value)
        actions[action] += 1
    best_fixed = study.best_fixed()
    fixed_total = sum(study.quality(t, best_fixed) for t in task_ids)
    react_total = sum(study.quality(t, FALLBACK) for t in task_ids)
    n = len(task_ids)
    return {
        "lambda": lam, "n": n,
        "router": round(router_total / n, 4),
        "best_fixed": best_fixed,
        "best_fixed_utility": round(fixed_total / n, 4),
        "react_utility": round(react_total / n, 4),
        "net_vs_best_fixed": round((router_total - fixed_total) / n, 4),
        "net_vs_react": round((router_total - react_total) / n, 4),
        "actions": dict(actions),
        "per_cell": {c: round(sum(v) / len(v), 4) for c, v in sorted(per_cell.items())},
    }


full_study = target.study()
all_tasks = sorted(full_study.complete_tasks)
gated = [t for t in all_tasks if tasks_by_id[t].get("irreversible")]
routing = [t for t in all_tasks if t not in set(gated)]
# Piso de ruido por replicas, igual que P16: la variabilidad entre corridas de la MISMA
# celda es la unica escala contra la cual una diferencia significa algo.
reps: dict[tuple[str, str], list[float]] = defaultdict(list)
for r in target.load_rows():
    if r.get("infra_error") or r.get("infeasible"):
        continue
    reps[(r["task_id"], r["paradigm"])].append(r["utility"])
floor_info = Study.noise_floor({f"{t}|{p}": u for (t, p), u in reps.items()})
noise = float(floor_info["noise_oracle_gap"])
print(f"tareas: {len(all_tasks)} | cohorte de ruteo: {len(routing)} | gateadas: {len(gated)}")

# --- P17a ------------------------------------------------------------------------------
primary = evaluate(LAMBDA_PRIMARY, routing)
cascades = sum(1 for t in all_tasks if decision_for(t).plan.action == "cascade")
print(f"\n--- P17a: cuantas cascadas ---")
print(f"  cascada dispara en {cascades}/{len(all_tasks)}")
print(f"  P17a: {'CONFIRMADA' if cascades <= 6 else 'REFUTADA'} (criterio <= 6)")

# --- P17b ------------------------------------------------------------------------------
probed = [t for t in all_tasks if decision_for(t).probed]
specialised = [t for t in all_tasks if decision_for(t).plan.action == "specialise"]
unresolved = [t for t in all_tasks if decision_for(t).unresolved]
print(f"\n--- P17b: LA SELECCION, ¿decide? ---")
print(f"  tareas sondeadas          : {len(probed)}")
print(f"  vuelven specialise        : {len(specialised)}")
print(f"  quedan sin resolver       : {len(unresolved)}")
print(f"  costo de decidir          : {probe_tokens:,} tokens")
print(f"  P17b: {'CONFIRMADA' if len(specialised) >= 7 else 'REFUTADA'} (criterio >= 7)")

# --- P17c ------------------------------------------------------------------------------
print(f"\n--- P17c: brecha NETA sobre el cohorte de ruteo, lambda={LAMBDA_PRIMARY} ---")
print(f"  ruteo={primary['router']} | mejor fijo ({primary['best_fixed']})="
      f"{primary['best_fixed_utility']} | siempre-react={primary['react_utility']}")
print(f"  neto vs mejor fijo: {primary['net_vs_best_fixed']:+.4f}")
print(f"  neto vs siempre-react: {primary['net_vs_react']:+.4f}")
print(f"  acciones: {primary['actions']}")
print(f"  por celda: {primary['per_cell']}")
if noise is not None:
    verdict = "CONFIRMADA" if primary["net_vs_best_fixed"] > noise else "REFUTADA"
    print(f"  piso de ruido: {noise:.5f}")
else:
    verdict = "CONFIRMADA" if primary["net_vs_best_fixed"] > 0 else "REFUTADA"
print(f"  P17c: {verdict}")

# --- barrido de lambda, parte del veredicto y no un extra -----------------------------
print(f"\n--- P17c-sweep: el barrido, escrito antes de ver nada ---")
sweep = []
for lam in LAMBDA_SWEEP:
    r = evaluate(lam, routing)
    sweep.append(r)
    print(f"  lambda={lam:<5} neto={r['net_vs_best_fixed']:+.4f} "
          f"(vs react {r['net_vs_react']:+.4f})")

# --- precio del gate --------------------------------------------------------------------
if gated:
    g = evaluate(LAMBDA_PRIMARY, gated)
    print(f"\n--- P17: PRECIO DEL GATE (cohorte irreversible) ---")
    print(f"  gateado={g['router']} vs mejor fijo={g['best_fixed_utility']} | "
          f"precio: {g['net_vs_best_fixed']:+.4f}")
else:
    g = None

# --- P17d -------------------------------------------------------------------------------
same = 0
for task_id in all_tasks:
    first = decisions[task_id]
    decisions.pop(task_id)
    again = decision_for(task_id)
    if (again.plan.paradigm == first.plan.paradigm
            and again.plan.action == first.plan.action):
        same += 1
    decisions[task_id] = first
print(f"\n--- P17d: reproducibilidad ---")
print(f"  re-decision identica: {same}/{len(all_tasks)}")
print(f"  P17d: {'CONFIRMADA' if same == len(all_tasks) else 'REFUTADA'}")

out = settings.results_dir / "p17_verdict.json"
out.write_text(json.dumps({
    "corpus": CORPUS, "train_corpora": list(TRAIN), "cell_episodes": len(episodes),
    "lambda_primary": LAMBDA_PRIMARY, "noise_floor": floor_info,
    "p17a": {"cascades": cascades, "of": len(all_tasks),
             "verdict": "CONFIRMADA" if cascades <= 6 else "REFUTADA"},
    "p17b": {"probed": len(probed), "specialised": len(specialised),
             "unresolved": len(unresolved), "deciding_tokens": probe_tokens,
             "verdict": "CONFIRMADA" if len(specialised) >= 7 else "REFUTADA"},
    "p17c": {**primary, "verdict": verdict},
    "sweep": sweep,
    "gate_price": g,
    "p17d": {"identical": same, "of": len(all_tasks),
             "verdict": "CONFIRMADA" if same == len(all_tasks) else "REFUTADA"},
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nveredicto: {out}")
