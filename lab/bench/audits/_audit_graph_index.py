"""¿Que falsifico P10a: la tesis de travesia, o el extractor que arma el grafo?

LA SOSPECHA (del autor, 2026-08-28). `graph_traverse` quedo FALSIFICADO con u=0,000 en las
dos celdas acopladas, despues de un indice de ~280k tokens. Pero el indice **no usa NER**:
se arma preguntandole al modelo, unidad por unidad, «listá las entidades y las relaciones»,
y se acepta **lo que conteste, sin verificar nada**. Ni que la entidad aparezca literal en
el texto, ni que la relacion exista.

Compararlo con la sonda deja la asimetria a la vista: `probe._resolve` exige que la
referencia este LITERALMENTE en la unidad y guarda el offset del span para que un auditor
lo encuentre. El indice del grafo no exige nada. O sea que este paradigma se midio con un
insumo de la clase que el invariante del producto **no admite como evidencia**.

QUE DECIDE ESTE SCRIPT. Las tareas C3 declaran su cadena: `truth_n_units` y las unidades
relevantes son la cadena A->B(->C). Si esa arista NO ESTA en el indice, la travesia nunca
tuvo con que caminar, y P10a midio el extractor y no la tesis. Si la arista SI esta y aun
asi u=0,000, la falsificacion se sostiene y es del patron.

Es la leccion de «la atribucion exige la traza» (paper §8.4) aplicada a una falsacion
nuestra. Cero tokens: el indice esta en cache y las cadenas estan en el corpus.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import glob
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CORPUS = sys.argv[1] if len(sys.argv) > 1 else "gold_deep"


def main() -> None:
    indexes = sorted(glob.glob("cache/*/graph/*.json"))
    if not indexes:
        print("No hay indice de grafo en cache: nada que auditar.")
        return

    tasks = json.load(open(f"corpus/{CORPUS}/tasks.json", encoding="utf-8"))
    docs = json.load(open(f"corpus/{CORPUS}/documents.json", encoding="utf-8"))
    coupled = [t for t in tasks if t["cell"].startswith("C3")]
    print(f"corpus {CORPUS}: {len(coupled)} tareas acopladas\n")

    for path in indexes:
        raw = json.load(open(path, encoding="utf-8"))
        entity_units = raw.get("entity_units", {})
        edges = raw.get("edges", {})
        print(f"indice {path.split('/')[-1]}: {len(entity_units)} entidades, "
              f"{len(edges)} nodos con aristas")

        # ¿Las entidades del indice existen LITERALMENTE en alguna unidad?
        checked = grounded = 0
        for entity, units in list(entity_units.items())[:400]:
            checked += 1
            if any(entity.lower() in (docs.get(u) or "").lower() for u in units):
                grounded += 1
        if checked:
            print(f"  entidades que aparecen literal en la unidad que las declara: "
                  f"{grounded}/{checked} ({grounded / checked:.0%})")

        # ¿La cadena de cada tarea acoplada esta representada?
        print(f"\n  {'tarea':<14}{'cadena declarada':<34}{'¿conectada en el indice?'}")
        for task in coupled:
            relevant = task.get("relevant_units") or []
            chain = " -> ".join(relevant) if relevant else "(sin declarar)"
            # ¿Hay alguna entidad que toque dos unidades consecutivas de la cadena?
            linked = []
            for a, b in zip(relevant, relevant[1:]):
                bridges = [
                    e for e, us in entity_units.items()
                    if a in us and b in us
                ]
                linked.append(bool(bridges))
            verdict = ("SI" if linked and all(linked)
                       else f"NO ({sum(linked)}/{len(linked)} saltos)" if linked
                       else "sin cadena declarada")
            print(f"  {task['task_id']:<14}{chain:<34}{verdict}")
        print("")

    print("=" * 76)
    print("  Si los saltos no estan conectados, la travesia nunca tuvo con que caminar y")
    print("  P10a midio el EXTRACTOR, no la tesis. La falsacion habria que reabrirla —")
    print("  no para declarar que el patron sirve, sino para dejar de afirmar que no.")
    print("=" * 76)


if __name__ == "__main__":
    main()
