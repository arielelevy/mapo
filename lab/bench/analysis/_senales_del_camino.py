"""¿El camino a mano es el perfecto? ¿Y qué SEÑAL lo recuperaría? Cero llamadas al modelo.

DOS PREGUNTAS DISTINTAS, y confundirlas es lo que hace que un análisis de ruteo mienta.

  **1. ¿El camino a mano vale algo?** No alcanza con que se parezca al oráculo: la vara es
  el **mejor paradigma FIJO**. Un camino que elige distinto en cada tarea y termina donde
  termina siempre-`react` no compró nada, y la maquinaria de decidir sale gratis sólo en las
  transparencias.

  **2. ¿Qué señal disponible al decidir lo recuperaría?** Ésta es la del producto. Un camino
  derivado leyendo la pregunta y sabiendo la respuesta no es una política — es una cota
  superior. La pregunta que importa es cuál de las señales que existen ANTES de gastar un
  token separa lo mismo.

CÓMO SE EVALÚA UNA SEÑAL, y por qué no alcanza con «predice bien mi pick». Una señal se
juzga por la **utilidad que una política keyed en ella consigue**, no por su acuerdo con mi
etiqueta: mi etiqueta puede estar mal, y una señal que la reproduce heredaría el error.

  · se agrupan las tareas por el valor de la señal
  · dentro de cada grupo se elige el brazo de mayor utilidad media
  · se mide qué consigue esa elección **en las tareas que no se usaron para elegirla**

**Leave-one-out, y no ajuste en muestra.** Con 41 tareas y pocos segmentos, elegir el mejor
brazo por grupo sobre las mismas tareas donde se lo evalúa infla todo: el grupo de una sola
tarea acierta siempre. LOO no lo arregla del todo pero saca el caso degenerado, que es el
que más miente.

LA VARA, y son tres:

    oráculo         el techo: el mejor brazo factible por tarea. Nadie lo puede alcanzar
    mejor fijo      el piso que hay que superar para que decidir valga la pena
    señal           lo que consigue una política que sólo ve esa señal

Corre DESDE `lab/`:  py bench/analysis/_senales_del_camino.py
"""

from __future__ import annotations

import collections
import json
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import feasibility
from app.features import Features
from app.paradigms import campaign_roster
from app.runner import load_rows
from app.verify import normalise

CONTAMINADAS = {"b2-000-w4", "b2-001-w16", "b2-002-w16", "c3-000-h1", "c2-001-w4"}

# El pick a mano, por celda — el mismo de `bench/oneoff/_camino_por_pregunta.py`.
CAMINO = {
    "C1_single_verifiable": "rewoo", "C2_bulk_independent": "rewoo",
    "C4_aggregate_full_coverage": "rewoo", "C8_currency": "rewoo",
    "C9_declared_roster": "rewoo", "B2_absence": "rewoo",
    "D1_presupposition": "rewoo", "C3_coupled_chain": "react",
    "C7_irreversible": "react", "W1_shared_writes": "react",
}


def pick_a_mano(t: dict) -> str:
    if t["cell"] == "C5_unknown_horizon":
        return "direct" if t["task_id"].endswith("w4") else "react"
    return CAMINO[t["cell"]]


# ─────────────────────────────────────────────────────────────────────────────
# LAS SEÑALES CANDIDATAS. Todas se computan ANTES de gastar un token — es el
# requisito, no una preferencia: una señal que necesita la respuesta no es una señal,
# es el oráculo con otro nombre.
# ─────────────────────────────────────────────────────────────────────────────

def termino_literal(t: dict, docs: dict[str, str]) -> str:
    """¿Hay en la pregunta un término entrecomillado que aparezca LITERAL en el material?

    ES LA SEÑAL QUE SALIÓ DE DERIVAR EL CAMINO A MANO, y la razón de que 57 de las 78
    preguntas se resolvieran con el mismo mecanismo: cuando el término existe verbatim
    —un rol (`'director'`), un número de cuenta (`AR7142464820`), una ciudad— el plan
    completo se puede escribir **antes de ver un resultado**, y ahí un brazo de dos
    llamadas domina a uno de veinte.

    Es aritmética sobre el material, cuesta cero, y usa la misma maquinaria que
    `contracts.term_absence`: contención de una cadena conocida adentro de un texto.
    """
    import re
    q = t["question"]
    candidatos = re.findall(r"'([^']{3,40})'", q) + re.findall(r"\b(AR\d{6,})\b", q)
    if not candidatos:
        return "sin_termino"
    cuerpo = " ".join(normalise(docs[u]) for u in t["unit_ids"])
    presentes = sum(1 for c in candidatos if normalise(c) in cuerpo)
    if presentes == len(candidatos):
        return "literal_presente"
    return "literal_ausente" if presentes == 0 else "literal_parcial"


def cabe(t: dict, docs: dict[str, str]) -> str:
    """¿El material entra en el presupuesto declarado? Aritmética pura."""
    tok = sum(len(docs[u]) for u in t["unit_ids"]) // 4
    return "cabe" if tok <= t["budget_tokens"] else "no_cabe"


def demanda_imposible(t: dict, docs: dict[str, str]) -> str:
    """La pregunta exige cobertura exhaustiva Y el presupuesto la prohíbe.

    ES UN HECHO DECIDIBLE ANTES DE GASTAR, y es la conjunción de dos cosas que el sistema
    ya tiene por separado: `coverage_demanded` lo declara el caller y el tamaño lo cuenta
    la factibilidad. Ninguna de las dos sola dice nada; juntas dicen que **ningún brazo
    puede cumplir lo que la tarea pide**, que es exactamente cuándo un motor debería
    abstenerse o bajar la garantía en vez de elegir topología.
    """
    exh = t.get("coverage_demanded") == "exhaustive"
    return "imposible" if (exh and cabe(t, docs) == "no_cabe") else "satisfacible"


def region_actual(t: dict) -> str:
    f = Features(
        n_units=len(t["unit_ids"]), has_oracle=bool(t.get("has_oracle")),
        irreversible=bool(t.get("irreversible")),
        shared_writes=bool(t.get("shared_writes")),
        budget_tokens=t["budget_tokens"],
        coupling=t.get("truth_coupling"),
        horizon_unknown=t.get("truth_horizon_unknown"),
    )
    return f.region()


SENALES = {
    "region (la de hoy)": lambda t, d: region_actual(t),
    "cardinalidad": lambda t, d: t.get("answer_cardinality") or "?",
    "cobertura exigida": lambda t, d: t.get("coverage_demanded") or "?",
    "termino literal": termino_literal,
    "el material CABE": cabe,
    "demanda IMPOSIBLE": demanda_imposible,
    "cardinalidad x termino": lambda t, d: f"{t.get('answer_cardinality')}/{termino_literal(t, d)}",
    "cardinalidad x cabe": lambda t, d: f"{t.get('answer_cardinality')}/{cabe(t, d)}",
}


def main() -> None:
    docs = json.loads(_Path("corpus/gold_h1/documents.json").read_text(encoding="utf-8"))
    tareas = json.loads(_Path("corpus/gold_h1/tasks.json").read_text(encoding="utf-8"))
    roster = list(campaign_roster())

    filas = [f for f in load_rows(_Path("results/luna/gold_h1_rows.jsonl"))
             if not f.get("infeasible")]
    u = collections.defaultdict(list)
    c = collections.defaultdict(list)
    for f in filas:
        u[(f["task_id"], f["paradigm"])].append(f["utility"])
        c[(f["task_id"], f["paradigm"])].append(f.get("cost_tokens") or 0)

    def med(d, tid, p):
        v = d.get((tid, p))
        return sum(v) / len(v) if v else None

    # Sólo tareas con medición y no contaminadas.
    T = []
    for t in tareas:
        tid = t["task_id"]
        if tid in CONTAMINADAS:
            continue
        fact = [p for p in roster if feasibility.check(p, docs, t).feasible]
        medidos = {p: med(u, tid, p) for p in fact if med(u, tid, p) is not None}
        if not medidos:
            continue
        T.append({"t": t, "tid": tid, "fact": fact, "u": medidos,
                  "c": {p: med(c, tid, p) or 0 for p in medidos}})

    def util(reg, p):
        return reg["u"].get(p)

    oraculo = {r["tid"]: max(r["u"].values()) for r in T}
    n = len(T)

    # ── 1. ¿EL CAMINO A MANO VALE ALGO? La vara es el mejor FIJO ──────────────
    print("=" * 96)
    print("1. ¿EL CAMINO A MANO ES EL PERFECTO?")
    print("=" * 96)

    fijos = {}
    for p in roster:
        vals = [util(r, p) for r in T if util(r, p) is not None]
        if len(vals) >= n * 0.8:      # sólo brazos que corren casi todo
            fijos[p] = sum(vals) / len(vals)
    mejor_fijo = max(fijos, key=fijos.get)

    cam = [util(r, pick_a_mano(r["t"])) for r in T]
    cam_ok = [x for x in cam if x is not None]
    podados = sum(1 for x in cam if x is None)
    u_cam = sum(cam_ok) / len(cam_ok)
    u_ora = sum(oraculo.values()) / n
    u_fij = fijos[mejor_fijo]

    print(f"\n  sobre {n} tareas limpias con medicion"
          f"{f' ({podados} donde el pick quedo PODADO por factibilidad)' if podados else ''}\n")
    print(f"    oraculo (techo, irrealizable)   {u_ora:.3f}")
    print(f"    camino a mano                   {u_cam:.3f}")
    print(f"    mejor FIJO ({mejor_fijo:14s})   {u_fij:.3f}")
    print(f"\n    brecha que el camino CAPTURA sobre el mejor fijo: "
          f"{u_cam - u_fij:+.3f}  "
          f"({(u_cam - u_fij) / (u_ora - u_fij) * 100:.0f}% de la brecha disponible)"
          if u_ora > u_fij else "")
    print(f"    los otros fijos: "
          + " · ".join(f"{p} {v:.3f}" for p, v in
                       sorted(fijos.items(), key=lambda x: -x[1])[:5]))

    # DONDE EL CAMINO PIERDE, Y POR QUE. Un pick equivocado y un brazo roto se ven igual
    # desde el numero, y piden arreglos opuestos.
    print(f"\n  donde el camino NO alcanza el oraculo:")
    print(f"    {'tarea':16s} {'pick':14s} {'u pick':>7s} {'oraculo':>8s}  quien gana")
    for r in sorted(T, key=lambda r: (util(r, pick_a_mano(r["t"])) or 0) - oraculo[r["tid"]]):
        p = pick_a_mano(r["t"])
        up = util(r, p)
        if up is not None and up >= oraculo[r["tid"]] - 1e-9:
            continue
        gana = [q for q, v in r["u"].items() if v >= oraculo[r["tid"]] - 1e-9]
        print(f"    {r['tid']:16s} {p:14s} "
              f"{('PODADO' if up is None else f'{up:7.2f}'):>7s} {oraculo[r['tid']]:8.2f}  "
              f"{','.join(sorted(gana)[:3])}")

    # ── 1b. DE DONDE VIENE EL DEFICIT: ¿mi razonamiento o un brazo roto? ─────
    #
    # Son dos causas que se ven IDENTICAS desde el numero y piden arreglos opuestos. 57 de
    # los 78 picks fueron `rewoo`, y el registro de `rewoo` se hizo con la lectura ROTA
    # (RW-1: llamaba a `read` en 130 de 138 celdas y leia CERO unidades). Asi que una parte
    # del deficit mide un brazo que no podia hacer lo que el camino le pedia, y otra parte
    # mide que el camino eligio mal.
    print(f"\n  el deficit de {u_cam - u_fij:+.3f}, partido en dos:")
    for etiqueta, filtro in (("picks de `rewoo` (brazo ROTO al medir)",
                              lambda r: pick_a_mano(r["t"]) == "rewoo"),
                             ("picks de otros brazos",
                              lambda r: pick_a_mano(r["t"]) != "rewoo")):
        sub = [r for r in T if filtro(r)]
        if not sub:
            continue
        uc = [util(r, pick_a_mano(r["t"])) for r in sub]
        uc = [x for x in uc if x is not None]
        uo = [oraculo[r["tid"]] for r in sub]
        print(f"    {etiqueta:42s} {len(sub):3d} tareas · camino {sum(uc)/len(uc):.3f} "
              f"· oraculo {sum(uo)/len(uo):.3f} · brecha {sum(uo)/len(uo) - sum(uc)/len(uc):+.3f}")

    # ── 1c. EL EJE QUE EL CAMINO SI ESTABA OPTIMIZANDO ───────────────────────
    #
    # El camino se derivo bajo «maxima utilidad y, entre las que empatan, MINIMO COSTO».
    # Juzgarlo solo por utilidad es juzgarlo por la mitad de su objetivo — y el mejor fijo
    # de este corpus es `reflection`, el brazo mas caro del catalogo.
    def costo_medio(elige):
        v = [r["c"][elige(r)] for r in T if elige(r) in r["c"]]
        return sum(v) / len(v)

    c_cam = costo_medio(lambda r: pick_a_mano(r["t"]))
    c_fij = costo_medio(lambda r: mejor_fijo)
    print(f"\n  y el COSTO, que es la mitad del objetivo con que se derivo el camino:")
    print(f"    camino a mano      u={u_cam:.3f}  {c_cam:>9,.0f} tokens/tarea")
    print(f"    {mejor_fijo:18s} u={u_fij:.3f}  {c_fij:>9,.0f} tokens/tarea"
          f"   ({c_fij / max(c_cam, 1):.0f}x mas caro)")
    print(f"\n    utilidad por cada 1.000 tokens:  camino {u_cam / c_cam * 1000:.3f}  ·  "
          f"{mejor_fijo} {u_fij / c_fij * 1000:.3f}")

    # ── 2. QUE SEÑAL LO RECUPERA ─────────────────────────────────────────────
    print("\n" + "=" * 96)
    print("2. QUE SEÑAL DISPONIBLE AL DECIDIR CAPTURA ESA BRECHA")
    print("=" * 96)
    print(f"""
  Politica por señal: agrupar por su valor, elegir el brazo de mayor utilidad media dentro
  del grupo, y medirlo **leave-one-out** — la tarea evaluada no participa de elegir su
  propio ganador. Con {n} tareas y grupos chicos, ajustar en muestra da casi el oraculo y
  no significa nada.
""")
    print(f"  {'señal':26s} {'grupos':>6s} {'LOO':>7s} {'vs fijo':>8s} {'% brecha':>9s}"
          f"  {'acuerdo con':>11s}")
    print(f"  {'':26s} {'':>6s} {'':>7s} {'':>8s} {'':>9s}  {'el camino':>11s}")

    resultados = []
    for nombre, fn in SENALES.items():
        clave = {r["tid"]: fn(r["t"], docs) for r in T}
        logrado, acuerdos = [], 0
        for r in T:
            g = clave[r["tid"]]
            otros = [o for o in T if clave[o["tid"]] == g and o["tid"] != r["tid"]]
            cand = collections.defaultdict(list)
            for o in otros:
                for p, v in o["u"].items():
                    cand[p].append(v)
            # Sólo brazos factibles AQUI, con evidencia en el grupo.
            elegibles = {p: sum(v) / len(v) for p, v in cand.items()
                         if p in r["u"] and len(v) >= 2}
            if not elegibles:
                elegido = max(r["u"], key=lambda p: (r["u"][p], -r["c"][p]))
            else:
                elegido = max(elegibles, key=lambda p: (elegibles[p], -1))
            logrado.append(r["u"][elegido])
            acuerdos += elegido == pick_a_mano(r["t"])
        ul = sum(logrado) / len(logrado)
        pct = (ul - u_fij) / (u_ora - u_fij) * 100 if u_ora > u_fij else 0.0
        resultados.append((nombre, len(set(clave.values())), ul, ul - u_fij, pct,
                           acuerdos / n))
    for nombre, g, ul, d, pct, ac in sorted(resultados, key=lambda x: -x[2]):
        print(f"  {nombre:26s} {g:6d} {ul:7.3f} {d:+8.3f} {pct:8.0f}%  {ac:10.0%}")

    print(f"\n  referencia:  oraculo {u_ora:.3f} · camino a mano {u_cam:.3f} · "
          f"mejor fijo {u_fij:.3f}")


if __name__ == "__main__":
    main()
