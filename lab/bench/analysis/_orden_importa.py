"""¿El ORDEN de las herramientas dice algo que el histograma no? Cero llamadas al modelo.

LA AFIRMACIÓN QUE ESTO PONE A PRUEBA está escrita en `tools.py`, en el docstring del campo
`sequence`, y nunca se verificó:

    «`calls` es un conteo, y un conteo no distingue "busco, leo, busco, leo" de
     "busco, busco, leo, leo" — que son dos estrategias distintas con el mismo histograma.
     La secuencia es lo único que permite aprender asociaciones (tool_i -> tool_j), que es
     donde el aprendizaje Hebbiano tiene contenido propio: una asociación entre PARES no se
     reduce a una estadística marginal de un brazo.»

Es la justificación de guardar la secuencia **y** de que la plasticidad de `MAP.md` tenga
algo propio que aportar. Si es falsa, guardar el orden es guardar ruido y el aprendizaje por
pares no tiene dónde agarrarse.

EL DISEÑO, y es lo que lo hace una prueba y no una correlación. **Se comparan filas con el
MISMO multiconjunto de herramientas y distinto orden.** Eso controla el histograma por
construcción, sin modelo ni regresión: si dos filas llamaron exactamente a las mismas
herramientas la misma cantidad de veces, todo lo que las distingue es la secuencia.

  · dentro de cada grupo (mismo brazo, misma tarea, mismo multiconjunto) se mide la
    dispersión de utilidad ENTRE órdenes distintos
  · y se la compara contra la dispersión entre RÉPLICAS del mismo orden, que es el ruido
  · si la primera no supera a la segunda, el orden no dice nada que el conteo no diga

LA TRAMPA QUE EVITA: correlacionar bigramas con utilidad sobre todo el registro daría señal
aunque el orden no importe, porque los brazos que usan ciertos pares son también los que
puntúan distinto. La comparación pareada mata ese confundido de raíz.

Corre DESDE `lab/`:  py bench/analysis/_orden_importa.py
"""

from __future__ import annotations

import collections
import json
import statistics
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def filas_de(ruta: _Path) -> list[dict]:
    """Lee tolerando una última línea a medio escribir: el archivo puede estar creciendo."""
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


def main() -> None:
    filas = [f for f in filas_de(_Path("results/luna/gold_h1_rows.jsonl"))
             if not f.get("infeasible") and not f.get("infra_error")]

    # (brazo, tarea, multiconjunto) -> {orden: [utilidades]}
    grupos: dict[tuple, dict[tuple, list[float]]] = collections.defaultdict(
        lambda: collections.defaultdict(list))
    con_secuencia = 0
    for f in filas:
        seq = ((f.get("tool_usage") or {}).get("sequence")) or []
        if len(seq) < 2:
            continue
        con_secuencia += 1
        multi = tuple(sorted(collections.Counter(seq).items()))
        grupos[(f["paradigm"], f["task_id"], multi)][tuple(seq)].append(f["utility"])

    print("=" * 94)
    print("¿EL ORDEN DICE ALGO QUE EL HISTOGRAMA NO?")
    print("=" * 94)
    print(f"\n  {len(filas):,} filas · {con_secuencia:,} con secuencia de 2+ llamadas")

    # ENTRE ORDENES: dispersion de la utilidad media de cada orden, dentro del grupo.
    # ENTRE REPLICAS: dispersion dentro de un mismo orden. Es el ruido, y es la vara.
    entre_ordenes, entre_replicas = [], []
    grupos_utiles = 0
    for clave, por_orden in grupos.items():
        if len(por_orden) >= 2:
            grupos_utiles += 1
            medias = [statistics.mean(v) for v in por_orden.values()]
            entre_ordenes.append(statistics.pvariance(medias))
        for v in por_orden.values():
            if len(v) >= 2:
                entre_replicas.append(statistics.pvariance(v))

    print(f"  {len(grupos):,} grupos (brazo x tarea x multiconjunto)")
    print(f"  {grupos_utiles:,} con DOS O MAS ordenes distintos del mismo multiconjunto")

    if not entre_ordenes or not entre_replicas:
        print("\n  >>> NO HAY MATERIAL PARA LA PRUEBA en este registro.")
        return

    vo = statistics.mean(entre_ordenes)
    vr = statistics.mean(entre_replicas)
    print(f"\n  varianza de utilidad ENTRE ORDENES (mismo histograma)  {vo:.4f}")
    print(f"  varianza de utilidad ENTRE REPLICAS (mismo orden)      {vr:.4f}")
    razon = vo / vr if vr else float("inf")
    print(f"  razon                                                  {razon:.2f}")
    print(f"\n  >>> {'EL ORDEN DICE ALGO' if razon > 1.5 else 'EL ORDEN NO SUPERA AL RUIDO'}")

    # ── ¿Y QUE PARES? Solo si el orden dice algo, mirar cuales ──────────────
    print("\n" + "=" * 94)
    print("LOS PARES, Y SI ALGUNO SE ASOCIA CON GANAR — pareado por brazo y tarea")
    print("=" * 94)
    print("""
  Un bigrama que aparece mas en las filas buenas no prueba nada por si solo: los brazos que
  lo usan son otros brazos. Se compara DENTRO de (brazo, tarea): entre las replicas de una
  misma celda, las que usaron el par contra las que no.
""")
    pares = collections.defaultdict(lambda: {"con": [], "sin": []})
    por_celda = collections.defaultdict(list)
    for f in filas:
        seq = ((f.get("tool_usage") or {}).get("sequence")) or []
        if len(seq) >= 2:
            por_celda[(f["paradigm"], f["task_id"])].append((seq, f["utility"]))
    for celda, v in por_celda.items():
        if len(v) < 2:
            continue
        todos = {(a, b) for seq, _ in v for a, b in zip(seq, seq[1:])}
        for par in todos:
            con = [u for seq, u in v if par in set(zip(seq, seq[1:]))]
            sin = [u for seq, u in v if par not in set(zip(seq, seq[1:]))]
            if con and sin:
                pares[par]["con"].append(statistics.mean(con))
                pares[par]["sin"].append(statistics.mean(sin))

    filas_par = []
    for par, d in pares.items():
        if len(d["con"]) < 5:
            continue
        delta = statistics.mean(d["con"]) - statistics.mean(d["sin"])
        filas_par.append((par, len(d["con"]), delta))
    if not filas_par:
        print("  (ningun par aparece en 5+ celdas con y sin: no hay con que comparar)")
    else:
        print(f"  {'par (tool_i -> tool_j)':40s} {'celdas':>7s} {'delta u':>9s}")
        for par, n, d in sorted(filas_par, key=lambda x: -abs(x[2]))[:12]:
            print(f"  {par[0] + ' -> ' + par[1]:40s} {n:7d} {d:+9.3f}")
        print(f"""
  COMO LEER: `delta u` es cuanto mas (o menos) puntua una replica que uso ese par, contra
  otra replica de LA MISMA celda que no lo uso. Pareado, asi que el brazo y la tarea estan
  controlados. Un delta grande con pocas celdas es ruido; lo que interesa es un delta que
  se sostenga sobre muchas.""")


if __name__ == "__main__":
    main()
