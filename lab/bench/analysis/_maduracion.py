"""LA TRAYECTORIA DE MADURACIÓN DE θ SOBRE EL REGISTRO DE LA CAMPAÑA. Cero llamadas al modelo.

Qué mide, y por qué esto y no la utilidad. "Aprender", en este proyecto, significa que el
sistema cambia lo que hace con la experiencia, que cada cambio es un artefacto legible, y que
ningún cambio rompe la garantía. Nada de eso se mide con una curva de utilidad. Se mide con la
trayectoria del propio θ mientras absorbe episodios:

  · cuántas regiones tienen evidencia, y cuántos pares (región, brazo) cruzaron el piso de
    confianza (`MIN_EPISODES_FOR_CONFIDENCE`), que es lo que habilita a una fila a gobernar;
  · cuántas tareas del corpus caen en una región donde θ ya gobierna en vez de caer al
    fallback;
  · si el candidato de cada ciclo pasó la guarda de promoción sobre los episodios que todavía
    no había visto (el lote siguiente), es decir si la maduración es segura;
  · si dos construcciones del mismo bundle sobre los mismos episodios dan las mismas tablas,
    es decir si lo aprendido es reproducible;
  · y qué dice el artefacto: el `explain_text` de θ al final, que es lo que un auditor lee.

Los episodios se arman igual que `Runner.episodes` (una celda por par tarea-brazo, media
sobre réplicas, `was_best` sobre medias). Los ciclos simulan la llegada de tareas en lotes:
el registro llegó de una vez, así que el orden por `task_id` es un proxy de llegada y se
declara como tal.

Corre DESDE `lab/`:  py bench/analysis/_maduracion.py
"""
from __future__ import annotations

import collections
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.policy import (MIN_EPISODES_FOR_CONFIDENCE, Episode, Plasticity, PolicyBundle,
                        learnable_rows, promote)
from app.runner import load_rows

REGISTRO = Path("results/luna/gold_h1_rows.jsonl")
FALLBACK = "react"
TAU = 0.05
LOTES = 6


def episodios(filas):
    filas, descartadas = learnable_rows(filas)
    cells = collections.defaultdict(list)
    for r in filas:
        cells[(r["task_id"], r["paradigm"])].append(r)
    mean_u = {k: statistics.mean(x["utility"] for x in v) for k, v in cells.items()}
    best = collections.defaultdict(float)
    for (t, _), u in mean_u.items():
        best[t] = max(best[t], u)
    eps = [Episode(task_id=t, region=v[0]["region"], paradigm=p, utility=mean_u[(t, p)],
                   cost_tokens=int(statistics.mean(x["cost_tokens"] for x in v)),
                   was_best=(mean_u[(t, p)] >= best[t] > 0.0))
           for (t, p), v in sorted(cells.items())]
    return eps, descartadas


def eleccion(bundle: PolicyBundle, region: str) -> str:
    """Qué brazo gobierna θ en esa región: el mejor par confiado si su margen sobre el
    fallback supera tau; si no, el fallback."""
    stats = bundle.stats.get(region, {})
    confiados = {p: s for p, s in stats.items() if s.episodes >= MIN_EPISODES_FOR_CONFIDENCE}
    if not confiados:
        return bundle.fallback
    mejor = max(confiados, key=lambda p: confiados[p].mean_utility)
    fb = confiados.get(bundle.fallback)
    if fb is not None and confiados[mejor].mean_utility - fb.mean_utility <= bundle.tau:
        return bundle.fallback
    return mejor


def valor(bundle: PolicyBundle, holdout: list[Episode]) -> float:
    """Utilidad media que θ obtiene sobre un holdout: por tarea, la utilidad del brazo que
    θ elige en su región, leída de los episodios de esa tarea (si el brazo elegido no tiene
    episodio en la tarea, se toma el fallback)."""
    por_tarea = collections.defaultdict(dict)
    for e in holdout:
        por_tarea[e.task_id][e.paradigm] = e
    vals = []
    for t, brazos in por_tarea.items():
        region = next(iter(brazos.values())).region
        p = eleccion(bundle, region)
        e = brazos.get(p) or brazos.get(bundle.fallback)
        if e is not None:
            vals.append(e.utility)
    return statistics.mean(vals) if vals else 0.0


def main() -> None:
    eps, descartadas = episodios(load_rows(REGISTRO))
    tareas = sorted({e.task_id for e in eps})
    print("=" * 96)
    print(f"TRAYECTORIA DE MADURACIÓN · {len(eps)} episodios sobre {len(tareas)} tareas · "
          f"descartes: {descartadas}")
    print("=" * 96)
    print(f"  fallback {FALLBACK} · tau {TAU} · piso de confianza {MIN_EPISODES_FOR_CONFIDENCE} episodios por par"
          f" · {LOTES} lotes por orden de task_id (proxy de llegada, declarado)\n")

    por_tarea = collections.defaultdict(list)
    for e in eps:
        por_tarea[e.task_id].append(e)
    tam = -(-len(tareas) // LOTES)
    lotes = [tareas[i:i + tam] for i in range(0, len(tareas), tam)]
    region_de = {t: por_tarea[t][0].region for t in tareas}

    incumbent = PolicyBundle.cold_start(FALLBACK, TAU)
    print(f"  {'ciclo':>5}{'episodios':>10}{'regiones':>9}{'pares n>=8':>11}{'tareas gobernadas':>18}"
          f"{'guarda':>9}{'ganancia [IC95]':>24}{'reproducible':>13}")
    for i, lote in enumerate(lotes, start=1):
        nuevos = [e for t in lote for e in por_tarea[t]]
        cand = Plasticity.candidate(incumbent, nuevos, TAU, notes=f"ciclo {i}")
        cand2 = Plasticity.candidate(incumbent, nuevos, TAU, notes=f"ciclo {i}")
        mismas_tablas = {r: {p: s.as_dict() for p, s in ps.items()} for r, ps in cand.stats.items()} == \
                        {r: {p: s.as_dict() for p, s in ps.items()} for r, ps in cand2.stats.items()}
        regiones = len(cand.stats)
        pares = sum(1 for ps in cand.stats.values() for s in ps.values()
                    if s.episodes >= MIN_EPISODES_FOR_CONFIDENCE)
        gobernadas = sum(1 for t in tareas if eleccion(cand, region_de[t]) != FALLBACK)
        siguiente = lotes[i] if i < len(lotes) else None
        if siguiente:
            holdout = [e for t in siguiente for e in por_tarea[t]]
            v = promote(incumbent, cand, holdout, valor)
            guarda = "pasa" if v.accepted else "NO"
            ic = (f"{v.candidate_value - v.incumbent_value:+.3f} "
                  f"[{v.gain_low:+.3f}, {v.gain_high:+.3f}]" if v.gain_low is not None else "s/IC")
        else:
            guarda, ic = "sin lote", ""
        print(f"  {i:>5}{len(cand.absorbed):>10}{regiones:>9}{pares:>11}{gobernadas:>10} de {len(tareas):<4}"
              f"{guarda:>9}{ic:>24}{('sí' if mismas_tablas and cand.verify() else 'NO'):>13}")
        incumbent = cand

    print("\n  Lectura. `tareas gobernadas` cuenta en cuántas de las 78 tareas θ elegiría un brazo"
          " distinto del fallback con su regla de confianza y margen;")
    print("  `guarda` dice si el candidato del ciclo habría entrado, evaluado sobre el lote que"
          " todavía no había visto (bootstrap pareado, borde inferior >= 0).")
    print("\n" + "=" * 96)
    print("EL ARTEFACTO: θ al final, tal como lo lee un auditor (extracto)")
    print("=" * 96)
    texto = incumbent.explain_text().split("\n")
    print("\n".join("  " + l for l in texto[:3]))
    # las dos regiones con más tareas
    conteo = collections.Counter(region_de.values())
    for region, n in conteo.most_common(2):
        idx = texto.index(f"region {region}")
        bloque = []
        for l in texto[idx:]:
            if l == "" and bloque:
                break
            bloque.append(l)
        print(f"\n  ({n} tareas)")
        print("\n".join("  " + l for l in bloque))
    print(f"\n  regiones en θ: {len(incumbent.stats)} · episodios absorbidos: {len(incumbent.absorbed)}"
          f" · firma verificada: {incumbent.verify()}")


if __name__ == "__main__":
    main()
