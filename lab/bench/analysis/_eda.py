"""Analisis exploratorio del registro. Cero llamadas al modelo, cero supuestos previos.

QUE ES Y QUE NO ES. Los otros analizadores contestan una pregunta que alguien trajo. Este
NO trae pregunta: recorre el registro entero y reporta lo que se ve, para que lo que salte
lo elija el dato y no el que mira. Es lo que corresponde despues de una campana, y antes de
formular la siguiente hipotesis.

POR QUE HACE FALTA, con evidencia de esta sesion: casi todos los defectos serios del
2026-08-29 estaban **contados y visibles** antes de que alguien preguntara.
`provider_cached_tokens` corregia un factor de 1,57x a 1,36x y no entraba en ninguna
conclusion. `barren_total` en 0 para dos brazos era un cero estructural que ningun analisis
dirigido miraba. Un barrido sin hipotesis los habria levantado el primer dia.

QUE MIRA, en este orden:

  1. CAMPOS MUERTOS       lo que es constante o siempre cero. Un campo que nunca varia no
                          puede explicar nada, y si prometia hacerlo es un defecto
  2. DISTRIBUCIONES       rango, mediana, asimetria y ceros de cada numerico. Una media sin
                          su forma esconde bimodalidad, que es lo que borra un promedio
  3. RELACION CON u       correlacion de cada campo con la utilidad, y CONTROLADA por celda
                          — una correlacion global puede ser el promedio de dos signos
  4. DESCOMPOSICION       cuanta varianza de u es de la TAREA, cuanta del PARADIGMA y cuanta
                          entre replicas. Eso acota cuanto puede ganar CUALQUIER router:
                          si la varianza de paradigma es chica, no hay que elegir
  5. ATIPICOS             celdas lejos de sus vecinas, que es donde suele estar el defecto

QUE NO HACE. No prueba nada. Una correlacion aca es una invitacion a medir, y este archivo
no distingue una regularidad de un artefacto — para eso hace falta el control, y esta
sesion mostro que un patron dentro de un subgrupo no es un efecto del subgrupo hasta que se
lo mide afuera.

Corre DESDE `lab/`:  py bench/analysis/_eda.py --modelo luna
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.runner import load_rows


def numericos(filas: list[dict]) -> dict[str, list[float]]:
    """Todo campo numerico del nivel superior y de `tool_usage`, aplanado."""
    cols: dict[str, list[float]] = collections.defaultdict(list)
    for f in filas:
        plano = {k: v for k, v in f.items() if isinstance(v, (int, float))
                 and not isinstance(v, bool)}
        plano.update({f"tu.{k}": v for k, v in (f.get("tool_usage") or {}).items()
                      if isinstance(v, (int, float)) and not isinstance(v, bool)})
        for k, v in plano.items():
            cols[k].append(float(v))
    # Sólo las columnas presentes en TODAS las filas: una columna a medias no se puede
    # correlacionar sin decidir qué significa su ausencia, y ausente no es cero.
    return {k: v for k, v in cols.items() if len(v) == len(filas)}


def corr(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 8:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    d = (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5
    return (sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / d) if d else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--modelo", default="luna")
    ap.add_argument("--corpus", default="gold_h1")
    args = ap.parse_args()

    ruta = _Path("results") / args.modelo / f"{args.corpus}_rows.jsonl"
    todas = load_rows(ruta)
    filas = [f for f in todas if not f.get("infeasible")]
    print(f"{ruta.name}: {len(todas)} filas · {len(filas)} medidas "
          f"({len(todas) - len(filas)} infactibles, que NO son mediciones)\n")

    cols = numericos(filas)
    u = [f["utility"] for f in filas]

    # ---------------------------------------------------------------- 1
    print("=" * 78)
    print("1. CAMPOS MUERTOS — constantes o siempre cero\n")
    muertos = [(k, v[0]) for k, v in sorted(cols.items()) if len(set(v)) == 1]
    for k, v in muertos:
        print(f"   {k:<34}constante en {v:g}")
    if not muertos:
        print("   ninguno")
    print(f"\n   {len(muertos)} de {len(cols)} columnas no varían. Un campo que nunca "
          f"cambia no puede\n   explicar nada — y si su nombre promete que sí, es deuda.")

    # ---------------------------------------------------------------- 2
    print("\n" + "=" * 78)
    print("2. DISTRIBUCIONES — la forma, no sólo la media\n")
    print(f"   {'campo':<30}{'mediana':>12}{'media':>12}{'máx':>14}{'ceros':>8}{'p90/p50':>9}")
    vivos = {k: v for k, v in cols.items() if len(set(v)) > 1}
    for k in sorted(vivos, key=lambda k: -statistics.mean(vivos[k])):
        v = sorted(vivos[k])
        med = statistics.median(v)
        p90 = v[int(0.9 * (len(v) - 1))]
        ceros = sum(1 for x in v if x == 0)
        razon = (p90 / med) if med else float("inf")
        print(f"   {k:<30}{med:>12,.2f}{statistics.mean(v):>12,.2f}{v[-1]:>14,.0f}"
              f"{100*ceros/len(v):>7.0f}%{razon:>9.1f}")

    # ---------------------------------------------------------------- 3
    print("\n" + "=" * 78)
    print("3. RELACIÓN CON LA UTILIDAD — global, y controlada por celda\n")
    print("   La global puede ser el promedio de dos signos opuestos. La segunda columna\n"
          "   promedia la correlación DENTRO de cada celda, que es donde la pregunta vive.\n")
    porcelda: dict[str, list[dict]] = collections.defaultdict(list)
    for f in filas:
        porcelda[f.get("cell") or "?"].append(f)
    print(f"   {'campo':<30}{'r global':>10}{'r por celda':>14}{'discrepa':>10}")
    filas_r = []
    for k in sorted(vivos):
        if k == "utility":
            continue
        g = corr(vivos[k], u)
        dentro = []
        for c, gg in porcelda.items():
            if len(gg) < 8:
                continue
            sub = numericos(gg)
            if k in sub:
                r = corr(sub[k], [x["utility"] for x in gg])
                if r is not None:
                    dentro.append(r)
        d = statistics.mean(dentro) if dentro else None
        if g is None:
            continue
        disc = "SÍ" if (d is not None and abs(g - d) > 0.15) else ""
        filas_r.append((abs(g), k, g, d, disc))
    for _, k, g, d, disc in sorted(filas_r, reverse=True)[:16]:
        ds = f"{d:>+14.3f}" if d is not None else f"{'-':>14}"
        print(f"   {k:<30}{g:>+10.3f}{ds}{disc:>10}")

    # ---------------------------------------------------------------- 4
    print("\n" + "=" * 78)
    print("4. DE DÓNDE VIENE LA VARIANZA DE `u` — y esto acota a CUALQUIER router\n")
    celdas: dict[tuple, list[float]] = collections.defaultdict(list)
    for f in filas:
        celdas[(f["task_id"], f["paradigm"])].append(f["utility"])
    med = {k: statistics.mean(v) for k, v in celdas.items()}
    total = statistics.pvariance(u)
    # dentro de celda = entre réplicas
    dentro = statistics.mean([statistics.pvariance(v) for v in celdas.values()
                              if len(v) > 1]) if celdas else 0.0
    portarea = collections.defaultdict(list)
    porpara = collections.defaultdict(list)
    for (t, p), m in med.items():
        portarea[t].append(m)
        porpara[p].append(m)
    var_tarea = statistics.pvariance([statistics.mean(v) for v in portarea.values()])
    var_para = statistics.pvariance([statistics.mean(v) for v in porpara.values()])
    print(f"   varianza total de la utilidad          {total:.4f}")
    print(f"   entre RÉPLICAS de la misma celda       {dentro:.4f}   "
          f"({100*dentro/total:.0f}% del total)")
    print(f"   entre TAREAS (media por tarea)         {var_tarea:.4f}   "
          f"({100*var_tarea/total:.0f}%)")
    print(f"   entre PARADIGMAS (media por brazo)     {var_para:.4f}   "
          f"({100*var_para/total:.0f}%)")
    print()
    print("   LO QUE ESTO ACOTA: un router elige PARADIGMA. Sólo puede pelear por la")
    print("   varianza que el paradigma explica — la de tarea no la mueve nadie, y la de")
    print("   réplica es ruido. Si la de paradigma es chica frente al ruido, no hay")
    print("   política que gane, y el problema no es el aprendizaje.")

    # ---------------------------------------------------------------- 5
    print("\n" + "=" * 78)
    print("5. ATÍPICOS — celdas lejos de la mediana de su tarea\n")
    atip = []
    for t, _ in [(k[0], 0) for k in med]:
        pass
    portarea_med = collections.defaultdict(list)
    for (t, p), m in med.items():
        portarea_med[t].append((p, m))
    for t, lst in portarea_med.items():
        vals = [m for _, m in lst]
        if len(vals) < 4:
            continue
        mu = statistics.median(vals)
        for p, m in lst:
            if abs(m - mu) >= 0.6:
                atip.append((abs(m - mu), t, p, m, mu))
    for d, t, p, m, mu in sorted(atip, reverse=True)[:12]:
        print(f"   {t:<16}{p:<17}u={m:.3f}   mediana de la tarea {mu:.3f}   Δ={m-mu:+.3f}")
    print(f"\n   {len(atip)} celdas a 0,6 o más de la mediana de su tarea. Ahí es donde un")
    print("   router podría ganar algo — y también donde suele estar el defecto.")


if __name__ == "__main__":
    main()
