"""¿Este corpus PUEDE contestar la pregunta del ruteo? Cero llamadas al modelo.

LA PREGUNTA QUE NADIE HACIA ANTES DE PAGAR. Un banco de selección de paradigma sólo puede
demostrar algo si los paradigmas **se separan** en ese corpus. Si la varianza entre brazos
está al nivel del ruido entre réplicas, ninguna política puede ganar — y el resultado se lee
como «el ruteo no sirve» cuando lo que dice es «este corpus no lo puede medir».

DE DONDE SALE, y es caro: sobre `gold_h1` con la campaña terminada, la descomposición dio

    varianza total de la utilidad          0,2469
    entre TAREAS                           0,1153   47%
    entre PARADIGMAS                       0,0311   13%
    entre REPLICAS de la misma celda       0,0311   13%

**0,0311 contra 0,0311, iguales a la cuarta decimal.** La señal sobre la que un router elige
tiene exactamente el tamaño del ruido contra el que se la mide. Eso no se supo hasta después
de gastar la campaña entera, y **se podía haber sabido con una fracción**: la descomposición
necesita réplicas y varios brazos, no el producto cruzado completo.

QUE HACE ESTO. Toma el registro que HAYA —parcial sirve— y reporta las tres varianzas más
la razón que decide:

    señal / ruido = varianza entre paradigmas / varianza entre réplicas

Por debajo de 1 el corpus no puede demostrar ruteo, y decirlo antes es la diferencia entre
un resultado negativo y plata tirada. No es un umbral estadístico con teoría atrás: es la
comparación mínima que tiene que dar a favor para que valga la pena seguir.

QUE **NO** HACE. No dice que el ruteo no sirva; dice que ESTE corpus no lo puede mostrar. Y
no reemplaza al piso de ruido por celda, que es lo que decide una comparación puntual: esto
mira la estructura del corpus entero, aquello mira una diferencia.

Corre DESDE `lab/`:  py bench/_potencia_corpus.py --modelo luna
"""

from __future__ import annotations

import argparse
import collections
import statistics
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.runner import load_rows

# EL UMBRAL NO ES 1,0, Y CORREGIRLO FUE EL PRIMER USO DE ESTE ARCHIVO.
#
# Lo escribí en 1,0 —«la señal tiene que superar al ruido»— y sobre `gold_h1` dio **1,0010**
# y **pasó**. O sea que la guarda habría aprobado exactamente el corpus que la motivó, donde
# la varianza entre brazos y el ruido de réplica coinciden a la cuarta decimal.
#
# La razón de fondo: `señal/ruido = 1` NO significa «apenas alcanza». Significa **que la
# diferencia entre dos brazos mide lo mismo que la diferencia entre dos corridas del mismo
# brazo**. En ese punto no hay nada que elegir, y aprobar ahí es aprobar el caso de falla.
#
# 2,0 pide que la varianza entre brazos DUPLIQUE al ruido — lo mínimo para que un
# ordenamiento entre brazos sobreviva a volver a correrlos. No tiene teoría atrás y se dice:
# es un piso de sentido común, y lo que lo justifica es que 1,0 demostradamente no sirve.
RAZON_MINIMA = 2.0

# Y HACE FALTA UN MINIMO DE TAREAS PARA QUE LA RAZON SIGNIFIQUE ALGO. Submuestreando
# `gold_h1` —S/R verdadero 1,00— el estimador da >= 2,0 en el 46% de los sorteos con 3
# tareas, 34% con 8, 13% con 20 y 2% con 30. Debajo de 30 la guarda aprueba ruido.
TAREAS_MINIMAS = 30


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--modelo", default="luna")
    ap.add_argument("--corpus", default="gold_h1")
    ap.add_argument("--archivo", default="", help="sufijo de factores, si aplica")
    args = ap.parse_args()

    nombre = f"{args.corpus}{args.archivo}_rows.jsonl"
    ruta = _Path("results") / args.modelo / nombre
    filas = [f for f in load_rows(ruta) if not f.get("infeasible")]
    if not filas:
        raise SystemExit(f"{ruta} no tiene filas medidas.")

    celdas: dict[tuple, list[float]] = collections.defaultdict(list)
    for f in filas:
        celdas[(f["task_id"], f["paradigm"])].append(f["utility"])
    con_replicas = [v for v in celdas.values() if len(v) > 1]
    if not con_replicas:
        raise SystemExit(
            "Ninguna celda tiene réplicas. Sin réplicas no hay ruido que medir, y sin "
            "ruido esta comparación no significa nada — correr con `repeat >= 3`."
        )

    med = {k: statistics.mean(v) for k, v in celdas.items()}
    portarea = collections.defaultdict(list)
    porpara = collections.defaultdict(list)
    for (t, p), m in med.items():
        portarea[t].append(m)
        porpara[p].append(m)

    total = statistics.pvariance([f["utility"] for f in filas])
    ruido = statistics.mean([statistics.pvariance(v) for v in con_replicas])
    v_tarea = statistics.pvariance([statistics.mean(v) for v in portarea.values()])
    v_para = statistics.pvariance([statistics.mean(v) for v in porpara.values()])

    print(f"{nombre}: {len(filas)} filas medidas · {len(celdas)} celdas · "
          f"{len(porpara)} brazos · {len(portarea)} tareas")
    print(f"celdas con réplicas: {len(con_replicas)} de {len(celdas)}\n")
    print(f"  varianza total de la utilidad       {total:>8.4f}")
    print(f"  entre TAREAS                        {v_tarea:>8.4f}   "
          f"{100*v_tarea/total:>3.0f}%   no lo mueve ninguna política")
    print(f"  entre PARADIGMAS                    {v_para:>8.4f}   "
          f"{100*v_para/total:>3.0f}%   es TODO lo que un router puede pelear")
    print(f"  entre RÉPLICAS de la misma celda    {ruido:>8.4f}   "
          f"{100*ruido/total:>3.0f}%   ruido por construcción")

    razon = v_para / ruido if ruido else float("inf")

    # EL INTERVALO, Y SIN ÉL ESTE NÚMERO MIENTE SOBRE UN CORPUS CHICO (2026-08-30).
    #
    # La primera versión reportaba la razón pelada. Medido después: submuestreando
    # `gold_h1` —cuyo S/R verdadero es **1,00**— a 8 tareas, **el 34% de los sorteos da
    # 2,0 o más**, con mediana 1,59 y máximo 24,94. O sea que sobre un corpus de 8 tareas
    # esta guarda habría aprobado un corpus que no separa nada, un tercio de las veces.
    #
    # Y el sesgo tiene dirección: la mediana baja 1,80 → 1,59 → 1,28 → 1,07 → 1,00 a
    # medida que crecen las tareas. **Con pocas tareas el estimador exagera**, así que un
    # corpus chico con S/R alto es la lectura más fácil de creer y la menos confiable.
    #
    # Bootstrap sobre TAREAS —no sobre filas— porque la tarea es la unidad que se
    # remuestrea: dos réplicas de la misma tarea no son dos observaciones independientes
    # de la separación entre brazos.
    import random
    tareas = sorted({t for t, _ in med})
    rng = random.Random(7)
    muestras = []
    for _ in range(400):
        sub = [rng.choice(tareas) for _ in tareas]
        cuenta = collections.Counter(sub)
        pp = collections.defaultdict(list)
        rr = []
        for (t, p_), m in med.items():
            for _ in range(cuenta.get(t, 0)):
                pp[p_].append(m)
        for (t, p_), v in celdas.items():
            if len(v) > 1:
                rr += [statistics.pvariance(v)] * cuenta.get(t, 0)
        if len(pp) < 2 or not rr:
            continue
        r_ = statistics.mean(rr)
        if r_:
            muestras.append(
                statistics.pvariance([statistics.mean(v) for v in pp.values()]) / r_)
    muestras.sort()
    lo = muestras[int(0.05 * (len(muestras) - 1))] if muestras else float("nan")
    hi = muestras[int(0.95 * (len(muestras) - 1))] if muestras else float("nan")

    print(f"\n  SEÑAL / RUIDO = {razon:.3f}   [{lo:.2f} – {hi:.2f}]   "
          f"(hace falta >= {RAZON_MINIMA:.1f})")
    if len(portarea) < TAREAS_MINIMAS:
        print(f"\n  NO ALCANZA PARA CONCLUIR: {len(portarea)} tareas, hacen falta "
              f"{TAREAS_MINIMAS}.")
        print(f"  Medido: sobre 8 tareas, un corpus cuyo S/R real es 1,00 da >= 2,0 el")
        print(f"  34% de las veces. Con menos tareas el estimador EXAGERA, así que un")
        print(f"  numerito alto acá es la lectura más fácil de creer y la menos confiable.")
        raise SystemExit(2)
    if lo < RAZON_MINIMA <= hi:
        print(f"\n  EL INTERVALO CRUZA EL UMBRAL: no se puede concluir en ninguna")
        print(f"  dirección. Hacen falta más TAREAS — no más réplicas, que achican el")
        print(f"  error de la media y no la varianza entre brazos.")
        raise SystemExit(2)
    print()
    if razon < RAZON_MINIMA:
        print("  ESTE CORPUS NO PUEDE DEMOSTRAR RUTEO.")
        print("  La varianza entre brazos no supera al ruido entre réplicas, así que")
        print("  ninguna política puede ganar de forma distinguible — y un resultado")
        print("  negativo acá NO dice «el ruteo no sirve», dice «acá no se puede ver».")
        print()
        print("  Lo que lo movería: brazos que se separen más en estas tareas, o tareas")
        print("  donde la elección importe. NO es más `repeat` — más réplicas achican el")
        print("  error de la MEDIA, no la varianza entre brazos, que es la que falta.")
        print()
        print("  Y `razón = 1` no es «apenas alcanza»: es que la diferencia ENTRE brazos")
        print("  mide lo mismo que la diferencia entre dos corridas DEL MISMO brazo.")
        raise SystemExit(1)
    print("  El corpus separa los brazos por encima del ruido: la pregunta se puede medir.")


if __name__ == "__main__":
    main()
