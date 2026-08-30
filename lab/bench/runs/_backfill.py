"""Rellenar el registro con campos nuevos, DESDE EL CACHE. Cero tokens. `L-4`.

DE DONDE SALE LA POSIBILIDAD. El cache es content-addressed y guarda el CUERPO COMPLETO de
cada respuesta, no un resumen: ahi estan `completion_tokens_details.reasoning_tokens` y el
bloque `latency_checkpoint` con el tiempo al primer token. Cuando se agrega un campo a
`Row`, volver a correr con `resume=False` re-ejecuta cada celda contra el cache y escribe
las filas otra vez, ahora con el campo. **Ninguna llamada sale al proveedor.**

POR QUE HACE FALTA HACERLO Y NO ALCANZA CON AGREGAR EL CAMPO. Las filas viejas no lo
tienen, y un analizador que promedie sobre ellas reporta cero. Cero de un campo que nunca
se capturo se lee EXACTAMENTE igual que cero medido — es la misma trampa que este banco ya
piso tres veces, y la unica forma de cerrarla es que el dato exista.

SE VERIFICA CONTRA LAS LLAMADAS, NO CONTRA LOS TOKENS. Un acierto de cache REPORTA el uso
de la llamada original —lo correcto para medir el paradigma, lo equivocado para saber si
una corrida gasto— asi que `cost_tokens` de un rellenado perfecto es identico al de la
corrida que copia. La primera version de esta guarda miraba tokens y habria reventado sobre
todo rellenado sano. Lo que decide es `calls - cached_calls`, y tiene que dar cero.

Y SE HACE COPIA ANTES. Reescribir un registro es la operacion mas destructiva del banco: si
el cache no cubre, el archivo queda con menos filas que antes y lo pagado se perdio.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import argparse
import os
import shutil
import sys
import time
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner, load_rows
from bench.runs._run_homogenea import MODELOS


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--model-dir", required=True,
                    help="subcarpeta de results/ (nano, terra, ...)")
    # EL MODELO SALE DE LA TABLA, NO DE ARGUMENTOS SUELTOS (2026-08-29). Estaba clavado
    # a `MAPO_NANO_ENDPOINT` y a `reasoning_effort=None`, o sea que rellenar un registro
    # de `luna` o `terra` habria armado la huella EQUIVOCADA — y con la huella equivocada
    # ninguna clave de cache acierta, asi que el «rellenado» pagaria el registro entero
    # de nuevo. La guarda de gasto lo habria atajado DESPUES de gastar.
    ap.add_argument("--modelo", choices=sorted(MODELOS),
                    help="toma endpoint, key, deployment y esfuerzo de la tabla de "
                         "modelos. Es la forma correcta; `--deployment` queda para "
                         "registros viejos que no esten en la tabla.")
    ap.add_argument("--deployment", help="solo si no se pasa `--modelo`")
    # `--temperature-zero-OBSOLETO` SE SACO EN EL MERGE, y no por limpieza: `temperature`
    # ya no esta en la huella —salio del payload Y de la huella en el mismo movimiento
    # cuando se midio que los modelos de razonamiento la rechazan de plano— asi que el
    # flag no podia cambiar ninguna clave de cache. Un flag que promete afectar la huella
    # y no la afecta es peor que su ausencia: se pasa creyendo que arregla algo.
    #
    # Lo que ese flag queria decir sigue vivo y ahora lo dice el comentario de arriba mas
    # la linea que imprime la huella: si no coincide con la del registro, ninguna clave
    # acierta y esto deja de ser un rellenado.
    args = ap.parse_args()

    if not args.modelo and not args.deployment:
        raise SystemExit("hace falta `--modelo` (preferido) o `--deployment`.")

    base = Settings.from_env()
    if args.modelo:
        m = MODELOS[args.modelo]
        s = replace(
            base,
            endpoint=os.environ[m["endpoint"]].rstrip("/"),
            api_key=os.environ[m["key"]],
            chat_deployment=m["deployment"],
            reasoning_effort=m["esfuerzo"],
            results_dir=base.results_dir / args.model_dir,
        )
    else:
        s = replace(
            base,
            endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
            api_key=os.environ["MAPO_NANO_KEY"],
            chat_deployment=args.deployment,
            reasoning_effort=None,
            results_dir=base.results_dir / args.model_dir,
        )
    print(f"huella del rellenado: {s.fingerprint()}")
    print("Si no coincide con la del registro, NINGUNA clave acierta y esto deja de ser "
          "un rellenado.")
    runner = Runner(s, args.corpus, retriever_arm="hybrid", surface_variant="basic")
    destino = runner._results_path  # noqa: SLF001
    if not destino.exists():
        print(f"{destino} no existe. Nada que rellenar — se dice, no se supone.")
        return

    antes = load_rows(destino)
    # EL ALCANCE SALE DEL ARCHIVO, no de argumentos. Un rellenado tiene que reproducir
    # EXACTAMENTE la corrida original: si corre tareas o brazos que no estaban, esas
    # celdas no tienen entrada de cache y se pagan de verdad — y entonces esto deja de
    # ser un rellenado y pasa a ser una corrida nueva escrita encima de una vieja.
    #
    # Ya paso: la primera version tomaba los paradigmas por argumento y el corpus entero,
    # y arranco a pagar 24 tareas que nunca se habian corrido. La copia salvo el registro.
    tareas = sorted({r["task_id"] for r in antes})
    brazos = sorted({r["paradigm"] for r in antes})
    if not tareas or not brazos:
        print("El registro no declara tareas ni brazos: no hay alcance que reproducir.")
        return
    print(f"alcance leido del registro: {len(tareas)} tareas x {brazos}")
    replicas = max(
        len([r for r in antes
             if r["task_id"] == tareas[0] and r["paradigm"] == brazos[0]]), 1
    )
    copia = destino.with_suffix(destino.suffix + f".pre-backfill-{int(time.time())}")
    shutil.copy2(destino, copia)
    print(f"{len(antes)} filas · copia en {copia.name}")
    destino.unlink()

    try:
        filas = runner.run_cross_product(
            paradigms=brazos, repeat=replicas, task_ids=tareas, resume=False,
            # UN REPLAY PUEDE LEER BRAZOS EN STANDBY. La regla de standby es no GASTAR en
            # ellos, y aca no se gasta: la guarda de abajo compara `calls` contra
            # `cached_calls` y levanta si algo salio al proveedor. Sin esto, un registro que
            # contiene un brazo despriorizado no se podria rellenar nunca — y quedaria con
            # campos en cero que se leen igual que ceros medidos.
            replay_only=True,
        )
    except BaseException:
        # SE RESTAURA ANTE CUALQUIER FALLA, incluido Ctrl-C. El archivo se borro ANTES de
        # correr, asi que una excepcion a mitad —o una guarda del runner que se dispara
        # antes de la primera celda— deja el registro INEXISTENTE y lo pagado perdido
        # salvo por la copia. Ya paso: 402 filas de `nano` desaparecieron porque la guarda
        # de standby corto la corrida despues del `unlink`.
        #
        # `BaseException` y no `Exception` a proposito: una interrupcion tiene que
        # restaurar igual, y es el caso mas probable en una corrida larga.
        shutil.copy2(copia, destino)
        print(f"restaurado {destino.name} desde la copia — el registro no se perdio")
        raise
    # LO QUE DECIDE ES CUANTAS LLAMADAS SALIERON, no cuantos tokens se reportan. Un
    # acierto de cache REPORTA el uso de la llamada original —que es lo correcto para
    # medir el paradigma— asi que `cost_tokens` de un rellenado perfecto es el mismo que
    # el de la corrida que copia. Mirar eso habria hecho fallar todo rellenado sano.
    llamadas = sum(r.calls for r in filas)
    servidas = sum(r.cached_calls for r in filas)
    reales = llamadas - servidas
    # LAS CELDAS QUE HABIAN FALLADO POR INFRA SI VUELVEN A LLAMAR, y eso es correcto: un
    # 429 que agoto el presupuesto de reintento nunca escribio entrada de cache, asi que
    # no hay nada que replayar. Se toleran EXACTAMENTE esas y ninguna mas — tolerar «unas
    # pocas» convertiria la guarda en una advertencia, que es lo que no se quiere.
    fallidas = {(r["task_id"], r["paradigm"], r["trial"]) for r in antes
                if r.get("infra_error")}
    margen = sum(
        r.calls for r in filas if (r.task_id, r.paradigm, r.trial) in fallidas
    )

    if len(filas) < len(antes):
        shutil.copy2(copia, destino)
        raise SystemExit(
            f"El rellenado produjo {len(filas)} filas y habia {len(antes)}. Se restauro "
            f"la copia: un registro con menos filas que antes perdio algo pagado."
        )
    print(f"{len(filas)} filas escritas")
    if reales > margen:
        raise SystemExit(
            f"{reales} de {llamadas} llamadas salieron al proveedor y solo {margen} "
            f"estaban justificadas por celdas con `infra_error` en el registro original. "
            f"Las otras tenian "
            f"que ser CERO: {servidas} vinieron del cache. O el cache no cubria estas "
            f"celdas, o el payload cambio y las claves dejaron de acertar. En los dos "
            f"casos esto no es un rellenado — es una corrida nueva escrita encima de una "
            f"vieja. La copia quedo en {copia.name}."
        )
    print(f"{llamadas} llamadas, {servidas} del cache, {reales} al proveedor "
          f"({margen} justificadas por celdas que habian fallado por infra) — gratis, "
          f"como tenia que ser")

    nuevas = load_rows(destino)
    for campo in ("reasoning_tokens", "first_ttft_ms", "ttft_ms_total"):
        con = sum(1 for r in nuevas if campo in r)
        print(f"  {campo:<18} presente en {con}/{len(nuevas)} filas")


if __name__ == "__main__":
    main()
