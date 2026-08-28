"""La misma vara para los patrones que YA estan. Cero tokens.

LA INCONSISTENCIA QUE ESTO CIERRA. A un candidato nuevo se le exige prediccion registrada,
criterio de falsacion y que sobreviva a una corrida antes de entrar. A los que ya estaban
no se les exigio nada: entraron por historia. `cot` es la unica excepcion —se retiro por
dominancia, con evidencia— y esa es exactamente la vara que corresponde aplicarle al resto.

EL CRITERIO, QUE ES EL DE `cot`. Un paradigma esta DOMINADO si nunca es unicamente el
mejor y, cuando empata, nunca es el mas barato. Un brazo asi no puede ser la respuesta
correcta a ninguna pregunta: cualquier cosa que el resuelva, otro la resuelve igual o mejor
por el mismo precio o menos. Mantenerlo cuesta grilla —cada celda son tres replicas— y
ensucia el maximo del oraculo, que es el techo contra el que se mide todo lo demas.

LO QUE ESTE AUDIT NO HACE. No mide si un paradigma es BUENO, sino si aporta algo que los
otros no aporten. Un brazo mediocre en todos lados pero unico ganador en una celda se
queda: la utilidad de un catalogo es su cobertura, no su promedio.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")

CORPORA = sys.argv[1:] or [
    "gold_p17", "gold_p16", "gold_transfer", "gold_deep", "gold_v2", "gold_holdout",
]
EPS = 1e-9


def main() -> None:
    # (corpus, tarea) -> paradigma -> (utilidad media, costo medio, veces infactible)
    cells: dict[tuple[str, str], dict[str, list]] = defaultdict(lambda: defaultdict(list))
    infeasible: dict[str, int] = defaultdict(int)
    seen: dict[str, int] = defaultdict(int)

    for corpus in CORPORA:
        try:
            runner = Runner(settings, corpus, retriever_arm="hybrid",
                            surface_variant="basic")
            rows = list(runner.load_rows())
        except FileNotFoundError:
            continue
        for r in rows:
            if r.get("infra_error"):
                continue
            seen[r["paradigm"]] += 1
            if r.get("infeasible"):
                infeasible[r["paradigm"]] += 1
                continue
            cells[(corpus, r["task_id"])][r["paradigm"]].append(
                (r["utility"], r.get("cost_tokens", 0))
            )

    uniquely_best: dict[str, int] = defaultdict(int)
    tied_best: dict[str, int] = defaultdict(int)
    cheapest_when_tied: dict[str, int] = defaultdict(int)
    competed: dict[str, int] = defaultdict(int)

    for arms in cells.values():
        summary = {
            p: (sum(u for u, _ in v) / len(v), sum(c for _, c in v) / len(v))
            for p, v in arms.items() if v
        }
        if len(summary) < 2:
            continue
        for p in summary:
            competed[p] += 1
        top = max(u for u, _ in summary.values())
        winners = [p for p, (u, _) in summary.items() if u >= top - EPS]
        if len(winners) == 1:
            uniquely_best[winners[0]] += 1
            continue
        cheapest = min(winners, key=lambda p: summary[p][1])
        for p in winners:
            tied_best[p] += 1
        cheapest_when_tied[cheapest] += 1

    print(f"Auditoria de dominancia sobre {len(cells)} tareas de "
          f"{len([c for c in CORPORA])} corpus\n")
    print(f"  {'paradigma':<16}{'filas':>7}{'infact.':>9}{'compite':>9}"
          f"{'unico mejor':>13}{'empata':>8}{'+barato':>9}  veredicto")

    verdicts = {}
    for p in sorted(seen, key=lambda x: -uniquely_best[x]):
        n_inf = infeasible[p]
        uniq, tie, cheap, comp = (uniquely_best[p], tied_best[p],
                                  cheapest_when_tied[p], competed[p])
        if comp == 0:
            verdict = "SIN DATOS"
        elif uniq == 0 and cheap == 0:
            verdict = "DOMINADO — retirar"
        elif uniq == 0:
            verdict = "solo por precio"
        else:
            verdict = "aporta cobertura"
        verdicts[p] = {
            "rows": seen[p], "infeasible": n_inf, "competed": comp,
            "uniquely_best": uniq, "tied_best": tie,
            "cheapest_when_tied": cheap, "verdict": verdict,
        }
        print(f"  {p:<16}{seen[p]:>7}{n_inf:>9}{comp:>9}{uniq:>13}{tie:>8}"
              f"{cheap:>9}  {verdict}")

    print("")
    dominated = [p for p, v in verdicts.items() if v["verdict"] == "DOMINADO — retirar"]
    price_only = [p for p, v in verdicts.items() if v["verdict"] == "solo por precio"]
    print(f"  DOMINADOS (nunca unico mejor, nunca el mas barato al empatar): "
          f"{dominated or 'ninguno'}")
    print(f"  Se sostienen SOLO por precio: {price_only or 'ninguno'}")
    print("")
    print("  Un dominado no puede ser la respuesta correcta a ninguna pregunta: lo que")
    print("  resuelve, otro lo resuelve igual o mejor por el mismo precio o menos.")
    print("  Mantenerlo cuesta grilla —tres replicas por celda— y ensucia el maximo del")
    print("  oraculo, que es el techo contra el que se mide todo lo demas.")
    print("")
    print("  Y 'solo por precio' NO es una condena: en un banco donde el costo decide")
    print("  —P16c y P17c lo midieron— un brazo que empata mas barato es exactamente lo")
    print("  que hay que tener. Es una condena para el que no logra ni eso.")

    out = settings.results_dir / "catalog_audit.json"
    out.write_text(json.dumps({
        "corpora": CORPORA, "tasks": len(cells), "paradigms": verdicts,
        "dominated": dominated, "price_only": price_only,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nreporte: {out}")


if __name__ == "__main__":
    main()
