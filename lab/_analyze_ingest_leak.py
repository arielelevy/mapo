"""G-3: la ingesta adentro del request, y si contamina alguna medicion ya publicada.

QUE SE SUPONIA. Que la ingesta es asincrona, se hace una sola vez y es INDEPENDIENTE del
patron — por eso no contamina la comparacion entre brazos.

QUE PASA EN REALIDAD. `graph_traverse` construye y persiste su propio indice de entidades
ADENTRO de un request: una llamada corta por unidad, pagada por la primera tarea que lo
necesita. Eso ya estaba escrito y declarado honestamente en el codigo. Lo que NO estaba
mirado es la segunda mitad del efecto:

  `_entity_graph` lee cada unidad con `surface.read_one()`, y eso REGISTRA la lectura.

Entonces la fila que paga el indice no solo carga su costo: carga `units_read` y
`fraction_read` del corpus ENTERO. Y `fraction_read` es la variable sobre la que se midio
O-4a — «leer mas no compra la exhaustividad». Si esas filas entraron, la correlacion se
midio contra un denominador que un brazo infla por construir su indice y no por buscar.

ESTO NO ES UN DEFECTO NUEVO NI UNA SORPRESA DEL CODIGO: es la consecuencia medible de que
un paradigma haga ingesta adentro de un request, que es exactamente lo que G-4 propone
prohibir. Se mide para saber si algo publicado hay que corregir.
"""

import json
import statistics
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner
from corpus.generate import REQUEST_DEMANDS

CORPORA = ["gold_p17", "gold_p16", "gold_transfer", "gold_v2", "gold_deep"]
BUILDER = "graph_traverse"


def pearson(pairs):
    n = len(pairs)
    if n < 4:
        return None
    mx = sum(x for x, _ in pairs) / n
    my = sum(y for _, y in pairs) / n
    sx = sum((x - mx) ** 2 for x, _ in pairs) ** 0.5
    sy = sum((y - my) ** 2 for _, y in pairs) ** 0.5
    if not sx or not sy:
        return None
    return sum((x - mx) * (y - my) for x, y in pairs) / (sx * sy)


def main() -> None:
    base = Settings.from_env()
    settings = replace(base, results_dir=base.results_dir / "nano")

    rows = []
    missing = []
    for name in CORPORA:
        if not (settings.corpus_dir / name).is_dir():
            missing.append(name)
            continue
        runner = Runner(settings, name, retriever_arm="hybrid", surface_variant="basic")
        for r in runner.load_rows():
            if r.get("infra_error") or r.get("infeasible"):
                continue
            r["_corpus"] = name
            rows.append(r)
    if missing:
        print(f"corpus ausentes, declarados: {missing}")
    if not rows:
        raise SystemExit("sin filas: el analisis no tuvo con que correr")

    builder = [r for r in rows if r["paradigm"] == BUILDER]
    print(f"{len(rows)} filas | {len(builder)} de `{BUILDER}`\n")

    if not builder:
        print(f"`{BUILDER}` no tiene filas en estos corpus: nada que contaminar aca.")
    else:
        print("--- ¿el brazo que construye indice lee mas que los otros? ---")
        by_par = defaultdict(list)
        for r in rows:
            frac = (r.get("tool_usage") or {}).get("fraction_read")
            if frac is not None:
                by_par[r["paradigm"]].append(frac)
        for p, v in sorted(by_par.items(), key=lambda kv: -statistics.mean(kv[1])):
            mark = "  <- construye indice" if p == BUILDER else ""
            print(f"  {p:<16} n={len(v):>4}  fraccion leida media {statistics.mean(v):.3f}"
                  f"  mediana {statistics.median(v):.3f}{mark}")

    # --- ¿cambia O-4a al sacarlas? -----------------------------------------------------
    print("\n--- O-4a con y sin el brazo que construye indice ---")
    for label, subset in (("con todas", rows),
                          (f"sin `{BUILDER}`",
                           [r for r in rows if r["paradigm"] != BUILDER])):
        per_task = defaultdict(list)
        cov_of = {}
        for r in subset:
            d = REQUEST_DEMANDS.get(r["task_id"].split("-")[0].upper())
            frac = (r.get("tool_usage") or {}).get("fraction_read")
            if d is None or frac is None:
                continue
            key = (r["_corpus"], r["task_id"])
            per_task[key].append((frac, r["utility"]))
            cov_of[key] = d[1]

        by_cov = defaultdict(list)
        for key, pairs in per_task.items():
            rho = pearson(pairs)
            if rho is not None:
                by_cov[cov_of[key]].append(rho)

        parts = []
        for cov in ("sufficient", "exhaustive"):
            v = by_cov[cov]
            parts.append(f"{cov} n={len(v)} rho={statistics.mean(v):+.3f}" if v
                         else f"{cov} sin n")
        gap = (statistics.mean(by_cov["exhaustive"]) - statistics.mean(by_cov["sufficient"])
               if by_cov["exhaustive"] and by_cov["sufficient"] else None)
        print(f"  {label:<20} {' | '.join(parts)}"
              f"{f'  brecha {gap:+.3f}' if gap is not None else ''}")

    # --- el costo del indice, separado del costo de responder --------------------------
    if builder:
        print(f"\n--- el costo del indice va a la fila que lo paga ---")
        costs = sorted((r["cost_tokens"] for r in builder), reverse=True)
        print(f"  costo de `{BUILDER}`: max {costs[0]:,} | mediana "
              f"{statistics.median(costs):,.0f} | min {costs[-1]:,}")
        print(f"  razon max/mediana: {costs[0] / max(statistics.median(costs), 1):.1f}x")
        print("  Una sola fila carga la ingesta entera; las demas la reciben gratis.")
        print("  Promediar el brazo mezcla dos economias distintas.")

    out = settings.results_dir / "ingest_leak.json"
    out.write_text(json.dumps({
        "rows": len(rows), "builder_rows": len(builder),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndetalle: {out}")


if __name__ == "__main__":
    main()
