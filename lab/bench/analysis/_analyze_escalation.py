"""Cuando conviene auto-escalar al modelo caro, y con que senal. Planteo del autor.

LA PREGUNTA. Tener nano por defecto y un modelo poderoso «solo cuando es necesario». Dos
formas, y no son la misma cosa:

  POR DISENO      se sabe de antemano, desde creencias sobre el request. Ya esta
                  implementado: el dial eleva a A3 lo irreversible y A3 exige capacidad
                  DEEP; la cota de plata poda el par que no entra. Es aritmetica + reglas
  AUTO-ESCALADO   se corre barato, se detecta que fallo, y se reintenta caro. Eso es la
                  CASCADA, y solo es sana donde existe un detector barato de falla

Y AHI ESTA EL PROBLEMA CON EL EJEMPLO DE `C3`. `HONEST_DETECTORS` dice que en C3 verificar
ES resolver: comprobar el extremo de una cadena significa recorrer la cadena. O sea que en
C3 el auto-escalado degenera en «escalar siempre» o «no enterarse nunca». Es el PEOR caso
para escalar por falla, no el mejor.

LA SALIDA QUE NO EXISTIA HASTA HOY. No hace falta un detector de GOLD. Hace falta una senal
COMPUTADA y barata correlacionada con falla, y los contratos son exactamente eso:

  `fill()` se niega        una ranura no llego al piso de procedencia
  `complete()` se niega    la enumeracion no cubre el dominio declarado
  `absence()` se niega     se afirmo una ausencia sin haber recorrido el dominio
  cobertura inimponible    ninguna topologia admisible recorre el alcance

Ninguna es la opinion del modelo sobre si le fue bien —eso seria `ELICITED` y ademas
gobernaria el flujo de control, que el invariante prohibe—. Son hechos computables sobre lo
que produjo. Un contrato que se niega es una falla DETECTADA SIN ORACULO.

QUE CALCULA ESTO. La economia, que es lo que decide: escalar cuesta `1 + p x R`, con `p` la
fraccion que escala y `R` el multiplicador de precio del caro. Con `R = 25`, escalar el 10%
duplica el gasto. Asi que la pregunta no es «sirve» sino «con que `p` sigue conviniendo», y
eso sale del registro.
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

from app.runner import load_rows
from app.tariffs import DEEP, NANO, breakeven
from bench._sanity import bounded, share


def main() -> None:
    raiz = Path("results/nano")
    if not raiz.exists():
        print("No hay registro nano. Nada que calcular — se dice, no se inventa.")
        return

    filas = []
    for f in sorted(raiz.glob("*.jsonl")):
        filas.extend(load_rows(f))
    filas = [r for r in filas if not r.get("error")]
    if not filas:
        print("Registro vacio — SIN N.")
        return

    R = breakeven(NANO, DEEP, 0.15)
    print(f"multiplicador de precio del caro: {R:.0f}x por token (referencia)\n")

    # LA TASA DE FALLA POR CELDA. `u < 1` es «no acerto del todo», que es lo que un
    # escalado querria atrapar.
    por_celda = defaultdict(list)
    for r in filas:
        por_celda[(r["task_id"], r["paradigm"])].append(r["utility"])
    medias = {k: sum(v) / len(v) for k, v in por_celda.items()}
    fallan = {k: u for k, u in medias.items() if u < 1.0}
    p = share(len(fallan), len(medias), "tasa de falla")
    bounded(p, 0.0, 1.0, "tasa de falla")

    print(f"celdas: {len(medias)} · con u<1: {len(fallan)} ({p:.1%})")
    print(f"gasto si se escala esa fraccion al caro: {1 + p * R:.1f}x el gasto de hoy")
    print(f"  (escalar el 100% seria {1 + R:.0f}x; escalar 0% es 1,0x)\n")

    # EL UMBRAL QUE DECIDE. Escalar paga si la utilidad recuperada compensa el costo
    # extra al lambda del despliegue. Se reporta el lambda de indiferencia, no un
    # veredicto: lambda es del lector.
    recuperable = sum(1.0 - u for u in fallan.values())
    if recuperable <= 0:
        print("No hay utilidad recuperable: nada que escalar.")
        return
    extra = p * R
    lam = recuperable / len(medias) / extra if extra else float("inf")
    print(f"utilidad recuperable si el caro acertara TODO lo que el barato erro: "
          f"{recuperable / len(medias):+.4f} por celda")
    print(f"lambda de indiferencia: {lam:.4f}")
    print(f"  por debajo de ese lambda, escalar paga; por encima, no.")
    print(f"  Y es una COTA OPTIMISTA: supone que el caro acierta el 100% de lo que el")
    print(f"  barato erro, que nadie midio. Con un acierto del 50%, el lambda se parte.\n")

    # DONDE SE PUEDE ESCALAR SIN ORACULO. Sin detector barato, «escalar al fallar»
    # degenera; con un contrato que se niega, la falla se detecta sin oraculo.
    con_detector = [r for r in filas if r.get("has_oracle")]
    sin_detector = [r for r in filas if not r.get("has_oracle")]
    print(f"filas con detector barato de falla : {len(con_detector)} "
          f"({share(len(con_detector), len(filas), 'detector'):.1%})")
    print(f"filas SIN detector                 : {len(sin_detector)}")
    print("  En las de la segunda linea, escalar por falla necesita una senal COMPUTADA")
    print("  que no sea el oraculo: un contrato que se NIEGA. Eso existe desde hoy")
    print("  (`C-NUM`, `C-COMPLETE`, `C-ABSENCE`, cobertura inimponible) y todavia no se")
    print("  midio cuanta falla atrapa — que es lo unico que falta para decidir.")


if __name__ == "__main__":
    main()
