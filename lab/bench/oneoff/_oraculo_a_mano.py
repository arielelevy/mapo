"""El camino ideal DERIVADO A MANO, contra el que el registro midio. Cero llamadas.

EL EXPERIMENTO, propuesto por el autor (2026-08-30): en vez de preguntarle a un modelo o
ajustar una politica, **un analista lee cada pregunta del corpus y deriva cual deberia ser
el mejor patron y por que** — maximo acierto al minimo costo. Despues se compara esa
prediccion contra el oraculo empirico, y se busca que senales disponibles la explican.

POR QUE ESTO CONTESTA ALGO QUE NINGUN OTRO ANALISIS PUEDE. `ONT-1` midio que agrupar por
celda del corpus separa los brazos mejor por segmento que el vocabulario estructural, y
dejo una amenaza escrita: **la celda es un PROXY de la ontologia, y que agrupar por ella
funcione no dice que un clasificador pueda recuperar el eje de un request REAL.** Aca el
clasificador es un analista leyendo el texto de la pregunta y nada mas. Si acierta, el eje
es recuperable; si no, no lo es, y eso cierra la discusion en la direccion incomoda.

LA CONTAMINACION, DECLARADA ANTES DE PUNTUAR — y sin esto el experimento no vale nada:

  YA VISTO   la utilidad media POR BRAZO sobre todo el corpus; las 5 tareas con un unico
             mejor brazo y cuales eran (3 de `b2` las gana `handoff`, `c3-000-h1` la gana
             `gist_reader`); la correlacion cobertura-utilidad por celda
  NO VISTO   el mejor brazo por tarea, para 41 de las 46

Las 5 contaminadas se puntuan APARTE y no cuentan para el resultado principal. Marcarlas
cuesta una linea; no marcarlas invalidaria las 46.

LA PREDICCION SE HACE DESDE EL TEXTO DE LA PREGUNTA y los campos que un request declara —
NO desde `relevant_units`, que es gold y no existe al decidir. El razonamiento de cada una
esta escrito abajo para que se pueda discutir por separado del acierto.

LA PRIMERA VERSION IGNORO LA FACTIBILIDAD, Y ESO LA INVALIDABA (corregido por el autor,
2026-08-30). Predije `direct` en 27 de 41 tareas. **`direct` no es candidato en 42 de 46**:
el porton aritmetico lo poda antes de que exista un token, por presupuesto. El 66% de mis
predicciones nombraban un brazo que no puede correr.

    LA REGLA, Y VA PRIMERO: el conjunto de candidatos es lo que PUEDE correr, no el
    catalogo. La factibilidad es aritmetica, es gratis, y se resuelve antes que cualquier
    otra cosa. Un camino ideal que empieza ignorandola no es un camino: es un deseo.

Medido sobre `gold_h1`: el porton deja **9,3 candidatos de 12** en promedio, podando 124
celdas. `direct` cae en 42 tareas, `extract_compute` y `streaming_scan` en 38 cada uno.

Y HAY UNA SEGUNDA REGLA QUE LA PRIMERA VERSION TAMPOCO RESPETO: el objetivo es **maxima
utilidad y, entre las que empatan, minimo costo**. Sin eso «el mejor brazo» no esta
definido — en las 46 tareas empatan **6,6 brazos** en el maximo, asi que nombrar uno de los
seis y llamarlo acierto no mide nada.

Con las dos reglas puestas, la prediccion pasa a ser: **de los brazos FACTIBLES, cual da la
maxima utilidad al menor costo**. Es mas dificil y es la que el router tiene que hacer.

Corre DESDE `lab/`:  py bench/oneoff/_oraculo_a_mano.py
"""

from __future__ import annotations

import collections
import json
import statistics
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.runner import load_rows

CONTAMINADAS = {"b2-000-w4", "b2-001-w16", "b2-002-w16", "c3-000-h1", "c2-001-w4"}

# (patrón predicho, eje ontológico, razonamiento). El eje sale de la pregunta, no de la
# celda: la celda es la etiqueta del generador y no existe en un request real.
PREDICCION: dict[str, tuple[str, str, str]] = {
    # ---- un hecho en una unidad. No hay nada que buscar ni que decidir.
    "c1-000": ("direct", "puntual", "una unidad, un hecho. Leerla es la respuesta"),
    "c1-001": ("direct", "puntual", "idem"),
    "c1-002": ("direct", "puntual", "idem"),

    # ---- enumerar sobre TODO el alcance, unidad por unidad e independientes entre si.
    #      Descomponer es SEGURO porque no hay dependencia entre unidades.
    "c2-000-w4": ("direct", "cobertura", "5 unidades entran: leer todo y enumerar"),
    "c2-000-w16": ("handoff", "cobertura",
                   "20 unidades, independientes: partir el alcance garantiza cobertura"),
    "c2-001-w16": ("handoff", "cobertura", "idem"),
    "c2-002-w16": ("handoff", "cobertura", "idem"),

    # ---- cadena SECUENCIAL: el paso 2 no se puede formular sin el resultado del 1.
    #      Descomponer la destruye. 60 unidades con 40k: leer todo es infactible.
    "c3-001-h2": ("react", "encadenamiento",
                  "dos saltos: hay que usar el resultado del primero para el segundo"),

    # ---- contar sobre todo el alcance. Miscontar es la falla; hace falta ver todo junto.
    "c4-000-w4": ("direct", "cobertura", "5 unidades: leer y contar"),
    "c4-001-w4": ("direct", "cobertura", "idem"),
    "c4-000-w16": ("direct", "cobertura",
                   "contar exige tener todo a la vez; partir arriesga doble conteo"),
    "c4-001-w16": ("direct", "cobertura", "idem"),
    "c4-002-w16": ("direct", "cobertura", "idem"),

    # ---- CONTRADICCION entre unidades. Un sub-agente que ve un lado no la puede ver.
    #      Descomponer es fatal por construccion.
    "c5-000-w4": ("direct", "contradiccion", "la contradiccion cruza unidades: todo junto"),
    "c5-001-w4": ("direct", "contradiccion", "idem"),
    "c5-000-w16": ("direct", "contradiccion",
                   "17 unidades, pero partirlas esconde la contradiccion en la costura"),
    "c5-001-w16": ("direct", "contradiccion", "idem"),
    "c5-002-w16": ("direct", "contradiccion", "idem"),

    # ---- booleano con testigo unico. Positivo: encontrar la alerta. Negativo: probar
    #      que no esta. 8-9 unidades con 20k entran comodas.
    "c7-000-neg": ("direct", "puntual", "entra todo: leer y decidir"),
    "c7-000-pos": ("direct", "puntual", "idem"),
    "c7-001-neg": ("direct", "puntual", "idem"),
    "c7-001-pos": ("direct", "puntual", "idem"),
    "c7-002-neg": ("direct", "puntual", "idem"),
    "c7-002-pos": ("direct", "puntual", "idem"),

    # ---- VIGENCIA: hay enmiendas que supersiguen. Leer mas trae mas candidatos VIEJOS.
    #      La falla es contestar con un valor superado, con procedencia impecable.
    "c8-000-w4": ("direct", "vigencia", "hay que ordenar por fecha: todo en un contexto"),
    "c8-001-w4": ("direct", "vigencia", "idem"),
    "c8-000-w16": ("direct", "vigencia",
                   "un sub-agente que ve solo el registro viejo contesta convencido"),
    "c8-001-w16": ("direct", "vigencia", "idem"),
    "c8-002-w16": ("direct", "vigencia", "idem"),

    # ---- la lista de nombres VIENE EN LA PREGUNTA: descomposicion de manual, una
    #      busqueda independiente por nombre.
    "c9-000-w4": ("handoff", "cobertura", "4 lookups independientes, dados de antemano"),
    "c9-001-w4": ("handoff", "cobertura", "idem"),
    "c9-000-w16": ("handoff", "cobertura", "5 lookups sobre 20 unidades: partir por nombre"),
    "c9-001-w16": ("handoff", "cobertura", "idem"),
    "c9-002-w16": ("handoff", "cobertura", "idem"),

    # ---- PRESUPOSICION FALSA: no existe tal transferencia. Hay que negarse.
    #      Un bucle que busca y no encuentra tiende a confabular una fecha.
    "d1-000-w4": ("direct", "ausencia", "5 unidades: ver que no esta y decirlo"),
    "d1-000-w16": ("direct", "ausencia",
                   "negar una presuposicion exige haber mirado todo, no haber buscado mal"),
    "d1-001-w16": ("direct", "ausencia", "idem"),
    "d1-002-w16": ("direct", "ausencia", "idem"),

    # ---- booleano sobre conflicto de escritura. Entra todo.
    "w1-000-pos": ("direct", "puntual", "9 unidades con 20k: leer y decidir"),
    "w1-001-neg": ("direct", "puntual", "idem"),

    # ---- AUSENCIA: la respuesta es «ninguno», y probarla exige cobertura TOTAL.
    "b2-000-w16": ("handoff", "ausencia",
                   "probar una ausencia sobre 20 unidades exige particion garantizada"),
    # contaminadas (se puntuan aparte)
    "b2-000-w4": ("direct", "ausencia", "5 unidades entran: leer todo y negar"),
    "b2-001-w16": ("handoff", "ausencia", "idem que b2-000-w16"),
    "b2-002-w16": ("handoff", "ausencia", "idem"),
    "c3-000-h1": ("react", "encadenamiento", "un salto: buscar, leer, buscar de nuevo"),
    "c2-001-w4": ("direct", "cobertura", "5 unidades entran"),
}


def main() -> None:
    filas = [f for f in load_rows(_Path("results/luna/gold_h1_rows.jsonl"))
             if not f.get("infeasible")]
    celdas: dict[tuple, list[float]] = collections.defaultdict(list)
    costos: dict[tuple, list[float]] = collections.defaultdict(list)
    for f in filas:
        celdas[(f["task_id"], f["paradigm"])].append(f["utility"])
        costos[(f["task_id"], f["paradigm"])].append(f["cost_tokens"])
    u = {k: statistics.mean(v) for k, v in celdas.items()}
    c = {k: statistics.mean(v) for k, v in costos.items()}

    por_tarea: dict[str, dict[str, float]] = collections.defaultdict(dict)
    for (t, p), v in u.items():
        por_tarea[t][p] = v

    print(f"{len(PREDICCION)} predicciones · {len(por_tarea)} tareas con medicion")
    print(f"{len(CONTAMINADAS)} contaminadas, puntuadas aparte\n")
    print("=" * 100)
    print(f"{'tarea':<15}{'predicho':<15}{'u pred':>7}{'mejor medido':<17}{'u':>6}"
          f"{'Δ':>7}  eje")
    limpio = collections.Counter()
    conta = collections.Counter()
    detalle = []
    for t, (pred, eje, _) in sorted(PREDICCION.items()):
        d = por_tarea.get(t)
        if not d:
            continue
        mejor = max(d.values())
        ganadores = sorted(p for p, v in d.items() if abs(v - mejor) < 1e-9)
        up = d.get(pred)
        if up is None:
            veredicto = "PODADO"
        elif abs(up - mejor) < 1e-9:
            veredicto = "ACIERTA"
        else:
            veredicto = "falla"
        (conta if t in CONTAMINADAS else limpio)[veredicto] += 1
        detalle.append((t, pred, up, ganadores, mejor, eje, veredicto, len(ganadores)))
        marca = "*" if t in CONTAMINADAS else " "
        gan = ganadores[0] + (f" +{len(ganadores)-1}" if len(ganadores) > 1 else "")
        upd = f"{up:.2f}" if up is not None else "  —"
        print(f"{marca}{t:<14}{pred:<15}{upd:>7}  {gan:<15}{mejor:>6.2f}"
              f"{(mejor - (up or 0)):>7.2f}  {eje}")

    n = sum(limpio.values())
    print("\n" + "=" * 100)
    print(f"SOBRE LAS {n} NO CONTAMINADAS:")
    for k in ("ACIERTA", "falla", "PODADO"):
        if limpio[k]:
            print(f"   {k:<10}{limpio[k]:>4}   {100*limpio[k]/n:>5.1f}%")
    print(f"\nSOBRE LAS {sum(conta.values())} CONTAMINADAS (no cuentan): {dict(conta)}")

    # EL PISO CONTRA EL QUE HAY QUE COMPARAR. Acertar el mejor brazo no vale nada si
    # CUALQUIER brazo lo acierta: en 35 de 43 tareas el mejor fijo YA es el oraculo.
    empatan = [d for d in detalle if d[7] > 1 and d[0] not in CONTAMINADAS]
    unicas = [d for d in detalle if d[7] == 1 and d[0] not in CONTAMINADAS]
    print(f"\nEL PISO: en {len(empatan)} de {n} tareas empatan {statistics.mean([d[7] for d in empatan]):.1f} brazos"
          f" en el maximo — ahi acertar es facil.")
    print(f"Las que DECIDEN son las {len(unicas)} con un unico mejor brazo:")
    for t, pred, up, gan, mejor, eje, ver, _ in unicas:
        print(f"   {t:<15}predicho {pred:<15}real {gan[0]:<15}{ver}   ({eje})")


if __name__ == "__main__":
    main()
