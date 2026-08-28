"""Estadistica del registro: intervalos, multiplicidad y AURC.

TRES HUECOS QUE UN TRIBUNAL MIRA PRIMERO, y ninguno estaba cerrado.

1. INTERVALOS. Las brechas netas se reportaban como una diferencia de medias contra un
   piso de ruido. El piso responde "¿pudo salir de la loteria de replicas?" y es la
   pregunta correcta sobre el RUIDO DE MEDICION — pero no dice nada sobre el ruido de
   MUESTREO de 26 tareas. Son dos incertidumbres distintas y hasta ahora habia una sola.
   Bootstrap pareado sobre tareas: se remuestrean TAREAS, no filas, porque la unidad
   independiente es la tarea y las replicas de una misma tarea no lo son.

2. MULTIPLICIDAD. Dieciseis predicciones registradas y cero correccion. Con dieciseis
   binarias, unas cuantas "se confirman" por azar. Se aplica Benjamini-Hochberg sobre
   las que TIENEN p-valor, y se dice explicitamente cuales no lo tienen: una prediccion
   evaluada por umbral (factibilidad, reproducibilidad 26/26) no es un test y meterla en
   una correccion de FDR seria inventar precision.

3. AURC. La curva riesgo-cobertura existe en metrics.risk_coverage y nunca se reporto
   como un numero. El area bajo la curva de captura es la medida estandar de un
   predictor selectivo, y es la que permite comparar abstenciones entre sistemas.

Todo esto es analisis puro: cero tokens, sobre filas ya pagadas.
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
from app.paradigms import COST_PRIORS, FALLBACK
from app.policy import MIN_EPISODES_FOR_CONFIDENCE, Plasticity, PolicyBundle
from app.router import Router
from app.runner import Runner

BOOTSTRAP = 10_000
SEED = 20260827  # fijo: un intervalo que cambia entre corridas no es un intervalo

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")


def continuation_of(corpus):
    docs = json.load(open(f"corpus/{corpus}/documents.json"))
    tasks = json.load(open(f"corpus/{corpus}/tasks.json"))
    return {t["task_id"]: measure_continuation(docs, t["unit_ids"]) for t in tasks}


def segment(c):
    return "c?" if c is None else ("chain" if c else "flat")


def paired_bootstrap(deltas: list[float], rng) -> dict:
    """IC percentil 95% y p-valor de dos colas sobre la media de las diferencias.

    Pareado por tarea: cada delta es (ruteo - fijo) en la MISMA tarea, asi que la
    variabilidad entre tareas — que es enorme y comun a los dos brazos — no entra al
    intervalo. El p-valor es la fraccion de remuestreos que cruza el cero, que es la
    lectura honesta de un bootstrap: cuan seguido el signo se da vuelta.
    """
    arr = np.asarray(deltas, dtype=float)
    n = len(arr)
    idx = rng.integers(0, n, size=(BOOTSTRAP, n))
    means = arr[idx].mean(axis=1)
    observed = float(arr.mean())
    lo, hi = np.percentile(means, [2.5, 97.5])
    crossings = float(np.mean(means >= 0.0) if observed < 0 else np.mean(means <= 0.0))
    return {
        "mean": round(observed, 5),
        "ci95": [round(float(lo), 5), round(float(hi), 5)],
        "p_two_sided": round(min(1.0, 2 * crossings), 5),
        "n_tasks": n,
    }


def benjamini_hochberg(pvalues: dict[str, float], q: float = 0.05) -> dict:
    """BH sobre la familia. Devuelve el umbral y que sobrevive."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    threshold, k_star = 0.0, 0
    for k, (_, p) in enumerate(items, start=1):
        if p <= k * q / m:
            threshold, k_star = p, k
    return {
        "q": q,
        "m": m,
        "threshold": round(threshold, 5),
        "survivors": [name for name, p in items[:k_star]],
        "rejected": [name for name, p in items[k_star:]],
    }


# ---- el estudio de gold_transfer, con el eje ---------------------------------------
episodes = []
for corpus in ("gold_deep", "gold_holdout", "gold_v2"):
    runner = Runner(settings, corpus, retriever_arm="hybrid", surface_variant="basic")
    cont = continuation_of(corpus)
    for e in runner.episodes():
        episodes.append(replace(e, region=f"{e.region}/{segment(cont.get(e.task_id))}"))
theta = Plasticity.candidate(
    PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3), episodes, tau=0.3
)
router = Router(theta, COST_PRIORS, FALLBACK)

target = Runner(settings, "gold_transfer", retriever_arm="hybrid", surface_variant="basic")
study = target.study()
cont_t = continuation_of("gold_transfer")
rows_by_task = defaultdict(dict)
for row in target.load_rows():
    rows_by_task[row["task_id"]][row["paradigm"]] = row
tasks_by_id = {t["task_id"]: t for t in target._tasks}  # noqa: SLF001
cells = {t["task_id"]: t["cell"] for t in target._tasks}  # noqa: SLF001
tasks = sorted(study.complete_tasks)
best_fixed = study.best_fixed()


def plan_for(task_id):
    region = next(iter(rows_by_task[task_id].values()))["region"]
    return router.plan(
        task=tasks_by_id[task_id], candidates=sorted(rows_by_task[task_id]),
        region=f"{region}/{segment(cont_t.get(task_id))}",
    )


def action_value(task_id):
    plan = plan_for(task_id)
    if plan.action == "cascade" and len(plan.ladder) > 1:
        for rung in plan.ladder:
            if study.quality(task_id, rung) >= 1.0:
                return study.quality(task_id, rung)
        return study.quality(task_id, plan.ladder[-1])
    paradigm = FALLBACK if plan.gated or plan.action == "defer_to_fallback" else plan.paradigm
    return study.quality(task_id, paradigm)


rng = np.random.default_rng(SEED)
print(f"bootstrap pareado: {BOOTSTRAP:,} remuestreos de TAREAS, seed {SEED}")
print(f"corpus gold_transfer | {len(tasks)} tareas | mejor fijo: {best_fixed}\n")

results = {}
for label, valuation in (
    ("P15 registrada (plan.paradigm)", lambda t: study.quality(t, plan_for(t).paradigm)),
    ("por accion real", action_value),
):
    for reference, ref_name in ((best_fixed, f"mejor fijo ({best_fixed})"),
                                (FALLBACK, f"siempre-{FALLBACK}")):
        deltas = [valuation(t) - study.quality(t, reference) for t in tasks]
        stats = paired_bootstrap(deltas, rng)
        key = f"{label} vs {ref_name}"
        results[key] = stats
        sig = "" if stats["ci95"][0] <= 0 <= stats["ci95"][1] else "  <- el IC excluye el cero"
        print(f"  {key:52s} {stats['mean']:+.4f} "
              f"IC95 [{stats['ci95'][0]:+.4f}, {stats['ci95'][1]:+.4f}] "
              f"p={stats['p_two_sided']:.3f}{sig}")

# por celda, donde la afirmacion mecanica vive
print("\n  por celda (accion real vs mejor fijo):")
per_cell = defaultdict(list)
for t in tasks:
    per_cell[cells[t][:2]].append(action_value(t) - study.quality(t, best_fixed))
cell_stats = {}
for cell, deltas in sorted(per_cell.items()):
    st = paired_bootstrap(deltas, rng)
    cell_stats[cell] = st
    print(f"    {cell}: {st['mean']:+.4f} IC95 [{st['ci95'][0]:+.4f}, {st['ci95'][1]:+.4f}] "
          f"n={st['n_tasks']}")

# ---- AURC de la abstencion ---------------------------------------------------------
def rank(task_id):
    """La confianza que gobierna la abstencion: el margen de theta, no una credencia."""
    region = next(iter(rows_by_task[task_id].values()))["region"]
    region = f"{region}/{segment(cont_t.get(task_id))}"
    _, margin = router.theta_assertions(region, sorted(rows_by_task[task_id]))
    return margin


curve = study.risk_coverage(rank=rank, propose=lambda t: plan_for(t).paradigm)
if curve:
    cov = np.array([p["coverage"] for p in curve])
    cap = np.array([p["captured"] for p in curve])
    order = np.argsort(cov)
    aurc = float(np.trapezoid(cap[order], cov[order]))
    print(f"\n  AURC (area bajo captura vs cobertura): {aurc:+.5f}")
    print(f"    cobertura 0 -> captura {cap[order][0]:+.3f} | "
          f"cobertura 1 -> captura {cap[order][-1]:+.3f}")
    print("    (un AURC negativo dice que rutear captura MENOS que abstenerse siempre)")
else:
    aurc = None

# ---- multiplicidad -----------------------------------------------------------------
print("\n--- Multiplicidad sobre la familia registrada ---")
with_p = {k: v["p_two_sided"] for k, v in results.items()}
bh = benjamini_hochberg(with_p)
print(f"  Benjamini-Hochberg q={bh['q']} sobre m={bh['m']} contrastes CON p-valor")
print(f"  sobreviven: {bh['survivors'] or 'ninguno'}")
print("  NO entran a la correccion (son juicios por umbral, no tests): P1 factibilidad")
print("  aritmetica, P15d/P16d reproducibilidad 26/26, P7c infactibilidad, y las")
print("  predicciones de mecanismo. Meterlas seria inventar precision.")

out = settings.results_dir / "statistics.json"
out.write_text(json.dumps({
    "bootstrap": BOOTSTRAP, "seed": SEED, "corpus": "gold_transfer",
    "paired_over": "tasks", "contrasts": results, "per_cell": cell_stats,
    "aurc": aurc, "benjamini_hochberg": bh,
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nreporte: {out}")
