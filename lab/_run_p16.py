"""P16: la replica limpia de P15, con lo que el mecanismo senalo.

P15 refuto la afirmacion del producto y dijo por que: el vocabulario de region no
representaba continuidad, y la valuacion puntuaba el primer peldano de una escalera que
el producto sube al fallar. Las dos cosas estan corregidas y medidas gratis sobre el
corpus anterior. Esta corrida las pone a prueba donde importa: un mundo nuevo.

  corpus     gold_p16, seed 61 (usados: 7, 23, 47). Verificado 26/26 por el
             verificador independiente del generador; el eje de continuidad lo
             separa igual que en los otros tres (C5 6/6, cero falsos positivos).
  theta      se ajusta sobre el registro previo COMPLETO (deep + holdout + v2 +
             transfer) con regiones de 4 segmentos. gold_p16 no entra jamas.
  veredicto  _analyze_p16.py, COMMITEADO ANTES DE ESTA CORRIDA. Congelar el codigo
             que juzga es mas fuerte que registrar la prediccion en prosa: no queda
             margen para elegir la valuacion despues de ver los numeros.

Estimado antes de gastar: 12,344,856 tokens sobre 336 celdas factibles (P15 real:
14,07M). repeat=3 por el piso de ruido por celda; workers=1 para no competir contra
la cuota. El runner reanuda por (task, paradigm, trial) y el cache no vuelve a pagar
lo pagado.
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
print("corpus: gold_p16 (seed 61, nunca visto por theta)", flush=True)

runner = Runner(settings, "gold_p16", retriever_arm="hybrid", surface_variant="basic")
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
