"""Un brazo que llama a una herramienta y no obtiene su efecto tiene un defecto. Cero costo.

DE DONDE SALE (2026-08-30). `rewoo` llama a `read` en **130 de 138 celdas** y lee **cero
unidades**. Es el unico brazo del plantel con unidades alucinadas —36, contra 0 de todos
los demas— y estuvo asi en el registro desde siempre. Ninguna guarda lo veia: los tests
prueban el codigo, `_audit_inerte` mira guardas que ningun corpus dispara, `_audit_specs`
mira lo que los modulos declaran. **Ninguna mira si una llamada tuvo su efecto.**

LA FORMA GENERAL: llamar no es lograr. Entre la llamada y el efecto hay plomeria —parseo de
argumentos, resolucion de ids, sustitucion de variables— y cuando esa plomeria falla el
brazo **corre, no revienta, y mide su ausencia**. Es la misma familia que «un factor que no
llega al modelo no existe», del lado de la herramienta.

QUE CHEQUEA, y las tres son derivables del registro:

  1. un brazo que llama a `read` y nunca aumenta `units_read`
  2. un brazo que busca y nunca ve una unidad nueva (todas sus busquedas esteriles)
  3. un brazo con unidades alucinadas cuando los demas tienen cero — un id que no existe
     es casi siempre un argumento mal construido, no una invencion del modelo

QUE **NO** HACE. No dice que el brazo este mal disenado. Dice que hay una desconexion entre
lo que pide y lo que obtiene, y eso se decide leyendo el codigo — pero hay que saber que
mirar, y para eso existe esto.

Corre DESDE `lab/`:  py bench/audits/_audit_plomeria.py
"""

from __future__ import annotations

import argparse
import collections
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.runner import load_rows

BUSQUEDAS = {"search", "keyword_search", "semantic_search"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--modelo", default="luna")
    ap.add_argument("--corpus", default="gold_h1")
    args = ap.parse_args()

    ruta = _Path("results") / args.modelo / f"{args.corpus}_rows.jsonl"
    filas = [f for f in load_rows(ruta) if not f.get("infeasible")]
    if not filas:
        raise SystemExit(f"{ruta} no tiene filas medidas.")
    tu = lambda x: (x.get("tool_usage") or {})

    agg = collections.defaultdict(lambda: collections.Counter())
    for f in filas:
        a = agg[f["paradigm"]]
        seq = tu(f).get("sequence") or []
        a["celdas"] += 1
        if "read" in seq or "read_all" in seq:
            a["llama_read"] += 1
        if (tu(f).get("units_read", 0) or 0) > 0:
            a["lee"] += 1
        busc = sum(1 for t in seq if t in BUSQUEDAS)
        a["busquedas"] += busc
        a["esteriles"] += tu(f).get("barren_total", 0) or 0
        a["alucinadas"] += tu(f).get("hallucinated_units", 0) or 0

    print(f"{ruta.name}: {len(filas)} filas medidas · {len(agg)} brazos\n")
    print(f"{'brazo':<17}{'llama read':>11}{'lee':>6}{'busca':>7}{'esteril':>9}"
          f"{'alucina':>9}")
    hallazgos: list[str] = []
    for b, a in sorted(agg.items()):
        print(f"{b:<17}{a['llama_read']:>11}{a['lee']:>6}{a['busquedas']:>7}"
              f"{a['esteriles']:>9}{a['alucinadas']:>9}")

        if a["llama_read"] >= 5 and a["lee"] == 0:
            hallazgos.append(
                f"{b}: llama a `read` en {a['llama_read']} celdas y **no lee ninguna "
                f"unidad**. Entre la llamada y el efecto hay plomeria rota — un argumento "
                f"mal construido, un id que no resuelve, una sustitucion textual donde "
                f"hacia falta un identificador."
            )
        if a["busquedas"] >= 20 and a["esteriles"] == a["busquedas"]:
            hallazgos.append(
                f"{b}: sus {a['busquedas']} busquedas son TODAS esteriles. O repite la "
                f"misma consulta, o el resultado no llega a quien decide la siguiente."
            )

    # LAS ALUCINADAS SE JUZGAN CONTRA EL RESTO, no contra un umbral. Un id inventado pasa
    # a veces; que UN brazo tenga todos y el resto cero no es el modelo, es el brazo.
    total = sum(a["alucinadas"] for a in agg.values())
    if total:
        solos = [b for b, a in agg.items() if a["alucinadas"] == total]
        if solos:
            hallazgos.append(
                f"{solos[0]}: concentra las {total} unidades alucinadas del registro y "
                f"todos los demas tienen CERO. Un id que no existe es casi siempre un "
                f"argumento mal armado, no una invencion del modelo."
            )

    print()
    if hallazgos:
        print("=" * 78)
        print(f"{len(hallazgos)} DESCONEXIONES ENTRE LLAMAR Y LOGRAR:\n")
        for h in hallazgos:
            print(f"  · {h}\n")
        print("Cada una se decide LEYENDO el codigo del brazo. Esto no dice que el patron")
        print("este mal disenado — dice donde mirar.")
        raise SystemExit(1)
    print("Todo brazo que llama a una herramienta obtiene su efecto.")


if __name__ == "__main__":
    main()
