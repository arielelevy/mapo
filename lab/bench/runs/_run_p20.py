"""P20: la regla de parada, con el factor encendido. Predicciones en README (P20a-d).

POR QUE ESTA CORRIDA CUESTA MUCHO MENOS DE LO QUE PARECE. El factor solo cambia lo que el
paradigma puede hacer DONDE LA REGLA DISPARA. En una celda que nunca acumulo tres busquedas
esteriles seguidas, la superficie devuelve exactamente lo mismo, el payload es identico y la
llamada es un hit de cache: cero tokens nuevos.

Medido sobre el registro replayado, con umbral 3:

  73 de 336 filas tienen `barren_peak >= 3` y pueden disparar
  esas filas costaron 3.371.617 tokens en la corrida original
  las otras 263 son hits de cache

Asi que la cota superior es ~3,4M y no los ~9,8M que da multiplicar brazos por tareas. Y es
COTA SUPERIOR en el sentido util: la regla EXISTE para cortar busquedas, asi que si funciona
la corrida cuesta menos que eso. Si costara mas, algo anda mal.

POR QUE SE CORREN TODOS LOS BRAZOS Y NO SOLO LOS QUE SE ESTANCAN. Los que no se estancan
salen gratis, y tenerlos da la comparacion pareada completa contra el registro sin factor —
que es sobre lo que se decide P20a y P20b.

UNA OBSERVACION ANOTADA ANTES DE CORRER, y que NO cambia ninguna prediccion. El
estancamiento se concentra en `dag_strategy` y `rewoo`; `react` casi no se estanca (2 filas
con `barren_peak >= 2`, ninguna con >= 3). `P20c` predijo que la regla morderia mas donde el
modelo controla el bucle, y `react` es el caso mas puro de eso. Queda dicho ahora para que
el veredicto no se lea despues en la direccion que hayan ido los datos.
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

CORPUS = "gold_p17"
UMBRAL = 3
REPEAT = 3
PARADIGMS = ["dag_strategy", "gist_reader", "map_reduce", "react", "rewoo"]

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
print(f"corpus: {CORPUS} | factor stop_on_barren={UMBRAL} | repeat={REPEAT}", flush=True)
print("cota superior estimada: ~3,4M tokens (73 de 336 filas pueden disparar)", flush=True)

runner = Runner(
    settings, CORPUS,
    retriever_arm="hybrid", surface_variant="basic",
    stop_on_barren=UMBRAL,
)
print(f"resultados: {runner._results_path.name}", flush=True)  # noqa: SLF001

started = time.perf_counter()
rows = runner.run_cross_product(paradigms=PARADIGMS, repeat=REPEAT)

gastado = sum(r.cost_tokens for r in rows)
rechazos = sum((r.tool_usage or {}).get("barren_refusals", 0) for r in rows)
print(f"\nfilas: {len(rows)}")
print(f"tokens: {gastado:,}")
print(f"busquedas rechazadas por la regla: {rechazos}")
print(f"wall: {(time.perf_counter() - started) / 60:.1f} min")
