"""P-2c: ¿el ORDEN de llamadas lleva informacion que el CONTEO no lleva? Cero tokens.

LA PREGUNTA, Y POR QUE TIENE UNA RESPUESTA HONESTA POSIBLE. El peso Hebbiano por
`(region, paradigma)` esta demostrado redundante para elegir paradigma: es una
transformacion monotona de la tasa de victorias. Esa demostracion depende de que la
estadistica sea MARGINAL. Una asociacion `(a -> b)` no lo es — y la pregunta empirica es
si esa diferencia estructural se traduce en informacion real, o si el orden que un
paradigma produce esta tan determinado por el paradigma que la transicion no agrega nada.

EL TEST, Y ES FALSABLE. Si el orden fuera puro habito del paradigma, entonces conocer el
paradigma haria irrelevante conocer la transicion: dentro de un mismo paradigma todas las
transiciones tendrian la misma tasa de exito. Se mide exactamente eso — la DISPERSION de
tasas de exito entre transiciones, dentro de cada paradigma. Dispersion cero significa que
el orden no discrimina y que P-2c no vale la pena.

QUE NO PRUEBA. Correlacion, no causalidad: una transicion presente en episodios buenos no
es responsable de que hayan salido bien. Alcanza para un prior, que es todo lo que se le
va a pedir, y no alcanza para gobernar nada por si sola.
"""

import json
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.association import END, START, AssociationTable
from app.config import Settings
from app.runner import Runner

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")

CORPORA = sys.argv[1:] or ["gold_p17", "gold_transfer", "gold_p16"]
GOOD = 1.0  # un episodio es bueno si resolvio la tarea


def main() -> None:
    table = AssociationTable()
    per_paradigm: dict[str, list[tuple[str, str, bool]]] = defaultdict(list)
    rows_used = rows_total = 0

    for corpus in CORPORA:
        try:
            runner = Runner(settings, corpus, retriever_arm="hybrid",
                            surface_variant="basic")
            rows = list(runner.load_rows())
        except FileNotFoundError:
            continue
        for r in rows:
            rows_total += 1
            sequence = (r.get("tool_usage") or {}).get("sequence")
            if not sequence:
                continue
            rows_used += 1
            good = r["utility"] >= GOOD
            table.observe(r["paradigm"], sequence, good)
            steps = [START, *sequence, END]
            for a, b in zip(steps, steps[1:]):
                per_paradigm[r["paradigm"]].append((a, b, good))

    print(f"filas con secuencia: {rows_used}/{rows_total} sobre {', '.join(CORPORA)}")
    print(f"transiciones distintas aprendidas: {len(table.links)}\n")

    if not rows_used:
        print("Sin secuencias todavia: la instrumentacion es nueva y solo las corridas")
        print("posteriores la traen. Volver a correr esto cuando P17 termine.")
        return

    # --- el test: ¿el orden discrimina ADENTRO de un paradigma? ------------------------
    print("¿El orden lleva informacion que el paradigma solo no lleva?\n")
    print(f"  {'paradigma':<16}{'transic.':>9}{'obs':>7}{'tasa min':>10}"
          f"{'tasa max':>10}{'dispersion':>12}")
    verdict_rows = {}
    for paradigm in sorted(per_paradigm):
        agg: dict[tuple[str, str], list[bool]] = defaultdict(list)
        for a, b, good in per_paradigm[paradigm]:
            agg[(a, b)].append(good)
        # Sólo transiciones con evidencia suficiente para que una tasa signifique algo.
        rates = [sum(v) / len(v) for v in agg.values() if len(v) >= 5]
        if len(rates) < 2:
            print(f"  {paradigm:<16}{len(agg):>9}{sum(len(v) for v in agg.values()):>7}"
                  f"{'—':>10}{'—':>10}{'sin n':>12}")
            continue
        lo, hi = min(rates), max(rates)
        mean = sum(rates) / len(rates)
        var = sum((x - mean) ** 2 for x in rates) / len(rates)
        print(f"  {paradigm:<16}{len(agg):>9}{sum(len(v) for v in agg.values()):>7}"
              f"{lo:>10.3f}{hi:>10.3f}{var ** 0.5:>12.4f}")
        verdict_rows[paradigm] = {"transitions": len(agg), "min": round(lo, 4),
                                  "max": round(hi, 4), "sd": round(var ** 0.5, 4)}

    if verdict_rows:
        worst = max(v["sd"] for v in verdict_rows.values())
        print("")
        print("  Dispersion CERO significaria que, dentro de un paradigma, todas las")
        print("  transiciones rinden igual — o sea que el orden es puro habito y P-2c no")
        print(f"  vale la pena. La mayor dispersion medida es {worst:.4f}.")
        print("")
        if worst < 0.05:
            print("  LECTURA: el orden NO discrimina. La asociacion entre pares no compra")
            print("  nada sobre conocer el paradigma, y P-2c se cierra como negativo.")
        else:
            print("  LECTURA: el orden SI discrimina adentro del paradigma. La asociacion")
            print("  entre pares lleva informacion que el conteo no lleva — condicion")
            print("  NECESARIA para P-2c, y todavia no suficiente: falta que sirva para")
            print("  decidir algo, medido con el costo cobrado.")

    print("\ntransiciones mejor sostenidas, por paradigma:")
    for paradigm in sorted(per_paradigm):
        top = table.successors(paradigm, START)[:2]
        after_search = table.successors(paradigm, "search")[:2]
        shown = " | ".join(f"{START}->{b}:{w:.2f}" for b, w in top)
        shown2 = " | ".join(f"search->{b}:{w:.2f}" for b, w in after_search)
        print(f"  {paradigm:<16}{shown}   {shown2}")

    out = settings.results_dir / "associations.json"
    out.write_text(json.dumps({
        "corpora": CORPORA, "rows_used": rows_used, "rows_total": rows_total,
        "links": len(table.links), "dispersion": verdict_rows,
        "table": table.as_dict(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nreporte: {out}")


if __name__ == "__main__":
    main()
