"""X-5e, con lo que ya esta pagado: ¿dos modelos re-abren la brecha que uno solo cierra?

LA PROPUESTA DEL AUTOR. Tener DOS modelos en el sistema —uno rapido y barato, uno caro— y
usar en cada caso el que convenga.

POR QUE PUEDE SER LO QUE VUELVA MEDIBLE LA TESIS. Dentro de UN modelo la brecha de oraculo
se va a cero apenas se cobra el costo: `rewoo` domina y no hay nada que un ruteador pueda
capturar. Eso no dice que el ruteo no sirva — dice que en este espacio de accion no hay
heterogeneidad. Agregar un eje de modelo la crea: hay tareas donde el barato alcanza y
tareas donde no.

Y NO HACE FALTA CORRER NADA. `gold_v2` y `gold_deep` estan corridos en los DOS modelos. La
comparacion se arma UNIENDO estudios por modelo — nunca juntando filas, que es lo que la
guarda de `load_rows` impide con razon: promediar entre modelos no mide un paradigma, mide
el modelo.

LA TRAMPA QUE HAY QUE EVITAR, Y ES LA QUE MANUFACTURA BRECHAS. Al agregar un eje, el
baseline TAMBIEN se fortalece. «Mejor fijo» pasa a ser el mejor PAR (modelo, paradigma)
fijo, porque eso es lo que elegiria un despliegue que no rutea. Compararse contra el mejor
paradigma de UN solo modelo seria darse una ventaja de la nada.

LO QUE ESTO NO ES. No es plata: los dos modelos tienen precios distintos y la tarifa no
esta declarada, asi que el eje de costo sigue siendo TOKENS y eso favorece sistematicamente
al modelo caro —que usa menos tokens por la misma tarea—. El resultado de abajo hay que
leerlo sabiendo eso: es una COTA OPTIMISTA para el modelo caro, no una cuenta.
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
from dataclasses import replace
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings

CORPORA = ["gold_v2", "gold_deep"]
MODELOS = {"caro (primer modelo)": "", "barato (nano)": "nano"}


def celdas(path: Path) -> dict[tuple[str, str], dict[str, float]]:
    """Promedio por (tarea, paradigma). Trials promediados ANTES del oraculo."""
    if not path.exists():
        return {}
    acc: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("infra_error") or r.get("infeasible"):
            continue
        acc[(r["task_id"], r["paradigm"])].append(r)
    return {
        k: {
            "utility": statistics.mean(x["utility"] for x in v),
            "cost": statistics.mean(x["cost_tokens"] for x in v),
        }
        for k, v in acc.items()
    }


def main() -> None:
    base = Settings.from_env()

    for corpus in CORPORA:
        por_modelo = {}
        for etiqueta, sub in MODELOS.items():
            root = base.results_dir / sub if sub else base.results_dir
            por_modelo[etiqueta] = celdas(root / f"{corpus}_rows.jsonl")

        if not all(por_modelo.values()):
            print(f"{corpus}: falta en algun modelo, se declara y se saltea")
            continue

        # Solo las celdas que EXISTEN en los dos: comparar sobre distinta cobertura
        # mediria que corpus corrio cada uno.
        comunes = set(por_modelo["caro (primer modelo)"]) & set(por_modelo["barato (nano)"])
        tareas = sorted({t for t, _ in comunes})
        print(f"\n=== {corpus} — {len(comunes)} celdas en AMBOS modelos, "
              f"{len(tareas)} tareas ===")

        for etiqueta, celdas_m in por_modelo.items():
            u = [celdas_m[k]["utility"] for k in comunes]
            c = [celdas_m[k]["cost"] for k in comunes]
            print(f"  {etiqueta:<24} utilidad media {statistics.mean(u):.3f}  "
                  f"tokens medios {statistics.mean(c):>10,.0f}")

        # --- el punto de equilibrio en PLATA -------------------------------------------
        #
        # El eje de costo son TOKENS y los dos modelos no valen lo mismo por token, asi
        # que la comparacion de arriba favorece al caro. Lo que SI se puede computar sin
        # tarifa es el punto de equilibrio: cuantas veces mas caro por token puede ser el
        # modelo caro y seguir saliendo igual de plata.
        tok_caro = statistics.mean(
            por_modelo["caro (primer modelo)"][k]["cost"] for k in comunes)
        tok_barato = statistics.mean(
            por_modelo["barato (nano)"][k]["cost"] for k in comunes)
        if tok_caro > 0:
            equilibrio = tok_barato / tok_caro
            print(f"\n  el caro usa {tok_caro / tok_barato:.2f}x los tokens del barato")
            print(f"  PUNTO DE EQUILIBRIO: el caro puede costar hasta **{equilibrio:.2f}x** "
                  f"por token")
            if equilibrio > 1.0:
                print(f"  => usa MENOS tokens, asi que tiene margen de precio. Con la "
                      f"tarifa puesta esto se vuelve una cuenta")
            else:
                print(f"  => usa MAS tokens, asi que ya pierde en tokens antes del precio")

        # --- el mejor fijo, sobre PARES ------------------------------------------------
        pares = defaultdict(list)
        for etiqueta, celdas_m in por_modelo.items():
            for (task, paradigm) in comunes:
                pares[(etiqueta, paradigm)].append(celdas_m[(task, paradigm)]["utility"])
        medias = {p: statistics.mean(v) for p, v in pares.items() if len(v) == len(tareas)}
        if not medias:
            medias = {p: statistics.mean(v) for p, v in pares.items()}
        mejor_par = max(medias, key=medias.get)
        print(f"\n  mejor PAR fijo: {mejor_par[0]} + {mejor_par[1]}  "
              f"utilidad {medias[mejor_par]:.3f}")

        # --- el oraculo, sobre pares ---------------------------------------------------
        oraculo_par, oraculo_un_modelo = [], []
        gana_barato = gana_caro = empata = 0
        for task in tareas:
            mejores = {}
            for etiqueta, celdas_m in por_modelo.items():
                vals = [celdas_m[(t, p)]["utility"] for (t, p) in comunes if t == task]
                if vals:
                    mejores[etiqueta] = max(vals)
            if len(mejores) < 2:
                continue
            oraculo_par.append(max(mejores.values()))
            oraculo_un_modelo.append(mejores["barato (nano)"])
            b, c = mejores["barato (nano)"], mejores["caro (primer modelo)"]
            if abs(b - c) < 1e-9:
                empata += 1
            elif b > c:
                gana_barato += 1
            else:
                gana_caro += 1

        if not oraculo_par:
            print("  sin tareas comparables")
            continue

        brecha_par = statistics.mean(oraculo_par) - medias[mejor_par]
        print(f"  oraculo sobre PARES: {statistics.mean(oraculo_par):.3f}")
        print(f"  BRECHA contra el mejor par fijo: {brecha_par:+.4f}")
        print(f"\n  por tarea, quien alcanza mas: barato {gana_barato} · "
              f"caro {gana_caro} · empatan {empata} (de {len(tareas)})")
        if empata == len(tareas):
            print("  => NINGUNA tarea distingue a los modelos: el eje no crea "
                  "heterogeneidad acá, y un ruteador de modelo no tendria que elegir")
        else:
            print(f"  => {gana_barato + gana_caro} tareas SI distinguen: hay algo que "
                  f"un ruteador de modelo podria capturar")


if __name__ == "__main__":
    main()
