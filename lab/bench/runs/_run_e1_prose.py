"""E1: el router en prosa, medido — la premisa del producto deja de ser una creencia.

Todo el proyecto se apoya en que rutear con reglas escritas en prosa, evaluadas por un
modelo, es fragil; y en que una capa de decision deterministica lo reemplaza. Nadie
midio nunca lo que se reemplaza. Esto lo mide.

Sobre FILAS YA PAGADAS: no corre ningun paradigma. Las utilidades y los costos de cada
(tarea, paradigma) ya estan en el registro; lo unico que cambia entre brazos es QUIEN
elige. Cuesta una llamada mini por tarea y por brazo, nada mas.

Tres brazos, sobre las mismas tareas y el mismo oraculo:

  Pi(phi, theta)  la capa deterministica: aritmetica + estadistica aprendida, cero
                  llamadas al modelo para decidir
  prose naive     el clasificador como corria en produccion: la pregunta y cuantos
                  documentos hay
  prose informed  el router en prosa MAS FUERTE que se puede construir: ve exactamente
                  lo que ve phi (unidades, tamano del contenido, presupuesto, si hay
                  detector barato), en prosa

La distincion entre los dos ultimos es la que decide que dice el paper. Ganarle al
naive vale poco: es un router que no ve los numeros. Ganarle al informed es la
afirmacion, porque ahi la unica diferencia es COMO se decide, no con que informacion.

Y el costo de rutear se reporta aparte, nunca sumado a la utilidad: la capa
deterministica decide gratis y el router en prosa paga una llamada por request. Es una
ventaja real y merece su propio numero, no disolverse dentro de otro.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import os
import sys
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.baselines import ProseRouter
from app.config import Settings
from app.llm import LLMClient
from app.paradigms import COST_PRIORS, FALLBACK
from app.policy import Plasticity, PolicyBundle
from app.router import Router
from app.runner import Runner

CORPUS = sys.argv[1] if len(sys.argv) > 1 else "gold_transfer"

base = Settings.from_env()
settings = replace(
    base,
    endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
    api_key=os.environ["MAPO_NANO_KEY"],
    chat_deployment="gpt-5.4-nano",
    temperature=0.0,
    results_dir=base.results_dir / "nano",
)
print(f"modelo: {settings.fingerprint()}", flush=True)
print(f"corpus: {CORPUS}\n", flush=True)

runner = Runner(settings, CORPUS, retriever_arm="hybrid", surface_variant="basic")
study = runner.study()
episodes = runner.episodes()

# theta ajustada sobre el registro, igual que en report()
cold = PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3)
theta = Plasticity.candidate(cold, episodes, tau=0.3, notes="E1 baseline comparison")
router = Router(theta, COST_PRIORS, FALLBACK)

rows_by_task: dict[str, dict] = {}
for row in runner.load_rows():
    rows_by_task.setdefault(row["task_id"], {})[row["paradigm"]] = row


def task_of(task_id: str) -> dict:
    return next(t for t in runner._tasks if t["task_id"] == task_id)  # noqa: SLF001


def region_of(task_id: str) -> str:
    return next(iter(rows_by_task[task_id].values()))["region"]


def theta_decide(task_id: str) -> str:
    return router.plan(
        task=task_of(task_id),
        candidates=sorted(rows_by_task[task_id]),
        region=region_of(task_id),
    ).paradigm


candidates = sorted({p for row in rows_by_task.values() for p in row})
client = LLMClient(settings)
tasks = [task_of(t) for t in study.complete_tasks]

arms: dict[str, object] = {}
for variant in ("naive", "informed"):
    arms[variant] = ProseRouter(
        client,
        tasks,
        runner._documents,  # noqa: SLF001
        candidates,
        fallback=FALLBACK,
        variant=variant,
    )

print(f"tareas completas: {len(study.complete_tasks)} | candidatos: {candidates}")
print(f"mejor fijo: {study.best_fixed()} | oraculo: {study.oracle_value():.4f} "
      f"| brecha de oraculo: {study.oracle_gap():.4f}\n", flush=True)

report: dict = {
    "corpus": CORPUS,
    "model": settings.fingerprint(),
    "tasks": len(study.complete_tasks),
    "candidates": candidates,
    "best_fixed": study.best_fixed(),
    "oracle_value": round(study.oracle_value(), 5),
    "oracle_gap": round(study.oracle_gap(), 5),
    "arms": {},
}

for name, decide in (
    ("theta", theta_decide),
    ("prose_naive", arms["naive"].decide),
    ("prose_informed", arms["informed"].decide),
):
    terms = study.selection_terms(decide)
    value = study.router_value(decide)
    captured = study.captured_fraction(decide)
    entry = {
        "router_value": round(value, 5),
        "net_vs_best_fixed": round(value - study.mean_utility(study.best_fixed()), 5),
        "captured_fraction_of_gap": round(captured, 5),
        "terms": terms.as_dict() if hasattr(terms, "as_dict") else str(terms),
        "routing_calls": 0,
        "routing_tokens": 0,
        "invalid_choices": 0,
    }
    if name != "theta":
        arm = arms["naive" if name == "prose_naive" else "informed"]
        entry["routing_calls"] = arm.usage.calls
        entry["routing_tokens"] = arm.usage.total_tokens
        entry["invalid_choices"] = arm.invalid_choices
        entry["choices"] = {
            t: d.paradigm for t, d in sorted(arm.decisions.items())
        }
    else:
        entry["choices"] = {t: theta_decide(t) for t in study.complete_tasks}
    report["arms"][name] = entry

    print(f"{name:16s} valor={entry['router_value']:.4f} "
          f"neto vs mejor fijo={entry['net_vs_best_fixed']:+.4f} "
          f"captura={entry['captured_fraction_of_gap']:+.3f} "
          f"| rutear costo {entry['routing_tokens']:,} tok en "
          f"{entry['routing_calls']} llamadas"
          + (f" | {entry['invalid_choices']} elecciones invalidas"
             if entry["invalid_choices"] else ""),
          flush=True)

# En que tareas discrepan: es lo que hay que mirar a mano despues
theta_choice = report["arms"]["theta"]["choices"]
informed_choice = report["arms"]["prose_informed"]["choices"]
disagreements = [
    {
        "task_id": t,
        "theta": theta_choice[t],
        "prose": informed_choice.get(t, ""),
        "utility_theta": round(study.utility(t, theta_choice[t]), 3),
        "utility_prose": round(
            study.utility(t, informed_choice.get(t, study.best_fixed())), 3
        ),
    }
    for t in study.complete_tasks
    if theta_choice[t] != informed_choice.get(t)
]
report["disagreements"] = disagreements
print(f"\ndiscrepancias theta vs prose_informed: {len(disagreements)}/"
      f"{len(study.complete_tasks)} tareas")
for d in disagreements[:10]:
    print(f"  {d['task_id']:16s} theta={d['theta']:14s} u={d['utility_theta']:.3f} | "
          f"prosa={d['prose']:14s} u={d['utility_prose']:.3f}")

out = settings.results_dir / f"e1_prose_{CORPUS}.json"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nreporte: {out}")
