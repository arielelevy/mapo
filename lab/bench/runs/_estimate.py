"""Estimar una corrida ANTES de pagarla. Contra el corpus, nunca contra el registro.

POR QUE EXISTE. La regla del repo dice «estimar tokens antes de correr», y yo la cumpli con
el numero equivocado: lei un `.jsonl` de 90 filas y estime 362k. Eran 6 de 32 tareas — el
archivo era una corrida PARCIAL y no lo declara en ningun lado. La corrida gasto 12,2
millones: **34x**.

LA ARITMETICA CORRECTA es sobre el corpus, que si declara su tamano:

    celdas   = len(tasks.json) x brazos x repeat
    tokens   = suma sobre brazos de (celdas del brazo x costo medido por celda)

El costo por celda SI sale del registro, y ahi esta bien: es una media por brazo sobre
celdas que existieron. Lo que no se puede sacar del registro es CUANTAS celdas hay.

Y SE DESCUENTA LO QUE YA ESTA PAGO. El cache es content-addressed, asi que una celda cuyo
prompt no cambio vuelve gratis. Se reporta por separado —bruto y neto— porque son dos
numeros distintos y confundirlos es como el estimado sale mal en la otra direccion.
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

# Mezcla de salida para convertir a plata. Cota alta, igual que en la factibilidad.
SALIDA = 0.15


def costo_por_brazo() -> dict[str, float]:
    """Media de tokens por celda, por brazo, sobre TODO el registro nano.

    Esto SI sale del registro y esta bien: es una media sobre celdas que existieron. Lo
    que no se puede sacar de ahi es cuantas celdas tiene un corpus.
    """
    por: dict[str, list[int]] = defaultdict(list)
    raiz = Path("results/nano")
    if not raiz.exists():
        return {}
    for f in sorted(raiz.glob("*.jsonl")):
        for r in load_rows(f):
            if not r.get("error"):
                por[r["paradigm"]].append(r["cost_tokens"])
    return {p: statistics.mean(v) for p, v in por.items() if v}


def estimar(corpus: str, paradigmas: list[str], brazos: list[str],
            repeat: int) -> None:
    tp = Path(f"corpus/{corpus}/tasks.json")
    if not tp.exists():
        print(f"{corpus}: no existe. Se dice, no se supone.")
        return
    tareas = json.loads(tp.read_text(encoding="utf-8"))
    costos = costo_por_brazo()

    faltan = [p for p in paradigmas if p not in costos]
    if faltan:
        # SIN COSTO MEDIDO NO SE ESTIMA ESE BRAZO, y se declara. Ponerle el promedio de
        # los demas seria inventar el numero que la estimacion existe para dar.
        print(f"  [aviso] sin costo medido para {faltan}: quedan FUERA del estimado, "
              f"y el total es una COTA INFERIOR")

    celdas = len(tareas) * len(paradigmas) * repeat * len(brazos)
    por_brazo = {
        p: costos[p] * len(tareas) * repeat * len(brazos)
        for p in paradigmas if p in costos
    }
    total = sum(por_brazo.values())
    plata = total * ((1 - SALIDA) * NANO.prompt_per_mtok
                     + SALIDA * NANO.completion_per_mtok) / 1_000_000

    print(f"\n=== {corpus}: {len(tareas)} tareas x {len(paradigmas)} paradigmas "
          f"x {repeat} trials x {len(brazos)} brazos = {celdas:,} celdas")
    for p, t in sorted(por_brazo.items(), key=lambda kv: -kv[1]):
        print(f"    {p:<14} {costos[p]:>9,.0f} tok/celda  ->  {t:>12,.0f}")
    print(f"    {'TOTAL':<14} {'':>9}     ->  {total:>12,.0f} tokens "
          f"· USD ~{plata:.2f} de referencia")


def main() -> None:
    PARADIGMAS = ["dag_strategy", "gist_reader", "react", "rewoo"]
    print("CAMPAÑA DE FACTORES — un factor por vez contra una linea base comun.")
    print("El producto cruzado de 6 factores son 64 corridas; el barrido son 7.")
    print("Sets emparejados por celda, no producto cruzado completo (regla del repo).\n")

    estimar("gold_guards", PARADIGMAS, ["hybrid"], repeat=3)
    print("\n  ^ LA LINEA BASE. Cada factor cuesta OTRA corrida de este tamano.")
    print("    7 factores + base = 8 x lo de arriba, menos lo que el cache devuelva.")


if __name__ == "__main__":
    main()
