"""Latencia: la dimension que se registro en cada fila y nadie leyo. Planteo del autor.

TERCERA VEZ EL MISMO PATRON. `wall_seconds` esta en `Row`, se estampa en las 2.369 filas
del registro, y **ningun analizador lo consume**. Igual que `REGION_VOCABULARY` y que
`mean_cost`: el numero se guarda, se puede imprimir, y no gobierna ni informa nada. Esto lo
lee, y sale gratis porque el dato ya se pago.

POR QUE IMPORTA PARA EL PRODUCTO Y NO SOLO PARA EL PAPER. La utilidad y el costo deciden
que paradigma conviene; la LATENCIA decide si alguien lo puede usar. Un brazo que gana por
0,02 de utilidad y tarda cuatro veces mas no gana: cambia una metrica que el usuario no ve
por una que sufre en cada request.

Y NO ES UNA FUNCION DEL COSTO. Un brazo de dos llamadas grandes y uno de veinte chicas
pueden gastar lo mismo y tardar muy distinto, porque la latencia tiene un componente FIJO
por llamada —la ida y vuelta— que los tokens no expresan. Por eso se reporta el costo por
llamada aparte: es lo que separa «tarda porque gasta» de «tarda porque llama mucho».

LO QUE ESTE ANALISIS NO PUEDE CONTESTAR, y conviene decirlo arriba: **tiempo al primer
token**. `llm.py` no hace streaming —un POST y se espera la respuesta entera— asi que no
existe un evento de primer token que cronometrar. Medirlo es trabajo, no analisis, y esta
registrado aparte. Para una interfaz con SSE (lo que `ARQUITECTURA.es.md` propone) ese es
el numero que el usuario percibe, y hoy no se tiene.

CUIDADO CON LEER ESTO COMO LATENCIA DE PRODUCCION. El banco corre con concurrencia y
comparte cuota consigo mismo, asi que estos numeros incluyen espera por rate limit. Sirven
para COMPARAR brazos entre si —todos sufren lo mismo— y no como cota de lo que un request
solo tardaria.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.runner import load_rows
from bench._sanity import bounded


def percentil(valores: list[float], q: float) -> float:
    """El percentil `q` sobre una lista chica, sin dependencias.

    Se usa p50 y p95 y NO la media: la latencia tiene cola larga —un reintento por rate
    limit multiplica una celda— y la media de una distribucion con cola describe un caso
    que casi nunca ocurre. La mediana dice como es normalmente y el p95 dice cuanto duele
    cuando duele.
    """
    if not valores:
        raise ValueError("percentil de una lista vacia: no hay nada que resumir")
    orden = sorted(valores)
    if len(orden) == 1:
        return orden[0]
    pos = q * (len(orden) - 1)
    bajo = int(pos)
    alto = min(bajo + 1, len(orden) - 1)
    return orden[bajo] + (orden[alto] - orden[bajo]) * (pos - bajo)


def main() -> None:
    raiz = Path("results/nano")
    if not raiz.exists():
        print("No hay registro nano. Nada que leer — se dice, no se inventa.")
        return

    filas = []
    for f in sorted(raiz.glob("*.jsonl")):
        filas.extend(load_rows(f))
    filas = [
        r for r in filas
        if not r.get("error") and r.get("wall_seconds") and r.get("calls")
    ]
    if not filas:
        print("Ninguna fila con latencia y llamadas — SIN N.")
        return

    por: dict[str, list[dict]] = defaultdict(list)
    for r in filas:
        por[r["paradigm"]].append(r)

    print(f"{len(filas)} filas con latencia registrada\n")
    print(f"  {'brazo':<14} {'p50 s':>8} {'p95 s':>8} {'s/llamada':>10} "
          f"{'llamadas':>9} {'u media':>8}")
    resumen = {}
    for brazo, rs in sorted(por.items()):
        segs = [r["wall_seconds"] for r in rs]
        llamadas = [r["calls"] for r in rs]
        # SEGUNDOS POR LLAMADA, y se calcula por FILA antes de promediar. Dividir el
        # promedio de segundos por el promedio de llamadas mezcla filas de tamanos
        # distintos y da un numero que no le corresponde a ninguna.
        por_llamada = [r["wall_seconds"] / r["calls"] for r in rs if r["calls"] > 0]
        p50, p95 = percentil(segs, 0.50), percentil(segs, 0.95)
        bounded(p50, 0.0, None, f"p50 de {brazo}")
        u = statistics.mean(r["utility"] for r in rs)
        resumen[brazo] = (p50, statistics.mean(por_llamada), u)
        print(f"  {brazo:<14} {p50:>8.1f} {p95:>8.1f} "
              f"{statistics.mean(por_llamada):>10.2f} "
              f"{statistics.mean(llamadas):>9.1f} {u:>8.3f}")

    # LA PREGUNTA QUE IMPORTA: alguien gana utilidad y la paga en tiempo?
    print("\n  latencia RELATIVA al mas rapido, contra utilidad:")
    piso = min(v[0] for v in resumen.values())
    if piso <= 0:
        print("    el mas rapido registra 0 s: no hay escala. Se dice, no se inventa.")
        return
    for brazo, (p50, spc, u) in sorted(resumen.items(), key=lambda kv: kv[1][0]):
        print(f"    {brazo:<14} {p50 / piso:>5.1f}x mas lento   u={u:.3f}")

    print("\n  Y la parte que NO sale de aca: tiempo al PRIMER TOKEN. `llm.py` no hace")
    print("  streaming —un POST y se espera la respuesta entera— asi que no hay evento")
    print("  de primer token que cronometrar. Para una interfaz con SSE ese es el numero")
    print("  que el usuario percibe, y hoy no existe en ninguna fila.")


if __name__ == "__main__":
    main()
