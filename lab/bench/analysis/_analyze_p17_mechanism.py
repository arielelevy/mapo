"""P17a: que regla decide, con detectores honestos. Cero tokens.

Se puede contestar OFFLINE porque la pregunta no es sobre calidad sino sobre cual regla
llega primero, y eso lo fija la prioridad y los features — no el modelo. Correrlo antes
de gastar es el punto: si el corpus no cambia que regla dispara, la corrida no mide lo
que P17 dice medir y no vale la pena pagarla.

El prerrequisito (`features.py` leyendo `has_oracle` declarado en vez de `bool(oracle)`)
NO esta aplicado todavia: P16 esta a mitad de corrida con su analizador congelado. Aca se
simula con un override local, que es exactamente lo que la linea hara — asi el numero se
puede verificar hoy sin tocar lo que P16 tiene fijado.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import sys
from collections import Counter
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.features import Features, measure_continuation
from app.paradigms import COST_PRIORS, FALLBACK
from app.policy import Plasticity, PolicyBundle
from app.router import Router
from app.runner import Runner

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")


def continuation_of(corpus):
    docs = json.load(open(f"corpus/{corpus}/documents.json", encoding="utf-8"))
    tasks = json.load(open(f"corpus/{corpus}/tasks.json", encoding="utf-8"))
    return {t["task_id"]: measure_continuation(docs, t["unit_ids"]) for t in tasks}


def segment(c):
    return "c?" if c is None else ("chain" if c else "flat")


# theta, ajustado sobre el registro existente
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

CANDIDATES = ["react", "dag_strategy", "map_reduce", "rewoo", "gist_reader"]


def rules_on(corpus, honest):
    """Que regla decide cada tarea, con o sin el prerrequisito aplicado."""
    tasks = json.load(open(f"corpus/{corpus}/tasks.json", encoding="utf-8"))
    docs = json.load(open(f"corpus/{corpus}/documents.json", encoding="utf-8"))
    cont = continuation_of(corpus)

    fired, unresolved = Counter(), 0
    for task in tasks:
        # El prerrequisito toca DOS lugares, no uno: features.py:214 (el segmento de
        # region) y rules.py:248 (la creencia `oracle_available`, que es la que la
        # cascada lee). Los dos derivan de `bool(task["oracle"])`, asi que vaciar el
        # oraculo donde no hay detector declarado los simula a ambos exactamente.
        # El gold NO se toca: la correccion vive en runner.py y no pasa por aca.
        seen = dict(task)
        if honest and not task["has_oracle"]:
            seen["oracle"] = []

        features = Features(
            n_units=len(task["unit_ids"]),
            has_oracle=bool(seen["oracle"]),
            irreversible=bool(task.get("irreversible", False)),
            shared_writes=bool(task.get("shared_writes", False)),
            budget_tokens=int(task["budget_tokens"]),
        )
        region = f"{features.region()}/{segment(cont.get(task['task_id']))}"
        plan = router.plan(
            task={**seen, "units": task["unit_ids"]},
            candidates=CANDIDATES,
            region=region,
            documents=docs,
        )
        fired[plan.action] += 1
        if plan.needs_probe:
            unresolved += 1
    return fired, unresolved, len(tasks)


print("P17a — que regla decide, por corpus y por regimen\n")
for corpus in ("gold_p16", "gold_p17"):
    for honest in (False, True):
        label = "honesto" if honest else "como P16 lo corre"
        fired, unresolved, n = rules_on(corpus, honest)
        actions = ", ".join(f"{a}={c}" for a, c in sorted(fired.items()))
        print(f"  {corpus:10s} {label:18s} n={n}  {actions}")
        print(f"  {'':10s} {'':18s} sin resolver (esperan sonda): {unresolved}")
    print()

print("P17a se cumple si la cascada dispara en <= 6 de 26 sobre gold_p17 honesto.")
