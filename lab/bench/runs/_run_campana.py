"""La campaña que cierra los 8 «implementado, falta correr». Tres corridas, no ocho.

EL DISEÑO MAGRO, y por que se saca `dag_strategy`. Es el 58% del costo de la campaña y lo
medido hoy no lo justifica: compra **+0,030 de utilidad** sobre `rewoo` a **11,5x la
latencia** (leccion 5.19) y ~35x los tokens. No es un recorte de conveniencia — es la
misma decision que ya se tomo con `map_reduce`, con la evidencia al lado.

EL ORDEN NO ES ARBITRARIO. `A` primero porque `P26d` es la unica prediccion de toda la
campaña que puede TIRAR ABAJO TRABAJO YA HECHO: si el orden de los paradigmas cambia con el
brazo de recuperacion, toda comparacion entre brazos de este banco es condicional a una
constante que nadie vario. Es la mas barata Y la de mayor riesgo, asi que va primero y las
demas esperan su resultado.

  A   {hybrid, hybrid_hyde}          cierra H-3, AR-3, AR-4     P26a-d
  B   obligaciones en gold_guards    cierra O-2, O-3            P25a-d
  C   handoff + read_all + terse     cierra D-4, D-1b, X-4c     P23, P21, P24

`hybrid` en A sale casi entero del cache: los payloads no cambiaron con los factores
apagados, asi que lo que se paga de verdad es el brazo nuevo.

RESUMIBLE POR `(task, paradigm, trial)`. Si se corta, volver a lanzarlo continua — no
reempieza. Por eso cada corrida es su propia invocacion y no un solo proceso largo.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import argparse
import os
import statistics
import sys
import time
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner

# SIN `dag_strategy`, y la evidencia va en el docstring. Sin `map_reduce`, que esta en
# standby por decision del autor y el runner se niega a correrlo.
BRAZOS = ["gist_reader", "react", "rewoo"]
REPEAT = 3

CORRIDAS = {
    "A": dict(corpus="gold_p18", brazos=BRAZOS, arms=["hybrid", "hybrid_hyde"],
              factores={}, cierra="H-3, AR-3, AR-4"),
    "B": dict(corpus="gold_guards", brazos=BRAZOS, arms=["hybrid"],
              factores={"demand_obligations": True}, cierra="O-2, O-3"),
    "C1": dict(corpus="gold_p18", brazos=BRAZOS + ["handoff"], arms=["hybrid"],
               factores={}, cierra="D-4 (handoff entra al catalogo medido)"),
    "C2": dict(corpus="gold_p18", brazos=BRAZOS, arms=["hybrid"],
               factores={"offer_read_all": True}, cierra="D-1b"),
    "C3": dict(corpus="gold_p18", brazos=BRAZOS, arms=["hybrid"],
               factores={"terse_tools": True}, cierra="X-4c"),
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--que", required=True, choices=sorted(CORRIDAS),
                    help="cual corrida de la campaña")
    args = ap.parse_args()
    plan = CORRIDAS[args.que]

    base = Settings.from_env()
    s = replace(
        base,
        endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
        api_key=os.environ["MAPO_NANO_KEY"],
        chat_deployment="gpt-5.4-nano",
        temperature=0.0,
        results_dir=base.results_dir / "nano",
    )
    print(f"=== {args.que} · cierra {plan['cierra']}")
    print(f"corpus {plan['corpus']} · brazos {plan['brazos']} · repeat {REPEAT}")
    print(f"retriever {plan['arms']} · factores {plan['factores'] or '(ninguno)'}",
          flush=True)

    for arm in plan["arms"]:
        runner = Runner(s, plan["corpus"], retriever_arm=arm, surface_variant="basic",
                        **plan["factores"])
        print(f"\n--- {arm} -> {runner._results_path.name}", flush=True)  # noqa: SLF001
        t0 = time.perf_counter()
        filas = runner.run_cross_product(paradigms=plan["brazos"], repeat=REPEAT)
        if not filas:
            print("  0 filas nuevas: ya estaba entero en el registro", flush=True)
            continue
        infra = sum(1 for r in filas if r.infra_error)
        buenas = [r for r in filas if not r.error]
        print(f"  filas {len(filas)} ({infra} infra_error, fuera de toda estadistica)")
        print(f"  tokens {sum(r.cost_tokens for r in filas):,} · "
              f"u media {statistics.mean(r.utility for r in buenas):.4f} · "
              f"wall {(time.perf_counter() - t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
