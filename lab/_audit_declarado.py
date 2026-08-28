"""Campos y constantes que se DECLARAN y no los lee nadie.

DE DONDE SALE. Cuatro veces en un dia aparecio la misma forma: una capacidad completa,
declarada, que ningun camino ejecutaba.

  `theta_may_learn_online`   vivia en el perfil de garantia y no lo leia nadie
  la calibracion             el router recibia un objeto que ninguno de 5 sitios pasaba
  las particiones            se descubrian sobre ejes inevaluables al decidir
  `mean_cost`                el comentario prometia que superseder­ia al prior; no ocurria

Ninguna rompia nada. Todas se cumplian «por casualidad» o no se cumplian, y el sintoma
era el mismo: el sistema anda, y una garantia que alguien enuncio no existe.

QUE BUSCA ESTO. Nombres que se DEFINEN —campo de dataclass o constante de modulo— y cuyo
unico uso es su propia definicion, su serializacion o un formato de impresion. Un nombre
asi no gobierna nada: describe.

QUE NO ES. No es un detector de codigo muerto. Un campo que solo se serializa puede estar
bien —la huella de decodificacion se guarda para que el registro sea autodescriptivo, y
eso es su trabajo entero—. Lo que produce es una LISTA PARA MIRAR, y cada caso se decide
leyendo. La diferencia entre «se guarda a proposito» y «se declaro y se olvido» no la
puede hacer un grep, y no se pretende.
"""

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path("app")
# Usos que NO cuentan como gobernar: guardarse, mostrarse, o nombrarse a si mismo.
SOLO_DESCRIBE = re.compile(
    r'(as_dict|to_dict|__repr__|print\(|f"|json\.dumps|"[a-z_]+":)'
)


def definiciones(path: Path) -> list[tuple[str, int, str]]:
    """Campos de dataclass y constantes de modulo, con su linea."""
    try:
        arbol = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    out = []
    for nodo in ast.walk(arbol):
        # constante de modulo
        if isinstance(nodo, ast.Assign) and getattr(nodo, "col_offset", 1) == 0:
            for t in nodo.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    out.append((t.id, nodo.lineno, "constante"))
        # campo de dataclass
        if isinstance(nodo, ast.ClassDef):
            for cuerpo in nodo.body:
                if isinstance(cuerpo, ast.AnnAssign) and isinstance(cuerpo.target, ast.Name):
                    out.append((cuerpo.target.id, cuerpo.lineno, f"campo de {nodo.name}"))
    return out


def main() -> None:
    fuentes = sorted(RAIZ.rglob("*.py"))
    texto = {p: p.read_text(encoding="utf-8") for p in fuentes}
    todo = "\n".join(texto.values())

    sospechosos = []
    for path in fuentes:
        for nombre, linea, clase in definiciones(path):
            if nombre.startswith("_") or len(nombre) < 4:
                continue
            usos = [
                (p, i + 1, l)
                for p, s in texto.items()
                for i, l in enumerate(s.split("\n"))
                if re.search(rf"\b{re.escape(nombre)}\b", l)
            ]
            # Sacar la definicion misma.
            reales = [
                (p, i, l) for p, i, l in usos
                if not (p == path and i == linea)
            ]
            if not reales:
                sospechosos.append((path, nombre, clase, "definido y NUNCA nombrado"))
                continue
            gobierna = [
                (p, i, l) for p, i, l in reales
                if not SOLO_DESCRIBE.search(l)
            ]
            if not gobierna:
                sospechosos.append((
                    path, nombre, clase,
                    f"nombrado {len(reales)}x, y SOLO para guardarse o mostrarse",
                ))

    if not sospechosos:
        print("Ninguno: todo lo declarado tiene al menos un uso que gobierna.")
        return

    print(f"{len(sospechosos)} nombres para mirar — la lista NO es un veredicto:\n")
    por_archivo = defaultdict(list)
    for path, nombre, clase, por_que in sospechosos:
        por_archivo[path].append((nombre, clase, por_que))
    for path, items in sorted(por_archivo.items()):
        print(f"{path}")
        for nombre, clase, por_que in items:
            print(f"    {nombre:<28} {clase:<22} {por_que}")
    print()
    print("Cada caso se decide LEYENDO. Un campo que solo se serializa puede estar bien:")
    print("la huella de decodificacion se guarda para que el registro sea autodescriptivo,")
    print("y ese ES su trabajo. La diferencia entre «se guarda a proposito» y «se declaro")
    print("y se olvido» no la puede hacer un grep, y esto no lo pretende.")


if __name__ == "__main__":
    main()
