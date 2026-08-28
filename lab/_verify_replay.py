"""R-1: ¿el registro se puede replayar sellado, por el MISMO camino que lo produjo?

QUE AFIRMA EL PRODUCTO, Y POR QUE ESTO LO PONE A PRUEBA. La garantia tiene una sola
forma: «misma base de creencias => misma decision». Del lado del banco eso se apoya en
una propiedad operativa que hasta hoy estaba SUPUESTA: que una fila ya pagada se puede
volver a producir sin llamar al modelo. Si no se puede, ningun re-analisis es
reproducible y la palabra «determinismo» no tiene respaldo ejecutable.

EL INTENTO ANTERIOR NO CONCLUYO. `_replay_sequences.py` dio 93 de 112 misses sellados y
la causa quedo sin identificar. La sospecha registrada era que el defecto estaba en el
replay y no en el cache — pero una sospecha no es una medida, y mientras tanto R-1
figuraba como «intentado, no concluyente».

POR QUE ESTE TEST ES DISTINTO. No reconstruye el camino: usa el del runner. Misma clase,
mismos argumentos, `sealed=True`, y las mismas `(task, paradigm, trial)` que el registro
ya tiene. Si algo falla, falla en el codigo que produjo las filas, no en un espejo.

DONDE ESCRIBE. `results_dir` apunta a un directorio aparte, asi que el registro congelado
de P17 no se toca. El `cache_dir` NO cambia — es el que se esta poniendo a prueba.

LO QUE UN MISS SIGNIFICARIA, y hay que decirlo antes de correr para no interpretarlo
despues: que la clave de cache depende de algo que no esta en la fila. La clave es
`sha256(fingerprint, payload)`, y el `seed` aparece en LAS DOS mitades con valores
distintos —`settings.seed` en el fingerprint, `settings.seed + trial` en el payload—, asi
que un replay que reconstruya mal la semilla base falla entero aunque el cache este sano.
"""

import os
import shutil
import sys
import traceback
from dataclasses import replace
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.llm import SealedCacheMiss
from app.runner import Runner

CORPUS = "gold_p17"
# Pocas tareas y pocos brazos: el test es de MECANISMO, no de cobertura. Si una celda
# replaya, el mecanismo anda; si falla, falla igual con tres que con trescientas.
TASK_IDS = ["c1-000", "c2-000-w16", "c5-000-w4"]
PARADIGMS = ["react", "rewoo", "dag_strategy"]
REPEAT = 3


def main() -> None:
    base = Settings.from_env()
    # EL MODELO ES PARTE DE LA CLAVE, y `Settings.from_env()` devuelve el PRIMER modelo,
    # que quedo congelado. Reconstruir solo `results_dir` produce la huella
    # `gpt-5-chat|t=model_default` y falla el 100% de las entradas escritas por
    # `gpt-5.4-nano|t=0.0` — un miss que no dice nada sobre el cache.
    #
    # Esta es la causa del R-1 inconcluyente: no era el replay ni el cache, era la
    # reconstruccion de los ajustes. Se replica exactamente como `_run_p2f.py`.
    live = replace(
        base,
        endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
        api_key=os.environ["MAPO_NANO_KEY"],
        chat_deployment="gpt-5.4-nano",
        temperature=0.0,
        results_dir=base.results_dir / "nano",
    )
    print(f"modelo: {live.fingerprint()}")

    scratch = live.results_dir / "_replay_probe"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    sealed_settings = replace(live, results_dir=scratch)

    # Que celdas del registro vamos a exigir de vuelta.
    reference = Runner(live, CORPUS, retriever_arm="hybrid", surface_variant="basic")
    have = {
        (r["task_id"], r["paradigm"], r.get("trial", 0)): r
        for r in reference.load_rows(include_infra=True)
        if r["task_id"] in TASK_IDS and r["paradigm"] in PARADIGMS
    }
    wanted = [k for k in have if k[2] < REPEAT]
    print(f"corpus {CORPUS} | celdas del registro que se van a exigir: {len(wanted)}")
    if not wanted:
        print("El registro no tiene esas celdas. Nada que replayar.")
        return

    print("\n--- replay SELLADO por el camino del runner ---")
    try:
        runner = Runner(
            sealed_settings, CORPUS, sealed=True,
            retriever_arm="hybrid", surface_variant="basic",
        )
        rows = runner.run_cross_product(
            paradigms=PARADIGMS, task_ids=TASK_IDS, repeat=REPEAT, resume=False,
        )
    except SealedCacheMiss as exc:
        # Un miss sellado ES el resultado del test, no una falla del script: se reporta y
        # se sale con codigo distinto de cero para que nadie lo lea como "corrio bien".
        print(f"  MISS SELLADO: {exc}")
        raise SystemExit(
            "el registro NO es replayable por su propio camino."
        ) from exc

    print(f"  produjo {len(rows)} filas sin una sola llamada viva")

    # --- ¿son las MISMAS filas? --------------------------------------------------------
    #
    # Que no haya miss demuestra que el cache alcanzo. Que la fila COINCIDA demuestra que
    # el camino entero es determinista — que es la afirmacion, y no la misma cosa: un
    # paradigma podria consumir las mismas completions y componer otra respuesta.
    print("\n--- ¿coincide con lo que el registro ya tenia? ---")
    checked = mismatched = 0
    diffs: list[str] = []
    for row in rows:
        key = (row.task_id, row.paradigm, row.trial)
        old = have.get(key)
        if old is None:
            continue
        checked += 1
        for field in ("utility", "answer", "cost_tokens", "infeasible"):
            new_v = getattr(row, field, None)
            old_v = old.get(field)
            if new_v != old_v:
                mismatched += 1
                diffs.append(f"    {key} · {field}: registro={old_v!r} replay={new_v!r}")
                break

    print(f"  celdas comparadas: {checked}")
    print(f"  discrepancias    : {mismatched}")
    for d in diffs[:8]:
        print(d)

    if checked and not mismatched:
        print("\n  => R-1 CONCLUYE: el registro se replaya sellado y reproduce sus filas.")
    elif not checked:
        print("\n  => sin celdas comparables: no concluye.")
    else:
        print("\n  => el replay corre pero NO reproduce: el determinismo tiene un agujero.")


if __name__ == "__main__":
    main()
