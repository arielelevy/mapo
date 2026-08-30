"""El board y el guard, cruzados: `{cola, sin} x {guard, sin}` sobre `w16`.

QUE PREGUNTA CONTESTA. La capa de ejecucion anterior —congelada, la unica que corrio
contra un indice real— tenia UN mecanismo en dos piezas: el guard acota la ventana por
crecimiento y **produce** un hallazgo enfocado en la pregunta, y el board lo conserva y
con eso **dirige** lo que sigue (cobertura, no-repetir, y una directiva derivada del
numero). El banco tenia las dos mitades rotas por separado:

  el board  llegaba al modelo por la plantilla de `dag_strategy` y por una tool que el
            modelo llamo **1 vez en 125 llamadas**. Un agente SOLO no podia llevar cola
  el guard  no existia. Las dos compactaciones del banco DEGRADAN —`compact_history` a
            un stub si el modelo anoto (1 nota en 28 filas), `manage_history` a un gist
            incondicional (61 llamadas sobre `w4`, 0 mensajes degradados)— y ninguna
            PRODUCE contenido nuevo

POR ESO SE CRUZAN Y NO SE MIDEN POR SEPARADO. Medir la cola sola mide media maquina: sus
hallazgos seguirian siendo lo que el modelo se acuerde de postear. Y medir el guard solo
deja el hallazgo rescatado en un board que nadie dirige.

POR QUE `w16` Y NO `w4`. El guard dispara por CRECIMIENTO —20k caracteres en una
iteracion— y la cola solo compra algo donde leer todo no es la opcion obvia. En `w4` el
material entra comodo: los dos factores correrian y medirian su propia irrelevancia, que
se lee igual que un efecto nulo. `w16` es el estrato mas barato donde la pregunta existe.

POR QUE ESTOS DOS BRAZOS. Son los dos casos que el mecanismo distingue, y son los mas
baratos que los ejercitan:

  `react`         un agente SOLO con su propia cola de evidencia y pendientes. Es la
                  version general, la que la correccion del autor puso en el centro
  `dag_strategy`  un GRUPO compartiendo una. Ya tiene board estructural escrito por el
                  codigo, asi que mide que agrega la cola sobre algo que ya coordina

`reflection` queda afuera por precio (121M proyectados en la campana entera) y
`supervisor` por lo mismo en menor grado: entran despues si el cruce dice algo.

COSTO ESTIMADO CONTRA EL CORPUS, no contra el registro: ~12,6M tokens por brazo del
cruce, ~25M los cuatro. La estimacion sale de `bench/_estimate.py` (tokens por unidad de
material, por paradigma) x las 21 tareas de `w16` x repeat 3. Una corrida parcial no
sirve para estimar: ese error costo 34x una vez.

Y LA EXTRACCION DEL GUARD ES UNA LLAMADA AL MODELO Y SE COBRA. La proyeccion de arriba
NO la incluye, asi que los brazos con guard van a salir mas caros que su estimacion — eso
es el punto de medirlo, no una sorpresa.

Corre DESDE `lab/`:  py bench/runs/_run_board.py --modelo luna
DE A UNA: dos procesos appendean al mismo `.jsonl` y el resumen sale con mas filas que
celdas.
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

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dataclasses import replace

from app.config import Settings
from app.runner import Runner
from bench.runs._run_homogenea import MODELOS

CORPUS = "gold_h1"
BRAZOS = ("react", "dag_strategy")
RAZON = "cruce board x guard: el mecanismo de la capa anterior, en dos piezas"

# EL CRUCE, y `base` va primero porque es contra lo que se mide todo lo demas.
CELDAS = [
    ("base", {}),
    ("cola", {"board_queue": True}),
    ("guard", {"context_guard": True}),
    ("ambos", {"board_queue": True, "context_guard": True}),
]


def tareas_w16(settings: Settings) -> list[str]:
    ruta = _Path("corpus") / CORPUS / "tasks.json"
    tareas = json.loads(ruta.read_text(encoding="utf-8"))
    return [t["task_id"] for t in tareas if "w16" in t["task_id"]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--modelo", default="luna", choices=sorted(MODELOS))
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--solo", default="", help="coma-separada: correr solo estas celdas")
    ap.add_argument("--ensayo", action="store_true", help="listar y salir, sin gastar")
    args = ap.parse_args()

    modelo = MODELOS[args.modelo]
    # El endpoint y la key salen del MODELO, no del entorno global: cada uno vive en su
    # propio recurso y mezclarlos da un 404 que no se parece a su causa.
    base = Settings.from_env()
    settings = replace(
        base,
        endpoint=os.environ[modelo["endpoint"]].rstrip("/"),
        api_key=os.environ[modelo["key"]],
        chat_deployment=modelo["deployment"],
        reasoning_effort=modelo["esfuerzo"],
        results_dir=base.results_dir / args.modelo,
    )
    tareas = tareas_w16(settings)
    celdas = [c for c in CELDAS
              if not args.solo or c[0] in args.solo.split(",")]

    print(f"modelo {args.modelo} ({modelo['deployment']}) · huella {settings.fingerprint()}")
    print(f"{len(tareas)} tareas de w16 × {len(BRAZOS)} brazos × repeat {args.repeat}")
    print(f"celdas del cruce: {', '.join(n for n, _ in celdas)}\n", flush=True)

    if args.ensayo:
        print("ENSAYO: no se gasta nada.")
        for n, kw in celdas:
            print(f"  {n:<8}{kw or '(la base)'}")
        return

    resumen = []
    for nombre, kw in celdas:
        arranque = time.perf_counter()
        runner = Runner(settings, CORPUS, retriever_arm="hybrid",
                        surface_variant="basic", **kw)
        runner.run_cross_product(
            paradigms=list(BRAZOS), task_ids=tareas, repeat=args.repeat,
            baseline_reason=RAZON,
        )
        # Contra el ARCHIVO y no contra lo que devolvio la corrida: con resume una celda
        # ya presente se saltea y no vuelve en la lista, y comparar el retorno daria
        # «inerte» en una corrida reanudada.
        filas = runner.load_rows()
        gasto = sum(f.get("cost_tokens", 0) for f in filas)
        util = [f["utility"] for f in filas if not f.get("infeasible")]
        # Los tres numeros del guard salen SEPARADOS: expulsiones, rescates, y las veces
        # que el texto expulsado no aportaba nada a la pregunta. La tercera es
        # informacion sobre la RECUPERACION y colapsarla con las otras la perderia.
        ev = sum((f.get("tool_usage") or {}).get("guard_evictions", 0) for f in filas)
        ex = sum((f.get("tool_usage") or {}).get("guard_extracted", 0) for f in filas)
        na = sum((f.get("tool_usage") or {}).get("guard_evicted_nothing", 0) for f in filas)
        hall = sum((f.get("tool_usage") or {}).get("board_findings", 0) for f in filas)
        resumen.append({
            "celda": nombre, "filas": len(filas), "tokens": gasto,
            "u": round(sum(util) / len(util), 4) if util else None,
            "expulsiones": ev, "rescates": ex, "vacios": na, "hallazgos": hall,
            "minutos": round((time.perf_counter() - arranque) / 60, 1),
            "archivo": runner._results_path.name,
        })
        r = resumen[-1]
        print(f"[{nombre}] {r['filas']} filas · u={r['u']} · {gasto:,} tok · "
              f"expulsiones {ev} (rescates {ex}, vacios {na}) · "
              f"hallazgos {hall} · {r['minutos']} min", flush=True)

    salida = settings.results_dir / "board_guard_summary.json"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(resumen, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    print(f"\n-> {salida}")


if __name__ == "__main__":
    main()
