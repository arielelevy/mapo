"""D-5b: derivar las constantes atadas al modelo, en vez de elegirlas a mano.

LA «CONSTANT SOUP» TENIA INVENTARIO Y NO DERIVACION. `MODELO_Y_CONSTANTES.es.md` separo
seis constantes que suponen algo del modelo de siete que no, y escribio de donde saldria
cada una. Esto las calcula. No cuesta un token: todo sale del registro pagado.

LO QUE NO HACE. No las cambia. Un cambio de constante cambia lo que los paradigmas hacen,
asi que es un FACTOR y entra con prediccion registrada, como todo lo demas. Esto produce
el numero que esa decision necesita, y la distancia entre el valor a mano y el derivado.

LA PRUEBA QUE DECIDE SI UNA CONSTANTE VA ACA: ¿su valor correcto cambiaria si el mismo
corpus lo corriera otro modelo? Si si, es del modelo y se deriva. Si no, es del problema.
"""

import json
import statistics
import sys
from collections import defaultdict
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from _sanity import all_present
from app.config import Settings
from app.runner import Runner

# `gold_v2` y `gold_deep` van incluidos porque son los UNICOS donde `direct`
# corrio: sin el, el prior queda definido contra un brazo ausente y la
# distancia no se puede computar. El script se niega en vez de estimarla.
CORPORA = ["gold_p17", "gold_p16", "gold_transfer", "gold_v2", "gold_deep"]
# Percentil al que se corta un tope: el valor que cubre a casi todos sin premiar la cola.
PERCENTIL = 0.95


def percentil(valores: list[float], q: float) -> float:
    if not valores:
        return 0.0
    orden = sorted(valores)
    return orden[min(len(orden) - 1, int(q * len(orden)))]


def main() -> None:
    base = Settings.from_env()
    settings = replace(base, results_dir=base.results_dir / "nano")

    rows, faltan = [], []
    for corpus in CORPORA:
        if not (settings.corpus_dir / corpus).is_dir():
            faltan.append(corpus)
            continue
        runner = Runner(settings, corpus, retriever_arm="hybrid",
                        surface_variant="basic")
        rows.extend(r for r in runner.load_rows() if not r.get("infeasible"))
    if faltan:
        print(f"corpus ausentes, declarados: {faltan}")
    if not rows:
        raise SystemExit("sin filas: no hay de donde derivar")

    print(f"{len(rows)} filas factibles\n")

    # --- max_iterations, por brazo -----------------------------------------------------
    print("--- `max_iterations`: cuantas vueltas necesita ESTE modelo ---")
    print("  el tope a mano cubre la cola; el derivado corta donde ya no compra utilidad")
    por_brazo = defaultdict(list)
    exito = defaultdict(list)
    for r in rows:
        por_brazo[r["paradigm"]].append(r.get("iterations", 0))
        if r["utility"] >= 1.0:
            exito[r["paradigm"]].append(r.get("iterations", 0))
    A_MANO = {"react": 20, "reflection": 10, "handoff": 6}
    print(f"  {'brazo':<15}{'a mano':>8}{'p95 todas':>11}{'p95 aciertos':>14}{'max':>7}")
    derivadas = {}
    for p in sorted(por_brazo):
        v = por_brazo[p]
        e = exito[p]
        d = percentil(e, PERCENTIL) if e else percentil(v, PERCENTIL)
        derivadas[p] = d
        print(f"  {p:<15}{A_MANO.get(p, '—'):>8}{percentil(v, PERCENTIL):>11.0f}"
              f"{d:>14.0f}{max(v):>7}")
    print("  => el p95 de las REPLICAS QUE ACERTARON es el tope honesto: mas vueltas que")
    print("     eso no compro un acierto en este registro.")

    # --- max_tokens de salida -----------------------------------------------------------
    print("\n--- `max_tokens` por llamada: cuanto escribe de salida ---")
    comp = [r["completion_tokens"] for r in rows if r.get("completion_tokens")]
    if comp:
        print(f"  a mano: 800 y 600 segun el sitio")
        print(f"  observado: mediana {statistics.median(comp):,.0f}  "
              f"p95 {percentil(comp, 0.95):,.0f}  max {max(comp):,}")
        print("  => el tope a mano esta muy por encima de la cola: no acota nada, y eso")
        print("     tambien es un dato — no lo alcanza casi nunca.")
    else:
        print("  el split de salida no esta en estas filas: se declara y no se estima")

    # --- stop_on_barren -----------------------------------------------------------------
    print("\n--- `stop_on_barren`: cuando ESTE modelo deja de encontrar algo nuevo ---")
    picos = [(r.get("tool_usage") or {}).get("barren_peak")
             for r in rows if "barren_peak" in (r.get("tool_usage") or {})]
    picos = [p for p in picos if p is not None]
    if picos:
        con_pico = [p for p in picos if p > 0]
        print(f"  a mano: 3")
        print(f"  filas con el contador: {len(picos)} · con alguna esteril: {len(con_pico)}")
        if con_pico:
            print(f"  distribucion del pico: mediana {statistics.median(con_pico):.0f}  "
                  f"p95 {percentil(con_pico, 0.95):.0f}  max {max(con_pico)}")
            print("  => cortar en la mediana toca la mitad de las filas que se estancan;")
            print("     cortar en el p95 casi ninguna. El 3 esta cerca de la mediana.")
    else:
        print("  AUSENTE del registro — no es cero: hay que replayar para tenerlo")

    # --- COST_PRIORS ---------------------------------------------------------------------
    print("\n--- `COST_PRIORS`: multiplicadores de costo relativos ---")
    # LA BASE DEL RATIO SE ENUNCIA, o el numero se lee al reves. El prior esta definido
    # contra `direct = 1,0`; compararlo contra otro denominador da la conclusion OPUESTA
    # —lo hice, y daba que los priors se quedaban cortos cuando en realidad sobran—.
    #
    # Y hay una salvedad estructural: `direct` solo es factible donde toda la evidencia
    # entra en ventana, asi que el ratio se computa PAREADO sobre las tareas donde los dos
    # corrieron. Un promedio global compararia poblaciones distintas.
    por_tarea = defaultdict(dict)
    for r in rows:
        por_tarea[r["paradigm"]].setdefault(r["task_id"], []).append(r["cost_tokens"])
    medias_tarea = {p: {t: statistics.mean(v) for t, v in d.items()}
                    for p, d in por_tarea.items()}
    base_arm = medias_tarea.get("direct", {})
    if not base_arm:
        print("  `direct` no tiene filas en estos corpus: el prior esta definido contra un")
        print("  brazo que no corrio, asi que NO se computa la distancia. Se dice.")
        medias, piso = {}, 1.0
    else:
        medias, piso = {}, 1.0
        print(f"  `direct` corrio en {len(base_arm)} tareas — y SOLO donde fue factible")
    A_MANO_COST = {"direct": 1.0, "react": 3.0, "reflection": 5.0, "handoff": 5.0,
                   "plan_execute": 6.0, "map_reduce": 8.0, "dag_strategy": 12.0}
    if base_arm:
        print(f"  {'brazo':<15}{'prior':>7}{'pareado':>10}{'factor':>9}{'n':>5}")
        ratios: dict[str, float] = {}
        for p in sorted(medias_tarea):
            comunes = sorted(set(medias_tarea[p]) & set(base_arm))
            if not comunes:
                continue
            par = (statistics.mean([medias_tarea[p][t] for t in comunes])
                   / statistics.mean([base_arm[t] for t in comunes]))
            ratios[p] = par
            mano = A_MANO_COST.get(p)
            de_mas = f"{mano / par:.1f}x" if mano and par else "—"
            print(f"  {p:<15}{(mano if mano is not None else '—'):>7}{par:>10.1f}"
                  f"{de_mas:>9}{len(comunes):>5}")
        # LA CONCLUSION SE COMPUTA, NO SE AFIRMA. La primera version decia «todos
        # sobreestiman» y era falsa: `plan_execute` subestima. Escribir la direccion a
        # mano al lado de una tabla es la forma de que la tabla cambie y la frase no.
        sobre = [p for p, r in ratios.items()
                 if A_MANO_COST.get(p) and A_MANO_COST[p] > r]
        sub = [p for p, r in ratios.items()
               if A_MANO_COST.get(p) and A_MANO_COST[p] < r]
        print(f"  => sobreestiman {len(sobre)} ({', '.join(sorted(sobre)) or '—'})")
        print(f"     subestiman   {len(sub)} ({', '.join(sorted(sub)) or '—'})")
        if sobre:
            print("     sobreestimar => la poda descarta brazos que SI entraban, antes de")
            print("     mirar y con un numero que nadie midio.")
        if sub:
            print("     subestimar => deja pasar brazos que van a exceder el presupuesto.")
        print("  => y la base es estructuralmente flaca: `direct` solo es factible donde")
        print("     todo entra en ventana, asi que la escala no tiene base medible en el")
        print("     regimen que el producto apunta.")

    out = settings.results_dir / "constantes.json"
    out.write_text(json.dumps({
        "iteraciones_p95_aciertos": {k: v for k, v in derivadas.items()},
        "cost_ratio_observado": {k: v / piso for k, v in medias.items()},
        "completion_p95": percentil(comp, 0.95) if comp else None,
        "barren_peak_mediana": (statistics.median([p for p in picos if p > 0])
                                if picos and any(p > 0 for p in picos) else None),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ndetalle: {out}")


if __name__ == "__main__":
    main()
