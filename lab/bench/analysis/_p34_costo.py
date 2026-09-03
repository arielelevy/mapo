"""P34 — ¿LA CONSOLIDACIÓN APRENDE EL DESEMPATE POR COSTO SOBRE UNA CLAVE COMPUTED? Cero llamadas.

LA APUESTA, registrada el 2026-09-03 en `historico/BITACORA-PREDICCIONES.es.md` antes de correr.
Hoy la señal suelta `cardinalidad × término` ahorra 58% a utilidad igual (`_predictores.py`), y
la política θ sobre la clave computada ahorra 31% a −0,104 (`_plasticidad.py`). La brecha entre
las dos es lo que este script mide: si se cierra con la θ REAL (piso de evidencia, acumulación
jerárquica con retroceso a la región padre) sobre claves `COMPUTED`, o si es del algoritmo.

QUÉ CAMBIA RESPECTO DE `_plasticidad.py`. Aquél emulaba θ con una agrupación simple por clave y
caía a constante con menos de dos tareas en el grupo. Acá θ se construye con `Plasticity.candidate`
—el mismo código que consolida en producción— sobre los episodios de las otras 63 tareas, con
`MIN_EPISODES_FOR_CONFIDENCE` y `hierarchical=True`, que es la corrección que el primer episodio
del ciclo (§6.5.2 del paper) dejó escrita: sin retroceso a la región padre, un vocabulario más
fino fragmenta la evidencia por debajo del piso.

EL DISEÑO ES LEAVE-ONE-TASK-OUT sobre el rectángulo 64 × 8, y el contrafáctico es la constante
que no aprende, elegida sobre los mismos pliegues. Tres claves, las tres reordenadas para que el
prefijo grueso sea lo más informativo:

  región completa      card / oráculo / ACOPLAMIENTO (ELICITED) / continuidad / literal
  región COMPUTADA     card / literal / oráculo / continuidad    (sin el eje elicitado)
  card × literal       card / literal                            (la señal, como clave de θ)

CRITERIO REGISTRADO (P34): éxito si alguna clave COMPUTED ahorra >= 50% con Δu cuyo IC95 incluye
cero; parcial entre 40% y 50%; fracaso por debajo de 40% o con Δu significativamente negativo,
y entonces la brecha es del algoritmo y se diagnostica dónde.

Corre DESDE `lab/`:  py bench/analysis/_p34_costo.py
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import collections
import json
import random
import statistics
from pathlib import Path

_sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.policy import (MIN_EPISODES_FOR_CONFIDENCE, Episode, Plasticity, PolicyBundle,
                        learnable_rows)
from app.runner import load_rows
from bench.panel import rectangulo

REGISTRO = Path("results/luna/gold_h1_rows.jsonl")
SALIDA = Path("results/luna/p34_verdicto.json")
FALLBACK = "react"
TAU = 0.05
REMUESTREOS = 4000
SEMILLA = 11


def _partes(region: str) -> list[str]:
    p = region.split("/")
    if len(p) != 5:
        raise ValueError(f"región con {len(p)} ejes, se esperaban 5 (regions/3-literal): {region}")
    return p


def clave_completa(region: str) -> str:
    return region


def clave_computada(region: str) -> str:
    c, o, _acopl, cont, lit = _partes(region)
    return "/".join([c, lit, o, cont])


def clave_card_literal(region: str) -> str:
    c, _o, _a, _cont, lit = _partes(region)
    return "/".join([c, lit])


# LO QUE LA PRIMERA CORRIDA DESTAPÓ (2026-09-03). El eje `card` de la región es cardinalidad de
# UNIDADES (`single/few/many`), y la señal del 58% de `_predictores.py` usa la cardinalidad de
# la RESPUESTA que el caller declara (`boolean/singular/enumerative/aggregate`), que el
# vocabulario de región NO tiene. Las tres primeras claves son las de la región; las dos últimas
# son la señal de §6.4.1 como clave de θ, que es lo que la apuesta P34 nombra.
CLAVES = [
    ("región completa (incluye el eje ELICITED)", clave_completa, False),
    ("región COMPUTADA · 4 ejes · jerárquica", clave_computada, True),
    ("card. de UNIDADES × literal(región) · jerárquica", clave_card_literal, True),
    ("card. de RESPUESTA × término(regex) · jerárquica", "answer_x_termino", True),
    ("card. de RESPUESTA × literal(región) · jerárquica", "answer_x_lit", True),
]
CORPUS = Path("corpus/gold_h1")


def main() -> None:
    filas, desc = learnable_rows(load_rows(REGISTRO))
    panel = rectangulo([{"task_id": f["task_id"], "paradigm": f["paradigm"], "infeasible": False}
                        for f in filas])
    ts, bs = sorted(panel.tareas), sorted(panel.brazos)
    st, sb = set(ts), set(bs)

    U: dict[tuple[str, str], list[float]] = collections.defaultdict(list)
    C: dict[tuple[str, str], list[int]] = collections.defaultdict(list)
    region: dict[str, str] = {}
    for f in filas:
        if f["task_id"] in st and f["paradigm"] in sb:
            k = (f["task_id"], f["paradigm"])
            U[k].append(float(f.get("utility", 0.0)))
            C[k].append(int(f.get("cost_tokens") or 0))
            region[f["task_id"]] = f["region"]
    um = {k: statistics.mean(v) for k, v in U.items()}
    cm = {k: statistics.mean(v) for k, v in C.items()}
    best = collections.defaultdict(float)
    for (t, _), u in um.items():
        best[t] = max(best[t], u)

    dentro = [statistics.pvariance(U[k]) for k in U if len(U[k]) > 1]
    tol = (statistics.mean(dentro) / 3) ** 0.5 if dentro else 0.0

    # las claves que usan lo que el caller declara y el término de la señal de §6.4.1
    from bench.analysis._predictores import _termino_literal
    docs = json.loads((CORPUS / "documents.json").read_text(encoding="utf-8"))
    tareas = {t["task_id"]: t for t in json.loads((CORPUS / "tasks.json").read_text(encoding="utf-8"))}
    answer_card = {t: (tareas[t].get("answer_cardinality") or "?") for t in ts}
    termino = {t: _termino_literal(tareas[t], docs) for t in ts}
    clave_por_tarea = {
        "answer_x_termino": {t: f"{answer_card[t]}/{termino[t]}" for t in ts},
        "answer_x_lit": {t: f"{answer_card[t]}/{_partes(region[t])[4]}" for t in ts},
    }

    def resolver(clave):
        """Una clave es una función de la región o el nombre de una tabla por tarea."""
        if callable(clave):
            return lambda t: clave(region[t])
        tabla = clave_por_tarea[clave]
        return lambda t: tabla[t]

    print("=" * 96)
    print("P34 · ¿LA CONSOLIDACIÓN APRENDE EL DESEMPATE POR COSTO SOBRE UNA CLAVE COMPUTED?")
    print("=" * 96)
    print(f"\n  {panel.descripcion()} · descartadas al aprender: {desc.as_dict() if hasattr(desc, 'as_dict') else vars(desc)}")
    print(f"  tolerancia de empate (un sigma del ruido de la media): {tol:.3f}")
    print(f"  piso de evidencia por par: {MIN_EPISODES_FOR_CONFIDENCE} episodios · τ = {TAU}\n")

    def episodios(kt) -> list[Episode]:
        return [Episode(task_id=t, region=kt(t), paradigm=p, utility=um[(t, p)],
                        cost_tokens=int(cm[(t, p)]), was_best=(um[(t, p)] >= best[t] > 0.0))
                for (t, p) in sorted(um)]

    def decidir_costo(theta: PolicyBundle, key: str, jerarquica: bool, entren: list[str]):
        """La regla de producción con objetivo de costo: en el nivel más fino con evidencia,
        entre los brazos confiados que empatan en utilidad, el más barato. Sin nivel con
        evidencia, la constante sobre los pliegues de entrenamiento."""
        for nivel in Plasticity._levels(key, jerarquica):
            conf = {p: s for p, s in theta.paradigms_for(nivel).items()
                    if p in sb and s.episodes >= MIN_EPISODES_FOR_CONFIDENCE}
            if len(conf) >= 2:
                techo = max(s.mean_utility for s in conf.values())
                empatan = [p for p, s in conf.items() if s.mean_utility >= techo - tol]
                return min(empatan, key=lambda p: conf[p].mean_cost), nivel
        return constante(entren), "constante"

    def constante(entren: list[str]) -> str:
        med = {p: statistics.mean(um[(x, p)] for x in entren) for p in bs}
        techo = max(med.values())
        empatan = [p for p in bs if med[p] >= techo - tol]
        cost = {p: statistics.mean(cm[(x, p)] for x in entren) for p in empatan}
        return min(empatan, key=lambda p: cost[p])

    resultados = {}
    # la constante, una vez
    u_c, c_c = [], []
    for t in ts:
        entren = [x for x in ts if x != t]
        p = constante(entren)
        u_c.append(um[(t, p)]); c_c.append(cm[(t, p)])
    resultados["constante (no aprende)"] = dict(u=statistics.mean(u_c), c=statistics.mean(c_c),
                                                 v=u_c, gobernadas=0, niveles={})

    for nombre, clave, jer in CLAVES:
        kt = resolver(clave)
        eps = episodios(kt)
        u_v, c_v, gob, niveles = [], [], 0, collections.Counter()
        for t in ts:
            entren = [x for x in ts if x != t]
            train = [e for e in eps if e.task_id != t]
            theta = Plasticity.candidate(PolicyBundle.cold_start(fallback=FALLBACK, tau=TAU),
                                         train, tau=TAU, hierarchical=jer,
                                         notes=f"P34 LOTO sin {t}")
            p, nivel = decidir_costo(theta, kt(t), jer, entren)
            gob += nivel != "constante"
            niveles[nivel.count("/") + 1 if nivel != "constante" else 0] += 1
            u_v.append(um[(t, p)]); c_v.append(cm[(t, p)])
        resultados[nombre] = dict(u=statistics.mean(u_v), c=statistics.mean(c_v), v=u_v,
                                  gobernadas=gob, niveles=dict(niveles))

    base = resultados["constante (no aprende)"]
    rng = random.Random(SEMILLA)
    print(f"  {'política':<48}{'utilidad':>9}{'Δu':>8}{'IC95':>20}{'tok/tarea':>11}{'ahorro':>8}{'gob.':>6}")
    veredicto = {}
    for nombre, r in resultados.items():
        d = [a - b for a, b in zip(r["v"], base["v"])]
        if nombre == "constante (no aprende)":
            lo = hi = 0.0
        else:
            ms = sorted(statistics.mean(d[rng.randrange(len(d))] for _ in d)
                        for _ in range(REMUESTREOS))
            lo, hi = ms[int(REMUESTREOS * 0.025)], ms[int(REMUESTREOS * 0.975)]
        ahorro = 1 - r["c"] / base["c"]
        print(f"  {nombre:<48}{r['u']:>9.3f}{statistics.mean(d):>+8.3f}"
              f"{'[' + f'{lo:+.3f}, {hi:+.3f}' + ']':>20}{r['c']:>11,.0f}{ahorro:>8.0%}"
              f"{r['gobernadas']:>6}")
        veredicto[nombre] = dict(utilidad=round(r["u"], 4), delta_u=round(statistics.mean(d), 4),
                                 ic95=[round(lo, 4), round(hi, 4)], tokens=round(r["c"]),
                                 ahorro=round(ahorro, 4), tareas_gobernadas=r["gobernadas"],
                                 nivel_de_decision=r["niveles"])
    print("\n  `gob.` = tareas decididas por θ con evidencia sobre el piso; el resto cayó a la constante.")
    print("  `nivel_de_decision` en el JSON dice en qué profundidad de la clave se decidió cada tarea.\n")

    # ---- el veredicto contra lo registrado
    computadas = {n: v for n, v in veredicto.items()
                  if "COMPUTADA" in n or "card." in n}
    mejor = max(computadas.items(), key=lambda kv: kv[1]["ahorro"])
    n, v = mejor
    cruza_cero = v["ic95"][0] <= 0 <= v["ic95"][1]
    if v["ahorro"] >= 0.50 and cruza_cero:
        fallo = "ÉXITO: la política aprende lo que la señal muestra, sobre una clave COMPUTED"
    elif v["ahorro"] >= 0.40 or (v["ahorro"] >= 0.50 and not cruza_cero):
        fallo = "PARCIAL: aprende en parte; se reporta qué regiones pierden"
    else:
        fallo = "FRACASO: la brecha es del algoritmo de consolidación"
    print("=" * 96)
    print(f"  VEREDICTO P34 · mejor clave COMPUTED: «{n}»")
    print(f"    ahorro {v['ahorro']:.0%} · Δu {v['delta_u']:+.3f} IC95 {v['ic95']} · "
          f"{'cruza cero' if cruza_cero else 'NO cruza cero'}")
    print(f"    {fallo}")
    print("=" * 96)

    SALIDA.write_text(json.dumps({
        "prediccion": "P34", "fecha_corrida": "2026-09-03", "panel": panel.descripcion(),
        "tolerancia_empate": round(tol, 4), "piso_episodios": MIN_EPISODES_FOR_CONFIDENCE,
        "tau": TAU, "politicas": veredicto, "mejor_clave_computed": n, "veredicto": fallo,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  guardado en {SALIDA}")


if __name__ == "__main__":
    main()
