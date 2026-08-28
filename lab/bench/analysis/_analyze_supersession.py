"""O-1: ¿que paradigma respeta la supersesion? Cero tokens, sobre filas ya pagadas.

EL EJE MAS BARATO QUE NADIE MIDIO. El corpus trae enmiendas con la precedencia ESCRITA, no
inferida: «The domicile of record associated with settlement account AR2936541590 is
Rosario. This filing supersedes any earlier domicile on record for that account.» Hay verbo
de precedencia, alcance declarado y limite declarado. Todo verificable por codigo. Y
ninguna prediccion registrada lo usa.

QUE SEPARA ESTE ANALISIS, Y ES LA RAZON DE QUE VALGA. Una respuesta incorrecta esconde dos
fallas que no son la misma:

  (a) NO ENCONTRO el dato — falla de recuperacion. El paradigma no llego al documento.
  (b) ENCONTRO EL VIEJO — falla de VIGENCIA. Llego a los dos documentos, y eligio el
      superado. Peor: eligio con evidencia impecable, porque el memo viejo dice lo que
      dice.

El F1 contra gold castiga las dos igual y no las distingue. Es exactamente «la atribucion
exige la traza» (paper §8.4) aplicado a un eje nuevo: sin separar (a) de (b), un arreglo de
recuperacion se le acredita a un problema de precedencia y viceversa.

Y (b) es la que le importa a este producto. Un sistema que devuelve el valor superado con
procedencia perfecta es exactamente lo que la capa de decision existe para impedir.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import re
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner
from app.verify import normalise

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")

CORPORA = sys.argv[1:] or ["gold_p17", "gold_p16", "gold_transfer", "gold_deep"]

# Vocabulario CERRADO, no parseo de prosa: la enmienda declara cuenta y valor en una forma
# fija que el generador produce, y se leen esos dos campos.
ACCOUNT = re.compile(r"settlement account (\w+)")
DOMICILE = re.compile(r"domicile of record associated with settlement account \w+ is ([A-Z][a-z]+)")


def main() -> None:
    print("O-1 — ¿que paradigma respeta la supersesion?\n")
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for corpus in CORPORA:
        try:
            runner = Runner(settings, corpus, retriever_arm="hybrid",
                            surface_variant="basic")
            docs = json.load(open(f"corpus/{corpus}/documents.json", encoding="utf-8"))
            rows = list(runner.load_rows())
            tasks = {t["task_id"]: t for t in runner._tasks}  # noqa: SLF001
        except FileNotFoundError:
            continue

        # La enmienda declara: cuenta -> valor nuevo. Y el memo viejo tiene otro valor
        # para la misma cuenta: ese es el superado.
        current: dict[str, str] = {}
        for uid, text in docs.items():
            if not uid.startswith("amend"):
                continue
            acc = ACCOUNT.search(text)
            dom = DOMICILE.search(text)
            if acc and dom:
                current[acc.group(1)] = dom.group(1)

        superseded: dict[str, set[str]] = defaultdict(set)
        for uid, text in docs.items():
            if uid.startswith("amend"):
                continue
            for acc in ACCOUNT.findall(text):
                if acc not in current:
                    continue
                # El domicilio que ESE memo asocia a la cuenta.
                for m in re.finditer(r"(?:resident of|domiciled in) ([A-Z][a-z]+)", text):
                    value = m.group(1)
                    if normalise(value) != normalise(current[acc]):
                        superseded[acc].add(value)

        if not current:
            continue

        stale_values = {normalise(v) for vs in superseded.values() for v in vs}
        fresh_values = {normalise(v) for v in current.values()}
        contested = stale_values - fresh_values
        if not contested:
            continue

        affected = [
            t for t in tasks.values()
            if any(normalise(o) in fresh_values for o in (t.get("oracle") or []))
        ]
        print(f"{corpus}: {len(current)} cuentas enmendadas | "
              f"{len(affected)} tareas cuyo gold es el valor VIGENTE")

        for r in rows:
            if r.get("infra_error") or r.get("infeasible"):
                continue
            task = tasks.get(r["task_id"])
            if task is None or task not in affected:
                continue
            answer = normalise(r.get("answer") or "")
            p = r["paradigm"]
            totals[p]["intentos"] += 1
            if r["utility"] >= 1.0:
                totals[p]["correcto"] += 1
            elif any(v in answer for v in contested):
                totals[p]["devolvio_superado"] += 1
            else:
                totals[p]["fallo_otro"] += 1

    if not totals:
        print("\nNinguna tarea del registro tiene su gold en un valor enmendado.")
        print("La supersesion esta en el MATERIAL y ninguna pregunta la interroga —")
        print("que es, en si mismo, el hallazgo: el eje existe y el corpus no lo usa.")
        return

    print(f"\n  {'paradigma':<16}{'intentos':>10}{'correcto':>10}"
          f"{'DEVOLVIO SUPERADO':>20}{'fallo otro':>12}")
    for p in sorted(totals, key=lambda x: -totals[x]["devolvio_superado"]):
        d = totals[p]
        print(f"  {p:<16}{d['intentos']:>10}{d['correcto']:>10}"
              f"{d['devolvio_superado']:>20}{d['fallo_otro']:>12}")


if __name__ == "__main__":
    main()
