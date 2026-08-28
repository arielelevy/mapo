"""O-4: ¿las demandas tipadas del request explican algo que la region no explica ya?

QUE SE PREGUNTA. `REQUEST_DEMANDS` declara por celda un par (cardinalidad, cobertura).
La pregunta no es si el eje es real —lo es por construccion, esta en el enunciado— sino
si COMPRA ALGO que el vocabulario de region no compre ya. Un eje que se deduce de la
region no es informacion nueva: es la misma particion con otro nombre, y agregarlo al
router seria contarse la misma evidencia dos veces.

PREDICCIONES, REGISTRADAS ANTES DE COMPUTAR (2026-08-28)

  O-4a  En celdas `exhaustive`, la utilidad sube con la fraccion leida; en `sufficient`
        no. Refutada si el signo y la magnitud son parecidos en las dos clases — eso
        querria decir que leer mas ayuda siempre, y entonces la distincion no describe
        nada del sistema.

  O-4b  `coverage_demanded` separa mejor que `answer_cardinality`. Concretamente: el
        ranking de paradigmas cambia mas entre clases de cobertura que entre clases de
        cardinalidad. Refutada si cardinalidad separa igual o mas.

  O-4c  La cobertura NO es funcion de la region. Refutada si cada region observada cae
        entera en una sola clase de cobertura — ahi el eje ya esta adentro y no hay nada
        que agregar.

NOTA DE HONESTIDAD. Esto corre sobre filas YA PAGADAS. No es una corrida nueva y no
puede serlo: el eje es una relectura del registro, no un experimento. Vale como
descriptivo y como criterio de decision sobre si vale la pena elicitar la demanda
(U-3, una llamada por request). No vale como falsacion de un patron.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import statistics
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner
from corpus.generate import REQUEST_DEMANDS

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")

CORPORA = ["gold_p17", "gold_p16", "gold_transfer", "gold_v2", "gold_deep"]


def demands(task_id: str) -> tuple[str, str] | None:
    prefix = task_id.split("-")[0].upper()
    return REQUEST_DEMANDS.get(prefix)


def pearson(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 4:
        return None
    n = len(pairs)
    mx = sum(x for x, _ in pairs) / n
    my = sum(y for _, y in pairs) / n
    sx = sum((x - mx) ** 2 for x, _ in pairs) ** 0.5
    sy = sum((y - my) ** 2 for _, y in pairs) ** 0.5
    if not sx or not sy:
        return None
    return sum((x - mx) * (y - my) for x, y in pairs) / (sx * sy)


def main() -> None:
    rows = []
    missing: list[str] = []
    for name in CORPORA:
        # Un corpus que no esta es un hecho del entorno y se DECLARA; cualquier otra cosa
        # es un defecto y tiene que romper. Tragarse todo con un `continue` haria que el
        # analisis reportara "sobre 5 corpus" habiendo leido tres, y ahora ademas se
        # tragaria la guarda de decodificaciones mezcladas — que levanta ValueError.
        if not (settings.corpus_dir / name).is_dir():
            missing.append(name)
            continue
        runner = Runner(settings, name, retriever_arm="hybrid", surface_variant="basic")
        for r in runner.load_rows():
            if r.get("infra_error") or r.get("infeasible"):
                continue
            d = demands(r["task_id"])
            if d is None:
                continue
            r["_card"], r["_cov"], r["_dom"] = d
            r["_corpus"] = name
            rows.append(r)

    if missing:
        print(f"corpus ausentes, declarados y no ignorados: {missing}")
    if not rows:
        raise SystemExit(
            "Sin una sola fila utilizable. Eso no es un resultado vacio: es que el "
            "analisis no tuvo con que correr, y devolver 0 en silencio lo haria pasar "
            "por una medicion."
        )
    print(f"{len(rows)} filas utiles sobre {len(set(r['_corpus'] for r in rows))} corpus\n")

    # --- O-4a --------------------------------------------------------------------------
    print("--- O-4a: ¿leer mas ayuda solo donde la cobertura se exige? ---")
    out_a = {}
    for cov in ("sufficient", "exhaustive"):
        pairs = [
            (frac, r["utility"])
            for r in rows if r["_cov"] == cov
            for frac in [(r.get("tool_usage") or {}).get("fraction_read")]
            if frac is not None
        ]
        rho = pearson(pairs)
        out_a[cov] = {"n": len(pairs), "rho": rho}
        shown = f"{rho:+.3f}" if rho is not None else "sin n"
        print(f"  {cov:<12} n={len(pairs):>4}  corr(fraccion leida, utilidad) = {shown}")
    ra, rb = out_a["exhaustive"]["rho"], out_a["sufficient"]["rho"]
    if ra is not None and rb is not None:
        gap = ra - rb
        verdict_a = "CONFIRMADA" if gap > 0.10 else "REFUTADA"
        print(f"  diferencia exhaustive - sufficient: {gap:+.3f}   O-4a: {verdict_a} (criterio > 0,10)")
    else:
        gap, verdict_a = None, "SIN N"
        print("  O-4a: SIN N")

    # --- O-4b --------------------------------------------------------------------------
    print("\n--- O-4b: ¿que eje reordena mas el ranking de paradigmas? ---")

    def spread(axis: str) -> tuple[float, dict]:
        """Distancia media entre los rankings de paradigmas de dos clases del eje."""
        by_class: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for r in rows:
            by_class[r[axis]][r["paradigm"]].append(r["utility"])
        ranks: dict[str, list[str]] = {}
        for klass, per_par in by_class.items():
            usable = {p: statistics.mean(v) for p, v in per_par.items() if len(v) >= 3}
            if len(usable) >= 4:
                ranks[klass] = [p for p, _ in sorted(usable.items(), key=lambda kv: -kv[1])]
        classes = sorted(ranks)
        dists = []
        for i, a in enumerate(classes):
            for b in classes[i + 1:]:
                common = [p for p in ranks[a] if p in ranks[b]]
                if len(common) < 4:
                    continue
                pa = {p: k for k, p in enumerate(ranks[a])}
                pb = {p: k for k, p in enumerate(ranks[b])}
                dists.append(sum(abs(pa[p] - pb[p]) for p in common) / len(common))
        return (statistics.mean(dists) if dists else 0.0,
                {k: v[:4] for k, v in ranks.items()})

    s_cov, r_cov = spread("_cov")
    s_card, r_card = spread("_card")
    for klass, top in sorted(r_cov.items()):
        print(f"  cobertura {klass:<12} top-4: {', '.join(top)}")
    for klass, top in sorted(r_card.items()):
        print(f"  cardinal. {klass:<12} top-4: {', '.join(top)}")
    print(f"  reordenamiento medio | cobertura {s_cov:.2f} | cardinalidad {s_card:.2f}")
    verdict_b = "CONFIRMADA" if s_cov > s_card else "REFUTADA"
    print(f"  O-4b: {verdict_b}")

    # --- O-4c --------------------------------------------------------------------------
    print("\n--- O-4c: ¿la region ya contiene la cobertura? ---")
    by_region: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        region = r.get("region")
        if region:
            by_region[region].add(r["_cov"])
    mixed = {k: sorted(v) for k, v in by_region.items() if len(v) > 1}
    print(f"  regiones observadas: {len(by_region)}")
    print(f"  regiones que MEZCLAN clases de cobertura: {len(mixed)}")
    for k, v in sorted(mixed.items())[:8]:
        print(f"    {k}  ->  {', '.join(v)}")
    verdict_c = "CONFIRMADA" if mixed else "REFUTADA"
    print(f"  O-4c: {verdict_c} (confirmada = la region NO la determina)")

    out = settings.results_dir / "demands.json"
    out.write_text(json.dumps({
        "rows": len(rows),
        "o4a": {"per_class": out_a, "gap": gap, "verdict": verdict_a},
        "o4b": {"spread_coverage": s_cov, "spread_cardinality": s_card,
                "verdict": verdict_b},
        "o4c": {"regions": len(by_region), "mixed": mixed, "verdict": verdict_c},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nveredicto: {out}")


if __name__ == "__main__":
    main()
