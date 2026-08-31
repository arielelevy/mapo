"""El sistema visual de las figuras del paper. Un solo lugar.

POR QUÉ EXISTE. Cuatro figuras hechas por separado salen con cuatro tipografías, cuatro
tamaños y cuatro tratamientos de grilla, y el lector lo lee como cuatro fuentes distintas
aunque los datos vengan del mismo registro. La coherencia visual no es decoración: es lo que
permite comparar dos figuras sin volver a aprender a leerlas.

LAS DECISIONES, y cada una tiene un motivo:

  · **el color codifica UNA cosa en todo el paper** — de qué es función el costo de un brazo.
    Nunca la utilidad, nunca el ancho. Un color que significa dos cosas en dos figuras es
    peor que no usar color
  · **sin leyenda cuando se puede etiquetar directo.** Una leyenda obliga a saltar entre la
    clave y el dato; una etiqueta al lado del punto, no
  · **el eje no arranca en cero cuando el cero no es un valor posible ni informativo.** Toda
    la utilidad medida vive entre 0,35 y 0,95; forzar el cero regala la mitad del alto y
    aplana justo las diferencias que la figura existe para mostrar
  · **el título dice el HALLAZGO, el subtítulo dice cómo leerlo.** Un título que sólo nombra
    los ejes desperdicia el único renglón que el lector garantiza mirar
  · **grilla apenas visible y sólo en el eje que se compara.** La grilla ayuda a estimar
    valores y compite con los datos; en el eje que no se compara, sólo compite
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# LA CLASE DE COSTO, y es lo unico que el color significa en todo el paper.
COLOR = {
    "alcance": "#b5495b",      # granate
    "vueltas": "#3b6ea5",      # azul
    "estructural": "#2e8b6f",  # verde
}
GRIS = "#9aa0a6"
TINTA = "#22252a"
SUAVE = "#d8dbdf"

CLASE = {
    "handoff": "alcance",
    "react": "vueltas", "reflection": "vueltas", "supervisor": "vueltas",
    "dag_strategy": "vueltas", "gist_reader": "vueltas", "pointer_chase": "vueltas",
    "rewoo": "estructural", "direct": "estructural", "graph_traverse": "estructural",
    "extract_compute": "estructural", "streaming_scan": "estructural",
}


def color_de(brazo: str) -> str:
    return COLOR.get(CLASE.get(brazo, ""), GRIS)


def aplicar() -> None:
    """El estilo base. Se llama UNA vez, antes de dibujar nada."""
    plt.rcParams.update({
        "figure.dpi": 180,
        "savefig.dpi": 180,
        "savefig.bbox": "tight",
        "savefig.facecolor": "white",
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "text.color": TINTA,
        "axes.labelcolor": TINTA,
        "axes.labelsize": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "regular",
        "axes.titlelocation": "left",
        "axes.edgecolor": SUAVE,
        "axes.linewidth": 0.9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": GRIS,
        "ytick.color": GRIS,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "legend.frameon": False,
        "legend.fontsize": 9,
        "grid.color": SUAVE,
        "grid.linewidth": 0.7,
        # EL TEXTO DEL SVG VA COMO TEXTO, NO COMO TRAZOS. Por omisión matplotlib convierte
        # cada letra en un `<path>`, y con eso el docstring de `guardar()` mentía: el texto
        # no queda ni seleccionable ni buscable dentro del PDF, y el archivo pesa el triple.
        # `none` lo deja como `<text>` y delega la fuente al visor — que es lo correcto para
        # una familia estándar como DejaVu Sans.
        "svg.fonttype": "none",
    })


def titular(ax, titulo: str, subtitulo: str = "") -> None:
    """Título = el hallazgo. Subtítulo = cómo leerlo.

    Van separados y con jerarquía distinta porque hacen cosas distintas: el primero es la
    afirmación y el segundo la instrucción. Fundirlos en dos renglones del mismo tamaño
    —que es lo que hace `\\n` en un `set_title`— los deja compitiendo.
    """
    ax.set_title(titulo, fontsize=13, color=TINTA, pad=26 if subtitulo else 12,
                 loc="left")
    if subtitulo:
        ax.annotate(subtitulo, xy=(0, 1), xycoords="axes fraction",
                    xytext=(0, 12), textcoords="offset points",
                    fontsize=9.5, color=GRIS, va="bottom", ha="left")


def leyenda_clases(ax, loc: str = "lower right") -> None:
    """La única leyenda del paper, y siempre significa lo mismo."""
    from matplotlib.lines import Line2D
    ax.legend(
        handles=[Line2D([], [], marker="o", linestyle="", color=c, label=k,
                        markersize=7) for k, c in COLOR.items()],
        loc=loc, title="de qué es función su costo", title_fontsize=8.5,
        fontsize=8.5, labelspacing=0.4, handletextpad=0.5,
    )


def miles(x: float, _pos=None) -> str:
    """`10k` y `100k` en vez de `10^4` y `10^5`: nadie piensa en exponentes."""
    if x >= 1_000_000:
        return f"{x / 1_000_000:g}M"
    if x >= 1_000:
        return f"{x / 1_000:g}k"
    return f"{x:g}"


def guardar(fig, nombre: str, salida=None) -> None:
    """Guarda la figura como **SVG**, y en un solo lugar.

    POR QUÉ SVG Y NO PNG. Una figura de paper se mira ampliada —en pantalla, en un PDF, en
    una diapositiva— y un PNG a 180 dpi se rompe en cuanto alguien hace zoom sobre una
    etiqueta de eje. El SVG es texto vectorial: escala sin pérdida, pesa menos que el PNG en
    estas figuras (son puntos y líneas, no fotos), y su texto queda **seleccionable y
    buscable** dentro del PDF, que para una tabla de números importa.

    Y SE HACE ACÁ y no en cada script por la misma razón que el resto de este módulo existe:
    tres scripts guardando por su cuenta terminan con tres dpi, tres formatos y tres
    convenciones de nombre, y la coherencia visual es lo que permite comparar dos figuras sin
    volver a aprender a leerlas.
    """
    from pathlib import Path
    destino = Path(salida) if salida else Path("../whitepaper/figuras")
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / f"{nombre}.svg"
    fig.savefig(ruta, format="svg")
    plt.close(fig)
    print(f"ok  {ruta.name}")
