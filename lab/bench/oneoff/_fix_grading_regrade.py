"""Re-puntúa todos los result rows tras el fix del substring bidireccional en
grading.score (code-review-2026-08-27.md, C4): `candidate in only` regalaba 1.0 a
todo prefijo/fragmento de la respuesta correcta en oráculos singleton.

No re-corre ningún LLM: recomputa utility desde el `answer` almacenado contra el
oráculo del corpus. Backups timestampeados junto a cada archivo antes de escribir.
Filas infeasible/infra_error no se tocan (su 0.0 no viene de grade()).
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from app.grading import score

ROOT = Path(__file__).parent
STAMP = int(time.time())

oracles: dict[str, dict[str, list[str]]] = {}
for tasks_file in (ROOT / "corpus").glob("*/tasks.json"):
    corpus = tasks_file.parent.name
    oracles[corpus] = {
        t["task_id"]: t["oracle"]
        for t in json.loads(tasks_file.read_text(encoding="utf-8"))
    }


def corpus_of(path: Path) -> str | None:
    stem = path.name[: -len("_rows.jsonl")]
    while stem:
        if stem in oracles:
            return stem
        if "_" not in stem:
            return None
        stem = stem.rsplit("_", 1)[0]
    return None


total_changed = 0
for rows_path in sorted(ROOT.glob("results/**/*_rows.jsonl")):
    if ".bak" in rows_path.name:
        continue
    corpus = corpus_of(rows_path)
    if corpus is None:
        print(f"SKIP (corpus desconocido): {rows_path}")
        continue
    lines = rows_path.read_text(encoding="utf-8").splitlines()
    out, changed = [], []
    for line in lines:
        if not line.strip():
            continue
        r = json.loads(line)
        if not r.get("infeasible") and not r.get("infra_error"):
            oracle = oracles[corpus].get(r["task_id"])
            if oracle is not None:
                new_u = score(r.get("answer", ""), oracle)
                if abs(new_u - r["utility"]) > 1e-9:
                    changed.append(
                        (r["task_id"], r["paradigm"], r.get("trial", 0),
                         r["utility"], new_u)
                    )
                    r["utility"] = new_u
        out.append(json.dumps(r, ensure_ascii=False))
    if changed:
        backup = rows_path.with_name(f"{rows_path.name}.pregrade.{STAMP}.bak")
        backup.write_text("\n".join(lines) + "\n", encoding="utf-8")
        rows_path.write_text("\n".join(out) + "\n", encoding="utf-8")
        total_changed += len(changed)
        rel = rows_path.relative_to(ROOT)
        print(f"\n{rel}: {len(changed)} filas re-puntuadas (backup {backup.name})")
        for task, para, trial, old, new in changed:
            print(f"  {task:<14} {para:<15} t{trial}  {old:.3f} -> {new:.3f}")
print(f"\nTOTAL: {total_changed} filas cambiaron.")
