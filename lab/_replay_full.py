"""Replay sellado del registro COMPLETO: verifica R-1 a escala y mide X-3 gratis.

DOS COSAS DE UNA, y las dos salen del mismo trabajo porque no cuesta un token.

R-1 quedo concluida sobre 27 celdas. Concluir sobre 27 no es concluir sobre 390: alcanza
para demostrar que el mecanismo anda, no para afirmar que el registro entero es
reproducible. Esto lo cierra o lo rompe.

X-3 pregunta si algun paradigma pierde utilidad porque no le sale el FORMATO en vez de
porque no resuelve la tarea. Sobre 27 celdas dio cero malformaciones — que descarta la
explicacion en esa rebanada y no en el resto. Reprocesar todo el registro contesta con la
poblacion entera.

POR QUE ES GRATIS. Todas las completions estan en el cache y el modo sellado prohibe la
llamada viva: si algo intentara salir a la red, levanta en vez de gastar.
"""

import json
import os
import shutil
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.llm import SealedCacheMiss
from app.runner import Runner

CORPUS = os.environ.get("MAPO_REPLAY_CORPUS", "gold_p17")


def main() -> None:
    base = Settings.from_env()
    live = replace(
        base,
        endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
        api_key=os.environ["MAPO_NANO_KEY"],
        chat_deployment="gpt-5.4-nano",
        temperature=0.0,
        results_dir=base.results_dir / "nano",
    )
    print(f"modelo: {live.fingerprint()}", flush=True)

    scratch = live.results_dir / "_replay_full"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)

    reference = Runner(live, CORPUS, retriever_arm="hybrid", surface_variant="basic")
    have = {
        (r["task_id"], r["paradigm"], r.get("trial", 0)): r
        for r in reference.load_rows(include_infra=True)
    }
    paradigms = sorted({k[1] for k in have})
    trials = max(k[2] for k in have) + 1
    print(f"registro: {len(have)} filas · {len(paradigms)} brazos · {trials} trials",
          flush=True)

    runner = Runner(replace(live, results_dir=scratch), CORPUS, sealed=True,
                    retriever_arm="hybrid", surface_variant="basic")
    try:
        rows = runner.run_cross_product(paradigms=paradigms, repeat=trials, resume=False)
    except SealedCacheMiss as exc:
        print(f"\nMISS SELLADO: {exc}")
        raise SystemExit("el registro completo NO se replaya.") from exc

    print(f"\nreplayadas {len(rows)} filas sin una sola llamada viva")

    # --- R-1 a escala -------------------------------------------------------------------
    checked = 0
    diffs: list[str] = []
    for row in rows:
        old = have.get((row.task_id, row.paradigm, row.trial))
        if old is None:
            continue
        checked += 1
        for field in ("utility", "answer", "cost_tokens", "infeasible"):
            if getattr(row, field, None) != old.get(field):
                diffs.append(
                    f"    {row.task_id}/{row.paradigm}/t{row.trial} · {field}"
                )
                break

    print(f"\n--- R-1 sobre el registro completo ---")
    print(f"  celdas comparadas: {checked}")
    print(f"  discrepancias    : {len(diffs)}")
    for d in diffs[:10]:
        print(d)

    # --- X-3 sobre la poblacion entera --------------------------------------------------
    print(f"\n--- X-3: ¿pierde utilidad por el FORMATO o por la tarea? ---")
    agg = defaultdict(lambda: {"n": 0, "mal": 0, "drop": 0, "u": 0.0, "con_mal": 0})
    for row in rows:
        if row.infeasible:
            continue
        tu = row.tool_usage or {}
        a = agg[row.paradigm]
        a["n"] += 1
        a["mal"] += tu.get("malformed_json", 0)
        a["drop"] += tu.get("dropped_items", 0)
        a["u"] += row.utility
        if tu.get("malformed_json", 0):
            a["con_mal"] += 1

    print(f"  {'paradigma':<16}{'filas':>7}{'malform':>9}{'% filas':>9}"
          f"{'dropped':>9}{'util':>8}")
    for p, a in sorted(agg.items()):
        share = a["con_mal"] / a["n"] if a["n"] else 0
        print(f"  {p:<16}{a['n']:>7}{a['mal']:>9}{share:>8.0%}"
              f"{a['drop']:>9}{a['u']/a['n']:>8.3f}")

    # La pregunta que X-3 hace: ¿las filas CON malformacion rinden menos?
    with_mal = [r.utility for r in rows
                if not r.infeasible and (r.tool_usage or {}).get("malformed_json", 0)]
    without = [r.utility for r in rows
               if not r.infeasible and not (r.tool_usage or {}).get("malformed_json", 0)]
    print()
    if with_mal and without:
        gap = sum(with_mal) / len(with_mal) - sum(without) / len(without)
        print(f"  con malformacion  n={len(with_mal):>4}  utilidad {sum(with_mal)/len(with_mal):.3f}")
        print(f"  sin malformacion  n={len(without):>4}  utilidad {sum(without)/len(without):.3f}")
        print(f"  brecha {gap:+.3f}")
    else:
        print(f"  filas con malformacion: {len(with_mal)} — "
              f"el formato NO explica nada en este registro.")

    out = scratch.parent / "replay_full.json"
    out.write_text(json.dumps({
        "corpus": CORPUS,
        "rows_replayed": len(rows),
        "cells_compared": checked,
        "mismatches": len(diffs),
        "per_paradigm": {k: dict(v) for k, v in agg.items()},
        "rows_with_malformed": len(with_mal),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndetalle: {out}")


if __name__ == "__main__":
    main()
