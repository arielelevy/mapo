"""RECÓMPUTO PARA LA REVISIÓN DEL 2026-09-01. Cero llamadas al modelo.

Produce, contra el registro vigente y sobre el rectángulo mecánico de `bench.panel`, todos los
números que las dos revisiones externas encontraron desactualizados, mal definidos o sin
script:

  1. conteos de la campaña (filas, tokens, tareas por brazo);
  2. utilidad, pass@1, pass^3 e inestabilidad con la definición correcta (réplicas
     realmente distintas, no `0 < media < 1`);
  3. descomposición de varianza con ddof = 1 y ruido descontado en las tres componentes;
  4. brecha de oráculo con TRES estimadores de piso, para que se vea cuál dice qué:
       (a) el bootstrap del propio estadístico, que es el que usaba `_predictores.py` y
           que por construcción devuelve piso ≈ brecha (se imprime sólo para mostrarlo);
       (b) `metrics.noise_floor`: k réplicas del MISMO brazo como k pseudo-brazos (k = 3);
       (c) pseudo-brazos emparejados por número de brazos: para cada brazo real, se
           remuestrean sus réplicas hasta tener tantos pseudo-brazos como brazos compara el
           panel, y se toma la brecha; media y p95 sobre 400 corridas y sobre los brazos;
     más el intervalo bootstrap pareado (por tarea) de la brecha observada;
  5. lo mismo sobre el held-out, por estrato acumulativo;
  6. degradación por ancho sobre todas las filas factibles;
  7. leave-one-arm-out con el baseline que faltaba: identidad ADITIVA (dificultad de la
     tarea más efecto del brazo, viendo al brazo);
  8. P30 con el registro re-puntuado;
  9. la curva de consenso completa sobre `terra`, restringida a los ocho brazos del panel.

Se corre desde `lab/`:  py bench/analysis/_recomputo_revision.py
"""
from __future__ import annotations

import collections
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np

from app.metrics import Study
from app.runner import load_rows
from app.verify import normalise
from bench.panel import rectangulo

LUNA = Path("results/luna/gold_h1_rows.jsonl")
HOLDOUT = Path("results/luna/gold_holdout_rows.jsonl")
READALL = Path("results/luna/gold_h1_readall_rows.jsonl")
TERRA = Path("results/terra/gold_h1_rows.jsonl")
TASKS = Path("corpus/gold_h1/tasks.json")
SEMILLA = 7
B = 400
BCI = 2000


def celdas(filas):
    reps = collections.defaultdict(list)
    for f in filas:
        if f.get("infeasible"):
            continue
        reps[(f["task_id"], f["paradigm"])].append(float(f.get("utility", 0.0)))
    return reps


def brecha(U, tids, brazos):
    ora = statistics.mean(max(U[(t, p)] for p in brazos) for t in tids)
    fijo = max(statistics.mean(U[(t, p)] for t in tids) for p in brazos)
    return ora, fijo, ora - fijo


def pisos(reps, tids, brazos, rng):
    """Los tres estimadores más el IC pareado. Devuelve un dict con todo."""
    U = {k: statistics.mean(v) for k, v in reps.items()}
    k_rep = min(len(reps[(t, p)]) for t in tids for p in brazos)
    ora, fijo, obs = brecha(U, tids, brazos)
    n_arms = len(brazos)

    # (a) bootstrap del estadístico: el que NO hay que usar como piso
    sesgos = []
    for _ in range(B):
        falso = {(t, p): statistics.mean(rng.choice(reps[(t, p)]) for _ in range(k_rep))
                 for t in tids for p in brazos}
        sesgos.append(brecha(falso, tids, brazos)[2])
    piso_a = statistics.mean(sesgos)

    # (b) metrics.noise_floor por brazo, k = réplicas
    nf = []
    for p in brazos:
        r = {t: reps[(t, p)] for t in tids if len(reps[(t, p)]) >= 2}
        out = Study.noise_floor(r)
        if "noise_oracle_gap" in out:
            nf.append(out["noise_oracle_gap"])
    piso_b_media, piso_b_max = statistics.mean(nf), max(nf)

    # (c) pseudo-brazos emparejados por número de brazos Y por varianza: cada pseudo-brazo
    # vale, por tarea, la MEDIA de k_rep réplicas remuestreadas del brazo real, porque la
    # brecha observada se computa sobre medias de celda y no sobre réplicas sueltas. Usar una
    # réplica suelta por pseudo-brazo infla el piso en ~sqrt(k_rep); el test §60 de
    # `test_science.py` lo detectó sobre brazos idénticos (piso 0,113 contra brecha 0,075).
    todos = []
    por_brazo = {}
    for p in brazos:
        vals = []
        for _ in range(B):
            pseudo = {t: [statistics.mean(rng.choice(reps[(t, p)]) for _ in range(k_rep))
                          for _ in range(n_arms)] for t in tids}
            o = statistics.mean(max(pseudo[t]) for t in tids)
            f_ = max(statistics.mean(pseudo[t][j] for t in tids) for j in range(n_arms))
            vals.append(o - f_)
        por_brazo[p] = statistics.mean(vals)
        todos.extend(vals)
    piso_c_media = statistics.mean(todos)
    piso_c_p95 = sorted(todos)[int(0.95 * len(todos))]

    # IC pareado de la brecha observada, remuestreando TAREAS
    bs = []
    tl = list(tids)
    for _ in range(BCI):
        s = [rng.choice(tl) for _ in tl]
        bs.append(brecha(U, s, brazos)[2])
    bs.sort()
    ic = (bs[int(0.025 * BCI)], bs[int(0.975 * BCI)])

    return dict(oraculo=ora, fijo=fijo, brecha=obs, k_rep=k_rep, n_arms=n_arms,
                piso_a=piso_a, piso_b_media=piso_b_media, piso_b_max=piso_b_max,
                piso_c_media=piso_c_media, piso_c_p95=piso_c_p95, ic=ic,
                neto_b=obs - piso_b_media, neto_c=obs - piso_c_media)


def imprimir_pisos(titulo, d):
    print(f"\n  {titulo}: {d['n_arms']} brazos, k_rep={d['k_rep']}")
    print(f"    oráculo {d['oraculo']:.3f} · mejor fijo {d['fijo']:.3f} · brecha {d['brecha']:+.3f}"
          f"   IC95 pareado [{d['ic'][0]:+.3f}, {d['ic'][1]:+.3f}]")
    print(f"    (a) bootstrap del estadístico (NO usar)   {d['piso_a']:.3f}")
    print(f"    (b) noise_floor, réplicas sueltas como brazos (conservador ~sqrt(k))  "
          f"{d['piso_b_media']:.3f} / {d['piso_b_max']:.3f}   -> neto {d['neto_b']:+.3f}")
    print(f"    (c) pseudo-brazos k={d['n_arms']} con medias de réplicas, media / p95  "
          f"{d['piso_c_media']:.3f} / {d['piso_c_p95']:.3f}   -> neto {d['neto_c']:+.3f}")


def main() -> None:
    rng = random.Random(SEMILLA)
    filas = load_rows(LUNA)
    reps = celdas(filas)
    panel = rectangulo(filas)
    tids, brazos = panel.tareas, panel.brazos
    U = {k: statistics.mean(v) for k, v in reps.items()}

    print("=" * 96)
    print("1. CONTEOS DE LA CAMPAÑA")
    print("=" * 96)
    print(f"  filas (sin infra_error): {len(filas)} · tokens: {sum(f.get('cost_tokens') or 0 for f in filas):,}")
    por_brazo = collections.Counter(f["paradigm"] for f in filas)
    tareas_por_brazo = {p: len({f['task_id'] for f in filas if f['paradigm'] == p}) for p in por_brazo}
    print("  tareas ofrecidas por brazo:", dict(sorted(tareas_por_brazo.items())))
    print(f"  rectángulo mecánico: {panel.descripcion()}")

    print("\n" + "=" * 96)
    print("2. UTILIDAD, pass@1, pass^3 E INESTABILIDAD SOBRE EL RECTÁNGULO")
    print("=" * 96)
    print(f"  {'brazo':16}{'u':>7}{'pass@1':>8}{'pass^3':>8}{'inest. (distintas)':>20}{'inest. (0<m<1)':>16}")
    for p in sorted(brazos, key=lambda p: -statistics.mean(U[(t, p)] for t in tids)):
        us = [reps[(t, p)][:3] for t in tids if len(reps[(t, p)]) >= 3]
        pass1 = statistics.mean(statistics.mean(x) for x in us)
        passk = statistics.mean(1.0 if all(v == 1.0 for v in x) else 0.0 for x in us)
        inest = statistics.mean(1.0 if len(set(x)) > 1 else 0.0 for x in us)
        vieja = statistics.mean(1.0 if 0.0 < statistics.mean(x) < 1.0 else 0.0 for x in us)
        print(f"  {p:16}{statistics.mean(U[(t, p)] for t in tids):7.3f}{pass1:8.3f}{passk:8.3f}"
              f"{inest:19.0%}{vieja:16.0%}")

    print("\n" + "=" * 96)
    print("3. DESCOMPOSICIÓN DE VARIANZA, ddof = 1, ruido descontado")
    print("=" * 96)
    mu = statistics.mean(U[(t, p)] for t in tids for p in brazos)
    a = {t: statistics.mean(U[(t, p)] for p in brazos) - mu for t in tids}
    b = {p: statistics.mean(U[(t, p)] for t in tids) - mu for p in brazos}
    g = [U[(t, p)] - mu - a[t] - b[p] for t in tids for p in brazos]
    eps = statistics.mean(statistics.variance(reps[(t, p)]) for t in tids for p in brazos
                          if len(reps[(t, p)]) > 1)
    n_rep = 3
    va, vb, vg = statistics.variance(list(a.values())), statistics.variance(list(b.values())), statistics.variance(g)
    va_c = max(0.0, va - eps / (n_rep * len(brazos)))
    vb_c = max(0.0, vb - eps / (n_rep * len(tids)))
    vg_c = max(0.0, vg - eps / n_rep)
    expl = va + vb + vg
    expl_c = va_c + vb_c + vg_c
    print(f"  α {va:.4f} ({va/expl:.0%} crudo, {va_c/expl_c:.0%} descontado)")
    print(f"  β {vb:.4f} ({vb/expl:.0%} crudo, {vb_c/expl_c:.0%} descontado)")
    print(f"  γ {vg:.4f} ({vg/expl:.0%} crudo, {vg_c/expl_c:.0%} descontado); γ limpio {vg_c:.4f}; S/R {vg_c/(eps/n_rep):.2f}")
    print(f"  ε {eps:.4f}; total con ε {expl+eps:.4f}; γ sobre el total {vg/(expl+eps):.0%}")

    print("\n" + "=" * 96)
    print("4. BRECHA DE ORÁCULO Y PISOS, EN MUESTRA")
    print("=" * 96)
    medias = {p: statistics.mean(U[(t, p)] for t in tids) for p in brazos}
    best = max(medias.values())
    contendientes = sorted(p for p in brazos if medias[p] >= best - 0.05)
    print("  contendientes (a ≤ 0,05 del mejor fijo):", contendientes)
    imprimir_pisos("tres contendientes", pisos(reps, tids, contendientes, rng))
    imprimir_pisos("ocho brazos", pisos(reps, tids, brazos, rng))
    familias = {"adaptativo": ["react", "reflection"], "plan_fijo": ["dag_strategy", "rewoo"],
                "canal_con_perdida": ["gist_reader", "handoff", "pointer_chase", "supervisor"]}
    rep_fam = {}
    for nombre, miembros in familias.items():
        mejor = max(miembros, key=lambda p: medias[p])
        rep_fam[nombre] = mejor
    reps_f = {(t, nombre): reps[(t, rep_fam[nombre])] for t in tids for nombre in familias}
    print("  familia representada por su mejor brazo:", rep_fam)
    imprimir_pisos("tres familias", pisos(reps_f, tids, sorted(familias), rng))
    gana = collections.Counter(max(familias, key=lambda n: U[(t, rep_fam[n])]) for t in tids)
    print("  familia ganadora por tarea:", dict(gana))

    print("\n" + "=" * 96)
    print("5. HELD-OUT POR ESTRATO ACUMULATIVO")
    print("=" * 96)
    fh = load_rows(HOLDOUT)
    reph = celdas(fh)
    ph = rectangulo(fh)
    print(f"  filas {len(fh)} · tokens {sum(f.get('cost_tokens') or 0 for f in fh):,} · infactibles "
          f"{sum(1 for f in fh if f.get('infeasible'))} · rectángulo {ph.descripcion()}")
    def ancho(t):
        return t.rsplit("-", 1)[-1]
    estratos = [("base+w4", {"w4"}), ("+w16", {"w4", "w16"}), ("+w48", {"w4", "w16", "w48"})]
    for nombre, anchos in estratos:
        ts = [t for t in ph.tareas if ancho(t) in anchos or not ancho(t).startswith("w")]
        filas_e = sum(1 for f in fh if f["task_id"] in ts)
        d = pisos(reph, ts, ph.brazos, rng)
        print(f"\n  estrato {nombre}: {len(ts)} tareas, {filas_e} filas")
        imprimir_pisos(nombre, d)

    print("\n" + "=" * 96)
    print("6. DEGRADACIÓN POR ANCHO, TODAS LAS FILAS FACTIBLES")
    print("=" * 96)
    por = collections.defaultdict(list)
    for f in filas:
        if f.get("infeasible"):
            continue
        w = ancho(f["task_id"])
        if w in ("w4", "w16", "w48"):
            por[(f["paradigm"], w)].append(float(f["utility"]))
    print(f"  {'brazo':16}{'w4':>7}{'w16':>7}{'w48':>7}{'Δ':>8}{'n':>14}")
    for p in sorted(brazos + ["graph_traverse"], key=lambda p: -statistics.mean(por.get((p, 'w4'), [0]))):
        vals = [statistics.mean(por[(p, w)]) if por.get((p, w)) else float('nan') for w in ("w4", "w16", "w48")]
        ns = [len(por.get((p, w), [])) for w in ("w4", "w16", "w48")]
        print(f"  {p:16}{vals[0]:7.2f}{vals[1]:7.2f}{vals[2]:7.2f}{vals[2]-vals[0]:+8.2f}   {ns}")

    print("\n" + "=" * 96)
    print("7. LEAVE-ONE-ARM-OUT: identidad aditiva (dificultad + efecto del brazo, viendo al brazo)")
    print("=" * 96)
    um = {(t, p): U[(t, p)] for t in tids for p in brazos}
    errs = collections.defaultdict(list)
    for fuera in brazos:
        entren = [p for p in brazos if p != fuera]
        dif = {t: statistics.mean(um[(t, p)] for p in entren) for t in tids}
        efecto = statistics.mean(um[(t, fuera)] - dif[t] for t in tids)  # viendo al brazo
        media_fuera = statistics.mean(um[(t, fuera)] for t in tids)        # identidad sin tarea
        for t in tids:
            y = um[(t, fuera)]
            errs["media_global"].append(abs(y - statistics.mean(um[(t2, p)] for t2 in tids for p in entren)))
            errs["dificultad_tarea"].append(abs(y - dif[t]))
            errs["identidad_sin_tarea (paper)"].append(abs(y - media_fuera))
            errs["identidad_aditiva"].append(abs(y - max(0.0, min(1.0, dif[t] + efecto))))
    for k, v in errs.items():
        print(f"  {k:32}{statistics.mean(v):.3f}")

    print("\n" + "=" * 96)
    print("8. P30 CON EL REGISTRO RE-PUNTUADO")
    print("=" * 96)
    if READALL.exists():
        ra = load_rows(READALL)
        w16 = {f["task_id"] for f in ra}
        base = {(f["task_id"], f["trial"]): f for f in filas
                if f["paradigm"] == "react" and f["task_id"] in w16 and not f.get("infeasible")}
        pares = [(base[(f["task_id"], f["trial"])], f) for f in ra
                 if (f["task_id"], f["trial"]) in base and not f.get("infeasible")]
        ub = statistics.mean(float(b_["utility"]) for b_, _ in pares)
        ur = statistics.mean(float(r_["utility"]) for _, r_ in pares)
        tb = statistics.mean(b_["cost_tokens"] for b_, _ in pares)
        tr = statistics.mean(r_["cost_tokens"] for _, r_ in pares)
        cambian = sum(1 for b_, r_ in pares if float(b_["utility"]) != float(r_["utility"]))
        suben = sum(1 for b_, r_ in pares if float(r_["utility"]) > float(b_["utility"]))
        print(f"  pares {len(pares)} · u base {ub:.3f} · u readall {ur:.3f} · tok {tb:,.0f} / {tr:,.0f} "
              f"({tb/tr:.2f}×) · celdas que cambian {cambian} (suben {suben}, bajan {cambian-suben})")

    print("\n" + "=" * 96)
    print("9. CONSENSO EN TERRA, OCHO BRAZOS DEL PANEL, RÉPLICA 0")
    print("=" * 96)
    if TERRA.exists():
        ft = [f for f in load_rows(TERRA) if not f.get("infeasible")]
        bt = set(brazos)
        R, Ut = {}, {}
        for f in ft:
            if f["paradigm"] in bt and f["trial"] == 0:
                R[(f["task_id"], f["paradigm"])] = normalise(f.get("answer") or "")
                Ut[(f["task_id"], f["paradigm"])] = float(f.get("utility", 0.0))
        tt = sorted({t for t, _ in R})
        print(f"  tareas {len(tt)} · filas terra {len(load_rows(TERRA))} · celdas factibles 8 brazos réplica 0 {len(R)}")
        por_k = collections.defaultdict(list)
        dentro3, fuera3, con3 = [], [], set()
        for t in tt:
            cel = [(p, R[(t, p)]) for p in brazos if (t, p) in R and R[(t, p)].strip()]
            cnt = collections.Counter(a for _, a in cel)
            for p, a in cel:
                por_k[cnt[a] - 1].append(Ut[(t, p)])
            may = {a for a, n in cnt.items() if n - 1 >= 3}
            if may:
                con3.add(t)
                for p, a in cel:
                    (dentro3 if a in may else fuera3).append(Ut[(t, p)])
        print(f"  {'k':>4}{'celdas':>9}{'P(correcta)':>14}")
        for k in sorted(por_k):
            print(f"  {k:>4}{len(por_k[k]):>9}{statistics.mean(por_k[k]):>14.3f}")
        for kk in (3, 4):
            v = [u for k, vs in por_k.items() if k >= kk for u in vs]
            tareas_k = len({t for t in tt if any((cnt := collections.Counter(R[(t, p)] for p in brazos if (t, p) in R and R[(t, p)].strip()))[a] - 1 >= kk for a in cnt)})
            print(f"  k ≥ {kk}: {len(v)} celdas, P = {statistics.mean(v):.3f}, {tareas_k} de {len(tt)} tareas")
        print(f"  control k ≥ 3: dentro {statistics.mean(dentro3):.3f} (n={len(dentro3)}) · fuera {statistics.mean(fuera3):.3f} (n={len(fuera3)}) · tareas con consenso {len(con3)}")


if __name__ == "__main__":
    main()
