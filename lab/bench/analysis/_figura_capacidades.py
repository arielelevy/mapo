"""El EDA de capacidades, dibujado: ¿transfiere la abstracción a un brazo nunca visto?

QUÉ PREGUNTA CONTESTA. `P15` se refutó mapeando ontología de la pregunta → **nombre de
paradigma**. La propuesta es el eslabón del medio —ontología → **capacidades exigidas** →
brazos que las tienen— y la afirmación fuerte es que las capacidades «predicen sobre brazos
que nunca se corrieron». La prueba correcta es **dejar un brazo afuera**, no una tarea.

POR QUÉ ES UNA FIGURA Y NO UNA TABLA, y son dos razones distintas por panel:

  · **izquierda** — ocho pliegues × tres modelos son 24 números, y lo que importa no es
    ninguno sino **cuántas veces gana cada modelo**. Un dumbbell por pliegue lo muestra de
    un vistazo; una tabla de 8×3 obliga a comparar de a filas
  · **derecha** — el veredicto es `p = 0,065`, y un `p` solo no dice si quedó cerca o lejos.
    La distribución del nulo con el valor real marcado sí: se ve que cae **adentro** de la
    cola, no del otro lado del histograma

LOS NÚMEROS SE LEEN DE `results/eda_capacidades.json`, que produce el propio EDA. No se
transcriben: un número copiado a mano es un número que se puede desincronizar del que lo
produjo, y esta figura ya tiene un antecedente de eso en el repo.

EL RESULTADO ES NEGATIVO Y LA FIGURA NO LO DISIMULA. Las capacidades ganan 6 de 8 pliegues y
bajan el error contra la dificultad de la tarea sola, pero **no cruzan** el nulo de
capacidades barajadas. El título dice eso, no otra cosa.

Corre DESDE `lab/`:  py bench/analysis/_figura_capacidades.py
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from bench.analysis._estilo import COLOR, GRIS, SUAVE, TINTA, aplicar, guardar, titular

FUENTE = Path("results/eda_capacidades.json")
MODELOS = [
    ("media_global", GRIS, "media global"),
    ("dificultad_tarea", COLOR["vueltas"], "dificultad de la tarea"),
    ("capacidades", COLOR["estructural"], "capacidades"),
]


def main() -> None:
    if not FUENTE.exists():
        raise SystemExit(
            f"falta {FUENTE}. Corré primero:\n"
            f"  py bench/analysis/_eda_capacidades.py --json {FUENTE}")
    d = json.loads(FUENTE.read_text(encoding="utf-8"))
    aplicar()

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.0, 5.2),
                                  gridspec_kw={"width_ratios": [1.25, 1]})

    # ── izquierda: un pliegue por fila, el brazo dejado afuera ─────────────────
    pliegues = d["por_pliegue"]
    ys = list(range(len(pliegues)))[::-1]
    for y, f in zip(ys, pliegues):
        vals = [(f[k], c) for k, c, _ in MODELOS]
        # LA LÍNEA UNE LOS TRES: el largo es cuánto separa al peor del mejor en ESE pliegue,
        # y es la magnitud que un promedio de los ocho borra.
        ax.plot([min(v for v, _ in vals), max(v for v, _ in vals)], [y, y],
                color=SUAVE, linewidth=2.2, zorder=1)
        mejor = min(v for v, _ in vals)
        for v, c in vals:
            gana = abs(v - mejor) < 1e-12
            ax.scatter(v, y, s=155 if gana else 95, color=c, zorder=3,
                       edgecolor="white", linewidth=1.3, alpha=1.0 if gana else 0.55)
    ax.set_yticks(ys)
    ax.set_yticklabels([f["fuera"] for f in pliegues], fontsize=9.5)
    ax.set_xlabel("error absoluto medio al predecir el brazo dejado afuera  (menos es mejor)")
    ax.grid(axis="x", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)
    gana_cap = sum(1 for f in pliegues
                   if f["capacidades"] <= min(f[k] for k, _, _ in MODELOS) + 1e-12)
    titular(ax, f"Las capacidades ganan {gana_cap} de {len(pliegues)} pliegues",
            "cada fila entrena con siete brazos y predice el octavo, que el modelo nunca vio")
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker="o", linestyle="", color=c, label=lab,
                              markersize=8) for _, c, lab in MODELOS],
              loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3, fontsize=9,
              handletextpad=0.4, columnspacing=1.8)

    # ── derecha: el nulo de capacidades barajadas ─────────────────────────────
    nulos = d["nulos"]
    real = d["medias"]["capacidades"]
    n_, _, _ = ax2.hist(nulos, bins=28, color=SUAVE, edgecolor="white", linewidth=0.8,
                        zorder=2)
    # AIRE ARRIBA: sin esto la linea vertical del valor real llega al borde y se lee como si
    # el eje la cortara, que es justo la impresion contraria a la que da el dato.
    ax2.set_ylim(0, max(n_) * 1.30)
    ax2.axvline(real, color=COLOR["estructural"], linewidth=2.4, zorder=4)
    ax2.axvline(d["medias"]["dificultad_tarea"], color=COLOR["vueltas"], linewidth=1.8,
                linestyle=(0, (5, 3)), zorder=3)
    # LA ETIQUETA VA HACIA ADENTRO. Anclada a la izquierda de la línea se salía del eje,
    # porque el valor real está cerca del borde izquierdo del nulo — que es justamente el
    # hallazgo, así que la etiqueta tenía que irse del lado contrario.
    ax2.annotate(f"capacidades reales · {real:.3f}", xy=(real, ax2.get_ylim()[1] * 0.96),
                 xytext=(9, 0), textcoords="offset points", ha="left", fontsize=9,
                 color=COLOR["estructural"], va="top", fontweight="bold")
    ax2.annotate(f"dificultad sola\n{d['medias']['dificultad_tarea']:.3f}",
                 xy=(d["medias"]["dificultad_tarea"], ax2.get_ylim()[1] * 0.62),
                 xytext=(9, 0), textcoords="offset points", ha="left", fontsize=9,
                 color=COLOR["vueltas"], va="top")
    ax2.set_xlabel("error del modelo con las capacidades BARAJADAS entre brazos")
    ax2.set_ylabel("permutaciones")
    ax2.grid(axis="y", alpha=0.5, zorder=0)
    ax2.set_axisbelow(True)
    titular(ax2, f"Pero no cruzan su nulo: p = {d['p']:.3f}",
            f"{len(nulos)} permutaciones · mismos vectores, asignados al brazo equivocado")

    fig.subplots_adjust(wspace=0.30, bottom=0.20)
    guardar(fig, "eda-capacidades")

    print(f"  panel: {d['panel']}")
    print(f"  capacidades {real:.4f} · dificultad {d['medias']['dificultad_tarea']:.4f} "
          f"· nulo medio {statistics.mean(nulos):.4f} · p {d['p']:.3f}")


if __name__ == "__main__":
    main()
