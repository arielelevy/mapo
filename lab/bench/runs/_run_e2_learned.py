"""E2: theta contra un modelo aprendido trivial sobre las MISMAS features.

LA PREGUNTA QUE ESTO CIERRA. La capa de decision es aritmetica de factibilidad, creencias
tipadas, un dial, reglas y una politica firmada. Un revisor duro pregunta lo obvio: si a
una regresion de treinta parametros sobre el mismo phi le va igual, toda esa maquinaria
es decoracion cara. Es la pregunta mas barata de responder de todo el proyecto — cero
tokens, las filas ya estan pagadas — y la unica respuesta honesta es medirla.

EL BRAZO. Ridge por paradigma: predice utilidad desde phi (forma cerrada, deterministica,
sin iteraciones ni semilla), y rutea al argmax de utilidad predicha entre los candidatos
presentes en esa tarea. Ve EXACTAMENTE lo que ve theta — cardinalidad, oraculo,
irreversibilidad, escrituras compartidas, presupuesto, coupling, continuidad — porque si
gana viendo mas, no probo nada.

LA COMPARACION ES JUSTA EN LAS DOS DIRECCIONES:

  Mismo split que P15: entrena en deep + holdout + v2, decide sobre gold_transfer.
  Misma valuacion por accion: el ruteo de theta escala la cascada y respeta el gate.

  Y ahi hay una asimetria que se reporta en vez de taparse: el brazo aprendido predice
  UN paradigma y se lo puntua directo. No tiene cascada, ni gate, ni abstencion — no
  porque se lo prohiba este script, sino porque un regresor no tiene donde expresarlas.
  Esa es justamente la diferencia bajo estudio, asi que se mide en las dos formas: el
  brazo crudo (lo que el regresor produce) y el brazo envuelto (su eleccion metida en la
  misma maquinaria de accion). Si theta solo gana en la version envuelta, lo que gana no
  es el estimador: es el gobierno — y eso es exactamente lo que hay que poder decir.
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

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.features import measure_continuation
from app.metrics import Study
from app.paradigms import COST_PRIORS, FALLBACK
from app.policy import Plasticity, PolicyBundle
from app.router import Router
from app.runner import Runner

TRAIN = ("gold_deep", "gold_holdout", "gold_v2")
TEST = "gold_transfer"
RIDGE = 1.0

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")


def continuation_of(corpus):
    docs = json.load(open(f"corpus/{corpus}/documents.json"))
    tasks = json.load(open(f"corpus/{corpus}/tasks.json"))
    return {t["task_id"]: measure_continuation(docs, t["unit_ids"]) for t in tasks}


def segment(c):
    return "c?" if c is None else ("chain" if c else "flat")


def phi(task, continuation):
    """El vector que ve theta, como numeros. Nada mas."""
    units = task.get("unit_ids") or []
    return np.array([
        1.0,
        len(units),
        np.log1p(len(units)),
        1.0 if task.get("oracle") else 0.0,
        1.0 if task.get("irreversible") else 0.0,
        1.0 if task.get("shared_writes") else 0.0,
        np.log1p(int(task["budget_tokens"])),
        1.0 if continuation else 0.0,
        1.0 if continuation is None else 0.0,
    ])


# ---- datos ------------------------------------------------------------------------
train_rows = defaultdict(list)  # paradigm -> [(phi, utility)]
for corpus in TRAIN:
    runner = Runner(settings, corpus, retriever_arm="hybrid", surface_variant="basic")
    cont = continuation_of(corpus)
    tasks = {t["task_id"]: t for t in runner._tasks}  # noqa: SLF001
    cells = defaultdict(lambda: defaultdict(list))
    for row in runner.load_rows():
        cells[row["task_id"]][row["paradigm"]].append(row["utility"])
    for task_id, per_paradigm in cells.items():
        if task_id not in tasks:
            continue
        x = phi(tasks[task_id], cont.get(task_id))
        for paradigm, us in per_paradigm.items():
            train_rows[paradigm].append((x, sum(us) / len(us)))

weights = {}
for paradigm, samples in train_rows.items():
    if len(samples) < 4:
        continue
    X = np.vstack([x for x, _ in samples])
    y = np.array([u for _, u in samples])
    A = X.T @ X + RIDGE * np.eye(X.shape[1])
    weights[paradigm] = np.linalg.solve(A, X.T @ y)

n_params = sum(len(w) for w in weights.values())
print(f"brazo aprendido: ridge por paradigma, {len(weights)} paradigmas x "
      f"{len(next(iter(weights.values())))} features = {n_params} parametros")
print(f"entrenado en {sum(len(v) for v in train_rows.values())} celdas de {list(TRAIN)}\n")

# ---- theta, mismo registro, con el eje ---------------------------------------------
episodes = []
for corpus in TRAIN:
    runner = Runner(settings, corpus, retriever_arm="hybrid", surface_variant="basic")
    cont = continuation_of(corpus)
    for e in runner.episodes():
        episodes.append(replace(e, region=f"{e.region}/{segment(cont.get(e.task_id))}"))
theta = Plasticity.candidate(
    PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3), episodes, tau=0.3
)
router = Router(theta, COST_PRIORS, FALLBACK)

# ---- test --------------------------------------------------------------------------
target = Runner(settings, TEST, retriever_arm="hybrid", surface_variant="basic")
study = target.study()
cont_t = continuation_of(TEST)
rows_by_task = defaultdict(dict)
for row in target.load_rows():
    rows_by_task[row["task_id"]][row["paradigm"]] = row
tasks_by_id = {t["task_id"]: t for t in target._tasks}  # noqa: SLF001
cells = {t["task_id"]: t["cell"] for t in target._tasks}  # noqa: SLF001


def learned_choice(task_id):
    x = phi(tasks_by_id[task_id], cont_t.get(task_id))
    candidates = [p for p in sorted(rows_by_task[task_id]) if p in weights]
    if not candidates:
        return FALLBACK
    return max(candidates, key=lambda p: float(weights[p] @ x))


def theta_plan(task_id):
    region = next(iter(rows_by_task[task_id].values()))["region"]
    return router.plan(
        task=tasks_by_id[task_id],
        candidates=sorted(rows_by_task[task_id]),
        region=f"{region}/{segment(cont_t.get(task_id))}",
    )


def action_value(task_id, plan):
    """La misma valuacion por accion de la descomposicion de P15."""
    if plan.action == "cascade" and len(plan.ladder) > 1:
        for rung in plan.ladder:
            if study.quality(task_id, rung) >= 1.0:
                return study.quality(task_id, rung)
        return study.quality(task_id, plan.ladder[-1])
    paradigm = (
        FALLBACK if plan.gated or plan.action == "defer_to_fallback" else plan.paradigm
    )
    return study.quality(task_id, paradigm)


tasks = sorted(study.complete_tasks)
best_fixed = study.best_fixed()
fixed_value = study.mean_utility(best_fixed)

raw_learned = sum(study.quality(t, learned_choice(t)) for t in tasks) / len(tasks)
theta_action = sum(action_value(t, theta_plan(t)) for t in tasks) / len(tasks)
theta_raw = sum(study.quality(t, theta_plan(t).paradigm) for t in tasks) / len(tasks)

# el brazo aprendido ENVUELTO: su eleccion, dentro de la misma maquinaria
wrapped = 0.0
for t in tasks:
    plan = theta_plan(t)
    if plan.gated:
        wrapped += study.quality(t, FALLBACK)
    elif plan.action == "cascade" and len(plan.ladder) > 1:
        ladder = [learned_choice(t)] + [p for p in plan.ladder if p != learned_choice(t)]
        got = None
        for rung in ladder:
            if study.quality(t, rung) >= 1.0:
                got = study.quality(t, rung)
                break
        wrapped += got if got is not None else study.quality(t, ladder[-1])
    else:
        wrapped += study.quality(t, learned_choice(t))
wrapped /= len(tasks)

print(f"corpus de prueba: {TEST} | mejor fijo ({best_fixed}) = {fixed_value:.4f} "
      f"| piso de ruido 0.0573\n")
for label, value in (
    ("theta, plan.paradigm (como P15)", theta_raw),
    ("brazo aprendido, crudo", raw_learned),
    ("brazo aprendido, ENVUELTO en la maquinaria", wrapped),
    ("theta, por accion real", theta_action),
):
    print(f"  {label:44s} {value:.4f}  neto={value - fixed_value:+.4f}")

agree = sum(1 for t in tasks if learned_choice(t) == theta_plan(t).paradigm)
print(f"\ncoinciden en {agree}/{len(tasks)} tareas")
print("elecciones del brazo aprendido:",
      dict(sorted(defaultdict(int, {p: sum(1 for t in tasks if learned_choice(t) == p)
                                    for p in {learned_choice(t) for t in tasks}}).items())))

out = settings.results_dir / "e2_learned_arm.json"
out.write_text(json.dumps({
    "train": list(TRAIN), "test": TEST, "ridge": RIDGE, "parameters": n_params,
    "best_fixed": best_fixed, "best_fixed_value": round(fixed_value, 5),
    "theta_plan_paradigm": round(theta_raw, 5),
    "theta_action_aware": round(theta_action, 5),
    "learned_raw": round(raw_learned, 5),
    "learned_wrapped": round(wrapped, 5),
    "agreement": f"{agree}/{len(tasks)}",
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nreporte: {out}")
