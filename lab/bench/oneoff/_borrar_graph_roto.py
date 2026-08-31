"""Borra las filas de `graph_traverse` que midieron un ÍNDICE VACÍO. Cero llamadas.

POR QUÉ SE BORRAN. Medido sobre sus 165 filas, el histograma de llamadas tiene exactamente
dos valores:

    NO llama a ninguna herramienta    89 filas (54%)   u = 0,112
    lee al menos una unidad           76 filas         u = 0,525

Cuando ningún término de la pregunta matchea una entidad del grafo, la caminata no arranca:
`frontier` vacía, `scores` vacío, cero lecturas — **y el brazo contestaba igual**, desde la
nada, después de haber pagado una llamada de extracción por unidad.

    Más de la mitad de sus corridas no midieron el paradigma: midieron un índice
    inutilizable. Y su veredicto `P10a` se calculó sobre esa población.

**No se separan las 89 de las 76.** Las dos poblaciones salieron del mismo brazo bajo el
mismo nombre, y ninguna guarda de mezcla las distingue; y las 76 «buenas» tampoco son
comparables con lo que el brazo hace ahora, porque el arreglo cambia cuándo corre. Se borra
entero y se re-corre, que es lo mismo que se hizo con `rewoo` (`RW-1`, 292 filas).

QUÉ CAMBIÓ EN EL BRAZO (`GT-1`): si la caminata no alcanza ninguna unidad, levanta
`Infeasible` con el motivo. Tres efectos, los tres correctos: **no se puntúa** —una celda que
no corrió no es una respuesta mala—, **no gasta la llamada de solve** sobre evidencia que no
existe, y **el motivo queda en el registro**.

QUÉ NO SE TOCA: `results/archivo-2026-08-29-pre-K6/`, que es un snapshot fechado de otro
régimen.

Corre DESDE `lab/`:  py bench/oneoff/_borrar_graph_roto.py [--escribir]
"""

from __future__ import annotations

import json
import shutil
import sys as _sys
import time
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BRAZO = "graph_traverse"
SELLADO = "archivo-2026-08-29-pre-K6"
STAMP = time.strftime("%Y%m%d-%H%M%S")


def main() -> None:
    escribir = "--escribir" in sys.argv
    total = tocados = 0

    print("=" * 92)
    print(f"BORRAR LAS FILAS DE `{BRAZO}` "
          f"{'— ESCRIBIENDO' if escribir else '(ENSAYO)'}")
    print("=" * 92 + "\n")

    for archivo in sorted(_Path("results").rglob("*_rows.jsonl")):
        if SELLADO in archivo.parts:
            continue
        lineas = [l for l in archivo.read_text(encoding="utf-8").splitlines()
                  if l.strip()]
        quedan, n = [], 0
        for l in lineas:
            try:
                fila = json.loads(l)
            except json.JSONDecodeError:
                # La ultima linea puede estar a medio escribir si la corrida se corto.
                continue
            if fila.get("paradigm") == BRAZO:
                n += 1
            else:
                quedan.append(json.dumps(fila, ensure_ascii=False))
        if not n:
            continue
        total += n
        tocados += 1
        print(f"  {n:4d} filas  {archivo}")
        if escribir:
            shutil.copy2(archivo, archivo.with_suffix(f".jsonl.bak-{BRAZO}-{STAMP}"))
            archivo.write_text("\n".join(quedan) + "\n", encoding="utf-8")

    print(f"\n  {total} filas en {tocados} archivos del arbol vivo")
    if not escribir:
        print("\n  Nada se escribio. Para aplicar:  "
              f"py bench/oneoff/_borrar_graph_roto.py --escribir")


if __name__ == "__main__":
    main()
