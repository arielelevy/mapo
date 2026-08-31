"""Recomputa `region` bajo `regions/3-literal` sobre el registro vivo. Cero llamadas.

POR QUÉ ESTO ES EL CAMINO DISEÑADO Y NO UN PARCHE. El docstring de `Row` lo dice:

    «La región es una función determinista de los features, pero guardar los features que
     la produjeron permite **recomputarla con un vocabulario nuevo sin volver a correr**.»

Para eso existen los `phi_*`. Cambiar `REGION_VOCABULARY` sin usarlos obligaría a re-correr
un registro pago, o a dejar dos vocabularios conviviendo — y `load_rows` levanta contra eso,
con razón: una región significa lo que su vocabulario dice que significa, así que promediar
dos compara etiquetas que no nombran lo mismo.

QUÉ HACE FALTA ADEMÁS DE LOS `phi_*`. El vocabulario nuevo agrega dos ejes que las filas
viejas no guardaron —`literal` y `cardinality`— y los dos se computan **sin modelo**: uno por
contención de una cadena contra el material, el otro es una declaración del caller. Se
recomputan desde el corpus, que es de donde salen.

LA GUARDA: `n_units` es el único `phi_*` que la región vieja usa y que no se puede derivar de
otra cosa, así que una fila sin `phi_*` NO se migra — se cuenta y se nombra. Adivinarle la
región a una fila que no guardó con qué computarla sería inventar la etiqueta que todo el
análisis usa como clave.

Corre DESDE `lab/`:  py bench/oneoff/_migrar_region_v3.py [--escribir]
"""

from __future__ import annotations

import collections
import json
import shutil
import sys as _sys
import time
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.features import (REGION_VOCABULARY, Features, measure_continuation,
                          measure_question_literal)

SELLADO = "archivo-2026-08-29-pre-K6"
STAMP = time.strftime("%Y%m%d-%H%M%S")


def main() -> None:
    escribir = "--escribir" in sys.argv

    # Corpus disponibles, para los dos ejes nuevos.
    corpus: dict[str, tuple[dict, dict]] = {}
    for tareas_json in _Path("corpus").glob("*/tasks.json"):
        nombre = tareas_json.parent.name
        docs_json = tareas_json.parent / "documents.json"
        if not docs_json.exists():
            continue
        corpus[nombre] = (
            {t["task_id"]: t
             for t in json.loads(tareas_json.read_text(encoding="utf-8"))},
            json.loads(docs_json.read_text(encoding="utf-8")),
        )

    def corpus_de(archivo: _Path) -> str | None:
        base = archivo.name[: -len("_rows.jsonl")]
        cand = [c for c in corpus if base == c or base.startswith(c + "_")]
        return max(cand, key=len) if cand else None

    print("=" * 92)
    print(f"MIGRAR A `{REGION_VOCABULARY}` "
          f"{'— ESCRIBIENDO' if escribir else '(ENSAYO)'}")
    print("=" * 92)

    migradas = sin_phi = sin_corpus = ya = 0
    por_archivo: dict[str, tuple[int, int]] = {}

    for archivo in sorted(_Path("results").rglob("*_rows.jsonl")):
        if SELLADO in archivo.parts:
            continue
        nombre = corpus_de(archivo)
        if nombre is None:
            sin_corpus += 1
            continue
        tareas, docs = corpus[nombre]
        lineas = [l for l in archivo.read_text(encoding="utf-8").splitlines()
                  if l.strip()]
        filas = [json.loads(l) for l in lineas]
        n_mig = n_no = 0
        for f in filas:
            if f.get("region_vocabulary") == REGION_VOCABULARY:
                ya += 1
                continue
            t = tareas.get(f.get("task_id"))
            if t is None or f.get("n_units") is None:
                n_no += 1
                sin_phi += 1
                continue
            feats = Features(
                n_units=int(f["n_units"]),
                has_oracle=bool(f.get("has_oracle")),
                irreversible=bool(t.get("irreversible")),
                shared_writes=bool(t.get("shared_writes")),
                budget_tokens=int(t["budget_tokens"]),
                coupling=f.get("phi_coupling"),
                horizon_unknown=f.get("phi_horizon_unknown"),
                continuation=(f.get("phi_continuation")
                              if "phi_continuation" in f
                              else measure_continuation(docs, t["unit_ids"])),
                cardinality=t.get("answer_cardinality"),
                literal=measure_question_literal(
                    t["question"], docs, t["unit_ids"],
                    cardinality=t.get("answer_cardinality")),
            )
            f["region"] = feats.region()
            f["region_vocabulary"] = REGION_VOCABULARY
            n_mig += 1
            migradas += 1
        if n_mig or n_no:
            por_archivo[str(archivo)] = (n_mig, n_no)
        if n_mig and escribir:
            shutil.copy2(archivo, archivo.with_suffix(f".jsonl.bak-regionv3-{STAMP}"))
            archivo.write_text(
                "\n".join(json.dumps(x, ensure_ascii=False) for x in filas) + "\n",
                encoding="utf-8")

    print(f"\n  {'migradas':>8s} {'sin phi':>8s}  archivo")
    for a, (m, n) in sorted(por_archivo.items()):
        print(f"  {m:8d} {n:8d}  {a}")
    print(f"\n  {migradas} filas migradas · {ya} ya estaban · {sin_phi} sin `phi_*` "
          f"(NO se tocan) · {sin_corpus} archivos sin corpus identificable")
    print(f"  el snapshot `{SELLADO}` queda intacto")

    if not escribir:
        print("\n  Nada se escribio. Para aplicar:  "
              "py bench/oneoff/_migrar_region_v3.py --escribir")


if __name__ == "__main__":
    main()
