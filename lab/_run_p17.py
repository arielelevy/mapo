"""P17: la primera corrida en la que la regla de seleccion PUEDE disparar.

P15 y P16 refutaron la afirmacion de ruteo en dos corpus held-out independientes, y las
dos midieron lo mismo sin querer: la CASCADA, no la seleccion. La regla de seleccion
quedo pre-empatada tres veces —el corpus declaraba detector en el 96% de las tareas,
sacar el detector le entrega la decision a la sonda y no a la seleccion, y el banco daba
un solo paso de los dos que `probe_then_decide` nombra— y las tres estan corregidas.

  corpus     gold_p17, seed 73 (usados: 7, 23, 47, 61). Verificado 26/26 por el
             verificador independiente del generador. El detector de runtime se declara
             POR CELDA segun si verificar es mas barato que resolver: 6 de 26 lo tienen,
             contra 25 de 26 en todo el registro anterior.
  theta      se ajusta sobre el registro previo completo con las regiones RE-DERIVADAS
             bajo la regla honesta y el vocabulario de cuatro segmentos. gold_p17 no
             entra jamas.
  medido     antes de gastar: la cascada cae de 22 a 2 de 26, quedan 14 tareas
             esperando la sonda, y theta tiene estadisticas suficientes en 10 de 26.
             P17b sigue siendo una apuesta real y no un tramite.
  veredicto  _analyze_p17.py, COMMITEADO ANTES DE ESTA CORRIDA, con el barrido de
             lambda adentro desde el nacimiento — porque P16c midio que el ruteo captura
             +0,1211 sin cobrar el costo y ya esta adentro del ruido en lambda=0,02.

Estimado: ~14M tokens, la misma forma que P16 (390 filas sobre 130 celdas). repeat=3 por
el piso de ruido por celda; workers=1 para no competir contra la cuota. El runner reanuda
por (task, paradigm, trial) y el cache no vuelve a pagar lo pagado.
"""

import os
import sys
import time
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner

PARADIGMS = ["react", "dag_strategy", "map_reduce", "rewoo", "gist_reader"]

base = Settings.from_env()
nano_results = base.results_dir / "nano"
nano_results.mkdir(parents=True, exist_ok=True)
settings = replace(
    base,
    endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
    api_key=os.environ["MAPO_NANO_KEY"],
    chat_deployment="gpt-5.4-nano",
    temperature=0.0,
    results_dir=nano_results,
)
print(f"modelo: {settings.fingerprint()}", flush=True)
print("corpus: gold_p17 (seed 73, nunca visto por theta)", flush=True)

runner = Runner(settings, "gold_p17", retriever_arm="hybrid", surface_variant="basic")
started = time.perf_counter()
rows = runner.run_cross_product(paradigms=PARADIGMS, repeat=3, workers=1)

infeasible = sum(1 for r in rows if getattr(r, "infeasible", False))
errors = sum(1 for r in rows if getattr(r, "infra_error", False))
tokens = sum(r.cost_tokens for r in rows)
print(
    f"\n{len(rows)} filas | {infeasible} infactibles (gratis) | {errors} excluidas "
    f"| {tokens:,} tokens | {(time.perf_counter() - started) / 60:.1f} min",
    flush=True,
)
print("FIN", flush=True)
