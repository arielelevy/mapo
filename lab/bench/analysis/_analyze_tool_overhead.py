"""X-4d: descontar la declaracion de tools, y ver si algun veredicto de lambda se movia.

QUE SE PREGUNTA, Y POR QUE ES LA PRIMERA DE LA FAMILIA. Las specs de tools se re-envian en
cada llamada QUE LAS LLEVA — que no son todas: de 27 sitios que llaman al modelo, uno pasa
`tools`. Medido con `tooled_calls`: 6,7% del gasto, repartido `dag_strategy` 8,0%,
`react` 4,5% y `rewoo` 0,0%.

Ese sobrecosto NO ES UNA PROPIEDAD DEL PARADIGMA: es una propiedad de cuantas veces llama
al bucle de tools, multiplicada por un tamano de spec que es del harness. La pregunta es si
el barrido de lambda —que decide que paradigma conviene— sobrevive a sacarselo.

Esto no cuesta un token: el registro se replaya sellado y se recomputa.

UNA VERSION ANTERIOR DE ESTE SCRIPT ESTIMABA EL SOBRECOSTO POR `calls`, y era falso: suponia
que toda llamada lleva la declaracion. Daba 43% para `rewoo`, que en realidad es CERO, y en
7 celdas producia mas declaracion que prompt entero. Ahora se descuenta por `tooled_calls`,
y si una celda no lo registra el script SE NIEGA a descontar en vez de estimar.

LO QUE DECIDE. Si al descontarlo ningun veredicto se mueve, el resto de X-4 —cache de
prompt, acortar descripciones— es OPTIMIZACION y no correccion. Si alguno se mueve, hay un
resultado publicado que hay que revisar.

LO QUE NO ES. No es una propuesta de cambiar como se cobra el costo. Cobrar la declaracion
es correcto: se paga de verdad. La pregunta es si la COMPARACION entre brazos sobrevive a
sacarla, que es distinto.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import sys
from dataclasses import replace
from typing import Any

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.metrics import Observation, Study
from app.runner import Runner
from app.tools import specs_for
from bench._sanity import share

# Solo `gold_p17`, que es el unico replayado con el contador nuevo. Los otros dos
# necesitan su propio replay sellado; incluirlos sin el contador daria un descuento
# de cero disfrazado de medicion.
CORPORA = ["gold_p17"]
LAMBDAS = (0.0, 0.02, 0.05, 0.10)


def spec_tokens(variant: str) -> int:
    return len(json.dumps(specs_for(variant), ensure_ascii=False)) // 4


def tooled(row: dict[str, Any]) -> int | None:
    """Llamadas que LLEVARON la declaracion. `None` si la fila no lo registra.

    AUSENTE NO ES CERO. Una fila anterior al contador no dice «no llevo declaracion»:
    dice que no se sabe. Leerla como cero descontaria de menos y haria pasar por
    resultado un promedio sobre filas que no se pueden descontar.
    """
    tu = row.get("tool_usage") or {}
    return tu.get("tooled_calls") if "tooled_calls" in tu else None


def observations(rows: list[dict[str, Any]], discount: int) -> list[Observation] | None:
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
        counts = [tooled(x) for x in group]
        if any(c is None for c in counts):
            return None  # el registro no permite descontar: se dice, no se estima
        calls = sum(counts) / n
        # `max(..., 1)`: descontar no puede producir un costo cero o negativo. Si el
        # sobrecosto estimado supera al costo registrado, lo que hay es una fila cuyo
        # `calls` y `cost_tokens` no son coherentes, y aplastarlo a 1 lo deja visible en
        # el ratio en vez de romper la division.
        if discount:
            # POR CELDA, que es donde la imposibilidad se ve. El agregado la esconde:
            # 82.368 sobre 189.899 es posible, y `c1-000` con 1.056 de declaracion sobre
            # 664 de prompt no lo es. Y el `max(...,1)` que habia acá aplastaba el piso y
            # produjo utilidades de -463 que se leyeron como «la brecha cae a cero».
            share(discount * calls, cost, f"declaracion/gasto {task_id}/{paradigm}")
        adjusted = int(cost - discount * calls) if discount else int(cost)
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
        replayed = settings.results_dir / "_replay_full" / f"{corpus}_rows.jsonl"
        if not replayed.exists():
            print(f"{corpus}: sin replay con el contador. Corre `_replay_full.py` primero.")
            continue
        rows = [json.loads(l) for l in
                replayed.read_text(encoding="utf-8").splitlines() if l.strip()]
        rows = [r for r in rows if not r.get("infeasible")]
        if not rows:
            print(f"{corpus}: sin filas factibles")
            continue

        print(f"--- {corpus} ({len(rows)} filas) ---")
        print(f"  {'lambda':>7} | {'mejor fijo':<28} | {'brecha de oraculo':>20}")
        print(f"  {'':>7} | {'con decl.':<13}{'sin decl.':<15} | {'con':>9}{'sin':>11}")

        per_corpus = {}
        for lam in LAMBDAS:
            obs_with, obs_without = observations(rows, 0), observations(rows, overhead)
            if obs_without is None:
                print("  el registro no lleva `tooled_calls` en toda celda: no se descuenta")
                break
            with_o = Study(obs_with, lambda_cost=lam)
            without = Study(obs_without, lambda_cost=lam)
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
