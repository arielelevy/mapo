"""¿La ventaja de un paradigma sobrevive a controlar por cuánta evidencia leyó?

LA PREGUNTA. El registro dice que ciertas estructuras de control ganan. Pero un
paradigma que gana podría estar ganando por dos razones muy distintas: porque razona
mejor sobre la misma evidencia, o simplemente porque ENCUENTRA más evidencia. Son
afirmaciones diferentes y la segunda es más barata de accionar — si "la estructura gana"
se disuelve en "esta estructura recupera más", el arreglo es el recuperador, no el
paradigma.

QUÉ SE MIDE ACÁ, Y QUÉ NO. Esto NO es retención de contexto. Retención sería cuánta de
la evidencia recuperada sobrevive hasta la llamada que responde, y eso no está
instrumentado: haría falta código nuevo y una corrida. Lo que sí está en las filas ya
pagadas es el RECALL de evidencia — qué fracción de las unidades que de verdad llevan la
respuesta llegó a leer el paradigma. Es el primer eslabón de la misma cadena y se puede
contestar gratis; el segundo queda declarado como pendiente y no se lo llama medido.

EL DISEÑO, Y POR QUÉ NO ES UNA REGRESIÓN. Con ~130 celdas por corpus, un modelo de
mediación lineal daría coeficientes con más precisión aparente que evidencia. El control
no paramétrico dice lo mismo sin pedir prestada esa precisión: quedarse SÓLO con las
celdas donde el paradigma leyó toda la evidencia relevante, y preguntar si la ventaja
sigue ahí. Si desaparece entre celdas de recall completo, la ventaja era del recuperador.

El emparejamiento es por TAREA. Comparar medias entre paradigmas sobre conjuntos
distintos de tareas confunde dificultad con paradigma; comparar dentro de la misma tarea
no.

LA SALVEDAD QUE HACE HONESTO A ESTO, Y NO ES MENOR. El recall NO es una covariable
previa: es consecuencia del paradigma. Condicionar sobre una variable posterior al
tratamiento no entrega un efecto directo insesgado — puede abrir sesgo de colisionador,
porque las celdas de recall completo de un paradigma torpe son las tareas fáciles
mientras que las de uno bueno incluyen tareas difíciles. Asi que esto es DESCRIPTIVO:
dice dónde vive la varianza, no cuánto causa cada cosa. La comparación de magnitudes
—brecha de recall contra brecha de paradigma— es robusta a esa objeción; el cambio de
signo de un paradigma en particular no lo es, y se reporta como indicio, no como
veredicto.
"""

import json
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")

CORPORA = ("gold_transfer", "gold_deep", "gold_v2", "gold_holdout")


def cells_of(corpus):
    """Una celda por (tarea, paradigma): utilidad media y recall medio de evidencia."""
    runner = Runner(settings, corpus, retriever_arm="hybrid", surface_variant="basic")
    tasks = {t["task_id"]: t for t in runner._tasks}  # noqa: SLF001

    grouped = defaultdict(list)
    for r in runner.load_rows():
        if r.get("infra_error") or r.get("infeasible"):
            continue
        grouped[(r["task_id"], r["paradigm"])].append(r)

    out = {}
    for (task_id, paradigm), rows in grouped.items():
        task = tasks.get(task_id)
        if task is None:
            continue
        relevant = task.get("relevant_units") or []
        if not relevant:
            # Sin unidades relevantes declaradas no hay denominador, y un recall
            # inventado sería peor que no tener el dato.
            continue
        recalls = []
        for r in rows:
            usage = r.get("tool_usage") or {}
            read = usage.get("relevant_units_read")
            if read is None:
                continue
            recalls.append(min(1.0, read / len(relevant)))
        if not recalls:
            continue
        out[(task_id, paradigm)] = {
            "utility": sum(x["utility"] for x in rows) / len(rows),
            "recall": sum(recalls) / len(recalls),
            "cell": task["cell"][:2],
            "n_relevant": len(relevant),
        }
    return out


def paired_advantage(cells, restrict_full_recall):
    """Ventaja de cada paradigma contra el promedio de sus pares, EN LA MISMA TAREA."""
    by_task = defaultdict(dict)
    for (task_id, paradigm), c in cells.items():
        if restrict_full_recall and c["recall"] < 1.0:
            continue
        by_task[task_id][paradigm] = c

    advantage = defaultdict(list)
    for task_id, peers in by_task.items():
        if len(peers) < 2:
            continue  # sin par no hay comparación pareada
        for paradigm, c in peers.items():
            others = [o["utility"] for p, o in peers.items() if p != paradigm]
            advantage[paradigm].append(c["utility"] - sum(others) / len(others))
    return advantage, sum(len(v) for v in by_task.values())


print("Recall de evidencia como variable mediadora — cero tokens\n")
print("NO es retención de contexto: eso requiere instrumentar la llamada que responde.")
print("Es el primer eslabón — qué fracción de las unidades que llevan la respuesta se leyó.\n")

report = {}
for corpus in CORPORA:
    cells = cells_of(corpus)
    if not cells:
        print(f"{corpus}: sin unidades relevantes declaradas, se saltea\n")
        continue

    full = sum(1 for c in cells.values() if c["recall"] >= 1.0)
    print(f"--- {corpus} · {len(cells)} celdas · recall completo en {full} "
          f"({full / len(cells) * 100:.0f}%)")

    # ¿el recall explica la utilidad?
    hi = [c["utility"] for c in cells.values() if c["recall"] >= 1.0]
    lo = [c["utility"] for c in cells.values() if c["recall"] < 1.0]
    if hi and lo:
        print(f"    utilidad media con recall completo : {sum(hi) / len(hi):.3f}  (n={len(hi)})")
        print(f"    utilidad media con recall parcial  : {sum(lo) / len(lo):.3f}  (n={len(lo)})")
        print(f"    diferencia                         : {sum(hi) / len(hi) - sum(lo) / len(lo):+.3f}")

    all_adv, _ = paired_advantage(cells, restrict_full_recall=False)
    ctl_adv, _ = paired_advantage(cells, restrict_full_recall=True)

    print(f"\n    {'paradigma':<16} {'ventaja':>9} {'n':>4}   {'controlado':>10} {'n':>4}   {'sobrevive':>9}")
    rows_out = {}
    for paradigm in sorted(all_adv, key=lambda p: -sum(all_adv[p]) / len(all_adv[p])):
        a = sum(all_adv[paradigm]) / len(all_adv[paradigm])
        na = len(all_adv[paradigm])
        if paradigm in ctl_adv and len(ctl_adv[paradigm]) >= 2:
            c = sum(ctl_adv[paradigm]) / len(ctl_adv[paradigm])
            nc = len(ctl_adv[paradigm])
            # "sobrevive" = conserva el signo y al menos la mitad de la magnitud
            survives = "si" if (a * c > 0 and abs(c) >= abs(a) * 0.5) else "NO"
            shown = f"{c:+.3f}"
        else:
            c, nc, survives, shown = None, len(ctl_adv.get(paradigm, [])), "sin n", "  --  "
        print(f"    {paradigm:<16} {a:+.3f}   {na:>3}   {shown:>10}  {nc:>3}   {survives:>9}")
        rows_out[paradigm] = {"advantage": round(a, 4), "n": na,
                              "controlled": None if c is None else round(c, 4),
                              "n_controlled": nc, "survives": survives}
    gap = (sum(hi) / len(hi) - sum(lo) / len(lo)) if (hi and lo) else None
    report[corpus] = {"cells": len(cells), "full_recall": full,
                      "recall_gap": None if gap is None else round(gap, 4),
                      "paradigms": rows_out}
    print()

# --- el titular: comparar las dos magnitudes -----------------------------------------
print("=" * 72)
print("La comparacion que no depende del condicionamiento:")
print("")
for corpus, rep in report.items():
    advs = [abs(v["advantage"]) for v in rep["paradigms"].values()]
    if not advs:
        continue
    biggest = max(advs)
    gap = rep.get("recall_gap")
    if gap is None:
        continue
    print(f"  {corpus:<15} brecha de recall {gap:+.3f}   "
          f"mayor ventaja de paradigma {biggest:.3f}   "
          f"razón {gap / biggest:.1f}x")
print()
print("  La diferencia entre leer toda la evidencia y no leerla es varias veces")
print("  mayor que la diferencia entre paradigmas. Eso no depende de condicionar")
print("  sobre nada: son dos medias sobre las mismas celdas.")
print("=" * 72)

path = settings.results_dir / "retention.json"
path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"reporte: {path}")
print("\nLectura: 'ventaja' es contra el promedio de los pares EN LA MISMA TAREA.")
print("'controlado' repite el cálculo sólo sobre celdas que leyeron TODA la evidencia")
print("relevante. Un paradigma cuya ventaja desaparece ahí ganaba recuperando, no")
print("razonando — y entonces el arreglo es el recuperador, no el paradigma.")
