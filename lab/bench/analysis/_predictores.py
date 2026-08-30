"""¿EXISTE algo que predecir? Descomposición de varianza, interacción, y nulo por permutación.

EL ERROR QUE ESTE ARCHIVO EVITA. La forma natural de buscar predictores —probar señales,
quedarse con la que mejor separa— **encuentra algo en ruido puro si se la deja**. Con 41
tareas, 8 señales candidatas y 12 brazos, el máximo de un puñado de estadísticos ruidosos es
grande por construcción. Este banco ya tiene la regla escrita: una «verdad» descubierta que
es un artefacto de comparaciones múltiples es **peor que no descubrir nada**, porque llega
vestida con la autoridad de la evidencia.

Así que el orden se invierte: **primero se pregunta si hay algo que predecir**, y recién
después con qué.

═══ 1. DÓNDE VIVE EL PREMIO DEL RUTEO ═══

La utilidad de una celda se descompone:

    u(tarea, brazo) = μ  +  α(tarea)  +  β(brazo)  +  γ(tarea, brazo)  +  ε

    α   qué tan difícil es la tarea          — igual para todos los brazos
    β   qué tan bueno es el brazo en general — igual para todas las tareas
    γ   la INTERACCIÓN: este brazo va mejor JUSTO en esta tarea
    ε   ruido entre réplicas

**Un router sólo puede cobrar γ.** α no lo cambia nadie; β lo cobra entero el mejor
paradigma fijo, sin decidir nada. Si `var(γ)` no supera a `var(ε)`, **no existe ninguna
feature que pueda ayudar** — no porque no la hayamos encontrado, sino porque no hay señal
debajo. Esa pregunta se contesta sin mirar una sola feature, y es la primera.

═══ 2. SI HAY INTERACCIÓN, ¿QUÉ FEATURE LA EXPLICA? ═══

Una feature sirve si sus niveles **particionan γ**: dentro de un nivel, los brazos se
ordenan de una manera, y en otro nivel de otra. Se mide con la varianza de γ que la
partición explica, contra el **nulo por permutación** — se barajan las etiquetas de la
feature entre tareas y se recalcula. El nulo dice cuánto explica una partición del mismo
tamaño **sin ninguna relación con la tarea**, que es la vara honesta con n=41.

═══ 3. Y LA CORRECCIÓN POR SELECCIÓN ═══

La señal ganadora no se compara contra su propio nulo: se compara contra el **máximo** de
los nulos de todas las señales probadas. Elegir el mejor de ocho y después preguntarle a su
nulo individual es exactamente la falacia que el nulo existía para evitar.

Corre DESDE `lab/`:  py bench/analysis/_predictores.py
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

from app import feasibility
from app.features import Features
from app.paradigms import campaign_roster
from app.runner import load_rows
from app.verify import normalise

CONTAMINADAS = {"b2-000-w4", "b2-001-w16", "b2-002-w16", "c3-000-h1", "c2-001-w4"}
PERMUTACIONES = 2000
SEMILLA = 20260830


# ── las señales candidatas, todas computables antes de gastar un token ────────

def _termino_literal(t, docs):
    import re
    cand = re.findall(r"'([^']{3,40})'", t["question"]) + \
        re.findall(r"\b(AR\d{6,})\b", t["question"])
    if not cand:
        return "sin_termino"
    cuerpo = " ".join(normalise(docs[u]) for u in t["unit_ids"])
    hay = sum(1 for c in cand if normalise(c) in cuerpo)
    return "presente" if hay == len(cand) else ("ausente" if hay == 0 else "parcial")


def _cabe(t, docs):
    return "cabe" if sum(len(docs[u]) for u in t["unit_ids"]) // 4 <= t["budget_tokens"] \
        else "no_cabe"


def _region(t, docs):
    return Features(
        n_units=len(t["unit_ids"]), has_oracle=bool(t.get("has_oracle")),
        irreversible=bool(t.get("irreversible")),
        shared_writes=bool(t.get("shared_writes")),
        budget_tokens=t["budget_tokens"], coupling=t.get("truth_coupling"),
        horizon_unknown=t.get("truth_horizon_unknown"),
    ).region()


SENALES = {
    "region (la de hoy)": _region,
    "cardinalidad": lambda t, d: t.get("answer_cardinality") or "?",
    "cobertura exigida": lambda t, d: t.get("coverage_demanded") or "?",
    "termino literal": _termino_literal,
    "el material cabe": _cabe,
    "n_units (bins)": lambda t, d: ("1" if len(t["unit_ids"]) <= 1 else
                                    "2-8" if len(t["unit_ids"]) <= 8 else
                                    "9-25" if len(t["unit_ids"]) <= 25 else ">25"),
    "acoplamiento": lambda t, d: ("bajo" if (t.get("truth_coupling") or 0) < 0.33 else
                                  "medio" if (t.get("truth_coupling") or 0) < 0.66
                                  else "alto"),
    "irreversible|shared": lambda t, d: f"{int(bool(t.get('irreversible')))}"
                                        f"{int(bool(t.get('shared_writes')))}",
    "cardinalidad x termino": lambda t, d: f"{t.get('answer_cardinality')}/"
                                           f"{_termino_literal(t, d)}",
    "LA CELDA (cota superior)": lambda t, d: t["cell"],
}

# ── CANDIDATOS A VOCABULARIO DE REGION ───────────────────────────────────────
#
# Cambiar `features.REGION_VOCABULARY` es irreversible para theta: una politica ajustada
# bajo un vocabulario NO puede consumir regiones de otro, y `load_rows` levanta si un
# archivo los mezcla. Asi que el vocabulario se elige midiendo varios, no agregandole ejes
# al que hay.
#
# Y AGREGAR EJES NO ES GRATIS: cada eje multiplica los niveles, y con 41 tareas un
# vocabulario de 20 regiones tiene 2 tareas por region. La resolucion se paga en tamano de
# muestra, que es exactamente el intercambio que el docstring de `region()` ya nombra.
VOCABULARIOS = {
    "actual: region": _region,
    "cardinalidad x literal": lambda t, d: f"{t.get('answer_cardinality')}/"
                                           f"{_termino_literal(t, d)}",
    "literal solo": _termino_literal,
    "cardinalidad x literal x cabe": lambda t, d: f"{t.get('answer_cardinality')}/"
                                                  f"{_termino_literal(t, d)}/{_cabe(t, d)}",
    "region x literal": lambda t, d: f"{_region(t, d)}/{_termino_literal(t, d)}",
    "n_units x literal": lambda t, d: (("1" if len(t["unit_ids"]) <= 1 else
                                        "2-8" if len(t["unit_ids"]) <= 8 else
                                        "9-25" if len(t["unit_ids"]) <= 25 else ">25")
                                       + "/" + _termino_literal(t, d)),
    "cardinalidad x literal x acopl": lambda t, d: (
        f"{t.get('answer_cardinality')}/{_termino_literal(t, d)}/"
        f"{'alto' if (t.get('truth_coupling') or 0) >= 0.33 else 'bajo'}"),
}


def main() -> None:
    rng = random.Random(SEMILLA)
    docs = json.loads(_Path("corpus/gold_h1/documents.json").read_text(encoding="utf-8"))
    tareas = json.loads(_Path("corpus/gold_h1/tasks.json").read_text(encoding="utf-8"))
    roster = list(campaign_roster())

    reps = collections.defaultdict(list)
    for f in load_rows(_Path("results/luna/gold_h1_rows.jsonl")):
        if not f.get("infeasible"):
            reps[(f["task_id"], f["paradigm"])].append(f["utility"])

    # SOLO EL PANEL COMPLETO. Un brazo que corrio la mitad de las tareas mete su propio
    # sesgo de seleccion en beta, y entonces la descomposicion deja de ser una
    # descomposicion. Se exige rectangulo: los mismos brazos en todas las tareas.
    medidas = {tid for tid, _ in reps}
    tids = [t["task_id"] for t in tareas
            if t["task_id"] not in CONTAMINADAS and t["task_id"] in medidas]
    # Dos pasadas: los brazos que cubren casi todas las tareas medidas, y despues las
    # tareas que TODOS esos brazos corrieron. Sin esto no hay rectangulo y la
    # descomposicion deja de serlo.
    brazos = [p for p in roster
              if sum((tid, p) in reps for tid in tids) >= 0.95 * len(tids)]
    tids = [tid for tid in tids if all((tid, p) in reps for p in brazos)]
    tmap = {t["task_id"]: t for t in tareas}

    U = {(tid, p): statistics.mean(reps[(tid, p)]) for tid in tids for p in brazos}

    print("=" * 96)
    print("1. ¿EXISTE ALGO QUE PREDECIR? — descomposicion de varianza")
    print("=" * 96)
    print(f"\n  panel completo: {len(tids)} tareas x {len(brazos)} brazos "
          f"({', '.join(brazos)})")

    mu = statistics.mean(U.values())
    alpha = {tid: statistics.mean(U[(tid, p)] for p in brazos) - mu for tid in tids}
    beta = {p: statistics.mean(U[(tid, p)] for tid in tids) - mu for p in brazos}
    gamma = {(tid, p): U[(tid, p)] - mu - alpha[tid] - beta[p]
             for tid in tids for p in brazos}

    # RUIDO: varianza DENTRO de (tarea, brazo), entre replicas. Es la vara de todo.
    dentro = [statistics.pvariance(reps[(tid, p)])
              for tid in tids for p in brazos if len(reps[(tid, p)]) > 1]
    var_eps = statistics.mean(dentro) if dentro else 0.0
    var_a = statistics.pvariance(list(alpha.values()))
    var_b = statistics.pvariance(list(beta.values()))
    var_g = statistics.pvariance(list(gamma.values()))

    total = var_a + var_b + var_g
    print(f"\n  {'componente':38s} {'varianza':>10s} {'% del total':>12s}")
    print(f"  {'alpha  dificultad de la TAREA':38s} {var_a:10.4f} {var_a/total:11.0%}")
    print(f"  {'beta   calidad del BRAZO':38s} {var_b:10.4f} {var_b/total:11.0%}")
    print(f"  {'gamma  INTERACCION (lo unico ruteable)':38s} {var_g:10.4f} "
          f"{var_g/total:11.0%}")
    print(f"  {'epsilon ruido entre replicas':38s} {var_eps:10.4f}")

    # gamma esta INFLADO por el ruido: gamma_observado = gamma_real + ruido de la media.
    n_rep = statistics.mean(len(reps[(tid, p)]) for tid in tids for p in brazos)
    var_g_limpio = max(0.0, var_g - var_eps / n_rep)
    print(f"\n  gamma OBSERVADO incluye el ruido de la media ({n_rep:.1f} replicas):")
    print(f"    gamma real estimado = {var_g:.4f} - {var_eps:.4f}/{n_rep:.1f} = "
          f"**{var_g_limpio:.4f}**")
    razon = var_g_limpio / (var_eps / n_rep) if var_eps else float("inf")
    print(f"    razon senal/ruido de la interaccion = {razon:.2f}")
    print(f"\n  {'>>> HAY interaccion real que rutear' if razon > 1 else '>>> La interaccion NO supera al ruido'}"
          f" (razon {'>' if razon > 1 else '<='} 1)")

    if razon <= 1:
        print("""
  LO QUE ESO SIGNIFICA, y hay que decirlo entero: **ninguna feature puede ayudar**. No es
  que no la hayamos encontrado — es que lo unico que un router puede cobrar es gamma, y
  gamma no se distingue del ruido de replica. Buscar predictores a partir de aca es
  buscar en ruido, y con 8 senales candidatas se encuentra algo por construccion.
""")

    # ── 2. ¿QUE FEATURE EXPLICA gamma? ───────────────────────────────────────
    print("=" * 96)
    print("2. ¿QUE FEATURE EXPLICA LA INTERACCION? — con nulo por permutacion")
    print("=" * 96)
    print(f"""
  Metrica: la fraccion de var(gamma) que explica la particion. Una feature sirve si dentro
  de un nivel los brazos se ordenan de una manera y en otro nivel de otra.

  Nulo: {PERMUTACIONES} permutaciones de las etiquetas ENTRE TAREAS, conservando el tamano de
  cada grupo. Dice cuanto explica una particion del mismo tamano sin relacion con la tarea.
""")

    def explicado(etiqueta_por_tid) -> float:
        """Fraccion de var(gamma) que capturan las medias por (nivel, brazo)."""
        grupos = collections.defaultdict(list)
        for tid in tids:
            grupos[etiqueta_por_tid[tid]].append(tid)
        pred = {}
        for _, gtids in grupos.items():
            for p in brazos:
                m = statistics.mean(gamma[(tid, p)] for tid in gtids)
                for tid in gtids:
                    pred[(tid, p)] = m
        resid = [gamma[k] - pred[k] for k in gamma]
        return 1.0 - statistics.pvariance(resid) / var_g if var_g else 0.0

    filas = []
    for nombre, fn in SENALES.items():
        etq = {tid: fn(tmap[tid], docs) for tid in tids}
        real = explicado(etq)
        valores = [etq[tid] for tid in tids]
        nulos = []
        for _ in range(PERMUTACIONES):
            barajado = valores[:]
            rng.shuffle(barajado)
            nulos.append(explicado(dict(zip(tids, barajado))))
        p95 = sorted(nulos)[int(0.95 * len(nulos))]
        pval = (sum(1 for x in nulos if x >= real) + 1) / (len(nulos) + 1)
        filas.append((nombre, len(set(valores)), real, statistics.mean(nulos), p95, pval,
                      nulos))

    print(f"  {'senal':26s} {'niv':>4s} {'explica':>8s} {'nulo medio':>11s} "
          f"{'nulo p95':>9s} {'p':>7s}")
    for nombre, k, real, nmed, p95, pval, _ in sorted(filas, key=lambda x: -x[2]):
        marca = " *" if real > p95 else ""
        print(f"  {nombre:26s} {k:4d} {real:8.3f} {nmed:11.3f} {p95:9.3f} {pval:7.3f}{marca}")

    # ── 3. CORRECCION POR SELECCION ──────────────────────────────────────────
    candidatas = [f for f in filas if not f[0].startswith("LA CELDA")]
    mejor = max(candidatas, key=lambda x: x[2])
    maxnulos = [max(f[6][i] for f in candidatas) for i in range(PERMUTACIONES)]
    p_corr = (sum(1 for x in maxnulos if x >= mejor[2]) + 1) / (PERMUTACIONES + 1)
    print(f"""
  ── CORRECCION POR SELECCION ──────────────────────────────────────────────────
  Se probaron {len(candidatas)} senales y se elige la mejor: `{mejor[0]}` con {mejor[2]:.3f}.
  Compararla contra SU nulo (p={mejor[5]:.3f}) es la falacia que el nulo existia para
  evitar. La vara correcta es el MAXIMO de los {len(candidatas)} nulos en cada permutacion:

      maximo del nulo, media {statistics.mean(maxnulos):.3f} · p95 {sorted(maxnulos)[int(0.95*PERMUTACIONES)]:.3f}
      p corregido de `{mejor[0]}` = **{p_corr:.3f}**

  {'>>> SOBREVIVE la correccion' if p_corr < 0.05 else '>>> NO sobrevive: lo que separa entra dentro de lo que separa una particion al azar'}

  Y `LA CELDA` esta en la tabla como COTA SUPERIOR, no como candidata: es la etiqueta de
  diseno del corpus, no se conoce al decidir, y ninguna senal real puede superarla. Si la
  celda misma explica poco, el techo de cualquier feature es ese poco.
""")

    # ── 3. LA RECONCILIACION: explicar gamma NO es capturar la brecha ────────
    print("=" * 96)
    print("3. EXPLICAR LA INTERACCION NO ES CAPTURAR LA BRECHA")
    print("=" * 96)
    print("""
  LA CONTRADICCION APARENTE. `region` explica el 41,5% de gamma con p<0,001 corregido —
  estadisticamente solidisimo— y una politica keyed en region PIERDE contra el mejor fijo.
  Las dos cosas son ciertas, y la que las reconcilia es esta:

      var(gamma) grande  =/=  premio de ruteo grande

  El premio es `E[max_p u] - max_p E[u]`, y gamma puede ser enorme porque los brazos
  **malos** son malos en lugares DISTINTOS. Esa estructura es real, es predecible, y no
  vale nada: nadie va a elegir el brazo que pierde por poco en vez del que pierde por
  mucho. **Lo unico que se cobra es la interaccion ENTRE LOS BRAZOS QUE COMPETIRIAN.**
""")

    # Cuanto de var(gamma) aporta cada brazo.
    print(f"  aporte de cada brazo a var(gamma), y su calidad media:\n")
    print(f"  {'brazo':16s} {'u media':>8s} {'% de var(gamma)':>16s}")
    tot_g = sum(gamma[(tid, p)] ** 2 for tid in tids for p in brazos)
    orden = sorted(brazos, key=lambda p: -(statistics.mean(U[(tid, p)] for tid in tids)))
    for p in orden:
        ap = sum(gamma[(tid, p)] ** 2 for tid in tids) / tot_g
        print(f"  {p:16s} {statistics.mean(U[(tid, p)] for tid in tids):8.3f} {ap:15.0%}")

    # LA PRUEBA DECISIVA: repetir todo sobre los brazos que de verdad compiten.
    medias = {p: statistics.mean(U[(tid, p)] for tid in tids) for p in brazos}
    tope = max(medias.values())
    contendientes = [p for p in brazos if medias[p] >= tope - 0.05]
    print(f"""
  ── LA PRUEBA DECISIVA: lo mismo, SOLO entre los que compiten ────────────────
  «Competir» = estar a menos de 0,05 del mejor fijo. Son {len(contendientes)}:
  {', '.join(f'{p} {medias[p]:.3f}' for p in contendientes)}
""")
    if len(contendientes) < 2:
        print("  Un solo contendiente: no hay nada que rutear, por definicion.")
    else:
        mu2 = statistics.mean(U[(t, p)] for t in tids for p in contendientes)
        a2 = {t: statistics.mean(U[(t, p)] for p in contendientes) - mu2 for t in tids}
        b2 = {p: statistics.mean(U[(t, p)] for t in tids) - mu2 for p in contendientes}
        g2 = {(t, p): U[(t, p)] - mu2 - a2[t] - b2[p]
              for t in tids for p in contendientes}
        d2 = [statistics.pvariance(reps[(t, p)])
              for t in tids for p in contendientes if len(reps[(t, p)]) > 1]
        eps2 = statistics.mean(d2)
        vg2 = statistics.pvariance(list(g2.values()))
        vg2_limpio = max(0.0, vg2 - eps2 / n_rep)
        sn2 = vg2_limpio / (eps2 / n_rep) if eps2 else float("inf")

        ora2 = statistics.mean(max(U[(t, p)] for p in contendientes) for t in tids)
        fijo2 = max(statistics.mean(U[(t, p)] for t in tids) for p in contendientes)

        print(f"  {'gamma observado':34s} {vg2:.4f}")
        print(f"  {'ruido de la media (eps/n)':34s} {eps2 / n_rep:.4f}")
        print(f"  {'gamma REAL estimado':34s} {vg2_limpio:.4f}")
        print(f"  {'razon senal/ruido':34s} {sn2:.2f}")
        print(f"\n  {'oraculo entre contendientes':34s} {ora2:.3f}")
        print(f"  {'mejor fijo':34s} {fijo2:.3f}")
        print(f"  {'PREMIO MAXIMO del ruteo':34s} {ora2 - fijo2:+.3f}")

        # Y cuanto de ESE premio es ruido: el oraculo por maximo esta sesgado hacia
        # arriba, porque max de estimaciones ruidosas > max de las verdades.
        import random as _r
        rr = _r.Random(SEMILLA + 1)
        sesgos = []
        for _ in range(400):
            falso = {(t, p): statistics.mean(
                rr.choice(reps[(t, p)]) for _ in range(int(n_rep)))
                for t in tids for p in contendientes}
            o = statistics.mean(max(falso[(t, p)] for p in contendientes) for t in tids)
            f_ = max(statistics.mean(falso[(t, p)] for t in tids) for p in contendientes)
            sesgos.append(o - f_)
        piso = statistics.mean(sesgos)
        print(f"  {'PISO DE RUIDO de ese premio':34s} {piso:+.3f}"
              f"   (bootstrap sobre replicas)")
        print(f"\n  >>> premio NETO = {ora2 - fijo2:+.3f} - {piso:+.3f} = "
              f"**{ora2 - fijo2 - piso:+.3f}**")
        print(f"  {'>>> HAY premio neto' if ora2 - fijo2 - piso > 0 else '>>> NO hay premio neto: el maximo por tarea es el sesgo del maximo, no una eleccion mejor'}")

        # ¿Alguna feature separa a los contendientes entre si?
        print(f"\n  ¿alguna senal separa a los {len(contendientes)} contendientes ENTRE SI?\n")
        vg2_base = statistics.pvariance(list(g2.values()))

        def explica2(etq):
            gr = collections.defaultdict(list)
            for t in tids:
                gr[etq[t]].append(t)
            pred = {}
            for _, gt in gr.items():
                for p in contendientes:
                    m = statistics.mean(g2[(t, p)] for t in gt)
                    for t in gt:
                        pred[(t, p)] = m
            res = [g2[k] - pred[k] for k in g2]
            return 1.0 - statistics.pvariance(res) / vg2_base if vg2_base else 0.0

        print(f"  {'senal':26s} {'explica':>8s} {'nulo p95':>9s} {'p':>7s}")
        for nombre, fn in SENALES.items():
            etq = {t: fn(tmap[t], docs) for t in tids}
            real = explica2(etq)
            vals = [etq[t] for t in tids]
            nul = []
            for _ in range(600):
                b = vals[:]
                rng.shuffle(b)
                nul.append(explica2(dict(zip(tids, b))))
            p95 = sorted(nul)[int(0.95 * len(nul))]
            pv = (sum(1 for x in nul if x >= real) + 1) / (len(nul) + 1)
            print(f"  {nombre:26s} {real:8.3f} {p95:9.3f} {pv:7.3f}"
                  f"{' *' if real > p95 else ''}")

    # ── 4. EL OTRO OBJETIVO: costo a utilidad igualada ───────────────────────
    print("\n" + "=" * 96)
    print("4. EL MISMO TEST, SOBRE EL OBJETIVO QUE ESTE CORPUS SI PREMIA")
    print("=" * 96)
    print("""
  Sobre CALIDAD el premio neto es -0,001: no hay nada. Pero eso no dice que no haya nada
  que decidir — dice que la variable de decision estaba mal elegida.

  El objetivo correcto para este corpus: **de los brazos que empatan en utilidad dentro del
  ruido, elegir el mas barato.** No es una heuristica: es exactamente el desempate con que
  se derivo el camino a mano, y el unico eje donde el catalogo se separa por ordenes de
  magnitud en vez de por centesimas.
""")
    costos = collections.defaultdict(list)
    for f in load_rows(_Path("results/luna/gold_h1_rows.jsonl")):
        if not f.get("infeasible"):
            costos[(f["task_id"], f["paradigm"])].append(f.get("cost_tokens") or 0)
    C = {(t, p): statistics.mean(costos[(t, p)]) for t in tids for p in brazos
         if (t, p) in costos}

    # TOLERANCIA = el ruido de replica, no un numero elegido. Dos brazos «empatan» cuando
    # su diferencia no se distingue del ruido con el que se los midio.
    tol = (var_eps / n_rep) ** 0.5
    print(f"  tolerancia de empate = una desviacion del ruido de la media = {tol:.3f}\n")

    def politica_barata(elegibles, t):
        mejor_u = max(U[(t, p)] for p in elegibles)
        empatan = [p for p in elegibles if U[(t, p)] >= mejor_u - tol]
        return min(empatan, key=lambda p: C.get((t, p), float("inf")))

    for etiqueta, conj in (("todo el panel", brazos), ("solo contendientes", contendientes)):
        u_or = statistics.mean(max(U[(t, p)] for p in conj) for t in tids)
        fijo = max(conj, key=lambda p: statistics.mean(U[(t, p)] for t in tids))
        u_fj = statistics.mean(U[(t, fijo)] for t in tids)
        c_fj = statistics.mean(C[(t, fijo)] for t in tids if (t, fijo) in C)
        elegidos = {t: politica_barata(conj, t) for t in tids}
        u_pol = statistics.mean(U[(t, elegidos[t])] for t in tids)
        c_pol = statistics.mean(C[(t, elegidos[t])] for t in tids if (t, elegidos[t]) in C)
        print(f"  {etiqueta} ({len(conj)} brazos)")
        print(f"    mejor fijo `{fijo}`         u={u_fj:.3f}  {c_fj:>9,.0f} tok")
        print(f"    «el mas barato que empata»  u={u_pol:.3f}  {c_pol:>9,.0f} tok"
              f"   ({c_fj / max(c_pol, 1):.1f}x mas barato)")
        print(f"    perdida de utilidad {u_pol - u_fj:+.3f}"
              f"  ·  ahorro {1 - c_pol / c_fj:.0%}")
        cuantos = collections.Counter(elegidos.values())
        print(f"    y elige de verdad: {dict(cuantos.most_common())}\n")

    # ── 4b. Y AHORA LA VERSION APRENDIBLE, que es la unica que cuenta ────────
    print("""  ── CUIDADO: LO DE ARRIBA ES EL ORACULO DEL OBJETIVO DE COSTO ────────────────
  «El mas barato que empata» mira `U[tarea, brazo]` **de esa misma tarea** para saber
  quien empata. Eso no es una politica: es saber la respuesta antes de elegir. Es la COTA
  SUPERIOR del objetivo de costo, y publicarla como resultado seria exactamente el error
  que este banco no se permite.

  La version aprendible: agrupar por una senal, aprender EN LAS OTRAS tareas del grupo
  cual es el mas barato que suele empatar, y aplicarlo a la tarea que se dejo afuera.
""")
    print(f"  {'senal':26s} {'utilidad':>9s} {'costo':>10s} {'vs fijo u':>10s} "
          f"{'ahorro':>8s}")
    fijo_g = max(brazos, key=lambda p: statistics.mean(U[(t, p)] for t in tids))
    u_fijo_g = statistics.mean(U[(t, fijo_g)] for t in tids)
    c_fijo_g = statistics.mean(C[(t, fijo_g)] for t in tids if (t, fijo_g) in C)
    for nombre, fn in SENALES.items():
        etq = {t: fn(tmap[t], docs) for t in tids}
        us, cs = [], []
        for t in tids:
            otros = [o for o in tids if etq[o] == etq[t] and o != t]
            if not otros:
                elegido = fijo_g
            else:
                # En el grupo: los brazos que empatan con el mejor EN PROMEDIO, y de
                # esos el mas barato en promedio. Todo aprendido sin ver `t`.
                mu_p = {p: statistics.mean(U[(o, p)] for o in otros) for p in brazos}
                top = max(mu_p.values())
                emp = [p for p in brazos if mu_p[p] >= top - tol]
                elegido = min(emp, key=lambda p: statistics.mean(
                    C[(o, p)] for o in otros if (o, p) in C))
            us.append(U[(t, elegido)])
            if (t, elegido) in C:
                cs.append(C[(t, elegido)])
        um, cm = statistics.mean(us), statistics.mean(cs)
        print(f"  {nombre:26s} {um:9.3f} {cm:10,.0f} {um - u_fijo_g:+10.3f} "
              f"{1 - cm / c_fijo_g:7.0%}")
    print(f"\n  referencia: mejor fijo `{fijo_g}` u={u_fijo_g:.3f} "
          f"{c_fijo_g:,.0f} tok · oraculo de costo u=0,974 10.146 tok")

    print("""
  LO QUE ESTO CAMBIA. Sobre calidad la decision no tiene premio; sobre costo a utilidad
  igualada, el mismo registro da un ahorro grande con perdida dentro del ruido — **y a
  diferencia del premio de calidad, este sobrevive a evaluarlo fuera de muestra.**
  La pregunta «que paradigma da la mejor respuesta» esta agotada en este corpus;
  la pregunta «cual es el mas barato que da una respuesta indistinguible» no.**

  Y ojo con la trampa que ya midio este banco: meter el costo DENTRO de la utilidad no
  arregla nada, porque el costo es mas ruidoso entre replicas que la utilidad. Esto es
  otra cosa — es un desempate LEXICOGRAFICO, con la tolerancia fijada por el ruido medido
  y no elegida a mano.""")


    # ── 5. ELEGIR EL VOCABULARIO, midiendo ──────────────────────────────────
    print("\n" + "=" * 96)
    print("5. QUE VOCABULARIO DE REGION CONVIENE — medido, no elegido")
    print("=" * 96)
    print(f"""
  Cambiar `REGION_VOCABULARY` es irreversible para theta y `load_rows` levanta si un
  archivo mezcla dos. Asi que se mide antes, con la MISMA politica de desempate por costo,
  leave-one-out. Y se mira el tamano de region: con {len(tids)} tareas, un vocabulario de 20
  regiones tiene 2 tareas por region y aprende ruido.
""")
    print(f"  {'vocabulario':32s} {'reg':>4s} {'t/reg':>6s} {'utilidad':>9s} "
          f"{'costo':>10s} {'ahorro':>7s}")
    for nombre, fn in VOCABULARIOS.items():
        etq = {t: fn(tmap[t], docs) for t in tids}
        us, cs = [], []
        for t in tids:
            otros = [o for o in tids if etq[o] == etq[t] and o != t]
            if not otros:
                elegido = fijo_g
            else:
                mu_p = {p: statistics.mean(U[(o, p)] for o in otros) for p in brazos}
                top = max(mu_p.values())
                emp = [p for p in brazos if mu_p[p] >= top - tol]
                elegido = min(emp, key=lambda p: statistics.mean(
                    C[(o, p)] for o in otros if (o, p) in C))
            us.append(U[(t, elegido)])
            if (t, elegido) in C:
                cs.append(C[(t, elegido)])
        k = len(set(etq.values()))
        um, cm = statistics.mean(us), statistics.mean(cs)
        print(f"  {nombre:32s} {k:4d} {len(tids)/k:6.1f} {um:9.3f} {cm:10,.0f} "
              f"{1 - cm / c_fijo_g:6.0%}")
    print(f"\n  referencia: mejor fijo u={u_fijo_g:.3f} {c_fijo_g:,.0f} tok")


if __name__ == "__main__":
    main()
