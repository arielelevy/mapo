"""EP-5: la regla que `literal_absent` habilita, medida antes de adoptarse. Cero llamadas.

LA REGLA PROPUESTA. Si el literal que la pregunta cita no aparece en NINGUNA unidad del
alcance, la respuesta es una **ausencia**, y una ausencia la establece una búsqueda léxica
vacía a costo cero — no hace falta el brazo caro.

POR QUÉ VALE LA PENA MIRARLA. Medido en `B2_absence`: gana `handoff` con `u = 0,92`
**leyendo 19 unidades**. Es la respuesta cara a una pregunta que tiene una respuesta
aritmética, y el contrato `C-ABSENCE` ya demostró que el camino caro es directamente
**insatisfacible** ahí (9 de 9 tareas: el dominio entero no entra en el presupuesto).

EL ORDEN, y no es negociable: **primero se valida el SENSOR, después se mide la REGLA.**
Una regla construida sobre un sensor que no identifica lo que dice identificar mide su
propio error, y con suerte da un número lindo.

  1. ¿`lit_absent` marca las tareas cuya respuesta es realmente una ausencia? Se contrasta
     contra el oráculo del corpus —una tarea es de ausencia cuando no tiene unidades
     relevantes— que es información que el sensor NO ve.
  2. Sólo si el sensor discrimina, se mide qué compra la regla contra el mejor fijo.

Corre DESDE `lab/`:  py bench/analysis/_regla_ausencia.py
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

from app.features import measure_question_literal
from app.paradigms import campaign_roster
from app.runner import load_rows

CONTAMINADAS = {"b2-000-w4", "b2-001-w16", "b2-002-w16", "c3-000-h1", "c2-001-w4"}


def main() -> None:
    docs = json.loads(_Path("corpus/gold_h1/documents.json").read_text(encoding="utf-8"))
    tareas = {t["task_id"]: t for t in json.loads(
        _Path("corpus/gold_h1/tasks.json").read_text(encoding="utf-8"))}
    roster = list(campaign_roster())

    U, C = collections.defaultdict(list), collections.defaultdict(list)
    for f in load_rows(_Path("results/luna/gold_h1_rows.jsonl")):
        if not f.get("infeasible"):
            U[(f["task_id"], f["paradigm"])].append(f["utility"])
            C[(f["task_id"], f["paradigm"])].append(f.get("cost_tokens") or 0)

    medidas = {t for t, _ in U}
    tids = [t for t in tareas if t not in CONTAMINADAS and t in medidas]
    brazos = [p for p in roster if sum((t, p) in U for t in tids) >= 0.95 * len(tids)]
    tids = [t for t in tids if all((t, p) in U for p in brazos)]
    um = {(t, p): statistics.mean(U[(t, p)]) for t in tids for p in brazos}
    cm = {(t, p): statistics.mean(C[(t, p)]) for t in tids for p in brazos}

    lit = {t: measure_question_literal(
        tareas[t]["question"], docs, tareas[t]["unit_ids"],
        cardinality=tareas[t].get("answer_cardinality")) for t in tids}
    # LA VERDAD QUE EL SENSOR NO VE: una tarea es de ausencia cuando el gold no tiene
    # unidades relevantes. Es el oraculo del corpus, no una feature.
    ausencia = {t: len(tareas[t]["relevant_units"]) == 0 for t in tids}

    print("=" * 96)
    print("1. ¿EL SENSOR DISCRIMINA? — `lit_absent` contra la verdad del corpus")
    print("=" * 96)
    tabla = collections.Counter((lit[t], ausencia[t]) for t in tids)
    valores = sorted({lit[t] for t in tids})
    print(f"\n  {'valor del sensor':18s} {'es ausencia':>12s} {'no lo es':>10s} "
          f"{'precision':>10s}")
    for v in valores:
        si = tabla[(v, True)]
        no = tabla[(v, False)]
        prec = si / (si + no) if (si + no) else 0.0
        print(f"  {str(v):18s} {si:12d} {no:10d} {prec:10.0%}")

    tp = tabla[("lit_absent", True)]
    fp = tabla[("lit_absent", False)]
    fn = sum(1 for t in tids if ausencia[t] and lit[t] != "lit_absent")
    base = sum(1 for t in tids if ausencia[t])
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / base if base else 0.0
    print(f"\n  como detector de ausencia: precision {prec:.0%} · recall {rec:.0%} "
          f"({tp} de {base} ausencias, {fp} falsos positivos)")
    print(f"  prevalencia de ausencia en el panel: {base}/{len(tids)} = "
          f"{base/len(tids):.0%}")

    if tp == 0:
        print("\n  >>> EL SENSOR NO DETECTA NINGUNA AUSENCIA EN ESTE PANEL. La regla no se "
              "puede\n      medir aca, y proponerla igual seria proponerla a ciegas.")
        return

    # ── 2. QUE COMPRARIA LA REGLA ────────────────────────────────────────────
    print("\n" + "=" * 96)
    print("2. ¿QUE COMPRA LA REGLA? — contrafactual sobre el registro")
    print("=" * 96)
    fijo = max(brazos, key=lambda p: statistics.mean(um[(t, p)] for t in tids))
    barato = min(brazos, key=lambda p: statistics.mean(cm[(t, p)] for t in tids))
    print(f"""
  La regla: si `lit_absent`, rutear al mas barato ({barato}); si no, al mejor fijo
  ({fijo}). Es la forma minima — no elige entre brazos, solo reconoce que hay una
  pregunta cuya respuesta no exige leer.
""")

    def politica(t):
        return barato if lit[t] == "lit_absent" else fijo

    u_fijo = statistics.mean(um[(t, fijo)] for t in tids)
    c_fijo = statistics.mean(cm[(t, fijo)] for t in tids)
    u_pol = statistics.mean(um[(t, politica(t))] for t in tids)
    c_pol = statistics.mean(cm[(t, politica(t))] for t in tids)

    print(f"  {'':28s} {'utilidad':>9s} {'costo':>10s}")
    print(f"  {'mejor fijo `' + fijo + '`':28s} {u_fijo:9.3f} {c_fijo:10,.0f}")
    print(f"  {'con la regla':28s} {u_pol:9.3f} {c_pol:10,.0f}")
    print(f"  {'':28s} {u_pol - u_fijo:+9.3f} {1 - c_pol / c_fijo:9.0%} de ahorro")

    # SOLO EN LAS TAREAS QUE LA REGLA TOCA, que es donde se juega.
    tocadas = [t for t in tids if lit[t] == "lit_absent"]
    if tocadas:
        uf = statistics.mean(um[(t, fijo)] for t in tocadas)
        up = statistics.mean(um[(t, barato)] for t in tocadas)
        cf = statistics.mean(cm[(t, fijo)] for t in tocadas)
        cp = statistics.mean(cm[(t, barato)] for t in tocadas)
        print(f"\n  y SOLO en las {len(tocadas)} tareas que la regla toca:")
        print(f"    {fijo:16s} u={uf:.3f}  {cf:>9,.0f} tok")
        print(f"    {barato:16s} u={up:.3f}  {cp:>9,.0f} tok")
        print(f"    {'':16s}   {up - uf:+.3f}  {1 - cp / max(cf, 1):.0%} de ahorro")

    print(f"""
  {'-' * 92}
  COMO DECIDIR CON ESTO. La regla se adopta si en las tareas que TOCA no pierde utilidad
  fuera del ruido y ahorra de verdad. Si pierde utilidad, lo que dice es que reconocer la
  ausencia no alcanza: hay que contestarla, y contestarla bien cuesta.
""")


if __name__ == "__main__":
    main()
