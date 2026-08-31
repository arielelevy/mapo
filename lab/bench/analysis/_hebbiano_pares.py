"""HEBBIANO SOBRE PARES Y TRIPLAS: ¿predicen fuera de muestra más que los conteos? Cero llamadas.

LA PREGUNTA, planteada como aprendizaje y no como orden. `tools.py` justifica guardar la
secuencia diciendo que *«una asociación entre PARES no se reduce a una estadística marginal
de un brazo»*. Operacionalmente eso significa una sola cosa:

    ¿un predictor construido sobre pares (o triplas) le gana, FUERA DE MUESTRA, a uno
    construido sólo sobre conteos?

Si no le gana, la asociación no tiene contenido propio: lo que sabe ya estaba en el
histograma.

QUÉ SE PREDICE, y no es la utilidad. Se predice **γ**, el residuo de
`u = μ + α(tarea) + β(brazo) + γ + ε`. Predecir la utilidad cruda daría señal enorme y
vacía: un par aparece más en las filas buenas porque los brazos que lo usan son otros brazos,
y las tareas donde aparece son otras tareas. **α y β son exactamente ese confundido**, y
sacarlos deja lo único que un aprendizaje sobre herramientas podría explicar.

LA LECTURA HEBBIANA, literal: cada n-grama acumula el residuo medio de las filas donde
co-ocurre —eso es su peso— y la predicción de una fila es el promedio de los pesos de sus
n-gramas. Fortalecer lo que co-activa con buen resultado, sin más maquinaria.

LA EVALUACIÓN: **leave-one-task-out**. Los pesos se aprenden sin ver ninguna fila de la tarea
evaluada. Con `repeat=3`, entrenar y evaluar sobre la misma tarea daría casi memorización.

LA VARA, y son dos:
  · el predictor de **unigramas** (los conteos) — si los pares no le ganan, no aportan
  · el **nulo por permutación** — barajar los residuos entre filas y reajustar, que dice
    cuánto predice un modelo del mismo tamaño sin ninguna relación

Corre DESDE `lab/`:  py bench/analysis/_hebbiano_pares.py
"""

from __future__ import annotations

import collections
import json
import random
import statistics
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PERMUTACIONES = 400
SEMILLA = 20260830
MIN_APARICIONES = 4      # un n-grama visto 3 veces es una anécdota, no una asociación


def filas_de(ruta: _Path) -> list[dict]:
    out = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            out.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    return out


def ngramas(seq: list[str], n: int) -> list[tuple]:
    if n == 1:
        return [(t,) for t in seq]
    return [tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)]


def main() -> None:
    rng = random.Random(SEMILLA)
    filas = [f for f in filas_de(_Path("results/luna/gold_h1_rows.jsonl"))
             if not f.get("infeasible") and not f.get("infra_error")]

    # ── el residuo gamma, por fila ──────────────────────────────────────────
    celdas = collections.defaultdict(list)
    for f in filas:
        celdas[(f["task_id"], f["paradigm"])].append(f)
    u = {k: statistics.mean(x["utility"] for x in v) for k, v in celdas.items()}
    tareas_all = sorted({t for t, _ in u})
    brazos_all = sorted({p for _, p in u})
    mu = statistics.mean(u.values())
    alpha = {t: statistics.mean(u[(t, p)] for p in brazos_all if (t, p) in u) - mu
             for t in tareas_all}
    beta = {p: statistics.mean(u[(t, p)] for t in tareas_all if (t, p) in u) - mu
            for p in brazos_all}

    datos = []
    for f in filas:
        seq = ((f.get("tool_usage") or {}).get("sequence")) or []
        if not seq:
            continue
        datos.append({
            "tarea": f["task_id"], "brazo": f["paradigm"],
            "seq": list(seq),
            "y": f["utility"] - mu - alpha.get(f["task_id"], 0.0)
                 - beta.get(f["paradigm"], 0.0),
        })

    print("=" * 94)
    print("HEBBIANO SOBRE PARES Y TRIPLAS — ¿predicen fuera de muestra?")
    print("=" * 94)
    print(f"\n  {len(datos):,} filas con al menos una llamada · "
          f"{len({d['tarea'] for d in datos})} tareas")
    if len(datos) < 100:
        print("\n  >>> material insuficiente")
        return

    var_y = statistics.pvariance([d["y"] for d in datos])

    def evaluar(orden: int) -> tuple[float, int]:
        """Leave-one-task-out. Devuelve (varianza explicada fuera de muestra, n-gramas)."""
        pred, real = [], []
        vistos: set = set()
        for tarea in sorted({d["tarea"] for d in datos}):
            tren = [d for d in datos if d["tarea"] != tarea]
            prueba = [d for d in datos if d["tarea"] == tarea]
            peso = collections.defaultdict(list)
            for d in tren:
                for g in set(ngramas(d["seq"], orden)):
                    peso[g].append(d["y"])
            w = {g: statistics.mean(v) for g, v in peso.items()
                 if len(v) >= MIN_APARICIONES}
            vistos |= set(w)
            for d in prueba:
                gs = [g for g in set(ngramas(d["seq"], orden)) if g in w]
                pred.append(statistics.mean(w[g] for g in gs) if gs else 0.0)
                real.append(d["y"])
        sr = sum((r - p) ** 2 for r, p in zip(real, pred)) / len(real)
        return (1.0 - sr / var_y if var_y else 0.0), len(vistos)

    print(f"\n  {'orden':22s} {'n-gramas':>9s} {'R2 fuera de muestra':>21s} "
          f"{'nulo p95':>9s} {'p':>7s}")
    resultados = {}
    for orden, nombre in ((1, "unigramas (conteos)"), (2, "PARES"), (3, "TRIPLAS")):
        real, n_g = evaluar(orden)
        # NULO: se barajan los residuos entre filas y se reajusta entero. Dice cuanto
        # explica un modelo del mismo tamaño sin ninguna relación con la secuencia.
        ys = [d["y"] for d in datos]
        nulos = []
        for _ in range(PERMUTACIONES):
            b = ys[:]
            rng.shuffle(b)
            for d, y in zip(datos, b):
                d["y"] = y
            nulos.append(evaluar(orden)[0])
        for d, y in zip(datos, ys):
            d["y"] = y
        p95 = sorted(nulos)[int(0.95 * len(nulos))]
        pv = (sum(1 for x in nulos if x >= real) + 1) / (len(nulos) + 1)
        resultados[nombre] = (real, n_g, p95, pv)
        print(f"  {nombre:22s} {n_g:9d} {real:21.4f} {p95:9.4f} {pv:7.3f}"
              f"{' *' if real > p95 else ''}")

    uni = resultados["unigramas (conteos)"][0]
    par = resultados["PARES"][0]
    tri = resultados["TRIPLAS"][0]
    print(f"""
  {'-' * 90}
  LO QUE DECIDE: **si los pares le ganan a los conteos.** Esa es la afirmacion de
  `tools.py` — que la asociacion entre pares no se reduce a la estadistica marginal.

      unigramas {uni:+.4f}   pares {par:+.4f}   triplas {tri:+.4f}
      pares - unigramas = {par - uni:+.4f}

  >>> {'LOS PARES APORTAN sobre los conteos' if par > uni else 'LOS PARES NO APORTAN: lo que saben ya estaba en el histograma'}
""")

    # ── los pesos aprendidos, para poder leerlos a ojo ──────────────────────
    peso = collections.defaultdict(list)
    for d in datos:
        for g in set(ngramas(d["seq"], 2)):
            peso[g].append(d["y"])
    w = {g: (statistics.mean(v), len(v)) for g, v in peso.items()
         if len(v) >= MIN_APARICIONES * 3}
    print("  los pares con mas peso (ajustados sobre TODO, solo para leerlos):\n")
    print(f"  {'par':38s} {'filas':>6s} {'peso':>8s}")
    for g, (m, n) in sorted(w.items(), key=lambda kv: -abs(kv[1][0]))[:10]:
        print(f"  {g[0] + ' -> ' + g[1]:38s} {n:6d} {m:+8.3f}")


if __name__ == "__main__":
    main()
