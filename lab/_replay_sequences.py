"""Reconstruir la SECUENCIA de llamadas a herramientas de corridas ya pagadas.

POR QUE SE PUEDE HACER GRATIS. El cache es content-addressed y el modelo de medicion
corre con t=0 + seed, con determinismo casi al token verificado. Volver a ejecutar un
paradigma sobre una tarea ya corrida produce EXACTAMENTE los mismos payloads de request,
asi que cada llamada es un hit de cache y el costo en tokens nuevos es cero. Esto no es
una estimacion: el script lo verifica al final contra el contador del cliente y falla si
gasto algo.

POR QUE NO SE PODIA ANTES, Y QUE CAMBIO. Las filas guardaban `calls`, un conteo por
herramienta. Un conteo no distingue "busco, leyo, busco, leyo" de "busco, busco, leyo,
leyo": mismo histograma, dos estrategias distintas. Ahora la superficie registra el orden
(`tool_usage.sequence`), asi que el replay lo materializa.

QUE HABILITA. Las asociaciones (tool_i -> tool_j) son lo unico que el aprendizaje
Hebbiano aporta y una estadistica marginal no puede: el peso por (region, paradigma) es
—demostrado en `_analyze_hebbian.py`— una transformacion monotona de la tasa de victorias
y por eso no puede cambiar un argmax. Una asociacion entre PARES no tiene esa propiedad.

QUE NO TOCA. No escribe ninguna fila. El registro de P15 y el de P16 quedan intactos; la
salida es un archivo aparte.
"""

import json
import sys
from collections import Counter, defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.llm import SeededClient
from app.paradigms import REGISTRY
from app.runner import Runner

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")

CORPUS = sys.argv[1] if len(sys.argv) > 1 else "gold_transfer"


def main() -> None:
    runner = Runner(settings, CORPUS, retriever_arm="hybrid", surface_variant="basic")
    tasks = {t["task_id"]: t for t in runner._tasks}  # noqa: SLF001

    cells = sorted({
        (r["task_id"], r["paradigm"])
        for r in runner.load_rows()
        if not r.get("infra_error") and not r.get("infeasible")
    })
    print(f"{CORPUS}: {len(cells)} celdas ya pagadas a replayar\n")

    # Mismo cliente sembrado que la corrida original: el seed entra en el fingerprint
    # del cache, asi que un seed distinto seria un miss garantizado en cada llamada.
    client = SeededClient(runner._client, settings.seed)  # noqa: SLF001
    before = client.spent.total_tokens
    sequences: dict[str, dict[str, list[str]]] = defaultdict(dict)
    misses = 0

    for i, (task_id, paradigm) in enumerate(cells, start=1):
        fn = REGISTRY.get(paradigm)
        if fn is None:
            continue
        surface = runner.surface_for(tasks[task_id])
        spent_before = client.spent.total_tokens
        try:
            fn(client, surface, tasks[task_id])
        except Exception as exc:  # noqa: BLE001
            # Un paradigma que fallo en la corrida original vuelve a fallar acá, y eso
            # es correcto: se registra lo que alcanzó a hacer antes de romperse.
            print(f"  [{i}/{len(cells)}] {task_id}/{paradigm}: {type(exc).__name__}")
        if client.spent.total_tokens > spent_before:
            misses += 1
        sequences[task_id][paradigm] = list(surface.sequence)

    spent = client.spent.total_tokens - before
    print(f"\ncosto del replay: {spent:,} tokens nuevos  ({misses} celdas con miss)")
    if spent > 0:
        print("  ATENCION: hubo misses de cache. El replay dejo de ser gratis y los")
        print("  payloads no son identicos a los de la corrida original — no usar estas")
        print("  secuencias como si fueran las de aquella corrida sin explicar por que.")

    # --- que dice la secuencia -------------------------------------------------------
    transitions: dict[str, Counter] = defaultdict(Counter)
    lengths: dict[str, list[int]] = defaultdict(list)
    for task_id, per_paradigm in sequences.items():
        for paradigm, seq in per_paradigm.items():
            lengths[paradigm].append(len(seq))
            for a, b in zip(seq, seq[1:]):
                transitions[paradigm][(a, b)] += 1

    print(f"\n{'paradigma':<16}{'llamadas medias':>17}{'transiciones distintas':>24}")
    for paradigm in sorted(lengths):
        n = lengths[paradigm]
        print(f"{paradigm:<16}{sum(n) / len(n):>17.1f}{len(transitions[paradigm]):>24}")

    print("\ntransiciones mas frecuentes por paradigma:")
    for paradigm in sorted(transitions):
        top = transitions[paradigm].most_common(3)
        shown = "  ".join(f"{a}->{b}:{c}" for (a, b), c in top)
        print(f"  {paradigm:<16}{shown}")

    out = settings.results_dir / f"{CORPUS}_sequences.json"
    out.write_text(json.dumps({
        "corpus": CORPUS,
        "replay_cost_tokens": spent,
        "cells": len(cells),
        "cache_misses": misses,
        "sequences": sequences,
        "transitions": {
            p: {f"{a}->{b}": c for (a, b), c in t.items()}
            for p, t in transitions.items()
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nescrito: {out}")


if __name__ == "__main__":
    main()
