"""Las dos figuras que faltaban: el sensor determinista, y qué señal explica la interacción.

POR QUÉ ESTAS DOS Y NO OTRAS. Eran los dos resultados nuevos sin figura, y los dos son
difíciles de leer como tabla por el mismo motivo: **lo que importa no es un número sino la
relación entre dos**.

  1. **el sensor determinista** — la afirmación es que sacarle una decisión de flujo al
     modelo mejora la utilidad *y* el determinismo A LA VEZ. Son dos ejes que suben juntos,
     y en una tabla eso son dos columnas que el lector tiene que cruzar a mano. Con las
     réplicas dibujadas una por una se ve además POR QUÉ: el antes no es «peor en promedio»,
     es **inestable**
  2. **los predictores** — cada señal tiene un valor observado y un nulo, y la pregunta es
     si el primero le gana al segundo. Una tabla de cuatro columnas obliga a hacer la resta;
     una barra contra su banda de nulo la muestra. Y la corrección por selección —que la
     vara no es el nulo propio sino el MÁXIMO de los nulos— es geométrica: una segunda línea

EL «ANTES» SE LEE DEL RESPALDO FECHADO, no se transcribe. Si el número del paper y el del
respaldo se separan, esta figura lo muestra en vez de esconderlo.

Corre DESDE `lab/`:  py bench/analysis/_figuras_sensor.py
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import glob
import json
import statistics
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from bench.analysis._estilo import COLOR, GRIS, SUAVE, TINTA, aplicar, guardar, titular

ANTES = "results/terra/gold_h1_rows.jsonl.bak-pointer_chase-*"
DESPUES = "results/terra/gold_h1_rows.jsonl"
TAREAS = ["c3-000-h1", "c3-001-h2", "c3-002-h3"]
ETIQ = {"c3-000-h1": "1 salto", "c3-001-h2": "2 saltos", "c3-002-h3": "3 saltos"}


def _replicas(ruta: str, brazo: str) -> dict[str, list[float]]:
    d: dict[str, list[float]] = defaultdict(list)
    with open(ruta, encoding="utf-8") as fh:
        for linea in fh:
            r = json.loads(linea)
            if r["paradigm"] == brazo and r["task_id"] in TAREAS and not r.get("infeasible"):
                d[r["task_id"]].append(r.get("utility", 0.0))
    return d


# ── 1. el sensor determinista ───────────────────────────────────────────────────
def fig_sensor() -> None:
    respaldos = sorted(glob.glob(ANTES))
    if not respaldos:
        raise SystemExit(f"sin respaldo del ANTES ({ANTES}) — la figura no se inventa")
    antes = _replicas(respaldos[0], "pointer_chase")
    despues = _replicas(DESPUES, "pointer_chase")

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(10.4, 4.9),
                                  gridspec_kw={"width_ratios": [1.35, 1]})

    # IZQUIERDA: cada replica, un punto. Es lo que hace visible que el «antes» no era peor
    # en promedio sino INESTABLE — y la inestabilidad es la mitad del hallazgo.
    for i, t in enumerate(TAREAS):
        for x, (datos, color, lado) in enumerate(
                ((antes, GRIS, -0.13), (despues, COLOR["vueltas"], 0.13))):
            us = datos.get(t, [])
            for j, u in enumerate(us):
                ax.scatter(i + lado + (j - 1) * 0.045, u, s=95, color=color,
                           alpha=0.85, edgecolor="white", linewidth=1.2, zorder=3)
            if us:
                ax.plot([i + lado - 0.075, i + lado + 0.075],
                        [statistics.mean(us)] * 2, color=color, linewidth=2.6, zorder=4)
    ax.set_xticks(range(len(TAREAS)))
    ax.set_xticklabels([ETIQ[t] for t in TAREAS])
    ax.set_ylim(-0.09, 1.12)
    ax.set_yticks([0, 0.5, 1.0])
    ax.set_ylabel("utilidad (una réplica por punto, la raya es la media)")
    ax.grid(axis="y", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.annotate("antes", xy=(0 - 0.13, 1.06), ha="center", fontsize=9.5, color=GRIS)
    ax.annotate("después", xy=(0 + 0.13, 1.06), ha="center", fontsize=9.5,
                color=COLOR["vueltas"])
    titular(ax, "El antes no era peor en promedio: era inestable",
            "`pointer_chase` sobre la celda de cadenas acopladas")

    # DERECHA: los dos ejes que suben juntos, que es la afirmacion.
    ma = statistics.mean(statistics.mean(antes[t]) for t in TAREAS if t in antes)
    md = statistics.mean(statistics.mean(despues[t]) for t in TAREAS if t in despues)
    pa = sum(1 for t in TAREAS if antes.get(t) and all(u >= 0.999 for u in antes[t]))
    pd_ = sum(1 for t in TAREAS if despues.get(t) and all(u >= 0.999 for u in despues[t]))
    pa, pd_ = pa / len(TAREAS), pd_ / len(TAREAS)
    for x, (va, vd, nombre) in enumerate((
            (ma, md, "utilidad\n(pass@1)"), (pa, pd_, "consistencia\n(pass^3)"))):
        ax2.plot([x, x], [va, vd], color=SUAVE, linewidth=2.4, zorder=1)
        ax2.scatter(x, va, s=150, color=GRIS, zorder=3, edgecolor="white", linewidth=1.3)
        ax2.scatter(x, vd, s=190, color=COLOR["vueltas"], zorder=3, edgecolor="white",
                    linewidth=1.3)
        ax2.annotate(f"{va:.2f}", (x, va), xytext=(-13, -4), textcoords="offset points",
                     ha="right", fontsize=9.5, color=GRIS)
        ax2.annotate(f"{vd:.2f}", (x, vd), xytext=(13, -4), textcoords="offset points",
                     ha="left", fontsize=10, color=TINTA)
    ax2.set_xticks([0, 1])
    ax2.set_xticklabels(["utilidad\n(pass@1)", "consistencia\n(pass^3)"])
    ax2.set_xlim(-0.55, 1.55)
    ax2.set_ylim(-0.08, 1.12)
    ax2.set_yticks([0, 0.5, 1.0])
    ax2.grid(axis="y", alpha=0.5, zorder=0)
    ax2.set_axisbelow(True)
    titular(ax2, "Y suben los dos", "cuatro correcciones, ninguna de fraseo")
    fig.subplots_adjust(wspace=0.28)
    guardar(fig, "sensor-determinista")


# ── 2. qué señal explica la interacción ─────────────────────────────────────────
# LOS NUMEROS SALEN DE `_predictores.py`, y se transcriben acá con su fecha porque ese
# analisis tarda minutos (2.000 permutaciones x 10 senales x 2 paneles). Si cambian, esta
# constante es el unico lugar que hay que tocar, y la discrepancia se ve al re-correrlo.
PREDICTORES = [  # (senal, explica, nulo p95, sobrevive_correccion)
    ("la celda (cota superior)", 0.466, 0.205, None),
    ("cardinalidad × término", 0.309, 0.146, True),
    ("cardinalidad", 0.198, 0.083, False),
    ("región (la de hoy)", 0.138, 0.127, False),
    ("acoplamiento", 0.064, 0.037, False),
    ("término literal", 0.052, 0.061, False),
    ("n_units (bins)", 0.051, 0.061, False),
    ("irreversible|shared", 0.037, 0.062, False),
    ("cobertura exigida", 0.034, 0.035, False),
    ("el material cabe", 0.016, 0.039, False),
]
MAX_NULO_P95 = 0.148  # el maximo de los 9 nulos por permutacion — la vara correcta


def fig_predictores() -> None:
    """La versión corregida. La primera tenía cuatro defectos y los cuatro son de lectura:

      · el subtítulo de dos líneas se montaba sobre el título — `titular` reserva espacio
        para UNA línea, así que un `\\n` ahí lo rompe
      · la anotación de la vara caía encima de las barras, tapando justo la que gana
      · la etiqueta del valor chocaba con la raya del nulo cuando los dos quedan cerca
      · y el peor: `cardinalidad` figuraba en el mismo azul que las que superan su nulo,
        cuando el punto de la figura es que **no sobrevive la corrección**. El color decía
        lo contrario del texto
    """
    fig, ax = plt.subplots(figsize=(9.6, 6.0))
    nombres = [p[0] for p in PREDICTORES][::-1]
    ys = list(range(len(nombres)))
    for y, (nombre, obs, nulo, sobrevive) in zip(ys, PREDICTORES[::-1]):
        cota = nombre.startswith("la celda")
        # TRES ESTADOS Y TRES COLORES, y la distinción es la figura entera:
        #   verde  = cruza la vara corregida — la única que se puede afirmar
        #   azul   = le gana a SU nulo y NO a la vara. Es la falacia dibujada
        #   gris   = ni siquiera a su propio nulo
        color = (SUAVE if cota else COLOR["estructural"] if sobrevive
                 else COLOR["vueltas"] if obs > nulo else GRIS)
        ax.barh(y, obs, height=0.58, color=color, zorder=3,
                edgecolor="white", linewidth=1.1)
        ax.plot([nulo, nulo], [y - 0.33, y + 0.33], color=TINTA, linewidth=1.7, zorder=5)
        # La etiqueta va SIEMPRE al final de la barra y con aire suficiente para que la
        # raya del nulo nunca le caiga encima, aunque nulo y obs casi coincidan.
        # LA ETIQUETA VA DESPUES DE LO QUE ESTE MAS A LA DERECHA, barra o nulo. Cuando el
        # nulo SUPERA a la barra —las cinco de abajo, que es el caso interesante— anclarla
        # al fin de la barra la dejaba justo debajo de la raya.
        ax.annotate(f"{obs:.3f}", (max(obs, nulo), y), xytext=(9, 0),
                    textcoords="offset points", va="center", fontsize=9.2,
                    color=TINTA, zorder=6)
    ax.axvline(MAX_NULO_P95, color="#b5495b", linewidth=1.9, linestyle=(0, (5, 3)),
               zorder=4)
    # LA ANOTACION VA ARRIBA DE TODAS LAS BARRAS, en el aire que deja `ylim`.
    ax.annotate("la vara correcta: el MÁXIMO\nde los 9 nulos por permutación",
                xy=(MAX_NULO_P95, len(nombres) - 0.30), xytext=(8, 0),
                textcoords="offset points", fontsize=8.8, color="#b5495b",
                va="center", ha="left")
    ax.set_yticks(ys)
    ax.set_yticklabels(nombres, fontsize=9.5)
    ax.set_ylim(-0.7, len(nombres) - 0.05)
    ax.set_xlim(0, 0.56)
    ax.set_xlabel("fracción de la interacción (γ) que la señal explica")
    ax.grid(axis="x", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)
    titular(ax, "Una sola señal le gana al azar cuando se corrige por selección",
            "la raya negra sobre cada barra es su propio nulo (p95)")
    # La leyenda de colores explica la distinción que el texto hace, y va abajo del eje
    # para no competir con los datos.
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(facecolor=COLOR["estructural"], label="cruza la vara corregida"),
        Patch(facecolor=COLOR["vueltas"], label="le gana a SU nulo, no a la vara"),
        Patch(facecolor=GRIS, label="ni a su propio nulo"),
        Patch(facecolor=SUAVE, label="cota superior (no es candidata)"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=4, fontsize=8.5,
        handlelength=1.3, columnspacing=1.5)
    guardar(fig, "predictores-de-la-interaccion")


def main() -> None:
    aplicar()
    fig_sensor()
    fig_predictores()


if __name__ == "__main__":
    main()
