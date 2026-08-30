"""Las SPECS del codigo contra los invariantes del producto. Cero llamadas al modelo.

QUE ES UNA SPEC ACA. El docstring de arriba de cada modulo y de cada clase de `app/`. Este
repo se lee mas de lo que se escribe: la mitad de los defectos encontrados el 2026-08-29
—el board que no llegaba a nadie, el guard que no disparaba, el agotamiento invisible
adentro de un sub-agente— se encontraron LEYENDO. Una clase sin spec es una que nadie puede
auditar sin reconstruirla de memoria.

QUE CHEQUEA, Y ES UNA SOLA COSA: que los invariantes que `CLAUDE.md` declara **estén
nombrados en los modulos que los hacen cumplir**. No prueba que el codigo los cumpla —eso
lo prueban los tests— sino que el modulo que los sostiene lo DIGA, que es la condicion para
que alguien pueda revisarlo despues.

DOS FALSOS NEGATIVOS QUE ESTA VERSION EVITA, y los dos los cometio la primera:

  1. LA FRASE CORTADA POR EL SALTO DE LINEA. «misma base de creencias ⟹ misma decision»
     esta en `beliefs.py` partida en dos renglones, y un `in` crudo no la encuentra. Se
     normaliza el espacio en blanco antes de buscar.
  2. LAS FUNCIONES CUENTAN. `policy.py` nombra la garantia adentro de una funcion, no de
     una clase. Barrer solo modulos y clases la daba por ausente.

Un chequeo de coherencia con falsos negativos es PEOR que ninguno: manda a arreglar cosas
que no estan rotas, y despues nadie lo corre.

Corre DESDE `lab/`:  py bench/audits/_audit_specs.py
"""

from __future__ import annotations

import ast
import re
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = _Path("app")

# LOS INVARIANTES SALEN DE `CLAUDE.md`, no de la opinion de quien escribe esto. Cada uno
# es un patron y la lista de modulos que TIENEN que nombrarlo — los que lo hacen cumplir,
# no todos los que lo mencionan de paso.
INVARIANTES: dict[str, tuple[str, tuple[str, ...]]] = {
    "la forma de la garantía": (
        r"misma base de creencias",
        ("beliefs.py", "policy.py", "router.py"),
    ),
    "el LLM es sensor, no decisor": (
        r"sensor|no decide|jamás maneja|no maneja flujo",
        ("beliefs.py", "router.py"),
    ),
    "piso de procedencia en lo irreversible": (
        r"irreversible",
        ("beliefs.py", "assurance.py"),
    ),
    "el aprendizaje es offline": (
        r"offline|copy-on-write|adentro de un request",
        ("policy.py", "consolidation.py"),
    ),
    "un 429 no es una medición": (
        r"infra_error",
        ("runner.py",),
    ),
    "se califica sin juez": (
        r"sin juez|exact match|judge",
        ("runner.py", "grading.py"),
    ),
    "un factor que no llega al modelo no existe": (
        r"no llega al modelo|no existe: corre|mide su ausencia|un factor",
        ("tools.py",),
    ),
    "un episodio es una celda, no una réplica": (
        r"pseudorreplicaci|una celda|réplica",
        ("policy.py", "runner.py"),
    ),
}


def specs_de(f: _Path) -> str:
    """Todo el texto declarativo de un archivo: modulo, clases Y funciones.

    Las tres, porque un invariante puede vivir en cualquiera de los tres niveles y
    barrer solo dos lo da por ausente — que es el falso negativo #2 del docstring.
    """
    arbol = ast.parse(f.read_text(encoding="utf-8"))
    partes = [ast.get_docstring(arbol) or ""]
    for n in ast.walk(arbol):
        if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            partes.append(ast.get_docstring(n) or "")
    # EL ESPACIO SE NORMALIZA ANTES DE BUSCAR: una frase partida por el ancho de linea
    # sigue siendo la misma frase. Es el falso negativo #1.
    return re.sub(r"\s+", " ", " ".join(partes)).lower()


def main() -> None:
    archivos = {f.name: specs_de(f) for f in sorted(RAIZ.rglob("*.py"))}
    print(f"{len(archivos)} archivos de `app/` leídos\n")

    print("=" * 78)
    print("LOS INVARIANTES, contra los módulos que los hacen cumplir\n")
    faltan: list[str] = []
    for nombre, (patron, modulos) in INVARIANTES.items():
        tiene = [m for m in modulos if re.search(patron, archivos.get(m, ""))]
        sin = [m for m in modulos if m not in tiene]
        marca = "OK  " if not sin else "FALTA"
        print(f"  {marca} {nombre}")
        print(f"       lo nombran: {', '.join(tiene) or 'ninguno'}")
        if sin:
            print(f"       NO lo nombran: {', '.join(sin)}")
            faltan += [f"{nombre} → {m}" for m in sin]

    print("\n" + "=" * 78)
    print("COBERTURA DE SPEC — el piso escala con el tamaño de la clase\n")
    # Una clase de más de 80 líneas es MAQUINARIA y pide un párrafo; un contenedor de tres
    # campos no. Exigirle prosa a lo chico produce relleno, que le enseña al lector que la
    # documentación de este repo no dice nada.
    GRANDE, MINIMA = 80, 250
    chicas: list[str] = []
    total = 0
    for f in sorted(RAIZ.rglob("*.py")):
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if not isinstance(n, ast.ClassDef):
                continue
            total += 1
            d = ast.get_docstring(n) or ""
            if n.end_lineno - n.lineno > GRANDE and len(d) < MINIMA:
                chicas.append(f"{f.name}:{n.name} "
                              f"({n.end_lineno - n.lineno} líneas, {len(d)} chars)")
    print(f"  {total} clases · {len(chicas)} sin spec suficiente")
    for c in chicas:
        print(f"     {c}")

    print("\n" + "=" * 78)
    if faltan or chicas:
        print(f"{len(faltan) + len(chicas)} inconsistencias. Cada una se decide LEYENDO:")
        print("un invariante puede vivir en otro módulo con razón, y eso se arregla en la")
        print("lista de este script, no en el código.")
        raise SystemExit(1)
    print("Cada invariante está nombrado donde se hace cumplir, y ninguna clase grande")
    print("se despacha con un renglón.")


if __name__ == "__main__":
    main()
