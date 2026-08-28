"""Veredicto de P20 — CONGELADO. Las predicciones estan en README, registradas antes.

LAS PREDICCIONES, TAL COMO QUEDARON

  P20a  Con la regla, el costo medio por celda baja AL MENOS 10% contra las mismas celdas
        sin ella. Refutada si la baja es menor — eso querria decir que el tercio evitable
        no es alcanzable por esta regla, sea cierto lo que sea.
  P20b  La utilidad media por celda NO cae mas que el piso de ruido por celda. Refutada si
        cae — un ahorro que contesta peor no es un ahorro, y esta es la que puede matar al
        factor.
  P20c  La reduccion es mayor en los brazos cuyo bucle controla el modelo que en
        `map_reduce`, cuyo fan-out lo fija el codigo. Refutada si `map_reduce` baja igual.
  P20d  Despues de un rechazo, la proxima llamada es una lectura o una respuesta en la
        MAYORIA de los casos. Refutada si los modelos re-emiten una busqueda con otras
        palabras: eso haria de esto una regla que renombra el desperdicio.

LA COMPARACION ES PAREADA POR CELDA. Cada `(tarea, paradigma, trial)` existe en los dos
registros porque el corpus, la semilla y los brazos son los mismos; lo unico que cambia es
el factor. Comparar promedios globales mezclaria composicion con efecto.

UNA OBSERVACION ANOTADA ANTES DE CORRER, y que no cambio ninguna prediccion: el
estancamiento se concentra en `dag_strategy` y `rewoo`; `react` casi no se estanca. `P20c`
predijo que la regla morderia mas donde el modelo controla el bucle, y `react` es el caso
mas puro de eso.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import statistics
import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings

SIN = "gold_p17_rows.jsonl"
CON = "gold_p17_stop3_rows.jsonl"
LOOP = ("react", "dag_strategy", "rewoo", "gist_reader")
FIJO = ("map_reduce",)


def celdas(path: Path) -> dict[tuple[str, str, int], dict]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("infra_error") or r.get("infeasible"):
            continue
        out[(r["task_id"], r["paradigm"], r.get("trial", 0))] = r
    return out


def main() -> None:
    base = Settings.from_env()
    root = base.results_dir / "nano"
    sin, con = celdas(root / SIN), celdas(root / CON)
    comunes = sorted(set(sin) & set(con))
    print(f"celdas pareadas: {len(comunes)} (sin={len(sin)} con={len(con)})\n")
    if not comunes:
        raise SystemExit("sin celdas pareadas: no hay comparacion que hacer")

    # --- P20a: ¿baja el costo? -----------------------------------------------------------
    c_sin = statistics.mean(sin[k]["cost_tokens"] for k in comunes)
    c_con = statistics.mean(con[k]["cost_tokens"] for k in comunes)
    baja = (c_sin - c_con) / c_sin if c_sin else 0.0
    print("--- P20a: ¿baja el costo al menos 10%? ---")
    print(f"  sin regla {c_sin:>10,.0f}   con regla {c_con:>10,.0f}   baja {baja:>7.1%}")
    v_a = "CONFIRMADA" if baja >= 0.10 else "REFUTADA"
    print(f"  P20a: {v_a} (criterio >= 10%)")

    # --- P20b: ¿cuesta utilidad? ---------------------------------------------------------
    print("\n--- P20b: ¿cae la utilidad mas que el ruido? ---")
    u_sin = statistics.mean(sin[k]["utility"] for k in comunes)
    u_con = statistics.mean(con[k]["utility"] for k in comunes)
    # Piso de ruido POR CELDA: desviacion entre trials de la misma celda, sin la regla.
    por_celda = defaultdict(list)
    for (t, p, _), r in sin.items():
        por_celda[(t, p)].append(r["utility"])
    ruidos = [statistics.pstdev(v) for v in por_celda.values() if len(v) > 1]
    piso = statistics.mean(ruidos) if ruidos else 0.0
    caida = u_sin - u_con
    print(f"  sin regla {u_sin:.4f}   con regla {u_con:.4f}   caida {caida:+.4f}")
    print(f"  piso de ruido por celda: {piso:.4f}")
    v_b = "CONFIRMADA" if caida <= piso else "REFUTADA"
    print(f"  P20b: {v_b} (criterio: caida <= piso)")

    # --- P20c: ¿muerde donde esta la autonomia? ------------------------------------------
    print("\n--- P20c: ¿baja mas donde el modelo controla el bucle? ---")
    por_brazo = {}
    for grupo, nombre in ((LOOP, "bucle del modelo"), (FIJO, "fan-out del codigo")):
        ks = [k for k in comunes if k[1] in grupo]
        if not ks:
            continue
        a = statistics.mean(sin[k]["cost_tokens"] for k in ks)
        b = statistics.mean(con[k]["cost_tokens"] for k in ks)
        por_brazo[nombre] = (a - b) / a if a else 0.0
    for nombre, r in por_brazo.items():
        print(f"  {nombre:<20} baja {r:>7.1%}")
    print("\n  por brazo:")
    detalle = {}
    for p in sorted({k[1] for k in comunes}):
        ks = [k for k in comunes if k[1] == p]
        a = statistics.mean(sin[k]["cost_tokens"] for k in ks)
        b = statistics.mean(con[k]["cost_tokens"] for k in ks)
        rechazos = sum((con[k].get("tool_usage") or {}).get("barren_refusals", 0)
                       for k in ks)
        detalle[p] = (a - b) / a if a else 0.0
        print(f"    {p:<15} {a:>10,.0f} -> {b:>10,.0f}  ({detalle[p]:>+7.1%})  "
              f"rechazos={rechazos}")
    v_c = ("CONFIRMADA"
           if por_brazo.get("bucle del modelo", 0) > por_brazo.get("fan-out del codigo", 0)
           else "REFUTADA")
    print(f"  P20c: {v_c}")

    # --- P20d: ¿se usa el rechazo o se lo esquiva? ---------------------------------------
    print("\n--- P20d: ¿que hace el modelo DESPUES de un rechazo? ---")
    BUSQUEDAS = {"search", "keyword_search", "semantic_search"}
    despues = defaultdict(int)
    con_rechazo = 0
    for k in comunes:
        tu = con[k].get("tool_usage") or {}
        if not tu.get("barren_refusals"):
            continue
        con_rechazo += 1
        seq = tu.get("sequence") or []
        # La secuencia registra TODA llamada pedida, rechazada incluida. Se busca que
        # herramienta viene despues de la primera que pudo ser rechazada.
        for i, name in enumerate(seq[:-1]):
            if name in BUSQUEDAS:
                nxt = seq[i + 1]
                despues["otra busqueda" if nxt in BUSQUEDAS else nxt] += 1
    total = sum(despues.values())
    print(f"  filas con al menos un rechazo: {con_rechazo}")
    if total:
        for nombre, n in sorted(despues.items(), key=lambda kv: -kv[1]):
            print(f"    {nombre:<18} {n:>5}  ({n/total:.0%})")
        esquiva = despues.get("otra busqueda", 0) / total
        v_d = "CONFIRMADA" if esquiva < 0.5 else "REFUTADA"
        print(f"  re-emite busqueda el {esquiva:.0%} de las veces")
        print(f"  P20d: {v_d} (criterio: < 50%)")
    else:
        esquiva, v_d = None, "SIN N"
        print("  P20d: SIN N")

    out = root / "p20_verdict.json"
    out.write_text(json.dumps({
        "celdas_pareadas": len(comunes),
        "p20a": {"costo_sin": c_sin, "costo_con": c_con, "baja": baja, "verdict": v_a},
        "p20b": {"util_sin": u_sin, "util_con": u_con, "caida": caida,
                 "piso_ruido": piso, "verdict": v_b},
        "p20c": {"por_grupo": por_brazo, "por_brazo": detalle, "verdict": v_c},
        "p20d": {"reemite_busqueda": esquiva, "verdict": v_d},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nveredicto: {out}")


if __name__ == "__main__":
    main()
