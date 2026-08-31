"""¿La rama HyDE cambia lo que se VE? — `H-4`, y antes de gastar el grid entero.

POR QUE ESTE ANALISIS EXISTE, Y POR QUE VA PRIMERO. `hyde_only` esta implementado y nunca
corrio. Correrlo end-to-end significa re-correr los doce paradigmas —HyDE cambia la
recuperacion, la recuperacion cambia el prompt, y el cache es por contenido, asi que la
corrida entera sale a precio pleno: 121,4M tokens y ~7 h—. Y esa corrida contestaria la
pregunta equivocada primero.

HyDE es una hipotesis sobre **que unidades salen a la superficie**, no sobre que hace el
paradigma con lo que vio. Si el ranking no cambia, no hay nada aguas abajo que encontrar y
los 121M se gastan para medir cero. Asi que la pregunta se hace donde vive: sobre el
ranking, con **una generacion por pregunta y cero paradigmas**.

LAS TRES RAMAS, y la del medio es la que se compara:

  · `hybrid`      — lexico + denso por RRF. Lo que corrio toda la campana. Determinista
  · `hybrid_hyde` — lo anterior FUSIONADO con el vector de la hipotetica. La hipotetica
                    tiene que VENCER al ranking base para mover algo
  · `hyde_only`   — solo el vector de la hipotetica. Sin red debajo: si el modelo imagina
                    mal, no hay nada que lo corrija. Es el instrumento de diagnostico que
                    aisla si la rama tiene senal PROPIA

LO QUE ESTE ANALISIS NO PUEDE DECIR, y se declara arriba y no al pie:

  1. **La consulta acá es la PREGUNTA, y en la campana la emite el paradigma.** Un `react`
     busca sub-preguntas cortas; un `rewoo` emite su plan entero. HyDE puede ayudar mas
     —o menos— sobre esas consultas que sobre la pregunta completa. Esto acota el efecto
     sobre UNA consulta representativa, no sobre la distribucion real
  2. **Recall no es utilidad.** Una unidad que sube al top-5 y que el paradigma igual no
     iba a leer no compra nada. Por eso el resultado de acá es un GATE, no un veredicto:
     habilita la corrida end-to-end o la cancela
  3. **HyDE no es determinista.** La generacion es una llamada al modelo, asi que hay un
     piso de ruido propio. Se corre con la misma huella de la campana (t=0 + seed) y se
     repite `--repeticiones` veces para verlo en vez de suponerlo

LA COMPARACION ES PAREADA POR TAREA. Restar dos promedios de recall no dice si la
diferencia sobrevive a la variacion entre tareas — y con estas, que van de 5 a 60 unidades
de alcance, esa variacion es lo mas grande del tablero. Se reporta la distribucion de la
diferencia POR TAREA, su signo, y un bootstrap sobre tareas.
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import argparse
import json
import os
import random
import statistics
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

from app.config import Settings
from app.embeddings import EmbeddingClient
from app.llm import LLMClient
from app.retrieval import CorpusView, build_arms

# LAS PROFUNDIDADES SON LAS QUE EL BANCO USA, y esto no es un detalle de presentacion.
# `search` tiene limite por omision **8** (`tools.py:1345`) y los paradigmas que lo fijan
# piden **5** y **3** (`modern.py:675,754`). Medir R@10 y R@20 —lo canonico en un paper de
# recuperacion— contesta sobre una profundidad que ninguna corrida ejercita: una unidad
# que sube al puesto 12 no la ve nadie. `20` se conserva SOLO como cota: dice si la rama
# encuentra la unidad en algun lado, aunque no la ponga donde se lee.
KS = (3, 5, 8, 20)
K_OPERATIVO = 8
RAMAS = ("hybrid", "hybrid_hyde", "hyde_only")


def ancho_de(task_id: str) -> str:
    for w in ("w48", "w16", "w4"):
        if task_id.endswith(w):
            return w
    return "base"


def recall_en(orden: list[str], relevantes: set[str], k: int) -> float:
    """Cuantas de las portadoras entraron en el top-k, sobre el total de portadoras.

    Recall y no precision: la pregunta de HyDE es si ENCUENTRA lo que hace falta. Una
    unidad de mas en el top-20 cuesta tokens; una de menos hace la respuesta imposible, y
    esas dos no son el mismo error.
    """
    if not relevantes:
        return float("nan")
    return len(set(orden[:k]) & relevantes) / len(relevantes)


def bootstrap_ic(deltas: list[float], n: int = 4000, semilla: int = 7) -> tuple[float, float]:
    """IC del 95% de la media, remuestreando TAREAS.

    La unidad de remuestreo es la tarea y no la fila porque la tarea es la unidad
    independiente: dos repeticiones de la misma pregunta comparten su dificultad.
    """
    if len(deltas) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(semilla)
    medias = []
    for _ in range(n):
        muestra = [deltas[rng.randrange(len(deltas))] for _ in deltas]
        medias.append(statistics.mean(muestra))
    medias.sort()
    return (medias[int(0.025 * n)], medias[int(0.975 * n)])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="corpus/gold_h1")
    ap.add_argument("--modelo", default="luna")
    ap.add_argument("--repeticiones", type=int, default=1,
                    help="HyDE genera texto: repetir mide SU piso de ruido, no el del banco")
    ap.add_argument("--limite", type=int, default=0, help="0 = todas las tareas")
    args = ap.parse_args()

    base = Path(args.corpus)
    documents = json.loads((base / "documents.json").read_text(encoding="utf-8"))
    tasks = json.loads((base / "tasks.json").read_text(encoding="utf-8"))
    if isinstance(tasks, dict):
        tasks = list(tasks.values())

    vistas = []
    for t in tasks:
        view = CorpusView(
            task_id=t["task_id"],
            documents=documents,
            unit_ids=t["unit_ids"],
            relevant_units=t.get("relevant_units", []),
        )
        # SIN PORTADORAS DECLARADAS NO HAY RECALL QUE MEDIR, y se dice cuantas quedaron
        # afuera: una tarea sin gold de recuperacion no es una tarea facil, es una tarea
        # que este instrumento no puede leer.
        if view.relevant:
            vistas.append((view, t["question"]))
    afuera = len(tasks) - len(vistas)
    con_gold = len(vistas)
    if args.limite:
        vistas = vistas[:args.limite]

    print(f"{args.corpus}: {con_gold} tareas con unidades portadoras declaradas"
          + (f"  ({afuera} sin gold de recuperacion, fuera de este analisis)" if afuera else "")
          + (f"  [ACOTADO a {len(vistas)} por --limite]" if args.limite else ""))
    if not vistas:
        raise SystemExit("ninguna tarea declara `relevant_units`: no hay recall que medir")
    print(f"  portadoras por tarea: mediana "
          f"{statistics.median(len(v.relevant) for v, _ in vistas):.0f}"
          f"  ·  alcance: mediana {statistics.median(len(v.unit_ids) for v, _ in vistas):.0f} unidades")

    # LA HUELLA ES LA DE LA CAMPANA. Medir HyDE con otro modelo mediria otra rama: la
    # generacion es el brazo, no un detalle de implementacion.
    from bench.runs._run_homogenea import MODELOS
    modelo = MODELOS[args.modelo]
    s0 = Settings.from_env()
    settings = replace(
        s0,
        endpoint=os.environ[modelo["endpoint"]].rstrip("/"),
        api_key=os.environ[modelo["key"]],
        chat_deployment=modelo["deployment"],
        reasoning_effort=modelo["esfuerzo"],
    )
    print(f"  huella: {settings.fingerprint()}\n")

    embedder = EmbeddingClient(settings, settings.embedding_deployment)

    # `hybrid` es DETERMINISTA: se calcula una vez y se reusa en cada repeticion. Volver a
    # calcularlo por repeticion no cambiaria el numero y solo pondria ruido en el reloj.
    fijos = build_arms(embedder=embedder)
    orden_base = {v.task_id: fijos["hybrid"].rank(v, q, max(KS)) for v, q in vistas}

    # por rama -> por k -> {task_id: [recall de cada repeticion]}
    recalls: dict[str, dict[int, dict[str, list[float]]]] = {
        r: {k: defaultdict(list) for k in KS} for r in RAMAS
    }
    for v, _ in vistas:
        for k in KS:
            recalls["hybrid"][k][v.task_id].append(
                recall_en(orden_base[v.task_id], v.relevant, k))

    generaciones = 0
    gasto = 0
    for rep in range(args.repeticiones):
        # UNA SEED POR REPETICION, y por una razon que ya me costo una medicion vacia. El
        # cache de instancia de `HydeFused` no es el unico: el de DISCO es por contenido y
        # su clave incluye la HUELLA. Con la misma seed las tres repeticiones comparten
        # clave, devuelven la misma hipotetica y el desvio da 0,000 —que se lee como «HyDE
        # es estable» y dice «HyDE no se volvio a llamar»—. Variar la seed cambia la huella,
        # cambia la clave, y recien ahi la repeticion es una repeticion.
        s_rep = replace(settings, seed=settings.seed + rep)
        client = LLMClient(s_rep)
        brazos = build_arms(embedder=embedder, client=client)
        if args.repeticiones > 1:
            print(f"  [rep {rep + 1}/{args.repeticiones}] seed={s_rep.seed}", flush=True)
        for rama in ("hybrid_hyde", "hyde_only"):
            brazo = brazos[rama]
            for i, (v, q) in enumerate(vistas, 1):
                orden = brazo.rank(v, q, max(KS))
                for k in KS:
                    recalls[rama][k][v.task_id].append(recall_en(orden, v.relevant, k))
                if i % 20 == 0:
                    print(f"  [rep {rep + 1}/{args.repeticiones}] {rama}: {i}/{len(vistas)}",
                          flush=True)
            generaciones += getattr(brazo, "generations", 0)
        uso = getattr(client, "spent", None)
        gasto += getattr(uso, "total_tokens", 0) if uso else 0

    print(f"\n  {generaciones} generaciones HyDE  ·  {gasto:,} tokens gastados"
          f"  (el grid entero: 121.400.000)")

    print("\n" + "=" * 78)
    print("1. RECALL POR RAMA — promedio sobre tareas")
    print("=" * 78 + "\n")
    print(f"  {'rama':<16}" + "".join(f"{'R@' + str(k):>10}" for k in KS))
    medias: dict[str, dict[int, float]] = {}
    for rama in RAMAS:
        medias[rama] = {}
        fila = f"  {rama:<16}"
        for k in KS:
            por_tarea = [statistics.mean(vs) for vs in recalls[rama][k].values()]
            medias[rama][k] = statistics.mean(por_tarea)
            fila += f"{medias[rama][k]:>10.3f}"
        print(fila)

    print("\n" + "=" * 78)
    print("2. LA COMPARACION PAREADA — la unica que decide")
    print("=" * 78)
    print("""
  Restar dos promedios no dice si la diferencia sobrevive a la variacion ENTRE tareas,
  y acá esa variacion es lo mas grande del tablero: el alcance va de 5 a 60 unidades.
  Lo que decide es la distribucion de la diferencia POR TAREA.
""")
    veredicto: dict[str, bool] = {}
    for rama in ("hybrid_hyde", "hyde_only"):
        print(f"  ── {rama} vs hybrid " + "─" * (58 - len(rama)))
        for k in KS:
            deltas = []
            for tid in recalls["hybrid"][k]:
                d = (statistics.mean(recalls[rama][k][tid])
                     - statistics.mean(recalls["hybrid"][k][tid]))
                deltas.append(d)
            mejor = sum(1 for d in deltas if d > 1e-9)
            peor = sum(1 for d in deltas if d < -1e-9)
            lo, hi = bootstrap_ic(deltas)
            cruza = lo <= 0 <= hi
            m = statistics.mean(deltas)
            if not cruza:
                veredicto[f"{rama}@{k}"] = "mejora" if m > 0 else "empeora"
            print(f"    R@{k:<3} delta medio {statistics.mean(deltas):+.3f}"
                  f"   IC95 [{lo:+.3f}, {hi:+.3f}]"
                  f"   mejora {mejor:3} · empata {len(deltas) - mejor - peor:3} · empeora {peor:3}"
                  + ("" if cruza else "  *"))
        print()

    print("=" * 78)
    print("3. DONDE, SI EN ALGUN LADO — por ancho de alcance")
    print("=" * 78)
    print("""
  Si HyDE sirve, tiene que servir mas donde hay mas para descartar. Un efecto que
  aparece con 5 unidades y desaparece con 60 va al reves de su premisa.
""")
    k = K_OPERATIVO
    print(f"  {'ancho':<8}{'n':>5}{'hybrid':>10}{'+hyde':>10}{'hyde solo':>12}")
    for w in ("base", "w4", "w16", "w48"):
        tids = [v.task_id for v, _ in vistas if ancho_de(v.task_id) == w]
        if not tids:
            continue
        fila = f"  {w:<8}{len(tids):>5}"
        for rama in RAMAS:
            m = statistics.mean(statistics.mean(recalls[rama][k][t]) for t in tids)
            fila += f"{m:>10.3f}" if rama != "hyde_only" else f"{m:>12.3f}"
        print(fila)

    if args.repeticiones > 1:
        print("\n" + "=" * 78)
        print("4. EL PISO DE RUIDO PROPIO DE HYDE")
        print("=" * 78)
        print("""
  La generacion es una llamada al modelo. Si la misma pregunta da recalls distintos entre
  repeticiones, ese desvio es el piso contra el que hay que leer el delta de arriba — y
  un delta menor que el ruido de su propio instrumento no es un efecto.
""")
        for rama in ("hybrid_hyde", "hyde_only"):
            desvios = [statistics.pstdev(vs) for vs in recalls[rama][K_OPERATIVO].values() if len(vs) > 1]
            print(f"  {rama:<16} desvio medio entre repeticiones (R@{K_OPERATIVO}): "
                  f"{statistics.mean(desvios):.3f}")
        if gasto == 0 and args.repeticiones <= 1:
            # EL CACHE HACE QUE LA REPETICION NO SEA UNA REPETICION, y hay que decirlo o el
            # cero de arriba se lee como «HyDE es estable» cuando dice «HyDE no se volvio a
            # llamar». La clave del cache es por CONTENIDO y la huella incluye la seed: dos
            # repeticiones con la misma seed comparten clave y devuelven la MISMA
            # hipotetica. Evite el cache de instancia y no vi el de disco, que es el que
            # importa. Para medir la varianza de verdad hay que variar la seed.
            print()
            print("  [!] NO ES UNA MEDICION. Se gastaron 0 tokens: las "
                  f"{args.repeticiones} repeticiones salieron del cache de disco, que es")
            print("      por contenido, asi que devolvieron la MISMA hipotetica. Ese 0,000 dice")
            print("      «no se volvio a llamar al modelo», no «HyDE es estable». La varianza")
            print("      real de la rama exige variar la SEED, que entra a la huella.")

    print("\n" + "=" * 78)
    gana = [k for k, v in veredicto.items() if v == "mejora"]
    pierde = [k for k, v in veredicto.items() if v == "empeora"]
    if pierde and not gana:
        # NO ES LO MISMO «no hace nada» QUE «hace dano», y el veredicto los separa: el
        # primero cancela la corrida por falta de senal, el segundo la cancela POR TENERLA.
        print(f">>> NO habilita la corrida end-to-end, y no por falta de efecto: "
              f"{', '.join(pierde)}")
        print("    EMPEORAN el recall con IC95 que no cruza cero. Y justo en la profundidad")
        print(f"    que el banco ejercita —`search` pide 8 por omision y los paradigmas fijan")
        print("    5 y 3—, no en la que un paper de recuperacion reportaria. Donde HyDE")
        print("    insinua algo (R@20) no lo mira nadie.")
    elif gana:
        print(f">>> HABILITA la corrida end-to-end: {', '.join(gana)} mejoran con IC95 que")
        print("    no cruza cero. Hay mas material a la vista, y recien ahi tiene sentido")
        print("    preguntar si algun paradigma lo aprovecha.")
    else:
        print(">>> NO habilita la corrida end-to-end. Ninguna rama HyDE mueve el recall con")
        print("    un IC95 que no cruce cero, sobre ninguna profundidad. Si no cambia lo que")
        print("    se VE, no hay nada que los paradigmas puedan hacer distinto, y los 121M")
        print("    tokens del grid medirian cero a precio pleno.")
    print("=" * 78)


if __name__ == "__main__":
    main()
