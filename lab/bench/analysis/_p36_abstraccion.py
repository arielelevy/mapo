"""P36 — ¿LA ETAPA DE ABSTRACCIÓN PROPONE SOLA EL EJE QUE A P15 LE FALTABA? Cero llamadas.

LA APUESTA, registrada el 2026-09-03 en `historico/BITACORA-PREDICCIONES.es.md` antes de correr.
El primer episodio del ciclo (P15, mundo `gold_transfer`, semilla 47, `gpt-5.4-nano`) perdió
−0,087 porque el vocabulario de región no tenía eje de horizonte, y la reparación fue un
sensor nuevo, `measure_continuation`, que escribió una persona. El paper afirma que eso es
DISEÑO y no plasticidad, y deja registrado que la etapa de abstracción proponiendo ejes sola
«está en el diseño y no corrió». Acá corre.

QUÉ SE LE DA. El registro de P15 (390 filas, cinco brazos) con features CRUDOS del material,
computados acá como estadísticas genéricas de texto sobre `(pregunta, unidades)`, sin el
sensor de continuidad y sin ninguna forma de token tipada: largos, cantidad de literales
citados, solapamiento léxico entre unidades, cuántos tokens recurren entre unidades, y en
qué fracción de ellas. Ninguna infiere el TIPO de tarea del fraseo de la pregunta.

QUÉ HACE LA ETAPA. `discover_partitions` es la que corre en `sleep_cycle`: umbrales alineados
a un eje, propuestos sobre la mitad de búsqueda y puntuados sobre la de validación, partidas
por TAREA. Se corre con la partición canónica (orden de `task_id`, 50/25) y con 200
particiones al azar, porque 26 tareas son pocas y una sola partición puede esconder o inventar.

CRITERIO REGISTRADO (P36): éxito si una partición sobreviviente separa el horizonte
desconocido 6 de 6 sin falsos positivos; parcial si 4 o 5 de 6; fracaso si nada separa, y
entonces la reparación del vocabulario queda como método de desarrollo, que es lo que el paper
afirma hoy.

Corre DESDE `lab/`:  py bench/analysis/_p36_abstraccion.py
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import collections
import itertools
import json
import random
import re
import statistics
from pathlib import Path

_sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.consolidation import MIN_SIDE_EPISODES, discover_partitions
from app.features import measure_continuation

FILAS = Path("results/archivo-2026-08-29-pre-K6/gold_transfer_rows.jsonl")
CORPUS = Path("corpus/gold_transfer")
SALIDA = Path("results/nano/p36_verdicto.json")
PARTICIONES_AL_AZAR = 200
SEMILLA = 47

STOP = set("""the a an and or of to in on for by with from at as is are was were be been this that
these those it its their his her they them who whom which what when where how not no any all each
every than then there here into over under about after before between during without within also
if but so such per via""".split())
_TOK = re.compile(r"[A-Za-z][A-Za-z0-9\-]{2,}")


def _tokens(texto: str) -> set[str]:
    return {t.lower() for t in _TOK.findall(texto) if t.lower() not in STOP}


def features_crudos(tarea: dict, docs: dict[str, str]) -> dict[str, float]:
    """Estadísticas genéricas de (pregunta, material). Ninguna es un sensor tipado."""
    q = tarea["question"]
    uids = [u for u in tarea["unit_ids"] if u in docs]
    textos = [docs[u] for u in uids]
    n = len(uids)
    toks = [_tokens(t) for t in textos]
    largos = [len(t) for t in textos] or [0]

    # recurrencia genérica: en cuántas unidades aparece cada token (todos, sin tipar)
    cuenta: collections.Counter = collections.Counter()
    for s in toks:
        cuenta.update(s)
    en_dos_o_mas = [c for c in cuenta.values() if c >= 2]
    techo = max(2, n // 2)
    en_rango_medio = sum(1 for c in cuenta.values() if 2 <= c <= techo)
    # tokens con dígitos (cualquier forma) y tokens capitalizados, repetidos entre unidades
    cap: collections.Counter = collections.Counter()
    dig: collections.Counter = collections.Counter()
    for t in textos:
        caps = {w for w in re.findall(r"\b[A-Z][a-z]{2,}\b", t)}
        digs = {w.lower() for w in _TOK.findall(t) if any(ch.isdigit() for ch in w)}
        cap.update(caps); dig.update(digs)
    # solapamiento léxico entre unidades
    jac = []
    for a, b in itertools.combinations(range(n), 2):
        u = toks[a] | toks[b]
        jac.append(len(toks[a] & toks[b]) / len(u) if u else 0.0)
    qt = {t for t in _tokens(q) if len(t) >= 5}
    cubre_q = sum(1 for s in toks if s & qt) / n if n else 0.0

    return {
        "raw_n_units": float(n),
        "raw_budget_tokens": float(tarea["budget_tokens"]),
        "raw_total_chars": float(sum(largos)),
        "raw_mean_unit_chars": float(statistics.mean(largos)),
        "raw_unit_len_cv": float(statistics.pstdev(largos) / statistics.mean(largos)) if n and statistics.mean(largos) else 0.0,
        "raw_question_chars": float(len(q)),
        "raw_q_quoted_literals": float(len(re.findall(r"'[^']{3,40}'|\"[^\"]{3,40}\"", q))),
        "raw_q_digit_runs": float(len(re.findall(r"\d+", q))),
        "raw_jaccard_mean": float(statistics.mean(jac)) if jac else 0.0,
        "raw_shared_token_frac": float(len(en_dos_o_mas) / len(cuenta)) if cuenta else 0.0,
        "raw_max_token_coverage": float(max(cuenta.values()) / n) if cuenta and n else 0.0,
        "raw_tokens_recurring_2_to_half": float(en_rango_medio),
        "raw_cap_tokens_in_2plus": float(sum(1 for c in cap.values() if c >= 2)),
        "raw_digit_tokens_in_2plus": float(sum(1 for c in dig.values() if c >= 2)),
        "raw_units_touching_question": float(cubre_q),
    }


def evaluar_split(attr: str, umbral: float, feats: dict[str, dict[str, float]],
                  horizonte: set[str]) -> dict:
    """¿El lado alto (o el bajo) del umbral es exactamente el conjunto de horizonte?"""
    alto = {t for t, f in feats.items() if f[attr] > umbral}
    bajo = set(feats) - alto
    mejor = None
    for lado, nombre in ((alto, "alto"), (bajo, "bajo")):
        tp = len(lado & horizonte); fp = len(lado - horizonte)
        cand = dict(lado=nombre, tp=tp, fp=fp, fn=len(horizonte - lado))
        if mejor is None or (cand["tp"] - cand["fp"]) > (mejor["tp"] - mejor["fp"]):
            mejor = cand
    return mejor


def main() -> None:
    tareas = json.loads((CORPUS / "tasks.json").read_text(encoding="utf-8"))
    docs = json.loads((CORPUS / "documents.json").read_text(encoding="utf-8"))
    tmap = {t["task_id"]: t for t in tareas}
    horizonte = {t["task_id"] for t in tareas if t.get("truth_horizon_unknown")}

    filas = [json.loads(l) for l in FILAS.read_text(encoding="utf-8").splitlines() if l.strip()]
    filas = [f for f in filas if not f.get("infeasible") and not f.get("infra_error")]
    feats = {tid: features_crudos(tmap[tid], docs) for tid in tmap}
    attrs = sorted(next(iter(feats.values())).keys())
    for f in filas:
        f.update(feats[f["task_id"]])

    print("=" * 96)
    print("P36 · ¿LA ETAPA DE ABSTRACCIÓN PROPONE SOLA EL EJE DE HORIZONTE?")
    print("=" * 96)
    print(f"\n  registro P15: {len(filas)} filas aprendibles · {len(tmap)} tareas · "
          f"{len({f['paradigm'] for f in filas})} brazos · horizonte desconocido: {sorted(horizonte)}")
    print(f"  {len(attrs)} features crudos del material, sin sensor tipado · piso por lado {MIN_SIDE_EPISODES} filas\n")

    # referencia: lo que el sensor escrito por una persona separa sobre este corpus
    cont = {tid: measure_continuation(docs, tmap[tid]["unit_ids"]) for tid in tmap}
    positivos = {t for t, v in cont.items() if v}
    print(f"  referencia · `measure_continuation` (el sensor humano): "
          f"{len(positivos & horizonte)} de {len(horizonte)} horizonte, "
          f"{len(positivos - horizonte)} falsos positivos\n")

    # ---- partición canónica, la de sleep_cycle
    ids = sorted(tmap)
    a, b = int(len(ids) * 0.5), int(len(ids) * 0.75)
    search, validate = set(ids[:a]), set(ids[a:b])
    cand = discover_partitions([f for f in filas if f["task_id"] in search],
                               [f for f in filas if f["task_id"] in validate], attrs)
    print("  partición canónica (orden de task_id · 50% busca · 25% valida):")
    print(f"  {'atributo':<34}{'umbral':>10}{'sep.busca':>10}{'sep.valida':>11}{'sobrevive':>10}{'horizonte':>18}")
    canon = []
    for c in cand:
        ev = evaluar_split(c.attribute, c.threshold, feats, horizonte)
        canon.append({**c.as_dict(), "horizonte": ev})
        hz = f"{ev['tp']}/{len(horizonte)} tp · {ev['fp']} fp"
        print(f"  {c.attribute:<34}{c.threshold:>10.3g}{c.separation_search:>10.3f}"
              f"{c.separation_validate:>11.3f}{'sí' if c.survives else 'no':>10}{hz:>18}")
    if not cand:
        print("  (ninguna candidata alcanzó el piso de separación o de filas por lado)")

    # ---- 200 particiones al azar de las tareas, mismo 50/25
    rng = random.Random(SEMILLA)
    sobrevivientes: collections.Counter = collections.Counter()
    exactas: collections.Counter = collections.Counter()
    mejor_global = None
    for _ in range(PARTICIONES_AL_AZAR):
        orden = ids[:]
        rng.shuffle(orden)
        s, v = set(orden[:a]), set(orden[a:b])
        for c in discover_partitions([f for f in filas if f["task_id"] in s],
                                     [f for f in filas if f["task_id"] in v], attrs):
            if not c.survives:
                continue
            sobrevivientes[c.attribute] += 1
            ev = evaluar_split(c.attribute, c.threshold, feats, horizonte)
            if ev["tp"] == len(horizonte) and ev["fp"] == 0:
                exactas[c.attribute] += 1
            score = ev["tp"] - ev["fp"]
            if mejor_global is None or score > mejor_global[0]:
                mejor_global = (score, c.attribute, c.threshold, ev)

    print(f"\n  {PARTICIONES_AL_AZAR} particiones al azar · sobrevivientes por atributo:")
    for at, k in sobrevivientes.most_common():
        print(f"    {at:<34} sobrevive en {k:>3} · separa el horizonte exacto (6/6, 0 fp) en {exactas[at]:>3}")
    if not sobrevivientes:
        print("    ninguna partición sobrevivió la validación en ninguna de las 200")

    # ---- veredicto
    mejor_canon = max(canon, key=lambda c: c["horizonte"]["tp"] - c["horizonte"]["fp"], default=None)
    surv_canon = [c for c in canon if c["survives"]]
    exacto_canon = [c for c in surv_canon if c["horizonte"]["tp"] == len(horizonte) and c["horizonte"]["fp"] == 0]
    parcial_canon = [c for c in surv_canon if c["horizonte"]["tp"] >= 4 and c["horizonte"]["fp"] <= 1]
    if exacto_canon:
        veredicto = ("ÉXITO: una partición sobreviviente separa el horizonte 6/6 sin falsos positivos; "
                     f"eje propuesto: {exacto_canon[0]['attribute']} > {exacto_canon[0]['threshold']:.3g}")
    elif parcial_canon:
        c = parcial_canon[0]
        veredicto = (f"PARCIAL: {c['attribute']} > {c['threshold']:.3g} separa {c['horizonte']['tp']}/6 "
                     f"con {c['horizonte']['fp']} fp")
    else:
        veredicto = ("FRACASO: ninguna partición sobreviviente separa el horizonte; la reparación del "
                     "vocabulario queda como método de desarrollo, que es lo que el paper afirma hoy")
    print("\n" + "=" * 96)
    print(f"  VEREDICTO P36 · {veredicto}")
    if mejor_global:
        s, at, th, ev = mejor_global
        print(f"  lo más cerca que llegó alguna partición al azar: {at} > {th:.3g} → "
              f"{ev['tp']}/6 tp · {ev['fp']} fp")
    print("=" * 96)

    SALIDA.write_text(json.dumps({
        "prediccion": "P36", "fecha_corrida": "2026-09-03", "filas": len(filas),
        "features_crudos": attrs, "horizonte": sorted(horizonte),
        "referencia_sensor_humano": {"tp": len(positivos & horizonte), "fp": len(positivos - horizonte)},
        "particion_canonica": canon,
        "al_azar": {"n": PARTICIONES_AL_AZAR, "sobrevivientes": dict(sobrevivientes),
                    "exactas": dict(exactas),
                    "mejor": None if not mejor_global else
                    {"attribute": mejor_global[1], "threshold": mejor_global[2], **mejor_global[3]}},
        "veredicto": veredicto,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  guardado en {SALIDA}")


if __name__ == "__main__":
    main()
