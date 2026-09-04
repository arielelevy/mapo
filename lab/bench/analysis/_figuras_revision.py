"""Las tres figuras que pidió la revisión C (2026-09-03). Cero llamadas al modelo.

POR QUÉ ESTAS TRES. El revisor externo dijo que el argumento empírico se entiende casi solo
con tres imágenes: estabilidad contra ramificación, riesgo contra cobertura, y la frontera de
costo y utilidad con las políticas encima. Las tres salen del registro que ya está pagado.

  **1. Estabilidad contra ramificación** — un punto por brazo del rectángulo. El eje
  horizontal es el proxy de `d(T)` que el registro tiene, iteraciones medias por celda; el
  vertical, la fracción de celdas cuyas tres réplicas dieron la misma utilidad. Si más
  decisiones delegadas compraran menos estabilidad, los puntos bajarían hacia la derecha.
  `handoff` va hueco: su conteo es de sub-agentes y no compara (paper §6.1.6). Lo que la
  figura NO muestra es `V_T`: las secuencias de nodos no están comparadas en el registro.

  **2. Riesgo contra cobertura del consenso** — la única regla de abstención que el registro
  mide. Cada punto exige `k` o más brazos coincidentes para dejar pasar una respuesta:
  cobertura = fracción de celdas que pasan, riesgo = 1 − utilidad media de las que pasaron.
  Réplica 0, igualdad exacta de la cadena normalizada, como en `_consenso.py`.

  **3. Frontera de costo y utilidad, con las políticas** — los brazos fijos como círculos
  con la frontera de Pareto, y encima, como rombos, las políticas y cotas de §6.4.1. Esos
  números NO se transcriben: se leen de los JSON que escriben `_predictores.py` y
  `_p34_costo.py`. Un número copiado a mano es un número que se desincroniza.

Corre DESDE `lab/`:  py bench/analysis/_figuras_revision.py
Antes hay que haber corrido `_predictores.py` y `_p34_costo.py`, que dejan sus JSON.
"""

from __future__ import annotations

import collections
import json
import statistics
import sys as _sys
from pathlib import Path

_sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
_sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from app.runner import load_rows
from bench.analysis._consenso import cargar as cargar_consenso
from bench.analysis._estilo import (COLOR, GRIS, SUAVE, TINTA, aplicar, color_de,
                                    guardar, leyenda_clases, miles, titular)
from bench.panel import rectangulo

REGISTRO = Path("results/luna/gold_h1_rows.jsonl")
P34 = Path("results/luna/p34_verdicto.json")
PREDICTORES = Path("results/luna/predictores_costo.json")
# El paper (§6.1.6) deja a `handoff` fuera del conteo: sus iteraciones son de sub-agentes.
SIN_CONTEO = {"handoff"}


def _rectangulo():
    filas = [f for f in load_rows(REGISTRO) if not f.get("infeasible")]
    panel = rectangulo([{"task_id": f["task_id"], "paradigm": f["paradigm"],
                         "infeasible": False} for f in filas])
    ts, bs = set(panel.tareas), set(panel.brazos)
    reps = collections.defaultdict(list)
    costos = collections.defaultdict(list)
    iters = collections.defaultdict(list)
    for f in filas:
        if f["task_id"] in ts and f["paradigm"] in bs:
            k = (f["task_id"], f["paradigm"])
            reps[k].append(f["utility"])
            costos[k].append(f.get("cost_tokens") or 0)
            iters[f["paradigm"]].append(f.get("iterations") or 0)
    return panel, sorted(ts), sorted(bs), reps, costos, iters


def fig_estabilidad() -> None:
    panel, tids, brazos, reps, _, iters = _rectangulo()
    puntos = []
    for p in brazos:
        us = [reps[(t, p)][:3] for t in tids if len(reps[(t, p)]) >= 3]
        pass1 = statistics.mean(statistics.mean(x) for x in us)
        pass3 = statistics.mean(1.0 if all(v == 1.0 for v in x) else 0.0 for x in us)
        estable = statistics.mean(1.0 if len(set(x)) == 1 else 0.0 for x in us)
        puntos.append((p, statistics.mean(iters[p]), pass1, pass3, estable))
    con = [q for q in puntos if q[0] not in SIN_CONTEO]
    xs = [q[1] for q in con]
    caida = [q[3] - q[2] for q in con]
    mx, my = statistics.mean(xs), statistics.mean(caida)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, caida))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in caida)
    r = sxy / (sxx * syy) ** 0.5

    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    for p, it, _, _, est in puntos:
        hueco = p in SIN_CONTEO
        ax.scatter(it, est, s=95, color="white" if hueco else color_de(p),
                   edgecolor=GRIS if hueco else "white", linewidth=1.6 if hueco else 1.2,
                   zorder=4)
        # El hueco va rotulado ABAJO a la izquierda: a la derecha pisaba a `reflection`.
        ax.annotate(p + (" · conteo de sub-agentes" if hueco else ""), (it, est),
                    textcoords="offset points", xytext=(-9, -15) if hueco else (9, 7),
                    ha="right" if hueco else "left", fontsize=9,
                    color=GRIS if hueco else TINTA)
    ax.set_xlabel("iteraciones medias por celda  ·  proxy de d(T)")
    ax.set_ylabel("fracción de celdas con tres réplicas iguales")
    ax.set_ylim(0.6, 1.0)
    ax.set_xlim(0, max(xs) * 1.25)
    ax.grid(axis="y", alpha=0.5)
    ax.set_axisbelow(True)
    # TITULOS CORTOS A PROPOSITO: el bbox ajustado del SVG crece hasta abarcar el titulo, y
    # un subtitulo mas largo que los ejes deja el grafico ocupando el 60% del lienzo.
    titular(ax, f"Más iteraciones no compran menos estabilidad: r = {r:+.2f}, n = {len(con)}",
            "un punto por brazo · mide desacuerdo de utilidad, no V_T · el hueco no cuenta")
    leyenda_clases(ax, loc="lower right")
    plt.tight_layout()
    guardar(fig, "estabilidad-contra-ramificacion")
    for p, it, p1, p3, est in sorted(puntos, key=lambda q: -q[1]):
        print(f"  {p:14} it {it:4.1f}  pass@1 {p1:.3f}  pass^3 {p3:.3f}  estables {est:.0%}")
    print(f"  r(iteraciones, caída de pass^3) = {r:+.3f}  n = {len(con)}")


def umbral_k(curva) -> int | None:
    """El primer `k` con riesgo cero: el umbral que el paper reporta."""
    return next((K for K, _, riesgo, _ in curva if riesgo <= 1e-9), None)


def fig_riesgo_cobertura() -> None:
    panel, ts, bs, R, U, _ = cargar_consenso()
    celdas = []  # (k, utilidad)
    for t in ts:
        cel = [(p, R[(t, p)]) for p in bs if (t, p) in R and R[(t, p)].strip()]
        cnt = collections.Counter(a for _, a in cel)
        for p, a in cel:
            celdas.append((cnt[a] - 1, U[(t, p)]))
    total = len(celdas)
    curva = []
    for K in range(0, max(k for k, _ in celdas) + 1):
        pasan = [u for k, u in celdas if k >= K]
        if not pasan:
            break
        curva.append((K, len(pasan) / total, 1.0 - statistics.mean(pasan), len(pasan)))

    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.plot([c[1] for c in curva], [c[2] for c in curva], color=COLOR["vueltas"],
            linewidth=2.0, zorder=2)
    # Los puntos de riesgo cero se apilan sobre el eje: sus rotulos se escalonan en
    # vertical, arriba y abajo alternados, para que no se pisen.
    escalon = 0
    for K, cob, riesgo, n in curva:
        cero = riesgo <= 1e-9
        ax.scatter(cob, riesgo, s=110 if cero else 70,
                   color=COLOR["estructural"] if cero else COLOR["vueltas"],
                   edgecolor="white", linewidth=1.2, zorder=4)
        if cero:
            # Nunca mas de una fila por debajo: la segunda caia sobre el eje.
            desplaz = ((0, 14), (0, -18), (0, 28), (0, 14))[escalon % 4]
            escalon += 1
            ax.annotate(f"k ≥ {K} · {n}", (cob, riesgo), textcoords="offset points",
                        xytext=desplaz, ha="center", fontsize=8.5,
                        color=TINTA if K == umbral_k(curva) else GRIS)
        else:
            ax.annotate(f"k ≥ {K}  ·  {n} celdas", (cob, riesgo), textcoords="offset points",
                        xytext=(8, 8 if K % 2 == 0 else -14), fontsize=9, color=TINTA)
    ax.set_xlabel("cobertura  ·  fracción de las celdas que la regla deja pasar")
    ax.set_ylabel("riesgo  ·  1 − utilidad media de las que pasan")
    ax.set_xlim(0, 1.05)
    ax.set_ylim(-0.03, max(c[2] for c in curva) * 1.25)
    ax.grid(axis="y", alpha=0.5)
    ax.set_axisbelow(True)
    umbral = next((c for c in curva if c[2] <= 1e-9), None)
    titular(ax, "Exigir acuerdo baja el riesgo a cero"
            + (f": pasa el {umbral[1]:.0%} de las celdas a k ≥ {umbral[0]}" if umbral else ""),
            f"consenso como regla de abstención · réplica 0, rectángulo "
            f"{panel.descripcion().split(' (')[0]} · cadena normalizada exacta")
    plt.tight_layout()
    guardar(fig, "riesgo-cobertura-consenso")
    for K, cob, riesgo, n in curva:
        print(f"  k ≥ {K}: cobertura {cob:.3f}  riesgo {riesgo:.3f}  n {n}")


def fig_frontera() -> None:
    for ruta, quien in ((P34, "_p34_costo.py"), (PREDICTORES, "_predictores.py")):
        if not ruta.exists():
            raise SystemExit(f"falta {ruta}. Corré primero:\n  py bench/analysis/{quien}")
    p34 = json.loads(P34.read_text(encoding="utf-8"))
    pred = json.loads(PREDICTORES.read_text(encoding="utf-8"))
    panel, tids, brazos, reps, costos, _ = _rectangulo()
    um = {p: statistics.mean(statistics.mean(reps[(t, p)]) for t in tids) for p in brazos}
    cm = {p: statistics.mean(statistics.mean(costos[(t, p)]) for t in tids) for p in brazos}

    fig, ax = plt.subplots(figsize=(8.8, 5.6))
    puntos = sorted(((cm[p], um[p], p) for p in brazos), key=lambda q: q[0])
    frontera, techo = [], -1.0
    for x, y, p in puntos:
        if y > techo:
            frontera.append((x, y, p))
            techo = y
    ax.plot([x for x, _, _ in frontera], [y for _, y, _ in frontera], color=GRIS,
            linewidth=1.2, linestyle=(0, (4, 3)), zorder=1)
    # Tres brazos y la constante caen en el mismo rincon (0,80-0,85 × 85k-130k): a cada
    # uno se lo rotula hacia un lado distinto para que se lean.
    lado = {"react": (8, 6, "left"), "dag_strategy": (-9, -13, "right"),
            "reflection": (8, -13, "left")}
    for x, y, p in puntos:
        ax.scatter(x, y, s=80, color=color_de(p), alpha=0.85, zorder=3, edgecolor="white",
                   linewidth=1.2)
        dx, dy, ha = lado.get(p, (8, -12, "left"))
        ax.annotate(p, (x, y), textcoords="offset points", xytext=(dx, dy), ha=ha,
                    fontsize=8.5, color=GRIS)

    # LAS POLÍTICAS Y LAS COTAS, leídas de sus JSON. El nombre de cada clave es el que
    # escribe el script que la produce; si cambia allá, esto FALLA acá en vez de mentir.
    pol = p34["politicas"]
    constante = next(v for k, v in pol.items() if k.startswith("constante"))
    theta = pol[p34["mejor_clave_computed"]]
    senal = pred["senales"]["cardinalidad x termino"]
    region = pred["senales"]["region (la de hoy)"]
    oraculo = pred["oraculo_costo"]
    rombos = [
        ("θ constante, no aprende", constante["tokens"], constante["utilidad"], GRIS, (10, 2)),
        # Las dos señales se rotulan hacia la IZQUIERDA: a la derecha pisaban a
        # `reflection` y a la frontera.
        ("señal cardinalidad × término, LOTO", senal["tokens"], senal["utilidad"], TINTA, (-10, 6)),
        ("señal región, LOTO", region["tokens"], region["utilidad"], TINTA, (-10, -16)),
        ("θ sobre clave COMPUTED, ahorra "
         f"{theta['ahorro']:.0%}", theta["tokens"], theta["utilidad"], TINTA, (8, 8)),
        ("oráculo de costo, no es política", oraculo["tokens"], oraculo["utilidad"],
         COLOR["alcance"], (8, 8)),
    ]
    for nombre, x, y, col, off in rombos:
        ax.scatter(x, y, s=120, marker="D", color=col, zorder=5, edgecolor="white",
                   linewidth=1.3)
        ax.annotate(nombre, (x, y), textcoords="offset points", xytext=off, fontsize=9,
                    color=col, ha="right" if off[0] < 0 else "left")
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(miles))
    ax.set_xlabel("tokens por tarea  ·  escala logarítmica")
    ax.set_ylabel("utilidad media")
    ax.grid(axis="y", alpha=0.5)
    ax.set_axisbelow(True)
    ax.margins(x=0.2, y=0.2)
    titular(ax, f"θ mejora a su constante y ahorra {theta['ahorro']:.0%}; el oráculo dice cuánto queda",
            "círculos: brazos fijos y su frontera de Pareto · rombos: políticas y cotas, de sus JSON")
    # Arriba a la izquierda no hay nada: abajo a la izquierda pisaba a `pointer_chase`.
    leyenda_clases(ax, loc="upper left")
    plt.tight_layout()
    guardar(fig, "frontera-costo-utilidad")
    for nombre, x, y, _, _ in rombos:
        print(f"  {nombre:42} u {y:.3f}  {x:>9,.0f} tok")


def main() -> None:
    aplicar()
    print("1. estabilidad contra ramificación")
    fig_estabilidad()
    print("\n2. riesgo contra cobertura del consenso")
    fig_riesgo_cobertura()
    print("\n3. frontera de costo y utilidad, con las políticas")
    fig_frontera()


if __name__ == "__main__":
    main()
