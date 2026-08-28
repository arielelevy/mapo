"""P-2f: mas replicas SOLO donde el test pareado gana potencia.

EL TEST QUE ESTO ALIMENTA. Dentro de una misma celda (tarea, paradigma) —o sea con tarea
y paradigma fijos POR CONSTRUCCION— se pregunta si existe una transicion presente en todas
las replicas exitosas y ausente en todas las fallidas. Sobre 13 celdas dio 10 contra una
mediana nula de 7: p=0,055. Sugestivo, sin establecer.

POR QUE SOLO ESTAS 13 CELDAS. El test es pareado adentro de la celda, asi que una replica
nueva suma potencia UNICAMENTE donde el resultado y la secuencia ya varian. En una celda
que siempre sale igual, la replica numero 10 no aporta nada y cuesta lo mismo. Son 13
celdas y no 130.

POR QUE UN CORPUS GEMELO. Las 13 viven en gold_p17, cuyo veredicto esta CONGELADO.
Agregarle replicas cambiaria lo que un re-analisis computa sobre un resultado
prerregistrado — la falla que este proyecto ya demostro y documento. `gold_p17b` es una
copia byte-identica, asi que sus filas caen en otro archivo y el registro de P17 queda
intacto. Y como el seed por trial es `settings.seed + trial`, los trials 0-2 producen
payloads IDENTICOS: son hits de cache y no cuestan un token.

Costo real: 13 celdas x 6 trials nuevos = 78 filas.
"""

import os
import sys
import time
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner

TARGETS = {
    "dag_strategy": ["c3-000-h1", "c3-001-h2", "c5-001-w4"],
    "react": ["c2-000-w16", "c2-001-w16", "c4-001-w16", "c4-001-w4",
              "c5-000-w4", "c5-001-w4", "c7-000-pos"],
    "rewoo": ["c2-000-w16", "c2-000-w48", "c4-001-w4"],
}
REPEAT = 9  # 3 ya existentes (hits de cache) + 6 nuevos

base = Settings.from_env()
nano = base.results_dir / "nano"
settings = replace(
    base,
    endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
    api_key=os.environ["MAPO_NANO_KEY"],
    chat_deployment="gpt-5.4-nano",
    temperature=0.0,
    results_dir=nano,
)
print(f"modelo: {settings.fingerprint()}", flush=True)
print(f"corpus: gold_p17b (gemelo byte-identico de p17)", flush=True)

started = time.perf_counter()
total = tokens = 0
for paradigm, tasks in TARGETS.items():
    runner = Runner(settings, "gold_p17b", retriever_arm="hybrid", surface_variant="basic")
    rows = runner.run_cross_product(
        paradigms=[paradigm], task_ids=tasks, repeat=REPEAT, workers=1
    )
    total += len(rows)
    tokens += sum(r.cost_tokens for r in rows)
    print(f"  {paradigm}: {len(rows)} filas", flush=True)

print(f"\n{total} filas | {tokens:,} tokens | "
      f"{(time.perf_counter() - started) / 60:.1f} min", flush=True)
