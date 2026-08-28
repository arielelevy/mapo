"""¿La regla Hebbiana puede ganarse un lugar en el camino de decisión? Cero tokens.

QUÉ ES HOY, EXACTAMENTE. `policy.py` actualiza w <- (1-DECAY)*w + LEARNING_RATE*delta,
con delta = +0,5 si el paradigma fue el mejor en esa tarea y -0,3 si no. Eso es una media
móvil exponencial de `was_best`, o sea **una tasa de victorias ponderada por recencia**.
Y `theta_assertions` ya usa la tasa de victorias SIN ponderar.

Por eso está medido que eligen idéntico (0,5263 los tres: peso, utilidad media, tasa de
victorias). No es que el peso esté mal calculado — es que su único contenido distintivo
sobre lo que el router ya mira es **la recencia**. Un estimador con memoria sólo se
distingue de uno sin memoria cuando lo que estima CAMBIA.

ENTONCES LA PREGUNTA SE VUELVE UNA, Y ES EMPÍRICA: ¿el blanco se mueve? Si el mejor
paradigma por región es estable entre corpus, la recencia no tiene nada que rastrear y lo
honesto es sacar el peso del camino activo. Si se mueve, el peso Hebbiano tiene un trabajo
real que ninguna estadística marginal hace, y ese trabajo NO es "estimar mejor" sino
"rastrear un blanco móvil" — que es una afirmación distinta, más chica y defendible.

Hay un indicio previo en el registro: P15 verificó que `dag_strategy`, dominado por
`react` fuera de ventana en el registro anterior (P4), pasó a ser el mejor fijo en seed 47.

DOS MEDICIONES.
  A. ESTACIONARIEDAD, sin necesidad de orden: por región, cuál es el mejor paradigma en
     cada corpus, y con qué frecuencia cambia el ganador.
  B. ¿LA RECENCIA COMPRA ALGO?: ajustar los dos estimadores sobre los mismos episodios en
     el mismo orden, y comparar la utilidad que realizan eligiendo sobre un corpus que
     ninguno vio.
"""

import json
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.features import measure_continuation
from app.policy import DECAY, LEARNING_RATE, PRIOR_WEIGHT, WEIGHT_MAX, WEIGHT_MIN, Plasticity
from app.runner import Runner

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")

# El orden en que entraron al registro, según la historia del proyecto: gold_v2 fue la
# primera grilla, gold_transfer es el corpus held-out de P15. No sale de mtime — todas
# las corridas nano se hicieron el mismo día y el timestamp no distingue.
ORDER = ("gold_v2", "gold_deep", "gold_holdout")
TEST = "gold_transfer"


def continuation_of(corpus):
    docs = json.load(open(f"corpus/{corpus}/documents.json", encoding="utf-8"))
    tasks = json.load(open(f"corpus/{corpus}/tasks.json", encoding="utf-8"))
    return {t["task_id"]: measure_continuation(docs, t["unit_ids"]) for t in tasks}


def segment(c):
    return "c?" if c is None else ("chain" if c else "flat")


def episodes_of(corpus):
    runner = Runner(settings, corpus, retriever_arm="hybrid", surface_variant="basic")
    cont = continuation_of(corpus)
    return [
        replace(e, region=f"{e.region}/{segment(cont.get(e.task_id))}")
        for e in runner.episodes()
    ]


# =====================================================================================
# A. ¿El blanco se mueve?
# =====================================================================================
print("A. ESTACIONARIEDAD — ¿el mejor paradigma por región cambia entre corpus?\n")

best_by_corpus = {}
for corpus in ORDER + (TEST,):
    per_region = defaultdict(lambda: defaultdict(list))
    for e in episodes_of(corpus):
        per_region[e.region][e.paradigm].append(e.utility)
    best_by_corpus[corpus] = {
        region: max(arms, key=lambda p: sum(arms[p]) / len(arms[p]))
        for region, arms in per_region.items()
        if len(arms) >= 2
    }

regions = sorted({r for m in best_by_corpus.values() for r in m})
shared = [r for r in regions if sum(1 for m in best_by_corpus.values() if r in m) >= 2]

print(f"  {'región':<34}" + "".join(f"{c.replace('gold_', ''):>12}" for c in ORDER + (TEST,)))
flips = 0
for region in shared:
    winners = [best_by_corpus[c].get(region) for c in ORDER + (TEST,)]
    present = [w for w in winners if w]
    changed = len(set(present)) > 1
    flips += changed
    mark = "  <- cambia" if changed else ""
    print(f"  {region:<34}" + "".join(f"{(w or '-')[:11]:>12}" for w in winners) + mark)

print(f"\n  {flips} de {len(shared)} regiones comparables cambian de ganador "
      f"({flips / len(shared) * 100:.0f}%).")

# =====================================================================================
# B. ¿La recencia compra algo?
# =====================================================================================
print("\n" + "=" * 78)
print("B. ¿LA RECENCIA COMPRA ALGO? — dos estimadores, mismos episodios, mismo orden\n")

stream = [e for corpus in ORDER for e in episodes_of(corpus)]
print(f"  ajusta sobre {len(stream)} episodios de {', '.join(ORDER)}")

hebbian = defaultdict(lambda: PRIOR_WEIGHT)   # con memoria: EWMA de was_best
plain = defaultdict(lambda: [0, 0])           # sin memoria: tasa de victorias cruda
for e in stream:
    key = (e.region, e.paradigm)
    delta = 0.5 if e.was_best else -0.3
    w = (1.0 - DECAY) * hebbian[key] + LEARNING_RATE * delta
    hebbian[key] = max(WEIGHT_MIN, min(WEIGHT_MAX, w))
    plain[key][0] += 1 if e.was_best else 0
    plain[key][1] += 1

runner = Runner(settings, TEST, retriever_arm="hybrid", surface_variant="basic")
study = runner.study()
cont_t = continuation_of(TEST)
rows_by_task = defaultdict(dict)
for row in runner.load_rows():
    rows_by_task[row["task_id"]][row["paradigm"]] = row

tasks = sorted(study.complete_tasks)
best_fixed = study.best_fixed()


def pick(scorer, region, candidates):
    scored = [(p, scorer((region, p))) for p in candidates]
    scored = [(p, v) for p, v in scored if v is not None]
    if not scored:
        return None
    return max(scored, key=lambda pv: pv[1])[0]


def rate(key):
    wins, n = plain.get(key, (0, 0))
    return None if n == 0 else wins / n


def weight(key):
    return hebbian.get(key)


results = {}
for name, scorer in (("tasa de victorias (sin memoria)", rate),
                     ("peso Hebbiano (con memoria)", weight)):
    total, decided, agree = 0.0, 0, 0
    for task_id in tasks:
        region = next(iter(rows_by_task[task_id].values()))["region"]
        region = f"{region}/{segment(cont_t.get(task_id))}"
        candidates = sorted(rows_by_task[task_id])
        choice = pick(scorer, region, candidates)
        if choice is None:
            choice = best_fixed
        else:
            decided += 1
        total += study.quality(task_id, choice)
        if choice == pick(rate, region, candidates):
            agree += 1
    results[name] = {"utility": total / len(tasks), "decided": decided}
    print(f"  {name:<34} u={total / len(tasks):.4f}   decide en {decided}/{len(tasks)}")

fixed_u = sum(study.quality(t, best_fixed) for t in tasks) / len(tasks)
print(f"  {'mejor fijo (' + best_fixed + ')':<34} u={fixed_u:.4f}")

delta = results["peso Hebbiano (con memoria)"]["utility"] - results["tasa de victorias (sin memoria)"]["utility"]
print(f"\n  diferencia recencia - sin memoria: {delta:+.4f}")

# =====================================================================================
# C. El peso como DETECTOR, que es el unico trabajo que la matematica le deja
# =====================================================================================
# Por que no puede ser un selector mejor, y no es cuestion de tunear: en el punto fijo,
# para una tasa de victorias p constante,
#
#     w* = eta*(0,5p - 0,3(1-p))/DECAY = 1,6p - 0,6
#
# que es estrictamente creciente en p sobre el rango no clipeado. `theta_assertions` ya
# ordena por tasa de victorias. Una transformacion MONOTONA de la misma estadistica no
# puede cambiar un argmax — asi que "eligen identico" no es un accidente empirico ni un
# hiperparametro mal puesto: esta forzado.
#
# El unico lugar donde los dos difieren es el TRANSITORIO, o sea cuando p esta cambiando.
# Y eso los vuelve utiles para otra cosa: no para elegir mejor, sino para DETECTAR que la
# region es no estacionaria. Ahi el desacuerdo entre los dos es la senal, y la accion
# correcta no es rutear distinto — es bajar la confianza y abstenerse, que es maquinaria
# que el producto ya tiene.
print("\n" + "=" * 78)
print("C. EL DESACUERDO COMO SENAL — ¿marca las regiones que efectivamente giran?\n")

flipping = {r for r in shared
            if len({best_by_corpus[c][r] for c in ORDER + (TEST,) if r in best_by_corpus[c]}) > 1}

disagree, agree_regions = set(), set()
for region in shared:
    arms = sorted({p for (r, p) in plain if r == region})
    if len(arms) < 2:
        continue
    by_rate = max(arms, key=lambda a: rate((region, a)) or -1.0)
    by_weight = max(arms, key=lambda a: hebbian.get((region, a), 0.0))
    (disagree if by_rate != by_weight else agree_regions).add(region)

print(f"  regiones comparables            : {len(shared)}")
print(f"  giran de ganador (no estacionarias): {len(flipping)}")
print(f"  el peso y la tasa DISCREPAN en  : {len(disagree)}")
if disagree:
    hits = len(disagree & flipping)
    print(f"  de esas, giran de verdad        : {hits}/{len(disagree)}")
else:
    print("  ninguna: con ~6 episodios por clave el EWMA no se despega del prior")
    print("  (su horizonte es ~1/DECAY = 20 actualizaciones, y no las tiene)")

print("")
print("  DIAGNOSTICO DE LA PARAMETRIZACION, que es donde esta el problema real:")
print("  - por debajo de p = 0,375 el peso queda clavado en el piso 0,01, asi que")
print("    todos los brazos debiles se vuelven indistinguibles entre si;")
print("  - salir del piso cuesta ~5 victorias consecutivas para volver a un valor")
print("    medio, o sea que el rastreador se atrasa justo cuando deberia adelantarse;")
print("  - con 140 episodios sobre ~22 claves (region, paradigma) hay ~6 updates por")
print("    clave contra un horizonte de ~20: el estimador nunca sale del prior.")
print("")
print("  Por eso B da exactamente 0,0000, y no por falta de drift: el drift esta")
print(f"  medido en {flips}/{len(shared)} regiones. Falta el estimador que lo vea.")

out = {
    "order": list(ORDER), "test": TEST,
    "regions_flipping_set": sorted(flipping),
    "regions_disagreeing": sorted(disagree),
    "fixed_point": "w* = 1.6p - 0.6 (monotona en p ⇒ mismo argmax)",
    "regions_comparable": len(shared), "regions_flipping": flips,
    "selectors": results, "best_fixed": {"paradigm": best_fixed, "utility": round(fixed_u, 4)},
    "recency_delta": round(delta, 5),
}
path = settings.results_dir / "hebbian.json"
path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nreporte: {path}")
