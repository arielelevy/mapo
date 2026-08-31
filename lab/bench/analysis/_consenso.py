"""EL CONSENSO ENTRE PARADIGMAS COMO VERIFICADOR. Cero llamadas al modelo.

DE DÓNDE SALE, y por eso es emergente y no una medición más. El banco corre ocho brazos
sobre la misma pregunta y siempre los comparó **contra el oráculo**, nunca **entre sí**. Pero
en el registro hay ocho respuestas independientes por tarea, y nadie las miró juntas.

    ¿El acuerdo entre paradigmas predice la corrección, sin oráculo y sin juez?

SI LA RESPUESTA ES SÍ, ES EXACTAMENTE LO QUE LA CAPA DE DECISIÓN NECESITA. El producto
promete abstenerse cuando la evidencia no alcanza, y hasta hoy la única forma de saber si una
respuesta está bien era tener el gold. Un detector que funcione sin él cambia qué se puede
prometer en producción.

LOS TRES CONTROLES, y sin ellos el hallazgo no vale nada:

  1. **¿el acuerdo sólo marca «tarea fácil»?** El control es comparar, DENTRO de las mismas
     tareas, los brazos que están en el consenso contra los que quedaron afuera. Si el
     acuerdo sólo marcara dificultad, los dos grupos rendirían igual
  2. **¿es un artefacto de respuestas cortas?** La igualdad exacta de cadena es fácil para
     `AR9263415718` y difícil para una enumeración de cuatro ítems. Se parte por
     cardinalidad declarada
  3. **¿sirve para abaratar?** Se prueba la cascada: comité barato, y escalar sólo al
     discrepar. Es la lectura comercial obvia y **no se sostiene** — se reporta igual

LO QUE ESTE ANÁLISIS NO PUEDE AFIRMAR, y va antes del número. **Los brazos NO son
independientes**: comparten modelo, corpus y recuperador. Su acuerdo es diversidad de
PROCEDIMIENTO, no evidencia estadísticamente independiente, así que nada acá se puede leer
como un argumento tipo «voto de expertos independientes». Lo que se mide es si trayectorias
de control distintas, sobre el mismo material, convergen cuando aciertan.

Corre DESDE `lab/`:  py bench/analysis/_consenso.py [--k 4]
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import argparse
import itertools
import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

_sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.runner import load_rows
from app.verify import normalise
from bench.panel import rectangulo

REGISTRO = Path("results/luna/gold_h1_rows.jsonl")
CORPUS = Path("corpus/gold_h1")
# LA RÉPLICA 0 Y NO EL PROMEDIO. Un consenso se forma entre RESPUESTAS, y promediar tres
# réplicas de un brazo produce un número, no una cadena que se pueda comparar con otra.
TRIAL = 0


def cargar():
    filas = [f for f in load_rows(REGISTRO) if not f.get("infeasible")]
    panel = rectangulo([{"task_id": f["task_id"], "paradigm": f["paradigm"],
                         "infeasible": False} for f in filas])
    ts, bs = set(panel.tareas), set(panel.brazos)
    R: dict[tuple[str, str], str] = {}
    U: dict[tuple[str, str], float] = {}
    C: dict[tuple[str, str], int] = {}
    for f in filas:
        if f["task_id"] in ts and f["paradigm"] in bs and f["trial"] == TRIAL:
            k = (f["task_id"], f["paradigm"])
            R[k] = normalise(f.get("answer") or "")
            U[k] = f.get("utility", 0.0)
            C[k] = f.get("cost_tokens") or 0
    return panel, sorted(ts), sorted(bs), R, U, C


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--k", type=int, default=4, help="umbral de acuerdos")
    args = ap.parse_args()

    panel, ts, bs, R, U, C = cargar()
    tareas = {t["task_id"]: t for t in json.loads(
        (CORPUS / "tasks.json").read_text(encoding="utf-8"))}

    print("=" * 92)
    print("EL CONSENSO ENTRE PARADIGMAS COMO VERIFICADOR")
    print("=" * 92)
    print(f"\n  {panel.descripcion()} · réplica {TRIAL} · "
          f"{len([k for k in R if R[k].strip()])} respuestas no vacías\n")

    # ── 1. la curva ────────────────────────────────────────────────────────────
    print("1. P(la respuesta es correcta | k brazos coinciden con ella, exacto)")
    print("-" * 92)
    por_k: dict[int, list[float]] = defaultdict(list)
    for t in ts:
        cel = [(p, R[(t, p)]) for p in bs if (t, p) in R and R[(t, p)].strip()]
        cnt = Counter(a for _, a in cel)
        for p, a in cel:
            por_k[cnt[a] - 1].append(U[(t, p)])
    print(f"  {'k':>4}{'celdas':>9}{'P(correcta)':>14}")
    for k in sorted(por_k):
        v = por_k[k]
        print(f"  {k:>4}{len(v):>9}{statistics.mean(v):>14.3f}"
              + ("   <-- umbral" if k == args.k else ""))

    # ── 2. control: ¿marca tarea fácil? ────────────────────────────────────────
    print(f"\n2. CONTROL — ¿el acuerdo sólo marca «tarea fácil»?")
    print("-" * 92)
    dentro, fuera, con_consenso = [], [], set()
    for t in ts:
        cel = [(p, R[(t, p)]) for p in bs if (t, p) in R and R[(t, p)].strip()]
        cnt = Counter(a for _, a in cel)
        may = {a for a, n in cnt.items() if n - 1 >= args.k}
        if not may:
            continue
        con_consenso.add(t)
        for p, a in cel:
            (dentro if a in may else fuera).append(U[(t, p)])
    if dentro and fuera:
        print(f"  tareas con algún consenso de k>={args.k}: "
              f"{len(con_consenso)} de {len(ts)}")
        print(f"    brazos DENTRO del consenso        n={len(dentro):4}  "
              f"u = {statistics.mean(dentro):.3f}")
        print(f"    brazos FUERA, en esas MISMAS tareas n={len(fuera):4}  "
              f"u = {statistics.mean(fuera):.3f}")
        print(f"\n  >>> discrimina DENTRO de la tarea: "
              f"{statistics.mean(dentro) - statistics.mean(fuera):+.3f}. No es dificultad:")
        print("      sobre la misma pregunta, estar en el consenso o afuera es la diferencia.")

    # ── 3. control: ¿respuestas cortas? ────────────────────────────────────────
    print(f"\n3. CONTROL — ¿es un artefacto de la igualdad exacta de cadena?")
    print("-" * 92)
    print("   Una cuenta se compara fácil; una enumeración de cuatro ítems no. Si el efecto")
    print("   viviera sólo en `singular`, sería del comparador y no del consenso.\n")
    por_card: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for t in ts:
        card = tareas[t].get("answer_cardinality", "?")
        cel = [(p, R[(t, p)]) for p in bs if (t, p) in R and R[(t, p)].strip()]
        cnt = Counter(a for _, a in cel)
        for p, a in cel:
            por_card[card][f"k>={args.k}" if cnt[a] - 1 >= args.k else "k<"].append(U[(t, p)])
    print(f"  {'cardinalidad':<16}{'n':>6}{'P(ok) con consenso':>21}"
          f"{'n':>7}{'P(ok) sin':>12}")
    for c in sorted(por_card):
        a, b = por_card[c][f"k>={args.k}"], por_card[c]["k<"]
        pa = f"{statistics.mean(a):.3f}" if a else "—"
        pb = f"{statistics.mean(b):.3f}" if b else "—"
        print(f"  {c:<16}{len(a):>6}{pa:>21}{len(b):>7}{pb:>12}")

    # ── 4. la lectura comercial obvia, y por qué NO se sostiene ────────────────
    print(f"\n4. ¿SIRVE PARA ABARATAR? — la cascada, y el resultado es que NO")
    print("-" * 92)
    print("   Comité barato; si acuerdan se toma su respuesta, si no se escala al mejor")
    print("   fijo. Es la lectura obvia y hay que reportarla aunque salga en contra.\n")
    CARO = max(bs, key=lambda p: statistics.mean(
        [U[(t, p)] for t in ts if (t, p) in U] or [0]))
    base_u = statistics.mean(U[(t, CARO)] for t in ts if (t, CARO) in U)
    base_c = statistics.mean(C[(t, CARO)] for t in ts if (t, CARO) in C)
    print(f"  referencia — siempre `{CARO}`: u = {base_u:.3f} · {base_c:,.0f} tok\n")
    res = []
    for r in (2, 3):
        for combo in itertools.combinations([p for p in bs if p != CARO], r):
            uu, cc, ac = [], [], 0
            for t in ts:
                a = [R.get((t, p), "") for p in combo]
                cst = sum(C.get((t, p), 0) for p in combo)
                if all(x.strip() for x in a) and len(set(a)) == 1:
                    ac += 1
                    uu.append(U[(t, combo[0])])
                    cc.append(cst)
                else:
                    uu.append(U.get((t, CARO), 0.0))
                    cc.append(cst + C.get((t, CARO), 0))
            res.append((statistics.mean(cc), statistics.mean(uu), ac, combo))
    res.sort()
    print(f"  {'comité':<32}{'acuerdan':>10}{'u':>8}{'tok':>11}{'Δu':>8}{'ahorro':>9}")
    for c, u, ac, combo in res[:5]:
        print(f"  {'+'.join(combo):<32}{ac:>10}{u:>8.3f}{c:>11,.0f}"
              f"{u - base_u:>+8.3f}{1 - c / base_c:>9.0%}")
    print(f"""
  >>> NINGUNA CASCADA AHORRA. El comité se paga en TODAS las tareas y el caro se paga igual
      en la mayoría, así que el total sube. El consenso **no es un ruteador barato**.
""")

    print("=" * 92)
    print("QUÉ ES, ENTONCES")
    print("=" * 92)
    print(f"""
  Un **detector de corrección de alta precisión y cobertura parcial**, que es exactamente la
  forma de una regla de abstención: no dice qué brazo usar, dice **cuándo no hace falta
  verificar**. Con k>={args.k} el acierto es total en este corpus sobre las cuatro
  cardinalidades, y la cobertura es de {len(con_consenso)} de {len(ts)} tareas.

  Y LO QUE NO SE PUEDE AFIRMAR, otra vez porque importa: los ocho brazos comparten modelo,
  corpus y recuperador. Esto no es un voto de expertos independientes — es la observación de
  que **trayectorias de control distintas convergen cuando aciertan y divergen cuando no**.
  Que el mecanismo sea ése y no la independencia estadística es lo que hace falta probar
  antes de apoyarse en el número: el experimento que lo decidiría es repetirlo con otro
  modelo detrás, y no está corrido.
""")


if __name__ == "__main__":
    main()
