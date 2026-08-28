"""D-1: cuanto cuesta que el MODELO decida cuando parar.

LA DECISION QUE HOY NO GOBIERNA NADIE. En los brazos con bucle, quien decide seguir o
parar es el modelo. El codigo no impone ninguna cota que dependa de lo que ya se vio, y
sin embargo las senales para hacerlo ya estan contadas: `barren_searches`,
`stall_warnings`, `units_read`, `relevant_units_read`, `fraction_read` y la secuencia
entera de herramientas.

COMO SE MIDE SIN GASTAR NADA. Dentro de una misma celda `(tarea, paradigma)` las replicas
resuelven la MISMA tarea con el MISMO brazo. Si dos replicas llegan a la misma utilidad y
una cuesta la mitad que la otra, la diferencia no es dificultad: es **cuando cada una
decidio parar**. La celda misma dice cuanto sobraba.

  headroom de la celda = (costo_max - costo_min) entre replicas de IGUAL utilidad

Eso es el techo de lo que una regla de parada perfecta capturaria en esa celda. No es lo
que capturaria una regla real —una regla real se equivoca— pero acota el premio: si el
techo es chico, la decision no vale la pena gobernarla, y eso tambien es una respuesta.

LO QUE ESTA MEDIDA NO ES. No es una propuesta de regla ni una prediccion sobre una.
Es el tamano del premio, que es lo que hay que saber ANTES de disenar la regla.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import statistics
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner

CORPORA = ["gold_p17", "gold_p16", "gold_transfer", "gold_v2", "gold_deep"]


def main() -> None:
    base = Settings.from_env()
    settings = replace(base, results_dir=base.results_dir / "nano")

    cells = defaultdict(list)
    missing = []
    for name in CORPORA:
        if not (settings.corpus_dir / name).is_dir():
            missing.append(name)
            continue
        runner = Runner(settings, name, retriever_arm="hybrid", surface_variant="basic")
        for r in runner.load_rows():
            if r.get("infra_error") or r.get("infeasible"):
                continue
            cells[(name, r["task_id"], r["paradigm"])].append(r)
    if missing:
        print(f"corpus ausentes, declarados: {missing}")
    if not cells:
        raise SystemExit("sin celdas: el analisis no tuvo con que correr")

    print(f"{len(cells)} celdas con replicas\n")

    # --- el techo, por brazo ------------------------------------------------------------
    print("--- techo de una regla de parada perfecta, por brazo ---")
    print("  (entre replicas de IGUAL utilidad: mismo resultado, distinto gasto)")
    per_par = defaultdict(lambda: {"cells": 0, "waste": 0, "spent": 0, "worst": 0.0})
    for (corpus, task, paradigm), rows in cells.items():
        if len(rows) < 2:
            continue
        best = max(r["utility"] for r in rows)
        tied = [r for r in rows if r["utility"] == best]
        if len(tied) < 2:
            continue
        costs = [r["cost_tokens"] for r in tied]
        lo, hi = min(costs), max(costs)
        if hi == 0:
            continue
        a = per_par[paradigm]
        a["cells"] += 1
        a["waste"] += hi - lo
        a["spent"] += hi
        a["worst"] = max(a["worst"], (hi - lo) / hi)

    print(f"  {'brazo':<16}{'celdas':>8}{'gastado':>14}{'evitable':>14}{'%':>7}{'peor celda':>12}")
    total_w = total_s = 0
    for p, a in sorted(per_par.items(), key=lambda kv: -kv[1]["waste"]):
        share = a["waste"] / a["spent"] if a["spent"] else 0
        print(f"  {p:<16}{a['cells']:>8}{a['spent']:>14,}{a['waste']:>14,}"
              f"{share:>6.0%}{a['worst']:>11.0%}")
        total_w += a["waste"]
        total_s += a["spent"]
    if total_s:
        print(f"  {'TOTAL':<16}{'':>8}{total_s:>14,}{total_w:>14,}"
              f"{total_w/total_s:>6.0%}")

    # --- ¿la senal que gobernaria la regla ya existe y discrimina? ----------------------
    print("\n--- ¿las senales ya contadas separan la replica cara de la barata? ---")
    signals = ("barren_searches", "stall_warnings", "units_read")
    rows_cheap, rows_dear = [], []
    for rows in cells.values():
        if len(rows) < 2:
            continue
        best = max(r["utility"] for r in rows)
        tied = [r for r in rows if r["utility"] == best]
        if len(tied) < 2:
            continue
        tied.sort(key=lambda r: r["cost_tokens"])
        if tied[0]["cost_tokens"] == tied[-1]["cost_tokens"]:
            continue
        rows_cheap.append(tied[0])
        rows_dear.append(tied[-1])

    print(f"  pares (misma celda, misma utilidad, distinto gasto): {len(rows_cheap)}")
    if rows_cheap:
        for sig in signals:
            # AUSENTE NO ES CERO, y confundirlos hace leer "la senal no discrimina" donde
            # lo que pasa es que la senal no se guardo. `.get(sig, 0)` los vuelve
            # indistinguibles, que es la version silenciosa del mismo error que este
            # proyecto viene cerrando en el codigo.
            present = [r for r in rows_cheap + rows_dear
                       if sig in (r.get("tool_usage") or {})]
            if not present:
                print(f"    {sig:<18} AUSENTE del registro - no es un cero medido, "
                      f"es una senal que la fila no guarda")
                continue
            c = [(r.get("tool_usage") or {})[sig] for r in rows_cheap
                 if sig in (r.get("tool_usage") or {})]
            d = [(r.get("tool_usage") or {})[sig] for r in rows_dear
                 if sig in (r.get("tool_usage") or {})]
            if not c or not d:
                print(f"    {sig:<18} presente en una sola mitad: no comparable")
                continue
            print(f"    {sig:<18} barata {statistics.mean(c):>7.2f}   "
                  f"cara {statistics.mean(d):>7.2f}   "
                  f"delta {statistics.mean(d) - statistics.mean(c):+7.2f}")
        ic = [r.get("iterations", 0) for r in rows_cheap]
        idr = [r.get("iterations", 0) for r in rows_dear]
        print(f"    {'iterations':<18} barata {statistics.mean(ic):>7.2f}   "
              f"cara {statistics.mean(idr):>7.2f}   "
              f"delta {statistics.mean(idr) - statistics.mean(ic):+7.2f}")

    out = settings.results_dir / "stopping.json"
    out.write_text(json.dumps({
        "cells": len(cells),
        "per_paradigm": {k: dict(v) for k, v in per_par.items()},
        "total_spent": total_s,
        "total_avoidable": total_w,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndetalle: {out}")


if __name__ == "__main__":
    main()
