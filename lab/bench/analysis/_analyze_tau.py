"""`tau` — el umbral de abstencion — barrido sobre el registro. Cero llamadas al modelo.

POR QUE ESTE PARAMETRO Y NO OTRO. Toda la afirmacion de ruteo SELECTIVO descansa en el:
`tau` es lo que decide si theta opina o se abstiene, y el Corolario 3 dice que la cobertura
optima esta abajo de 1. En el bundle vale `0,3` **desde siempre y sin haberse ajustado
nunca** — un parametro que gobierna la curva que el paper reporta, fijado a mano.

Y P15 fallo con el margen en **0 en todas las tareas**, asi que la curva riesgo-cobertura
colapso a un punto en el origen: AURC 0,000 contra un techo de +0,400. Eso deja dos lecturas
que NADIE separo, y son opuestas:

  (a) el margen es 0 porque los paradigmas EMPATAN            -> `tau` no es la palanca
  (b) el margen es 0 porque theta no tiene EVIDENCIA          -> `tau` no es la palanca
                                                                  TODAVIA, y falta correr

Un barrido ciego de `tau` no las distingue: en las dos da lo mismo para todo `tau`. Asi que
esto reporta **primero la distribucion de margenes** y despues la curva — el barrido sin el
diagnostico produciria una tabla plana que se leeria como «tau no sirve».

QUE NO HACE. No promueve nada. Ajusta una candidata sobre el registro y la mira; instalar
pasa por `promote()` y su guarda, que es otro porton.

Corre DESDE `lab/`:  py bench/analysis/_analyze_tau.py --modelo luna
"""

import argparse
import json
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import statistics
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.policy import (MIN_EPISODES_FOR_CONFIDENCE, Episode, Plasticity, PolicyBundle,
                        learnable_rows)
from app.runner import load_rows

CORPUS = "gold_h1"
FALLBACK = "react"
TAUS = (0.0, 0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5)


def episodios(filas: list[dict]) -> list[Episode]:
    """Filas -> episodios. UN EPISODIO ES UNA CELDA: la media de sus replicas."""
    celdas: dict[tuple[str, str], list[dict]] = defaultdict(list)
    aptas, descartadas = learnable_rows(filas)
    print(f"  {descartadas}")
    for f in aptas:
        celdas[(f["task_id"], f["paradigm"])].append(f)
    medias: dict[str, dict[str, float]] = defaultdict(dict)
    for (tarea, par), fs in celdas.items():
        medias[tarea][par] = sum(x["utility"] for x in fs) / len(fs)
    out = []
    for (tarea, par), fs in celdas.items():
        u = medias[tarea][par]
        out.append(Episode(
            task_id=tarea, region=fs[0].get("region", ""), paradigm=par,
            utility=u, cost_tokens=int(sum(x["cost_tokens"] for x in fs) / len(fs)),
            was_best=abs(u - max(medias[tarea].values())) < 1e-9,
        ))
    return out


def margenes(bundle: PolicyBundle) -> list[tuple[str, float, int]]:
    """Por region: el margen entre el mejor y el segundo, y cuantos brazos CRUZAN el piso.

    El margen se computa SOLO sobre los brazos con evidencia suficiente, igual que
    `best_model`: un bin por debajo del piso no es menos confiable, es invisible, y
    promediarlo con uno que si cruza le presta confianza que no tiene.
    """
    out = []
    for region in bundle.regions():
        vistos = {p: st for p, st in bundle.paradigms_for(region).items()
                  if st.episodes >= MIN_EPISODES_FOR_CONFIDENCE}
        if len(vistos) < 2:
            out.append((region, 0.0, len(vistos)))
            continue
        orden = sorted(vistos.values(), key=lambda s: -s.mean_utility)
        out.append((region, orden[0].mean_utility - orden[1].mean_utility, len(vistos)))
    return sorted(out, key=lambda x: -x[1])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--modelo", default="luna")
    args = ap.parse_args()

    base = Settings.from_env()
    path = base.results_dir / args.modelo / f"{CORPUS}_rows.jsonl"
    filas = load_rows(path)
    eps = episodios(filas)
    frio = PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3)
    cand = Plasticity.candidate(frio, eps, tau=0.3, notes="barrido de tau")

    print(f"{len(filas)} filas · {len(eps)} episodios · "
          f"{len(list(cand.regions()))} regiones")
    print(f"piso de evidencia por brazo: {MIN_EPISODES_FOR_CONFIDENCE} episodios\n")

    print("=" * 74)
    print("1. EL DIAGNOSTICO — de donde sale el margen\n")
    ms = margenes(cand)
    print(f"  {'region':<40}{'margen':>9}{'brazos con evidencia':>22}")
    for region, m, n in ms:
        aviso = "  <- menos de 2: no hay margen que medir" if n < 2 else ""
        print(f"  {region:<40}{m:>9.4f}{n:>22}{aviso}")
    con_margen = [m for _, m, n in ms if n >= 2]
    sin_evidencia = sum(1 for _, _, n in ms if n < 2)
    print()
    if not con_margen:
        print("  NINGUNA region tiene dos brazos por encima del piso de evidencia.")
        print("  El margen es 0 por FALTA DE DATOS, no por empate: `tau` no puede ser la")
        print("  palanca todavia, y barrerlo daria una tabla plana que se leeria como que")
        print("  no sirve. Lo que falta son EPISODIOS, y eso son celdas — no un ajuste.")
    else:
        cero = sum(1 for m in con_margen if m < 1e-9)
        print(f"  {len(con_margen)} regiones con 2+ brazos con evidencia; "
              f"{cero} con margen exactamente 0 (EMPATE)")
        print(f"  margen mediano: {statistics.median(con_margen):.4f}   "
              f"maximo: {max(con_margen):.4f}")
    print(f"  {sin_evidencia} regiones sin evidencia suficiente")

    print("\n" + "=" * 74)
    print("2. EL BARRIDO — cuanta cobertura deja cada `tau`\n")
    print(f"  {'tau':>6}{'regiones que opinan':>22}{'cobertura':>12}")
    for tau in TAUS:
        opinan = sum(1 for _, m, n in ms if n >= 2 and m >= tau)
        print(f"  {tau:>6.2f}{opinan:>22}{opinan / max(1, len(ms)):>12.1%}")
    print(f"\n  `tau` en el bundle hoy: 0,30  (fijado a mano, nunca ajustado)")

    salida = base.results_dir / args.modelo / "tau_sweep.json"
    salida.write_text(json.dumps({
        "filas": len(filas), "episodios": len(eps),
        "margenes": [{"region": r, "margen": m, "brazos": n} for r, m, n in ms],
        "barrido": [{"tau": t,
                     "regiones_que_opinan": sum(1 for _, m, n in ms if n >= 2 and m >= t)}
                    for t in TAUS],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  -> {salida}")


if __name__ == "__main__":
    main()
