"""ONT-1 CON NULO POR PERMUTACIÓN, y el `p` EXACTO del nulo de capacidades. Cero llamadas.

Dos cosas que la revisión externa del 2026-09-01 pidió y que se pueden hacer sin modelo:

1. La tabla de §7.4.3 (señal/ruido por segmentación) no tenía script y controlaba el
   número de segmentos dividiendo la ganancia por `n`, que es ad hoc. Acá la segmentación se
   evalúa contra su PROPIO nulo por permutación: se barajan las etiquetas de segmento entre
   tareas (mismos tamaños de segmento) y se recalcula. Eso controla por número y tamaño de
   segmentos sin inventar una normalización.

   La cantidad: para cada segmento s, la varianza entre brazos de sus medias por brazo,
   descontado el ruido esperado de una media sobre |T_s| celdas con 3 réplicas (ε/(3|T_s|)).
   Se agrega ponderando por tareas, y se reporta relativa a la partición trivial (S/R = 1).

2. El nulo de capacidades barajadas de §7.4.2 usaba 400 barajadas y daba p = 0,065. Con
   ocho brazos hay 8! = 40.320 permutaciones: se recorren todas y el p es exacto. El modelo
   es el mismo de `_eda_capacidades.py`, copiado literal (las funciones viven adentro de su
   `main` y no se pueden importar).

Corre DESDE `lab/`:  py bench/analysis/_ontologia_nulo.py
"""
from __future__ import annotations

import collections
import itertools
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.capacidades import EXIGE, TIENE
from app.runner import load_rows
from bench.analysis._eda_capacidades import ejes_de
from bench.panel import rectangulo

REGISTRO = Path("results/luna/gold_h1_rows.jsonl")
CORPUS = Path("corpus/gold_h1")
PERMS = 2000
SEMILLA = 20260901

PRIORIDAD = ["cadena_acoplada", "contradiccion", "horizonte_desconocido", "ausencia",
             "cobertura_exhaustiva", "entidad_nombrada", "material_mayor_que_ventana"]


def eje_principal(t: dict) -> str:
    ejes = ejes_de(t)
    for e in PRIORIDAD:
        if e in ejes:
            return e
    return "ninguno"


def main() -> None:
    rng = random.Random(SEMILLA)
    docs = json.loads((CORPUS / "documents.json").read_text(encoding="utf-8"))
    tareas = {t["task_id"]: t for t in json.loads((CORPUS / "tasks.json").read_text(encoding="utf-8"))}
    for t in tareas.values():
        t["_material_tokens"] = sum(len(docs.get(u, "")) for u in t["unit_ids"]) // 4

    filas = [f for f in load_rows(REGISTRO) if not f.get("infeasible")]
    panel = rectangulo(filas)
    ts, bs = list(panel.tareas), sorted(panel.brazos)
    reps: dict[tuple[str, str], list[float]] = collections.defaultdict(list)
    region_de: dict[str, str] = {}
    for f in filas:
        if f["task_id"] in set(ts) and f["paradigm"] in bs:
            reps[(f["task_id"], f["paradigm"])].append(float(f.get("utility", 0.0)))
            region_de[f["task_id"]] = str(f.get("region"))
    um = {k: statistics.mean(v) for k, v in reps.items()}
    eps = statistics.mean(statistics.variance(v) for v in reps.values() if len(v) > 1)

    print("=" * 96)
    print(f"1. ONTOLOGÍA CONTRA REGIÓN, CON NULO POR PERMUTACIÓN · {panel.descripcion()}")
    print("=" * 96)

    def separacion(etiqueta: dict[str, str]) -> float:
        grupos: dict[str, list[str]] = collections.defaultdict(list)
        for t in ts:
            grupos[etiqueta[t]].append(t)
        total, peso = 0.0, 0
        for seg in grupos.values():
            medias = [statistics.mean(um[(t, p)] for t in seg) for p in bs]
            var_b = statistics.variance(medias)
            ruido = eps / (3.0 * len(seg))
            total += len(seg) * max(0.0, var_b - ruido)
            peso += len(seg)
        return total / peso

    segmentaciones = {
        "ninguna": {t: "todo" for t in ts},
        "región (vocabulario vigente)": {t: region_de[t] for t in ts},
        "región, primer eje": {t: region_de[t].split("/")[0] for t in ts},
        "cardinalidad × cobertura (declarados)": {
            t: f"{tareas[t].get('answer_cardinality')}/{tareas[t].get('coverage_demanded')}" for t in ts},
        "ontología, eje principal": {t: eje_principal(tareas[t]) for t in ts},
        "ontología, contradicción binaria": {
            t: "contra" if "contradiccion" in ejes_de(tareas[t]) else "otro" for t in ts},
        "ontología, horizonte binario": {
            t: "hor" if "horizonte_desconocido" in ejes_de(tareas[t]) else "otro" for t in ts},
        "modo del corpus (etiqueta de diseño)": {t: tareas[t]["cell"] for t in ts},
    }
    base = separacion(segmentaciones["ninguna"])
    print(f"  {'segmentación':40}{'segm.':>6}{'S/R':>7}{'nulo media':>11}{'nulo p95':>9}{'p':>8}")
    salida = {}
    for nombre, et in segmentaciones.items():
        obs = separacion(et) / base if base else float("nan")
        n_seg = len(set(et.values()))
        if n_seg == 1:
            print(f"  {nombre:40}{n_seg:>6}{obs:>7.2f}{'':>11}{'':>9}{'':>8}")
            continue
        labels = [et[t] for t in ts]
        nulos = []
        for _ in range(PERMS):
            rng.shuffle(labels)
            nulos.append(separacion(dict(zip(ts, labels))) / base)
        nulos.sort()
        p95 = nulos[int(0.95 * PERMS)]
        p = sum(1 for v in nulos if v >= obs) / PERMS
        salida[nombre] = (n_seg, obs, statistics.mean(nulos), p95, p)
        print(f"  {nombre:40}{n_seg:>6}{obs:>7.2f}{statistics.mean(nulos):>11.2f}{p95:>9.2f}{p:>8.3f}"
              + ("  *" if obs > p95 else ""))
    print("\n  * = supera el p95 de su propio nulo (mismos tamaños de segmento, etiquetas barajadas).")

    print("\n" + "=" * 96)
    print("2. NULO DE CAPACIDADES, EXACTO: las 40.320 permutaciones de TIENE entre los ocho brazos")
    print("=" * 96)

    # El modelo de `_eda_capacidades.py`, vectorizado. Los rasgos de una celda (t, p) dependen
    # sólo de los ejes de t y del conjunto de capacidades del brazo p, así que se precomputan
    # por (tarea, conjunto) y una permutación sólo remapea qué conjunto tiene cada brazo. El
    # ajuste es: efecto[r] = sum(residuos de las celdas de entrenamiento con r) / (conteo + 8),
    # predicción = dificultad_tarea + sum(efectos de los rasgos de la celda), recortada a [0, 1].
    import numpy as np

    conjuntos = [frozenset(TIENE.get(p, set())) for p in bs]          # conjunto original del brazo i
    caps = sorted({c for s in conjuntos for c in s} | {c for v in EXIGE.values() for c in v})
    F = 3 * len(caps)
    ex_de = {t: set().union(*(EXIGE.get(e, set()) for e in ejes_de(tareas[t]))) or set() for t in ts}
    T, S = len(ts), len(bs)
    X = np.zeros((T, S, F))                                            # X[t, s, r]
    for ti, t in enumerate(ts):
        for si, s in enumerate(conjuntos):
            for ci, c in enumerate(caps):
                if c in ex_de[t] and c not in s:
                    X[ti, si, ci] = 1.0                                 # falta::c
                if c in ex_de[t] and c in s:
                    X[ti, si, len(caps) + ci] = 1.0                     # cubre::c
                if c in s:
                    X[ti, si, 2 * len(caps) + ci] = 1.0                 # tiene::c
    UM = np.array([[um[(t, p)] for p in bs] for t in ts])              # UM[t, i]

    def mae_loao(perm: tuple[int, ...]) -> float:
        # el brazo i usa el conjunto perm[i]
        errs = []
        for f in range(S):
            tr = [i for i in range(S) if i != f]
            base_ = UM[:, tr].mean()
            R = UM[:, tr] - base_                                      # residuos [T, S-1]
            Xtr = X[:, [perm[i] for i in tr], :]                        # [T, S-1, F]
            suma = np.einsum("ti,tif->f", R, Xtr)
            conteo = Xtr.sum(axis=(0, 1))
            ef = suma / (conteo + 8.0)
            dif = UM[:, tr].mean(axis=1)
            pred = np.clip(dif + X[:, perm[f], :] @ ef, 0.0, 1.0)
            errs.append(np.abs(UM[:, f] - pred).mean())
        return float(np.mean(errs))

    real = mae_loao(tuple(range(S)))
    nulos = np.array([mae_loao(perm) for perm in itertools.permutations(range(S))])
    nulos.sort()
    p_exacto = float((nulos <= real).sum() / len(nulos))
    print(f"  MAE con capacidades REALES      {real:.4f}")
    print(f"  nulo exacto ({len(nulos)} permutaciones)  media {nulos.mean():.4f} · "
          f"p5 {nulos[int(0.05 * len(nulos))]:.4f} · mín {nulos[0]:.4f}")
    print(f"  p exacto = {p_exacto:.4f}   (la asignación real incluida entre las {len(nulos)})")


if __name__ == "__main__":
    main()
