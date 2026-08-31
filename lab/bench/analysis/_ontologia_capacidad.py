"""ONTOLOGÍA -> CAPACIDAD REQUERIDA -> clase de costo. Tres teoremas chicos, medidos.

EL PUENTE QUE FALTABA. `ONTOLOGIA_PREGUNTAS.es.md` mapea ejes de la pregunta y el banco mide
paradigmas, y entre las dos cosas no había nada. Mapear «ontología -> paradigma» directo es
lo que refutó `P15`: el paradigma es un nombre de control de flujo, y la pregunta no tiene
opinión sobre control de flujo.

    Lo que la pregunta SÍ determina es qué CAPACIDAD hace falta para contestarla.
    Y la capacidad determina qué clase de costo puede tenerla. El paradigma sale al final,
    y es casi un detalle.

TRES AFIRMACIONES, cada una falsable con el registro que ya existe:

  T1  **Una contradicción es una relación entre DOS unidades.** Ninguna unidad la contiene,
      así que un brazo sólo puede verla si tuvo las dos delante. No es una cuestión de
      topología: es de payload por llamada. Predice que en `C5` la utilidad depende de
      haber alcanzado AMBAS unidades relevantes, y de nada más.

  T2  **Cobertura exhaustiva con material > presupuesto es insatisfacible, y decidible
      antes de gastar.** No hay brazo que la cumpla. Predice que en esas celdas el ganador
      varía sin patrón — gana por suerte, no por mecanismo.

  T3  **Un roster declarado en la pregunta tiene valor de adaptación CERO.** Los pasos se
      enumeran antes de empezar, así que ver el resultado de uno no cambia el siguiente.
      Predice que en `C9` los brazos que adaptan no le ganan a los de plan fijo.

Corre DESDE `lab/`:  py bench/analysis/_ontologia_capacidad.py
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

# Las tres clases de costo, medidas en `_marcador`/el ajuste de leyes: de que es funcion el
# costo de cada brazo. NO es la taxonomia de control de flujo, y ese es el punto.
CLASE = {
    "handoff": "alcance",
    "pointer_chase": "vueltas", "react": "vueltas", "reflection": "vueltas",
    "supervisor": "vueltas", "gist_reader": "vueltas", "dag_strategy": "vueltas",
    "rewoo": "estructural", "direct": "estructural", "extract_compute": "estructural",
    "streaming_scan": "estructural", "graph_traverse": "estructural",
}


def filas_de(ruta: _Path) -> list[dict]:
    out = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            out.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    return out


def main() -> None:
    tareas = {t["task_id"]: t for t in json.loads(
        _Path("corpus/gold_h1/tasks.json").read_text(encoding="utf-8"))}
    docs = json.loads(_Path("corpus/gold_h1/documents.json").read_text(encoding="utf-8"))
    filas = [f for f in filas_de(_Path("results/luna/gold_h1_rows.jsonl"))
             if not f.get("infeasible") and not f.get("infra_error")]

    # ── T1: la contradiccion exige DOS unidades a la vez ────────────────────
    print("=" * 94)
    print("T1 — una contradiccion es una relacion entre DOS unidades")
    print("=" * 94)
    c5 = [f for f in filas if tareas[f["task_id"]]["cell"] == "C5_unknown_horizon"]
    por_alcanzadas = collections.defaultdict(list)
    for f in c5:
        tu = f.get("tool_usage") or {}
        rel = tu.get("relevant_units_read_any", tu.get("relevant_units_read"))
        if rel is None:
            continue
        por_alcanzadas[min(int(rel), 2)].append(f["utility"])
    print(f"\n  {len(c5)} filas de `C5`. El gold tiene SIEMPRE 2 unidades relevantes: "
          f"el par que se contradice.\n")
    print(f"  {'unidades relevantes alcanzadas':34s} {'filas':>6s} {'utilidad':>9s}")
    for k in sorted(por_alcanzadas):
        v = por_alcanzadas[k]
        print(f"  {('las ' + str(k)) if k == 2 else (str(k) + ' de 2'):34s} "
              f"{len(v):6d} {statistics.mean(v):9.3f}")
    if 2 in por_alcanzadas and len(por_alcanzadas) > 1:
        otras = [u for k, v in por_alcanzadas.items() if k < 2 for u in v]
        d = statistics.mean(por_alcanzadas[2]) - statistics.mean(otras)
        print(f"\n  >>> tener LAS DOS vale {d:+.3f} de utilidad. "
              f"{'T1 SE SOSTIENE' if d > 0.15 else 'T1 no se distingue del ruido'}")
    # Y la clase de costo NO deberia predecir nada una vez que se controla eso.
    print(f"\n  y por CLASE DE COSTO, entre los que alcanzaron las dos:")
    por_clase = collections.defaultdict(list)
    for f in c5:
        tu = f.get("tool_usage") or {}
        rel = tu.get("relevant_units_read_any", tu.get("relevant_units_read")) or 0
        if int(rel) >= 2:
            por_clase[CLASE.get(f["paradigm"], "?")].append(f["utility"])
    for k, v in sorted(por_clase.items()):
        print(f"    {k:14s} {len(v):4d} filas  u={statistics.mean(v):.3f}")
    print("""
  LO QUE ESTO SEPARA. Si la utilidad depende de haber alcanzado las dos y NO de la clase de
  costo, entonces la pregunta no pide una topologia: pide una CAPACIDAD —tener dos unidades
  delante a la vez— y cualquier brazo que la tenga sirve.""")

    # ── T2: la demanda imposible ────────────────────────────────────────────
    print("\n" + "=" * 94)
    print("T2 — cobertura exhaustiva con material > presupuesto es INSATISFACIBLE")
    print("=" * 94)
    imposibles, posibles = [], []
    for tid, t in tareas.items():
        mat = sum(len(docs[u]) for u in t["unit_ids"]) // 4
        exh = t.get("coverage_demanded") == "exhaustive"
        (imposibles if (exh and mat > t["budget_tokens"]) else posibles).append(tid)
    print(f"\n  {len(imposibles)} de {len(tareas)} tareas declaran cobertura exhaustiva "
          f"Y su material no entra en el presupuesto")

    def ganador_por_tarea(tids):
        g = collections.Counter()
        for tid in tids:
            u = collections.defaultdict(list)
            for f in filas:
                if f["task_id"] == tid:
                    u[f["paradigm"]].append(f["utility"])
            if not u:
                continue
            mej = max(u, key=lambda p: statistics.mean(u[p]))
            g[mej] += 1
        return g

    gi = ganador_por_tarea(imposibles)
    gp = ganador_por_tarea(posibles)
    for nombre, g in (("IMPOSIBLES", gi), ("satisfacibles", gp)):
        if not g:
            continue
        n = sum(g.values())
        top = g.most_common(1)[0]
        print(f"\n  {nombre}: {n} tareas, {len(g)} ganadores distintos. "
              f"El mas frecuente gana {top[1]}/{n} = {top[1]/n:.0%}")
        print(f"    {dict(g.most_common(5))}")
    if gi and gp:
        ci = max(gi.values()) / sum(gi.values())
        cp = max(gp.values()) / sum(gp.values())
        print(f"""
  >>> concentracion del ganador: {ci:.0%} en las imposibles contra {cp:.0%} en las
      satisfacibles. {'T2 SE SOSTIENE: donde nadie puede cumplir, el ganador se dispersa'
                      if ci < cp else 'T2 no se distingue'}""")

    # ── T3: el roster declarado no premia adaptarse ─────────────────────────
    print("\n" + "=" * 94)
    print("T3 — un roster DECLARADO tiene valor de adaptacion cero")
    print("=" * 94)
    print("""
  `C9` da la lista de personas EN LA PREGUNTA: los pasos se enumeran antes de empezar, asi
  que ver el resultado de uno no puede cambiar el siguiente. Prediccion: los brazos que
  adaptan (clase VUELTAS) no le ganan a los de plan fijo (clase ESTRUCTURAL).
""")
    for celda, etiqueta in (("C9_declared_roster", "C9 — roster declarado"),
                            ("C3_coupled_chain", "C3 — cadena (control: SI hay que adaptarse)")):
        sub = [f for f in filas if tareas[f["task_id"]]["cell"] == celda]
        pc = collections.defaultdict(list)
        for f in sub:
            pc[CLASE.get(f["paradigm"], "?")].append(f["utility"])
        if not pc:
            continue
        print(f"  {etiqueta}")
        for k in ("vueltas", "estructural", "alcance"):
            if k in pc:
                print(f"    {k:14s} {len(pc[k]):4d} filas  u={statistics.mean(pc[k]):.3f}")
        if "vueltas" in pc and "estructural" in pc:
            d = statistics.mean(pc["vueltas"]) - statistics.mean(pc["estructural"])
            print(f"    adaptarse vale {d:+.3f}\n")


if __name__ == "__main__":
    main()
