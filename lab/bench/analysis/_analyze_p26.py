"""P26: HyDE como rama fusionada. Veredicto sobre las cuatro predicciones registradas.

P26d ES LA QUE IMPORTA, y no por el resultado sino por lo que pone en juego. Toda
comparacion de paradigmas de este banco corrio bajo UN brazo de recuperacion. Si el ORDEN
de los paradigmas cambia al cambiar el brazo, esas comparaciones son condicionales a una
constante que nadie vario — y no es que queden matizadas: quedan sin sostener.

Se predijo que NO cambia, o sea que los resultados existentes sobreviven. Es la prediccion
que mas dolia perder, y por eso se registro antes de correr.

LA COMPARACION ES PAREADA POR CELDA. Promediar cada brazo por separado mezclaria
composicion con efecto. Y el costo se compara con la RECUPERACION COBRADA: `hybrid_hyde`
genera una hipotetica por consulta distinta, y ese gasto no aparece en la contabilidad del
paradigma —el paradigma nunca lo vio— asi que sin cobrarlo se compara una recuperacion
gratis contra una paga.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.runner import load_rows
from app.metrics import arm_dose
from bench._sanity import bounded

CORPUS = "gold_p18"
# Las celdas donde el enunciado y el documento se dicen distinto: es donde HyDE tiene un
# puente que cruzar. C1 es el control — una unidad, un hecho, la redaccion ya cerca.
CELDAS_CON_BRECHA = ("C2", "C4")
CELDA_CONTROL = "C1"


# EL DENOMINADOR DEL RECALL VIVE EN EL CORPUS, NO EN LA FILA. La tarea declara
# `relevant_units`, y `tools.py` cuenta contra `view.relevant`, que es esa lista
# INTERSECADA con `unit_ids`. Reproducir la interseccion es obligatorio: una tarea que
# declara una unidad relevante fuera de su alcance daria recall < 1 para un brazo que leyo
# todo lo que habia. Y `truth_n_units` no sirve como denominador aunque exista — cuenta
# unidades de la tarea, no unidades PORTADORAS.
def _relevantes_por_tarea() -> dict[str, int]:
    tareas = json.loads(Path(f"corpus/{CORPUS}/tasks.json").read_text(encoding="utf-8"))
    if isinstance(tareas, dict):
        tareas = list(tareas.values())
    return {
        t["task_id"]: len(set(t.get("relevant_units") or []) & set(t.get("unit_ids") or []))
        for t in tareas
    }


RELEVANTES = _relevantes_por_tarea()


def _dosis(usos: list[dict | None]) -> float | None:
    """Dosis media del brazo sobre las replicas. `None` si ninguna busco."""
    vals = [d for d in (arm_dose(u) for u in usos) if d is not None]
    return statistics.mean(vals) if vals else None


def celdas(nombre: str) -> dict[tuple[str, str], dict]:
    f = Path(f"results/nano/{nombre}")
    if not f.exists():
        return {}
    por = defaultdict(list)
    for r in load_rows(f):
        if not r.get("error"):
            por[(r["task_id"], r["paradigm"])].append(r)
    return {
        k: {
            "u": sum(x["utility"] for x in v) / len(v),
            "cost": sum(x["cost_tokens"] for x in v) / len(v),
            "recuperacion": sum(x.get("retrieval_tokens", 0) for x in v) / len(v),
            "cell": v[0].get("cell", ""),
            "recall": _recall(v, RELEVANTES.get(k[0], 0)),
            "leidas": sum((x.get("tool_usage") or {}).get("units_read", 0) for x in v) / len(v),
            "dosis": _dosis([x.get("tool_usage") for x in v]),
            "replicas": [x["utility"] for x in v],
        }
        for k, v in por.items()
    }


def _recall(filas: list[dict], relevantes: int) -> float | None:
    """Fraccion de unidades PORTADORAS que el brazo efectivamente leyo.

    `None` cuando el registro no lo trae: promediarlo como cero diria que no leyo
    ninguna, que es una afirmacion y no una ausencia.
    """
    if not relevantes:
        return None
    vals = []
    for r in filas:
        u = r.get("tool_usage") or {}
        # LA CLAVE DEL DENOMINADOR NO ESTA EN LA FILA. Estaba escrito `r["truth_n_units"]`
        # —que la TAREA si declara y la fila no— asi que devolvia SIEMPRE `None` y el
        # analizador imprimia «recall NO registrado» sobre un registro que si lo tiene.
        # Un ausente inventado por una clave mal buscada se lee igual que un ausente real,
        # y es el mismo defecto que este comentario advertia un nivel mas arriba.
        leidas = u.get("relevant_units_read")
        if leidas is None:
            continue
        vals.append(min(1.0, leidas / relevantes))
    return statistics.mean(vals) if vals else None


def main() -> None:
    base = celdas(f"{CORPUS}_rows.jsonl")
    hyde = celdas(f"{CORPUS}_hybrid_hyde_rows.jsonl")
    if not base or not hyde:
        print("Falta alguno de los dos brazos — SIN N. Se dice, no se supone.")
        return
    comunes = sorted(set(base) & set(hyde))
    if len(comunes) < 4:
        print(f"{len(comunes)} celdas pareadas — SIN N.")
        return

    print(f"{len(comunes)} celdas pareadas · {CORPUS}\n")

    # --- P26d: ¿cambia el ORDEN de los paradigmas?
    def orden(d):
        por_par = defaultdict(list)
        for (t, p) in comunes:
            por_par[p].append(d[(t, p)]["u"])
        medias = {p: statistics.mean(v) for p, v in por_par.items()}
        return [p for p, _ in sorted(medias.items(), key=lambda kv: -kv[1])], medias

    o_base, m_base = orden(base)
    o_hyde, m_hyde = orden(hyde)
    print("  utilidad media por paradigma:")
    for p in sorted(set(o_base) | set(o_hyde)):
        print(f"    {p:<14} hybrid {m_base.get(p, 0):.4f}   hyde {m_hyde.get(p, 0):.4f}   "
              f"delta {m_hyde.get(p, 0) - m_base.get(p, 0):+.4f}")
    print(f"\n  orden con hybrid : {o_base}")
    print(f"  orden con hyde   : {o_hyde}")
    if o_base == o_hyde:
        print("  P26d CONFIRMADA: el orden NO cambia.")
    else:
        print("  P26d REFUTADA al pie de la letra: el orden CAMBIA.")

    # UN ORDEN QUE CAMBIA NO SIGNIFICA LO MISMO SEGUN CUANTO SEPARE A LOS QUE SE DIERON
    # VUELTA, y sin esto la prediccion la decide el ruido. Se mide la separacion de cada
    # par que se invirtio, en errores estandar sobre la diferencia PAREADA por tarea.
    #
    # La prediccion original —«el orden no cambia»— era demasiado fragil: sobre un
    # conjunto que contiene brazos empatados, es una prediccion que decide una moneda.
    # Enunciar un orden sin decir a que resolucion es orden fue el defecto del registro,
    # y se corrige diciendolo, no reinterpretando el resultado despues.
    print()
    invertidos = [
        (a, b) for i, a in enumerate(o_base) for b in o_base[i + 1:]
        if o_hyde.index(a) > o_hyde.index(b)
    ]
    if not invertidos:
        print("  ningun par se invirtio.")
    for a, b in invertidos:
        for etiqueta, d in (("hybrid", base), ("hyde", hyde)):
            por_tarea = defaultdict(dict)
            for (t, par) in comunes:
                por_tarea[t][par] = d[(t, par)]["u"]
            dif = [v[a] - v[b] for v in por_tarea.values() if a in v and b in v]
            if len(dif) < 2:
                continue
            m, sd = statistics.mean(dif), statistics.pstdev(dif)
            ee = sd / len(dif) ** 0.5 if sd else 0.0
            sig = abs(m) / ee if ee else float("inf")
            print(f"    {a} - {b} bajo {etiqueta:<7} {m:+.4f}  "
                  f"({sig:.2f} errores estandar, n={len(dif)})")
    if invertidos:
        print("  Un par que se da vuelta separado por menos de un error estandar no es un")
        print("  cambio de orden: es un empate que cayo para el otro lado. Lo que se")
        print("  sostiene o no es lo que este numero diga, no la comparacion de listas.")

    # --- EL PISO DE RUIDO, ANTES DE CUALQUIER DELTA. Un `+0,04` sobre un piso de `0,05`
    # no es un efecto chico: es nada. Se mide ENTRE replicas del mismo punto, que es la
    # unica dispersion que no puede deberse al brazo.
    print()
    for etiqueta, d in (("hybrid", base), ("hyde", hyde)):
        sds = [statistics.pstdev(v["replicas"]) for v in d.values() if len(v["replicas"]) > 1]
        if sds:
            print(f"  piso de ruido intra-celda {etiqueta:<7} media {statistics.mean(sds):.4f}"
                  f"   max {max(sds):.4f}")
    print("  Con t=0 y seed fijo esto deberia ser cero. No lo es, asi que es el piso")
    print("  contra el que se lee todo lo que sigue.")

    # --- QUE PARADIGMAS PUEDEN MOVERSE. Uno que no consulta al retriever es invariante al
    # brazo POR CONSTRUCCION —`gist_reader` enumera `surface.unit_ids()` y resume todo, sin
    # `search` (`app/paradigms/modern.py`)— y sus filas salen identicas al token. Eso lo
    # vuelve DOS controles a la vez: del mecanismo, y de la INSTRUMENTACION. Si los dos
    # archivos se cobraran con reglas distintas, el mismo trabajo daria costos distintos y
    # aca se veria. Se detecta del registro, no de una lista escrita a mano.
    print()
    pares = sorted({p for _, p in comunes})
    invariantes = []
    for par in pares:
        sel = [k for k in comunes if k[1] == par]
        if all(abs(hyde[k]["u"] - base[k]["u"]) < 1e-12
               and abs(hyde[k]["cost"] - base[k]["cost"]) < 1e-9 for k in sel):
            invariantes.append(par)
    if invariantes:
        print(f"  invariantes al brazo, identicos al token: {invariantes}")
        print("  -> controlan el mecanismo Y verifican que el cobro es el mismo en los dos")
        print("     archivos. Su delta cero no es evidencia sobre HyDE.")
    moviles = [p for p in pares if p not in invariantes]
    print(f"  moviles (consultan al retriever): {moviles}")
    # LA DOSIS EXPLICA LA TABLA DE ABAJO. El brazo sustituye `hybrid`, o sea la tool
    # `search`; `keyword_search` y `semantic_search` son constantes entre brazos. Un
    # paradigma que busca mayormente por keyword recibe una fraccion del tratamiento, y
    # promediar el efecto entre paradigmas lo pondera por una dosis que nadie declaro.
    print()
    print("  dosis de brazo (fraccion de busquedas por `search`):")
    for par in pares:
        sel = [k for k in comunes if k[1] == par]
        ds = [hyde[k]["dosis"] for k in sel if hyde[k]["dosis"] is not None]
        etiqueta = f"{statistics.mean(ds):6.1%}" if ds else "  N/A  (no busca nunca)"
        print(f"    {par:<14} {etiqueta}")
    print("    N/A no es 0%: no recibio tratamiento, no lo recibio y no respondio.")

    # --- P26a / P26b: la ganancia donde hay brecha, contra el control. POR PARADIGMA,
    # porque promediar a traves de un invariante diluye el efecto con ceros estructurales.
    print()
    print(f"  {'par':<13} {'celdas':<7} {'n':>3} {'delta u':>9} {'ee':>7} {'sigma':>6}"
          f" {'d costo':>9} {'d leidas':>9} {'d recall':>9}")
    for par in moviles + invariantes:
        for nom, sel_celdas in ((f"brecha {'/'.join(CELDAS_CON_BRECHA)}", CELDAS_CON_BRECHA),
                                (f"control {CELDA_CONTROL}", (CELDA_CONTROL,)),
                                ("todas", None)):
            sel = [k for k in comunes if k[1] == par
                   and (sel_celdas is None or base[k]["cell"][:2] in sel_celdas)]
            if not sel:
                continue
            du = [hyde[k]["u"] - base[k]["u"] for k in sel]
            m, sd = statistics.mean(du), statistics.pstdev(du)
            ee = sd / len(du) ** 0.5 if sd else 0.0
            sig = f"{abs(m) / ee:.2f}" if ee else ("0.00" if abs(m) < 1e-12 else "inf")
            dc = statistics.mean(hyde[k]["cost"] - base[k]["cost"] for k in sel)
            dl = statistics.mean(hyde[k]["leidas"] - base[k]["leidas"] for k in sel)
            rec = [(hyde[k]["recall"], base[k]["recall"]) for k in sel
                   if hyde[k]["recall"] is not None and base[k]["recall"] is not None]
            dr = f"{statistics.mean(h - b for h, b in rec):+9.4f}" if rec else "  SIN N"
            print(f"  {par:<13} {nom:<7} {len(sel):>3} {m:>+9.4f} {ee:>7.4f} {sig:>6}"
                  f" {dc:>+9.0f} {dl:>+9.2f} {dr}")
        print()
    print("  P26a se enuncio sobre el RECALL de unidades portadoras (>=5pp en C2/C4) y")
    print("  P26b sobre la ausencia de ganancia en el control. Se leen de esta tabla, y")
    print("  la columna que decide P26a es `d recall`, NO `delta u`: una utilidad que sube")
    print("  con el recall quieto o en baja gana por un mecanismo que no es el predicho.")

    # --- P26c: neto de su propio costo, A LAMBDA>0, que es como se enuncio. Un delta de
    # utilidad al lado de un delta de costo no es un veredicto neto: hay que combinarlos.
    print()
    gen = statistics.mean(hyde[k]["recuperacion"] for k in comunes)
    bounded(gen, 0.0, None, "generacion de HyDE")
    print(f"  generacion de HyDE cobrada: {gen:,.0f} tokens/celda")
    if gen <= 0:
        print("  Y ESO ES UN PROBLEMA: si la generacion cobra cero, o no se ejecuto o no")
        print("  se esta cobrando — las dos cosas invalidan la comparacion de costo.")
    # `cost_tokens` YA trae la recuperacion cobrada por el medidor de celda (H-3). Sumarle
    # `retrieval_tokens` encima la cobraria dos veces, y la guarda lo comprueba en vez de
    # confiar en el comentario.
    for k in comunes:
        bounded(hyde[k]["cost"] - hyde[k]["recuperacion"], 0.0, None,
                "costo menos recuperacion (doble cobro?)")
    print()
    print(f"  {'lambda':>9}  " + "  ".join(f"{p:>13}" for p in moviles))
    for lam in (0.0, 1e-5, 5e-5, 1e-4, 5e-4, 1e-3):
        fila = []
        for par in moviles:
            sel = [k for k in comunes if k[1] == par]
            d = [(hyde[k]["u"] - lam * hyde[k]["cost"])
                 - (base[k]["u"] - lam * base[k]["cost"]) for k in sel]
            fila.append(f"{statistics.mean(d):>+13.4f}")
        print(f"  {lam:>9.5f}  " + "  ".join(fila))
    print()
    print("  costo medio por celda, para leer la escala de lambda:")
    for par in moviles:
        sel = [k for k in comunes if k[1] == par]
        print(f"    {par:<13} hybrid {statistics.mean(base[k]['cost'] for k in sel):>9,.0f}"
              f"   hyde {statistics.mean(hyde[k]['cost'] for k in sel):>9,.0f}"
              f"   generacion {statistics.mean(hyde[k]['recuperacion'] for k in sel):>7,.0f}")
    print()
    print("  P26c predijo que HyDE NO gana neto para los brazos BARATOS: una generacion por")
    print("  consulta es un impuesto fijo que una celda chica no amortiza. El veredicto es")
    print("  el lambda donde su columna cruza a negativo, contra su costo por celda.")


if __name__ == "__main__":
    main()
