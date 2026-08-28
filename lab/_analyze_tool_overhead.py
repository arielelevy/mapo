"""X-4d: descontar la declaracion de tools, y ver si algun veredicto de lambda se movia.

QUE SE PREGUNTA, Y POR QUE ES LA PRIMERA DE LA FAMILIA. Las specs de tools se re-envian en
CADA llamada. Medido: 7,7% del gasto total en `gold_p17`/`basic`. Pero el numero que
importa no es ese sino su DISPERSION — `rewoo` carga 43,4% de declaracion contra 3,8% de
`gist_reader`, un factor de diez.

Y ese sobrecosto NO ES UNA PROPIEDAD DEL PARADIGMA: es una propiedad de cuantas veces
llama, multiplicada por un tamano de spec que es del harness. El barrido de lambda —que
decide que paradigma conviene— compara brazos cargando cada uno con un fijo distinto que
no le pertenece.

Esto no cuesta un token: el sobrecosto es `llamadas x tokens_de_spec`, y las dos cantidades
ya estan en la fila.

LO QUE DECIDE. Si al descontarlo ningun veredicto se mueve, el resto de X-4 —cache de
prompt, acortar descripciones— es OPTIMIZACION y no correccion. Si alguno se mueve, hay un
resultado publicado que hay que revisar.

LO QUE NO ES. No es una propuesta de cambiar como se cobra el costo. Cobrar la declaracion
es correcto: se paga de verdad. La pregunta es si la COMPARACION entre brazos sobrevive a
sacarla, que es distinto.
"""

import json
import sys
from dataclasses import replace
from typing import Any

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.metrics import Observation, Study
from app.runner import Runner
from app.tools import specs_for

CORPORA = ["gold_p17", "gold_p16", "gold_transfer"]
LAMBDAS = (0.0, 0.02, 0.05, 0.10)


def spec_tokens(variant: str) -> int:
    return len(json.dumps(specs_for(variant), ensure_ascii=False)) // 4


def observations(rows: list[dict[str, Any]], discount: int) -> list[Observation]:
    """Celdas promediadas por trial, con el sobrecosto descontado o no.

    Se promedia por celda ANTES de tomar el oraculo, igual que `runner.study`: alimentar
    trials crudos dejaria que el oraculo elija la muestra mas afortunada de cada brazo.
    """
    cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rows:
        cells.setdefault((r["task_id"], r["paradigm"]), []).append(r)

    out = []
    for (task_id, paradigm), group in sorted(cells.items()):
        n = len(group)
        cost = sum(x["cost_tokens"] for x in group) / n
        calls = sum(x.get("calls", 0) for x in group) / n
        # `max(..., 1)`: descontar no puede producir un costo cero o negativo. Si el
        # sobrecosto estimado supera al costo registrado, lo que hay es una fila cuyo
        # `calls` y `cost_tokens` no son coherentes, y aplastarlo a 1 lo deja visible en
        # el ratio en vez de romper la division.
        adjusted = max(int(cost - discount * calls), 1) if discount else int(cost)
        out.append(Observation(
            task_id=task_id,
            region=group[0]["region"],
            paradigm=paradigm,
            utility=sum(x["utility"] for x in group) / n,
            cost_tokens=adjusted,
            has_oracle=group[0].get("has_oracle", True),
        ))
    return out


def main() -> None:
    base = Settings.from_env()
    settings = replace(base, results_dir=base.results_dir / "nano")
    overhead = spec_tokens("basic")
    print(f"declaracion en `basic`: {overhead} tokens por llamada\n")

    verdict: dict[str, Any] = {}
    moved = []

    for corpus in CORPORA:
        if not (settings.corpus_dir / corpus).is_dir():
            print(f"{corpus}: ausente, declarado y no ignorado")
            continue
        runner = Runner(settings, corpus, retriever_arm="hybrid",
                        surface_variant="basic")
        rows = [r for r in runner.load_rows() if not r.get("infeasible")]
        if not rows:
            print(f"{corpus}: sin filas factibles")
            continue

        print(f"--- {corpus} ({len(rows)} filas) ---")
        print(f"  {'lambda':>7} | {'mejor fijo':<28} | {'brecha de oraculo':>20}")
        print(f"  {'':>7} | {'con decl.':<13}{'sin decl.':<15} | {'con':>9}{'sin':>11}")

        per_corpus = {}
        for lam in LAMBDAS:
            with_o = Study(observations(rows, 0), lambda_cost=lam)
            without = Study(observations(rows, overhead), lambda_cost=lam)
            b1, b2 = with_o.best_fixed(), without.best_fixed()
            g1, g2 = with_o.oracle_gap(), without.oracle_gap()
            flag = "  <- CAMBIA" if b1 != b2 else ""
            print(f"  {lam:>7.2f} | {b1:<13}{b2:<15} | {g1:>9.4f}{g2:>11.4f}{flag}")
            per_corpus[str(lam)] = {
                "best_with": b1, "best_without": b2,
                "gap_with": g1, "gap_without": g2,
            }
            if b1 != b2:
                moved.append(f"{corpus} @ lambda={lam}: {b1} -> {b2}")
        verdict[corpus] = per_corpus
        print()

    print("--- veredicto ---")
    if moved:
        print("  El mejor fijo CAMBIA al descontar la declaracion:")
        for m in moved:
            print(f"    {m}")
        print("  => hay un resultado publicado que revisar, y el resto de X-4 es")
        print("     correccion y no optimizacion.")
    else:
        print("  Ningun mejor fijo cambia al descontar la declaracion.")
        print("  => la comparacion entre brazos SOBREVIVE al sobrecosto, y el resto de")
        print("     X-4 (cache de prompt, acortar descripciones) es OPTIMIZACION, no")
        print("     correccion. Baja su urgencia, no su valor.")

    out = settings.results_dir / "tool_overhead.json"
    out.write_text(json.dumps({
        "spec_tokens_basic": overhead,
        "per_corpus": verdict,
        "best_fixed_changes": moved,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndetalle: {out}")


if __name__ == "__main__":
    main()
