"""EDA: ¿por qué gana `react`, y las señales discriminan FAMILIAS aunque no individuos?

DOS PREGUNTAS QUE SON LA MISMA VISTA DESDE DOS LADOS.

  1. **`react` es el mas simple y el mejor.** Un resultado asi, en un banco que existe para
     medir estructuras de control mas elaboradas, o es una propiedad del corpus o es una
     propiedad de las estructuras. Hay que decir cual, y con un mecanismo, no con una
     narrativa.

  2. **`_predictores.py` cerro que ninguna senal separa a los tres punteros.** Pero esa es
     una prueba sobre INDIVIDUOS. Que `react` y `dag_strategy` sean indistinguibles no dice
     nada sobre si las senales separan **grupos** de brazos — y un ruteador que elige
     FAMILIA y despues toma el mas barato de la familia es un ruteador distinto, con un
     premio distinto, que esa prueba nunca evaluo.

EL METODO, y es el que se usa cuando el resultado agregado no explica nada: **descomponer el
desenlace en un embudo**. La utilidad de una celda es el producto de dos cosas que se pueden
medir por separado y que fallan por razones distintas:

    u  ≈  P(VIO las unidades portadoras)  ×  P(contesto bien | las vio)

El primer factor es RECUPERACION Y NAVEGACION: ¿el brazo llego al material? El segundo es
SINTESIS: ¿hizo algo con el? Dos brazos con la misma utilidad pueden estar fallando en
etapas opuestas, y el promedio los muestra iguales. Separarlos es lo unico que convierte
«react es mejor» en «react es mejor PORQUE».

LO QUE ESTE ANALISIS NO PUEDE DECIR. `relevant_units_read` cuenta unidades portadoras
LEIDAS, no comprendidas, y un brazo que lee la unidad y la ignora figura como que la vio. Es
la cota superior de la etapa 1, no su medida exacta.
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

from app.runner import load_rows
from bench.panel import rectangulo

REGISTRO = Path("results/luna/gold_h1_rows.jsonl")
CORPUS = Path("corpus/gold_h1")
CONTAMINADAS: set[str] = set()

# LAS FAMILIAS, y se declaran DESDE EL CODIGO, no desde el resultado. Agrupar brazos por
# como les fue seria dibujar el cluster alrededor de la respuesta; agruparlos por su
# estructura de control es una hipotesis que el dato puede refutar.
#
# El eje es ADAPTATIVIDAD: cuando el brazo decide su proxima llamada.
#
#   · `adaptativo`  — decide despues de ver lo que volvio. Puede corregir el rumbo
#   · `plan_fijo`   — decide todo antes de ejecutar. No puede corregir
#   · `canal_con_perdida` — hay una representacion intermedia mas chica que el material:
#                     un resumen, una ventana recortada, un indice de entidades. Lo que se
#                     pierde ahi no se recupera aguas abajo
FAMILIA = {
    "react": "adaptativo",
    "reflection": "adaptativo",
    "direct": "adaptativo",
    "rewoo": "plan_fijo",
    "dag_strategy": "plan_fijo",
    "extract_compute": "plan_fijo",
    "streaming_scan": "plan_fijo",
    "gist_reader": "canal_con_perdida",
    "pointer_chase": "canal_con_perdida",
    "graph_traverse": "canal_con_perdida",
    "handoff": "canal_con_perdida",
    "supervisor": "canal_con_perdida",
}


def cargar():
    filas = [f for f in load_rows(REGISTRO) if not f.get("infeasible")]
    tasks = json.loads((CORPUS / "tasks.json").read_text(encoding="utf-8"))
    if isinstance(tasks, dict):
        tasks = list(tasks.values())
    gold = {t["task_id"]: set(t.get("relevant_units", [])) & set(t["unit_ids"])
            for t in tasks}
    señal = {t["task_id"]: t for t in tasks}
    panel = rectangulo(
        [{"task_id": f["task_id"], "paradigm": f["paradigm"], "infeasible": False}
         for f in filas], excluir=CONTAMINADAS)
    return filas, gold, señal, panel


def media(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else float("nan")


def bootstrap(deltas, n=4000, semilla=7):
    if len(deltas) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(semilla)
    ms = sorted(statistics.mean([deltas[rng.randrange(len(deltas))] for _ in deltas])
                for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n)]


def main() -> None:
    filas, gold, meta, panel = cargar()
    tset, bset = set(panel.tareas), set(panel.brazos)
    dentro = [f for f in filas if f["task_id"] in tset and f["paradigm"] in bset]
    print(f"panel: {panel.descripcion()}")
    print(f"  {len(dentro)} filas factibles dentro del rectangulo\n")

    # celda -> lista de filas
    celdas = defaultdict(list)
    for f in dentro:
        celdas[(f["task_id"], f["paradigm"])].append(f)

    # -- el embudo, por celda ----------------------------------------------------
    # `vio` = leyo TODAS las portadoras. Todas y no algunas: una cadena de dos saltos con
    # una sola unidad leida no esta a mitad de camino, esta rota.
    emb = {}
    for (t, p), fs in celdas.items():
        g = gold.get(t) or set()
        vio, u, leidas, iters, calls, frac = [], [], [], [], [], []
        for f in fs:
            tu = f.get("tool_usage") or {}
            r = tu.get("relevant_units_read_any", tu.get("relevant_units_read", 0)) or 0
            vio.append(1.0 if g and r >= len(g) else 0.0)
            u.append(f.get("utility", 0.0))
            leidas.append(tu.get("units_read_any", tu.get("units_read", 0)) or 0)
            iters.append(f.get("iterations", 0) or 0)
            calls.append(f.get("calls", 0) or 0)
            frac.append(tu.get("fraction_read"))
        emb[(t, p)] = {"vio": media(vio), "u": media(u), "leidas": media(leidas),
                       "iters": media(iters), "calls": media(calls),
                       "frac": media(frac), "gold": len(gold.get(t) or set())}

    print("=" * 92)
    print("1. EL EMBUDO — la utilidad se parte en VER y en USAR, y fallan por motivos distintos")
    print("=" * 92)
    print("""
  u  ~  P(vio TODAS las portadoras)  x  P(contesto bien | las vio)

  Dos brazos con la misma utilidad pueden estar fallando en etapas opuestas. El promedio
  los muestra iguales; el embudo no.
""")
    print(f"  {'brazo':<16}{'familia':<20}{'u':>7}{'VIO':>8}{'u|vio':>8}{'u|no vio':>10}"
          f"{'leidas':>9}{'iters':>7}")
    orden = sorted(bset, key=lambda p: -media([emb[k]["u"] for k in emb if k[1] == p]))
    tabla = {}
    for p in orden:
        ks = [k for k in emb if k[1] == p]
        vio_si = [emb[k]["u"] for k in ks if emb[k]["vio"] >= 0.999]
        vio_no = [emb[k]["u"] for k in ks if emb[k]["vio"] < 0.999]
        fila = {
            "u": media([emb[k]["u"] for k in ks]),
            "vio": media([emb[k]["vio"] for k in ks]),
            "u_vio": media(vio_si), "u_novio": media(vio_no),
            "leidas": media([emb[k]["leidas"] for k in ks]),
            "iters": media([emb[k]["iters"] for k in ks]),
            "n_vio": len(vio_si), "n": len(ks),
        }
        tabla[p] = fila
        uv = f"{fila['u_vio']:>8.3f}" if fila["n_vio"] else f"{'—':>8}"
        un = f"{fila['u_novio']:>10.3f}" if fila["n"] - fila["n_vio"] else f"{'—':>10}"
        print(f"  {p:<16}{FAMILIA.get(p, '?'):<20}{fila['u']:>7.3f}{fila['vio']:>8.0%}"
              f"{uv}{un}{fila['leidas']:>9.1f}{fila['iters']:>7.1f}")

    print("""
  COMO SE LEE. `VIO` es la etapa 1: cuantas celdas leyeron TODAS las unidades portadoras.
  `u|vio` es la etapa 2: que hizo con ellas cuando las tuvo. Un brazo con `VIO` bajo y
  `u|vio` alto no es peor razonando — es peor BUSCANDO, y eso se arregla en otro lado.
""")

    # -- por que gana react ------------------------------------------------------
    print("=" * 92)
    print("2. `react` CONTRA CADA UNO, PAREADO POR TAREA — en que etapa se saca la ventaja")
    print("=" * 92)
    print("""
  Restar promedios no dice de donde sale la diferencia. Pareado por tarea y partido en las
  dos etapas, si.
""")
    print(f"  {'vs':<16}{'delta u':>10}{'IC95':>20}{'delta VIO':>12}{'delta u|vio':>13}")
    for p in orden:
        if p == "react":
            continue
        comunes = [t for t in panel.tareas
                   if (t, "react") in emb and (t, p) in emb]
        du = [emb[(t, "react")]["u"] - emb[(t, p)]["u"] for t in comunes]
        dv = [emb[(t, "react")]["vio"] - emb[(t, p)]["vio"] for t in comunes]
        # etapa 2 SOLO donde los dos vieron todo: comparar sintesis sobre material
        # distinto compara otra cosa.
        ambos = [t for t in comunes
                 if emb[(t, "react")]["vio"] >= 0.999 and emb[(t, p)]["vio"] >= 0.999]
        d2 = [emb[(t, "react")]["u"] - emb[(t, p)]["u"] for t in ambos]
        lo, hi = bootstrap(du)
        s2 = f"{statistics.mean(d2):>+13.3f}" if len(d2) >= 5 else f"{'(n<5)':>13}"
        print(f"  {p:<16}{statistics.mean(du):>+10.3f}"
              f"{f'[{lo:+.3f}, {hi:+.3f}]':>20}{statistics.mean(dv):>+12.0%}{s2}")

    # -- la hipotesis de las familias --------------------------------------------
    print()
    print("=" * 92)
    print("3. LA HIPOTESIS DE LOS CLUSTERS — ¿las senales separan FAMILIAS aunque no individuos?")
    print("=" * 92)
    print("""
  `_predictores.py` probo si alguna senal separa a los tres punteros ENTRE SI y no encontro
  ninguna. Esa es una prueba sobre INDIVIDUOS. La pregunta de aca es otra: ¿separan GRUPOS?

  Si la respuesta fuera si, el ruteador cambia de forma — elige familia por la senal, y
  despues toma el MAS BARATO de la familia. Es una decision mas gruesa y mas barata de
  aprender, y su premio se mide igual: contra el mejor fijo, fuera de muestra.
""")
    fam_de = {p: FAMILIA[p] for p in bset if p in FAMILIA}
    familias = sorted(set(fam_de.values()))
    print(f"  {'familia':<22}{'brazos':<44}{'u media':>9}")
    for fa in familias:
        ps = sorted(p for p in bset if fam_de.get(p) == fa)
        us = [emb[k]["u"] for k in emb if fam_de.get(k[1]) == fa]
        print(f"  {fa:<22}{', '.join(ps):<44}{media(us):>9.3f}")

    # u por (tarea, familia) = el MEJOR de la familia en esa tarea. Es lo que el ruteador
    # de familias conseguiria si dentro de la familia eligiera bien; la cota superior.
    print("""
  ¿Que familia gana en cada tarea? Y sobre todo: ¿es SIEMPRE LA MISMA? Si lo es, no hay
  nada que rutear — hay una familia mejor y se usa siempre.
""")
    # EL VALOR DE UNA FAMILIA NO ES SU MAXIMO, y esto lo tuve mal y dio un numero absurdo:
    # `plan_fijo` figuraba como la mejor familia fija con 0,879 cuando sus dos brazos
    # promedian 0,822 y 0,677. El maximo dentro de la familia le regala a la familia una
    # eleccion por tarea que el ruteador de familias NO puede hacer —si pudiera elegir el
    # brazo, no seria un ruteador de familias— y ademas premia a la familia mas numerosa
    # por puro sesgo del maximo: `canal_con_perdida` tiene cuatro brazos y las otras dos.
    #
    # El valor correcto es el del REPRESENTANTE: el brazo de mejor media de la familia,
    # elegido UNA vez sobre todo el panel y no por tarea. Eso es lo que un ruteador que
    # elige familia puede ejecutar de verdad.
    medias_brazo = {p: media([emb[k]["u"] for k in emb if k[1] == p]) for p in bset}
    repre = {}
    for fa in familias:
        ps = [p for p in bset if fam_de.get(p) == fa]
        repre[fa] = max(ps, key=lambda p: medias_brazo[p])
    print("  representante de cada familia (mejor media, elegido UNA vez sobre el panel):")
    for fa in familias:
        print(f"    {fa:<22}-> {repre[fa]} ({medias_brazo[repre[fa]]:.3f})")

    gana_fam = defaultdict(int)
    mejor_por_tarea = {}
    for t in panel.tareas:
        por_fam = {}
        for fa in familias:
            k = (t, repre[fa])
            if k in emb:
                por_fam[fa] = emb[k]["u"]
        if len(por_fam) == len(familias):
            mejor = max(por_fam, key=por_fam.get)
            gana_fam[mejor] += 1
            mejor_por_tarea[t] = (mejor, por_fam)
    n = len(mejor_por_tarea)
    for fa in familias:
        print(f"  {fa:<22}gana en {gana_fam[fa]:>3} de {n} tareas  ({gana_fam[fa] / n:>4.0%})")

    # EL PREMIO DE RUTEAR FAMILIAS, con la misma vara que el de rutear brazos.
    if n:
        oraculo_fam = statistics.mean(max(pf.values()) for _, pf in mejor_por_tarea.values())
        fijas = {}
        for fa in familias:
            fijas[fa] = statistics.mean(pf[fa] for _, pf in mejor_por_tarea.values())
        mejor_fija = max(fijas, key=fijas.get)
        print(f"\n  oraculo DE FAMILIAS (la mejor familia por tarea)   {oraculo_fam:.3f}")
        print(f"  mejor familia FIJA (`{mejor_fija}`)"
              + " " * max(1, 26 - len(mejor_fija)) + f"{fijas[mejor_fija]:.3f}")
        print(f"  premio maximo de rutear FAMILIAS                   {oraculo_fam - fijas[mejor_fija]:+.3f}")
        # y el mismo numero para brazos, para que se vean al lado
        oraculo_brazo = statistics.mean(
            max(emb[(t, p)]["u"] for p in bset if (t, p) in emb) for t in mejor_por_tarea)
        fijos_brazo = {p: statistics.mean(emb[(t, p)]["u"] for t in mejor_por_tarea
                                          if (t, p) in emb) for p in bset}
        mb = max(fijos_brazo, key=fijos_brazo.get)
        print(f"  (para comparar, rutear BRAZOS: {oraculo_brazo:.3f} contra "
              f"{fijos_brazo[mb]:.3f} de `{mb}` = {oraculo_brazo - fijos_brazo[mb]:+.3f})")

    # -- ¿que senal predice la familia ganadora? ---------------------------------
    print()
    print("=" * 92)
    print("4. ¿QUE SENAL PREDICE LA FAMILIA GANADORA? — informacion mutua contra su nulo")
    print("=" * 92)
    print("""
  Una senal sirve si saber su valor reduce la incertidumbre sobre que familia gana. Eso es
  informacion mutua. Y como con 59 tareas cualquier particion fina parece informativa por
  azar, cada senal se compara contra SU nulo por permutacion — la misma senal, las
  etiquetas de familia barajadas.
""")

    def senales_de(t):
        m = meta[t]
        tid = t
        ancho = ("w48" if tid.endswith("w48") else "w16" if tid.endswith("w16")
                 else "w4" if tid.endswith("w4") else "base")
        n_units = len(m.get("unit_ids") or [])
        return {
            "celda (cota superior)": m.get("cell", "?"),
            "cardinalidad": str(m.get("answer_cardinality")),
            "ancho del alcance": ancho,
            "portadoras (1 / varias)": "1" if len(gold.get(t) or ()) <= 1 else "varias",
            "material grande (>20 u.)": "si" if n_units > 20 else "no",
            "acoplamiento": ("alto" if (m.get("truth_coupling") or 0) >= 0.5 else "bajo"),
        }

    def imutua(pares):
        n_ = len(pares)
        if not n_:
            return 0.0
        px, py, pxy = defaultdict(int), defaultdict(int), defaultdict(int)
        for x, y in pares:
            px[x] += 1; py[y] += 1; pxy[(x, y)] += 1
        return sum((c / n_) * math.log2((c / n_) / ((px[x] / n_) * (py[y] / n_)))
                   for (x, y), c in pxy.items())

    nombres = list(senales_de(next(iter(mejor_por_tarea))).keys())
    ys = [mejor_por_tarea[t][0] for t in mejor_por_tarea]
    rng = random.Random(11)
    filas_sig = []
    nulos_max = []
    por_senal_nulos = {}
    for nom in nombres:
        xs = [senales_de(t)[nom] for t in mejor_por_tarea]
        obs = imutua(list(zip(xs, ys)))
        nulos = []
        for _ in range(2000):
            b = ys[:]
            rng.shuffle(b)
            nulos.append(imutua(list(zip(xs, b))))
        por_senal_nulos[nom] = nulos
        nulos.sort()
        p = sum(1 for v in nulos if v >= obs) / len(nulos)
        filas_sig.append((nom, obs, statistics.mean(nulos), nulos[int(0.95 * len(nulos))], p,
                          len(set(xs))))
    filas_sig.sort(key=lambda r: -(r[1] - r[2]))
    print(f"  {'senal':<28}{'niv':>5}{'IM':>8}{'nulo':>8}{'nulo p95':>10}{'p':>8}")
    for nom, obs, nm, n95, p, niv in filas_sig:
        print(f"  {nom:<28}{niv:>5}{obs:>8.3f}{nm:>8.3f}{n95:>10.3f}{p:>8.3f}"
              + ("  *" if p < 0.05 else ""))

    # CORRECCION POR SELECCION, la misma que en `_predictores.py`: se probaron k senales y
    # se mira la mejor, asi que la vara es el MAXIMO de los k nulos en cada permutacion.
    candidatas = [f for f in filas_sig if not f[0].startswith("celda")]
    if candidatas:
        k = len(candidatas)
        maxes = []
        for i in range(2000):
            maxes.append(max(por_senal_nulos[f[0]][i] for f in candidatas))
        maxes.sort()
        mejor = candidatas[0]
        pc = sum(1 for v in maxes if v >= mejor[1]) / len(maxes)
        print(f"\n  -- CORRECCION POR SELECCION -------------------------------------------")
        print(f"  Se probaron {k} senales y se elige la mejor: `{mejor[0]}` con IM {mejor[1]:.3f}.")
        print(f"  Vara correcta = maximo de los {k} nulos por permutacion: "
              f"media {statistics.mean(maxes):.3f} · p95 {maxes[int(0.95 * len(maxes))]:.3f}")
        print(f"  p corregido = {pc:.3f}   "
              + (">>> SOBREVIVE" if pc < 0.05 else ">>> NO sobrevive"))

    # -- el eje que estaba medido y nadie miro ----------------------------------
    print()
    print("=" * 92)
    print("5. LA LATENCIA — medida en el 100% de las filas, y nunca usada para decidir")
    print("=" * 92)
    print("""
  DOS RELOJES, y confundirlos es el error que casi cometo. `wall_seconds` NO sirve: el
  63-67% de las filas de `react` y `dag_strategy` estan por debajo de medio segundo porque
  son replays del cache de disco. Ese campo mide cuanto tarda el banco en releer, no
  cuanto tarda el sistema en contestar.

  `first_ttft_ms` y `ttft_ms_total` SI sirven, y vienen del proveedor —`latency_checkpoint`
  del objeto `usage`, presente en el 100% de las filas— asi que el cache los conserva: son
  la latencia de la llamada que efectivamente se hizo el dia que se hizo.

    · `first_ttft_ms`   cuanto tarda en aparecer el PRIMER token de la primera llamada.
                        Es lo que el usuario percibe como «arranco»
    · `ttft_ms_total`   la suma sobre todas las llamadas. Es la latencia SERIAL
                        IRREDUCIBLE: la parte que no se acelera con mas tokens por segundo,
                        porque cada llamada tiene que esperar a que termine la anterior

  Y esa segunda es la que discrimina: es el numero de turnos EN SERIE, que es exactamente
  la ley de costo `turn-driven` — pero cobrada en tiempo del usuario en vez de en tokens.
""")
    lat = {}
    for p_ in orden:
        pri = [f.get("first_ttft_ms") for f in dentro
               if f["paradigm"] == p_ and f.get("first_ttft_ms")]
        ser = [f.get("ttft_ms_total") for f in dentro
               if f["paradigm"] == p_ and f.get("ttft_ms_total")]
        if not ser:
            continue
        lat[p_] = {"pri": statistics.median(pri) if pri else 0.0,
                   "ser": statistics.median(ser) / 1000.0,
                   "p90": sorted(ser)[int(0.9 * len(ser))] / 1000.0}
    print(f"  {'brazo':<16}{'u':>7}{'1er token':>12}{'serie mediana':>16}{'serie p90':>12}"
          f"{'u por segundo':>16}")
    for p_ in orden:
        if p_ not in lat:
            continue
        L = lat[p_]
        print(f"  {p_:<16}{tabla[p_]['u']:>7.3f}{L['pri']:>10.0f}ms{L['ser']:>15.2f}s"
              f"{L['p90']:>11.2f}s{tabla[p_]['u'] / max(L['ser'], 1e-9):>16.2f}")

    if "react" in lat:
        print("""
  LO QUE ESTO AGREGA. El primer token es practicamente el MISMO en todos —250-410 ms, es
  una llamada al mismo modelo—. Lo que cambia entre brazos es la latencia SERIAL, y ahi el
  rango es de 3,6x. Ese eje no aparece en ninguna decision del ruteador de hoy, que decide
  sobre utilidad y, en la variante por costo, sobre tokens.""")
        r = lat["react"]
        mejores = sorted((p_ for p_ in lat if tabla[p_]["u"] >= tabla["react"]["u"] - 0.05),
                         key=lambda x: lat[x]["ser"])
        if mejores and mejores[0] != "react":
            m = mejores[0]
            print(f"""
  Y hay un candidato: `{m}` esta dentro de 0,05 de utilidad de `react`
  ({tabla[m]['u']:.3f} contra {tabla['react']['u']:.3f}) con {r['ser'] / lat[m]['ser']:.1f}x menos latencia serial
  ({lat[m]['ser']:.2f}s contra {r['ser']:.2f}s). Ese es el mismo desempate que la politica de
  costo, sobre un eje distinto — y sobre el eje que el usuario siente.""")
        else:
            # EL EJE NUEVO NO DESTRABA NADA, y eso tambien es un resultado. Si `react`
            # fuera el mejor en utilidad y hubiera OTRO igual de bueno y mas rapido, la
            # latencia abriria una decision que la utilidad no abria. No es el caso.
            mas_rapido = min(lat, key=lambda x: lat[x]["ser"])
            print(f"""
  Y NO DESTRABA NADA, que es lo que hay que decir. `react` es a la vez el de mayor utilidad
  Y el de menor latencia serial entre los contendientes: {r['ser']:.2f}s contra {lat['dag_strategy']['ser']:.2f}s de
  `dag_strategy`, el unico que le queda a menos de 0,05. No hay un brazo igual de bueno y
  mas rapido al que mandar la decision.

  El unico que compra tiempo es `{mas_rapido}` — {lat[mas_rapido]['ser']:.2f}s, {r['ser'] / lat[mas_rapido]['ser']:.1f}x mas rapido — y cuesta
  {tabla['react']['u'] - tabla[mas_rapido]['u']:.3f} de utilidad, muy por encima del ruido. Es un intercambio explicito, no un
  almuerzo gratis: solo lo compra quien tenga un techo de latencia declarado.""")

    print()
    print("=" * 92)
    print("6. EL VEREDICTO")
    print("=" * 92)
    print(f"""
  POR QUE GANA `react`, y no es por buscar mejor. Su tasa de VER es {tabla['react']['vio']:.0%}, ni la mejor
  ni cerca: `gist_reader` ve el {tabla['gist_reader']['vio']:.0%} de las portadoras y termina en {tabla['gist_reader']['u']:.3f}. Toda la
  ventaja esta en la etapa 2 — con el material a la vista `react` da {tabla['react']['u_vio']:.3f} y
  `gist_reader` {tabla['gist_reader']['u_vio']:.3f}, PEOR que cuando no lo vio todo. Y ese es el mecanismo:

      cada representacion intermedia mas chica que el material es una perdida que no se
      recupera aguas abajo. Un gist de 180 caracteres, una ventana recortada para el
      sub-agente, un indice de entidades: los tres tiran informacion antes de saber cual
      hacia falta.

  `react` no tiene ninguna. Lee menos que casi todos ({tabla['react']['leidas']:.1f} unidades) y no comprime nada
  de lo que lee. La simplicidad no es una virtud estetica aca: es la AUSENCIA de un canal
  con perdida, y eso es medible y es lo que se mide.

  LA HIPOTESIS DE LOS CLUSTERS: probada y REFUTADA en este corpus, y por una razon que vale
  mas que el veredicto. No falla porque las senales sean debiles — falla porque **no hay
  frontera que cruzar**: `adaptativo` gana en el 84% de las tareas. El premio de rutear
  familias es +0,079 contra un piso de ruido de +0,065, y ninguna senal predice que familia
  gana (`cardinalidad`, la mejor, no sobrevive la correccion por seleccion: p=0,365).

  Un cluster que gana casi siempre no es un cluster que rutear: es un default.
""")


if __name__ == "__main__":
    main()
