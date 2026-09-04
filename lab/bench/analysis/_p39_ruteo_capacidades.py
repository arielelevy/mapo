"""P39: ¿rutear por capacidades cobra el premio que existe entre los ocho brazos? Cero tokens.

LA PREGUNTA. §6.2 mide que sobre los ocho brazos del rectángulo la brecha de oráculo es neta y
positiva (+0,110, piso p95 0,065) y que ninguna política medida la captura, ni por identidad
de paradigma ni por familia. El paper lo dejaba abierto: «sobre qué clave se cobra un premio
que existe». La clave candidata está en el propio paper, §6.3: la ontología de la pregunta
EXIGE capacidades, cada brazo TIENE capacidades, y de ahí sale el conjunto de brazos capaces.
Esto mide si esa clave cobra el premio, con cuatro políticas y dos vocabularios de ejes.

LAS CUATRO POLÍTICAS, todas leave-one-task-out (la tarea evaluada nunca participa de lo que
se aprende para decidirla):
  1. capaces → el de mejor utilidad media entre los capaces, aprendida en las otras tareas
  2. capaces → el más barato entre los capaces que empatan con el mejor dentro del ruido
  3. mismos ejes → el mejor brazo en las otras tareas que activan EXACTAMENTE los mismos ejes
     (ruteo keyed en la ontología, sin pasar por capacidades)
  4. puntuar por capacidades: regresión ridge de u(t, p) sobre el vector de capacidades del
     brazo, con pesos condicionales al eje activo, ajustada en las otras tareas; se elige el
     brazo de mayor predicción. Es «puntuar los brazos por capacidad y elegir».
Sin brazo capaz (ausencia: nadie junta cobertura y abstención) se cae al mejor fijo.

LOS DOS VOCABULARIOS DE EJES, porque la salvedad de §6.3.5 manda:
  · «etiqueta de diseño»: `ejes_de` del EDA, que usa la celda del corpus para tres ejes. Es la
    cota superior: en producción esa etiqueta no existe
  · «sólo COMPUTED»: los ejes que hoy se computan sin modelo ni etiqueta desde la pregunta y
    el material (entidad nombrada, material mayor que la ventana). Es lo que un request real
    tiene hoy; los demás ejes tienen `ELICITED` como techo y son `P35`

LA VARA. Δ contra el mejor fijo aprendido leave-one-task-out, con IC95 pareado por tarea, y el
piso p95 por pseudo-brazos de los ocho brazos (el mismo estimador de §6.2.3). Una política
cobra el premio si su Δ supera ese piso. El veredicto está escrito antes de correr en la
bitácora (`P39`).

Corre DESDE `lab/`:  py bench/analysis/_p39_ruteo_capacidades.py
"""

from __future__ import annotations

import collections
import json
import random
import statistics
import sys as _sys
from pathlib import Path

_sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
_sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np

from app.capacidades import EXIGE, NOMBRES, TIENE, capaces
from app.features import entidad_en
from app.runner import load_rows
from bench.analysis._eda_capacidades import ejes_de
from bench.analysis._recomputo_revision import pisos
from bench.panel import rectangulo

REGISTRO = Path("results/luna/gold_h1_rows.jsonl")
CORPUS = Path("corpus/gold_h1")
SALIDA = Path("results/luna/p39_ruteo_capacidades.json")
SEMILLA = 20260903
B = 2000


def ejes_computed(t: dict) -> set[str]:
    """Sólo lo que se computa hoy sin modelo ni etiqueta de diseño."""
    e: set[str] = set()
    if entidad_en(t["question"]):
        e.add("entidad_nombrada")
    if t.get("_material_tokens", 0) > (t.get("budget_tokens") or 0):
        e.add("material_mayor_que_ventana")
    return e


def cargar():
    docs = json.loads((CORPUS / "documents.json").read_text(encoding="utf-8"))
    tareas = {t["task_id"]: t for t in json.loads((CORPUS / "tasks.json").read_text(encoding="utf-8"))}
    for t in tareas.values():
        t["_material_tokens"] = sum(len(docs.get(u, "")) for u in t["unit_ids"]) // 4
    filas = [f for f in load_rows(REGISTRO) if not f.get("infeasible")]
    panel = rectangulo(filas)
    ts, bs = sorted(panel.tareas), sorted(panel.brazos)
    reps = collections.defaultdict(list)
    costos = collections.defaultdict(list)
    for f in filas:
        if f["task_id"] in panel.tareas and f["paradigm"] in panel.brazos:
            reps[(f["task_id"], f["paradigm"])].append(f["utility"])
            costos[(f["task_id"], f["paradigm"])].append(f.get("cost_tokens") or 0)
    U = {k: statistics.mean(v) for k, v in reps.items()}
    C = {k: statistics.mean(v) for k, v in costos.items()}
    return panel, tareas, ts, bs, reps, U, C


def main() -> None:
    rng = random.Random(SEMILLA)
    panel, tareas, ts, bs, reps, U, C = cargar()
    print("=" * 96)
    print("P39 · ¿RUTEAR POR CAPACIDADES COBRA EL PREMIO ENTRE LOS OCHO BRAZOS?")
    print("=" * 96)
    print(f"  {panel.descripcion()}")

    # tolerancia de empate = una desviación del ruido de la media (como en `_predictores.py`)
    dentro = [statistics.variance(reps[(t, p)]) for t in ts for p in bs if len(reps[(t, p)]) > 1]
    n_rep = statistics.mean(len(reps[(t, p)]) for t in ts for p in bs)
    tol = (statistics.mean(dentro) / n_rep) ** 0.5

    def mejor_fijo(otros):
        return max(bs, key=lambda p: statistics.mean(U[(o, p)] for o in otros))

    def media(p, otros):
        return statistics.mean(U[(o, p)] for o in otros)

    caps = {p: np.array([1.0 if c in TIENE.get(p, set()) else 0.0 for c in NOMBRES]) for p in bs}
    todos_ejes = sorted(EXIGE)

    def puntuar(t, otros, ejes_fn):
        """Ridge sobre [caps(p), caps(p) x 1[eje activo]] ajustada en las otras tareas."""
        def x(tid, p):
            e = ejes_fn(tareas[tid])
            base = caps[p]
            inter = np.concatenate([base * (1.0 if ej in e else 0.0) for ej in todos_ejes])
            return np.concatenate([[1.0], base, inter])
        X = np.array([x(o, p) for o in otros for p in bs])
        y = np.array([U[(o, p)] for o in otros for p in bs])
        lam = 1.0
        w = np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)
        return max(bs, key=lambda p: float(x(t, p) @ w))

    def evaluar(nombre, decidir):
        elegidos = {t: decidir(t, [o for o in ts if o != t]) for t in ts}
        u_pol = [U[(t, elegidos[t])] for t in ts]
        u_fijo = [U[(t, mejor_fijo([o for o in ts if o != t]))] for t in ts]
        dif = [a - b for a, b in zip(u_pol, u_fijo)]
        bs_ = []
        for _ in range(B):
            s = [rng.choice(dif) for _ in dif]
            bs_.append(statistics.mean(s))
        bs_.sort()
        tok = statistics.mean(C[(t, elegidos[t])] for t in ts)
        distintos = sum(1 for t in ts if elegidos[t] != mejor_fijo([o for o in ts if o != t]))
        return {"utilidad": round(statistics.mean(u_pol), 4),
                "delta_vs_fijo": round(statistics.mean(dif), 4),
                "ic95": [round(bs_[int(0.025 * B)], 4), round(bs_[int(0.975 * B)], 4)],
                "tokens": round(tok), "tareas_ruteadas": distintos,
                "elige": dict(collections.Counter(elegidos.values()).most_common())}

    resultados = {}
    for etiqueta, ejes_fn in (("etiqueta de diseño", ejes_de), ("sólo COMPUTED", ejes_computed)):
        def cap_de(t):
            exig = set().union(*(EXIGE[e] for e in ejes_fn(tareas[t]))) if ejes_fn(tareas[t]) else set()
            return capaces(exig, plantel=bs), exig

        def pol_mejor(t, otros):
            cs, _ = cap_de(t)
            return max(cs, key=lambda p: media(p, otros)) if cs else mejor_fijo(otros)

        def pol_barato(t, otros):
            cs, _ = cap_de(t)
            if not cs:
                return mejor_fijo(otros)
            top = max(media(p, otros) for p in cs)
            emp = [p for p in cs if media(p, otros) >= top - tol]
            return min(emp, key=lambda p: statistics.mean(C[(o, p)] for o in otros))

        def pol_ejes(t, otros):
            e = frozenset(ejes_fn(tareas[t]))
            mismos = [o for o in otros if frozenset(ejes_fn(tareas[o])) == e]
            return max(bs, key=lambda p: media(p, mismos)) if mismos else mejor_fijo(otros)

        def pol_puntuar(t, otros):
            return puntuar(t, otros, ejes_fn)

        sin_capaz = sum(1 for t in ts if not cap_de(t)[0])
        print(f"\n  ── ejes: {etiqueta} · tareas sin brazo capaz: {sin_capaz} de {len(ts)}")
        print(f"  {'política':44} {'u':>6} {'Δ vs fijo':>10} {'IC95':>20} {'tok/tarea':>10} {'rutea':>6}")
        bloque = {}
        for nombre, fn in (("capaces → mejor promedio", pol_mejor),
                           ("capaces → más barato que empata", pol_barato),
                           ("mismos ejes → mejor promedio", pol_ejes),
                           ("puntuar por capacidades (ridge)", pol_puntuar)):
            r = evaluar(nombre, fn)
            bloque[nombre] = r
            print(f"  {nombre:44} {r['utilidad']:6.3f} {r['delta_vs_fijo']:+10.3f} "
                  f"[{r['ic95'][0]:+.3f}, {r['ic95'][1]:+.3f}]   {r['tokens']:>10,} {r['tareas_ruteadas']:>6}")
        resultados[etiqueta] = {"sin_brazo_capaz": sin_capaz, "politicas": bloque}

    # la vara: oráculo, mejor fijo y piso p95 de los ocho, con el estimador de §6.2.3
    print("\n  ── la vara")
    piso = pisos(reps, ts, bs, random.Random(SEMILLA))
    for k, v in piso.items():
        if isinstance(v, (int, float)):
            print(f"  {k:36} {v:+.4f}")
    u_fijo = statistics.mean(U[(t, mejor_fijo([o for o in ts if o != t]))] for t in ts)
    u_ora = statistics.mean(max(U[(t, p)] for p in bs) for t in ts)
    print(f"  {'mejor fijo (LOTO)':36} {u_fijo:.4f}")
    print(f"  {'oráculo por tarea':36} {u_ora:.4f}   brecha {u_ora - u_fijo:+.4f}")

    SALIDA.write_text(json.dumps({
        "prediccion": "P39", "fecha_corrida": "2026-09-03", "panel": panel.descripcion(),
        "tolerancia_empate": round(tol, 4), "mejor_fijo_loto": round(u_fijo, 4),
        "oraculo": round(u_ora, 4),
        "piso": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in piso.items()
                 if isinstance(v, (int, float, str))},
        "resultados": resultados,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  guardado en {SALIDA}")


if __name__ == "__main__":
    main()
