"""¿Theta tiene estadisticas donde gold_p17 va a caer? Cero tokens.

POR QUE ESTO VA ANTES DE CORRER P17. El riesgo registrado de P17b es que theta se ajusta
sobre corpus cuyas regiones se computaron con la regla vieja, asi que el segmento
`oracle`/`no_oracle` significa una cosa en el entrenamiento y otra en la decision. Si
theta no tiene episodios en las regiones donde gold_p17 aterriza, el margen va a ser 0
por FALTA DE DATOS y no por falta de senal — y una corrida de ~14M tokens habria medido
"abstencion por no tener estadisticas", que ya sabemos de antemano.

Es exactamente la misma disciplina que hizo confirmable a P17a sin gastar: la pregunta no
depende del modelo, depende de que region toca cada tarea y de cuantos episodios hay ahi.

DECIDE UNA COSA CONCRETA: correr P17 ya, o reconstruir antes los corpus de entrenamiento
bajo la regla honesta.
"""

import json
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.features import Features, has_runtime_detector, measure_continuation
from _regions import continuation_segment, rederived_episodes
from app.paradigms import COST_PRIORS, FALLBACK
from app.policy import MIN_EPISODES_FOR_CONFIDENCE, Plasticity, PolicyBundle
from app.runner import Runner

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")

TRAIN = ("gold_deep", "gold_holdout", "gold_v2", "gold_transfer")
TARGET = "gold_p17"
CANDIDATES = ["react", "dag_strategy", "map_reduce", "rewoo", "gist_reader"]


def continuation_of(corpus):
    docs = json.load(open(f"corpus/{corpus}/documents.json", encoding="utf-8"))
    tasks = json.load(open(f"corpus/{corpus}/tasks.json", encoding="utf-8"))
    return {t["task_id"]: measure_continuation(docs, t["unit_ids"]) for t in tasks}


def segment(c):
    return "c?" if c is None else ("chain" if c else "flat")


# --- theta, tal como P17 la usaria --------------------------------------------------
# Re-derivadas: la region grabada en la fila usa el vocabulario y la regla de cuando la
# fila se escribio. Se conserva el acoplamiento MEDIDO y se corrige el resto.
episodes = []
for corpus in TRAIN:
    runner = Runner(settings, corpus, retriever_arm="hybrid", surface_variant="basic")
    episodes += rederived_episodes(runner, corpus)

theta = Plasticity.candidate(
    PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3), episodes, tau=0.3
)
print(f"theta: {len(episodes)} episodios de {', '.join(TRAIN)}\n")

train_regions = defaultdict(int)
for e in episodes:
    train_regions[e.region] += 1

print("regiones del ENTRENAMIENTO (por segmento de oraculo):")
by_seg = defaultdict(int)
for region, n in train_regions.items():
    by_seg[region.split("/")[1]] += n
for seg, n in sorted(by_seg.items(), key=lambda kv: -kv[1]):
    print(f"  {seg:<12} {n:>4} episodios")

# --- donde aterriza gold_p17 --------------------------------------------------------
tasks = json.load(open(f"corpus/{TARGET}/tasks.json", encoding="utf-8"))
cont_t = continuation_of(TARGET)

print(f"\ndonde aterriza {TARGET} con la regla honesta:\n")
print(f"  {'tarea':<16}{'region':<40}{'episodios':>10}{'confiable':>11}")

landed = []
for task in tasks:
    features = Features(
        n_units=len(task["unit_ids"]),
        has_oracle=has_runtime_detector(task),
        irreversible=bool(task.get("irreversible", False)),
        shared_writes=bool(task.get("shared_writes", False)),
        budget_tokens=int(task["budget_tokens"]),
    )
    # El acoplamiento en decision lo trae la sonda, asi que aca se acota: si NINGUN
    # valor posible tiene episodios, no hay cobertura y no depende de lo que sonde.
    card = features.region().split("/")[0]
    detector = "oracle" if has_runtime_detector(task) else "no_oracle"
    cont = continuation_segment(TARGET, task["task_id"])
    best_region, n = None, 0
    for coupling in ("loose", "tight", "unknown"):
        candidate = f"{card}/{detector}/{coupling}/{cont}"
        peers = {p: s for p, s in theta.paradigms_for(candidate).items() if p in CANDIDATES}
        got = max((s.episodes for s in peers.values()), default=0) if len(peers) >= 2 else 0
        if got > n:
            best_region, n = candidate, got
    region = best_region or f"{card}/{detector}/*/{cont}"
    ok = "si" if n >= MIN_EPISODES_FOR_CONFIDENCE else "NO"
    landed.append((task["task_id"], region, n, ok))
    print(f"  {task['task_id']:<16}{region:<40}{n:>10}{ok:>11}")

con = sum(1 for _, _, _, ok in landed if ok == "si")
sin_datos = sum(1 for _, _, n, _ in landed if n == 0)

print(f"\n  con estadisticas suficientes : {con}/{len(landed)}")
print(f"  con CERO episodios           : {sin_datos}/{len(landed)}")

print("\n" + "=" * 74)
if con == 0:
    print("VEREDICTO: NO correr P17 todavia.")
    print("")
    print("  theta no tiene estadisticas en ninguna region donde gold_p17 aterriza, asi")
    print("  que el margen seria 0 por FALTA DE DATOS y no por falta de senal. La corrida")
    print("  mediria abstencion por no tener con que decidir — algo que ya sabemos ahora,")
    print("  gratis, en vez de despues de ~14M tokens.")
    print("")
    print("  Primero: regenerar los corpus de entrenamiento con --honest-detectors y")
    print("  re-derivar sus episodios, para que el segmento de oraculo signifique lo")
    print("  mismo en el entrenamiento y en la decision.")
else:
    print(f"VEREDICTO: P17 es medible — theta decide en {con} de {len(landed)} tareas.")
    print("")
    print("  La distribucion se corrio pero no del todo: hay regiones con estadisticas")
    print("  suficientes. P17b (>= 7 de 14 vuelven specialise) sigue siendo una apuesta")
    print("  real y no un tramite.")
print("=" * 74)

out = settings.results_dir / "p17_coverage.json"
out.write_text(json.dumps({
    "train": list(TRAIN), "target": TARGET,
    "train_episodes": len(episodes),
    "landed": [{"task": t, "region": r, "episodes": n, "confident": ok} for t, r, n, ok in landed],
    "confident": con, "zero_episodes": sin_datos,
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nreporte: {out}")
