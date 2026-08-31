"""EL ESPACIO DE CAPACIDADES: cada brazo, un punto. Cero llamadas al modelo.

LA TESIS QUE ESTA FIGURA HACE VISIBLE. El catálogo llama a sus brazos por su estructura de
control de flujo —«plan-ejecuta», «supervisor», «cadena»— y esa taxonomía **no predice
nada**: `P15` se refutó tratando de mapear ontología de la pregunta a nombre de paradigma.
Lo que sí predice es qué **capacidades** tiene cada uno, y son tres, medibles:

    x   PAYLOAD POR LLAMADA   cuántas unidades ve el modelo de una vez
    y   ADAPTABILIDAD         ¿puede corregir el plan después de ver un resultado?
    z   LEY DE COSTO          de qué es función su costo: alcance, vueltas, o nada

LAS DOS PRIMERAS SE LEEN DEL CÓDIGO, y ése es el punto: **predicen sobre brazos que nunca
se corrieron**. Una tabla de paradigmas sólo sabe de los que se midieron.

POR QUÉ ESTOS TRES EJES Y NO OTROS. Cada uno explica una medición que la taxonomía de
control de flujo no puede:

  · `handoff` LEE las dos unidades de una contradicción y saca **0,067** — porque cada
    sub-agente ve su mitad y ninguna llamada tiene el par. Eso es el eje x, no su topología
  · `rewoo` **puede** tenerlas juntas y saca 0,133 — le falta poder elegir CUÁLES dos, que
    exige ver un resultado antes de pedir el siguiente. Eso es el eje y
  · `handoff` tiene techo de 12 llamadas y gasta 131.310 tokens; `dag_strategy` tiene techo
    de 160 y gasta 105.293. Casi lo mismo con un factor 13 de diferencia en el techo —
    contar llamadas para acotar esfuerzo es contar envases para acotar peso. Eso es el eje z

Y UNA REGIÓN POR FAMILIA DE PREGUNTA. Una contradicción exige `x ≥ 2` **y** `y = 1`. Medido:
con las dos, 0,71–0,91; con una sola, 0,13; con ninguna, 0,00–0,40.

Corre DESDE `lab/`:  py bench/analysis/_espacio_capacidades.py
"""

from __future__ import annotations

import collections
import json
import math
import statistics
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# EL GUARDADO ES COMPARTIDO aunque el estilo de esta figura sea propio (es 3D):
# el formato de salida es una decision del paper, no de la figura.
from bench.analysis._estilo import guardar

SALIDA = _Path("../whitepaper/figuras")

# ── LOS DOS EJES QUE SE LEEN DEL CODIGO, declarados aca y no inferidos ───────
#
# PAYLOAD: cuantas unidades puede tener el modelo en UNA llamada. `None` = todas las del
# alcance. Sale de leer el paradigma, no del registro — y por eso vale para un brazo que
# todavia no existe.
PAYLOAD = {
    "direct": None, "gist_reader": None, "react": None, "reflection": None,
    "dag_strategy": None,
    "rewoo": 10,            # MAX_BATCH_READ por paso de lectura
    "handoff": None,        # su alcance entero... pero NUNCA el del otro sub-agente
    "supervisor": 8,        # la ventana recortada por el codigo
    "streaming_scan": 6,    # un trozo por pasada
    "pointer_chase": 1,     # «la UNICA unidad que podes ver», dice su prompt
    "extract_compute": 1,   # una unidad por extraccion
    "graph_traverse": None,
}
# ADAPTABILIDAD: ¿puede el brazo cambiar lo que pide DESPUES de ver un resultado?
ADAPTA = {
    "react": 1.0, "reflection": 1.0, "dag_strategy": 1.0, "supervisor": 1.0,
    "pointer_chase": 1.0,
    "gist_reader": 0.5,     # un solo triage: elige que leer, pero una vez
    "rewoo": 0.0, "direct": 0.0, "streaming_scan": 0.0, "extract_compute": 0.0,
    "graph_traverse": 0.0,
}
COLOR = {"alcance": "#c44e52", "vueltas": "#4c72b0", "estructural": "#55a868"}
CLASE = {
    "handoff": "alcance",
    "react": "vueltas", "reflection": "vueltas", "supervisor": "vueltas",
    "dag_strategy": "vueltas", "gist_reader": "vueltas", "pointer_chase": "vueltas",
    "rewoo": "estructural", "direct": "estructural", "graph_traverse": "estructural",
    "extract_compute": "estructural", "streaming_scan": "estructural",
}


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    tareas = {t["task_id"]: t for t in json.loads(
        _Path("corpus/gold_h1/tasks.json").read_text(encoding="utf-8"))}

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

    # EL EJE Z SE MIDE, no se declara: exponente del ajuste log-log de costo contra alcance.
    puntos = collections.defaultdict(list)
    u = collections.defaultdict(list)
    aplica = collections.Counter()
    total = collections.Counter()
    for f in filas:
        p = f["paradigm"]
        total[p] += 1
        if f.get("infeasible") or f.get("infra_error"):
            continue
        aplica[p] += 1
        u[p].append(f["utility"])
        n = len(tareas[f["task_id"]]["unit_ids"])
        c = f.get("cost_tokens") or 0
        if n > 0 and c > 0:
            puntos[p].append((math.log(n), math.log(c)))

    def exponente(pts):
        if len(pts) < 8 or len({x for x, _ in pts}) < 2:
            return None
        mx = statistics.mean(x for x, _ in pts)
        my = statistics.mean(y for _, y in pts)
        sxy = sum((x - mx) * (y - my) for x, y in pts)
        sxx = sum((x - mx) ** 2 for x, _ in pts)
        return sxy / sxx if sxx else None

    # QUIEN NO ENTRA, Y POR QUE SE DICE. Un brazo que solo corrio en UN ancho no tiene ley
    # de costo ajustable —no hay dos valores de alcance que comparar— asi que no tiene eje
    # z. `direct`, `streaming_scan` y `extract_compute` estan en ese caso: la factibilidad
    # los poda fuera de `w4`. Excluirlos en silencio los haria parecer inexistentes en vez
    # de acotados, que es lo que son.
    brazos = [p for p in u if len(u[p]) >= 20 and exponente(puntos[p]) is not None]
    afuera = [p for p in u if p not in brazos]
    if afuera:
        print(f"(fuera de la figura, sin ley de costo ajustable — corren en un solo "
              f"ancho: {', '.join(sorted(afuera))})\n")

    fig = plt.figure(figsize=(12, 8.5))
    ax = fig.add_subplot(111, projection="3d")

    print(f"{'brazo':16s} {'payload':>8s} {'adapta':>7s} {'exp b':>7s} "
          f"{'u|aplica':>9s} {'cobertura':>10s}")
    for i, p in enumerate(sorted(brazos,
                                 key=lambda p: -statistics.mean(u[p]))):
        b = exponente(puntos[p])
        if b is None:
            continue
        pay = PAYLOAD.get(p)
        x = 60 if pay is None else pay          # `None` = todo el alcance mas grande
        y = ADAPTA.get(p, 0.0)
        cob = aplica[p] / total[p]
        um = statistics.mean(u[p])
        print(f"{p:16s} {('todas' if pay is None else str(pay)):>8s} {y:7.1f} "
              f"{b:7.2f} {um:9.3f} {cob:10.0%}")
        ax.scatter(math.log10(x), y, b, s=90 + um * 420, alpha=0.78,
                   color=COLOR.get(CLASE.get(p, ""), "#888"),
                   edgecolor="white", linewidth=1.3, depthshade=False)
        # LAS ETIQUETAS SE SEPARAN, LOS PUNTOS NO. `react`, `dag_strategy` y `reflection`
        # caen practicamente EN EL MISMO PUNTO — mismo payload, misma adaptabilidad,
        # exponentes de 0,29 a 0,45 — y eso **es el hallazgo**: son el mismo brazo para
        # decidir, y por eso quedan dentro de 0,05 de utilidad entre si. Moverlos para que
        # se lean seria borrar justamente lo que la figura muestra.
        ax.text(math.log10(x) + 0.04, y, b + 0.022 + 0.030 * (i % 3), p,
                fontsize=8.5, ha="left", zorder=10)

    ax.set_xlabel("\npayload por llamada\n(log₁₀ de unidades visibles a la vez)", fontsize=9)
    ax.set_ylabel("\nadaptabilidad\n(¿corrige tras ver un resultado?)", fontsize=9)
    ax.set_zlabel("\nley de costo\n(exponente sobre el alcance)", fontsize=9)
    ax.set_title("El espacio de capacidades: cada brazo, un punto\n"
                 "el tamaño es su utilidad; el color, de qué es función su costo",
                 fontsize=12, pad=18)
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker="o", linestyle="", color=c, label=k,
                              markersize=9) for k, c in COLOR.items()],
              loc="upper left", bbox_to_anchor=(0.0, 0.86), frameon=False, fontsize=9,
              title="de qué es función su costo", title_fontsize=9)
    ax.view_init(elev=20, azim=-125)
    plt.tight_layout()
    guardar(fig, "espacio-capacidades")
    plt.close(fig)
    print(f"\n  -> {SALIDA / 'espacio-capacidades.png'}")
    print("""
  COMO SE LEE. Los tres ejes NO son la topologia: son lo que la topologia le da al modelo.
  Dos brazos con nombres distintos y el mismo punto son el mismo brazo para decidir, y uno
  que todavia no existe se puede ubicar leyendo su codigo — que es lo que una tabla de
  paradigmas no puede hacer.""")


if __name__ == "__main__":
    main()
