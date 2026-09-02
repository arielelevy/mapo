"""EL RECTÁNGULO ENTERO, CELDA POR CELDA: dónde vive la interacción tarea × brazo. Cero llamadas.

QUÉ MUESTRA. §6.2 afirma dos cosas que una tabla de medias no puede mostrar juntas: que la
interacción `γ` es grande (45% de la varianza) y que **no vale premio** porque vive entre los
brazos que nadie elegiría. Un mapa de calor de las 64 × 8 celdas las muestra en una imagen:

  · izquierda, la utilidad `u(tarea, brazo)` cruda, con las tareas agrupadas por región y los
    brazos ordenados por su media. Los tres contendientes son tres columnas casi iguales; las
    columnas de la derecha son las que cambian de color fila a fila.
  · derecha, el residuo `γ = u − μ − α(tarea) − β(brazo)`: lo que queda cuando se descuenta
    qué tan difícil es la tarea y qué tan bueno es el brazo. Ahí se ve dónde está la
    interacción, y está a la derecha, no entre los contendientes.

El punto negro marca el mejor brazo de cada fila: cuando cae sobre una columna de la izquierda
en casi todas las filas, el oráculo por tarea casi no le gana al mejor fijo.

LOS NÚMEROS SE CALCULAN DEL REGISTRO con el mismo rectángulo mecánico que el resto del paper
(`bench.panel.rectangulo`), no se transcriben.

Corre DESDE `lab/`:  py bench/analysis/_figura_calor.py
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import collections
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from app.runner import load_rows
from bench.analysis._estilo import GRIS, SUAVE, TINTA, aplicar, guardar, titular
from bench.panel import rectangulo

REGISTRO = Path("results/luna/gold_h1_rows.jsonl")

# Abreviatura legible de la región para el margen izquierdo.
ABREV = {"many": "muchas", "few": "pocas", "no_oracle": "sin oráculo", "oracle": "oráculo",
         "loose": "", "tight": "acoplada", "flat": "", "chain": "cadena",
         "no_lit": "", "lit_present": "literal", "lit_absent": "literal ausente"}


def etiqueta(region: str) -> str:
    partes = [ABREV.get(p, p) for p in region.split("/")]
    return " · ".join(p for p in partes if p)


def main() -> None:
    filas = load_rows(REGISTRO)
    panel = rectangulo(filas)
    reps = collections.defaultdict(list)
    region = {}
    for f in filas:
        if f.get("infeasible"):
            continue
        reps[(f["task_id"], f["paradigm"])].append(float(f.get("utility", 0.0)))
        region[f["task_id"]] = f["region"]
    U = {k: statistics.mean(v) for k, v in reps.items()}

    brazos = sorted(panel.brazos, key=lambda p: -statistics.mean(U[(t, p)] for t in panel.tareas))
    # Regiones por tamaño, y adentro de cada región las tareas por su media.
    por_region = collections.defaultdict(list)
    for t in panel.tareas:
        por_region[region[t]].append(t)
    regiones = sorted(por_region, key=lambda r: (-len(por_region[r]), r))
    tareas = [t for r in regiones
              for t in sorted(por_region[r], key=lambda t: -statistics.mean(U[(t, p)] for p in brazos))]

    M = np.array([[U[(t, p)] for p in brazos] for t in tareas])
    mu = M.mean()
    alpha = M.mean(axis=1, keepdims=True) - mu
    beta = M.mean(axis=0, keepdims=True) - mu
    G = M - mu - alpha - beta
    mejor = M.argmax(axis=1)

    ora = float(M.max(axis=1).mean())
    fijo = float(M.mean(axis=0).max())
    var = {"α": float(np.var(alpha, ddof=1)), "β": float(np.var(beta, ddof=1)),
           "γ": float(np.var(G, ddof=1))}
    tot = sum(var.values())

    aplicar()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.2, 11.8), sharey=True,
                                   gridspec_kw={"wspace": 0.06})

    im1 = ax1.imshow(M, aspect="auto", cmap="Greys", vmin=0.0, vmax=1.0, interpolation="nearest")
    lim = float(np.abs(G).max())
    im2 = ax2.imshow(G, aspect="auto", cmap="BrBG", vmin=-lim, vmax=lim, interpolation="nearest")

    for ax in (ax1, ax2):
        ax.scatter(mejor, np.arange(len(tareas)), s=14, color="black", zorder=3)
        # los brazos van ARRIBA, con su media debajo del nombre; abajo queda la barra de color
        ax.xaxis.tick_top()
        ax.set_xticks(range(len(brazos)))
        ax.set_xticklabels([f"{p}  {M[:, j].mean():.3f}" for j, p in enumerate(brazos)],
                           fontsize=8.6, rotation=90, ha="center", va="bottom")
        ax.tick_params(axis="x", length=0, pad=4)
        ax.set_yticks([])
        for s_ in ax.spines.values():
            s_.set_visible(False)
        y = -0.5
        for r in regiones:
            y += len(por_region[r])
            ax.axhline(y, color="white", linewidth=1.6)
        ax.add_patch(plt.Rectangle((-0.5, -0.5), 3, len(tareas), fill=False,
                                   edgecolor=TINTA, linewidth=1.1, linestyle=(0, (3, 2))))

    y = -0.5
    for r in regiones:
        n = len(por_region[r])
        ax1.text(-0.65, y + n / 2, f"{etiqueta(r)}  ({n})", ha="right", va="center",
                 fontsize=8.4, color=GRIS)
        y += n

    # Un solo título para la figura: el hallazgo. Debajo, cómo leerla. Cada panel lleva
    # sólo su nombre corto, porque dos títulos largos lado a lado se pisan.
    fig.text(0.02, 0.985,
             f"La interacción tarea × brazo es el {var['γ'] / tot:.0%} de la varianza y vive fuera del marco:"
             + chr(10) +
             f"el mejor brazo cae en un contendiente en {int((mejor < 3).sum())} de {len(tareas)} tareas",
             fontsize=12, color=TINTA, ha="left", va="top", wrap=True)
    fig.text(0.02, 0.958,
             f"Rectángulo 64 × 8, filas agrupadas por región y columnas por media. El punto es el mejor brazo de la fila;"
             + chr(10) +
             f"el marco punteado, los tres contendientes (a menos de 0,05 del mejor fijo). "
             f"Oráculo por tarea {ora:.3f}, mejor fijo {fijo:.3f}.",
             fontsize=9.5, color=GRIS, ha="left", va="top")
    ax1.set_title("u(tarea, brazo)", fontsize=10, color=TINTA, loc="left", pad=8)
    ax2.set_title("γ = u − μ − α(tarea) − β(brazo)", fontsize=10, color=TINTA, loc="left", pad=8)

    cb1 = fig.colorbar(im1, ax=ax1, fraction=0.022, pad=0.015, location="bottom", aspect=40)
    cb1.set_label("utilidad", fontsize=8.5, color=GRIS)
    cb1.ax.tick_params(labelsize=8, color=GRIS)
    cb2 = fig.colorbar(im2, ax=ax2, fraction=0.022, pad=0.015, location="bottom", aspect=40)
    cb2.set_label("γ: marrón por debajo de lo esperado, verde por encima", fontsize=8.5, color=GRIS)
    cb2.ax.tick_params(labelsize=8, color=GRIS)
    fig.subplots_adjust(top=0.775, bottom=0.05, left=0.22, right=0.985)

    fig.savefig("../whitepaper/figuras/mapa-de-calor-rectangulo.svg", format="svg", bbox_inches=None)
    plt.close(fig)
    print("ok  mapa-de-calor-rectangulo.svg")
    print(f"  tareas {len(tareas)} · brazos {brazos}")
    print(f"  oráculo {ora:.3f} · mejor fijo {fijo:.3f} · brecha {ora - fijo:+.3f}")
    print("  varianza cruda:", {k: f"{v:.4f} ({v / tot:.0%})" for k, v in var.items()})
    print("  mejor de la fila cae en un contendiente:", int((mejor < 3).sum()), "de", len(tareas))


if __name__ == "__main__":
    main()
