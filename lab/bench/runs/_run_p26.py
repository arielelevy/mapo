"""P26: HyDE como rama fusionada, contra `hybrid`, con el costo cobrado.

QUE SE CORRE Y POR QUE LOS DOS BRAZOS. Los dos, aunque `hybrid` sobre `gold_p18` ya este
en el registro. Esas filas se pagaron ANTES de dos cambios de codigo —el cobro por medidor
de celda y `dag_shape`— y comparar a traves de un cambio de codigo es comparar dos
experimentos. El cache content-addressed hace que la mayor parte de `hybrid` vuelva gratis,
asi que la comparacion limpia cuesta casi lo mismo que la sucia.

COTA SUPERIOR ESTIMADA, calculada antes de correr sobre el registro existente:

  hybrid        ~362k tokens, mayormente CACHE (los prompts no cambiaron donde la forma
                del DAG coincide con los topes viejos: 30 de 32 tareas)
  hybrid_hyde   ~362k de los paradigmas, con cache FRIO —la recuperacion devuelve otras
                unidades, asi que los prompts son otros— mas <= 307 x 220 = 68k de
                generaciones
  TOTAL         ~792k tokens. Referencia nano: ~USD 0,07

LA ESTIMACION DE ARRIBA SALIO ~18x BAJA Y SE DEJA ESCRITA, no se corrige en su lugar: es
la unica forma de que la proxima estimacion se haga distinto. Lo medido, sobre `hybrid`:
`dag_strategy` sola cuesta **7,15M** tokens en 96 filas (74.485 por fila) y las otras tres
juntas 5,24M. El error no fue de aritmetica sino de MODELO: se proyecto desde el registro
de `hybrid` suponiendo cache caliente, y para `hybrid_hyde` el cache esta FRIO por
construccion —la recuperacion devuelve otras unidades, asi que los prompts son otros—, que
es justo lo que el parrafo de arriba dice y la suma no uso. El total real de P26 es
~12,4M, ~USD 2 de referencia nano.

LAS PREDICCIONES ESTAN REGISTRADAS EN README.md (P26a-d) ANTES de esta corrida. La que
importa es P26d: el ORDEN de los paradigmas no cambia con el brazo. Si cambiara, «el mejor
paradigma» seria en parte un artefacto de la calidad de busqueda, y se caeria toda
comparacion entre brazos hecha hasta hoy.

UN 429 NO ES PARTE DE LA EVALUACION. Las filas `infra_error` quedan en el archivo y fuera
de toda estadistica; `load_rows` las excluye por defecto.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import os
import sys
import time
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner

CORPUS = "gold_p18"
REPEAT = 3
# SIN `map_reduce`: despriorizado por decision del autor, y el runner se niega a correrlo
# en vez de gastar cuota. Su dato historico se replaya desde las filas ya pagadas.
PARADIGMS = ["dag_strategy", "gist_reader", "react", "rewoo"]
BRAZOS = ["hybrid", "hybrid_hyde"]

# SE PARAMETRIZA PORQUE LA CORRIDA QUEDO A MEDIAS Y RETOMARLA ENTERA NO ES GRATIS.
# `resume=True` salta las celdas que ya estan, asi que volver a lanzar el script completo
# no re-cobraria lo hecho — pero tampoco DECLARA que se esta corriendo una pata sola, y un
# log que dice «brazos=[hybrid, hybrid_hyde]» sobre una corrida que toco un paradigma en un
# brazo es un registro que miente por omision. El argumento hace visible el alcance real.
if len(sys.argv) > 1:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--paradigms", default=",".join(PARADIGMS))
    ap.add_argument("--arms", default=",".join(BRAZOS))
    ns = ap.parse_args()
    PARADIGMS = [x for x in ns.paradigms.split(",") if x]
    BRAZOS = [x for x in ns.arms.split(",") if x]

base = Settings.from_env()
settings = replace(
    base,
    endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
    api_key=os.environ["MAPO_NANO_KEY"],
    chat_deployment="gpt-5.4-nano",
    temperature=0.0,
    results_dir=base.results_dir / "nano",
)

print(f"modelo: {settings.fingerprint()}", flush=True)
print(f"corpus: {CORPUS} | brazos={BRAZOS} | repeat={REPEAT}", flush=True)
print("cota superior estimada: ~792k tokens (~USD 0,07 de referencia)", flush=True)

total = 0
for brazo in BRAZOS:
    runner = Runner(
        settings, CORPUS,
        retriever_arm=brazo, surface_variant="basic",
    )
    print(f"\n=== {brazo} -> {runner._results_path.name}", flush=True)  # noqa: SLF001
    started = time.perf_counter()
    rows = runner.run_cross_product(paradigms=PARADIGMS, repeat=REPEAT)

    gastado = sum(r.cost_tokens for r in rows)
    recuperacion = sum(r.retrieval_tokens for r in rows)
    infra = sum(1 for r in rows if r.infra_error)
    total += gastado
    print(f"  filas: {len(rows)}  ({infra} infra_error, fuera de toda estadistica)")
    print(f"  tokens: {gastado:,}  de los cuales recuperacion: {recuperacion:,}")
    print(f"  wall: {(time.perf_counter() - started) / 60:.1f} min", flush=True)

print(f"\nTOTAL: {total:,} tokens")
