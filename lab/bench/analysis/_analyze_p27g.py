"""P27g: si theta aprendiera PARES `(modelo, paradigma)`, ¿aguanta el piso de evidencia?

LA PREGUNTA Y POR QUE SE PUEDE CONTESTAR GRATIS. `P27e` midio que la ventaja del modelo caro
vive en el PARADIGMA (+0,8755 en `react`, +0,0912 en `rewoo`). Si el efecto esta en la
interaccion, la politica correcta aprende pares — y eso **multiplica los bins**, que es
exactamente el mecanismo por el que `P15` fracaso: agregar un cuarto segmento al vocabulario
de region dejo a cada episodio en un bin demasiado chico para cruzar el piso de evidencia, y
theta perdio toda su confianza.

Cuantos bins hay y cuantos episodios caen en cada uno **no necesita ninguna corrida**: sale
de contar el registro. Y contar antes de construir es la unica forma de no repetir `P15`
descubriendolo despues de pagarlo.

QUE SE CUENTA. Para cada particion, cuantos bins superan `MIN_EPISODES_FOR_CONFIDENCE` — el
mismo piso que `Router._cost_key` y `theta_assertions` consultan. Un bin por debajo no es
«poco confiable»: es INVISIBLE, porque el router cae al prior y la particion no gobierna
nada. Un esquema donde la mayoria de los bins queda invisible no es un esquema con menos
precision — es uno que no se usa.

LO QUE NO CONTESTA. Si los pares serian MEJORES. Solo si serian USABLES. Un esquema
inutilizable no hace falta evaluarlo, y uno usable todavia hay que medirlo.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.policy import MIN_EPISODES_FOR_CONFIDENCE
from app.runner import load_rows
from bench._sanity import share

MODELOS = ("nano", "terra")


def episodios() -> list[dict]:
    out = []
    for m in MODELOS:
        for f in sorted(Path(f"results/{m}").glob("*.jsonl")):
            for r in load_rows(f):
                if not r.get("error"):
                    r["_modelo"] = m
                    out.append(r)
    return out


def contar(eps: list[dict], clave, nombre: str) -> None:
    bins = defaultdict(int)
    for r in eps:
        bins[clave(r)] += 1
    cruzan = [b for b, n in bins.items() if n >= MIN_EPISODES_FOR_CONFIDENCE]
    cubiertos = sum(n for b, n in bins.items() if n >= MIN_EPISODES_FOR_CONFIDENCE)
    print(f"  {nombre:<32} {len(bins):>4} bins · {len(cruzan):>4} cruzan el piso "
          f"({share(len(cruzan), len(bins), nombre):>5.0%}) · "
          f"{share(cubiertos, len(eps), nombre + '/eps'):>5.0%} de los episodios visibles")


def main() -> None:
    eps = episodios()
    if not eps:
        print("Sin episodios de los dos modelos — SIN N. Se dice, no se supone.")
        return
    modelos = sorted({r["_modelo"] for r in eps})
    if len(modelos) < 2:
        print(f"Solo hay episodios de {modelos}: la particion por modelo no se puede "
              f"contar sin el otro. SIN N.")
        return

    print(f"{len(eps)} episodios · modelos {modelos} · "
          f"piso de evidencia = {MIN_EPISODES_FOR_CONFIDENCE} episodios por bin\n")

    contar(eps, lambda r: (r["region"], r["paradigm"]), "region x paradigma (HOY)")
    contar(eps, lambda r: (r["region"], r["_modelo"], r["paradigm"]),
           "region x modelo x paradigma")
    contar(eps, lambda r: (r["_modelo"], r["paradigm"]), "modelo x paradigma (sin region)")
    contar(eps, lambda r: r["paradigm"], "paradigma solo")

    # EL CONTEO DE ARRIBA ENGAÑA SI LA GRILLA ESTA DESBALANCEADA, y lo esta: se reporta
    # la cobertura de regiones por modelo para que nadie lea «+6 bins» como si el modelo
    # casi no multiplicara. Multiplica; lo que pasa es que el caro corrio pocas regiones.
    por_modelo = defaultdict(set)
    for r in eps:
        por_modelo[r["_modelo"]].add(r["region"])
    total = len(set().union(*por_modelo.values()))
    print()
    print("  COBERTURA DE REGIONES, y sin esto el conteo de arriba miente:")
    for m in sorted(por_modelo):
        print(f"    {m:<8} {len(por_modelo[m]):>3} de {total} regiones")
    solapan = set.intersection(*por_modelo.values()) if len(por_modelo) > 1 else set()
    print(f"    en comun {len(solapan)}")
    if min(len(v) for v in por_modelo.values()) < total * 0.5:
        print("    => `region x modelo x paradigma` parece barato SOLO porque un modelo")
        print("       cubre pocas regiones. Con la grilla balanceada los bins se DUPLICAN,")
        print("       y ese ES el mecanismo de `P15`.")

    print()
    print("  La tercera linea es la que importa y no es obvia: si el efecto del modelo NO")
    print("  interactua con la region —y `P27e` midio que la region NO explica nada—,")
    print("  entonces el par se puede aprender SIN partir por region. Eso deja el numero")
    print("  de bins casi igual que hoy y esquiva el mecanismo de `P15` entero.")
    print()
    print("  Un bin por debajo del piso no es «menos confiable»: es INVISIBLE. El router")
    print("  cae al prior y la particion no gobierna nada — asi que un esquema donde la")
    print("  mayoria queda debajo no tiene menos precision, no se usa.")


if __name__ == "__main__":
    main()
