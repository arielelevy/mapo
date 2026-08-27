"""Smoke del segundo modelo (gpt-5-nano en foundryopencode, temperature=0 EXPLICITA).

Verifica antes de comprometer una grilla: (1) el deployment acepta temperature=0 + seed
(su primo gpt-5-chat la rechaza — esto decide todo); (2) el tool calling funciona
(react); (3) el F1 califica igual; (4) cuantos tokens de razonamiento interno agrega a
la contabilidad. Resultados en results/nano/ para no mezclar modelos en un archivo de
resume; el fingerprint (deployment|t=0.0|seed) viaja en cada fila.

Nota: el endpoint reemplazado tambien alcanza al cliente de embeddings, pero los
vectores de gold_v2 ya estan cacheados por hash de contenido — si aparece una llamada
de embedding real, fallara visible y se cablea un endpoint separado.
"""
import os
import sys
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from app.config import Settings
from app.runner import Runner

base = Settings.from_env()
nano_results = base.results_dir / "nano"
nano_results.mkdir(parents=True, exist_ok=True)
s = replace(
    base,
    endpoint=os.environ["PAPERLAB_NANO_ENDPOINT"].rstrip("/"),
    api_key=os.environ["PAPERLAB_NANO_KEY"],
    chat_deployment="gpt-5.4-nano",
    temperature=0.0,
    results_dir=nano_results,
)
print(f"modelo: {s.fingerprint()}", flush=True)
r = Runner(s, "gold_v2", retriever_arm="hybrid", surface_variant="basic")
rows = r.run_cross_product(
    paradigms=["direct", "react"], task_ids=["c3-000-h1", "c4-000-w48"],
    repeat=2, workers=1,
)
err = sum(1 for x in rows if getattr(x, "infra_error", False))
tok = sum(x.cost_tokens for x in rows)
for x in rows:
    print(f"  {x.paradigm:8s} {x.task_id:12s} t{x.trial} u={x.utility:.2f} tok={x.cost_tokens:,}"
          + ("  INFRA_ERROR: " + x.error[:80] if getattr(x, "infra_error", False) else ""),
          flush=True)
print(f"\n{len(rows)} filas, {err} infra_error, {tok:,} tokens\nFIN", flush=True)
