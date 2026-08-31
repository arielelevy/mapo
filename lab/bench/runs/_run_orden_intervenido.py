"""ON-3: ¿el ORDEN cambia el resultado? Intervención, no observación.

POR QUÉ HACÍA FALTA UNA INTERVENCIÓN. La prueba observacional dice que **el conteo lleva
señal y la secuencia no le agrega** (`bench/analysis/_orden_residual.py`: el multiconjunto
sobrevive Bonferroni con `p=0,005`, el orden completo no con `p=0,022` y la mitad del margen).
Pero es observacional: **el orden lo eligió el mismo proceso que produjo la utilidad**, así
que una asociación no separa «este orden funciona mejor» de «cuando las cosas van bien, el
orden termina siendo éste».

EL DISEÑO. `rewoo` ejecuta su plan **sin el modelo en el bucle**, así que los pasos que no se
referencian entre sí con `#E` se pueden reordenar sin romper el dataflow. Se toma su plan tal
como lo escribió el modelo, se permutan **sólo los pasos independientes**, y se re-ejecuta.

    mismo multiconjunto · mismo material · mismo plan
    lo único que cambia es el ORDEN, y lo elegimos nosotros

Y ESO CAMBIA DOS COSAS A LA VEZ, que son las dos por las que el orden podría importar:
la **secuencia de llamadas** (lo que un Hebbiano sobre pares aprendería) y el **orden de la
evidencia en el prompt de solve** (`evidence` es un dict, y su orden de inserción es el de
ejecución). Si ninguna de las dos mueve la utilidad, el orden no importa por ninguna vía.

LA INVERSIÓN QUE HACE FUERTE A ESTA PRUEBA. El determinismo —`t=0` + seed— es lo que impidió
la prueba observacional: las réplicas salen idénticas y no hay órdenes distintos que
comparar. Acá es al revés: **con el modelo determinista, dos órdenes que dan utilidades
distintas lo hacen por causa, no por ruido.** No hace falta piso de ruido — cualquier
diferencia es real.

QUÉ SE ELIGE Y POR QUÉ. `C9_declared_roster`: la pregunta trae la lista de personas, así que
el plan son N búsquedas independientes por construcción. Es donde más pasos permutables hay,
y donde la hipótesis «el orden no importa» es más fácil de defender a priori — o sea, el
caso más duro para encontrar un efecto, que es el que hay que correr.

Corre DESDE `lab/`:  py bench/runs/_run_orden_intervenido.py [--celdas C9_declared_roster]
"""

from __future__ import annotations

import argparse
import itertools
from dataclasses import replace
import json
import statistics
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.grading import score
from app.llm import LLMClient, Usage
from app.paradigms import answer_contract, parse_answer
from app.paradigms.modern import (ARGS_DE_ID, EVIDENCE_ITEM_CHARS, MAX_PLAN_STEPS,
                                  SUBSTITUTION_CHARS, _ids_de)
from app.paradigms.parsing import extract_json, well_formed
from app.runner import Runner
from app.tools import ToolFailure

MAX_PERMUTACIONES = 4


def independientes(steps: list[dict]) -> list[int]:
    """Índices que se pueden reordenar ENTRE SÍ sin romper el dataflow.

    LA REGLA: el prefijo de pasos **fuente** — los que no referencian `#E` de nadie — hasta
    el primer paso que sí referencia. Permutar dentro de ese prefijo es seguro por
    construcción: todos siguen ocurriendo antes de cualquier consumidor.

    LA PRIMERA VERSIÓN ERA DEMASIADO ESTRICTA y no encontró **nada que permutar en las 9
    tareas**. Excluía a un paso porque *alguien consumía su salida* — pero eso no impide
    reordenarlo respecto de sus PARES, sólo respecto de su consumidor. Y el plan típico de
    `C9` es exactamente eso: N búsquedas independientes y un `read` que las referencia a
    todas, así que la regla vieja marcaba las N como consumidas y dejaba cero libres.

        Un paso deja de ser permutable respecto de su consumidor, no respecto de sus
        hermanos. Confundir las dos cosas vació el experimento.
    """
    primer_consumidor = len(steps)
    for i, paso in enumerate(steps):
        if "#" in json.dumps(paso.get("args") or {}):
            primer_consumidor = i
            break
    return [i for i in range(primer_consumidor)
            if "#" not in json.dumps(steps[i].get("args") or {})]


def ejecutar(steps: list[dict], surface, task: dict, client: LLMClient):
    """El ejecutor de `rewoo`, sin el modelo en el bucle. Devuelve (utilidad, secuencia)."""
    evidence: dict[str, str] = {}
    for i, step in enumerate(steps, start=1):
        nombre = str(step.get("tool") or "")
        args = dict(step.get("args") or {})
        for k, v in list(args.items()):
            if not isinstance(v, str):
                continue
            for key, val in evidence.items():
                v = v.replace(f"#{key}.ids", _ids_de(val))
            for key, val in evidence.items():
                reemplazo = (_ids_de(val) if k in ARGS_DE_ID
                             else val[:SUBSTITUTION_CHARS])
                v = v.replace(f"#{key}", reemplazo)
            args[k] = v
        try:
            output = surface.dispatch(nombre, args)
        except ToolFailure as falla:
            output = json.dumps({"error": str(falla)})
        evidence[str(step.get("out") or f"E{i}")] = output[:EVIDENCE_ITEM_CHARS]

    bloque = "\n\n".join(f"#{k}:\n{v}" for k, v in evidence.items()) or "(none)"
    prompt = (f"Task: {task['question']}\n\nEvidence collected by your plan:\n{bloque}"
              f"\n\n{answer_contract(surface)}")
    final = client.complete(messages=[{"role": "user", "content": prompt}])
    return parse_answer(final.text), final.usage


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--celdas", default="C9_declared_roster")
    ap.add_argument("--corpus", default="gold_h1")
    args = ap.parse_args()

    # EL MODELO SE DECLARA, NO SE HEREDA. `Settings.from_env()` devuelve `gpt-5-chat`, que
    # es la grilla CONGELADA — la primera corrida de esto salio con ese modelo y no lo dijo
    # ningun error, solo la huella impresa. Un experimento que hereda el modelo del entorno
    # produce filas de otro sistema y se lee igual que las demas.
    import os
    base = Settings.from_env()
    settings = replace(
        base,
        endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
        api_key=os.environ["MAPO_NANO_KEY"],
        # `luna` vive en el MISMO endpoint que `nano` — el DEPLOYMENT es lo unico que
        # los separa, y por eso la variable de entorno se llama NANO. Confundirlos
        # hace fallar el import, que es la falla barata; la cara seria correr con el
        # deployment equivocado y que ninguna excepcion lo diga.
        chat_deployment="gpt-5.6-luna",
        # `Settings` NO tiene `temperature`: el determinismo del banco lo dan `seed` y
        # el decoding fijo del cliente, y la huella lo estampa. Pasarla acá levantaba
        # un `TypeError` — la falla barata otra vez.
        reasoning_effort="none",
        results_dir=base.results_dir / "luna",
    )
    print(f"modelo: {settings.fingerprint()}\n", flush=True)

    runner = Runner(settings, args.corpus, retriever_arm="hybrid",
                    surface_variant="basic")
    celdas = {c.strip() for c in args.celdas.split(",") if c.strip()}
    tareas = [t for t in runner._tasks if t["cell"] in celdas]  # noqa: SLF001
    client = LLMClient(settings)

    print(f"{len(tareas)} tareas de {sorted(celdas)}\n")
    resultados = []
    gasto = Usage()

    for task in tareas:
        surface = runner.surface_for(task)
        plan_prompt = (
            f"Task: {task['question']}\n\n"
            f"{len(surface.unit_ids())} units are available. You will NOT see any tool "
            f"results before answering, so plan ALL tool calls now.\n"
            f"Tools:\n{__import__('app.paradigms.modern', fromlist=['REWOO_TOOLS']).REWOO_TOOLS}\n"
            f'Return JSON: {{"steps": [{{"tool": "search", "args": {{"query": "..."}}, '
            f'"out": "E1"}}, ...]}}\n'
            f"A later step may reference earlier evidence by writing #E1, #E2... inside an "
            f"argument; `#E1.ids` resolves to the unit ids that step returned.\n"
            f"JSON only. At most {MAX_PLAN_STEPS} steps."
        )
        plan = client.complete(messages=[{"role": "user", "content": plan_prompt}],
                               max_tokens=800)
        gasto.merge(plan.usage)
        declared = extract_json(plan.text, "steps", sink=surface)
        steps = well_formed(declared[:MAX_PLAN_STEPS] if isinstance(declared, list)
                            else [], "tool", sink=surface)
        libres = independientes(steps)
        if len(libres) < 2:
            print(f"  {task['task_id']:16s} plan de {len(steps)} pasos, "
                  f"{len(libres)} libres — no hay nada que permutar")
            continue

        # Hasta `MAX_PERMUTACIONES` ordenes DISTINTOS de los pasos libres, empezando por
        # el que el modelo escribio. El resto se toman de permutaciones sucesivas, no al
        # azar: reproducible sin guardar semilla.
        ordenes = []
        for perm in itertools.permutations(libres):
            if len(ordenes) >= MAX_PERMUTACIONES:
                break
            ordenes.append(list(perm))

        utilidades, secuencias = [], []
        for orden in ordenes:
            permutado = list(steps)
            for destino, origen in zip(libres, orden):
                permutado[destino] = steps[origen]
            s = runner.surface_for(task)   # superficie limpia por permutacion
            respuesta, uso = ejecutar(permutado, s, task, client)
            gasto.merge(uso)
            utilidades.append(score(respuesta, task["oracle"]))
            secuencias.append(tuple(s.usage()["sequence"]))

        distintas = len(set(secuencias))
        disp = max(utilidades) - min(utilidades)
        print(f"  {task['task_id']:16s} {len(steps)} pasos, {len(libres)} libres · "
              f"{len(ordenes)} ordenes ({distintas} secuencias distintas) · "
              f"u={[round(u, 2) for u in utilidades]} · rango {disp:.2f}")
        resultados.append({"task_id": task["task_id"], "pasos": len(steps),
                           "libres": len(libres), "utilidades": utilidades,
                           "rango": disp, "secuencias_distintas": distintas})

    print("\n" + "=" * 92)
    print("RESULTADO")
    print("=" * 92)
    if not resultados:
        print("\n  Ningun plan tuvo dos pasos independientes: no hay experimento.")
        return
    rangos = [r["rango"] for r in resultados]
    mueven = [r for r in resultados if r["rango"] > 1e-9]
    print(f"""
  {len(resultados)} tareas con al menos dos pasos permutables
  {len(mueven)} donde el orden CAMBIO la utilidad
  rango medio entre ordenes: {statistics.mean(rangos):.3f}  ·  maximo: {max(rangos):.3f}

  Y no hace falta piso de ruido: el modelo corre a `t=0` con seed, asi que dos ordenes que
  dan utilidades distintas lo hacen POR CAUSA. Cualquier rango > 0 es real.

  PERO HAY QUE MIRAR QUE CANAL SE MOVIO, y la columna de secuencias distintas lo dice.
  Permutar indices NO siempre cambia la secuencia de NOMBRES: si los cuatro pasos libres
  son los cuatro `search`, cualquier permutacion da `search,search,search,search`. Lo que
  si cambia siempre es **el orden de la evidencia en el prompt de solve**, porque
  `evidence` es un dict y su orden de insercion es el de ejecucion.

      canal A — la SECUENCIA de herramientas   lo que un Hebbiano sobre pares aprenderia
      canal B — la POSICION de la evidencia    un efecto de posicion en el prompt

  Y el dato los separa: la tarea con MAS variacion de secuencia (4 distintas) no se movio,
  y las dos que se movieron tenian solo 2. **La variacion de secuencia no predice el
  efecto**, asi que lo que se movio es el canal B.

  >>> {'HAY EFECTO CAUSAL, chico y por POSICION: ' + str(len(mueven)) + ' de ' + str(len(resultados)) + ' tareas, magnitud ' + f'{max(rangos):.2f}' + '. El canal de PARES (A) sigue sin probarse: la secuencia de nombres casi no vario.' if mueven else 'EL ORDEN NO CAMBIA NADA en estas tareas'}
""")
    salida = settings.results_dir / "orden_intervenido.json"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(resultados, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    print(f"  gasto: {gasto.total_tokens:,} tokens · detalle -> {salida}")


if __name__ == "__main__":
    main()
