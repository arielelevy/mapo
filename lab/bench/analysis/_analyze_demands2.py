"""Los dos controles que O-4a y O-4b necesitan antes de que su veredicto valga.

POR QUE HACEN FALTA, Y SON LOS DOS ERRORES QUE ESTE REGISTRO YA COMETIO.

O-4a salio al reves de lo predicho: leer mas correlaciona MAS donde la cobertura NO se
exige (+0,459 contra +0,145). Pero `fraction_read` tiene DENOMINADOR DISTINTO en cada
clase: las celdas `sufficient` (C1, C3, C7) tienen pocas unidades, asi que leer una sola
ya es una fraccion grande; las `exhaustive` (C2, C4) corren sobre anchos 4/16/48. La
correlacion entre clases mezcla dos escalas — es el mismo confundido con dificultad de
tarea que mato a los tres primeros tests Hebbianos. El control es DENTRO DE TAREA.

O-4b comparo un eje de 4 clases contra uno de 2 por distancia media entre rankings. Mas
clases significa menos filas por clase, rankings mas ruidosos, y distancia media mayor
POR CONSTRUCCION. Sin null, 2,56 contra 2,25 no dice nada. El control es permutar las
etiquetas a nivel CELDA — que es donde vive el bloque — y ver donde cae el observado.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import random
import statistics
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner
from corpus.generate import REQUEST_DEMANDS

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")
CORPORA = ["gold_p17", "gold_p16", "gold_transfer", "gold_v2", "gold_deep"]


def pearson(pairs):
    n = len(pairs)
    if n < 4:
        return None
    mx = sum(x for x, _ in pairs) / n
    my = sum(y for _, y in pairs) / n
    sx = sum((x - mx) ** 2 for x, _ in pairs) ** 0.5
    sy = sum((y - my) ** 2 for _, y in pairs) ** 0.5
    if not sx or not sy:
        return None
    return sum((x - mx) * (y - my) for x, y in pairs) / (sx * sy)


def load():
    rows = []
    missing: list[str] = []
    for name in CORPORA:
        # Un corpus que no esta es un hecho del entorno y se DECLARA; cualquier otra cosa
        # es un defecto y tiene que romper. Tragarse todo con un `continue` haria que el
        # analisis reportara "sobre 5 corpus" habiendo leido tres, y ahora ademas se
        # tragaria la guarda de decodificaciones mezcladas — que levanta ValueError.
        if not (settings.corpus_dir / name).is_dir():
            missing.append(name)
            continue
        runner = Runner(settings, name, retriever_arm="hybrid", surface_variant="basic")
        for r in runner.load_rows():
            if r.get("infra_error") or r.get("infeasible"):
                continue
            d = REQUEST_DEMANDS.get(r["task_id"].split("-")[0].upper())
            if d is None:
                continue
            r["_card"], r["_cov"], r["_dom"] = d
            r["_key"] = (name, r["task_id"])
            rows.append(r)
    if missing:
        print(f"corpus ausentes, declarados y no ignorados: {missing}")
    if not rows:
        raise SystemExit(
            "Sin una sola fila utilizable. Devolver una lista vacia en silencio dejaria "
            "que los controles corran sobre nada y reporten 'SIN N' como si fuera un "
            "hallazgo del dato."
        )
    return rows


def main() -> None:
    rows = load()
    print(f"{len(rows)} filas\n")

    # --- O-4a controlado: la correlacion DENTRO de cada tarea --------------------------
    print("--- O-4a controlado: corr(fraccion leida, utilidad) DENTRO de cada tarea ---")
    per_task = defaultdict(list)
    cov_of = {}
    for r in rows:
        frac = (r.get("tool_usage") or {}).get("fraction_read")
        if frac is None:
            continue
        per_task[r["_key"]].append((frac, r["utility"]))
        cov_of[r["_key"]] = r["_cov"]

    by_cov = defaultdict(list)
    for key, pairs in per_task.items():
        rho = pearson(pairs)
        if rho is not None:
            by_cov[cov_of[key]].append(rho)

    out_a = {}
    for cov in ("sufficient", "exhaustive"):
        vals = by_cov[cov]
        if vals:
            out_a[cov] = {"tareas": len(vals), "rho_medio": statistics.mean(vals),
                          "rho_mediano": statistics.median(vals)}
            print(f"  {cov:<12} tareas={len(vals):>3}  rho medio {statistics.mean(vals):+.3f} "
                  f" mediano {statistics.median(vals):+.3f}")
        else:
            out_a[cov] = None
            print(f"  {cov:<12} sin tareas con variacion")

    if out_a["sufficient"] and out_a["exhaustive"]:
        # Permutacion sobre las etiquetas de TAREA: el bloque es la tarea.
        obs = out_a["exhaustive"]["rho_medio"] - out_a["sufficient"]["rho_medio"]
        pool = list(by_cov["sufficient"]) + list(by_cov["exhaustive"])
        n_ex = len(by_cov["exhaustive"])
        rng = random.Random(11)
        hits = 0
        TRIALS = 20_000
        for _ in range(TRIALS):
            rng.shuffle(pool)
            d = statistics.mean(pool[:n_ex]) - statistics.mean(pool[n_ex:])
            if abs(d) >= abs(obs):
                hits += 1
        p_a = (hits + 1) / (TRIALS + 1)
        print(f"  diferencia observada {obs:+.3f}   p (permutacion por tarea) = {p_a:.4f}")
        verdict_a = ("la cobertura SI cambia el retorno de leer" if p_a < 0.05
                     else "SIN EFECTO detectable una vez controlada la tarea")
        print(f"  O-4a: {verdict_a}")
    else:
        obs, p_a, verdict_a = None, None, "SIN N"

    # --- O-4b controlado: null que permuta la etiqueta a nivel CELDA -------------------
    print("\n--- O-4b controlado: 2,56 contra 2,25, contra su propio null ---")

    def spread(label_of):
        by_class = defaultdict(lambda: defaultdict(list))
        for r in rows:
            by_class[label_of(r)][r["paradigm"]].append(r["utility"])
        ranks = {}
        for klass, per_par in by_class.items():
            usable = {p: statistics.mean(v) for p, v in per_par.items() if len(v) >= 3}
            if len(usable) >= 4:
                ranks[klass] = [p for p, _ in sorted(usable.items(), key=lambda kv: -kv[1])]
        classes = sorted(ranks)
        dists = []
        for i, a in enumerate(classes):
            for b in classes[i + 1:]:
                common = [p for p in ranks[a] if p in ranks[b]]
                if len(common) < 4:
                    continue
                pa = {p: k for k, p in enumerate(ranks[a])}
                pb = {p: k for k, p in enumerate(ranks[b])}
                dists.append(sum(abs(pa[p] - pb[p]) for p in common) / len(common))
        return statistics.mean(dists) if dists else 0.0

    cells = sorted({r["task_id"].split("-")[0].upper() for r in rows})
    obs_cov = spread(lambda r: r["_cov"])
    obs_card = spread(lambda r: r["_card"])
    print(f"  observado | cobertura {obs_cov:.2f} | cardinalidad {obs_card:.2f}")

    # Null: reasignar a cada CELDA una etiqueta al azar, respetando cuantas clases y
    # cuantas celdas por clase tiene cada eje. Asi el null tiene la misma granularidad.
    def null_dist(real_map, trials=2000):
        sizes = defaultdict(int)
        for c in cells:
            sizes[real_map[c]] += 1
        pool = [k for k, n in sizes.items() for _ in range(n)]
        rng = random.Random(7)
        out = []
        for _ in range(trials):
            rng.shuffle(pool)
            fake = dict(zip(cells, pool))
            out.append(spread(lambda r: fake[r["task_id"].split("-")[0].upper()]))
        return out

    cov_map = {c: REQUEST_DEMANDS[c][1] for c in cells}
    card_map = {c: REQUEST_DEMANDS[c][0] for c in cells}
    null_cov = null_dist(cov_map)
    null_card = null_dist(card_map)

    def pct(nulls, obs):
        return sum(1 for v in nulls if v >= obs) / len(nulls)

    p_cov, p_card = pct(null_cov, obs_cov), pct(null_card, obs_card)
    print(f"  null cobertura    media {statistics.mean(null_cov):.2f}  -> p = {p_cov:.3f}")
    print(f"  null cardinalidad media {statistics.mean(null_card):.2f}  -> p = {p_card:.3f}")
    verdict_b = ("ninguno de los dos ejes supera su propio null"
                 if p_cov >= 0.05 and p_card >= 0.05
                 else f"cobertura p={p_cov:.3f} / cardinalidad p={p_card:.3f}")
    print(f"  O-4b: {verdict_b}")

    out = settings.results_dir / "demands_controlled.json"
    out.write_text(json.dumps({
        "o4a": {"per_class": out_a, "obs": obs, "p": p_a, "verdict": verdict_a},
        "o4b": {"obs_cov": obs_cov, "obs_card": obs_card,
                "null_cov_mean": statistics.mean(null_cov),
                "null_card_mean": statistics.mean(null_card),
                "p_cov": p_cov, "p_card": p_card, "verdict": verdict_b},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nveredicto: {out}")


if __name__ == "__main__":
    main()
