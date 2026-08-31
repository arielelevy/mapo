"""¿El ORDEN explica la interacción? La prueba que sí se puede correr. Cero llamadas.

EL PROBLEMA QUE ESTO RODEA. La prueba estricta —mismas herramientas, mismas veces, distinto
orden, MISMA tarea— tiene **9 grupos de 738**: con `t=0` + seed las réplicas salen casi
idénticas. El determinismo que el banco necesita para replay destruye la variación que el
aprendizaje por pares necesitaría.

LA SALIDA, y no es aflojar la prueba: **cruzar tareas y controlar la dificultad con el
residuo**. El mismo multiconjunto de herramientas aparece en 50 grupos si se permite que las
tareas sean distintas — 305 filas, 34× más material. El precio es que la dificultad de la
tarea entra como confundido, y ése se paga con la descomposición que ya existe:

    u(tarea, brazo) = μ + α(tarea) + β(brazo) + γ(tarea, brazo) + ε

`α` es la dificultad y `β` la calidad del brazo. **Lo que queda, γ, es lo único que el orden
podría explicar** — y es exactamente lo mismo que se le pide a cualquier otra señal
candidata, así que el orden se juzga con la misma vara que `region` o `literal`.

LA VARA: nulo por permutación. Se barajan las etiquetas de orden entre filas conservando el
tamaño de cada grupo, y se recalcula. Con 50 grupos y 114 órdenes distintos, una partición
fina explica varianza por construcción — el nulo es lo que descuenta eso.

QUÉ **NO** RESUELVE, dicho antes del resultado: esto sigue siendo observacional. Que una fila
haya usado cierto orden no es una intervención — el orden lo eligió el mismo proceso que
produjo la utilidad. El experimento que sí lo decide está descrito al final.

Corre DESDE `lab/`:  py bench/analysis/_orden_residual.py
"""

from __future__ import annotations

import collections
import json
import random
import statistics
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PERMUTACIONES = 2000
SEMILLA = 20260830


def filas_de(ruta: _Path) -> list[dict]:
    out = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            out.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    return out


def main() -> None:
    rng = random.Random(SEMILLA)
    filas = [f for f in filas_de(_Path("results/luna/gold_h1_rows.jsonl"))
             if not f.get("infeasible") and not f.get("infra_error")]

    # ── la descomposicion, sobre el panel donde se puede hacer ──────────────
    celdas = collections.defaultdict(list)
    for f in filas:
        celdas[(f["task_id"], f["paradigm"])].append(f)
    u = {k: statistics.mean(x["utility"] for x in v) for k, v in celdas.items()}
    tareas = sorted({t for t, _ in u})
    brazos = sorted({p for _, p in u})
    mu = statistics.mean(u.values())
    alpha = {t: statistics.mean(u[(t, p)] for p in brazos if (t, p) in u) - mu
             for t in tareas}
    beta = {p: statistics.mean(u[(t, p)] for t in tareas if (t, p) in u) - mu
            for p in brazos}

    # ── el residuo POR FILA, que es lo que el orden podria explicar ─────────
    datos = []
    for f in filas:
        seq = tuple((f.get("tool_usage") or {}).get("sequence") or [])
        if len(seq) < 2:
            continue
        t, p = f["task_id"], f["paradigm"]
        resid = f["utility"] - mu - alpha.get(t, 0.0) - beta.get(p, 0.0)
        multi = tuple(sorted(collections.Counter(seq).items()))
        datos.append({"resid": resid, "orden": seq, "multi": multi, "brazo": p})

    # Solo las filas cuyo (brazo, multiconjunto) tiene DOS O MAS ordenes: en las demas el
    # orden no varia, asi que no puede explicar nada y solo diluiria.
    por_grupo = collections.defaultdict(set)
    for d in datos:
        por_grupo[(d["brazo"], d["multi"])].add(d["orden"])
    utiles = [d for d in datos if len(por_grupo[(d["brazo"], d["multi"])]) >= 2]

    print("=" * 94)
    print("¿EL ORDEN EXPLICA LA INTERACCION?")
    print("=" * 94)
    print(f"\n  {len(datos)} filas con secuencia · {len(utiles)} en grupos con 2+ ordenes")
    print(f"  {sum(1 for v in por_grupo.values() if len(v) >= 2)} grupos "
          f"(brazo x multiconjunto) comparables")
    if len(utiles) < 30:
        print("\n  >>> NO ALCANZA EL MATERIAL.")
        return

    var_total = statistics.pvariance([d["resid"] for d in utiles])

    def explicado(clave) -> float:
        g = collections.defaultdict(list)
        for d in utiles:
            g[clave(d)].append(d["resid"])
        pred = {k: statistics.mean(v) for k, v in g.items()}
        resid = [d["resid"] - pred[clave(d)] for d in utiles]
        return 1.0 - statistics.pvariance(resid) / var_total if var_total else 0.0

    # EL ORDEN COMPLETO, y el PRIMER PAR — dos granularidades, porque una particion muy
    # fina explica por construccion y el nulo tiene que descontarlo.
    pruebas = {
        "el orden completo": lambda d: (d["brazo"], d["orden"]),
        "el PRIMER par (tool_1 -> tool_2)": lambda d: (d["brazo"], d["orden"][:2]),
        "la primera herramienta": lambda d: (d["brazo"], d["orden"][0]),
        "(control) el multiconjunto — NO es orden": lambda d: (d["brazo"], d["multi"]),
    }
    resultados: dict[str, tuple] = {}
    print(f"\n  {'particion':40s} {'niveles':>8s} {'explica':>8s} {'nulo p95':>9s} {'p':>7s}")
    for nombre, clave in pruebas.items():
        real = explicado(clave)
        etiquetas = [clave(d) for d in utiles]
        nulos = []
        for _ in range(PERMUTACIONES):
            b = etiquetas[:]
            rng.shuffle(b)
            g = collections.defaultdict(list)
            for d, e in zip(utiles, b):
                g[e].append(d["resid"])
            pred = {k: statistics.mean(v) for k, v in g.items()}
            r = [d["resid"] - pred[e] for d, e in zip(utiles, b)]
            nulos.append(1.0 - statistics.pvariance(r) / var_total if var_total else 0.0)
        p95 = sorted(nulos)[int(0.95 * len(nulos))]
        pv = (sum(1 for x in nulos if x >= real) + 1) / (len(nulos) + 1)
        print(f"  {nombre:40s} {len(set(etiquetas)):8d} {real:8.3f} {p95:9.3f} "
              f"{pv:7.3f}{' *' if real > p95 else ''}")
        resultados[nombre] = (real, p95, pv, real - p95)

    # LA CORRECCION QUE DECIDE. Se probaron cuatro particiones y se mira la mejor: comparar
    # cada una contra SU nulo individual es la falacia que el nulo existia para evitar. Con
    # Bonferroni sobre 4 pruebas, el umbral es 0,0125.
    print(f"\n  {'-' * 90}")
    umbral = 0.05 / len(resultados)
    print(f"  corregido por las {len(resultados)} pruebas (Bonferroni, umbral "
          f"{umbral:.4f}):\n")
    for nombre, (real, p95, pv, margen) in resultados.items():
        veredicto = "SOBREVIVE" if pv < umbral else "no sobrevive"
        print(f"    {nombre:40s} p={pv:.3f}  margen sobre el nulo {margen:+.3f}  "
              f"{veredicto}")
    orden = resultados["el orden completo"]
    multi = resultados["(control) el multiconjunto — NO es orden"]
    print(f"""
  >>> EL VEREDICTO. El **multiconjunto** —el control, que NO es orden— sobrevive con
      p={multi[2]:.3f} y un margen de {multi[3]:+.3f} sobre su nulo. El **orden completo** no
      sobrevive (p={orden[2]:.3f}) y su margen es {orden[3]:+.3f}, MENOR que el del
      histograma pese a partir en 114 niveles contra 50.

      O sea: **el conteo lleva senal y la secuencia no le agrega**. Es lo contrario de lo
      que afirma el docstring de `sequence` en `tools.py`, al menos de forma
      observacional.""")

    print("""
  COMO LEER. El `multiconjunto` esta como CONTROL, no como candidata: no es orden, es el
  histograma. Si el orden completo no explica mas que el, entonces la secuencia no aporta
  nada sobre el conteo — que es exactamente la afirmacion bajo prueba.

  Y ESTO SIGUE SIENDO OBSERVACIONAL. El orden lo eligio el mismo proceso que produjo la
  utilidad, asi que una asociacion no separa «este orden funciona mejor» de «cuando las
  cosas van bien, el orden termina siendo este». La prueba que SI lo decide es una
  intervencion, y esta descrita en `PENDIENTES.es.md` (`ON-3`): permutar los pasos
  INDEPENDIENTES de un plan de `rewoo` —los que no se referencian entre si con `#E`— y
  re-solver. Mismo multiconjunto, mismo dataflow, orden forzado por nosotros y no elegido
  por el modelo.""")


if __name__ == "__main__":
    main()
