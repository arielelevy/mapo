"""Las tres figuras del 2026-08-30: el embudo, la latencia serial, y los modos de falla de C3.

CADA UNA EXISTE PORQUE UNA TABLA NO ALCANZABA:

  1. **el embudo** — la afirmación es que `react` no gana buscando sino no destruyendo. Eso
     son DOS números por brazo (cuánto vio, y qué hizo con lo que vio) y la relación entre
     ellos es el hallazgo. Un scatter lo muestra de un vistazo; dos columnas de una tabla
     obligan a hacer la resta a mano y a creerla
  2. **la latencia serial** — es un eje NUEVO, y lo primero que hay que poder ver es si abre
     una decisión que la utilidad no abría. Un frente de Pareto contesta eso y nada más
  3. **los modos de falla de C3** — cinco categorías por brazo, y lo que importa no son las
     alturas sino la COMPOSICIÓN: quién se equivoca confiado y quién se abstiene

EL SISTEMA VISUAL ES EL DE `_estilo.py` y no se re-decide acá: el color codifica de qué es
función el costo del brazo, en todo el paper, siempre lo mismo.

Corre DESDE `lab/`:  py bench/analysis/_figuras_embudo.py
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.runner import load_rows
from app.verify import is_refusal
from bench.analysis._estilo import (COLOR, GRIS, SUAVE, TINTA, aplicar, color_de, guardar,
                                    leyenda_clases, miles, titular)
from bench.panel import rectangulo

SALIDA = Path("../whitepaper/figuras")
REGISTRO = Path("results/luna/gold_h1_rows.jsonl")
TERRA = Path("results/terra/gold_h1_rows.jsonl")
CORPUS = Path("corpus/gold_h1")
CUENTA = re.compile(r"\bAR\d{10}\b")

# COLOCACION A MANO, y no es pereza: son ocho puntos fijos y el radio de cada uno depende
# de su utilidad, asi que ninguna regla uniforme los acomoda. `dag_strategy` y `rewoo` caen
# casi en la misma vertical y una regla «arriba salvo dos» los apilaba uno sobre otro.
# (dx, dy en PUNTOS, alineacion horizontal)
ETIQUETA = {
    "react": (0, 24, "center"),
    "reflection": (-30, 12, "right"),
    "dag_strategy": (34, 6, "left"),
    "rewoo": (-26, 0, "right"),
    "supervisor": (0, 20, "center"),
    "pointer_chase": (0, 18, "center"),
    "handoff": (-24, -4, "right"),
    "gist_reader": (0, 20, "center"),
}


def datos():
    filas = [f for f in load_rows(REGISTRO) if not f.get("infeasible")]
    tareas = json.loads((CORPUS / "tasks.json").read_text(encoding="utf-8"))
    gold = {t["task_id"]: set(t.get("relevant_units") or []) & set(t["unit_ids"])
            for t in tareas}
    panel = rectangulo([{"task_id": f["task_id"], "paradigm": f["paradigm"],
                         "infeasible": False} for f in filas])
    ts, bs = set(panel.tareas), set(panel.brazos)
    dentro = [f for f in filas if f["task_id"] in ts and f["paradigm"] in bs]

    celdas = defaultdict(list)
    for f in dentro:
        celdas[(f["task_id"], f["paradigm"])].append(f)
    emb = {}
    for (t, p), fs in celdas.items():
        g = gold.get(t) or set()
        vio, u = [], []
        for f in fs:
            tu = f.get("tool_usage") or {}
            r = tu.get("relevant_units_read_any", tu.get("relevant_units_read", 0)) or 0
            vio.append(1.0 if g and r >= len(g) else 0.0)
            u.append(f.get("utility", 0.0))
        emb[(t, p)] = {"vio": statistics.mean(vio), "u": statistics.mean(u)}

    resumen = {}
    for p in bs:
        ks = [k for k in emb if k[1] == p]
        si = [emb[k]["u"] for k in ks if emb[k]["vio"] >= 0.999]
        ser = [f.get("ttft_ms_total") for f in dentro
               if f["paradigm"] == p and f.get("ttft_ms_total")]
        resumen[p] = {
            "u": statistics.mean(emb[k]["u"] for k in ks),
            "vio": statistics.mean(emb[k]["vio"] for k in ks),
            "u_vio": statistics.mean(si) if si else float("nan"),
            "n_vio": len(si),
            "serie": statistics.median(ser) / 1000.0 if ser else float("nan"),
        }
    return resumen, panel


# ── 1. el embudo ────────────────────────────────────────────────────────────────
def fig_embudo(res, panel) -> None:
    fig, ax = plt.subplots(figsize=(8.6, 5.9))
    for p, d in res.items():
        c = color_de(p)
        # EL TAMANO ES LA UTILIDAD, y por eso no hace falta una tercera dimension: el punto
        # grande arriba a la izquierda es la tesis entera de la figura.
        ax.scatter(d["vio"], d["u_vio"], s=60 + 900 * d["u"] ** 2, color=c,
                   alpha=0.82, edgecolor="white", linewidth=1.4, zorder=3)
        # EL DESPLAZAMIENTO VA EN PUNTOS Y NO EN UNIDADES DE DATO: el radio del punto
        # escala con la utilidad, asi que un offset en el eje y se pisa con los puntos
        # grandes y sobra con los chicos. Los dos de abajo se etiquetan por debajo porque
        # arriba chocan con su vecino.
        dx, dy, ha = ETIQUETA.get(p, (0, 22, "center"))
        ax.annotate(p, (d["vio"], d["u_vio"]), xytext=(dx, dy),
                    textcoords="offset points", ha=ha,
                    va="top" if dy < 0 else ("center" if dy == 0 else "bottom"),
                    fontsize=9.2, color=TINTA, zorder=4)
    # LA DIAGONAL NO ES UNA REGRESION: es la creencia ingenua —«el que mas ve, mejor
    # contesta»— dibujada para que se vea que el dato no la sigue.
    ax.plot([0.3, 0.85], [0.55, 1.0], linestyle=(0, (4, 4)), color=SUAVE, linewidth=1.3,
            zorder=1)
    ax.annotate("lo que uno esperaría:\nver más ⇒ contestar mejor", xy=(0.80, 0.965),
                fontsize=8.6, color=GRIS, ha="right", va="top", style="italic")
    ax.set_xlabel("etapa 1 — fracción de celdas que leyó TODAS las unidades portadoras")
    ax.set_ylabel("etapa 2 — utilidad CUANDO las tuvo a la vista")
    ax.set_xlim(0.33, 0.86)
    ax.set_ylim(0.50, 1.04)
    ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
    ax.grid(axis="y", alpha=0.55, zorder=0)
    ax.set_axisbelow(True)
    titular(ax, "`react` no gana buscando: gana no destruyendo lo que encontró",
            f"área del punto = utilidad sobre el corpus  ·  {panel.descripcion()}")
    leyenda_clases(ax, loc="lower left")
    guardar(fig, "embudo-ver-contra-usar")


# ── 2. la latencia serial ───────────────────────────────────────────────────────
def fig_latencia(res, panel) -> None:
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    pts = sorted(((d["serie"], d["u"], p) for p, d in res.items()
                  if d["serie"] == d["serie"]), key=lambda x: x[0])
    # EL FRENTE: nadie a su izquierda es mejor Y mas rapido a la vez.
    frente, techo = [], -1.0
    for s, u, p in pts:
        if u > techo:
            frente.append((s, u, p))
            techo = u
    ax.plot([s for s, _, _ in frente], [u for _, u, _ in frente],
            color=SUAVE, linewidth=1.6, zorder=1)
    for s, u, p in pts:
        en_frente = any(p == q for _, _, q in frente)
        ax.scatter(s, u, s=190 if en_frente else 110, color=color_de(p),
                   alpha=0.9 if en_frente else 0.45,
                   edgecolor="white", linewidth=1.4, zorder=3)
        ax.annotate(p, (s, u), xytext=(0, 13 if en_frente else -17),
                    textcoords="offset points", ha="center",
                    fontsize=9.2 if en_frente else 8.4,
                    color=TINTA if en_frente else GRIS, zorder=4)
    ax.set_xlabel("latencia SERIAL — suma del tiempo al primer token sobre todas las "
                  "llamadas (mediana, s)")
    ax.set_ylabel("utilidad sobre el corpus")
    ax.set_xlim(0.5, 3.1)
    ax.set_ylim(0.46, 0.92)
    ax.grid(axis="y", alpha=0.55, zorder=0)
    ax.set_axisbelow(True)
    titular(ax, "El eje nuevo no destraba nada: `react` es el mejor Y el más rápido",
            "el frente une a los no dominados  ·  el primer token es igual en todos "
            "(250–410 ms); lo que cambia es cuántas llamadas van en serie")
    guardar(fig, "latencia-serial")


# ── 3. los modos de falla de C3 ─────────────────────────────────────────────────
def fig_c3() -> None:
    docs = json.loads((CORPUS / "documents.json").read_text(encoding="utf-8"))
    tareas = {t["task_id"]: t for t in json.loads(
        (CORPUS / "tasks.json").read_text(encoding="utf-8"))}
    c3 = {k: v for k, v in tareas.items() if v["cell"] == "C3_coupled_chain"}

    def cuenta_de(u):
        m = CUENTA.search(docs.get(u, ""))
        return m.group(0) if m else None

    caminos = {}
    for tid, t in c3.items():
        orac = (t.get("oracle") or [None])[0]
        port = list(t["relevant_units"])
        final = next((u for u in port if orac and orac in docs.get(u, "")), None)
        m = re.search(r"Starting from ([A-Z][\w'-]+(?: [A-Z][\w'-]+)*), follow", t["question"])
        ancla = next((u for u in port if m and m.group(1) in docs.get(u, "")), None)
        caminos[tid] = [ancla, *[u for u in port if u not in (final, ancla)], final] \
            if final and ancla and final != ancla else None

    modos = defaultdict(Counter)
    for ruta in (TERRA, REGISTRO):
        if not ruta.exists():
            continue
        for f in load_rows(ruta):
            if f["task_id"] not in c3 or f.get("infeasible"):
                continue
            cam = caminos.get(f["task_id"])
            ans = f.get("answer") or ""
            hall = CUENTA.findall(ans)
            p = f["paradigm"]
            if not hall:
                # `is_refusal` ES EL ARBITRO, el mismo que el grader. Sin el, `M. Arrieta`
                # —la PERSONA en vez de la cuenta— contaba como abstencion e inflaba la
                # unica columna con la que esta figura afirma algo.
                modos[p]["se abstuvo" if is_refusal(ans) else "contestó la persona"] += 1
            elif cam and hall[0] == cuenta_de(cam[-1]):
                modos[p]["correcta"] += 1
            elif cam and hall[0] == cuenta_de(cam[0]):
                modos[p]["saltó la cadena"] += 1
            elif cam and hall[0] in {cuenta_de(u) for u in cam[1:-1]}:
                modos[p]["cortó un escalón antes"] += 1
            else:
                modos[p]["otra cuenta del material"] += 1

    ORDEN = ["correcta", "se abstuvo", "cortó un escalón antes", "saltó la cadena",
             "otra cuenta del material", "contestó la persona"]
    # VERDE = acerto. GRIS = se callo. GRANATE = contesto mal y confiado. Tres estados, y
    # el del medio es el que el banco puntua igual que el ultimo y no es lo mismo.
    TONO = {"correcta": COLOR["estructural"], "se abstuvo": "#c9ccd1",
            "cortó un escalón antes": "#b5495b", "saltó la cadena": "#8f3546",
            "otra cuenta del material": "#d98d9b", "contestó la persona": "#e8b9c1"}
    brazos = sorted(modos, key=lambda p: (-modos[p]["correcta"], modos[p]["se abstuvo"]))
    fig, ax = plt.subplots(figsize=(9.0, 5.4))
    izq = [0.0] * len(brazos)
    for m in ORDEN:
        vals = [modos[p][m] for p in brazos]
        ax.barh(brazos, vals, left=izq, color=TONO[m], label=m, height=0.66,
                edgecolor="white", linewidth=1.1)
        for i, (v, x0) in enumerate(zip(vals, izq)):
            if v >= 2:
                ax.text(x0 + v / 2, i, str(v), ha="center", va="center", fontsize=8.6,
                        color="white" if m != "se abstuvo" else TINTA)
        izq = [a + b for a, b in zip(izq, vals)]
    ax.invert_yaxis()
    ax.set_xlabel("respuestas (3 preguntas × 3 réplicas × 2 modelos)")
    ax.grid(axis="x", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)
    # AFUERA DEL AREA DE DATOS: adentro tapaba la barra de `rewoo`, y una leyenda que
    # oculta un dato es peor que ninguna.
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=3, fontsize=8.6,
              labelspacing=0.4, columnspacing=1.6, handlelength=1.4)
    titular(ax, "C3: `dag_strategy` no encadena mejor — es el único que se calla",
            "el banco puntúa «se abstuvo» y «contestó mal» los dos con 0,000, "
            "y esa es la diferencia que el producto vende")
    guardar(fig, "c3-modos-de-falla")


def main() -> None:
    aplicar()
    SALIDA.mkdir(parents=True, exist_ok=True)
    res, panel = datos()
    fig_embudo(res, panel)
    fig_latencia(res, panel)
    fig_c3()


if __name__ == "__main__":
    main()
