"""Borra las filas de `rewoo` que midieron el brazo ROTO. Cero llamadas al modelo.

POR QUÉ SE BORRAN Y NO SE ANOTAN. `rewoo` llamaba a `read` en 130 de 138 celdas y leía
**cero unidades**: la sustitución de evidencia le pasaba el JSON de la búsqueda donde iba un
`unit_id` (`RW-1`), y su prompt no declaraba `semantic_search` (`RW-2`). Esas filas no miden
el paradigma ReWOO — miden un ReWOO que contesta desde snippets y no puede abrir un
documento.

    Una fila que midió un brazo roto no es evidencia débil: es evidencia de otra cosa.
    Dejarla anotada la deja disponible para promediarse, y ninguna estadística lo denuncia.

Decisión del autor (2026-08-30): borrarlas.

QUÉ SE TOCA Y QUÉ NO. Se borra del **árbol vivo** —lo que los análisis leen hoy—. NO se toca
`results/archivo-2026-08-29-pre-K6/`, que está sellado como régimen anterior por otro motivo
(el analizador léxico cambió y su registro no es replayable): reescribir un snapshot fechado
lo volvería otra cosa que un snapshot.

CON BACKUP FECHADO, que es la convención de esta carpeta —`_regrade_2026_08_30.py` hace lo
mismo—. Borrar sin copia haría irreproducible incluso el diagnóstico de por qué se borró.

Corre DESDE `lab/`:  py bench/oneoff/_borrar_rewoo_roto.py [--escribir]
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

SELLADO = "archivo-2026-08-29-pre-K6"
STAMP = time.strftime("%Y%m%d-%H%M%S")


def main() -> None:
    escribir = "--escribir" in sys.argv
    total = 0
    tocados = 0

    print("=" * 92)
    print(f"BORRAR LAS FILAS DE `rewoo` DEL BRAZO ROTO "
          f"{'— ESCRIBIENDO' if escribir else '(ENSAYO)'}")
    print("=" * 92)
    print()

    for archivo in sorted(_Path("results").rglob("*_rows.jsonl")):
        if SELLADO in archivo.parts:
            continue
        lineas = [l for l in archivo.read_text(encoding="utf-8").splitlines()
                  if l.strip()]
        quedan = []
        n = 0
        for l in lineas:
            fila = json.loads(l)
            if fila.get("paradigm") == "rewoo":
                n += 1
            else:
                quedan.append(l)
        if not n:
            continue
        total += n
        tocados += 1
        print(f"  {n:4d} filas  {archivo}")
        if escribir:
            shutil.copy2(archivo, archivo.with_suffix(f".jsonl.bak-rewoo-{STAMP}"))
            archivo.write_text("\n".join(quedan) + "\n", encoding="utf-8")

    sellados = sum(
        1 for a in _Path("results").rglob("*_rows.jsonl") if SELLADO in a.parts
        for l in a.read_text(encoding="utf-8").splitlines()
        if l.strip() and json.loads(l).get("paradigm") == "rewoo"
    )
    print(f"\n  {total} filas en {tocados} archivos del arbol vivo")
    print(f"  {sellados} filas quedan en `{SELLADO}`, que NO se toca: es un snapshot "
          f"fechado\n  de otro regimen, y reescribirlo lo volveria otra cosa que un "
          f"snapshot")

    if not escribir:
        print("\n  Nada se escribio. Para aplicar:  "
              "py bench/oneoff/_borrar_rewoo_roto.py --escribir")


if __name__ == "__main__":
    main()
