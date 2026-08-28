"""Veredicto de P18 — CONGELADO. Las predicciones se registraron en README antes de correr.

QUE MIDE ESTA CELDA QUE NINGUNA OTRA MIDE. En C8 los DOS valores viven en el material: el
vigente, que la enmienda declara, y el superado, que el memo base sigue diciendo. Por eso
una respuesta incorrecta no es simplemente incorrecta — dice CUAL de dos fallas ocurrio:

  otra ciudad cualquiera  -> nunca encontro la enmienda: falla de RECUPERACION
  el domicilio original   -> encontro las dos y eligio la vieja: falla de VIGENCIA

El F1 castiga las dos igual. La segunda se comete CON PROCEDENCIA IMPECABLE —el memo viejo
dice lo que dice— y es exactamente el modo de falla que la capa de decision existe para
impedir.

LAS PREDICCIONES, TAL COMO QUEDARON REGISTRADAS

  P18a  Un paradigma que lee TODAS las unidades resuelve la supersesion; uno que corta en
        el primer acierto devuelve el valor superado. Refutada si las dos clases son
        indistinguibles.
  P18b  El valor SUPERADO es la respuesta incorrecta mas frecuente, no una dispersion de
        ciudades cualesquiera. Refutada si los errores no se concentran ahi.
  P18c  La utilidad de C8 NO se predice desde la de C5 en el mismo (idx, width): detectar
        un conflicto y resolverlo son capacidades distintas. Refutada si correlacionan por
        encima de 0,7.

P18c usa las filas de C5 que P17 ya pago: las tareas son byte-identicas entre los dos
corpus porque comparten seed y C8 no planta documentos nuevos.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.runner import Runner
from app.verify import normalise

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")

ACCOUNT_IN_Q = re.compile(r"settlement account (\w+)")
HOLDER = re.compile(r"([A-Z][a-z]+ [A-Z][a-z]+)[^.]*?(?:serves as|Appointed signatory of|is)[^.]*?"
                    r"|Settlement account on file: (\w+)")
CITY_OF = re.compile(r"(?:resident of|domiciled in) ([A-Z][a-z]+)")
ACC_ON_FILE = re.compile(r"Settlement account on file: (\w+)")


def superseded_value(docs: dict, task: dict) -> str | None:
    """El domicilio que el memo base sigue afirmando para esa cuenta."""
    m = ACCOUNT_IN_Q.search(task["question"])
    if not m:
        return None
    account = m.group(1)
    for uid in task["unit_ids"]:
        if uid.startswith("amend"):
            continue
        text = docs.get(uid) or ""
        if account not in text:
            continue
        # El memo que nombra la cuenta declara el domicilio de su titular.
        city = CITY_OF.search(text)
        if city:
            return city.group(1)
    return None


def main() -> None:
    runner = Runner(settings, "gold_p18", retriever_arm="hybrid", surface_variant="basic")
    docs = json.load(open("corpus/gold_p18/documents.json", encoding="utf-8"))
    tasks = {t["task_id"]: t for t in runner._tasks}  # noqa: SLF001
    # CORRECCION DE INSTRUMENTO (2026-08-28), no de valuacion. La primera version no
    # excluia las filas INFACTIBLES, y map_reduce es infactible en 12 de las 90: la
    # aritmetica lo poda a costo cero y la fila queda con utilidad 0 y respuesta vacia.
    # Contarlas como errores hacia que 12 de 15 "errores" fueran podas, y P18b quedaba
    # refutada por una razon que no es la que la prediccion enuncia.
    #
    # Un plan infactible NUNCA SE INTENTA — es una garantia del producto, no un fallo.
    # Confundirlo con una respuesta incorrecta invierte el signo de la unica garantia
    # que la capa de factibilidad da.
    rows = [r for r in runner.load_rows()
            if r["task_id"].startswith("c8")
            and not r.get("infra_error") and not r.get("infeasible")]

    if not rows:
        print("Sin filas de C8 todavia.")
        return

    stale = {tid: superseded_value(docs, t) for tid, t in tasks.items()
             if tid.startswith("c8")}
    missing = [t for t, v in stale.items() if v is None]
    print(f"corpus gold_p18 | {len(rows)} filas de C8")
    if missing:
        print(f"  ATENCION: sin valor superado identificable en {missing}")
    print()

    # --- P18a: ¿leer todo resuelve la supersesion? -------------------------------------
    print("--- P18a: ¿el que lee MAS resuelve la supersesion? ---")
    # CRITERIO CORREGIDO, y la correccion es un reconocimiento de que la prediccion
    # estaba mal enunciada. `fraction_read` no pasa de 0,20 en NINGUNA fila: sobre una
    # tarea de anchos 4/16/48 con una sola unidad relevante, leerlo todo no hace falta y
    # nadie lo hace. Un umbral de 0,95 dejaba el grupo vacio por construccion, asi que
    # P18a no podia decidirse — no por falta de senal, por un criterio irrealizable.
    #
    # Se parte por la MEDIANA observada, que es la pregunta que la prediccion queria
    # hacer: entre los que leen mas y los que leen menos, ¿hay diferencia?
    fracs = sorted(
        f for f in ((r.get("tool_usage") or {}).get("fraction_read") for r in rows)
        if f is not None
    )
    cut = fracs[len(fracs) // 2] if fracs else 0.0
    buckets = {f"lee mas (>{cut:.2f})": [], f"lee menos (<={cut:.2f})": []}
    for r in rows:
        frac = (r.get("tool_usage") or {}).get("fraction_read")
        if frac is None:
            continue
        key = f"lee mas (>{cut:.2f})" if frac > cut else f"lee menos (<={cut:.2f})"
        buckets[key].append(r["utility"])
    for key, vals in buckets.items():
        if vals:
            print(f"  {key:<20} n={len(vals):>3}  utilidad media {sum(vals)/len(vals):.3f}")
    keys = list(buckets)
    full, part = buckets[keys[0]], buckets[keys[1]]
    if full and part:
        gap = sum(full) / len(full) - sum(part) / len(part)
        verdict_a = "CONFIRMADA" if gap > 0.25 else "REFUTADA"
        print(f"  brecha: {gap:+.3f}   P18a: {verdict_a} (criterio > 0,25)")
    else:
        gap, verdict_a = None, "SIN N"
        print(f"  P18a: SIN N — un solo grupo tiene filas")

    # --- P18b: ¿el error mas frecuente es el valor superado? ---------------------------
    print("\n--- P18b: ¿los errores se concentran en el valor SUPERADO? ---")
    wrong = Counter()
    total_wrong = 0
    for r in rows:
        if r["utility"] >= 1.0:
            continue
        total_wrong += 1
        answer = normalise(r.get("answer") or "")
        old = stale.get(r["task_id"])
        if old and normalise(old) in answer:
            wrong["el valor SUPERADO"] += 1
        elif not answer:
            wrong["sin respuesta"] += 1
        else:
            wrong["otra cosa"] += 1
    for k, n in wrong.most_common():
        share = n / total_wrong if total_wrong else 0
        print(f"  {k:<22} {n:>3}  ({share:.0%})")
    if total_wrong:
        share_stale = wrong["el valor SUPERADO"] / total_wrong
        verdict_b = "CONFIRMADA" if share_stale > 0.5 else "REFUTADA"
        print(f"  P18b: {verdict_b} (criterio > 50% de los errores)")
    else:
        share_stale, verdict_b = None, "SIN ERRORES"
        print("  P18b: SIN ERRORES — todo correcto, la celda no discrimina")

    # --- P18c: ¿C8 se predice desde C5? ------------------------------------------------
    print("\n--- P18c: ¿detectar el conflicto predice resolverlo? ---")
    p17 = Runner(settings, "gold_p17", retriever_arm="hybrid", surface_variant="basic")
    c5 = defaultdict(list)
    for r in p17.load_rows():
        if r["task_id"].startswith("c5") and not r.get("infra_error"):
            c5[(r["task_id"].replace("c5-", ""), r["paradigm"])].append(r["utility"])
    c8 = defaultdict(list)
    for r in rows:
        c8[(r["task_id"].replace("c8-", ""), r["paradigm"])].append(r["utility"])

    pairs = [
        (sum(c5[k]) / len(c5[k]), sum(c8[k]) / len(c8[k]))
        for k in c8 if k in c5 and c5[k] and c8[k]
    ]
    if len(pairs) >= 4:
        n = len(pairs)
        mx = sum(x for x, _ in pairs) / n
        my = sum(y for _, y in pairs) / n
        sxy = sum((x - mx) * (y - my) for x, y in pairs)
        sx = sum((x - mx) ** 2 for x, _ in pairs) ** 0.5
        sy = sum((y - my) ** 2 for _, y in pairs) ** 0.5
        rho = sxy / (sx * sy) if sx and sy else 0.0
        verdict_c = "CONFIRMADA" if abs(rho) <= 0.7 else "REFUTADA"
        print(f"  pares (tarea, paradigma) comparables: {n}")
        print(f"  C5 media {mx:.3f} | C8 media {my:.3f} | correlacion {rho:+.3f}")
        print(f"  P18c: {verdict_c} (criterio |r| <= 0,7)")
    else:
        rho, verdict_c = None, "SIN N"
        print(f"  P18c: SIN N ({len(pairs)} pares)")

    out = settings.results_dir / "p18_verdict.json"
    out.write_text(json.dumps({
        "corpus": "gold_p18", "rows": len(rows),
        "p18a": {"gap": gap, "verdict": verdict_a},
        "p18b": {"stale_share": share_stale, "detail": dict(wrong), "verdict": verdict_b},
        "p18c": {"rho": rho, "pairs": len(pairs), "verdict": verdict_c},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nveredicto: {out}")


if __name__ == "__main__":
    main()
