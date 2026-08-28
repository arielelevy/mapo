"""Guardas cuyo disparador NO lo satisface ningun corpus del repo.

DE DONDE SALE, Y ES UNA REINCIDENCIA. `_audit_declarado.py` busca nombres que se definen y
nadie lee. Encontro cinco reales, uno de ellos mio de una hora antes. Horas despues cometi
la MISMA falla en otra forma que ese barrido no puede ver:

  la precondicion de cobertura (`U-2`) poda paradigmas cuando la tarea exige cobertura
  total sobre material masivo. El codigo se lee, se ejecuta, tiene test que pasa. Y
  **ningun corpus del repo declara `coverage_demanded`**, asi que nunca disparo ni una vez.
  Peor: aunque disparara, `TRAVERSES_SCOPE` y la fila activa de medicion tienen
  interseccion VACIA, asi que siempre caeria en la rama «no se pudo imponer».

  La cerre como hecha.

POR QUE EL BARRIDO LEXICO NO LA VE. `TRAVERSES_SCOPE` SI se lee: el router la consulta. El
nombre gobierna. Lo que no existe es el DATO que hace verdadera la condicion. Eso no es una
propiedad del codigo — es una propiedad del cruce entre el codigo y los corpus, y solo se
puede ver ejecutando la condicion contra ellos.

QUE HACE ESTO. Toma condiciones de disparo declaradas y pregunta, por corpus, cuantas
tareas las satisfacen. Cero en todos es una guarda que no protege nada todavia, y eso puede
estar bien —una guarda para un corpus que aun no existe es legitima— pero tiene que ser una
DECISION y no una sorpresa.

QUE NO ES. No prueba que la guarda sea correcta ni que sirva. Prueba una sola cosa: si
alguna vez corrio. La lista es para mirar, igual que la del otro barrido.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.contracts import OBLIGATIONS
from app.feasibility import check
from app.paradigms import TRAVERSES_SCOPE
from app.rules import BULK_THRESHOLD

# La fila que se mide hoy. Se declara aca y no se deriva del REGISTRY porque lo que
# importa es que brazos se CORREN, no cuales existen: un paradigma retirado sigue en el
# registro y no puede satisfacer nada.
FILA_ACTIVA = ("react", "dag_strategy", "rewoo", "gist_reader", "handoff")


def disparadores() -> dict[str, callable]:
    """Cada condicion de disparo, como funcion sobre una tarea.

    Se escriben aca y no se importan de donde viven porque lo que se audita es la
    CONDICION, no la funcion que la usa: importar la funcion probaria que la funcion
    corre, que es otra cosa.
    """
    return {
        "U-2 precondicion de cobertura":
            lambda t: t.get("coverage_demanded") == "exhaustive"
            and len(t.get("unit_ids") or []) > BULK_THRESHOLD,
        "C-COMPLETE (verify_coverage)":
            lambda t: bool(t.get("domain_keys")),
        "C-ABSENCE (obligacion declarada)":
            lambda t: "absence" in (t.get("obligations") or []),
        "C-PRESUPPOSITION (obligacion declarada)":
            lambda t: "presupposition" in (t.get("obligations") or []),
        "presupuesto en PLATA (check_pair)":
            lambda t: t.get("budget_usd") is not None,
        "accion irreversible (piso A3)":
            lambda t: t.get("irreversible") is True,
        "escrituras compartidas (piso A2)":
            lambda t: t.get("shared_writes") is True,
    }


def main() -> None:
    corpora = sorted(
        d for d in Path("corpus").iterdir()
        if d.is_dir() and (d / "tasks.json").exists()
    )
    if not corpora:
        print("No hay corpus con `tasks.json`. Nada que auditar — se dice, no se supone.")
        return

    tareas: dict[str, list[dict]] = {}
    for d in corpora:
        tareas[d.name] = json.loads((d / "tasks.json").read_text(encoding="utf-8"))
    total = sum(len(v) for v in tareas.values())
    print(f"{len(corpora)} corpus, {total} tareas\n")

    ancho = max(len(k) for k in disparadores())
    inertes = []
    for nombre, cond in disparadores().items():
        por_corpus = {c: sum(1 for t in ts if cond(t)) for c, ts in tareas.items()}
        n = sum(por_corpus.values())
        donde = sorted(c for c, k in por_corpus.items() if k)
        marca = "  <- NUNCA DISPARO" if n == 0 else ""
        print(f"  {nombre:<{ancho}}  {n:>4}/{total}{marca}")
        if donde and n:
            print(f"  {'':<{ancho}}  en {', '.join(donde[:5])}"
                  + (" …" if len(donde) > 5 else ""))
        if n == 0:
            inertes.append(nombre)

    # SEGUNDO EJE, y es el que hizo doblemente inerte a `U-2`: aunque la condicion
    # dispare, puede no haber ningun brazo capaz de satisfacer la guarda. Una guarda que
    # dispara y no tiene con que cumplirse no poda: registra que no pudo.
    print()
    inter = sorted(set(FILA_ACTIVA) & set(TRAVERSES_SCOPE))
    print(f"  brazos que recorren el alcance : {sorted(TRAVERSES_SCOPE)}")
    print(f"  fila activa de medicion        : {list(FILA_ACTIVA)}")
    print(f"  interseccion                   : {inter or 'VACIA'}")
    if not inter:
        print("  => la precondicion de cobertura no puede imponerse con la fila activa:")
        print("     aunque disparara, siempre cae en la rama «no se pudo imponer»")

    print()
    if inertes:
        print(f"{len(inertes)} guardas nunca dispararon. Que este bien depende del caso:")
        print("una guarda para un corpus que todavia no existe es legitima, pero tiene")
        print("que ser una DECISION y no una sorpresa. Y una que se cerro como «hecha»")
        print("sin haber corrido nunca no es ninguna de las dos.")
    else:
        print("Todas las guardas disparan en algun corpus.")


if __name__ == "__main__":
    main()
