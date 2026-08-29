"""Un cambio propuesto, ¿es un FACTOR o toca el grafo de control?

DE DONDE SALE (2026-08-29). Escribí en `PENDIENTES` que aprender el reparto de `handoff`
«convierte una estadistica en control de flujo», y lo escribí **como intuicion**. El autor
pidio estresarlo, y estresarlo lo refuto.

POR QUE UN BARRIDO NO ALCANZA. `PATRON_O_FACTOR.es.md` da cuatro preguntas y son correctas,
pero se contestan LEYENDO, y leyendo es como entra una opinion disfrazada de criterio. Esto
las hace dato: cambia la pieza propuesta, corre las mismas celdas, y mira si se movieron las
COTAS del patron o solamente la respuesta.

  cotas iguales + respuestas distintas  -> FACTOR: cambia la VISTA, no el grafo
  alguna cota se movio                  -> es estructura, y entonces es otro PATRON
  todo identico                         -> el regimen no lo distingue; no dice nada

LA COTA, NO EL CONTEO. Un patron declara sus cotas —`SCOPES` alcances,
`MAX_TURNS_PER_AGENT` vueltas— y lo que lo define es que no se muevan. El conteo EXACTO de
llamadas varia con que la transferencia dispare o no, y eso es la realizacion, no el grafo.
Confundir los dos declararia patron nuevo a cualquier cosa que cambie una respuesta.

VEREDICTO MEDIDO SOBRE EL REPARTO DE `handoff` (2026-08-29, `gold_h1` w4, 3 repartos):

  8 de 8 celdas respetan la misma cota de control
  6 de 8 dan la misma respuesta — o sea que el reparto SI mueve el resultado
  y en `c8-000-w4` el reparto contiguo saca u=1,000 donde el actual saca u=0,000

  El reparto es un FACTOR, y encima uno que compra algo. La objecion era mia.

Corre DESDE `lab/`. Gasta cuota la primera vez; despues pega en el cache.
"""

import importlib
import os
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner

# `app.paradigms.__init__` hace `from .handoff import handoff`, asi que el atributo
# `app.paradigms.handoff` es la FUNCION y no el modulo. Hay que pedir el modulo.
H = importlib.import_module("app.paradigms.handoff")

CORPUS = "gold_h1"
ORIGINAL = H._scopes


def contiguo(unit_ids, n):
    """Bloques contiguos — el que el docstring de `_scopes` descarta por medir localidad."""
    if not unit_ids:
        return []
    corte = (len(unit_ids) + n - 1) // n
    return [sorted(unit_ids[i * corte:(i + 1) * corte]) for i in range(n)]


def invertido(unit_ids, n):
    """El actual sobre las unidades al reves: mismo tamano de alcance, otra asignacion."""
    return ORIGINAL(list(reversed(unit_ids)), n)


VARIANTES = {"indice": ORIGINAL, "contiguo": contiguo, "invertido": invertido}


def main() -> None:
    base = Settings.from_env()
    resultados: dict[str, dict] = {}
    for nombre, fn in VARIANTES.items():
        H._scopes = fn
        ajustes = replace(
            base,
            endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
            api_key=os.environ["MAPO_NANO_KEY"],
            chat_deployment="gpt-5.4-nano",
            temperature=0.0,
            # Directorio propio por variante: esto NO es una medicion del catalogo y no
            # puede mezclarse con una.
            results_dir=base.results_dir / f"_factor_{nombre}",
        )
        runner = Runner(ajustes, CORPUS, retriever_arm="hybrid", surface_variant="basic")
        tareas = [t["task_id"] for t in runner._tasks  # noqa: SLF001
                  if t["task_id"].endswith("w4")][:4]
        filas = runner.run_cross_product(
            paradigms=["handoff"], task_ids=tareas, repeat=1,
            baseline_reason="auditoria: el reparto es factor o patron?",
        )
        resultados[nombre] = {f.task_id: f for f in filas}
    H._scopes = ORIGINAL

    # La cota que el patron DECLARA. Si se mueve, es estructura.
    cota = H.SCOPES * H.MAX_TURNS_PER_AGENT + H.SCOPES

    print("\n" + "=" * 74)
    print(f"LAS CUATRO PREGUNTAS, HECHAS DATO   (cota declarada: {cota} vueltas)\n")
    print(f"{'tarea':<14}{'reparto':<11}{'vueltas':>9}{'utilidad':>10}{'tokens':>11}")
    tareas = sorted(next(iter(resultados.values())))
    for tarea in tareas:
        for nombre in VARIANTES:
            fila = resultados[nombre].get(tarea)
            if fila is None:
                continue
            print(f"{tarea:<14}{nombre:<11}{fila.iterations:>9}"
                  f"{fila.utility:>10.3f}{fila.cost_tokens:>11,}")
        print()

    dentro = distintas = comparadas = 0
    for tarea in tareas:
        ref = resultados["indice"].get(tarea)
        if ref is None:
            continue
        for nombre in ("contiguo", "invertido"):
            otro = resultados[nombre].get(tarea)
            if otro is None:
                continue
            comparadas += 1
            if otro.iterations <= cota and ref.iterations <= cota:
                dentro += 1
            if otro.answer != ref.answer:
                distintas += 1

    print("=" * 74)
    print(f"  celdas comparadas                  : {comparadas}")
    print(f"  respetan la MISMA cota de control  : {dentro}/{comparadas}")
    print(f"  cambian la respuesta               : {distintas}/{comparadas}")
    print()
    if dentro < comparadas:
        print("  ALGUNA COTA SE MOVIO -> es ESTRUCTURA, no vista. Lo propuesto seria otro")
        print("  PATRON y entra al catalogo con prediccion registrada, no como factor.")
    elif not distintas:
        print("  NADA CAMBIO -> este regimen no lo distingue. No falsa nada: dice que aca")
        print("  no se puede medir. `w4` tiene 4 unidades y 2 alcances, asi que hay pocas")
        print("  particiones distinguibles. Repetir en `w16`.")
    else:
        print("  ES UN FACTOR. Las cotas se sostienen y la respuesta se mueve: lo que")
        print("  cambia es QUE VE cada agente —la VISTA— y no quien decide ni cuantas")
        print("  veces. Se mide cruzado contra el catalogo, no como brazo nuevo.")


if __name__ == "__main__":
    main()
