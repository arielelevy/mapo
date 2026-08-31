"""La ley de costo, que el paper afirma en prosa y no tenía figura. Cero llamadas al modelo.

LA AFIRMACIÓN QUE DIBUJA: el costo de un bucle de herramientas crece como `N²` y la cobertura
como `N`, porque **la conversación se reenvía entera en cada vuelta**. Está en el paper desde
el principio, sostenida por dos números sueltos —«≤2 llamadas dan 9.779 tokens, ≥8 dan
136.432»— y esos dos números son compatibles con crecimiento lineal si uno no mira el resto.

POR QUÉ HACEN FALTA DOS PANELES, y es el punto entero:

  · el de la izquierda muestra el TOTAL contra el número de llamadas, con las curvas de
    referencia `N` y `N²` ancladas en el primer punto. Un total creciente no distingue
    «cada llamada cuesta lo mismo y hay más llamadas» de «cada llamada cuesta más»
  · el de la derecha muestra el costo POR LLAMADA **dentro de cada brazo**, y ahí la
    distinción es visual: **si no hubiera reenvío, esas líneas serían planas**

Y VA POR BRAZO PORQUE AGREGADO ESTÁ CONFUNDIDO, que es un defecto que tuvo la primera
versión de esta figura. Sobre todos los brazos juntos, la curva zigzaguea —7.411, 18.654,
29.528, 13.815, 19.113— porque distintos brazos dominan distintos conteos de llamadas y sus
alcances difieren en un orden de magnitud: «más llamadas» y «qué brazo» quedan mezclados, y
el zigzag es la mezcla, no el fenómeno. Condicionado por brazo el trazo se ordena y sube
monótono en tres de los cuatro que tienen suficientes puntos: `dag_strategy` va de 4.002 a
15.592 (**3,9×**) y `pointer_chase` de 1.544 a 4.107

LO QUE NO ES. No es un ajuste: no se estima ningún exponente ni se reporta un `R²`. Las dos
curvas de referencia están para que el ojo compare, y el hallazgo es cualitativo y robusto —
la línea de la derecha sube—. Estimar un exponente sobre doce puntos con `n` desparejo (de 26
a 540 filas por punto) daría una cifra con más precisión aparente que evidencia.

Y EL `n` DE CADA PUNTO SE DIBUJA, como área del marcador: el punto de 12 llamadas descansa en
112 filas y el de 11 en 26, y un lector que no lo vea les da el mismo peso.

Corre DESDE `lab/`:  py bench/analysis/_figura_ley_costo.py
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.runner import load_rows
from bench.analysis._estilo import (COLOR, GRIS, SUAVE, TINTA, aplicar, color_de,
                                    guardar, miles, titular)

REGISTRO = Path("results/luna/gold_h1_rows.jsonl")
TOPE = 12          # por encima, la cola tiene muy pocas filas por punto
MIN_POR_BRAZO = 15  # el mismo criterio, por brazo
MIN_FILAS = 20     # un punto con menos filas no se dibuja: sería ruido con forma de dato


def main() -> None:
    aplicar()
    por_llamadas: dict[int, list[int]] = defaultdict(list)
    for f in load_rows(REGISTRO):
        if f.get("infeasible"):
            continue
        c = f.get("calls") or 0
        if c >= 1:
            por_llamadas[min(c, TOPE)].append(f.get("prompt_tokens") or 0)

    xs = sorted(c for c in por_llamadas if len(por_llamadas[c]) >= MIN_FILAS)
    tot = [statistics.mean(por_llamadas[c]) for c in xs]
    por = [t / c for t, c in zip(tot, xs)]
    ns = [len(por_llamadas[c]) for c in xs]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(10.6, 4.8))

    # ── izquierda: el total, contra N y N^2 ────────────────────────────────────
    # LAS REFERENCIAS SE ANCLAN EN EL PRIMER PUNTO, que es la única forma de compararlas
    # sin ajustar nada: las dos pasan por ahí por construcción, y lo que se mira es cómo se
    # abren después.
    x0, y0 = xs[0], tot[0]
    ax.plot(xs, [y0 * (c / x0) for c in xs], linestyle=(0, (5, 3)), color=SUAVE,
            linewidth=1.6, zorder=1)
    ax.plot(xs, [y0 * (c / x0) ** 2 for c in xs], linestyle=(0, (2, 2)), color=SUAVE,
            linewidth=1.6, zorder=1)
    ax.annotate("N", (xs[-1], y0 * (xs[-1] / x0)), xytext=(6, -2),
                textcoords="offset points", fontsize=9.5, color=GRIS, va="center")
    ax.annotate("N²", (xs[-1], y0 * (xs[-1] / x0) ** 2), xytext=(6, -2),
                textcoords="offset points", fontsize=9.5, color=GRIS, va="center")
    ax.plot(xs, tot, color=COLOR["vueltas"], linewidth=2.0, zorder=3)
    ax.scatter(xs, tot, s=[18 + n * 0.35 for n in ns], color=COLOR["vueltas"],
               edgecolor="white", linewidth=1.2, zorder=4)
    ax.set_xlabel("llamadas al modelo en la celda")
    ax.set_ylabel("tokens de entrada por celda")
    ax.yaxis.set_major_formatter(miles)
    ax.set_ylim(0, max(tot) * 1.55)
    ax.grid(axis="y", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)
    titular(ax, "El total crece más que lineal",
            "área del punto = filas que lo sostienen · referencias ancladas en el 1er punto")

    # ── derecha: el costo POR llamada, DENTRO de cada brazo ────────────────────
    por_brazo: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
    for f in load_rows(REGISTRO):
        if f.get("infeasible"):
            continue
        c = f.get("calls") or 0
        if c >= 1:
            por_brazo[f["paradigm"]][min(c, TOPE)].append(f.get("prompt_tokens") or 0)

    dibujados = 0
    for p_, series in sorted(por_brazo.items()):
        pts = [(c, statistics.mean(v) / c) for c, v in sorted(series.items())
               if len(v) >= MIN_POR_BRAZO]
        # UN BRAZO CON MENOS DE CUATRO PUNTOS NO TRAZA UNA TENDENCIA: traza una recta entre
        # dos ruidos. Se omite en vez de dibujarse tenue, porque una línea tenue igual se lee.
        if len(pts) < 4:
            continue
        dibujados += 1
        cx = [c for c, _ in pts]
        cy = [v for _, v in pts]
        col = color_de(p_)
        ax2.plot(cx, cy, color=col, linewidth=1.9, zorder=3, marker="o",
                 markersize=5, markeredgecolor="white", markeredgewidth=1.1)
        ax2.annotate(p_, (cx[-1], cy[-1]), xytext=(7, 0), textcoords="offset points",
                     va="center", fontsize=9, color=col)
    ax2.set_xlabel("llamadas al modelo en la celda")
    ax2.set_ylabel("tokens de entrada POR llamada")
    ax2.yaxis.set_major_formatter(miles)
    ax2.set_xlim(2.2, 13.8)
    ax2.grid(axis="y", alpha=0.5, zorder=0)
    ax2.set_axisbelow(True)
    titular(ax2, "Y dentro de un brazo, cada llamada cuesta más",
            "si no hubiera reenvío estas líneas serían planas · "
            f"{dibujados} brazos con ≥4 puntos de ≥{MIN_POR_BRAZO} filas")

    fig.subplots_adjust(wspace=0.30)
    guardar(fig, "ley-de-costo")

    print(f"  puntos dibujados: {xs}")
    print(f"  filas por punto:  {ns}")
    print(f"  costo por llamada, agregado (CONFUNDIDO): {por[0]:,.0f} -> {por[-1]:,.0f}")


if __name__ == "__main__":
    main()
