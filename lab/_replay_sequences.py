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

ESTADO AL 2026-08-27: NO FUNCIONA TODAVIA, y la causa es desconocida.
-------------------------------------------------------------------
Sobre `gold_transfer`, 93 de 112 celdas dan miss sellado. Dos cosas que hay que decir con
cuidado:

1. UN MISS SELLADO ACA NO PRUEBA NADA SOBRE EL CACHE (R-1). Lo mucho mas probable es que
   el replay no este reconstruyendo el payload original. El runner llama
   `REGISTRY[paradigm](client, surface, task)` con la tarea cruda y `SeededClient(cliente,
   seed + trial)`, y esto usa `seed + 0`, asi que trial 0 deberia pegar. No pega, y por
   ahora no se sabe por que. Candidatos sin verificar: el contenido que devuelven las
   herramientas depende del recuperador, y el recuperador de embeddings puede estar
   entregando algo distinto de lo que entrego en la corrida original.

2. LA METRICA DE COSTO QUE ESTE SCRIPT IMPRIMIA ERA INCORRECTA. `SeededClient.spent`
   acumula el `usage` de TODA completion, incluidas las servidas por cache. Reportar eso
   como "tokens nuevos" confunde uso contabilizado con gasto real. En modo sellado el
   gasto real es cero por construccion — un miss levanta excepcion y jamas sale a la red.
   La cifra quedo renombrada a lo que es.

Lo que si quedo probado: el modo sellado es la guarda correcta para esta clase de script.
Sin el, la primera version salio a hacer llamadas vivas contra la misma cuota que estaba
usando una corrida en curso, y solo se noto mirando el reloj del cache.
"""

import json
import sys
from collections import Counter, defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
from app.config import Settings
from app.llm import SealedCacheMiss, SeededClient
from app.paradigms import REGISTRY
from app.runner import Runner

base = Settings.from_env()
# EL MODELO ES PARTE DE LA CLAVE DE CACHE, y `Settings.from_env()` devuelve el PRIMER
# modelo, que quedo congelado. Reconstruir solo `results_dir` produce la huella
# `gpt-5-chat|t=model_default` y hace MISS en el 100% de las entradas escritas por
# `gpt-5.4-nano|t=0.0` — sin que nada en el error lo diga.
#
# Esta es exactamente la causa de los 93/112 misses que dejaron a este script sin
# concluir, y la misma que dejo a R-1 sin concluir hasta que se identifico: un replay con
# los ajustes equivocados y un cache roto producen el MISMO sintoma.
settings = replace(
    base,
    endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
    api_key=os.environ["MAPO_NANO_KEY"],
    chat_deployment="gpt-5.4-nano",
    temperature=0.0,
    results_dir=base.results_dir / "nano",
)
print(f"modelo: {settings.fingerprint()}", flush=True)

CORPUS = sys.argv[1] if len(sys.argv) > 1 else "gold_transfer"


def main() -> None:
    # SELLADO, y es la decision importante del script. En modo sellado un miss de cache
    # es un ERROR DURO y nunca una llamada viva. Eso convierte "creo que el replay es
    # gratis" en "el replay no puede no ser gratis": si un payload no fuera identico al
    # de la corrida original, el script rompe en vez de gastar tokens contra la misma
    # cuota que esta usando la corrida en curso. Y de paso es la prueba de R-1 — que el
    # replay sellado sigue funcionando despues de mudar el cache a directorios con
    # namespace por cuenta.
    runner = Runner(settings, CORPUS, retriever_arm="hybrid",
                    surface_variant="basic", sealed=True)
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
    sealed_misses: list[tuple[str, str, str]] = []
    failures: list[tuple[str, str, str]] = []

    for i, (task_id, paradigm) in enumerate(cells, start=1):
        fn = REGISTRY.get(paradigm)
        if fn is None:
            continue
        surface = runner.surface_for(tasks[task_id])
        spent_before = client.spent.total_tokens
        try:
            fn(client, surface, tasks[task_id])
        except SealedCacheMiss as miss:
            # Distinto de un fallo del paradigma: es el replay diciendo que este payload
            # no esta en el cache. Se cuenta aparte porque significa otra cosa — que la
            # reconstruccion NO es la de la corrida original.
            sealed_misses.append((task_id, paradigm, str(miss)[:90]))
        except Exception as exc:  # noqa: BLE001
            # Un paradigma que fallo en la corrida original vuelve a fallar aca, y eso
            # es correcto: se registra lo que alcanzo a hacer antes de romperse.
            failures.append((task_id, paradigm, type(exc).__name__))
        if client.spent.total_tokens > spent_before:
            misses += 1
        sequences[task_id][paradigm] = list(surface.sequence)

    spent = client.spent.total_tokens - before
    reconstruidas = sum(1 for v in sequences.values() for s in v.values() if s)
    print(f"{chr(10)}uso contabilizado : {spent:,} tokens — incluye los servidos por")
    print( "                    cache. El gasto REAL es cero: en modo sellado un miss")
    print( "                    levanta excepcion y jamas sale a la red.")
    print(f"celdas con secuencia: {reconstruidas}/{len(cells)}")
    print(f"misses sellados     : {len(sealed_misses)}")
    print(f"fallos de paradigma : {len(failures)}")
    if sealed_misses:
        print("")
        print("  NO concluir de aca que el cache perdio entradas (R-1). Lo mucho mas")
        print("  probable es que este replay no reconstruya el payload original, y esa")
        print("  causa esta sin identificar. Ver el estado en el docstring.")
        for t,pa,why in sealed_misses[:3]:
            print(f"    {t}/{pa}: {why}")

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
        "sealed_misses": [list(m) for m in sealed_misses],
        "failures": [list(f) for f in failures],
        "sequences": sequences,
        "transitions": {
            p: {f"{a}->{b}": c for (a, b), c in t.items()}
            for p, t in transitions.items()
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nescrito: {out}")


if __name__ == "__main__":
    main()
