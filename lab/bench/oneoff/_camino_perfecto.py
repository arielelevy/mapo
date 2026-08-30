"""EL CAMINO PERFECTO derivado a mano sobre las 78, contra lo que luna midio. Cero llamadas.

EL EXPERIMENTO, del autor: leer cada pregunta, razonar cual patron deberia ganar y por que,
y comparar contra el registro. Lo que se busca no es acertar: es ver **donde hay brecha y
por que**, porque ahi es donde el lab tiene que mejorar.

LAS DOS REGLAS QUE LA PRIMERA VERSION VIOLO, y por eso no valia nada:

  1. LA FACTIBILIDAD VA PRIMERO. El conjunto de candidatos es lo que PUEDE correr. Predije
     `direct` en 27 de 41 tareas y `direct` es candidato en **2 de 18** combinaciones de
     celda x ancho: el porton aritmetico lo poda por presupuesto antes del primer token.
  2. EL OBJETIVO ES «MAXIMA UTILIDAD, Y ENTRE LAS QUE EMPATAN, MINIMO COSTO». Sin eso «el
     mejor brazo» no esta definido: empatan 6,6 brazos en el maximo.

Y UNA TERCERA QUE APARECIO AL CENTRALIZAR LAS GUARDAS: los patrones **no compiten al mismo
presupuesto** — 113x entre el mas barato y el mas caro. Asi que una parte de cualquier
brecha que encuentre este archivo es diferencia de presupuesto y no de topologia. Se declara
antes de leer el resultado.

CONTAMINACION DECLARADA: ya vi la utilidad media por brazo, las 5 tareas con un unico mejor
brazo y cuales eran, y la correlacion cobertura-utilidad por celda. Las tareas afectadas se
marcan y se puntuan aparte.

Corre DESDE `lab/`:  py bench/oneoff/_camino_perfecto.py
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

from app import feasibility
from app.paradigms import campaign_roster
from app.runner import load_rows

CONTAMINADAS = {"b2-000-w4", "b2-001-w16", "b2-002-w16", "c3-000-h1", "c2-001-w4"}

# El razonamiento va POR CELDA porque las preguntas de una celda son la misma forma. Donde
# el ancho cambia la respuesta, se dice.
#
# (celda, ancho) -> (patron, por que)
CAMINO: dict[tuple[str, str], tuple[str, str]] = {

    ("C1_single_verifiable", "base"): ("rewoo",
        "UNA unidad y un hecho. No hay nada que buscar ni que encadenar, asi que lo unico "
        "que importa es el precio de llegar: `rewoo` son dos llamadas fijas y no puede "
        "hacer menos ningun otro"),

    ("C2_bulk_independent", "w4"): ("gist_reader",
        "enumerar un ROL sobre todas las unidades. El rol es exactamente lo que un resumen "
        "conserva, asi que ver todas en gist alcanza; `handoff` garantizaria cobertura pero "
        "cuesta 4x por una garantia que el gist ya da para este atributo"),
    ("C2_bulk_independent", "w16"): ("gist_reader", "idem, y con 20 unidades la ventaja de "
        "ver todas por resumen crece"),

    ("C3_coupled_chain", "base"): ("react",
        "el paso dos no se puede FORMULAR sin el resultado del uno. Es el unico brazo con "
        "bucle reactivo real: descomponer una cadena la destruye, y planificar de antemano "
        "es planificar una busqueda cuyo termino todavia no se conoce"),

    ("C4_aggregate_full_coverage", "w4"): ("extract_compute",
        "CONTAR es la operacion que el modelo hace peor. Este patron extrae filas y agrega "
        "EN CODIGO — es literalmente su caso, y en w4 la factibilidad lo admite"),
    ("C4_aggregate_full_coverage", "w16"): ("handoff",
        "sin `extract_compute`, contar exige cobertura total. La particion es segura porque "
        "los conteos son ADITIVOS sobre alcances disjuntos — el unico riesgo es que una "
        "persona aparezca en dos unidades y se cuente dos veces"),

    ("C5_unknown_horizon", "w4"): ("direct",
        "la contradiccion CRUZA unidades: un sub-agente que ve un lado no la puede ver. "
        "Partir es fatal por construccion, y en w4 todo entra en un contexto"),
    ("C5_unknown_horizon", "w16"): ("gist_reader",
        "sin `direct`, hace falta algo que vea TODAS las unidades a la vez. El gist las "
        "sirve todas en un prompt, y una contradiccion de ciudad es visible entre dos "
        "resumenes. `handoff` esconderia la contradiccion en la costura"),

    ("C7_irreversible", "base"): ("gist_reader",
        "booleano con testigo unico: encontrar la alerta, o probar que no esta. Una alerta "
        "de compliance es justo lo que un resumen conserva, y ver las 8 unidades de una vez "
        "cubre las dos polaridades"),

    ("C8_currency", "w4"): ("direct",
        "hay que elegir el registro MAS RECIENTE entre varios que compiten, asi que hacen "
        "falta todos los registros CON SUS FECHAS en un solo lugar. Un gist puede borrar la "
        "fecha, que es exactamente el dato que decide"),
    ("C8_currency", "w16"): ("rewoo",
        "sin `direct`: una busqueda por el numero de cuenta trae todos los registros de esa "
        "cuenta, y la llamada final de `rewoo` los ve JUNTOS con su texto. `handoff` seria "
        "fatal — un sub-agente que solo ve el registro viejo contesta convencido"),

    ("C9_declared_roster", "w4"): ("rewoo",
        "la lista de nombres VIENE EN LA PREGUNTA. Los pasos se pueden enumerar antes de "
        "empezar y son independientes entre si: es la precondicion exacta de `rewoo`, y "
        "planificar de antemano deja de ser una limitacion"),
    ("C9_declared_roster", "w16"): ("rewoo", "idem — la lista sigue estando dada"),

    ("D1_presupposition", "w4"): ("gist_reader",
        "la presuposicion es FALSA y hay que negarse. El riesgo es confabular una fecha "
        "despues de buscar sin encontrar, asi que conviene VER todo de una vez en vez de "
        "iterar buscando"),
    ("D1_presupposition", "w16"): ("gist_reader", "idem, y con 20 unidades el riesgo de "
        "confabular tras busquedas fallidas es mayor"),

    ("W1_shared_writes", "base"): ("gist_reader",
        "booleano sobre un conflicto de escritura pendiente, 9 unidades. Misma forma que "
        "`C7`: ver todo una vez y decidir"),

    ("B2_absence", "w4"): ("handoff",
        "probar una AUSENCIA exige cobertura demostrada: presencia se prueba con un "
        "testigo, ausencia con el dominio entero. La particion la garantiza, y un gist que "
        "omite un rol raro es exactamente el error fatal aca"),
    ("B2_absence", "w16"): ("handoff", "idem, y sobre 20 unidades la garantia vale mas"),
}


def ancho(task_id: str) -> str:
    return "w16" if "w16" in task_id else "w4" if "w4" in task_id else "base"


def main() -> None:
    docs = json.loads(_Path("corpus/gold_h1/documents.json").read_text(encoding="utf-8"))
    tareas = json.loads(_Path("corpus/gold_h1/tasks.json").read_text(encoding="utf-8"))
    roster = list(campaign_roster())
    fact = {t["task_id"]: [p for p in roster
                           if feasibility.check(p, docs, t).feasible] for t in tareas}

    filas = [f for f in load_rows(_Path("results/luna/gold_h1_rows.jsonl"))
             if not f.get("infeasible")]
    u = collections.defaultdict(list)
    c = collections.defaultdict(list)
    for f in filas:
        u[(f["task_id"], f["paradigm"])].append(f["utility"])
        c[(f["task_id"], f["paradigm"])].append(f["cost_tokens"])
    U = {k: statistics.mean(v) for k, v in u.items()}
    C = {k: statistics.mean(v) for k, v in c.items()}
    pt = collections.defaultdict(dict)
    for (t, p), v in U.items():
        pt[t][p] = v

    print(f"{len(tareas)} tareas en el corpus · {len(pt)} con medicion de luna\n")
    print("=" * 104)
    print(f"{'tarea':<15}{'camino a mano':<16}{'u':>6}{'costo':>10}  "
          f"{'oraculo':<16}{'u':>6}{'costo':>10}{'brecha':>8}")

    filas_res = []
    for t in sorted(tareas, key=lambda z: z["task_id"]):
        tid = t["task_id"]
        d = pt.get(tid)
        pred, _ = CAMINO[(t["cell"], ancho(tid))]
        factible = pred in fact[tid]
        if not d:
            filas_res.append((tid, pred, None, None, None, None, "sin medir", factible))
            continue
        m = max(d.values())
        emp = sorted([(p, C[(tid, p)]) for p, v in d.items() if abs(v - m) < 1e-9],
                     key=lambda x: x[1])
        orac, orac_c = emp[0]
        up = d.get(pred)
        cp = C.get((tid, pred))
        brecha = (m - up) if up is not None else None
        filas_res.append((tid, pred, up, cp, orac, orac_c, brecha, factible))
        marca = "*" if tid in CONTAMINADAS else " "
        upd = f"{up:.2f}" if up is not None else "  PODADO"
        cpd = f"{cp:,.0f}" if cp is not None else "-"
        bd = f"{brecha:+.2f}" if brecha is not None else "-"
        print(f"{marca}{tid:<14}{pred:<16}{upd:>6}{cpd:>10}  "
              f"{orac:<16}{m:>6.2f}{orac_c:>10,.0f}{bd:>8}")

    medidas = [r for r in filas_res if r[2] is not None and r[0] not in CONTAMINADAS]
    conta = [r for r in filas_res if r[2] is not None and r[0] in CONTAMINADAS]
    print("\n" + "=" * 104)
    n = len(medidas)
    aciertos = sum(1 for r in medidas if abs(r[6]) < 1e-9)
    print(f"SOBRE LAS {n} MEDIDAS NO CONTAMINADAS")
    print(f"  alcanza la utilidad del oraculo : {aciertos}  ({100*aciertos/n:.0f}%)")
    print(f"  utilidad del camino a mano      : {statistics.mean(r[2] for r in medidas):.4f}")
    print(f"  utilidad del oraculo            : "
          f"{statistics.mean(r[2] + r[6] for r in medidas):.4f}")
    print(f"  BRECHA DE CALIDAD               : "
          f"{statistics.mean(r[6] for r in medidas):+.4f}")
    print(f"  costo del camino a mano         : "
          f"{statistics.mean(r[3] for r in medidas):>10,.0f} tokens/tarea")
    print(f"  costo del oraculo               : "
          f"{statistics.mean(r[5] for r in medidas):>10,.0f}")
    if conta:
        print(f"\n  (las {len(conta)} contaminadas, aparte: brecha "
              f"{statistics.mean(r[6] for r in conta):+.4f})")

    print("\n" + "=" * 104)
    print("DONDE ESTA LA BRECHA — y esto es lo que el lab tiene que mejorar\n")
    peores = sorted([r for r in medidas if r[6] > 1e-9], key=lambda r: -r[6])
    for tid, pred, up, cp, orac, oc, br, _ in peores:
        celda = next(t["cell"] for t in tareas if t["task_id"] == tid)
        print(f"  {tid:<15}{celda:<28}predije {pred:<15}({up:.2f})  "
              f"ganaba {orac:<15}({up+br:.2f})")
    if not peores:
        print("  (ninguna: el camino a mano alcanza al oraculo en todas)")


if __name__ == "__main__":
    main()
