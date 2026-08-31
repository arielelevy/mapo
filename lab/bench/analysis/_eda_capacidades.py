"""¿Las CAPACIDADES predicen mejor que la identidad del paradigma? — la prueba que faltaba.

LA CADENA QUE SE PONE A PRUEBA:

    ontología de la pregunta  →  capacidades que EXIGE  →  brazos que las tienen  →  utilidad

`P15` se refutó saltándose el eslabón del medio: mapeó ontología → **nombre de paradigma** y
perdió `−0,087`. `app/capacidades.py` propone el eslabón, y afirma algo fuerte que **hasta hoy
nadie midió**: que las capacidades «predicen sobre brazos que nunca se corrieron». Eso está
escrito como tesis desde que existe el espacio de capacidades, y es exactamente la clase de
afirmación que se puede falsar.

LA PRUEBA DECISIVA ES **DEJAR UN BRAZO AFUERA**, no una tarea. Y la asimetría es el punto:

  · un modelo con la IDENTIDAD del paradigma no puede decir NADA de un brazo que no vio —
    no tiene parámetro para él. Es su límite estructural, no un problema de ajuste
  · un modelo con CAPACIDADES sí puede: el brazo nuevo trae su vector declarado desde el
    código, y el modelo ya aprendió cuánto vale cada capacidad en cada eje de pregunta

Si las capacidades son la abstracción correcta, predecir un brazo no visto tiene que salir
**mejor que la media global**. Si no, la tabla de capacidades es vocabulario y no mecanismo.

LOS TRES COMPETIDORES, y ninguno ve al brazo dejado afuera:

    media_global       una constante. El piso: cualquier cosa que no le gane, no sabe nada
    dificultad_tarea   la media de la tarea sobre los otros brazos. Fuerte y honesto: captura
                       α, que es el 41% de la varianza, sin saber nada del brazo
    capacidades        dificultad de la tarea + lo que aportan las capacidades del brazo,
                       aprendido sobre los OTROS siete

Y un cuarto que **ve al brazo dejado afuera**: `identidad_del_brazo`, la media real de ese
brazo. Lo puse creyendo que sería un techo y **no lo es** — sale 0,339 contra 0,233 de
capacidades, o sea PEOR pese a hacer trampa. La razón es que ignora α, la dificultad de la
tarea, que es el 41% de la varianza: saber qué brazo es, sin saber qué pregunta es, predice
mal. Se conserva porque ese fracaso es el argumento: **la identidad del paradigma no es una
buena representación ni cuando se la deja hacer trampa.**

LO QUE ESTE ANÁLISIS NO PUEDE DECIR. Las capacidades están DECLARADAS por mí leyendo el
código, y ocho brazos son ocho puntos: si el resultado es positivo, es evidencia de que la
abstracción sirve en este corpus, no de que la tabla esté completa. `EXIGE` ya tiene un
contraejemplo escrito (`dag_strategy` gana C3 sin las capacidades que C3 declara exigir).

Corre DESDE `lab/`:  py bench/analysis/_eda_capacidades.py
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

_sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.capacidades import EXIGE, NOMBRES, TIENE
from app.features import entidad_en
from app.runner import load_rows
from bench.panel import rectangulo

REGISTRO = Path("results/luna/gold_h1_rows.jsonl")
CORPUS = Path("corpus/gold_h1")


def ejes_de(t: dict) -> set[str]:
    """Los ejes de ontología que esta pregunta activa. Determinista, desde los campos.

    Se deriva de lo que el corpus DECLARA por tarea —cardinalidad, cobertura, acoplamiento,
    presupuesto— y no del nombre de la celda, salvo donde la celda ES el eje. Una celda es
    un artefacto de este banco; un eje es una propiedad de la pregunta, y el ruteador de
    producción va a ver lo segundo.
    """
    e: set[str] = set()
    celda = t["cell"]
    if (t.get("truth_coupling") or 0) >= 0.5 or celda.startswith("C3"):
        e.add("cadena_acoplada")
    if celda.startswith("C8"):
        e.add("contradiccion")
    if t.get("coverage_demanded") == "exhaustive":
        e.add("cobertura_exhaustiva")
    if not t.get("relevant_units"):
        e.add("ausencia")
    if t.get("truth_horizon_unknown") or celda.startswith("C5"):
        e.add("horizonte_desconocido")
    if entidad_en(t["question"]):
        e.add("entidad_nombrada")
    # El material no entra si su costo supera el presupuesto. Aritmética, no juicio.
    if t.get("_material_tokens", 0) > (t.get("budget_tokens") or 0):
        e.add("material_mayor_que_ventana")
    return e


def main() -> None:
    docs = json.loads((CORPUS / "documents.json").read_text(encoding="utf-8"))
    tareas = {t["task_id"]: t for t in json.loads(
        (CORPUS / "tasks.json").read_text(encoding="utf-8"))}
    for t in tareas.values():
        t["_material_tokens"] = sum(len(docs.get(u, "")) for u in t["unit_ids"]) // 4

    filas = [f for f in load_rows(REGISTRO) if not f.get("infeasible")]
    panel = rectangulo([{"task_id": f["task_id"], "paradigm": f["paradigm"],
                         "infeasible": False} for f in filas])
    ts, bs = set(panel.tareas), sorted(panel.brazos)
    u: dict[tuple[str, str], list[float]] = defaultdict(list)
    for f in filas:
        if f["task_id"] in ts and f["paradigm"] in bs:
            u[(f["task_id"], f["paradigm"])].append(f.get("utility", 0.0))
    um = {k: statistics.mean(v) for k, v in u.items()}

    print("=" * 94)
    print("1. LA CADENA, DESPLEGADA SOBRE EL PANEL")
    print("=" * 94)
    print(f"\n  {panel.descripcion()}\n")
    conteo: dict[str, int] = defaultdict(int)
    for tid in panel.tareas:
        for e in ejes_de(tareas[tid]):
            conteo[e] += 1
    print(f"  {'eje de la pregunta':30}{'tareas':>8}   exige")
    for e in sorted(conteo, key=lambda x: -conteo[x]):
        print(f"  {e:30}{conteo[e]:>8}   {', '.join(sorted(EXIGE.get(e, set()))) or '—'}")
    sin_eje = sum(1 for tid in panel.tareas if not ejes_de(tareas[tid]))
    print(f"\n  tareas sin ningún eje activo: {sin_eje} de {len(panel.tareas)}"
          + ("   <- la ontología no las cubre, y eso acota todo lo que sigue"
             if sin_eje else ""))

    # ── la representación por capacidades ───────────────────────────────────────
    # UNA CELDA SE DESCRIBE POR EL CRUCE: para cada capacidad, si la tarea la exige y si el
    # brazo la tiene. Tres estados, y el del medio es el que debería doler.
    def rasgos(tid: str, p: str) -> dict[str, float]:
        ex = set().union(*(EXIGE.get(e, set()) for e in ejes_de(tareas[tid]))) or set()
        tiene = TIENE.get(p, set())
        r = {f"falta::{c}": 1.0 for c in ex - tiene}
        r.update({f"cubre::{c}": 1.0 for c in ex & tiene})
        # Las capacidades del brazo que NADIE exige acá también informan: son su perfil.
        r.update({f"tiene::{c}": 1.0 for c in tiene})
        return r

    print("\n" + "=" * 94)
    print("2. DEJAR UN BRAZO AFUERA — la única prueba que separa capacidad de identidad")
    print("=" * 94)
    print("""
  Se entrena sobre siete brazos y se predice el octavo, que el modelo NUNCA vio. Un modelo
  con la identidad del paradigma no tiene parámetro para un brazo nuevo: es su límite
  estructural. Uno con capacidades sí, porque el brazo trae su vector declarado del código.
""")

    def ajustar(entren: list[tuple[str, str]]) -> tuple[float, dict[str, float]]:
        """Media global + el efecto medio de cada rasgo. Sin librerías: es un modelo aditivo.

        Deliberadamente simple. Con ocho brazos, una regresión con regularización elegida
        por validación tendría más hiperparámetros que datos, y el punto no es exprimir el
        ajuste: es ver si la representación TRANSFIERE.
        """
        base = statistics.mean(um[k] for k in entren)
        efecto: dict[str, list[float]] = defaultdict(list)
        for k in entren:
            resid = um[k] - base
            for r in rasgos(*k):
                efecto[r].append(resid)
        # Encogimiento hacia cero por conteo: un rasgo visto 3 veces no puede pesar como uno
        # visto 200. Es la regularización mínima que evita que un rasgo raro domine.
        return base, {r: sum(v) / (len(v) + 8.0) for r, v in efecto.items()}

    resultados: dict[str, list[float]] = defaultdict(list)
    detalle = []
    for fuera in bs:
        entren = [(t, p) for t in panel.tareas for p in bs
                  if p != fuera and (t, p) in um]
        prueba = [(t, fuera) for t in panel.tareas if (t, fuera) in um]
        if not prueba:
            continue
        base, ef = ajustar(entren)
        # dificultad de la tarea, calculada SIN el brazo dejado afuera
        dif = {t: statistics.mean(um[(t, p)] for p in bs if p != fuera and (t, p) in um)
               for t in panel.tareas}
        real_brazo = statistics.mean(um[k] for k in prueba)

        err = defaultdict(list)
        for t, p in prueba:
            y = um[(t, p)]
            pred_cap = dif[t] + sum(ef.get(r, 0.0) for r in rasgos(t, p))
            err["media_global"].append(abs(y - base))
            err["dificultad_tarea"].append(abs(y - dif[t]))
            err["capacidades"].append(abs(y - max(0.0, min(1.0, pred_cap))))
            err["identidad (hace trampa)"].append(abs(y - real_brazo))
        for k, v in err.items():
            resultados[k].append(statistics.mean(v))
        detalle.append((fuera, {k: statistics.mean(v) for k, v in err.items()}))

    print(f"  {'brazo dejado afuera':22}" + "".join(
        f"{k:>26}" for k in ("media_global", "dificultad_tarea", "capacidades")))
    for fuera, e in detalle:
        fila = f"  {fuera:22}"
        for k in ("media_global", "dificultad_tarea", "capacidades"):
            mejor = e[k] == min(e[m] for m in
                                ("media_global", "dificultad_tarea", "capacidades"))
            fila += f"{e[k]:>24.3f}{' *' if mejor else '  '}"
        print(fila)

    print(f"\n  {'MAE promedio':22}", end="")
    orden = ["media_global", "dificultad_tarea", "capacidades", "identidad (hace trampa)"]
    medias = {k: statistics.mean(resultados[k]) for k in orden if resultados[k]}
    for k in ("media_global", "dificultad_tarea", "capacidades"):
        print(f"{medias[k]:>24.3f}  ", end="")
    print(f"\n  (techo, ve al brazo: {medias['identidad (hace trampa)']:.3f})")

    # ── el veredicto, contra un nulo ────────────────────────────────────────────
    print("\n" + "=" * 94)
    print("3. ¿ES REAL, O ES QUE CUALQUIER ETIQUETA AYUDA?")
    print("=" * 94)
    print("""
  Un vector de capacidades tiene muchos rasgos, y muchos rasgos ajustan cualquier cosa. El
  nulo correcto es BARAJAR las capacidades entre brazos: mismos vectores, mismo número de
  rasgos, misma estructura — asignados al brazo equivocado. Si el modelo con capacidades
  reales no le gana a ése, lo que mide es la capacidad de ajustar, no la de transferir.
""")
    real = medias["capacidades"]
    rng = random.Random(11)
    nulos = []
    original = dict(TIENE)
    for _ in range(400):
        vals = list(original.values())
        rng.shuffle(vals)
        TIENE.clear()
        TIENE.update(dict(zip(original.keys(), vals)))
        errs = []
        for fuera in bs:
            entren = [(t, p) for t in panel.tareas for p in bs
                      if p != fuera and (t, p) in um]
            prueba = [(t, fuera) for t in panel.tareas if (t, fuera) in um]
            if not prueba:
                continue
            _, ef = ajustar(entren)
            dif = {t: statistics.mean(um[(t, p)] for p in bs if p != fuera and (t, p) in um)
                   for t in panel.tareas}
            errs.append(statistics.mean(
                abs(um[(t, p)] - max(0.0, min(1.0, dif[t] + sum(ef.get(r, 0.0)
                                                               for r in rasgos(t, p)))))
                for t, p in prueba))
        nulos.append(statistics.mean(errs))
    TIENE.clear()
    TIENE.update(original)
    nulos.sort()
    p_val = sum(1 for v in nulos if v <= real) / len(nulos)
    print(f"  MAE con capacidades REALES      {real:.4f}")
    print(f"  MAE del nulo (barajadas)        media {statistics.mean(nulos):.4f} · "
          f"p5 {nulos[int(0.05 * len(nulos))]:.4f}")
    print(f"  p = {p_val:.3f}")
    print()
    gana_dif = real < medias["dificultad_tarea"]
    if p_val < 0.05 and gana_dif:
        print("  >>> LAS CAPACIDADES TRANSFIEREN. Predicen un brazo nunca visto mejor que")
        print("      la dificultad de la tarea sola, y mejor que sus propias etiquetas")
        print("      barajadas. El eslabón ontología→capacidad no es vocabulario.")
    elif p_val < 0.05:
        print("  >>> SEÑAL, PERO NO ALCANZA. Le ganan a sus etiquetas barajadas, y NO le")
        print("      ganan a la dificultad de la tarea sola. O sea: la representación tiene")
        print("      algo, y ese algo todavía no compra nada por encima de saber qué tan")
        print("      difícil es la pregunta.")
    else:
        print("  >>> NO TRANSFIEREN en este corpus. Las capacidades barajadas predicen igual")
        print("      de bien, así que lo que ayuda es tener rasgos, no tener LOS rasgos.")
        print("      La tabla es vocabulario hasta que esto dé distinto.")


if __name__ == "__main__":
    main()
