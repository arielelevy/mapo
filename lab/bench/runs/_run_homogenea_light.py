"""La corrida homogénea LIGHT: la matriz entera, sobre lo más barato que existe.

PARA QUE SIRVE (idea del autor, 2026-08-29). La campaña completa son decenas de millones de
tokens y horas de reloj. Si un factor no llega al modelo, un paradigma explota en una celda
rara o un archivo se mezcla, eso se descubre A LAS HORAS y con los tokens ya gastados.

Esta corrida ejercita **cada patrón contra cada factor** sobre las tareas de `w4` —las de
menor material del corpus— con `repeat=1`. No mide nada: **prueba que la matriz corre**. Un
resultado de acá NO entra a ninguna estadística, y por eso escribe en su propio directorio.

QUE ATRAPA, y son cosas que ya pasaron todas hoy:
  - un paradigma con `NameError` en tiempo de ejecución (le pasó a `graph_traverse`)
  - un factor que no llega al modelo (le pasó a `offer_board`, `terse_tools` y
    `compact_material`, tres veces en un día)
  - una cota de factibilidad mal elegida que poda un brazo casi siempre (le pasó a
    `handoff`, 21 de 78, y a `supervisor`, 6 de 78)
  - un archivo de resultados que mezcla condiciones (`load_rows` levanta)

QUE NO ATRAPA, y hay que decirlo: nada que dependa del tamaño. Un paradigma que funciona en
`w4` y muere en `w48` pasa esta corrida. `w48` es 12× el material de `w4` —483k tokens
contra 40k— así que es exactamente donde vive el régimen que el banco mide. Esta corrida
compra confianza en el CABLEADO, no en el comportamiento.

POR QUE HAY UNA COMPARACION CONTRA LA BASE (2026-08-29). La versión anterior imprimía
«0 errores, la matriz corre entera» y eso era verdad y era insuficiente: un factor que NO
LLEGA al modelo tampoco da error — da exactamente la base. Pasó tres veces en un día
(`offer_board`, `terse_tools`, `compact_material`), y la cuarta apareció comparando dos
archivos a mano: `managed` daba la base fila por fila y el resumen decía que estaba bien.

Así que el criterio de «este factor corre» ya no es «no explotó», es **cuántas filas movió
respecto de la base**. Cero filas movidas es un factor INERTE y la corrida lo grita.

Y HAY UN SEGUNDO ESTADO QUE SE VE IGUAL Y NO ES LO MISMO. Un factor puede llegar al modelo
y decidir correctamente no hacer nada. Desde el archivo de resultados eso es indistinguible
de un factor desconectado: las dos cosas dan la base. La diferencia importa —una bloquea la
campaña y la otra no— y no se puede resolver mirando filas, hay que medir si el camino se
ejecutó. Por eso existe `INERCIA_EXPLICADA` más abajo: la excepción se declara con su
medición y su fecha, y no se concede por conveniencia de que la corrida pase.

El umbral de «ejercitado apenas» es 20% de las filas. No sale de ninguna teoría: es «una de
cada cinco», suficiente para que el camino se haya recorrido de verdad y bajo para no
rechazar un factor que legítimamente aplica a pocos paradigmas.

Y UNA TRAMPA QUE YA COSTO UNA CORRIDA. Dos procesos de esta corrida a la vez appendean al
MISMO `.jsonl` y el resumen sale con más filas que celdas —`terse` reportó 77 de 52—. El
lock impide el archivo corrupto, no el conteo doble. Se corre de a una.
"""

# Corre DESDE `lab/`.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import os
import sys
import time
import textwrap
from dataclasses import replace
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.paradigms import REGISTRY
from app.runner import Runner

CORPUS = "gold_h1"
# LA RECETA DEL CORPUS, escrita acá porque el 2026-08-29 no estaba escrita en ningún lado.
# `gold_h1` se había generado en un directorio temporal de sesión y sobrevivía por accidente:
# una corrida que no se puede regenerar desde una receta no es reproducible, y esta es la
# que la campaña entera va a usar. Ahora vive en `corpus/gold_h1` y se rehace con:
#
#   py corpus/generate.py --seed 101 --people 60 --per-cell 3 --widths 4,16,48 \
#      --unit-tokens 8000 --hard --honest-detectors --out corpus/gold_h1
#
# 78 tareas = 3 por celda x (5 celdas sin width + 7 celdas x 3 widths). Verificado con
# `py corpus/verify.py --corpus corpus/gold_h1`: 11 celdas en PASS, y el guarda de
# correferencia da 39/39 saltos de cadena exigiendo resolver una variante.
NO_SE_CORREN = ("cot", "plan_execute")
ROSTER = sorted(set(REGISTRY) - set(NO_SE_CORREN))
RAZON = "corrida light: ejercita la matriz sin gastar, antes de la homogenea"

# LOS FACTORES, uno por vez desde la base. El producto cruzado completo no es el punto: acá
# se prueba que CADA UNO tiene camino, no cómo interactúan.
FACTORES = [
    ("base", {}),
    ("hyde", {"retriever_arm": "hybrid_hyde"}),
    ("managed", {"surface_variant": "managed"}),
    ("board", {"offer_board": True}),
    ("read_all", {"offer_read_all": True}),
    ("terse", {"terse_tools": True}),
    ("prune", {"compact_material": True}),
]


# Fraccion de filas que un factor tiene que mover para que esta corrida cuente como que lo
# EJERCITO. Ver el docstring: no es un umbral estadistico, es «una de cada cinco».
MINIMO_MOVIDO = 0.20

# INERCIA EXPLICADA: los factores que dan exactamente la base en `w4` y se sabe POR QUE.
#
# La guarda de arriba no puede separar dos cosas que se ven igual desde el archivo de
# resultados: un factor que NO LLEGA al modelo, y uno que llega y correctamente decide no
# hacer nada. La primera bloquea la campana; la segunda no. La unica forma honesta de
# distinguirlas es medir si el CAMINO se ejecuto, y eso no se ve en las filas.
#
# Asi que la excepcion es explicita, fechada y con su evidencia. Un factor entra aca solo
# despues de que alguien haya medido por que esta inerte — no por conveniencia de que la
# corrida pase.
INERCIA_EXPLICADA = {
    "managed": (
        "2026-08-29, medido con `bench/audits/_diagnose_managed.py`: `manage_history` se "
        "llama 61 veces sobre `w4` y demota 0 mensajes. No es cableado — es el regimen. "
        "Solo demota resultados de tool que traigan TEXTO COMPLETO, y en `w4` (4 unidades) "
        "el modelo busca una vez y lee una vez: lo unico que queda en la historia previa "
        "es un `search`, cuyas entradas traen `summary` y no `text`, y esos se saltean a "
        "proposito («ya son chicos, no rompas el mapa»). La lectura cae SIEMPRE en el "
        "ultimo batch, que por definicion no se demota. Su cableado se verifica en la "
        "primera celda `w16` de la campana, no aca."
    ),
}


def _firma(fila: dict) -> tuple:
    """Lo que tiene que cambiar si el factor llego al modelo.

    La respuesta y el gasto, no el reloj: `wall_seconds` cambia entre dos corridas
    IDENTICAS —una pega en el cache y la otra no— asi que compararlo daria «movio todo»
    siempre. `cached_calls` tiene el mismo problema y por el mismo motivo.
    """
    return (fila.get("answer"), fila.get("cost_tokens"), fila.get("prompt_tokens"))


def _clave(fila: dict) -> tuple:
    return (fila.get("paradigm"), fila.get("task_id"), fila.get("trial"))


def _movidas(base: list[dict], filas: list[dict]) -> tuple[int, int]:
    """Cuantas celdas difieren de la base, y sobre cuantas se pudo comparar.

    Se cruza por clave, no por posicion: si un factor poda una celda por factibilidad,
    las listas quedan desalineadas y comparar indice contra indice reportaria
    diferencias que son corrimiento.
    """
    ref = {_clave(f): _firma(f) for f in base}
    comunes = [f for f in filas if _clave(f) in ref]
    return sum(1 for f in comunes if ref[_clave(f)] != _firma(f)), len(comunes)


def main() -> None:
    # La comparacion de inercia mide contra `base`, asi que `base` tiene que correr
    # PRIMERO. Si alguien reordena la lista, el resto se compara contra una lista vacia
    # y todo da «movio 0 filas» — un falso INERTE en cada factor, que es peor que no
    # tener la guarda porque parece un hallazgo.
    if FACTORES[0][0] != "base":
        raise SystemExit("`base` tiene que ser el primer factor: es la referencia.")
    base_settings = Settings.from_env()
    settings = replace(
        base_settings,
        endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
        api_key=os.environ["MAPO_NANO_KEY"],
        chat_deployment="gpt-5.4-nano",
        temperature=0.0,
        results_dir=base_settings.results_dir / "light",
        corpus_dir=Path(sys.argv[1]) if len(sys.argv) > 1 else base_settings.corpus_dir,
    )

    sonda = Runner(settings, CORPUS, retriever_arm="hybrid", surface_variant="basic")
    # SOLO `w4`: las de menor material. Con `w48` esto dejaría de ser light — 12x el
    # material por tarea, y el punto entero es que un error no cueste la corrida.
    tareas = [t["task_id"] for t in sonda._tasks if t["task_id"].endswith("w4")][:4]  # noqa: SLF001
    if not tareas:
        tareas = [t["task_id"] for t in sonda._tasks][:4]  # noqa: SLF001
    print(f"corpus {CORPUS} | {len(ROSTER)} patrones | {len(FACTORES)} factores")
    print(f"tareas (las mas baratas): {tareas}\n", flush=True)

    resumen = []
    base_filas: list = []
    for nombre, kw in FACTORES:
        arranque = time.perf_counter()
        runner = Runner(
            settings, CORPUS,
            retriever_arm=kw.pop("retriever_arm", "hybrid"),
            surface_variant=kw.pop("surface_variant", "basic"),
            **kw,
        )
        nuevas = runner.run_cross_product(
            paradigms=ROSTER, task_ids=tareas, repeat=1, baseline_reason=RAZON
        )
        # LO QUE DEVUELVE `run_cross_product` ES LO QUE CORRIO RECIEN, no el contenido del
        # archivo: con `resume=True` una celda ya presente se saltea y no vuelve en la
        # lista. La primera version de esta guarda comparaba ese retorno y en una corrida
        # reanudada daba «0 de 0 filas — INERTE» en TODOS los factores, que es un falso
        # positivo perfecto: el mensaje mas alarmante posible sobre la evidencia mas vacia
        # posible. La comparacion se hace contra el ARCHIVO, que es donde vive la corrida.
        filas = runner.load_rows()
        errores = [f for f in nuevas if f.error]
        infact = sum(1 for f in filas if f.get("infeasible"))
        gasto = sum(f.get("cost_tokens", 0) for f in filas)
        ingesta = sum(f.get("ingest_tokens", 0) for f in filas)
        # `base` es la referencia contra la que se mide todo lo demas, asi que se guarda
        # entera. Que sea el primer factor de la lista no es casual y no puede cambiarse
        # sin romper esto — de ahi la guarda al entrar a `main`.
        if nombre == "base":
            base_filas = list(filas)
        movidas, comparables = (
            (None, 0) if nombre == "base" else _movidas(base_filas, filas)
        )
        resumen.append({
            "factor": nombre, "filas": len(filas), "errores": len(errores),
            "infactibles": infact, "tokens": gasto, "ingest_tokens": ingesta,
            "movidas": movidas, "comparables": comparables,
            "minutos": round((time.perf_counter() - arranque) / 60, 1),
            "archivo": runner._results_path.name,  # noqa: SLF001
        })
        if movidas is None:
            mov = ""
        elif not comparables:
            mov = " · SIN COMPARAR (ninguna celda en comun con la base)"
        else:
            mov = (f" · movio {movidas}/{comparables} filas"
                   f"{'  <-- INERTE' if movidas == 0 else ''}")
        print(f"\n=== {nombre:<9} {len(filas):>3} filas · {len(errores)} errores · "
              f"{infact} infactibles · {gasto:,} tokens · "
              f"{resumen[-1]['minutos']} min{mov}", flush=True)
        for f in errores:
            print(f"    ERROR {f.paradigm:<15} {f.task_id:<14} {str(f.error)[:90]}")

    print("\n" + "=" * 78)
    total = sum(r["tokens"] for r in resumen)
    fallidos = [r for r in resumen if r["errores"]]
    # Un factor que no movio NINGUNA fila no llego al modelo. Es el mismo defecto que
    # `offer_board`, `terse_tools` y `compact_material` tuvieron el 2026-08-29, y ninguno
    # de los tres daba error.
    # `comparables` tiene que ser > 0: sin celdas en comun no hay nada que comparar, y
    # llamar INERTE a eso es la version del bug que esta guarda tuvo el primer dia.
    inertes = [r for r in resumen if r["movidas"] == 0 and r["comparables"]
               and r["factor"] not in INERCIA_EXPLICADA]
    explicados = [r for r in resumen if r["movidas"] == 0 and r["comparables"]
                  and r["factor"] in INERCIA_EXPLICADA]
    sin_comparar = [
        r for r in resumen if r["movidas"] is not None and not r["comparables"]
    ]
    # Y el estado intermedio: llego, pero esta corrida apenas lo toco. No bloquea, avisa.
    flojos = [
        r for r in resumen
        if r["movidas"] not in (None, 0)
        and r["comparables"] and r["movidas"] / r["comparables"] < MINIMO_MOVIDO
    ]
    print(f"TOTAL: {total:,} tokens en {sum(r['minutos'] for r in resumen):.1f} min")
    if fallidos:
        print(f"\nHAY ERRORES en {len(fallidos)} factores — NO lanzar la homogenea:")
        for r in fallidos:
            print(f"  {r['factor']}: {r['errores']} de {r['filas']} filas")
    if inertes:
        print(f"\nHAY FACTORES INERTES ({len(inertes)}) — NO lanzar la homogenea. Un factor "
              f"que da exactamente la base no llego al modelo, y medirlo costaria la "
              f"campana entera para reportar cero:")
        for r in inertes:
            print(f"  {r['factor']}: 0 de {r['comparables']} filas distintas de la base")
    if flojos:
        print(f"\nEjercitados apenas ({len(flojos)}) — la homogenea puede lanzarse, pero "
              f"ESTA corrida no los probo. Su cableado sigue sin verificar:")
        for r in flojos:
            print(f"  {r['factor']}: {r['movidas']} de {r['comparables']} filas "
                  f"({r['movidas'] / r['comparables']:.0%}) — `w4` es demasiado chico "
                  f"para este factor")
    if explicados:
        print(f"\nInertes CON EXPLICACION MEDIDA ({len(explicados)}) — no bloquean, y "
              f"tampoco quedan verificados:")
        for r in explicados:
            print(f"  {r['factor']}: 0 de {r['comparables']} filas")
            for linea in textwrap.wrap(INERCIA_EXPLICADA[r["factor"]], 74):
                print(f"      {linea}")
    if sin_comparar:
        print(f"\nSin base con que comparar ({len(sin_comparar)}) — la guarda de inercia "
              f"no dice nada sobre estos factores:")
        for r in sin_comparar:
            print(f"  {r['factor']}: 0 celdas en comun con la base")
    if not (fallidos or inertes):
        print("\nSin errores y todos los factores llegan al modelo. La matriz corre "
              "entera; lo que falta es tamano, no cableado.")
    salida = settings.results_dir / "light_summary.json"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"resumen -> {salida}")


if __name__ == "__main__":
    main()
