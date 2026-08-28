"""P15: la afirmacion del PRODUCTO sobre un mundo que nunca vio (gold_transfer, seed 47).

Todas las corridas anteriores miden PARADIGMAS. Esta mide el MOTOR: theta se ajusta sobre
el registro existente, y el ruteo selectivo con abstencion se puntua contra el mejor fijo
--- incluido siempre-react --- sobre filas que theta no vio nunca.

Prediccion P15a-d registrada en README.md ANTES de esta corrida, y commiteada (2026-08-27),
que es lo que la vuelve falsable: la fecha no se puede retro-datar.

Estimacion previa al gasto: 9.0M tokens, 336 celdas. La aritmetica de factibilidad ya
podo map_reduce en 18 de 26 tareas sin gastar un token.

repeat=3 porque el piso de ruido se calcula POR CELDA y con dos replicas no hay piso, hay
dos numeros. workers=1 para no competir contra la cuota: el regulador del cliente aprende
el paso, pero cuatro hilos aprendiendo el mismo limite lo aprenden peor.

El runner reanuda por (task, paradigm, trial) y el cache es content-addressed, asi que
relanzarlo despues de una interrupcion no vuelve a pagar lo ya pagado.
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

# Los cinco informativos. direct/cot quedan afuera porque la factibilidad los poda gratis
# en este regimen, y sumarlos seria pagar por confirmar aritmetica ya hecha. Los tres
# candidatos verificados (graph_traverse, extract_compute, streaming_scan) quedan afuera
# de ESTA corrida: theta no tiene episodios suyos en el registro con el que se ajusta, y
# rutear hacia un paradigma sin evidencia es exactamente lo que la abstencion evita.
PARADIGMS = ["react", "dag_strategy", "map_reduce", "rewoo", "gist_reader"]

# gpt-5.4-nano, que es el modelo de medicion vigente desde 2026-08-26. El .env todavia
# apunta al primer modelo porque su grilla quedo CONGELADA: mezclar los dos en una misma
# afirmacion seria comparar dos experimentos. Los resultados van a results/nano/ por la
# misma razon.
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
print("corpus: gold_transfer (seed 47, nunca visto por theta)", flush=True)

runner = Runner(settings, "gold_transfer", retriever_arm="hybrid", surface_variant="basic")
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
