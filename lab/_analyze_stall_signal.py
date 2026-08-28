"""D-1, segunda mitad: recuperada la senal, ¿separa la replica cara de la barata?

LA PRIMERA MITAD dio el tamano del premio: entre replicas de la MISMA celda con la MISMA
utilidad, el 33% del gasto es evitable — 49% en el brazo mas caro. Eso acota lo que
capturaria una regla de parada perfecta.

LA SEGUNDA MITAD es la que decide si la regla es construible. Una regla necesita una senal
que se pueda leer ANTES de decidir seguir, y que discrimine. Las dos que el proyecto creia
tener no servian, por razones DISTINTAS:

  `barren_searches`  es un MEDIDOR que se reinicia al primer acierto, y la fila guarda el
                     valor final. Da 0 casi siempre — no porque no pase, sino porque no se
                     guarda. Se recuperan el PICO y el TOTAL, que si sobreviven.
  `stall_warnings`   solo incrementa en variantes con contabilidad, y TODO estudio medido
                     corrio en `basic`. Su cero dice que el aviso no existe ahi, no que el
                     sistema no se estanque.

Y las dos que si diferian —`units_read` e `iterations`— son proxies del costo mismo: "hizo
mas" cuesta mas por definicion. Una regla de parada basada en eso es circular.

ESTO CORRE SOBRE EL REGISTRO REPLAYADO, no sobre el original: las filas nuevas llevan los
contadores recuperados, y el replay es sellado, asi que no cuesta un token.
"""

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings

REPLAYED = Path("results/nano/_replay_full/gold_p17_rows.jsonl")


def main() -> None:
    if not REPLAYED.exists():
        raise SystemExit(
            f"No esta {REPLAYED}. Corre `_replay_full.py` primero: regenera las filas con "
            f"los contadores recuperados, sellado y sin gastar tokens."
        )
    rows = [json.loads(l) for l in REPLAYED.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if not r.get("infeasible") and not r.get("infra_error")]
    print(f"{len(rows)} filas replayadas\n")

    cells = defaultdict(list)
    for r in rows:
        cells[(r["task_id"], r["paradigm"])].append(r)

    cheap, dear = [], []
    for group in cells.values():
        if len(group) < 2:
            continue
        best = max(r["utility"] for r in group)
        tied = [r for r in group if r["utility"] == best]
        if len(tied) < 2:
            continue
        tied.sort(key=lambda r: r["cost_tokens"])
        if tied[0]["cost_tokens"] == tied[-1]["cost_tokens"]:
            continue
        cheap.append(tied[0])
        dear.append(tied[-1])

    print(f"pares (misma celda, misma utilidad, distinto gasto): {len(cheap)}")
    if not cheap:
        print("Sin pares discriminantes: la pregunta no se puede contestar con esto.")
        return

    print("\n--- ¿alguna senal LEIBLE ANTES de decidir separa las dos mitades? ---")
    SIGNALS = ("barren_peak", "barren_total", "barren_searches", "stall_warnings")
    PROXIES = ("units_read", "iterations")

    def mean(rs, key):
        vals = [(r.get("tool_usage") or {}).get(key, r.get(key, 0)) for r in rs]
        return statistics.mean(vals) if vals else 0.0

    print(f"  {'senal':<20}{'barata':>10}{'cara':>10}{'delta':>10}")
    findings = {}
    for sig in SIGNALS:
        c, d = mean(cheap, sig), mean(dear, sig)
        findings[sig] = d - c
        print(f"  {sig:<20}{c:>10.2f}{d:>10.2f}{d - c:>+10.2f}")
    print(f"  {'-- proxies del costo, no senales --':<20}")
    for sig in PROXIES:
        c, d = mean(cheap, sig), mean(dear, sig)
        print(f"  {sig:<20}{c:>10.2f}{d:>10.2f}{d - c:>+10.2f}")

    live = [k for k, v in findings.items() if abs(v) > 0.05]
    print()
    if live:
        print(f"  senales que discriminan: {', '.join(live)}")
        print("  Una regla de parada es CONSTRUIBLE sobre ellas.")
    else:
        print("  NINGUNA senal propia discrimina.")
        print("  El premio es grande (33% del gasto) y no hay con que capturarlo hoy:")
        print("  las senales de estancamiento no distinguen la replica cara de la barata,")
        print("  y las que si difieren son el costo con otro nombre.")
        print("  Lo que hace falta no es otro contador de actividad: es una senal de")
        print("  SUFICIENCIA — «ya tengo con que responder» — que es una pregunta de")
        print("  contrato, no de conteo.")

    out = Settings.from_env().results_dir / "nano" / "stall_signal.json"
    out.write_text(json.dumps({
        "pairs": len(cheap),
        "deltas": findings,
        "discriminating": live,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndetalle: {out}")


if __name__ == "__main__":
    main()
