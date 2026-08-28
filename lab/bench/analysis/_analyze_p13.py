"""Analisis P13a-P13c: estructura vs juicio en el segundo modelo (gpt-5.4-nano).

Compara por celda (corpus, task, paradigm) la grilla congelada gpt-5-chat contra la
grilla nano. Reglas de la casa: infra_error EXCLUIDO de toda estadistica; `cot` es
control nulo y no se compara; celdas infactibles se reportan aparte (la aritmetica es
identica en ambos modelos, asi que deben coincidir); Δu = u_chat - u_nano sobre la
media por celda.

P13a: estructura (rewoo, extract_compute, streaming_scan, map_reduce en su region
      C2/C4, direct donde factible) sostiene veredicto por celda: Δu <= 0.25.
P13b: juicio (react, reflection, dag_strategy) degrada material: Δu >= 0.25 en al
      menos la mitad de sus celdas factibles.
P13c: determinismo nano: pares de replicas identicos en utilidad en >= 90% de celdas.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent / "results"
CORPORA = ["gold_v2", "gold_deep"]
STRUCTURE = ["rewoo", "extract_compute", "streaming_scan", "map_reduce", "direct"]
MAP_REDUCE_REGION_CELLS = ("C2", "C4")  # "en su region": cobertura independiente
MODEL_CARRIED = ["react", "reflection", "dag_strategy"]


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("infra_error"):
            continue  # se registra y se EXCLUYE
        if r.get("paradigm") == "cot":
            continue  # control nulo
        rows.append(r)
    return rows


def cells(rows: list[dict]) -> dict[tuple, dict]:
    by = defaultdict(list)
    for r in rows:
        by[(r["task_id"], r["paradigm"])].append(r)
    out = {}
    for key, rs in by.items():
        feas = [r for r in rs if not r.get("infeasible")]
        out[key] = {
            "cell": rs[0].get("cell", ""),
            "n": len(feas),
            "infeasible": len(feas) == 0,
            "u": (sum(r["utility"] for r in feas) / len(feas)) if feas else None,
            "utilities": sorted(r["utility"] for r in feas),
            "tok": (sum(r["cost_tokens"] for r in feas) / len(feas)) if feas else 0,
        }
    return out


p13a_hold, p13a_break = [], []
p13b_by_paradigm: dict[str, list[tuple]] = defaultdict(list)
p13c_pairs, p13c_identical = 0, 0
infeas_mismatch = []

for corpus in CORPORA:
    chat = cells(load(ROOT / f"{corpus}_rows.jsonl"))
    nano = cells(load(ROOT / "nano" / f"{corpus}_rows.jsonl"))
    shared = sorted(set(chat) & set(nano))
    print(f"\n=== {corpus} — {len(shared)} celdas compartidas ===")
    print(f"{'task':<12} {'paradigm':<15} {'u_chat':>7} {'u_nano':>7} {'Δu':>6} "
          f"{'tok_chat':>9} {'tok_nano':>9}")
    for key in shared:
        task, para = key
        c, n = chat[key], nano[key]
        if c["infeasible"] != n["infeasible"]:
            infeas_mismatch.append((corpus, task, para, c["infeasible"], n["infeasible"]))
            continue
        if c["infeasible"]:
            print(f"{task:<12} {para:<15} {'INFACTIBLE en ambos':>15}")
            continue
        du = c["u"] - n["u"]
        print(f"{task:<12} {para:<15} {c['u']:>7.3f} {n['u']:>7.3f} {du:>6.2f} "
              f"{c['tok']:>9,.0f} {n['tok']:>9,.0f}")

        # P13c: replicas nano identicas en utilidad
        if n["n"] >= 2:
            p13c_pairs += 1
            if len(set(n["utilities"])) == 1:
                p13c_identical += 1

        # P13a
        in_region = para != "map_reduce" or n["cell"].startswith(MAP_REDUCE_REGION_CELLS)
        if para in STRUCTURE and in_region:
            (p13a_hold if du <= 0.25 else p13a_break).append((corpus, task, para, du))
        # P13b
        if para in MODEL_CARRIED:
            p13b_by_paradigm[para].append((corpus, task, du))

print("\n" + "=" * 70)
print("\n== P13a (estructura sostiene: Δu <= 0.25 por celda) ==")
total = len(p13a_hold) + len(p13a_break)
print(f"  sostienen: {len(p13a_hold)}/{total}")
for corpus, task, para, du in p13a_break:
    print(f"  ROMPE: {corpus}/{task}/{para} Δu={du:.2f}")

print("\n== P13b (juicio degrada: Δu >= 0.25 en >= mitad de celdas factibles) ==")
for para in MODEL_CARRIED:
    rows = p13b_by_paradigm[para]
    hits = [x for x in rows if x[2] >= 0.25]
    verdict = "CUMPLE" if rows and len(hits) >= len(rows) / 2 else "NO cumple"
    print(f"  {para:<13} {len(hits)}/{len(rows)} celdas con Δu>=0.25 -> {verdict}")
    for corpus, task, du in sorted(rows, key=lambda x: -x[2]):
        print(f"      {corpus}/{task}: Δu={du:.2f}")

print("\n== P13c (determinismo nano: replicas identicas en >= 90% de celdas) ==")
pct = 100 * p13c_identical / p13c_pairs if p13c_pairs else 0
print(f"  identicas: {p13c_identical}/{p13c_pairs} ({pct:.1f}%) -> "
      f"{'CUMPLE' if pct >= 90 else 'NO cumple'}")

if infeas_mismatch:
    print("\n!! Desacuerdo de factibilidad entre modelos (no deberia pasar):")
    for m in infeas_mismatch:
        print(f"  {m}")
