"""¿Aprender paga contra no aprender? La mitad del título, puesta a prueba. Cero llamadas.

LA PREGUNTA. El motor es determinista **y plástico**: `f` aprende offline, copy-on-write, con
guarda anti-regresión. La primera mitad está medida en todo §7; la segunda está **implementada
y sin validar**, y una palabra del título sostenida por implementación no es un resultado.

    ¿Una política que aprende del registro le gana a una constante que no aprende nada?

EL DISEÑO ES DEJAR UNA TAREA AFUERA, y el contrafáctico correcto no es el oráculo: es la
**mejor constante**, elegida sobre los mismos pliegues de entrenamiento. Comparar contra el
oráculo mide cuánto falta; comparar contra la constante mide si aprender **compra algo**, que
es la pregunta.

  · `constante`      el paradigma de mejor media sobre los pliegues de entrenamiento.
                     No mira la tarea. Es el piso que hay que superar
  · `θ región`       elige por región, con las estadísticas de los pliegues de entrenamiento
  · `θ computada`    igual, pero con la clave **sin el eje elicitado**

LA TERCERA POLÍTICA ES LA QUE IMPORTA, y sale de §7.3.6: la región tiene cuatro ejes
`COMPUTED` y uno `ELICITED`, y el elicitado cambia de valor en el 27% de las tareas al cambiar
de modelo. Una política keyed en la región completa **hereda la estocasticidad del sensor en su
propia clave**. Si aprender paga, tiene que pagar con una clave reproducible; si sólo paga con
la clave completa, lo que está capturando no es transferible.

DOS OBJETIVOS, porque el corpus premia uno y no el otro (§7.3.5):

  `utilidad`   máxima calidad. §7.3 mide que acá no hay premio, así que se espera que las
               tres políticas empaten dentro del ruido
  `costo`      entre las que empatan en utilidad dentro de la tolerancia, la más barata.
               Es el eje donde este corpus sí paga

Corre DESDE `lab/`:  py bench/analysis/_plasticidad.py
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

_sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.runner import load_rows
from bench.panel import rectangulo

REGISTRO = Path("results/luna/gold_h1_rows.jsonl")
# El eje elicitado es el TERCERO del vocabulario `regions/3-literal`:
# cardinalidad / oraculo / ACOPLAMIENTO / continuidad / literal
EJE_ELICITADO = 2


def clave_computada(region: str) -> str:
    """La región sin el eje que el modelo emite. Reproducible entre sensores."""
    p = region.split("/")
    return "/".join(x for i, x in enumerate(p) if i != EJE_ELICITADO)


def main() -> None:
    filas = [f for f in load_rows(REGISTRO) if not f.get("infeasible")]
    panel = rectangulo([{"task_id": f["task_id"], "paradigm": f["paradigm"],
                         "infeasible": False} for f in filas])
    ts, bs = sorted(panel.tareas), sorted(panel.brazos)
    U: dict[tuple[str, str], list[float]] = defaultdict(list)
    C: dict[tuple[str, str], list[int]] = defaultdict(list)
    region: dict[str, str] = {}
    for f in filas:
        if f["task_id"] in set(ts) and f["paradigm"] in set(bs):
            k = (f["task_id"], f["paradigm"])
            U[k].append(f.get("utility", 0.0))
            C[k].append(f.get("cost_tokens") or 0)
            if f.get("region"):
                region[f["task_id"]] = f["region"]
    um = {k: statistics.mean(v) for k, v in U.items()}
    cm = {k: statistics.mean(v) for k, v in C.items()}

    # tolerancia de empate: un sigma del ruido de la media entre replicas
    dentro = [statistics.pvariance(U[k]) for k in U if len(U[k]) > 1]
    tol = (statistics.mean(dentro) / 3) ** 0.5 if dentro else 0.0

    print("=" * 92)
    print("¿APRENDER PAGA CONTRA NO APRENDER?")
    print("=" * 92)
    print(f"\n  {panel.descripcion()} · tolerancia de empate {tol:.3f}")
    print(f"  claves: región completa {len({region[t] for t in ts if t in region})} valores · "
          f"región computada {len({clave_computada(region[t]) for t in ts if t in region})}\n")

    def politica(entren: list[str], t: str, clave, objetivo: str) -> str:
        """Elige un paradigma para `t` usando SÓLO las tareas de entrenamiento."""
        if clave is None:                      # constante: no mira la tarea
            cand = bs
            grupo = entren
        else:
            k = clave(region.get(t, ""))
            grupo = [x for x in entren if clave(region.get(x, "")) == k]
            if len(grupo) < 2:                 # sin evidencia en la región: cae a constante
                grupo = entren
            cand = bs
        med = {p: statistics.mean([um[(x, p)] for x in grupo if (x, p) in um] or [0.0])
               for p in cand}
        if objetivo == "utilidad":
            return max(med, key=lambda p: med[p])
        techo = max(med.values())
        empatan = [p for p in cand if med[p] >= techo - tol]
        costo = {p: statistics.mean([cm[(x, p)] for x in grupo if (x, p) in cm] or [1e18])
                 for p in empatan}
        return min(empatan, key=lambda p: costo[p])

    POL = [("constante  (no aprende)", None),
           ("θ región completa", lambda r: r),
           ("θ región COMPUTADA", clave_computada)]

    for objetivo in ("utilidad", "costo"):
        print(f"  ── objetivo: {objetivo} " + "─" * (62 - len(objetivo)))
        res = {}
        for nombre, clave in POL:
            u, c = [], []
            for t in ts:
                entren = [x for x in ts if x != t]
                p = politica(entren, t, clave, objetivo)
                if (t, p) in um:
                    u.append(um[(t, p)])
                    c.append(cm[(t, p)])
            res[nombre] = (statistics.mean(u), statistics.mean(c), u)
        base_u, base_c, base_v = res["constante  (no aprende)"]
        print(f"  {'política':<28}{'utilidad':>10}{'Δ vs const':>12}"
              f"{'tok/tarea':>12}{'ahorro':>9}")
        for nombre, _ in POL:
            u, c, v = res[nombre]
            d = u - base_u
            print(f"  {nombre:<28}{u:>10.3f}{d:>+12.3f}{c:>12,.0f}"
                  f"{1 - c / base_c:>9.0%}")
        # ¿la diferencia sobrevive al remuestreo de TAREAS?
        rng = random.Random(11)
        for nombre, _ in POL[1:]:
            _, _, v = res[nombre]
            d = [a - b for a, b in zip(v, base_v)]
            ms = sorted(statistics.mean([d[rng.randrange(len(d))] for _ in d])
                        for _ in range(4000))
            lo, hi = ms[100], ms[3900]
            cruza = lo <= 0 <= hi
            print(f"    {nombre} vs constante: Δ {statistics.mean(d):+.3f} "
                  f"IC95 [{lo:+.3f}, {hi:+.3f}]" + ("  (cruza cero)" if cruza else "  *"))
        print()

    print("=" * 92)
    print("""
  CÓMO SE LEE. Sobre `utilidad` §7.3 ya midió que no hay premio, así que el resultado
  esperado es empate dentro del ruido: aprender no puede comprar lo que no está. Sobre
  `costo` el corpus sí paga, y ahí la pregunta es si la política aprendida captura ese
  ahorro **con una clave reproducible** — la fila `θ región COMPUTADA` — o sólo con la clave
  que incluye el eje que cambia entre modelos.

  Una política que sólo gana con la clave completa gana con una clave que no se reproduce, y
  ese ahorro no es transferible a otro sensor.
""")


if __name__ == "__main__":
    main()
