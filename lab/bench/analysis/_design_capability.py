"""Disenar la medicion de capacidad: que tareas discriminan, y cuanto cuesta.

LA PREGUNTA ES ORDINAL, y eso cambia el diseno. No se pregunta «cuanto mejor es sol» sino
«cual de los tres va arriba en `Capability`», que es un piso que el dial compara. Un orden
se decide con muchas menos celdas que una magnitud.

DONDE DISCRIMINA. Una tarea que nano ya resuelve no distingue nada: los tres sacan 1,0 y el
orden queda indefinido. Una que nadie resuelve tampoco. **Solo discriminan las que nano
falla y son resolubles**, y lo segundo no se sabe de antemano — pero se acota: una tarea
donde ALGUN paradigma saco >0 con nano es resoluble, y donde el mejor de todos saco 0 puede
ser imposible o puede ser dificil, y esa diferencia es lo que el modelo caro deberia mover.

ASI QUE SE ELIGEN DOS GRUPOS Y SE REPORTAN SEPARADOS:

  margen      nano saca 0 < u < 1 con su mejor paradigma. Hay algo que recuperar, y se
              sabe que la tarea es resoluble
  piso        nano saca 0 con TODOS. O es imposible, o necesita mas capacidad — y cual de
              las dos es lo unico que un modelo mas grande puede contestar

Reportarlos juntos promediaria dos preguntas distintas.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.runner import load_rows
from app.tariffs import NANO
from bench._sanity import share

CORPUS = "gold_p18"
SALIDA = 0.15


def main() -> None:
    f = Path(f"results/nano/{CORPUS}_rows.jsonl")
    if not f.exists():
        print(f"No hay registro de {CORPUS}. Se dice, no se supone.")
        return
    filas = [r for r in load_rows(f) if not r.get("error")]

    por_tarea: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    costo: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for r in filas:
        por_tarea[r["task_id"]][r["paradigm"]].append(r["utility"])
        costo[r["task_id"]][r["paradigm"]].append(r["cost_tokens"])

    margen, piso, resueltas = [], [], []
    for t, brazos in sorted(por_tarea.items()):
        mejor = max(statistics.mean(v) for v in brazos.values())
        if mejor >= 1.0:
            resueltas.append(t)
        elif mejor > 0.0:
            margen.append((t, mejor))
        else:
            piso.append(t)

    n = len(por_tarea)
    print(f"{CORPUS}: {n} tareas medidas con nano\n")
    print(f"  resueltas (u=1 con algun brazo) : {len(resueltas):>3}  "
          f"({share(len(resueltas), n, 'resueltas'):.0%})  NO discriminan")
    print(f"  margen    (0 < u < 1)           : {len(margen):>3}  "
          f"({share(len(margen), n, 'margen'):.0%})  hay que recuperar, y son resolubles")
    print(f"  piso      (u=0 con TODOS)       : {len(piso):>3}  "
          f"({share(len(piso), n, 'piso'):.0%})  imposible o necesita capacidad")

    # EL BRAZO MAS BARATO QUE LLEGA. Para ordenar modelos no hace falta el brazo que mas
    # rinde: hace falta el mas barato que deje margen visible, porque lo que se compara es
    # el MODELO y el paradigma es constante entre ellos.
    print("\n  costo por brazo sobre las tareas que discriminan:")
    candidatas = [t for t, _ in margen] + piso
    for brazo in sorted({p for t in candidatas for p in por_tarea[t]}):
        cs = [c for t in candidatas for c in costo[t].get(brazo, [])]
        us = [u for t in candidatas for u in por_tarea[t].get(brazo, [])]
        if not cs:
            continue
        print(f"    {brazo:<14} {statistics.mean(cs):>9,.0f} tok/celda  "
              f"u media {statistics.mean(us):.3f}")

    # LA CUENTA, contra el corpus y no contra el registro.
    print("\n  ESTIMADO del diseno propuesto:")
    for brazo in ("rewoo", "react"):
        cs = [c for t in candidatas for c in costo[t].get(brazo, [])]
        if not cs:
            continue
        por_celda = statistics.mean(cs)
        for modelos in (2, 3):
            celdas = len(candidatas) * 3 * modelos
            tot = celdas * por_celda
            plata = tot * ((1 - SALIDA) * NANO.prompt_per_mtok
                           + SALIDA * NANO.completion_per_mtok) / 1_000_000
            print(f"    {brazo:<8} x {len(candidatas)} tareas x 3 trials x {modelos} "
                  f"modelos = {celdas:>4} celdas · {tot:>10,.0f} tok "
                  f"· USD ~{plata:.2f} AL PRECIO DE NANO")
    print("\n  OJO: los modelos grandes cuestan ~25x por token (referencia), asi que la")
    print("  plata real de las celdas del caro es ~25x la linea de arriba para esa parte.")


if __name__ == "__main__":
    main()
