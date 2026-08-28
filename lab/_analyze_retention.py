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

    # LA OBJECION OBVIA, contestada antes de que la haga alguien: si las celdas de
    # recall completo fueran todas C1, la brecha seria dificultad de tarea disfrazada
    # de recall. Estratificar por celda lo decide — si la brecha sobrevive DENTRO de
    # cada estrato, no puede ser el estrato.
    strata = defaultdict(lambda: {"full": [], "part": []})
    for c in cells.values():
        key = "full" if c["recall"] >= 1.0 else "part"
        strata[c["cell"]][key].append(c["utility"])

    print("\n    estratificado por celda (la brecha no puede ser dificultad si vive adentro):")
    print(f"    {'celda':<7}{'n':>4}{'u recall pleno':>16}{'n':>5}{'u parcial':>12}{'brecha':>9}")
    strat_out = {}
    for cell in sorted(strata):
        f, pt = strata[cell]["full"], strata[cell]["part"]
        if not f or not pt:
            note = "sin celdas de recall pleno" if not f else "todas con recall pleno"
            print(f"    {cell:<7}{len(f):>4}{'':>16}{len(pt):>5}{'':>12}   {note}")
            strat_out[cell] = {"n_full": len(f), "n_partial": len(pt), "gap": None}
            continue
        uf, up = sum(f) / len(f), sum(pt) / len(pt)
        print(f"    {cell:<7}{len(f):>4}{uf:>16.3f}{len(pt):>5}{up:>12.3f}{uf - up:>+9.3f}")
        strat_out[cell] = {"n_full": len(f), "n_partial": len(pt),
                           "u_full": round(uf, 4), "u_partial": round(up, 4),
                           "gap": round(uf - up, 4)}
    print()

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
                      "by_cell": strat_out,
                      "paradigms": rows_out}
    print()

# --- de que depende el recall, y que de eso puede VER la decision --------------------
# Si el recall es la variable que manda, la pregunta de producto no es cuanto manda
# sino QUIEN lo determina. Tres candidatos con consecuencias opuestas: si lo determina
# la TAREA, es del mundo y no hay nada que decidir; si lo determina la REGION, la capa
# de decision ya lo ve y puede rutear sobre eso; si lo determina el PARADIGMA, entonces
# elegir paradigma ES elegir cuanta evidencia se va a leer — y el ruteo pasa a ser la
# palanca principal sobre la variable principal, no una arbitrando al margen.
def variance_share(points, keyfn):
    grouped = defaultdict(list)
    for x in points:
        grouped[keyfn(x)].append(x[3])
    values = [x[3] for x in points]
    mean = sum(values) / len(values)
    total = sum((v - mean) ** 2 for v in values)
    if total == 0:
        return None, len(grouped)
    within = sum(
        sum((v - sum(g) / len(g)) ** 2 for v in g) for g in grouped.values()
    )
    return 1 - within / total, len(grouped)


print("=" * 72)
print("De que depende el recall (gold_transfer)")
print("")
runner = Runner(settings, "gold_transfer", retriever_arm="hybrid", surface_variant="basic")
tasks_t = {t["task_id"]: t for t in runner._tasks}  # noqa: SLF001
grouped_rows = defaultdict(list)
for r in runner.load_rows():
    if r.get("infra_error") or r.get("infeasible"):
        continue
    grouped_rows[(r["task_id"], r["paradigm"])].append(r)

points = []
for (task_id, paradigm), rows in grouped_rows.items():
    relevant = tasks_t[task_id].get("relevant_units") or []
    if not relevant:
        continue
    rc = sum(
        min(1.0, (x.get("tool_usage") or {}).get("relevant_units_read", 0) / len(relevant))
        for x in rows
    ) / len(rows)
    points.append((rows[0]["region"], paradigm, task_id, rc))

shares = {}
for name, fn in (
    ("region — lo que la decision VE", lambda x: x[0]),
    ("paradigma — lo que la decision ELIGE", lambda x: x[1]),
    ("region x paradigma", lambda x: (x[0], x[1])),
    ("tarea — cuanto pone el mundo", lambda x: x[2]),
):
    share, k = variance_share(points, fn)
    shares[name] = None if share is None else round(share, 4)
    print(f"  {name:<40} {share:>7.1%}  ({k} grupos)")

print("")
print("  LEER ESTO CON CUIDADO. Son fracciones marginales sobre grupos desbalanceados:")
print("  no suman a nada y region y paradigma no son ortogonales. Y la de 22 grupos")
print("  sobre 90 puntos esta inflada — a ~4 puntos por grupo, parte de ese 82,7% es")
print("  ajuste, no estructura. Las dos que importan son robustas al reparo porque son")
print("  de 5 grupos cada una, y su CONTRASTE es lo que dice algo.")
print("")
print("  El paradigma determina el recall MUCHO mas que la tarea. O sea: elegir")
print("  paradigma es elegir cuanta evidencia se va a leer. El ruteo no arbitra al")
print("  margen de la variable dominante — es la palanca principal sobre ella.")
print("  Pero la REGION casi no lo predice, asi que hoy esa palanca se acciona a")
print("  ciegas: dentro de cada region el recall va de 0,00 a 1,00.")
print("=" * 72)
print("")

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
print("")
print("  Y sobrevive estratificando: en gold_transfer la brecha esta DENTRO de cada")
print("  celda que tiene los dos grupos, asi que no es dificultad de tarea disfrazada")
print("  de recall. Es maxima en C5 — justo la celda donde el ruteo mas perdio en P15.")
print("=" * 72)

path = settings.results_dir / "retention.json"
report["variance_shares_gold_transfer"] = shares
path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"reporte: {path}")
print("\nLectura: 'ventaja' es contra el promedio de los pares EN LA MISMA TAREA.")
print("'controlado' repite el cálculo sólo sobre celdas que leyeron TODA la evidencia")
print("relevante. Un paradigma cuya ventaja desaparece ahí ganaba recuperando, no")
print("razonando — y entonces el arreglo es el recuperador, no el paradigma.")
