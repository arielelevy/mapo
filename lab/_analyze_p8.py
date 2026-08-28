"""Veredicto de P8 — la transferencia a un mundo no visto. Registrada el 2026-08-26.

POR QUE ESTABA SIN EVALUAR. Las cinco predicciones se registraron antes de correr, el
corpus se genero y se corrio, y el veredicto nunca se computo. El paper todavia dice «not
yet run». Apareció barriendo `R-3` — «declarado, no medido» es deuda por regla del repo.

QUE PONE A PRUEBA, Y ES LO MAS GRANDE QUE HAY EN JUEGO. Todos los veredictos por celda de
CONCLUSIONS salieron de mundos con seed 7. `gold_holdout` es seed 23, generado y verificado
independientemente. Si los veredictos no transfieren, no son estructurales: son
sobreajuste al mundo que los produjo.

LA REGLA DE DECISION, TAMBIEN REGISTRADA: si DOS O MAS de P8a-P8e no transfieren,
CONCLUSIONS baja a corpus-local y toda regla por celda tiene que llevar salvedad por mundo.

CADA PREDICCION SE EVALUA COMO ESTA ENUNCIADA. `P8a` dice «u >= 0,9 en TODA celda
factible» — es un criterio POR CELDA, no una media. Evaluarlo sobre el promedio seria
cambiar la prediccion despues de ver los datos, que es exactamente lo que preregistrar
existe para impedir.
"""

import json
import statistics
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from _sanity import paired  # noqa: F401  (disponible para comparaciones pareadas)
from app.config import Settings
from app.runner import Runner

CORPUS = "gold_holdout"


def main() -> None:
    base = Settings.from_env()
    settings = replace(base, results_dir=base.results_dir / "nano")
    runner = Runner(settings, CORPUS, retriever_arm="hybrid", surface_variant="basic")
    rows = [r for r in runner.load_rows() if not r.get("infeasible")]
    if not rows:
        raise SystemExit(f"{CORPUS} sin filas factibles: no hay veredicto que computar")

    celdas = defaultdict(list)
    for r in rows:
        celdas[(r["task_id"], r["paradigm"])].append(r["utility"])
    medias = {k: statistics.mean(v) for k, v in celdas.items()}
    costos = defaultdict(list)
    for r in rows:
        costos[(r["task_id"], r["paradigm"])].append(r["cost_tokens"])
    costo = {k: statistics.mean(v) for k, v in costos.items()}

    tareas = sorted({t for t, _ in medias})
    brazos = sorted({p for _, p in medias})
    print(f"{CORPUS}: {len(rows)} filas · {len(tareas)} tareas · {len(brazos)} brazos\n")
    print("utilidad por celda:")
    print(f"  {'tarea':<16}" + "".join(f"{p[:12]:>14}" for p in brazos))
    for t in tareas:
        fila = "".join(
            f"{medias[(t, p)]:>14.3f}" if (t, p) in medias else f"{'—':>14}"
            for p in brazos
        )
        print(f"  {t:<16}{fila}")

    fallan: list[str] = []
    sin_n: list[str] = []

    def veredicto(nombre: str, ok, detalle: str) -> None:
        """`None` = no se puede evaluar, y NO cuenta como que no transfiere.

        AUSENTE NO ES REFUTADO. La regla de decision cuenta predicciones que FALLAN;
        una que no tiene celdas donde evaluarse no fallo — no se pudo preguntar.
        Meterla en el conteo degradaria CONCLUSIONS por una ausencia de datos, que es
        la version silenciosa del mismo error que `_sanity.required` ataja.
        """
        if ok is None:
            print(f"  {nombre}: SIN N — {detalle}")
            sin_n.append(nombre)
            return
        print(f"  {nombre}: {'TRANSFIERE' if ok else 'NO TRANSFIERE'} — {detalle}")
        if not ok:
            fallan.append(nombre)

    print("\n--- las cinco, cada una como quedo enunciada ---")

    # P8a: react u >= 0.9 en TODA celda factible. Criterio POR CELDA.
    react = {t: u for (t, p), u in medias.items() if p == "react"}
    bajas = {t: u for t, u in react.items() if u < 0.9}
    veredicto("P8a", not bajas,
              f"react bajo 0,9 en {len(bajas)} de {len(react)} celdas"
              + (f" (min {min(bajas.values()):.3f})" if bajas else ""))

    # P8b: map_reduce u = 0 en la celda acoplada (C3).
    mr_c3 = {t: u for (t, p), u in medias.items()
             if p == "map_reduce" and t.startswith("c3")}
    veredicto("P8b",
              all(u == 0.0 for u in mr_c3.values()) if mr_c3 else None,
              f"map_reduce en C3: {mr_c3}" if mr_c3
              else "map_reduce no corrio en este corpus: no se puede evaluar")

    # P8c: rewoo gana C2/C4 barato y falla en acoplada/horizonte.
    def media_en(paradigm: str, prefijos: tuple[str, ...]) -> float | None:
        v = [u for (t, p), u in medias.items()
             if p == paradigm and t.startswith(prefijos)]
        return statistics.mean(v) if v else None

    rw_gana = media_en("rewoo", ("c2", "c4"))
    rw_falla = media_en("rewoo", ("c3", "c5"))
    ok_c = (rw_gana is not None and rw_falla is not None
            and rw_gana > rw_falla)
    veredicto("P8c", ok_c,
              f"rewoo C2/C4 {rw_gana if rw_gana is None else round(rw_gana, 3)} contra "
              f"C3/C5 {rw_falla if rw_falla is None else round(rw_falla, 3)}")

    # P8d: gist_reader u >= 0.75 en C2/C4/C5 y costo <= el de react.
    gr = media_en("gist_reader", ("c2", "c4", "c5"))
    c_gr = [c for (t, p), c in costo.items()
            if p == "gist_reader" and t.startswith(("c2", "c4", "c5"))]
    c_rc = [c for (t, p), c in costo.items()
            if p == "react" and t.startswith(("c2", "c4", "c5"))]
    mas_barato = bool(c_gr and c_rc and statistics.mean(c_gr) <= statistics.mean(c_rc))
    veredicto("P8d", gr is not None and gr >= 0.75 and mas_barato,
              f"gist_reader u={gr if gr is None else round(gr, 3)} en C2/C4/C5, "
              f"costo {statistics.mean(c_gr):,.0f} contra react {statistics.mean(c_rc):,.0f}"
              if c_gr and c_rc else "sin celdas comparables")

    # P8e: dag_strategy en riesgo en la celda acoplada profunda.
    dag_c3 = [(t, celdas[(t, "dag_strategy")], costos[(t, "dag_strategy")])
              for t in tareas if (t, "dag_strategy") in celdas and t.startswith("c3")]
    riesgo = False
    for t, us, cs in dag_c3:
        mediana = statistics.median(cs) if cs else 0
        if any(u == 0.0 for u in us) or (mediana and max(cs) >= 3 * mediana):
            riesgo = True
    veredicto("P8e", riesgo,
              f"dag_strategy en C3: {[(t, [round(u,2) for u in us]) for t, us, _ in dag_c3]}"
              if dag_c3 else "sin celdas C3")

    print(f"\n--- la regla de decision, tambien registrada ---")
    print(f"  no transfieren: {len(fallan)} ({', '.join(fallan) or 'ninguna'})")
    if sin_n:
        print(f"  sin poder evaluarse: {', '.join(sin_n)} — NO cuentan como fallo")
    if len(fallan) >= 2:
        print("  => CONCLUSIONS baja a CORPUS-LOCAL, y toda regla por celda tiene que")
        print("     llevar salvedad por mundo. Los veredictos por celda salieron de")
        print("     mundos seed-7 y este es seed-23.")
    else:
        print("  => CONCLUSIONS se sostiene: los veredictos por celda transfieren")
        print("     a un mundo no visto.")

    out = settings.results_dir / "p8_verdict.json"
    out.write_text(json.dumps({
        "corpus": CORPUS, "filas": len(rows), "tareas": len(tareas),
        "no_transfieren": fallan,
        "sin_n": sin_n,
        "regla": ("corpus-local" if len(fallan) >= 2 else "se sostiene"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nveredicto: {out}")


if __name__ == "__main__":
    main()
