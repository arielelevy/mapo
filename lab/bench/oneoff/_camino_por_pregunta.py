"""EL CAMINO PERFECTO **POR PREGUNTA** — razonado a mano sobre las 78. Cero llamadas.

QUE LO SEPARA DE `_camino_perfecto.py`, que razonaba por CELDA. Una celda no es una
pregunta: `c2-000-w4` tiene 1 unidad relevante y `c2-001-w4` tiene **0** —nadie es
signatario en esas cinco unidades— así que la misma celda contiene una pregunta de
enumeración y una de ausencia disfrazada, con modos de falla opuestos. Razonar por celda
promedia las dos y no ve ninguna.

LO PRIMERO QUE HAY QUE MEDIR ES EL GIST, y eso dio vuelta la mitad del camino anterior.
`SUMMARY_CHARS = 180`, y un gist real de este corpus es:

    Subject: engagement review, Delta Sur SA … [32218 chars]

Un asunto y una pista de largo. **No lleva el rol, ni la cuenta, ni la ciudad, ni el
nombre.** Medido sobre `c2-000-w16`: `'director'` aparece en **8 de 20 textos y en 0 de 20
gists**. Sobre `c1-000`: el número de cuenta que es la respuesta **no está** en el gist de
la única unidad.

    El camino anterior decía «el rol es exactamente lo que un resumen conserva» y
    «una alerta de compliance es justo lo que un resumen conserva». Las dos son
    falsas contra el material, y las dos sostenían picks de `gist_reader`.

Y no es sólo que el gist no responda: **tampoco discrimina**. Los 60 gists de `w48` son
asuntos casi idénticos, así que no le dan al modelo ninguna base para elegir qué leer.
`gist_reader` en este corpus es «elegir a ciegas, después leer».

LA SEGUNDA COTA, ARITMETICA: **la cobertura exhaustiva no se puede pagar.** `w16` son
160.982 tokens contra un presupuesto de 60.000; `w48` son 482.961. Trece de las celdas
declaran `coverage_demanded=exhaustive` y en `w16`/`w48` **ningún brazo puede verlas todas**.
Donde la pregunta exige cobertura y el presupuesto la prohíbe, lo que gane, gana por otra
cosa — y eso hay que decirlo antes de leer el resultado, no después.

DE ESAS DOS COTAS SALE EL CAMINO, y sale concentrado: 57 de 78 preguntas son **una búsqueda
literal y una lectura alrededor**. El término existe verbatim en el texto —un rol
(`director`), un número de cuenta (`AR7142464820`), una ciudad (`Rosario`)— así que el plan
completo se puede escribir antes de ver un solo resultado. Ésa es la precondición exacta de
`rewoo`, que hace **dos** llamadas contra las hasta 20 de `react`.

    Y esto llega al mismo lugar que el análisis de costo ya había llegado por otro
    camino: el premio de este corpus es de COSTO, no de calidad.

LA CONTAMINACION, DECLARADA. Ya vi: la utilidad media por brazo, las 5 tareas con un único
mejor brazo, la correlación cobertura-utilidad por celda, y el máximo de llamadas por brazo.
Las cinco tareas contaminadas se puntúan aparte.

LA ADVERTENCIA QUE MANDA SOBRE EL PUNTAJE. **57 de los 78 picks son `rewoo`, y el registro
de `rewoo` se hizo con la lectura ROTA** (`RW-1`): llamaba a `read` en 130 de 138 celdas y
leía CERO unidades, contestando desde snippets. Así que puntuar este camino contra el
registro mide un `rewoo` que no podía hacer lo que el camino le pide. **El puntaje es una
cota inferior**, y `M-6` —re-correrlo— es exactamente lo que lo resuelve.

Corre DESDE `lab/`:  py bench/oneoff/_camino_por_pregunta.py
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
from app.paradigms import campaign_roster
from app.runner import load_rows

CONTAMINADAS = {"b2-000-w4", "b2-001-w16", "b2-002-w16", "c3-000-h1", "c2-001-w4"}


# ─────────────────────────────────────────────────────────────────────────────
# EL RAZONAMIENTO, POR FAMILIA DE PREGUNTA — y los hechos POR PREGUNTA que lo modulan.
#
# Cada entrada dice el MECANISMO que la pregunta pide, no el nombre del patrón. El patrón
# sale del mecanismo; si el mecanismo está bien y el patrón pierde, el que falla es el
# catálogo y eso es lo que hay que encontrar.
# ─────────────────────────────────────────────────────────────────────────────

MECANISMO: dict[str, tuple[str, str]] = {

    "C1_single_verifiable": ("rewoo",
        "UNA unidad y un identificador verbatim. No hay nada que buscar, nada que "
        "encadenar, nada que cubrir: el único costo real es poner el texto delante del "
        "modelo una vez. `rewoo` son dos llamadas y ninguna topología puede hacer menos. "
        "Y el gist NO sirve acá — medido, el número de cuenta que es la respuesta no está "
        "en el resumen de la unidad, así que `gist_reader` tiene que leer igual y paga la "
        "llamada de triage de más."),

    "C2_bulk_independent": ("rewoo",
        "enumerar quién tiene un ROL. El rol aparece **literal** en el texto, así que un "
        "`keyword_search` del rol devuelve exactamente las unidades que lo contienen: el "
        "plan entero se escribe antes de ver un resultado. La alternativa —cobertura "
        "exhaustiva— no se puede pagar en `w16`/`w48`, y el gist no conserva el rol (0 de "
        "20). Así que la búsqueda literal no es una aproximación: es lo único que hay."),

    "C4_aggregate_full_coverage": ("rewoo",
        "contar personas de una CIUDAD. Mismo argumento que C2 y un riesgo más: hay que "
        "deduplicar a quien aparece en dos unidades, y eso exige ver los hallazgos JUNTOS. "
        "La llamada de solve de `rewoo` los ve juntos; una partición los dedup­lica sólo en "
        "la costura, que es donde una variante de superficie hace contar dos veces a la "
        "misma persona."),

    "C8_currency": ("rewoo",
        "el registro MAS RECIENTE de una cuenta. Es el caso más limpio del catálogo: el "
        "número de cuenta es un identificador literal, un `keyword_search` trae los pocos "
        "registros que lo mencionan, y la comparación de fechas se hace con todos delante. "
        "Cero adaptación: el plan no depende de lo que devuelva la búsqueda."),

    "C9_declared_roster": ("rewoo",
        "**la lista de personas VIENE EN LA PREGUNTA.** Los pasos son enumerables antes de "
        "empezar e independientes entre sí — la precondición exacta de planificar sin "
        "observar, donde no adaptarse deja de ser una limitación. Y es la familia donde "
        "`semantic_search` (agregada por RW-2) tiene que aparecer: K-6 midió que **36,5% de "
        "las menciones son invisibles a un keyword del nombre completo**, así que un plan "
        "que sólo busca la forma canónica pierde una de cada tres."),

    "B2_absence": ("rewoo",
        "las NUEVE tienen 0 unidades relevantes: la respuesta correcta es siempre «ninguno» "
        "y el modo de falla es inventar un nombre. Un `keyword_search` del rol sobre el "
        "alcance completo que vuelve vacío **sí** es evidencia de ausencia acá, porque el "
        "índice léxico cubre todas las unidades y el término es exacto.\n"
        "         Y el argumento estructural que decide: `react` puede buscar hasta 20 "
        "veces un rol que no existe —46,5% de sus búsquedas son estériles, con rachas de "
        "14— y cada vuelta es otra oportunidad de convencerse. **El brazo que no puede "
        "seguir buscando es el brazo que no puede hablarse a sí mismo hasta un nombre.**"),

    "D1_presupposition": ("rewoo",
        "la presuposición es FALSA: no hubo transferencia, y lo correcto es rechazar la "
        "premisa en vez de reportar una fecha. Mismo argumento que B2 y más fuerte, porque "
        "acá hay fechas por todos lados: buscar más aumenta la probabilidad de encontrar "
        "algo con forma de respuesta. Dos llamadas fijas acotan ese riesgo por "
        "construcción."),

    "C5_unknown_horizon": ("direct|react",
        "**una contradicción es una relación entre DOS unidades**: ninguna unidad la "
        "contiene, así que no hay término que buscar. Es la única familia que de verdad "
        "exige ver todo junto.\n"
        "         En `w4` son 32.281 tokens contra 60.000 de presupuesto: `direct` entra y "
        "ve las cinco unidades verbatim — la comparación es directa y no depende de que "
        "ningún resumen conserve la ciudad.\n"
        "         En `w16`/`w48` **ningún brazo puede verlas todas** (128.989 y 386.762 "
        "tokens). Lo mejor disponible es un bucle que compare de a pares, y `react` es el "
        "único con bucle reactivo real. Pero hay que decirlo: acá el camino perfecto **no "
        "existe** dentro del presupuesto, y lo que gane, gana por suerte."),

    "C3_coupled_chain": ("react",
        "**el paso dos no se puede FORMULAR sin el resultado del uno**: no se sabe la "
        "cuenta de quién buscar hasta haber resuelto la línea de reporte. Es la única "
        "familia con dependencia secuencial genuina, y la única donde `rewoo` está "
        "estructuralmente descalificado — no se puede escribir la consulta de un nombre que "
        "todavía no se conoce. `react` es el único brazo del plantel cuyo bucle encadena de "
        "verdad."),

    "C7_irreversible": ("react",
        "booleano sobre una condición de escalamiento, y **la pregunta no dice cuál es el "
        "disparador**: no hay término que planificar. Hay que leer una unidad para aprender "
        "el vocabulario del dominio y recién ahí buscar bien — que es exactamente lo que "
        "compra adaptarse.\n"
        "         Y las dos polaridades piden estrategias OPUESTAS con el mismo texto de "
        "pregunta: `pos` tiene un testigo único y se gana encontrándolo; `neg` tiene cero y "
        "exige probar que ninguna de las 9 unidades dispara —64.407 tokens contra un "
        "presupuesto de 20.000, o sea **imposible**—. Ninguna señal disponible al decidir "
        "distingue una de otra."),

    "W1_shared_writes": ("react",
        "misma forma que C7 —booleano sobre un conflicto de escritura pendiente, 9 unidades, "
        "presupuesto 20.000 contra 64.457 de material— y el mismo disparador no declarado. "
        "Se decide igual, y por las mismas razones."),
}


def ancho(task_id: str) -> str:
    for w in ("w4", "w16", "w48"):
        if task_id.endswith(w):
            return w
    return "base"


def elegir(tarea: dict) -> tuple[str, str]:
    """El pick de ESTA pregunta: el mecanismo de la familia, modulado por sus propios hechos."""
    celda = tarea["cell"]
    patron, razon = MECANISMO[celda]
    tid = tarea["task_id"]
    w = ancho(tid)
    rel = len(tarea["relevant_units"])

    if celda == "C5_unknown_horizon":
        patron = "direct" if w == "w4" else "react"

    # LOS HECHOS DE LA PREGUNTA, no de la celda. Es lo que separa esto del camino por celda.
    notas: list[str] = []
    if celda in ("C2_bulk_independent", "C4_aggregate_full_coverage") and rel == 0:
        notas.append(
            f"**esta pregunta tiene 0 unidades relevantes**: es una AUSENCIA disfrazada de "
            f"enumeración, y su modo de falla se da vuelta — no es omitir a alguien, es "
            f"inventarlo. El pick no cambia y la razón sí")
    if celda == "C3_coupled_chain":
        saltos = tid[-1]
        notas.append(
            f"**{saltos} salto(s)**: cada salto es una dependencia más que un plan fijo no "
            f"puede escribir, así que la ventaja de encadenar crece monótona con este número")
    if celda in ("C7_irreversible", "W1_shared_writes"):
        notas.append(
            "**polaridad `pos`** (hay testigo: se gana encontrándolo)" if rel
            else "**polaridad `neg`** (0 testigos: habría que probar ausencia sobre 64k "
                 "tokens con 20k de presupuesto — no se puede)")
    if tarea["coverage_demanded"] == "exhaustive" and w in ("w16", "w48"):
        notas.append(
            "la pregunta declara cobertura **exhaustiva** y el presupuesto la **prohíbe** "
            "(material > presupuesto): ningún brazo puede cumplirla, así que el pick es el "
            "mejor disponible y no el correcto")
    return patron, razon + ("\n         · " + "\n         · ".join(notas) if notas else "")


def main() -> None:
    docs = json.loads(_Path("corpus/gold_h1/documents.json").read_text(encoding="utf-8"))
    tareas = json.loads(_Path("corpus/gold_h1/tasks.json").read_text(encoding="utf-8"))
    roster = list(campaign_roster())

    filas = [f for f in load_rows(_Path("results/luna/gold_h1_rows.jsonl"))
             if not f.get("infeasible")]
    util = collections.defaultdict(list)
    cost = collections.defaultdict(list)
    for f in filas:
        util[(f["task_id"], f["paradigm"])].append(f["utility"])
        cost[(f["task_id"], f["paradigm"])].append(f.get("cost_tokens") or 0)

    def med(d, tid, p):
        v = d.get((tid, p))
        return sum(v) / len(v) if v else None

    print("=" * 100)
    print("EL CAMINO PERFECTO, PREGUNTA POR PREGUNTA")
    print("=" * 100)

    filas_res = []
    for t in tareas:
        tid = t["task_id"]
        pick, razon = elegir(t)
        fact = [p for p in roster if feasibility.check(p, docs, t).feasible]
        if pick not in fact:
            pick_efectivo, nota_fact = None, f"PODADO por factibilidad ({pick})"
        else:
            pick_efectivo, nota_fact = pick, ""

        u_pick = med(util, tid, pick_efectivo) if pick_efectivo else None
        candidatos = [(med(util, tid, p), med(cost, tid, p), p) for p in fact
                      if med(util, tid, p) is not None]
        if not candidatos:
            continue
        u_max = max(c[0] for c in candidatos)
        # «maxima utilidad y entre las que empatan, minimo costo»
        mejores = sorted([c for c in candidatos if c[0] >= u_max - 1e-9],
                         key=lambda c: c[1] or 0)
        mejor = mejores[0]
        filas_res.append({
            "tid": tid, "celda": t["cell"], "ancho": ancho(tid), "pick": pick,
            "razon": razon, "nota_fact": nota_fact,
            "u_pick": u_pick, "c_pick": med(cost, tid, pick_efectivo) if pick_efectivo else None,
            "u_mejor": mejor[0], "c_mejor": mejor[1], "mejor": mejor[2],
            "empatan": sum(1 for c in candidatos if c[0] >= u_max - 1e-9),
            "contaminada": tid in CONTAMINADAS,
        })

    # ── el detalle, agrupado por familia para que se lea el razonamiento una vez ──
    for celda in dict.fromkeys(f["celda"] for f in filas_res):
        grupo = [f for f in filas_res if f["celda"] == celda]
        print(f"\n{'─' * 100}")
        print(f"{celda}  ·  {len(grupo)} preguntas  ·  pick: {grupo[0]['pick']}")
        print(f"{'─' * 100}")
        print("  " + grupo[0]["razon"])
        print()
        for f in grupo:
            u = f"{f['u_pick']:.2f}" if f["u_pick"] is not None else "  — "
            marca = ("=" if f["u_pick"] is not None and f["u_pick"] >= f["u_mejor"] - 1e-9
                     else "<")
            cont = " (contaminada)" if f["contaminada"] else ""
            print(f"    {f['tid']:16s} u={u} {marca} mejor={f['u_mejor']:.2f} "
                  f"[{f['mejor']}] · empatan {f['empatan']} · "
                  f"costo {f['c_pick'] or 0:>8,.0f} vs {f['c_mejor'] or 0:>8,.0f}{cont}")
            if f["nota_fact"]:
                print(f"      !! {f['nota_fact']}")

    # ── el puntaje ───────────────────────────────────────────────────────────
    limpias = [f for f in filas_res if not f["contaminada"]]
    print(f"\n{'=' * 100}")
    print("PUNTAJE")
    print("=" * 100)

    # LAS DEGENERADAS SE SEPARAN, y es la corrección que más baja el puntaje. En 9 de las
    # 41 preguntas limpias **el máximo del catálogo entero es 0,00**: todo brazo factible
    # falla. Empatar con una falla universal cuenta como «acertó el mejor» y no es
    # habilidad — es que no había nada que acertar.
    degeneradas = [f for f in limpias if f["u_mejor"] <= 1e-9]
    decidibles = [f for f in limpias if f["u_mejor"] > 1e-9]

    for etiqueta, conjunto in (("todas", filas_res),
                               ("sin contaminadas", limpias),
                               ("sin contaminadas Y sin degeneradas", decidibles)):
        con = [f for f in conjunto if f["u_pick"] is not None]
        aciertos = sum(1 for f in con if f["u_pick"] >= f["u_mejor"] - 1e-9)
        u_cam = sum(f["u_pick"] for f in con) / len(con)
        u_mej = sum(f["u_mejor"] for f in con) / len(con)
        c_cam = sum(f["c_pick"] or 0 for f in con) / len(con)
        c_mej = sum(f["c_mejor"] or 0 for f in con) / len(con)
        print(f"\n  {etiqueta} ({len(con)} preguntas con medicion)")
        print(f"    alcanza el maximo en     {aciertos}/{len(con)}  ({aciertos/len(con):.0%})")
        print(f"    utilidad camino / mejor  {u_cam:.3f} / {u_mej:.3f}   brecha {u_mej-u_cam:+.3f}")
        print(f"    costo    camino / mejor  {c_cam:,.0f} / {c_mej:,.0f}")

    print(f"""
  LAS DEGENERADAS: {len(degeneradas)} de las {len(limpias)} limpias tienen maximo 0,00 — el
  catalogo ENTERO falla. Son las {sum(1 for f in degeneradas if f["celda"].startswith("C9"))}
  de `C9_declared_roster` y las {sum(1 for f in degeneradas if f["celda"].startswith("D1"))}
  de `D1_presupposition`. Empatar ahi no mide nada, y por eso el tercer renglon es el que
  vale.""")

    # ── donde esta la brecha, que es lo que se buscaba ───────────────────────
    print(f"\n{'=' * 100}")
    print("DONDE ESTA LA BRECHA")
    print("=" * 100)
    por_celda = collections.defaultdict(list)
    for f in limpias:
        if f["u_pick"] is None:
            continue
        por_celda[f["celda"]].append(f["u_mejor"] - f["u_pick"])
    print(f"\n  {'celda':28s} {'n':>3s} {'brecha media':>13s}   pick")
    for celda, gaps in sorted(por_celda.items(), key=lambda x: -sum(x[1]) / len(x[1])):
        pick = next(f["pick"] for f in limpias if f["celda"] == celda)
        print(f"  {celda:28s} {len(gaps):3d} {sum(gaps)/len(gaps):13.3f}   {pick}")

    # ── contra el mejor fijo, que es el patron de comparacion del banco ──────
    fijos = collections.defaultdict(list)
    for f in filas_res:
        for p in roster:
            u = med(util, f["tid"], p)
            if u is not None:
                fijos[p].append(u)
    print(f"\n  el mejor paradigma FIJO, para comparar:")
    for p, v in sorted(fijos.items(), key=lambda x: -sum(x[1]) / len(x[1]))[:5]:
        print(f"    {p:16s} u={sum(v)/len(v):.3f}  sobre {len(v)} tareas")

    print(f"\n{'=' * 100}")
    print("EL DIAGNOSTICO DE CADA BRECHA — que es para lo que se hizo esto")
    print("=" * 100)
    print("""
  1. C1, brecha 1,000 — LA MAXIMA POSIBLE, Y NO ES UN ERROR DEL CAMINO.
     `rewoo` saca 0,00 en las tres y `react` saca 1,00. Es exactamente la falla que RW-1
     documento antes de que este archivo existiera: una unidad, un numero de cuenta, y
     `rewoo` contestando desde un snippet que no lo trae porque su `read` no leia. El
     camino pide «leer la unica unidad»; el registro mide un brazo que no podia leer.
     **No hay que cambiar el pick: hay que re-correr el brazo** (M-6).

  2. B2 a w16, brecha 0,667 — Y ACA EL CAMINO APRENDE ALGO.
     Mi argumento era que un `keyword_search` vacio ES evidencia de ausencia. **Verificado
     y cierto**: sobre `b2-000-w16`, `keyword_search('trustee')` devuelve 0 unidades, y
     'director' devuelve 5 como control. El mecanismo existe y es solido.
     Pero medido, el brazo que gana la ausencia es `handoff` (u=0,92) y es **el que mas
     LEE** — 19 lecturas — mientras `rewoo` (u=0,00) uso `search` 19 veces contra 12 de
     `keyword_search`. Y `search` es el ranking fusionado: **nunca vuelve vacio**, asi que
     no puede testimoniar una ausencia.

         El mecanismo correcto esta disponible, es barato, es determinista — y ningun
         brazo del catalogo lo usa, porque quien elige la herramienta es el modelo y el
         modelo prefiere buscar antes que probar que no hay.

     Eso NO es una brecha de topologia: es un hueco del catalogo. Una busqueda lexica
     vacia sobre el alcance completo es un hecho COMPUTED, y contestar «ninguno» desde ahi
     no es un juicio del modelo — es la regla del producto aplicada al pie de la letra.

  3. C3 h2, brecha 0,667 — subestime la VERIFICACION sobre una cadena.
     Elegi `react` porque es el unico que encadena, y es cierto. Gano `reflection`, que es
     `react` mas una critica: en una cadena de dos saltos un error en el salto uno se
     propaga en silencio, y la segunda pasada es lo unico que lo puede agarrar. El
     mecanismo que la pregunta pide no es solo «encadenar», es «encadenar y verificar».

  4. C5 a w16, brecha 0,200 — declarado ANTES de mirar, y confirmado.
     El razonamiento decia que en w16/w48 ningun brazo puede ver las 17-49 unidades bajo
     presupuesto, asi que el camino perfecto no existe y lo que gane, gana por suerte. El
     ganador cambia de pregunta a pregunta (`gist_reader`, `dag_strategy`, `rewoo`), que es
     la firma de ganar por suerte.
""")

    print(f"\n{'=' * 100}")
    print("LA ADVERTENCIA QUE MANDA SOBRE TODO ESTO")
    print("=" * 100)
    n_rewoo = sum(1 for f in filas_res if f["pick"] == "rewoo")
    print(f"""
  {n_rewoo} de los {len(filas_res)} picks son `rewoo`, y el registro de `rewoo` se hizo con
  la lectura ROTA (RW-1): llamaba a `read` en 130 de 138 celdas y leia CERO unidades,
  contestando desde snippets. El camino le pide exactamente lo que no podia hacer —
  buscar un termino literal y LEER alrededor.

  Asi que este puntaje es una COTA INFERIOR del camino, no su valor. M-6 lo resuelve.
""")


if __name__ == "__main__":
    main()
