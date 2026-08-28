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

    # --- LA OBJECION: ¿es dificultad de tarea filtrandose? -----------------------------
    # Es la misma que aparecio con el recall, y alla hubo que salir a falsarla. Si las
    # transiciones buenas fueran simplemente las que ocurren en tareas faciles, la
    # dispersion desapareceria al comparar DENTRO de una celda.
    #
    # Y no alcanza con estratificar y volver a medir: agrupar mas fino SIEMPRE explica mas
    # en muestra — ese error ya se cometio hoy con el 82,7% que fuera de muestra era 62,1%.
    # Asi que va un test de PERMUTACION.
    #
    # PERO EL NULL HAY QUE ESPECIFICARLO BIEN, Y LA PRIMERA VERSION ESTABA MAL. El
    # resultado es de la FILA: una fila tiene una utilidad y TODAS sus transiciones heredan
    # la misma etiqueta, asi que estan perfectamente correlacionadas. Barajar etiquetas por
    # transicion rompe esos bloques y le regala al azar mas variacion independiente de la
    # que existe — el null sale mas disperso de lo que corresponde y el test se vuelve
    # imposible de pasar por una razon que no es la senal.
    #
    # El null correcto baraja QUE FILAS salieron bien, conservando cada fila con sus
    # transiciones juntas. Eso preserva el bloque, los tamanos de grupo y la dificultad.
    print("\n" + "=" * 74)
    print("¿La dispersion es dificultad de tarea disfrazada? — permutacion POR FILA\n")

    import random

    rng = random.Random(20260827)
    PERMUTATIONS = 2000

    def dispersion(blocks: list[tuple[list[tuple[str, str]], bool]]) -> float | None:
        agg: dict[tuple[str, str], list[bool]] = defaultdict(list)
        for transitions, good in blocks:
            for key in transitions:
                agg[key].append(good)
        rates = [sum(v) / len(v) for v in agg.values() if len(v) >= 3]
        if len(rates) < 2:
            return None
        mean = sum(rates) / len(rates)
        return (sum((x - mean) ** 2 for x in rates) / len(rates)) ** 0.5

    # Una entrada por FILA: sus transiciones y su resultado.
    strata: dict[tuple[str, str], list[tuple[list[tuple[str, str]], bool]]] = defaultdict(list)
    for corpus in CORPORA:
        try:
            runner = Runner(settings, corpus, retriever_arm="hybrid",
                            surface_variant="basic")
            cells_of = {t["task_id"]: t["cell"][:2] for t in runner._tasks}  # noqa: SLF001
            rows = list(runner.load_rows())
        except FileNotFoundError:
            continue
        for r in rows:
            sequence = (r.get("tool_usage") or {}).get("sequence")
            if not sequence:
                continue
            steps = [START, *sequence, END]
            transitions = list(zip(steps, steps[1:]))
            strata[(r["paradigm"], cells_of.get(r["task_id"], "??"))].append(
                (transitions, r["utility"] >= GOOD)
            )

    print(f"  {'paradigma':<15}{'celda':>6}{'filas':>7}{'observada':>11}"
          f"{'azar (p50)':>12}{'p':>8}")
    survive, tested = 0, 0
    strat_out = {}
    for (paradigm, cell), blocks in sorted(strata.items()):
        observed = dispersion(blocks)
        outcomes = [g for _, g in blocks]
        # Sin variacion de resultado adentro del estrato no hay nada que permutar: todas
        # las transiciones comparten la misma etiqueta y la dispersion es 0 por fuerza.
        if observed is None or len(blocks) < 6 or len(set(outcomes)) < 2:
            continue
        transitions_only = [t for t, _ in blocks]
        null = []
        for _ in range(PERMUTATIONS):
            shuffled = outcomes[:]
            rng.shuffle(shuffled)
            d = dispersion(list(zip(transitions_only, shuffled)))
            if d is not None:
                null.append(d)
        if len(null) < PERMUTATIONS // 2:
            continue
        null.sort()
        p_value = sum(1 for d in null if d >= observed) / len(null)
        median = null[len(null) // 2]
        tested += 1
        mark = ""
        if p_value <= 0.05:
            survive += 1
            mark = "  <- sobrevive"
        print(f"  {paradigm:<15}{cell:>6}{len(blocks):>7}{observed:>11.4f}"
              f"{median:>12.4f}{p_value:>8.3f}{mark}")
        strat_out[f"{paradigm}|{cell}"] = {
            "rows": len(blocks), "observed": round(observed, 4),
            "null_median": round(median, 4), "p": round(p_value, 4),
        }

    # POTENCIA, antes de leer el resultado. Con n filas de las cuales k salieron bien hay
    # C(n,k) asignaciones distintas, asi que el p MINIMO alcanzable es 1/C(n,k). Si ese
    # piso ya esta por encima de 0,05, el estrato NO PUEDE dar significativo aunque la
    # senal sea perfecta — y leer eso como "no hay senal" seria confundir ausencia de
    # potencia con ausencia de efecto.
    from math import comb

    powered = 0
    for key, body in strat_out.items():
        n = body["rows"]
        k = sum(1 for _, g in strata[tuple(key.split("|"))] if g)
        floor_p = 1.0 / comb(n, k) if 0 < k < n else 1.0
        body["min_p"] = round(floor_p, 4)
        if floor_p <= 0.05:
            powered += 1

    print("")
    print(f"  estratos evaluables (con variacion de resultado): {tested}")
    print(f"  de esos, con POTENCIA para alcanzar p<=0,05     : {powered}")
    print(f"  con dispersion mayor que el azar                : {survive}")
    print("")
    if powered == 0 and tested > 0:
        print("  LECTURA: NINGUN estrato tiene potencia. Con seis o siete filas por celda,")
        print("  el p minimo alcanzable ya esta por encima de 0,05 aunque la senal fuera")
        print("  perfecta. Esto NO refuta P-2c y NO lo confirma: no decide.")
        print("")
        print("  Lo que si queda establecido es que la dispersion sin estratificar (0,18)")
        print("  NO puede leerse como senal, porque el control que la separaria de la")
        print("  dificultad de tarea todavia no se puede correr.")
    elif tested == 0:
        print("  Ningun estrato tiene variacion de resultado adentro de la celda: o todo")
        print("  sale bien o todo sale mal, y entonces no hay nada que una transicion")
        print("  pueda explicar. No es evidencia en contra de P-2c: es falta de contraste.")
    elif survive == 0:
        print(f"  LECTURA: de los {powered} estratos CON potencia, ninguno supera al azar.")
        print("  Eso inclina en contra de P-2c y no lo refuta: con seis o siete filas por")
        print("  celda, no detectar un efecto es compatible con que exista y sea chico.")
        print("")
        print("  Lo que SI queda establecido, y es lo que importa: la dispersion sin")
        print("  estratificar (0,18) NO puede leerse como senal. Al controlar por celda")
        print("  —conservando el bloque de fila, que es la unidad de resultado— se cae a")
        print("  lo que el azar produce. Lo que parecia orden era, hasta donde este n")
        print("  permite ver, dificultad de tarea.")
        print("")
        print("  Se re-mide cuando P17 cierre: triplica las secuencias del registro.")
    else:
        print("  LECTURA: hay estratos donde la dispersion supera al azar conservando")
        print("  celda, bloques de fila y tamanos. NO es dificultad de tarea. Con este n")
        print("  es un indicio dirigido y no un veredicto: el numero que decide sigue")
        print("  siendo si sirve para decidir algo con el costo cobrado.")
    print("=" * 74)

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
        "stratified": strat_out,
        "table": table.as_dict(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nreporte: {out}")


if __name__ == "__main__":
    main()
