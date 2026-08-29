"""Se ejecuto el camino del factor, o solo no dio error?

DE DONDE SALE (2026-08-29). La corrida light aprendio a comparar cada factor contra la
base y a gritar INERTE cuando un factor da exactamente la base. La guarda funciono y
enseguida mostro su limite: `managed` daba la base en las 52 filas, y eso se puede leer de
dos formas que la corrida NO puede separar.

  (a) el factor no llega al modelo            -> bloquea la campana
  (b) el factor llega y decide no hacer nada  -> no bloquea

Las dos producen filas identicas a la base. La diferencia no esta en el resultado: esta en
si el CODIGO se ejecuto. Y eso no se ve en un `.jsonl`.

QUE HACE ESTO. Envuelve `manage_history` y cuenta dos cosas por paradigma: cuantas veces se
la LLAMO y cuantos mensajes DEMOTO. Los dos numeros juntos dicen cual de las dos formas es:

  0 llamadas                     -> (a) el camino no se recorre. Es un defecto.
  N llamadas y 0 demociones      -> (b) el camino se recorre y la condicion no se cumple.

VEREDICTO MEDIDO EL 2026-08-29, sobre `gold_h1` w4, los 13 del plantel activo:

  61 llamadas, 0 demociones. Es (b).

  El motivo, verificado inspeccionando la forma de la historia: `manage_history` solo
  demota resultados de tool que traigan TEXTO COMPLETO (`text` + `unit_id`). En `w4` hay 4
  unidades, y el modelo busca una vez y lee una vez: lo unico que queda en la historia
  ANTES del ultimo batch es el `search`, cuyas entradas traen `summary` y no `text` — y
  esos se saltean a proposito, porque un resumen ya es chico y demotarlo romperia el mapa.
  La lectura cae siempre en el ultimo batch, que por definicion no se demota.

  No es un bug. Es que `w4` no tiene historia que compactar, y `managed` es exactamente el
  factor que compacta historia. Su cableado se verifica en la primera celda `w16`.

QUE NO PRUEBA. Que `managed` funcione. Prueba que su ausencia de efecto en `w4` esta
explicada, que es lo que hace falta para no bloquear la campana con un falso positivo.
"""

# Corre DESDE `lab/`.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import os
import sys
from dataclasses import replace
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import app.cognitive as cog
import app.paradigms as par
from app.config import Settings
from app.paradigms import REGISTRY, campaign_roster
from app.runner import Runner

CORPUS = "gold_h1"
# EL PLANTEL SALE DEL CATALOGO, no de una lista literal. Estaba clavado a mano aca y en
# otros tres scripts, y los cuatro quedaron viejos el mismo dia en que se retiro
# `map_reduce`. Las excepciones —quien corre estando retirado o en standby, y por que—
# viven en `CAMPAIGN_INCLUDE`, en un solo lugar.


def main() -> None:
    conteo: dict[str, list[int]] = {}
    actual = {"paradigma": "?"}
    original = cog.manage_history

    def espia(messages):
        demotados = original(messages)
        fila = conteo.setdefault(actual["paradigma"], [0, 0])
        fila[0] += 1
        fila[1] += demotados
        return demotados

    # LAS DOS REFERENCIAS, y por que hacen falta las dos. `paradigms/__init__.py` hace
    # `from ..cognitive import manage_history`, asi que tiene su PROPIA referencia al
    # objeto: parchear solo el modulo de origen deja al llamador usando la de antes, y el
    # espia contaria cero llamadas — el sintoma exacto que este auditor existe para
    # distinguir de un defecto real.
    cog.manage_history = espia
    par.manage_history = espia

    base = Settings.from_env()
    settings = replace(
        base,
        endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
        api_key=os.environ["MAPO_NANO_KEY"],
        chat_deployment="gpt-5.4-nano",
        temperature=0.0,
        # Directorio propio: esto NO es una medicion y no puede mezclarse con una.
        results_dir=base.results_dir / "_diagnose_managed",
    )
    runner = Runner(settings, CORPUS, retriever_arm="hybrid", surface_variant="managed")
    tareas = [t["task_id"] for t in runner._tasks  # noqa: SLF001
              if t["task_id"].endswith("w4")][:4]
    roster = campaign_roster()

    for paradigma in roster:
        actual["paradigma"] = paradigma
        runner.run_cross_product(
            paradigms=[paradigma], task_ids=tareas, repeat=1,
            baseline_reason="diagnostico: se ejecuta el camino de `managed`?",
        )

    llamadas = sum(c for c, _ in conteo.values())
    demociones = sum(d for _, d in conteo.values())
    print("\n" + "=" * 74)
    print(f"llamadas a manage_history : {llamadas}")
    print(f"mensajes demotados        : {demociones}")
    print("\npor paradigma (llamadas, demociones):")
    for paradigma, (c, d) in sorted(conteo.items()):
        print(f"  {paradigma:<16} {c:>4}  {d:>4}")

    print()
    if not llamadas:
        print("(a) EL CAMINO NO SE RECORRE. `manage_history` no se llamo ni una vez: el "
              "factor no llega. Es un defecto y bloquea la campana.")
    elif not demociones:
        print("(b) EL CAMINO SE RECORRE Y LA CONDICION NO SE CUMPLE. El factor llega y "
              "correctamente no hace nada en este regimen. No bloquea, y tampoco queda "
              "verificado: hace falta un regimen con historia que compactar.")
    else:
        print(f"EL FACTOR ACTUA: {demociones} mensajes demotados. Si aun asi las filas "
              f"salen identicas a la base, el problema esta aguas abajo de la compactacion.")


if __name__ == "__main__":
    main()
