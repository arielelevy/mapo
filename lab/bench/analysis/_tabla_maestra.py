"""LA TABLA MAESTRA: los doce brazos, todas sus columnas, en un solo lugar. Cero llamadas.

POR QUÉ EXISTE. El paper mide cada brazo en **cinco tablas distintas** —cobertura y utilidad
en §7.9.1, degradación por ancho en §7.9.2, `pass^3` en §7.10.2, latencia en §7.10.5,
decisiones en §7.10.6— y ninguna las junta. Un lector que quiera decidir «cuál uso» tiene que
cruzar cinco tablas a mano, y dos de ellas están sobre paneles distintos.

    Cinco tablas que nadie cruza son menos útiles que una tabla que dice sus denominadores.

LAS COLUMNAS, y por qué cada una está:

  `aplica`      fracción de celdas donde el mecanismo CORRE. Un brazo tiene dos números y
                colapsarlos esconde el caso que importa: `direct` es el mejor del plantel
                donde corre, y corre en el 6%
  `u`           utilidad donde aplica, con λ=0 — calidad pura, el costo va en su columna
  `u × aplica`  lo que aporta sobre el corpus. Es la que decide si vale tenerlo
  `pass^3`      en cuántas celdas acierta en las TRES réplicas. `u` dice cuánto acierta;
                ésta dice si se puede contar con ello
  `tok/celda`   el costo, desglosado abajo en dólares porque entrada y salida se cobran
                distinto y los brazos se diferencian justo en esa proporción
  `USD/1k`      lo que cuestan mil celdas de ese brazo. Es la unidad con la que se decide
                comprar, y un total en tokens no lo es
  `serie`       la latencia SERIAL: la suma del tiempo al primer token sobre todas las
                llamadas, o sea la parte que no se acelera con más tokens por segundo
  `ley`         de qué es función su costo: alcance, vueltas, o nada

LOS DENOMINADORES SE IMPRIMEN, y no al pie. `aplica` y `u` salen del registro entero por
brazo; `pass^3` y `serie` sólo del rectángulo con tres réplicas. Son universos distintos y la
tabla lo dice en cada fila que corresponde, porque la versión anterior de este cruce ponía
tres valores de `u` para el mismo brazo en tres secciones sin declarar el panel.

Corre DESDE `lab/`:  py bench/analysis/_tabla_maestra.py [--markdown]
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

_sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.runner import load_rows
from bench.fiabilidad import perfil
from bench.panel import rectangulo

REGISTRO = Path("results/luna/gold_h1_rows.jsonl")
CORPUS = Path("corpus/gold_h1")
MODELO = "luna"

# De qué es función el costo de cada brazo. Declarado desde el código, igual que en
# `_estilo.py` — el color del paper y esta columna significan lo mismo.
LEY = {
    "handoff": "alcance",
    "react": "vueltas", "reflection": "vueltas", "supervisor": "vueltas",
    "dag_strategy": "vueltas", "gist_reader": "vueltas", "pointer_chase": "vueltas",
    "rewoo": "estructural", "direct": "estructural", "graph_traverse": "estructural",
    "extract_compute": "estructural", "streaming_scan": "estructural",
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--markdown", action="store_true", help="emitir para pegar en el paper")
    args = ap.parse_args()

    tar = json.loads(Path("config/tariffs.json").read_text(encoding="utf-8"))
    t = tar["tariffs"][MODELO]
    p_in, p_out = t["prompt"], t["completion"]

    tareas = json.loads((CORPUS / "tasks.json").read_text(encoding="utf-8"))
    n_tareas = len(tareas)
    todas = load_rows(REGISTRO)

    # ── universo 1: el registro entero, por brazo ───────────────────────────────
    # `aplica` ES FACTIBILIDAD, NO COBERTURA DE CAMPAÑA, y la primera versión de esta tabla
    # las confundía: dividía por las 78 del corpus, así que `react` figuraba con 86% porque
    # la campaña le corrió 67 tareas — un accidente de qué se ejecutó, no una propiedad del
    # brazo. Con ese denominador, un brazo que nunca se corrió parece infactible.
    #
    # El denominador correcto son las celdas que se le OFRECIERON a ese brazo: de ésas,
    # cuántas pasaron el portón aritmético. Es el mismo numerador/denominador que la lección
    # del regrade ya nombra — un defecto uniforme sobre las TAREAS no es uniforme sobre los
    # BRAZOS, porque los brazos no corren el mismo conjunto.
    ofrecidas: dict[str, set[str]] = defaultdict(set)
    factible: dict[str, set[str]] = defaultdict(set)
    util: dict[str, list[float]] = defaultdict(list)
    tok: dict[str, list[int]] = defaultdict(list)
    usd: dict[str, list[float]] = defaultdict(list)
    for f in todas:
        p = f["paradigm"]
        ofrecidas[p].add(f["task_id"])
        if f.get("infeasible"):
            continue
        factible[p].add(f["task_id"])
        util[p].append(f.get("utility", 0.0))
        tok[p].append(f.get("cost_tokens") or 0)
        usd[p].append(((f.get("prompt_tokens") or 0) * p_in
                       + (f.get("completion_tokens") or 0) * p_out) / 1e6)

    # ── universo 2: el rectángulo con tres réplicas ─────────────────────────────
    factibles = [f for f in todas if not f.get("infeasible")]
    panel = rectangulo([{"task_id": f["task_id"], "paradigm": f["paradigm"],
                         "infeasible": False} for f in factibles])
    pf = {x.paradigma: x for x in perfil(factibles, k=3, tareas=panel.tareas,
                                         brazos=panel.brazos)}
    ser: dict[str, list[float]] = defaultdict(list)
    for f in factibles:
        if f["task_id"] in set(panel.tareas) and f["paradigm"] in set(panel.brazos):
            v = f.get("ttft_ms_total")
            if v:
                ser[f["paradigm"]].append(v / 1000.0)

    filas = []
    for p in sorted(ofrecidas, key=lambda p: -(statistics.mean(util[p]) if util[p] else 0)
                    * len(factible[p]) / max(len(ofrecidas[p]), 1)):
        aplica = len(factible[p]) / len(ofrecidas[p])
        u = statistics.mean(util[p])
        filas.append({
            "brazo": p, "aplica": aplica, "u": u, "aporta": u * aplica,
            "pass3": pf[p].pass_k if p in pf else None,
            "tok": statistics.mean(tok[p]),
            "usd1k": statistics.mean(usd[p]) * 1000,
            "serie": statistics.median(ser[p]) if ser.get(p) else None,
            "ley": LEY.get(p, "?"),
        })

    if args.markdown:
        print("| brazo | aplica | u | u × aplica | pass^3 | tok/celda | USD/1k celdas | "
              "serie | ley de costo |")
        print("|---|---:|---:|---:|---:|---:|---:|---:|---|")
        for f in filas:
            p3 = f"{f['pass3']:.3f}".replace(".", ",") if f["pass3"] is not None else "—"
            se = f"{f['serie']:.2f} s".replace(".", ",") if f["serie"] is not None else "—"
            print(f"| `{f['brazo']}` | {f['aplica']:.0%} | "
                  f"{f['u']:.3f}".replace(".", ",")
                  + f" | {f['aporta']:.3f}".replace(".", ",")
                  + f" | {p3} | {f['tok']:,.0f} | "
                  + f"{f['usd1k']:,.0f}".replace(",", ".")
                  + f" | {se} | {f['ley']} |")
        return

    print("=" * 104)
    print(f"LA TABLA MAESTRA — {MODELO} · {n_tareas} tareas del corpus")
    print("=" * 104)
    print(f"\n  `aplica`, `u`, `u x aplica`, `tok` y `USD`: registro ENTERO por brazo")
    print(f"  `pass^3` y `serie`: sólo el rectángulo — {panel.descripcion()}")
    print(f"  Aranceles: {tar['source']} verificado {tar['verified_on']} · "
          f"{MODELO} {p_in}/{p_out} USD por millón (entrada/salida)\n")
    print(f"  {'brazo':<16}{'aplica':>8}{'u':>8}{'aporta':>9}{'pass^3':>9}"
          f"{'tok/celda':>12}{'USD/1k':>10}{'serie':>9}  ley")
    for f in filas:
        p3 = f"{f['pass3']:.3f}" if f["pass3"] is not None else "—"
        se = f"{f['serie']:.2f}s" if f["serie"] is not None else "—"
        print(f"  {f['brazo']:<16}{f['aplica']:>8.0%}{f['u']:>8.3f}{f['aporta']:>9.3f}"
              f"{p3:>9}{f['tok']:>12,.0f}{f['usd1k']:>10,.0f}{se:>9}  {f['ley']}")

    print(f"""
  COMO SE LEE, y las tres cosas que la tabla hace visibles de un vistazo:

  · **`u` y `u x aplica` son dos numeros distintos y ninguno reemplaza al otro.** `direct`
    es el mejor del plantel donde corre y aporta casi nada, porque corre casi nunca. La
    factibilidad decide eso ANTES del primer token, no es que falle en el resto.
  · **`pass^3` siempre es menor que `u`**, y la diferencia es la varianza que vive DENTRO de
    una celda — invisible para cualquier piso de ruido entre brazos.
  · **La columna de dolares no es la de tokens reescalada.** Entrada y salida se cobran 6x
    distinto en este modelo, y los brazos se diferencian justo en esa proporcion.
""")


if __name__ == "__main__":
    main()
