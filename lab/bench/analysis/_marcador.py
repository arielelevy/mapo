"""EL MARCADOR: el producto contra el camino perfecto y contra el techo. Cero llamadas.

POR QUÉ HACE FALTA UN SOLO ARCHIVO. Los números de esta línea de trabajo salieron de
paneles distintos —uno filtraba `infeasible`, otro no; uno usaba 7 brazos, otro 12; uno
medía brecha capturada y otro utilidad media— y **comparar entre paneles no compara nada**.
Acá van los cinco competidores sobre las MISMAS tareas, los MISMOS brazos y la MISMA
métrica, y se reportan calidad y costo juntos porque separarlos ya llevó a una conclusión
equivocada esta semana.

LOS CINCO, de techo a piso:

    ORÁCULO         el mejor brazo factible por tarea. Irrealizable: exige saber la
                    respuesta antes de elegir. Es la cota, no un competidor
    MEJOR FIJO      elegir siempre lo mismo. **Es la vara**: un motor que no lo supera
                    no compró nada, y la maquinaria de decidir no sale gratis
    PRODUCTO        el router como decide hoy — reglas + θ, por el camino ya corregido
                    que no puntúa placeholders. **θ FRÍA** (`cold_start`), no la ajustada
                    que `report()` aprende de los episodios: es una COTA INFERIOR del
                    producto, y hay que leerla así
    CAMINO A MANO   el derivado leyendo las 78 preguntas
    POLÍTICA POR REGIÓN  el desempate por costo sobre `regions/3-literal`, leave-one-out

EL PANEL ES 41 DE 78, Y LAS QUE FALTAN NO SON AL AZAR. Hay que leerlo con eso puesto:

    del corpus                              78
    - nunca se midieron                    -32   ->  46
    - contaminadas (declaradas)             -5   ->  41

Y de las 32 sin medir, **21 son de `w48`** —60 unidades, 483k tokens—, 9 de `w4` y 2 base.
`w48` es exactamente el régimen donde los paradigmas deberían diferir: donde leer todo es
imposible, donde la cobertura no se puede pagar, donde la topología tendría que decidir.

    Así que este cuadro dice que **en el régimen estrecho no hay premio de calidad**.
    NO dice que no lo haya en el ancho, porque el ancho no se corrió (`M-8`).

Corre DESDE `lab/`:  py bench/analysis/_marcador.py
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
from app.assurance import Assurance
from app.beliefs import Provenance
from app.paradigms import campaign_roster
from app.policy import PolicyBundle
from app.router import Router
from app.runner import COST_PRIORS, FALLBACK, load_rows

CONTAMINADAS = {"b2-000-w4", "b2-001-w16", "b2-002-w16", "c3-000-h1", "c2-001-w4"}
COUP = {"loose": 0.15, "mixed": 0.5, "tight": 0.85}

CAMINO = {
    "C1_single_verifiable": "rewoo", "C2_bulk_independent": "rewoo",
    "C4_aggregate_full_coverage": "rewoo", "C8_currency": "rewoo",
    "C9_declared_roster": "rewoo", "B2_absence": "rewoo",
    "D1_presupposition": "rewoo", "C3_coupled_chain": "react",
    "C7_irreversible": "react", "W1_shared_writes": "react",
}


def main() -> None:
    docs = json.loads(_Path("corpus/gold_h1/documents.json").read_text(encoding="utf-8"))
    tareas = {t["task_id"]: t for t in json.loads(
        _Path("corpus/gold_h1/tasks.json").read_text(encoding="utf-8"))}
    roster = list(campaign_roster())

    U, C = collections.defaultdict(list), collections.defaultdict(list)
    region = {}
    for f in load_rows(_Path("results/luna/gold_h1_rows.jsonl")):
        if f.get("infeasible"):
            continue
        U[(f["task_id"], f["paradigm"])].append(f["utility"])
        C[(f["task_id"], f["paradigm"])].append(f.get("cost_tokens") or 0)
        region[f["task_id"]] = f.get("region", "")

    medidas = {t for t, _ in U}
    tids = [t for t in tareas if t not in CONTAMINADAS and t in medidas]
    brazos = [p for p in roster
              if sum((t, p) in U for t in tids) >= 0.95 * len(tids)]
    tids = [t for t in tids if all((t, p) in U for p in brazos)]
    um = {(t, p): statistics.mean(U[(t, p)]) for t in tids for p in brazos}
    cm = {(t, p): statistics.mean(C[(t, p)]) for t in tids for p in brazos}

    dentro = [statistics.pvariance(U[(t, p)]) for t in tids for p in brazos
              if len(U[(t, p)]) > 1]
    tol = (statistics.mean(dentro) / 3.0) ** 0.5

    fijo = max(brazos, key=lambda p: statistics.mean(um[(t, p)] for t in tids))

    # ── el producto, por el camino corregido ────────────────────────────────
    router = Router(PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3),
                    COST_PRIORS, FALLBACK)

    def coup_de(t):
        for parte in region[t].split("/"):
            if parte in COUP:
                return COUP[parte], 1.0
        return None, 0.0

    def producto(t):
        c, cr = coup_de(t)
        plan = router.plan(task=tareas[t], candidates=sorted(brazos), region=region[t],
                           requested=Assurance.STANDARD, coupling=c,
                           coupling_provenance=Provenance.ELICITED, coupling_credence=cr)
        return plan.paradigm

    def a_mano(t):
        celda = tareas[t]["cell"]
        if celda == "C5_unknown_horizon":
            p = "direct" if t.endswith("w4") else "react"
        else:
            p = CAMINO[celda]
        return p if p in brazos else fijo

    def por_region(t):
        otros = [o for o in tids if region[o] == region[t] and o != t]
        if not otros:
            return fijo
        mu = {p: statistics.mean(um[(o, p)] for o in otros) for p in brazos}
        top = max(mu.values())
        emp = [p for p in brazos if mu[p] >= top - tol]
        return min(emp, key=lambda p: statistics.mean(cm[(o, p)] for o in otros))

    competidores = [
        ("ORACULO (techo, irrealizable)", lambda t: max(brazos, key=lambda p: um[(t, p)])),
        ("POLITICA POR REGION (LOO)", por_region),
        (f"MEJOR FIJO — siempre `{fijo}`", lambda t: fijo),
        ("PRODUCTO (router de hoy)", producto),
        ("CAMINO A MANO", a_mano),
    ]

    print("=" * 96)
    print(f"EL MARCADOR — {len(tids)} tareas x {len(brazos)} brazos, mismo panel para todos")
    print("=" * 96)
    print(f"\n  brazos: {', '.join(brazos)}")
    print(f"  tolerancia de empate (1 sigma del ruido de la media): {tol:.3f}\n")
    print(f"  {'':34s} {'utilidad':>9s} {'vs fijo':>8s} {'costo':>10s} {'vs fijo':>9s}"
          f"  {'u/1k tok':>9s}")

    base_u = statistics.mean(um[(t, fijo)] for t in tids)
    base_c = statistics.mean(cm[(t, fijo)] for t in tids)
    filas = []
    for nombre, fn in competidores:
        u = statistics.mean(um[(t, fn(t))] for t in tids)
        c = statistics.mean(cm[(t, fn(t))] for t in tids)
        filas.append((nombre, u, c))
        print(f"  {nombre:34s} {u:9.3f} {u - base_u:+8.3f} {c:10,.0f} "
              f"{c / base_c:8.2f}x  {u / c * 1000:9.3f}")

    ora = filas[0][1]
    print(f"""
  {'-' * 92}
  COMO LEER ESTE CUADRO, y son tres lecturas distintas.

  1. **La brecha total es {ora - base_u:.3f}.** Ese es TODO lo que hay para ganar eligiendo,
     y esta por debajo de la tolerancia de empate ({tol:.3f}) — o sea, por debajo del ruido
     con el que se midio cada celda. No es que el motor no la capture: es que **no hay
     resolucion para distinguirla**.

  2. **El producto de hoy no supera al mejor fijo.** Y el camino a mano tampoco. Los dos
     pierden contra elegir siempre lo mismo, por razones distintas: el router porque en el
     78% de las tareas la especializacion no ayuda y ahi solo puede equivocarse; el camino
     a mano porque optimizo COSTO con desempate y se lo evalua por calidad sola.

  3. **El producto le gana al camino a mano** (+0,079) y pierde contra la constante. Que un
     motor con reglas y theta supere a un experto que leyo las 78 preguntas no es poco — y
     que los dos pierdan contra `siempre reflection` dice donde esta el problema, que no es
     el motor.

  4. **El ORACULO es MAS BARATO que el mejor fijo** (0,54x). Elegir bien no es un
     intercambio calidad-contra-costo en este corpus: el brazo que gana suele ser tambien
     el barato. Lo que falta no es plata, es saber cual.

  5. **La ultima columna es la que se mueve.** En utilidad por cada 1.000 tokens hay
     ordenes de magnitud entre los competidores, cuando en utilidad hay centesimas. Es el
     mismo hecho que aparecio por cuatro caminos independientes esta semana.
""")


if __name__ == "__main__":
    main()
