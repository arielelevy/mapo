"""Las figuras por rama, con el sistema visual de `_estilo.py`. Cero llamadas al modelo.

QUÉ SE GRAFICA COMO ÁREA Y QUÉ NO, que es la decisión que hace honesta a la figura.
`bench/oneoff/_plot_areas.py` ya fijó la regla y ésta la respeta:

    Un área apilada afirma «partes de un todo sobre un eje ordenado». Usarla para otra
    cosa miente con la FORMA antes de mentir con los números.

Por eso acá **no** hay un área de utilidad por paradigma: doce paradigmas sobre una tarea no
son partes de un todo, son doce mediciones alternativas de la misma cosa, y apilarlas
inventa una suma que no existe.

Y POR LA MISMA REGLA SE DESCARTÓ UNA FIGURA QUE YA ESTABA HECHA: un área de en qué se le va
el presupuesto a cada brazo. Medido, la entrada es el **96,4%–100,9%** del costo en todos los
brazos y la salida va de 0% a 3,6%. **No hay composición que mostrar**, y dibujar una donde
una parte es el 99% es llenar el espacio. Que la entrada sea todo el costo es un hallazgo de
una línea —los paradigmas no se diferencian en lo que GENERAN sino en lo que ARRASTRAN al
prompt— y quedó como frase en el paper, no como gráfico.

LAS TRES QUE QUEDARON:

  **1. Bueno donde aplica, contra lo que aporta** — dos puntos por brazo, y sólo cuando hay
  algo que separar. `direct` saca 0,917 donde corre y corre en el 6%.

  **2. Cómo se degrada cada brazo con el ancho** — SMALL MULTIPLES. Nueve líneas en un solo
  panel eran espagueti: etiquetas pisadas y colores repetidos, porque el color codifica la
  clase de costo y hay seis brazos en la misma clase. Un panel por brazo, con los demás en
  gris de fondo, deja ver a la vez la forma individual y la comparación.

  **3. Utilidad contra costo** — dispersión con frontera de Pareto. La frontera es lo que
  convierte una nube en una afirmación: qué brazos NO están dominados.

Corre DESDE `lab/`:  py bench/analysis/_figuras_ramas.py
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

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from bench.analysis._estilo import (GRIS, SUAVE, TINTA, aplicar, color_de, guardar,
                                    leyenda_clases, miles, titular)

SALIDA = _Path("../whitepaper/figuras")
# LOS TRES ANCHOS REALES, Y `base` NO ES UNO. Estaba incluido como si fuera el extremo
# angosto del eje, y **no es un ancho**: agrupa `C1` (1 unidad), `C7` y `W1` (8-9) y `C3`
# (60). Un eje que mezcla 1 con 60 no esta ordenado, y toda la premisa de la figura —«que
# pasa cuando el material CRECE»— se cae con el.
#
# Lo destapo la propia figura: con `base` adentro, `handoff` y `graph_traverse` figuraban
# SIN degradarse punta a punta y el titulo decia que solo `rewoo` aguantaba. Con el eje
# corregido —5 -> 20 -> 60 unidades— el titulo pasa a ser cierto: **todos caen menos
# `rewoo`**, que sube +0,06.
ANCHOS = ("w4", "w16", "w48")
UNIDADES = {"w4": 5, "w16": 20, "w48": 60}


def ancho_de(task_id: str) -> str | None:
    """El ancho declarado, o `None` si la tarea no pertenece al eje.

    `None` y no `"base"`: las tareas sin sufijo de ancho no son el extremo angosto, son un
    grupo heterogeneo que no tiene lugar en un eje ordenado por tamano.
    """
    for w in ("w48", "w16", "w4"):
        if task_id.endswith(w):
            return w
    return None


def cargar() -> list[dict]:
    filas = []
    for linea in _Path("results/luna/gold_h1_rows.jsonl").read_text(
            encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            filas.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    return filas


def main() -> None:
    aplicar()
    SALIDA.mkdir(parents=True, exist_ok=True)
    filas = cargar()
    vivas = [f for f in filas if not f.get("infeasible") and not f.get("infra_error")]

    u = collections.defaultdict(list)
    c = collections.defaultdict(list)
    leidas = collections.defaultdict(list)
    aplica, total = collections.Counter(), collections.Counter()
    por_ancho = collections.defaultdict(lambda: collections.defaultdict(list))
    for f in filas:
        total[f["paradigm"]] += 1
    for f in vivas:
        p = f["paradigm"]
        aplica[p] += 1
        u[p].append(f["utility"])
        c[p].append(f.get("cost_tokens") or 0)
        leidas[p].append((f.get("tool_usage") or {}).get("units_read_any") or 0)
        w = ancho_de(f["task_id"])
        if w:
            por_ancho[w][p].append(f["utility"])

    um = {p: statistics.mean(v) for p, v in u.items()}
    cm = {p: statistics.mean(v) for p, v in c.items()}
    cob = {p: aplica[p] / total[p] for p in total if aplica[p]}
    completos = sorted(
        [p for p in um if all(por_ancho[w].get(p) for w in ANCHOS)],
        key=lambda p: -um[p])
    print(f"{len(vivas):,} filas · {len(completos)} brazos comparables por ancho\n")

    # ═══ 1. BUENO DONDE APLICA, CONTRA LO QUE APORTA ════════════════════════
    orden = sorted([p for p in um if aplica[p] >= 10], key=lambda p: um[p] * cob[p])
    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    for y, p in enumerate(orden):
        col = color_de(p)
        ax.scatter(um[p], y, s=78, color=col, zorder=4, edgecolor="white", linewidth=1.1)
        # EL HUECO APARECE SOLO CUANDO HAY ALGO QUE SEPARAR. Un brazo que aplica siempre
        # tiene UN numero, y dibujarle dos superpuestos lo hace leer como el otro.
        if cob[p] < 0.999:
            ax.plot([um[p] * cob[p], um[p]], [y, y], color=col, alpha=0.3, linewidth=3,
                    zorder=1, solid_capstyle="round")
            ax.scatter(um[p] * cob[p], y, s=78, color="white", zorder=5, edgecolor=col,
                       linewidth=1.9)
            ax.text(um[p] + 0.018, y, f"aplica en {cob[p]:.0%}", va="center",
                    fontsize=8.5, color=GRIS)
    ax.set_yticks(range(len(orden)))
    ax.set_yticklabels(orden, fontsize=9.5, color=TINTA)
    ax.set_xlabel("utilidad")
    ax.set_xlim(0, 1.12)
    ax.set_ylim(-0.7, len(orden) - 0.3)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", alpha=0.55)
    ax.set_axisbelow(True)
    titular(ax, "Un paradigma tiene dos números, y colapsarlos esconde el caso extremo",
            "relleno: utilidad donde su mecanismo corre  ·  hueco: multiplicada por su "
            "cobertura")
    plt.tight_layout()
    guardar(fig, "aplica-contra-aporta")

    # ═══ 2. DEGRADACION — SMALL MULTIPLES ═══════════════════════════════════
    #
    # NUEVE LINEAS EN UN PANEL ERAN ESPAGUETI. El color codifica la clase de costo y hay
    # seis brazos en la clase «vueltas», asi que seis lineas del mismo azul se cruzaban y
    # las etiquetas del extremo derecho se pisaban. Un panel por brazo, con los demas de
    # fondo en gris, muestra a la vez la forma individual y la comparacion — que es
    # exactamente lo que un solo panel no podia.
    fil, cols = 3, 3
    fig, axes = plt.subplots(fil, cols, figsize=(9.2, 7.6), sharex=True, sharey=True)
    fondo = [[statistics.mean(por_ancho[w][q]) if por_ancho[w].get(q) else None
              for w in ANCHOS] for q in completos]
    for k, p in enumerate(completos):
        ax = axes[k // cols][k % cols]
        for serie in fondo:
            xs = [w for w, v in zip(ANCHOS, serie) if v is not None]
            ys = [v for v in serie if v is not None]
            ax.plot(xs, ys, color=SUAVE, linewidth=1.1, zorder=1)
        xs = [w for w in ANCHOS if por_ancho[w].get(p)]
        ys = [statistics.mean(por_ancho[w][p]) for w in xs]
        col = color_de(p)
        ax.plot(xs, ys, color=col, linewidth=2.4, zorder=3, solid_capstyle="round")
        ax.scatter(xs, ys, color=col, s=26, zorder=4, edgecolor="white", linewidth=0.9)
        ax.text(0.04, 0.09, f"{p}\n{ys[-1] - ys[0]:+.2f} de 5 a 60 unidades",
                transform=ax.transAxes, fontsize=8.5, color=TINTA, va="bottom",
                linespacing=1.6)
        ax.set_ylim(0.3, 1.0)
        ax.grid(axis="y", alpha=0.5)
        ax.set_axisbelow(True)
        ax.tick_params(length=0)
    for k in range(len(completos), fil * cols):
        axes[k // cols][k % cols].set_visible(False)
    fig.supylabel("utilidad media", fontsize=10, color=TINTA, x=0.015)
    fig.supxlabel("unidades en el alcance  ·  5 → 20 → 60", fontsize=10, color=TINTA)
    fig.suptitle("Casi todos se degradan cuando el material crece. `rewoo` no.",
                 fontsize=13, color=TINTA, x=0.06, ha="left", y=0.985)
    fig.text(0.06, 0.947, "un panel por brazo; los demás, en gris de fondo",
             fontsize=9.5, color=GRIS, ha="left")
    plt.tight_layout(rect=(0.015, 0.015, 1, 0.925))
    guardar(fig, "degradacion-por-ancho")

    # ═══ 3. UTILIDAD CONTRA COSTO, CON FRONTERA ═════════════════════════════
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    puntos = sorted(((cm[p], um[p], p) for p in completos), key=lambda t: t[0])
    # LA FRONTERA CONVIERTE UNA NUBE EN UNA AFIRMACION: que brazos NO estan dominados —
    # nadie es a la vez mas barato y mejor—. Sin ella el lector tiene que calcular la
    # dominancia a ojo, punto por punto.
    frontera, techo = [], -1.0
    for x, y, p in puntos:
        if y > techo:
            frontera.append((x, y, p))
            techo = y
    en_frontera = {p for _, _, p in frontera}
    ax.plot([x for x, _, _ in frontera], [y for _, y, _ in frontera],
            color=GRIS, linewidth=1.2, linestyle=(0, (4, 3)), zorder=1)
    for x, y, p in puntos:
        n = statistics.mean(leidas[p])
        ax.scatter(x, y, s=70 + n * 42, color=color_de(p),
                   alpha=0.9 if p in en_frontera else 0.4, zorder=3,
                   edgecolor="white", linewidth=1.2)
        ax.annotate(p, (x, y), textcoords="offset points", xytext=(11, 8), fontsize=9,
                    color=TINTA if p in en_frontera else GRIS)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(miles))
    ax.set_xlabel("tokens por celda  ·  escala logarítmica")
    ax.set_ylabel("utilidad media")
    ax.grid(axis="y", alpha=0.5)
    ax.set_axisbelow(True)
    ax.margins(x=0.17, y=0.18)
    titular(ax, "Diez veces el costo compra 0,18 de utilidad",
            "la línea punteada une los no dominados  ·  el tamaño es cuántas unidades "
            "llega a mirar")
    leyenda_clases(ax, loc="lower right")
    plt.tight_layout()
    guardar(fig, "utilidad-contra-costo")
    print(f"\n  frontera de Pareto: {[p for _, _, p in frontera]}")


if __name__ == "__main__":
    main()
