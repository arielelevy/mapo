"""Maxima cobertura con minimas llamadas: el 10x que el registro ya senala.

EL NUMERO QUE LO MOTIVA, MEDIDO SOBRE 704 CELDAS YA PAGADAS y no propuesto:

    <= 2 llamadas al modelo     234 celdas      9.779 tokens     u = 0,509
    >= 8 llamadas                65 celdas    136.432 tokens     u = 0,631

    14x mas tokens, y +0,122 de utilidad.

LA CAUSA ES ESTRUCTURAL Y NO DEL MODELO: la conversacion se reenvia ENTERA en cada
vuelta, asi que el costo de N llamadas crece como el cuadrado de N mientras la cobertura
crece como N. Un texto leido en la vuelta 2 se vuelve a pagar en la vuelta 12.

LA COBERTURA POR LLAMADA, HOY, y ninguno pasa de dos unidades por llamada:

    handoff 1,60 · gist_reader 1,49 · react 1,41 · dag_strategy 0,81 · reflection 0,63

`read_all` lee TODAS las unidades en UNA llamada. Y hoy **no esta ofrecido en `basic`**,
que es la variante de todos los estudios medidos: el modelo nunca pudo pedir el material
entero aunque entrara comodo en su presupuesto. Eso no fue una decision que alguien tomo
midiendo — es una consecuencia de en que lista de tools quedo.

QUE SE CRUZA, y son tres brazos y no cuatro porque `base` ya lo esta produciendo la
corrida del board sobre las mismas tareas: reusarlo es gratis y correrlo de nuevo seria
appendear al mismo `.jsonl` desde dos procesos, que es la falla que este repo ya se comio.

    readall      `offer_read_all=True` sobre `basic` — la tool sola, SIN el resto de la
                 contabilidad, para que lo que se mida sea `read_all` y no el paquete
    accounting   la variante entera: `read_all` **mas** `coverage`, la tool que dice
                 cuanto falta. La hipotesis es que sin `coverage` el modelo no sabe que
                 le conviene pedir todo

POR QUE SOLO `react`. Es el bucle iterativo puro y el mas caro por unidad leida (10.878
tokens/unidad). Si el 10x existe en algun lado esta ahi, y un solo brazo hace la corrida
barata. `dag_strategy` y `reflection` entran despues si esto dice algo.

LA TRAZA POR LLAMADA SE ENCIENDE ACA (`MAPO_TRACE=1`). Sin ella la fila dice `calls=17` y
`cost_tokens=234.341` y **no cual llamada costo que** — que es exactamente el numero que
hace falta cuando lo que se estudia es como crece la ventana entre vueltas.

Corre DESDE `lab/`:  py bench/runs/_run_cobertura.py --modelo luna
DE A UNA: esperar a que termine la corrida del board.
"""

from __future__ import annotations

import argparse
import json
import os
import sys as _sys
import time
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner
from bench.runs._run_homogenea import MODELOS

CORPUS = "gold_h1"
BRAZOS = ("react",)
RAZON = "cobertura maxima con llamadas minimas: el 10x que el registro senala"

CELDAS = [
    ("readall", {"offer_read_all": True}),
    ("accounting", {"surface_variant": "accounting"}),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--modelo", default="luna", choices=sorted(MODELOS))
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--ancho", default="w16", help="w4, w16 o w48")
    ap.add_argument("--solo", default="",
                    help="coma-separada: correr solo estas celdas. `readall` es el brazo "
                         "que AISLA el mecanismo; `accounting` cambia dos cosas a la vez "
                         "(trae `read_all` Y `coverage`), asi que su efecto no es "
                         "atribuible a ninguna de las dos por separado.")
    ap.add_argument("--ensayo", action="store_true")
    args = ap.parse_args()

    # LA TRAZA ES EL PUNTO DE ESTA CORRIDA, asi que se enciende sin preguntar.
    os.environ["MAPO_TRACE"] = "1"

    modelo = MODELOS[args.modelo]
    base = Settings.from_env()
    settings = replace(
        base,
        endpoint=os.environ[modelo["endpoint"]].rstrip("/"),
        api_key=os.environ[modelo["key"]],
        chat_deployment=modelo["deployment"],
        reasoning_effort=modelo["esfuerzo"],
        results_dir=base.results_dir / args.modelo,
    )
    tareas_todas = json.loads(
        (_Path("corpus") / CORPUS / "tasks.json").read_text(encoding="utf-8")
    )
    tareas = [t["task_id"] for t in tareas_todas if args.ancho in t["task_id"]]

    print(f"modelo {args.modelo} · huella {settings.fingerprint()}")
    print(f"{len(tareas)} tareas de {args.ancho} × {len(BRAZOS)} brazo × "
          f"repeat {args.repeat}")
    print(f"traza por llamada: {settings.results_dir / 'traces'}\n", flush=True)

    # EL FILTRO SE CALCULA ANTES DEL ENSAYO. Estaba después, así que `--ensayo` reventaba
    # sobre una variable que todavía no existía — y un ensayo que no corre no puede
    # cumplir su única función, que es decir qué se va a gastar antes de gastarlo.
    celdas = [c for c in CELDAS if not args.solo or c[0] in args.solo.split(",")]
    if not celdas:
        raise SystemExit(f"`--solo {args.solo}` no matchea ninguna celda: "
                         f"{[n for n, _ in CELDAS]}")

    if args.ensayo:
        for n, kw in celdas:
            print(f"  {n:<12}{kw}")
        print("\nENSAYO: no se gasta nada.")
        return

    resumen = []
    for nombre, kw in celdas:
        arranque = time.perf_counter()
        runner = Runner(settings, CORPUS, retriever_arm="hybrid",
                        surface_variant=kw.pop("surface_variant", "basic"), **kw)
        runner.run_cross_product(
            paradigms=list(BRAZOS), task_ids=tareas, repeat=args.repeat,
            baseline_reason=RAZON,
        )
        filas = [f for f in runner.load_rows() if not f.get("infeasible")]
        if not filas:
            print(f"[{nombre}] sin filas medidas")
            continue
        tok = sum(f["cost_tokens"] for f in filas) / len(filas)
        u = sum(f["utility"] for f in filas) / len(filas)
        llamadas = sum(f.get("calls", 0) or 0 for f in filas) / len(filas)
        # LA COBERTURA ES EL EJE, no un extra: el punto no es gastar menos sino ver mas
        # por llamada. Un brazo que abarata bajando la cobertura no gano nada.
        leidas = sum((f.get("tool_usage") or {}).get("units_read", 0)
                     for f in filas) / len(filas)
        frac = sum((f.get("tool_usage") or {}).get("fraction_read", 0)
                   for f in filas) / len(filas)
        resumen.append({
            "celda": nombre, "filas": len(filas), "tok_celda": round(tok),
            "u": round(u, 4), "llamadas": round(llamadas, 2),
            "unidades": round(leidas, 2), "fraccion_leida": round(frac, 3),
            "unid_por_llamada": round(leidas / max(1e-9, llamadas), 2),
            "minutos": round((time.perf_counter() - arranque) / 60, 1),
            "archivo": runner._results_path.name,
        })
        r = resumen[-1]
        print(f"[{nombre}] {r['filas']} filas · u={r['u']} · {r['tok_celda']:,} tok/celda "
              f"· {r['llamadas']} llamadas · {r['unidades']} unidades "
              f"({r['unid_por_llamada']}/llamada, {100*r['fraccion_leida']:.0f}% del "
              f"material) · {r['minutos']} min", flush=True)

    salida = settings.results_dir / "cobertura_summary.json"
    salida.write_text(json.dumps(resumen, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    print(f"\n-> {salida}")
    print("La comparacion contra `base` sale del archivo de la corrida del board: "
          "`react` sobre las mismas tareas, sin `read_all`.")


if __name__ == "__main__":
    main()
