"""P18: la celda de vigencia. Solo las 6 tareas nuevas.

POR QUE NO ES UNA GRILLA ENTERA. `gold_p18` se genero con el MISMO seed 73 que
`gold_p17`, y C8 reusa la enmienda que C5 ya planta, asi que los 72 documentos y las 26
tareas anteriores son BYTE-IDENTICOS — verificado. Correr la grilla completa seria pagar
de nuevo 300 filas que ya estan en el registro.

Se corren las 6 tareas C8 sobre los 5 paradigmas con repeat=3: 90 filas. Y P18c —que
compara C8 contra C5 en el mismo (idx, width)— lee las filas de C5 que P17 ya pago.

Estimado: ~2,9M tokens, contra los 12,69M que costo P17 completa.

Predicciones registradas ANTES, en README.md: P18a (los que leen todo resuelven la
supersesion), P18b (el valor superado es el error mas frecuente), P18c (C8 no se predice
desde C5).
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

PARADIGMS = ["react", "dag_strategy", "map_reduce", "rewoo", "gist_reader"]
C8_TASKS = [f"c8-{i:03d}-w{w}" for i in range(2) for w in (4, 16, 48)]

base = Settings.from_env()
nano = base.results_dir / "nano"
nano.mkdir(parents=True, exist_ok=True)
settings = replace(
    base,
    endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
    api_key=os.environ["MAPO_NANO_KEY"],
    chat_deployment="gpt-5.4-nano",
    temperature=0.0,
    results_dir=nano,
)
print(f"modelo: {settings.fingerprint()}", flush=True)
print(f"corpus: gold_p18 (seed 73, documentos identicos a p17)", flush=True)
print(f"tareas: {len(C8_TASKS)} de C8 x {len(PARADIGMS)} paradigmas x 3", flush=True)

runner = Runner(settings, "gold_p18", retriever_arm="hybrid", surface_variant="basic")
started = time.perf_counter()
rows = runner.run_cross_product(
    paradigms=PARADIGMS, task_ids=C8_TASKS, repeat=3, workers=1
)
tokens = sum(r.cost_tokens for r in rows)
print(
    f"\n{len(rows)} filas | {sum(1 for r in rows if getattr(r, 'infeasible', False))} "
    f"infactibles | {sum(1 for r in rows if getattr(r, 'infra_error', False))} excluidas "
    f"| {tokens:,} tokens | {(time.perf_counter() - started) / 60:.1f} min",
    flush=True,
)
