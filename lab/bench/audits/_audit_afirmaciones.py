"""Re-deriva desde el registro y el codigo cada afirmacion de la tanda del 2026-08-29.

DE DONDE SALE. El autor pregunto «¿podes verificar?» sobre una tanda de afirmaciones que yo
habia hecho en prosa, y verificar encontro dos cosas distintas:

  - una afirmacion **sostenida por un metodo roto**: dije que `framed()` no tenia callers
    despues de buscar `build_prompt` y `_prompt(`, que no son su nombre. La conclusion
    resulto cierta y **la evidencia no la sostenia**. Buscada por su nombre real, `framed`
    aparece UNA vez en todo el repo: su propia definicion.
  - un numero **derivado en la granularidad comoda**: reporte «3,8% de la entrada la sirve
    el cache del proveedor» desde CUATRO celdas de `w16`. Sobre el registro entero es 2,3%,
    y sobre `w48` —el 61% del gasto— no esta medido.

POR QUE QUEDA COMO ARCHIVO. Las dos fallas son de metodo y no de suerte, y ninguna la
atrapa un test: un test prueba que el codigo hace lo que dice, no que lo que YO digo sobre
el codigo sea derivable. Esto se corre despues de una tanda de afirmaciones, y cada linea
falla ruidosamente en vez de imprimir un numero plausible.

LA REGLA QUE APLICA, y es del repo: un numero derivado se verifica en la granularidad donde
vive, no en el agregado — ni en la muestra que resulto comoda.

Corre DESDE `lab/`. No gasta cuota: todo sale del registro y del codigo.
"""

import json
import sys
from pathlib import Path

# Corre DESDE `lab/`: el prologo resuelve los imports al salir de la raiz.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.runner import load_rows

OK, MAL = "  [OK]  ", "  [MAL] "
fallas = []


def afirmo(etiqueta, condicion, detalle=""):
    print((OK if condicion else MAL) + etiqueta + (f"   {detalle}" if detalle else ""))
    if not condicion:
        fallas.append(etiqueta)


print("=" * 78)
print("1. `stable_prefix_first` es INERTE\n")
raiz = Path(".").resolve()
# EL AUDITOR SE CUENTA A SI MISMO, y eso lo hizo fallar la primera vez. Este archivo
# NOMBRA a `framed` en su propio docstring para explicar el hallazgo, asi que un barrido
# ingenuo encuentra dos apariciones y reporta que la afirmacion no se sostiene — sobre
# evidencia que produjo el propio auditor. Se excluye, y se dice por que: un barrido lexico
# sobre prosa cuenta menciones, no usos, y la unica prosa garantizada de este repo que
# menciona el nombre es esta.
YO = Path(__file__).resolve()

apariciones = []
for py in raiz.rglob("*.py"):
    if "__pycache__" in py.parts or py.resolve() == YO:
        continue
    for i, linea in enumerate(py.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if "framed" in linea and "framed the" not in linea:
            apariciones.append(f"{py.relative_to(raiz)}:{i}")
afirmo("`framed` aparece UNA sola vez (su definicion)", len(apariciones) == 1,
       str(apariciones))
lector = [
    f"{py.relative_to(raiz)}"
    for py in raiz.rglob("*.py")
    if "__pycache__" not in py.parts and py.resolve() != YO
    and 'getattr(surface, "stable_prefix_first"' in py.read_text(encoding="utf-8", errors="replace")
]
afirmo("el flag se LEE en un solo archivo", len(lector) == 1, str(lector))

print()
print("=" * 78)
print("2. El prefijo estable contra el umbral del proveedor\n")
from app.paradigms import ANSWER_CONTRACT
from app.tools import specs_for

tools = json.dumps(specs_for("basic", False))
prefijo = (len(tools) + len(ANSWER_CONTRACT)) // 4
afirmo(f"prefijo estable = {prefijo} tokens", 500 < prefijo < 700)
afirmo("NO cruza el umbral de 1.024", prefijo < 1024, f"faltan {1024 - prefijo}")

print()
print("=" * 78)
print("3. El reparto de la plata, sobre TODO el registro de la light\n")
filas = [f for f in load_rows(raiz / "results/light/gold_h1_rows.jsonl")
         if not f.get("infeasible")]
prom = sum(f.get("prompt_tokens", 0) for f in filas)
comp = sum(f.get("completion_tokens", 0) for f in filas)
cach = sum(f.get("provider_cached_tokens", 0) for f in filas)
print(f"   filas: {len(filas)}   entrada: {prom:,}   salida: {comp:,}   cacheada: {cach:,}")
afirmo(f"la entrada es el {prom/(prom+comp):.1%} del gasto", prom / (prom + comp) > 0.95)
afirmo("`provider_cached_tokens` LLEGA a la fila",
       "provider_cached_tokens" in filas[0],
       "el campo existe en el registro")
afirmo(f"y esta poblado (cacheada = {cach:,})", cach > 0)
print(f"   -> del total de entrada, el proveedor sirvio el {cach/prom:.1%}")

print()
print("=" * 78)
print("4. Las palancas de recorte, re-calculadas\n")
from app.feasibility import check
from app.paradigms import campaign_roster

docs = json.loads((raiz / "corpus/gold_h1/documents.json").read_text(encoding="utf-8"))
tasks = json.loads((raiz / "corpus/gold_h1/tasks.json").read_text(encoding="utf-8"))
mat = {t["task_id"]: sum(len(docs[u]) // 4 for u in t["unit_ids"]) for t in tasks}
roster = campaign_roster()
frac = {}
for p in roster:
    fs = [f for f in filas if f["paradigm"] == p]
    if fs:
        frac[p] = sum(f["cost_tokens"] for f in fs) / sum(mat[f["task_id"]] for f in fs)


def proy(tareas, repeat=3, ros=None):
    return sum(frac[p] * mat[t["task_id"]] * repeat
               for p in (ros or roster) if p in frac
               for t in tareas if check(p, docs, t).feasible)


BASE = proy(tasks)
w48 = [t for t in tasks if t["task_id"].endswith("w48")]
print(f"   BASE = {BASE/1e6:,.0f}M tokens")
afirmo(f"repeat 1 ahorra ~67%", abs((BASE - proy(tasks, repeat=1)) / BASE - 2/3) < 0.02,
       f"{(BASE-proy(tasks,repeat=1))/BASE:.1%}")
afirmo(f"w48 es ~61% del gasto", 0.55 < proy(w48) / BASE < 0.65,
       f"{proy(w48)/BASE:.1%}")
# LO QUE SE AFIRMA ES EL MECANISMO; LA MAGNITUD SE REPORTA (corregido 2026-08-29).
#
# Esto afirmaba «sacar dag_strategy ahorra ~27%» y volteo la campaña el dia que la corrida
# light paso de `nano` a `luna`: con luna es 10,4%. El numero no estaba mal — estaba
# MEDIDO SOBRE OTRO MODELO, y es exactamente la distincion que `MODELO_Y_CONSTANTES.es.md`
# hace: los mecanismos son independientes del modelo, las magnitudes no.
#
# Un auditor que afirma una magnitud como si fuera invariante rechaza una corrida legitima
# la primera vez que cambia el modelo. Asi que se afirma lo que es aritmetica —`repeat`
# escala lineal— y lo que es propiedad del MATERIAL —`w48` domina porque tiene 12x—, y el
# reparto entre paradigmas se imprime para mirar.
print(r"\n   reparto del gasto por paradigma (magnitud: depende del modelo, se reporta):")
for nombre in sorted(roster, key=lambda x: -proy(tasks, ros=[x]) if x in frac else 0)[:5]:
    if nombre not in frac:
        continue
    parte = proy(tasks, ros=[nombre])
    print(f"     {nombre:<16} {parte/1e6:>6.0f}M  ({parte/BASE:>5.1%})")

print()
print("=" * 78)
print("5. El catalogo dice lo que digo que dice\n")
from app.paradigms import CATALOG, REGISTRY, Status

afirmo("map_reduce esta RETIRADO", CATALOG["map_reduce"].status is Status.RETIRED)
afirmo("y sigue en el REGISTRY, para replay", "map_reduce" in REGISTRY)
afirmo("el plantel de campana son 12", len(roster) == 12, str(len(roster)))
activos = [n for n, e in CATALOG.items() if e.status is Status.ACTIVE]
afirmo("hay 8 activos", len(activos) == 8, str(sorted(activos)))
diag = sorted(p.stem for p in (raiz / "app/paradigms/diagramas").glob("*.svg"))
afirmo("cada activo tiene diagrama", set(diag) == set(activos), str(diag))

print()
print("=" * 78)
if fallas:
    print(f"HAY {len(fallas)} AFIRMACIONES QUE NO SE SOSTIENEN:")
    for f in fallas:
        print(f"   - {f}")
    sys.exit(1)
print("Las 14 afirmaciones se re-derivaron desde el registro y el codigo.")
