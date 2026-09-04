"""EDA profunda: ¿hay ALGO, computable antes de decidir, que prediga el mejor brazo?

POR QUÉ EXISTE. `P39` midió que rutear por la tabla de capacidades declarada no cobra el
premio, y el veredicto se quedó en «la tabla está mal». Esto va un paso más atrás y pregunta
qué hay en la pregunta y en el índice, ANTES de correr un brazo, que se correlacione con qué
brazo gana. Es exploración: se mira el dato y se proponen candidatos. Nada de acá es un
resultado establecido, y por eso termina en un test sobre el held-out, que ninguna de estas
features vio.

LAS TRES REGLAS QUE LO MANTIENEN HONESTO:

  1. **Ninguna feature toca el gold.** El eje `ausencia` de la ontología sale de
     `relevant_units == []`, que ES la respuesta: en ausencia no hay unidad que la porte. Usarlo
     para rutear es rutear con la respuesta. Acá se mide con y sin él, y la diferencia entre las
     dos columnas es exactamente lo que la ontología no puede saber en producción.
  2. **La sonda de índice no cuesta un token.** El recuperador léxico corre sobre el corpus sin
     modelo, así que «qué unidades surgirían para esta pregunta» es aritmética sobre el índice y
     está disponible antes de elegir el brazo.
  3. **Todo se evalúa leave-one-task-out y contra el piso p95 por pseudo-brazos**, el mismo
     estimador de §6.2.3 del paper. Y después sobre el held-out, que es el único juez limpio
     de algo que se eligió mirando el rectángulo.

Corre DESDE `lab/`:  py bench/analysis/_eda_ruteo_profunda.py
"""

from __future__ import annotations

import collections
import json
import math
import random
import statistics
import sys as _sys
from pathlib import Path

_sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
_sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np

from app.capacidades import EXIGE, NOMBRES, TIENE
from app.features import entidad_en
from app.retrieval import CorpusView, LexicalRetriever
from app.runner import load_rows
from bench.panel import rectangulo

SEMILLA = 20260904
SALIDA = Path("results/luna/eda_ruteo_profunda.json")
PANELES = {
    "rectángulo": (Path("results/luna/gold_h1_rows.jsonl"), Path("corpus/gold_h1")),
    "held-out": (Path("results/luna/gold_holdout_rows.jsonl"), Path("corpus/gold_holdout")),
}


# ── el mundo, cargado una vez por panel ────────────────────────────────────────────

def cargar(registro: Path, corpus: Path):
    docs = json.loads((corpus / "documents.json").read_text(encoding="utf-8"))
    tareas = {t["task_id"]: t for t in json.loads((corpus / "tasks.json").read_text(encoding="utf-8"))}
    filas = [f for f in load_rows(registro) if not f.get("infeasible")]
    panel = rectangulo(filas)
    ts, bs = sorted(panel.tareas), sorted(panel.brazos)
    reps, costos = collections.defaultdict(list), collections.defaultdict(list)
    for f in filas:
        if f["task_id"] in panel.tareas and f["paradigm"] in panel.brazos:
            reps[(f["task_id"], f["paradigm"])].append(f["utility"])
            costos[(f["task_id"], f["paradigm"])].append(f.get("cost_tokens") or 0)
    U = {k: statistics.mean(v) for k, v in reps.items()}
    C = {k: statistics.mean(v) for k, v in costos.items()}
    return panel, docs, tareas, ts, bs, reps, U, C


# ── las features, todas COMPUTED y ninguna del gold ────────────────────────────────

PALABRAS_ENUM = ("list", "all ", "which ", "who are", "every")
PALABRAS_BOOL = ("did ", "is there", "was there", "does ", "answer '")


def sonda(t: dict, docs: dict, ret: LexicalRetriever) -> dict:
    """La sonda de índice: qué traería el recuperador léxico para esta pregunta.

    Es aritmética sobre el índice, sin modelo, y está disponible antes de elegir el brazo.
    Devuelve concentración y cobertura, que son las dos cosas que un arnés querría saber:
    ¿la evidencia está en una unidad o repartida?

    LA VISTA SE CONSTRUYE SIN `relevant_units`: ese campo es el gold. `_scored` sólo mira
    `documents` y `unit_ids`, así que la sonda no puede ver la respuesta ni por accidente.
    """
    alcance = [u for u in t["unit_ids"] if u in docs]
    vista = CorpusView(task_id=t["task_id"], documents={u: docs[u] for u in alcance},
                       unit_ids=alcance, relevant_units=[])
    puntajes = [s for s, _ in ret._scored(vista, t["question"])[:10]]
    top = puntajes[0] if puntajes else 0.0
    seg = puntajes[1] if len(puntajes) > 1 else 0.0
    suma = sum(puntajes) or 1.0
    return {
        "sonda_hits": float(len(puntajes)),
        "sonda_cobertura": len(puntajes) / max(1, len(alcance)),
        "sonda_top": top,
        "sonda_concentracion": (top - seg) / (top or 1.0),
        "sonda_entropia": -sum((p / suma) * math.log((p / suma) + 1e-12) for p in puntajes),
    }


def features(t: dict, docs: dict, ret: LexicalRetriever, con_gold: bool) -> dict:
    alcance = [u for u in t["unit_ids"] if u in docs]
    material = sum(len(docs[u]) for u in alcance) // 4
    q = t["question"].lower()
    lit = 0
    ent = entidad_en(t["question"])
    if ent:
        lit = sum(1 for u in alcance if ent.lower() in docs[u].lower())
    f = {
        "n_units": float(len(alcance)),
        "material_tokens": float(material),
        "cabe": 1.0 if material <= (t.get("budget_tokens") or 0) else 0.0,
        "ratio_presupuesto": material / max(1.0, float(t.get("budget_tokens") or 1)),
        "card_singular": 1.0 if t.get("answer_cardinality") == "singular" else 0.0,
        "card_enumerativa": 1.0 if t.get("answer_cardinality") == "enumerative" else 0.0,
        "card_agregada": 1.0 if t.get("answer_cardinality") == "aggregate" else 0.0,
        "card_booleana": 1.0 if t.get("answer_cardinality") == "boolean" else 0.0,
        "entidad_nombrada": 1.0 if ent else 0.0,
        "literal_en_unidades": float(lit),
        "literal_disperso": 1.0 if lit >= 2 else 0.0,
        "literal_ausente": 1.0 if (ent and lit == 0) else 0.0,
        "q_tokens": float(len(q.split())),
        "q_enumerativa": 1.0 if any(w in q for w in PALABRAS_ENUM) else 0.0,
        "q_booleana": 1.0 if any(w in q for w in PALABRAS_BOOL) else 0.0,
        "irreversible": 1.0 if t.get("irreversible") else 0.0,
        "shared_writes": 1.0 if t.get("shared_writes") else 0.0,
    }
    f.update(sonda(t, docs, ret))
    if con_gold:
        # SÓLO PARA MEDIR LA DIFERENCIA. Es el gold, no está en producción.
        f["gold_ausencia"] = 0.0 if t.get("relevant_units") else 1.0
        f["gold_n_portadoras"] = float(len(t.get("relevant_units") or []))
    return f


# ── el piso de ruido, el mismo estimador del paper ─────────────────────────────────

def piso_p95(reps, ts, bs, rng, B=400):
    k = min(len(reps[(t, p)]) for t in ts for p in bs)
    n = len(bs)
    vals = []
    for p in bs:
        for _ in range(B):
            ps = {t: [statistics.mean(rng.choice(reps[(t, p)]) for _ in range(k))
                      for _ in range(n)] for t in ts}
            o = statistics.mean(max(ps[t]) for t in ts)
            fj = max(statistics.mean(ps[t][j] for t in ts) for j in range(n))
            vals.append(o - fj)
    vals.sort()
    return statistics.mean(vals), vals[int(0.95 * len(vals))]


# ── el Teorema 1 del paper, con sus parámetros medidos ─────────────────────────────

def umbral_teorema(ts, bs, U):
    """Los términos de `V(r) − V(p⋆) = Σⱼ (π_j α_j G_j − ν_j β_j L_j)`, medidos.

    ES EL INSTRUMENTO DEL PAPER USADO PARA LO QUE FUE HECHO. §4.2 dice que la identidad
    existe para que una evaluación de ruteo sea falsable; esto la instancia sobre el
    registro y devuelve `β_max`, la fracción de errores que un ruteador puede permitirse
    ANTES de perderle a siempre-fallback, suponiendo `α = 1`: que acierta en TODAS las
    tareas donde el brazo elegido gana.

    Un brazo con `π = 0` no le gana al fallback en ninguna tarea del panel, así que
    rutearle nunca se justifica y su `β_max` es cero. Eso no es una opinión sobre el brazo:
    es una cota sobre cualquier política que lo elija.
    """
    fijo = max(bs, key=lambda p: statistics.mean(U[(t, p)] for t in ts))
    filas, suma_pg, suma_nl = [], 0.0, 0.0
    for p in bs:
        if p == fijo:
            continue
        d = [U[(t, p)] - U[(t, fijo)] for t in ts]
        pos = [x for x in d if x > 1e-9]
        neg = [-x for x in d if x < -1e-9]
        pi, nu = len(pos) / len(d), len(neg) / len(d)
        G = statistics.mean(pos) if pos else 0.0
        L = statistics.mean(neg) if neg else 0.0
        suma_pg += pi * G
        suma_nl += nu * L
        filas.append({"brazo": p, "pi": round(pi, 3), "tau": round(1 - pi - nu, 3),
                      "nu": round(nu, 3), "G": round(G, 3), "L": round(L, 3),
                      "beta_max": round((pi * G) / (nu * L), 3) if nu * L else None})
    return {"fallback": fijo, "suma_pi_G": round(suma_pg, 4), "suma_nu_L": round(suma_nl, 4),
            "beta_max_global": round(suma_pg / suma_nl, 4) if suma_nl else None,
            "por_brazo": filas}


# ── correlaciones: cada feature contra el margen de cada brazo ─────────────────────

def correlaciones(ts, bs, U, F, nombres):
    """r de Pearson entre cada feature y el margen del brazo contra el mejor fijo.

    El margen y no la utilidad: lo que un ruteador necesita saber es DÓNDE un brazo gana
    respecto del que correría siempre, no si la tarea es fácil.
    """
    fijo = max(bs, key=lambda p: statistics.mean(U[(t, p)] for t in ts))
    out = []
    for nombre in nombres:
        x = np.array([F[t][nombre] for t in ts])
        if x.std() < 1e-12:
            continue
        fila = {"feature": nombre, "por_brazo": {}}
        mejor_abs = 0.0
        for p in bs:
            if p == fijo:
                continue
            y = np.array([U[(t, p)] - U[(t, fijo)] for t in ts])
            if y.std() < 1e-12:
                continue
            r = float(np.corrcoef(x, y)[0, 1])
            fila["por_brazo"][p] = round(r, 3)
            mejor_abs = max(mejor_abs, abs(r))
        fila["max_abs"] = round(mejor_abs, 3)
        out.append(fila)
    return fijo, sorted(out, key=lambda d: -d["max_abs"])


# ── políticas ──────────────────────────────────────────────────────────────────────

def evaluar(ts, bs, U, C, decidir, rng, B=2000):
    """LOTO: el mejor fijo también se aprende sin la tarea evaluada."""
    def fijo_sin(t):
        otros = [o for o in ts if o != t]
        return max(bs, key=lambda p: statistics.mean(U[(o, p)] for o in otros))
    elegidos = {t: decidir(t, [o for o in ts if o != t]) for t in ts}
    dif = [U[(t, elegidos[t])] - U[(t, fijo_sin(t))] for t in ts]
    boot = sorted(statistics.mean([rng.choice(dif) for _ in dif]) for _ in range(B))
    return {"utilidad": round(statistics.mean(U[(t, elegidos[t])] for t in ts), 4),
            "delta": round(statistics.mean(dif), 4),
            "ic95": [round(boot[int(0.025 * B)], 4), round(boot[int(0.975 * B)], 4)],
            "tokens": round(statistics.mean(C[(t, elegidos[t])] for t in ts)),
            "rutea": sum(1 for t in ts if elegidos[t] != fijo_sin(t)),
            "elige": dict(collections.Counter(elegidos.values()).most_common(4))}


def pesos_por_capacidad(ts, bs, U, F, ejes_fn, tareas):
    """EXIGE MEDIDO en vez de declarado: cuánto paga cada capacidad en cada eje.

    Es la mitad que `P39` dejó sin medir. `TIENE` sigue declarado desde el código, que es lo
    que le permite hablar de un brazo que no corrió; lo que se aprende es el PESO de cada
    capacidad cuando un eje está activo.
    """
    w = collections.defaultdict(float)
    for eje in EXIGE:
        tareas_eje = [t for t in ts if eje in ejes_fn(tareas[t])]
        if len(tareas_eje) < 4:
            continue
        fijo = max(bs, key=lambda p: statistics.mean(U[(t, p)] for t in ts))
        for c in NOMBRES:
            con = [U[(t, p)] - U[(t, fijo)] for t in tareas_eje for p in bs if c in TIENE.get(p, set())]
            sin = [U[(t, p)] - U[(t, fijo)] for t in tareas_eje for p in bs if c not in TIENE.get(p, set())]
            if len(con) >= 3 and len(sin) >= 3:
                w[(eje, c)] = statistics.mean(con) - statistics.mean(sin)
    return w


def ridge(X, y, lam=1.0):
    return np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)


def main() -> None:
    rng = random.Random(SEMILLA)
    ret = LexicalRetriever()
    from bench.analysis._eda_capacidades import ejes_de
    resultados = {}

    for etiqueta, (registro, corpus) in PANELES.items():
        panel, docs, tareas, ts, bs, reps, U, C = cargar(registro, corpus)
        for t in tareas.values():
            t["_material_tokens"] = sum(len(docs.get(u, "")) for u in t["unit_ids"]) // 4
        F = {t: features(tareas[t], docs, ret, con_gold=True) for t in ts}
        nombres_prod = [n for n in F[ts[0]] if not n.startswith("gold_")]
        nombres_todos = list(F[ts[0]])

        print("=" * 96)
        print(f"PANEL: {etiqueta} · {panel.descripcion()}")
        print("=" * 96)

        fijo, corrs = correlaciones(ts, bs, U, F, nombres_todos)
        pm, pp95 = piso_p95(reps, ts, bs, random.Random(SEMILLA))
        ora = statistics.mean(max(U[(t, p)] for p in bs) for t in ts)
        u_fijo = statistics.mean(U[(t, fijo)] for t in ts)
        print(f"  mejor fijo `{fijo}` {u_fijo:.3f} · oráculo {ora:.3f} · brecha {ora - u_fijo:+.3f}"
              f" · piso media {pm:.3f} p95 {pp95:.3f}")

        print(f"\n  1. CORRELACIÓN feature → margen del brazo contra `{fijo}` (|r| máximo y el brazo)")
        for d in corrs[:14]:
            top = max(d["por_brazo"].items(), key=lambda kv: abs(kv[1]))
            marca = "  <- GOLD, no existe al decidir" if d["feature"].startswith("gold_") else ""
            print(f"     {d['feature']:22} |r|max {d['max_abs']:.3f}  ({top[0]} {top[1]:+.3f}){marca}")

        # ── políticas ──────────────────────────────────────────────────────────────
        print("\n  2. POLÍTICAS, leave-one-task-out")
        print(f"     {'política':46} {'u':>6} {'Δ':>8} {'IC95':>20} {'rutea':>6}")
        pol = {}

        def reg(nombre, fn):
            r = evaluar(ts, bs, U, C, fn, random.Random(SEMILLA))
            pol[nombre] = r
            cruza = "  *" if r["delta"] > pp95 else ""
            print(f"     {nombre:46} {r['utilidad']:6.3f} {r['delta']:+8.3f} "
                  f"[{r['ic95'][0]:+.3f}, {r['ic95'][1]:+.3f}]  {r['rutea']:>6}{cruza}")

        def ridge_sobre(nombres):
            def fn(t, otros):
                X = np.array([[1.0] + [F[o][n] for n in nombres] + list(cap(p))
                              for o in otros for p in bs])
                y = np.array([U[(o, p)] for o in otros for p in bs])
                Xi = np.array([np.concatenate([[1.0], [F[o][n] for n in nombres], cap(p),
                                               np.outer([F[o][n] for n in nombres], cap(p)).ravel()])
                               for o in otros for p in bs])
                w = ridge(Xi, y, 3.0)
                def punt(p):
                    v = np.concatenate([[1.0], [F[t][n] for n in nombres], cap(p),
                                        np.outer([F[t][n] for n in nombres], cap(p)).ravel()])
                    return float(v @ w)
                return max(bs, key=punt)
            return fn

        cap = lambda p: np.array([1.0 if c in TIENE.get(p, set()) else 0.0 for c in NOMBRES])

        # a. EXIGE medido: el peso de cada capacidad por eje, aprendido
        def pol_exige_medido(t, otros):
            w = pesos_por_capacidad(otros, bs, U, F, ejes_de, tareas)
            ejes = ejes_de(tareas[t])
            def punt(p):
                return sum(w[(e, c)] for e in ejes for c in TIENE.get(p, set()))
            mejor = max(bs, key=punt)
            return mejor if punt(mejor) > 0 else max(
                bs, key=lambda q: statistics.mean(U[(o, q)] for o in otros))
        reg("EXIGE medido (peso por eje × capacidad)", pol_exige_medido)

        # b. ridge sobre features de produccion × capacidades
        top_prod = [d["feature"] for d in corrs if d["feature"] in nombres_prod][:6]
        reg(f"ridge: {len(top_prod)} features × capacidades", ridge_sobre(top_prod))

        # c. la misma con el gold, para medir el techo que la ontologia promete
        top_gold = [d["feature"] for d in corrs][:6]
        reg("ridge: idem, pero con el GOLD adentro (techo)", ridge_sobre(top_gold))

        # d. tabla por celda de la feature mas correlacionada, agrupando
        def por_grupo(nombre, bins=3):
            xs = sorted(F[t][nombre] for t in ts)
            cortes = [xs[int(len(xs) * q)] for q in (0.33, 0.66)]
            def grupo(t):
                v = F[t][nombre]
                return 0 if v <= cortes[0] else (1 if v <= cortes[1] else 2)
            def fn(t, otros):
                g = grupo(t)
                mismos = [o for o in otros if grupo(o) == g] or otros
                return max(bs, key=lambda p: statistics.mean(U[(o, p)] for o in mismos))
            return fn
        if top_prod:
            reg(f"agrupar por `{top_prod[0]}` (3 bins)", por_grupo(top_prod[0]))

        th = umbral_teorema(ts, bs, U)
        print(f"\n3. TEOREMA 1 INSTANCIADO · fallback `{th['fallback']}`")
        print(f"     {'brazo':15}{'pi':>7}{'tau':>7}{'nu':>7}{'G':>8}{'L':>8}{'beta_max':>10}")
        for fila in th["por_brazo"]:
            bm = "  0.000" if fila["beta_max"] is None else f"{fila['beta_max']:10.3f}"
            print(f"     {fila['brazo']:15}{fila['pi']:7.3f}{fila['tau']:7.3f}{fila['nu']:7.3f}"
                  f"{fila['G']:8.3f}{fila['L']:8.3f}{bm}")
        print(f"     Σ π·G = {th['suma_pi_G']:.3f}  ·  Σ ν·L = {th['suma_nu_L']:.3f}"
              f"  ·  β_max con α=1 = {th['beta_max_global']:.3f}")
        print(f"     Un ruteador perfecto donde gana puede equivocarse en el "
              f"{100 * th['beta_max_global']:.1f}% de donde pierde, y nada más.")

        resultados[etiqueta] = {
            "teorema_1": th,
            "panel": panel.descripcion(), "mejor_fijo": fijo,
            "u_fijo": round(u_fijo, 4), "oraculo": round(ora, 4),
            "brecha": round(ora - u_fijo, 4),
            "piso_media": round(pm, 4), "piso_p95": round(pp95, 4),
            "correlaciones": corrs[:20], "politicas": pol,
            "features_produccion": nombres_prod, "top_produccion": top_prod,
        }
        print()

    SALIDA.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"guardado en {SALIDA}")


if __name__ == "__main__":
    main()
