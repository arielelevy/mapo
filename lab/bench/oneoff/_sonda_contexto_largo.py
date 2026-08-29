"""SONDA MANUAL (2026-08-29). Resultado en PENDIENTES.es.md, AR-6.

PRUEBA MANUAL: `direct` sobre C3 con `terra`, sin la poda de presupuesto.

QUE PREGUNTA CONTESTA. La factibilidad poda `direct` en las 9 celdas de C3 porque la tarea
declara un presupuesto de 40.000 tokens y el material son 483.481 — 12x por encima. Pero
`terra` tiene una ventana de 922.000: el material LE ENTRA. Asi que la pregunta es si la
poda esta escondiendo una capacidad, o si el regimen es duro aunque se vea todo de una.

Y HAY UNA SEGUNDA DIMENSION que solo existe aca. `direct` NO usa tools, y la restriccion de
`gpt-5.6` es «tools + razonamiento» — sin tools, `terra` puede razonar. Es el unico
paradigma del catalogo que puede correr con el razonamiento ENCENDIDO.

QUE NO ES. No es una medicion del banco: una celda, un modelo, sin replicas, fuera del
harness y sin escribir en ningun `.jsonl`. Es una sonda para saber si vale la pena
preguntar en serio.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

# Corre DESDE `lab/`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LAB = Path(".").resolve()
TAREA = "c3-002-h3"
MODELO = "gpt-5.6-terra"
V = "2025-04-01-preview"

docs = json.loads((LAB / "corpus/gold_h1/documents.json").read_text(encoding="utf-8"))
tareas = json.loads((LAB / "corpus/gold_h1/tasks.json").read_text(encoding="utf-8"))
t = next(x for x in tareas if x["task_id"] == TAREA)

# El mismo contrato de respuesta que usa el banco, para que la comparacion signifique algo.
CONTRATO = (
    "Answer with a single line of the form:\n"
    "ANSWER: <value>\n"
    "If several values are required, separate them with '; '. "
    "Do not explain. Do not add anything else."
)
cuerpo = "\n\n".join(f"[{u}]\n{docs[u]}" for u in t["unit_ids"])
prompt = f"Task: {t['question']}\n\n{CONTRATO}\n\n{cuerpo}"
material = len(cuerpo) // 4

print(f"tarea      : {TAREA}")
print(f"pregunta   : {t['question']}")
print(f"oraculo    : {t['oracle']}")
print(f"unidades   : {len(t['unit_ids'])}   material ~{material:,} tokens")
print(f"presupuesto declarado por la tarea: {t['budget_tokens']:,}  -> por eso se poda")
print(f"ventana de {MODELO}: 922.000  -> le entra\n")

base = os.environ["MAPO_NANO_ENDPOINT"].rstrip("/")
url = f"{base}/openai/deployments/{MODELO}/chat/completions?api-version={V}"
h = {"api-key": os.environ["MAPO_NANO_KEY"], "Content-Type": "application/json"}


def normalizar(s):
    return {x.strip().lower() for x in re.split(r"[;,]", s) if x.strip()}


def f1(pred, gold):
    p, g = normalizar(pred), {x.lower() for x in gold}
    if not p or not g:
        return 0.0
    inter = len(p & g)
    if not inter:
        return 0.0
    prec, rec = inter / len(p), inter / len(g)
    return 2 * prec * rec / (prec + rec)


for esfuerzo in ("medium", "high"):
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "seed": 7,
        "max_completion_tokens": 8000,
        "reasoning_effort": esfuerzo,
    }
    t0 = time.perf_counter()
    try:
        for intento in range(6):
            r = httpx.post(url, headers=h, json=payload, timeout=900)
            if r.status_code != 429:
                break
            espera = 45 * (intento + 1)
            print(f"    [429] la campana esta usando la cuota; espero {espera}s", flush=True)
            time.sleep(espera)
    except Exception as exc:
        print(f"  effort={esfuerzo:<7} ERROR de transporte: {type(exc).__name__}")
        continue
    seg = time.perf_counter() - t0
    if r.status_code != 200:
        print(f"  effort={esfuerzo:<7} {r.status_code}: "
              f"{r.json().get('error', {}).get('message', '')[:110]}")
        continue
    d = r.json()
    texto = (d["choices"][0]["message"]["content"] or "").strip()
    u = d.get("usage", {})
    det = u.get("completion_tokens_details", {})
    linea = next((l for l in texto.splitlines() if l.upper().startswith("ANSWER:")), "")
    resp = linea.split(":", 1)[1].strip() if ":" in linea else texto[:80]
    print(f"  effort={esfuerzo:<7} u={f1(resp, t['oracle']):.3f}  «{resp[:46]}»")
    print(f"                 entrada={u.get('prompt_tokens', 0):>8,}  "
          f"cacheada={u.get('prompt_tokens_details', {}).get('cached_tokens', 0):>8,}  "
          f"salida={u.get('completion_tokens', 0):>6,}  "
          f"razonamiento={det.get('reasoning_tokens', 0):>6,}  {seg:>5.0f}s")
    # Precio: >272k de entrada cobra la tarifa LARGA sobre la request entera.
    tar = json.loads((LAB / "config/tariffs.json").read_text(encoding="utf-8"))["tariffs"]
    largo = u.get("prompt_tokens", 0) > 272_000
    pin = tar["terra"]["long_context_prompt"] if largo else tar["terra"]["prompt"]
    pout = tar["terra"]["long_context_completion"] if largo else tar["terra"]["completion"]
    usd = u.get("prompt_tokens", 0) / 1e6 * pin + u.get("completion_tokens", 0) / 1e6 * pout
    print(f"                 tarifa {'LARGA' if largo else 'corta'} "
          f"({pin}/{pout} por millon)  ->  USD {usd:.2f}\n")
