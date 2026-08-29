"""La corrida homogénea: el plantel entero, sobre el mismo corpus, en las mismas condiciones.

QUE CIERRA. Es la BASE de la campaña — 12 patrones × 78 tareas × repeat 3 sobre `gold_h1`,
`hybrid`/`basic`/`nano`. Cierra el ranking homogéneo y, con él, `D-4` (handoff), `P-2b`
(drift, que sólo necesita episodios) y `P-2e`. Los factores van DESPUÉS y en corridas
propias: acá no se cruza nada.

POR QUE «HOMOGENEA» Y NO «LA CAMPAÑA». Los veredictos que sacaron brazos del catálogo se
tomaron cada uno bajo su propio régimen: otro corpus, otro tokenizador, sin entidades, con
`offer_board` que no llegaba al modelo. Un ranking armado con esos números compara
mediciones que nunca coexistieron. El valor de esto está en que **todos corran bajo las
mismas condiciones**, y por eso el plantel incluye brazos que el catálogo bloquea — nombrados
uno por uno en `CAMPAIGN_INCLUDE`, no por un `include_all` que volvería invisible lo que el
catálogo existe para hacer visible.

RESUMIBLE, Y ESO NO ES UN EXTRA. `Runner.existing_keys()` saltea toda celda
`(tarea, paradigma, trial)` que ya esté en el `.jsonl`, así que **relanzar continúa, no
reempieza**. Importa porque una corrida en background muere con la sesión y esto son horas:
la disciplina es lanzar, y si se corta, volver a lanzar lo mismo.

Y POR ESO SE CORRE POR ANCHO, DE MENOR A MAYOR. `w4` (5,9% del gasto), después `w16`
(20,3%), después `w48` (60,8%). No es para ahorrar —el total es el mismo— es para que una
interrupción deje **estratos completos** en vez de un borde dentado: un `w4`+`w16` entero se
puede analizar, un 60% repartido al azar no. Las tareas sin width van primero, con `w4`.

DE A UNA. Dos procesos de esto appendean al MISMO `.jsonl`. El lock impide el archivo
corrupto, no el conteo doble — ya pasó con la light, que reportó 77 filas sobre 52 celdas.

ANTES DE LANZAR: `py bench/_listo.py`. Son las ocho condiciones del protocolo, y esto se
niega a arrancar si no pasan.
"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.paradigms import campaign_roster
from app.runner import Runner

CORPUS = "gold_h1"
REPEAT = 3
RAZON = (
    "corrida homogenea: el plantel entero bajo las mismas condiciones. Incluye brazos "
    "que el catalogo bloquea, nombrados en CAMPAIGN_INCLUDE — un ranking armado con "
    "veredictos de regimenes distintos compara mediciones que nunca coexistieron"
)

# El orden de ejecucion. Ver el docstring: una interrupcion deja estratos completos.
ORDEN = ("w4", "w16", "w48")


def _ancho(task_id: str) -> str:
    cola = task_id.rsplit("-", 1)[-1]
    return cola if cola in ORDEN else ORDEN[0]


def _listo() -> None:
    """Las ocho condiciones, o no se arranca.

    NO ES CINTURON Y TIRADORES. La corrida light y los tests son baratos y esto es caro;
    un protocolo que depende de que alguien se acuerde no es un protocolo. Se puede saltear
    con `--sin-chequeo`, y saltearlo es una decision que queda escrita en la consola.
    """
    print("Chequeando las ocho condiciones (`bench/_listo.py`)...\n", flush=True)
    p = subprocess.run([sys.executable, "bench/_listo.py"])
    if p.returncode != 0:
        raise SystemExit(
            "\nNO SE LANZA: alguna condicion no se cumple. Arriba esta cual."
        )
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--anchos", default=",".join(ORDEN),
                    help="que estratos correr, en orden. Por defecto los tres.")
    ap.add_argument("--repeat", type=int, default=REPEAT)
    ap.add_argument("--sin-chequeo", action="store_true",
                    help="saltear `bench/_listo.py`. Queda escrito en la consola.")
    # PROBAR ESTO NO PUEDE ARRANCAR LA CAMPAÑA, y hace falta decirlo porque ya paso: correr
    # el runner «para ver si imprime bien» escribio 8 filas en el `.jsonl` de la campaña.
    # Esas filas eran validas —mismo corpus, mismo plantel, trial 0— asi que no ensuciaron
    # nada, y el susto es el punto: la version sin esta bandera no tenia ningun camino para
    # ejercitar el runner sin tocar el archivo real.
    ap.add_argument("--ensayo", action="store_true",
                    help="escribe en `results/_ensayo/` en vez del archivo de la campaña. "
                         "Para probar el runner sin tocarla.")
    args = ap.parse_args()

    if args.sin_chequeo:
        print("[!] SE SALTEO EL CHEQUEO DE LAS OCHO CONDICIONES, por pedido explicito.\n")
    else:
        _listo()

    anchos = [a.strip() for a in args.anchos.split(",") if a.strip()]
    desconocidos = [a for a in anchos if a not in ORDEN]
    if desconocidos:
        raise SystemExit(f"anchos desconocidos: {desconocidos}. Validos: {list(ORDEN)}")

    base = Settings.from_env()
    settings = replace(
        base,
        endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
        api_key=os.environ["MAPO_NANO_KEY"],
        chat_deployment="gpt-5.4-nano",
        temperature=0.0,
        results_dir=base.results_dir / "_ensayo" if args.ensayo else base.results_dir,
    )
    if args.ensayo:
        print("[ensayo] escribe en `results/_ensayo/`. NADA de esto es la campana.\n")
    roster = campaign_roster()
    runner = Runner(settings, CORPUS, retriever_arm="hybrid", surface_variant="basic")

    por_ancho: dict[str, list[str]] = {a: [] for a in ORDEN}
    for t in runner._tasks:  # noqa: SLF001
        por_ancho[_ancho(t["task_id"])].append(t["task_id"])

    total_celdas = sum(len(por_ancho[a]) for a in anchos) * len(roster) * args.repeat
    ya = len(runner.existing_keys())
    print(f"corpus {CORPUS} · {len(roster)} patrones · repeat {args.repeat}")
    print(f"plantel: {roster}")
    print(f"estratos: {anchos}")
    print(f"celdas del plan: {total_celdas:,}   ya en el archivo: {ya:,}")
    print(f"archivo: {runner._results_path}\n")  # noqa: SLF001

    resumen = []
    arranque_total = time.perf_counter()
    for a in anchos:
        tareas = sorted(por_ancho[a])
        if not tareas:
            print(f"=== {a}: sin tareas, se saltea")
            continue
        print(f"\n{'=' * 78}\n=== ESTRATO {a} — {len(tareas)} tareas × "
              f"{len(roster)} patrones × {args.repeat}\n{'=' * 78}", flush=True)
        arranque = time.perf_counter()
        filas = runner.run_cross_product(
            paradigms=roster, task_ids=tareas, repeat=args.repeat,
            baseline_reason=RAZON,
        )
        minutos = (time.perf_counter() - arranque) / 60
        errores = [f for f in filas if f.error]
        infra = [f for f in filas if f.infra_error]
        gasto = sum(f.cost_tokens for f in filas)
        resumen.append({
            "ancho": a, "tareas": len(tareas), "filas_nuevas": len(filas),
            "errores": len(errores), "infra": len(infra),
            "tokens": gasto, "minutos": round(minutos, 1),
        })
        print(f"\n=== {a}: {len(filas)} filas nuevas · {len(errores)} errores · "
              f"{len(infra)} infra · {gasto:,} tokens · {minutos:.1f} min", flush=True)
        for f in errores[:10]:
            print(f"    ERROR {f.paradigm:<15} {f.task_id:<14} {str(f.error)[:80]}")
        # UN INFRA_ERROR NO ES PARTE DE LA EVALUACION, y por eso se avisa fuerte: la fila
        # queda registrada y FUERA de toda estadistica, pero la celda sigue sin medirse.
        # Volver a lanzar la completa, que es exactamente para lo que sirve el resume.
        if infra:
            print(f"    [!] {len(infra)} fallos de INFRAESTRUCTURA. No puntuan, y esas "
                  f"celdas quedan SIN MEDIR: relanzar para completarlas.")

    print("\n" + "=" * 78)
    total = sum(r["tokens"] for r in resumen)
    print(f"TOTAL de esta pasada: {total:,} tokens en "
          f"{(time.perf_counter() - arranque_total) / 60:.1f} min")
    print(f"celdas en el archivo ahora: {len(runner.existing_keys()):,} de "
          f"{total_celdas:,} del plan")
    faltan = total_celdas - len(runner.existing_keys())
    if faltan > 0:
        print(f"\nFALTAN {faltan:,} celdas. Volver a lanzar CONTINUA — no reempieza.")
    else:
        print("\nEl plan esta completo.")
    salida = settings.results_dir / "homogenea_resumen.json"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"resumen -> {salida}")


if __name__ == "__main__":
    main()
