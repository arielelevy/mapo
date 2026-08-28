"""P-2f: el test pareado DENTRO de celda, con las replicas que le faltaban.

QUE DECIDE. Es la unica parte viva de la tesis Hebbiana. Como selector de paradigma la
tesis es redundante y es aritmetica —en el punto fijo `w* = 1,6p - 0,6`, monotona en la
tasa de victorias, y una transformacion monotona no cambia un argmax—. Como reloj de
decaimiento funciona y es conserjeria. Lo unico que NO se deduce de ahi es la asociacion
entre PARES: `(a -> b)` no es una estadistica marginal de un brazo.

EL TEST, Y POR QUE ESTE Y NO OTRO. Dentro de una misma celda `(tarea, paradigma)` —o sea
con tarea y paradigma fijos POR CONSTRUCCION, no por ajuste— se pregunta si existe una
transicion presente en TODAS las replicas exitosas y ausente en TODAS las fallidas. Los
tres tests anteriores no podian contestar esto:

  dispersion de tasas por transicion    confundida con dificultad de tarea
  estratificado, permutacion por fila   ninguna sobrevive Benjamini-Hochberg
  largo de secuencia, pareado           p = 1,000

EL NULL. Permutar las etiquetas exito/fallo DENTRO de la celda, conservando cuantas de
cada una. Eso preserva el bloque: la tarea, el paradigma, el numero de replicas y el
numero de exitos quedan fijos, y lo unico que se destruye es la correspondencia entre
QUE secuencia salio bien. Permutar entre celdas le regalaria al azar variacion de
dificultad que no es la hipotesis.

LA POTENCIA, ANTES DE LEER EL p. Con `n` replicas de las que `k` salieron bien, el `p`
minimo alcanzable por celda es `1/C(n,k)`. Con 3 replicas y 1 exito ese piso es 1/3, asi
que ninguna celda podia dar significativa AUNQUE la senal fuera perfecta. Con 9 replicas
el piso baja a 1/126 en el caso balanceado. Eso es lo que P-2f compro.

CONTEXTO: 13 celdas x 9 trials en `gold_p17b`, gemelo byte-identico de `gold_p17`, para
no tocar un registro cuyo veredicto esta congelado.
"""

import json
import random
import statistics
import sys
from collections import defaultdict
from dataclasses import replace
from math import comb

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner

CORPUS = "gold_p17b"
TRIALS = 20_000


def transitions(sequence: list[str]) -> set[tuple[str, str]]:
    """Los pares consecutivos. Un par repetido cuenta una vez: la hipotesis es que la
    transicion ESTA, no cuantas veces."""
    return {(a, b) for a, b in zip(sequence, sequence[1:])}


def separating(rows: list[dict]) -> set[tuple[str, str]]:
    """Transiciones en TODAS las exitosas y en NINGUNA fallida (o al reves).

    Las dos direcciones cuentan: una transicion que aparece solo cuando falla separa
    igual de bien que una que aparece solo cuando acierta, y descartar la segunda mitad
    seria buscar unicamente la hipotesis que nos gusta.
    """
    good = [transitions((r.get("tool_usage") or {}).get("sequence") or [])
            for r in rows if r["utility"] >= 1.0]
    bad = [transitions((r.get("tool_usage") or {}).get("sequence") or [])
           for r in rows if r["utility"] < 1.0]
    if not good or not bad:
        return set()
    in_all_good = set.intersection(*good)
    in_any_bad = set.union(*bad)
    in_all_bad = set.intersection(*bad)
    in_any_good = set.union(*good)
    return (in_all_good - in_any_bad) | (in_all_bad - in_any_good)


def main() -> None:
    base = Settings.from_env()
    settings = replace(base, results_dir=base.results_dir / "nano")
    runner = Runner(settings, CORPUS, retriever_arm="hybrid", surface_variant="basic")

    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in runner.load_rows():
        if r.get("infeasible"):
            continue
        cells[(r["paradigm"], r["task_id"])].append(r)

    usable = {k: v for k, v in cells.items()
              if len({row["utility"] >= 1.0 for row in v}) > 1}
    print(f"corpus {CORPUS} | {len(cells)} celdas | {len(usable)} con resultado VARIABLE")
    if not usable:
        print("Ninguna celda discrimina: el test no aplica.")
        return

    # --- potencia, antes del p ---------------------------------------------------------
    print("\n--- potencia por celda (piso alcanzable = 1/C(n,k)) ---")
    floors = []
    for (paradigm, task), rows in sorted(usable.items()):
        n = len(rows)
        k = sum(1 for r in rows if r["utility"] >= 1.0)
        floor = 1 / comb(n, k)
        floors.append(floor)
        print(f"  {paradigm:<14} {task:<14} n={n} exitos={k}  piso p={floor:.4f}"
              f"{'' if floor < 0.05 else '   <- no puede dar significativa'}")
    print(f"  celdas con potencia suficiente: "
          f"{sum(1 for f in floors if f < 0.05)} de {len(floors)}")

    # --- observado ---------------------------------------------------------------------
    print("\n--- ¿cuantas celdas tienen una transicion que separa? ---")
    observed = 0
    detail = []
    for (paradigm, task), rows in sorted(usable.items()):
        found = separating(rows)
        if found:
            observed += 1
            detail.append((paradigm, task, sorted(f"{a}->{b}" for a, b in found)[:3]))
    print(f"  observado: {observed} de {len(usable)}")
    for paradigm, task, trans in detail[:10]:
        print(f"    {paradigm:<14} {task:<14} {', '.join(trans)}")

    # --- null: permutar exito/fallo DENTRO de cada celda -------------------------------
    print(f"\n--- null: permutacion de etiquetas dentro de celda, {TRIALS:,} veces ---")
    rng = random.Random(23)
    pools = []
    for rows in usable.values():
        seqs = [transitions((r.get("tool_usage") or {}).get("sequence") or [])
                for r in rows]
        k = sum(1 for r in rows if r["utility"] >= 1.0)
        pools.append((seqs, k))

    def count_null() -> int:
        total = 0
        for seqs, k in pools:
            idx = list(range(len(seqs)))
            rng.shuffle(idx)
            good = [seqs[i] for i in idx[:k]]
            bad = [seqs[i] for i in idx[k:]]
            if not good or not bad:
                continue
            sep = ((set.intersection(*good) - set.union(*bad))
                   | (set.intersection(*bad) - set.union(*good)))
            if sep:
                total += 1
        return total

    nulls = [count_null() for _ in range(TRIALS)]
    hits = sum(1 for v in nulls if v >= observed)
    p = (hits + 1) / (TRIALS + 1)
    print(f"  null: mediana {statistics.median(nulls):.0f}  media "
          f"{statistics.mean(nulls):.2f}  max {max(nulls)}")
    print(f"  observado {observed}  ->  p = {p:.4f}")

    verdict = ("ESTABLECIDA" if p < 0.05 else
               "SIN ESTABLECER" if p < 0.15 else "SIN EVIDENCIA")
    print(f"\n  P-2c/P-2f: {verdict}")
    if p >= 0.05:
        print("  Ni refutacion ni confirmacion. Es el estado que corresponde reportar.")

    out = settings.results_dir / "p2f_verdict.json"
    out.write_text(json.dumps({
        "corpus": CORPUS,
        "cells_total": len(cells),
        "cells_discriminating": len(usable),
        "cells_with_power": sum(1 for f in floors if f < 0.05),
        "observed": observed,
        "null_median": statistics.median(nulls),
        "null_mean": statistics.mean(nulls),
        "p": p,
        "verdict": verdict,
        "detail": [{"paradigm": a, "task": b, "transitions": c} for a, b, c in detail],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nveredicto: {out}")


if __name__ == "__main__":
    main()
