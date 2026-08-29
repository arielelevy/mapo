"""P27e: ¿hay ALGUN eje en el que la ventaja del modelo caro varie?

POR QUE IMPORTA MAS QUE EL PROMEDIO. `X-5b` y `X-5f` construyeron el ruteo por modelo sobre
una tesis: la ventaja del caro depende de la DIFICULTAD, y la region ya mide dificultad, asi
que theta podria aprender a llamarlo donde paga. `P27b` refuto la mitad de eso — la ganancia
es plana entre `piso` y `margen`, +0,5000 contra +0,4778.

Pero «plana en un eje» no es «plana en todos». Si hubiera OTRO eje donde varie —la celda, el
paradigma, la region— el ruteo sigue teniendo algo que aprender, y sobre ese eje. Si no lo
hay, entonces elegir modelo por request **no compra nada**: la decision es de presupuesto
—pagar siempre o nunca— y no de ruteo, y eso hay que decirlo aunque tire abajo trabajo.

QUE SE MIRA. La ganancia pareada `u(terra) - u(nano)` partida por cada eje que el registro
declara. Y se reporta la DISPERSION entre particiones, no solo las medias: dos particiones
con medias parecidas y varianzas enormes no son «planas», son ruidosas — y eso se decide
distinto.

LO QUE ESTE ANALISIS NO PUEDE HACER. Con 16 celdas pareadas, ningun eje tiene N para un
contraste serio. Se reporta como SCREENING: si ni siquiera aparece una diferencia bruta, no
hay nada que perseguir con mas N; si aparece, hace falta una corrida pensada para ese eje.
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

CORPUS = "gold_p18"
MIN_POR_GRUPO = 3


def celdas(carpeta: str) -> dict[tuple[str, str], dict]:
    f = Path(f"results/{carpeta}/{CORPUS}_rows.jsonl")
    if not f.exists():
        return {}
    por = defaultdict(list)
    for r in load_rows(f):
        if not r.get("error"):
            por[(r["task_id"], r["paradigm"])].append(r)
    return {
        k: {
            "u": sum(x["utility"] for x in v) / len(v),
            "region": v[0].get("region", ""),
            "cell": v[0].get("cell", ""),
            "n_units": v[0].get("n_units") or 0,
            "razonamiento": sum(x.get("reasoning_tokens", 0) for x in v) / len(v),
        }
        for k, v in por.items()
    }


def partir(comunes, base, otro, clave, nombre: str) -> None:
    grupos = defaultdict(list)
    for k in comunes:
        grupos[clave(k, base, otro)].append(otro[k]["u"] - base[k]["u"])
    utiles = {g: v for g, v in grupos.items() if len(v) >= MIN_POR_GRUPO}
    chicos = len(grupos) - len(utiles)
    if len(utiles) < 2:
        print(f"  {nombre:<22} menos de dos grupos con n>={MIN_POR_GRUPO} — SIN N")
        return
    medias = {g: statistics.mean(v) for g, v in utiles.items()}
    spread = max(medias.values()) - min(medias.values())
    print(f"  {nombre:<22} dispersion entre grupos: {spread:+.4f}"
          + (f"  ({chicos} grupo(s) con n<{MIN_POR_GRUPO}, fuera)" if chicos else ""))
    for g, m in sorted(medias.items(), key=lambda kv: -kv[1]):
        sd = statistics.pstdev(utiles[g]) if len(utiles[g]) > 1 else 0.0
        print(f"      {str(g)[:34]:<34} {m:+.4f}  (n={len(utiles[g])}, sd={sd:.3f})")


def main() -> None:
    base, otro = celdas("nano"), celdas("terra")
    if not base or not otro:
        print("Faltan filas de alguno de los dos — SIN N.")
        return
    comunes = sorted(set(base) & set(otro))
    if len(comunes) < 4:
        print(f"{len(comunes)} celdas pareadas — SIN N.")
        return

    du = [otro[k]["u"] - base[k]["u"] for k in comunes]
    print(f"{len(comunes)} celdas pareadas · ganancia media {statistics.mean(du):+.4f} "
          f"· sd {statistics.pstdev(du):.4f}\n")

    # EL PISO CONTRA EL QUE SE COMPARA CADA PARTICION. Si la dispersion entre grupos no
    # supera la variabilidad DENTRO de los grupos, la particion no explica nada — solo
    # esta cortando ruido en pedazos.
    print(f"  {'(referencia)':<22} sd dentro del conjunto: {statistics.pstdev(du):.4f}")
    print("  Una particion solo dice algo si su dispersion supera eso.\n")

    partir(comunes, base, otro, lambda k, b, o: k[1], "por PARADIGMA")
    partir(comunes, base, otro, lambda k, b, o: b[k]["cell"], "por CELDA")
    partir(comunes, base, otro, lambda k, b, o: b[k]["region"], "por REGION")
    partir(comunes, base, otro,
           lambda k, b, o: "bulk" if (b[k]["n_units"] or 0) > 8 else "chico",
           "por MATERIAL")
    partir(comunes, base, otro,
           lambda k, b, o: "razona mucho" if o[k]["razonamiento"] > 400 else "razona poco",
           "por RAZONAMIENTO")

    print("\n  Con 16 celdas ningun eje tiene N para un contraste serio. Esto es un")
    print("  SCREENING: si ni siquiera aparece una diferencia bruta, no hay nada que")
    print("  perseguir con mas N; si aparece, hace falta una corrida pensada para ese eje.")


if __name__ == "__main__":
    main()
