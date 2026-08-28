"""Barrido de factibilidad a costo cero sobre los corpus grandes.

La factibilidad es aritmetica pura sobre lo que la tarea ya declara (feasibility.check),
asi que el claim de regimen entre escalas (135k / 483k / 1.272k tokens) no necesita
gastar un token: se computa para TODOS los tasks x paradigmas y se registra como tabla.
Es la evidencia de P1 (prediccion registrada 2026-08-26 en README).
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
import sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

from app import feasibility
from app.paradigms import REGISTRY

ROOT = Path(__file__).parent
PARAS = sorted(REGISTRY)
CORPORA = ["gold_v2", "gold_wide", "gold_deep", "gold_xl"]

sweep: dict[str, dict] = {}
for corpus in CORPORA:
    docs = json.loads((ROOT / "corpus" / corpus / "documents.json").read_text(encoding="utf-8"))
    tasks = json.loads((ROOT / "corpus" / corpus / "tasks.json").read_text(encoding="utf-8"))
    corpus_tokens = sum(len(v) for v in docs.values()) // feasibility.CHARS_PER_TOKEN
    rows = {}
    for task in tasks:
        _, verdicts = feasibility.admissible(PARAS, docs, task)
        rows[task["task_id"]] = {
            "cell": task["cell"],
            "verdicts": {p: v.as_dict() for p, v in verdicts.items()},
        }
    n_cells = len(tasks) * len(PARAS)
    n_inf = sum(1 for t in rows.values() for v in t["verdicts"].values() if not v["feasible"])
    by_para = {
        p: sum(1 for t in rows.values() if not t["verdicts"][p]["feasible"])
        for p in PARAS
    }
    sweep[corpus] = {
        "corpus_tokens": corpus_tokens,
        "tasks": len(tasks),
        "cells": n_cells,
        "infeasible_cells": n_inf,
        "infeasible_by_paradigm": by_para,
        "rows": rows,
    }
    pruned = ", ".join(f"{p}={n}/{len(tasks)}" for p, n in by_para.items() if n)
    print(f"{corpus:10s} ~{corpus_tokens:>9,} tok  {len(tasks):3d} tareas  "
          f"podadas {n_inf:3d}/{n_cells:3d} celdas  [{pruned or 'ninguna'}]", flush=True)

out = ROOT / "results" / "feasibility_sweep.json"
out.write_text(json.dumps(sweep, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nguardado: {out}")
