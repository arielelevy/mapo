"""La curva de consenso, en PNG y en inglés, para pegar en un correo.

POR QUÉ PNG Y NO SVG. Ningún cliente de correo renderiza SVG inline: Gmail y Outlook lo
descartan o lo bajan como adjunto. Las trece figuras del paper son SVG porque van a un PDF;
ésta es la única que tiene que sobrevivir un `<img>` en un mail.

POR QUÉ ESTA Y NINGUNA OTRA. Es la única figura del registro que se entiende sin leyenda, sin
ejes explicados y sin contexto previo: cinco puntos, monótona a partir del segundo, y termina
en `1,000`. La de predictores necesita que alguien explique qué es el máximo de los nulos; la
del método necesita los dos carriles. Un gráfico que pide explicación en un correo en frío es
decoración.

POR QUÉ EN INGLÉS. El paper va en español y los destinatarios no lo leen. Es el único
artefacto del repo que se aparta de esa regla, y por eso lleva sufijo en el nombre del archivo.

LOS DATOS son la tabla de §7.5.1 del paper: acuerdo exacto sobre la cadena normalizada, sobre
el panel de 64 tareas × 8 brazos.

Corre DESDE `lab/`:  py bench/analysis/_figura_consenso.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SALIDA = Path("../whitepaper/figuras/consenso-para-mail.png")

TINTA, GRIS, SUAVE = "#22252a", "#6b7178", "#d8dbdf"
AZUL, VERDE = "#3b6ea5", "#2e8b6f"

# §7.5.1 — (etiqueta, celdas, P(correcta))
CURVA = [("0", 208, 0.424), ("1", 36, 0.389), ("2", 24, 0.600),
         ("3", 64, 0.812), ("≥ 4", 180, 1.000)]


def main() -> None:
    plt.rcParams.update({
        "figure.dpi": 200, "savefig.dpi": 200, "savefig.bbox": "tight",
        "savefig.facecolor": "white", "font.family": "DejaVu Sans", "font.size": 10,
        "text.color": TINTA, "axes.labelcolor": TINTA, "axes.edgecolor": SUAVE,
        "axes.linewidth": 0.9, "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": GRIS, "ytick.color": GRIS, "grid.color": SUAVE, "grid.linewidth": 0.7,
    })

    fig, ax = plt.subplots(figsize=(6.4, 3.5))
    x = range(len(CURVA))
    y = [p for _, _, p in CURVA]

    ax.grid(axis="y", zorder=0)
    ax.plot(x, y, color=AZUL, linewidth=2.2, zorder=3)
    # el punto del umbral se distingue por COLOR y por TAMAÑO: en un mail la imagen puede
    # llegar reescalada, y un solo canal de distinción no sobrevive eso
    for i, (_, n, p) in enumerate(CURVA):
        cruza = p >= 1.0
        ax.plot(i, p, "o", color=VERDE if cruza else AZUL,
                markersize=11 if cruza else 7.5, zorder=4)
        ax.annotate(f"{p:.3f}".replace(".", "."), (i, p), textcoords="offset points",
                    xytext=(0, 15 if i < 4 else 12), ha="center",
                    fontsize=10.5, fontweight="600" if cruza else "400",
                    color=VERDE if cruza else TINTA, zorder=5)
        ax.annotate(f"n={n}", (i, p), textcoords="offset points", xytext=(0, -20),
                    ha="center", fontsize=8.5, color=GRIS, zorder=5)

    ax.set_xticks(list(x), [e for e, _, _ in CURVA])
    ax.set_xlabel("paradigms agreeing on the same answer", fontsize=10, color=GRIS)
    ax.set_ylabel("P(the answer is correct)", fontsize=10, color=GRIS)
    ax.set_ylim(0.30, 1.12)
    ax.set_yticks([0.4, 0.6, 0.8, 1.0])

    ax.set_title("Agreement between paradigms is a verifier — no oracle, no judge",
                 fontsize=12.5, loc="left", pad=24, color=TINTA)
    ax.annotate("full precision from four matches: 180 of 180 cells, on exact string "
                "agreement · replicated on a second model family",
                xy=(0, 1), xycoords="axes fraction", xytext=(0, 10),
                textcoords="offset points", fontsize=9, color=GRIS, va="bottom", ha="left")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(SALIDA)
    plt.close(fig)
    kb = SALIDA.stat().st_size // 1024
    print(f"  {SALIDA}  ({kb} KB)")
    if kb > 200:
        print("  [!] pesa mas de 200 KB — algunos clientes de correo lo degradan")


if __name__ == "__main__":
    main()
