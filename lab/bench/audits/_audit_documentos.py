"""Los documentos VIVOS contra el codigo: conteos, estados del catalogo y enlaces.

DE DONDE SALE (2026-08-29). Retirar `map_reduce` dejo **nueve documentos** diciendo «13
patrones» cuando eran 12. Ninguno estaba mal escrito: estaban bien el dia que se
escribieron. Y ninguna otra guarda los ve — los tests prueban el codigo, `_audit_declarado`
barre nombres, `_audit_inerte` cruza codigo con corpus, y ninguno lee prosa.

El mismo dia, cuatro scripts tenian el plantel clavado a mano y quedaron viejos por el mismo
retiro. Eso se arreglo en el codigo (`campaign_roster()`); esto es la mitad que faltaba.

QUE REVISA, Y POR QUE SOLO ESO. Tres cosas que se pueden DERIVAR, no opinar:

  1. conteos de patrones que contradigan al `CATALOG`
  2. un paradigma nombrado con un estado que el `CATALOG` desmiente
  3. enlaces a archivos que no existen

Lo que NO revisa es si lo que el documento dice es CIERTO. Un barrido lexico no lee: puede
decir que un numero contradice al catalogo, no que un parrafo este bien pensado.

QUE ES UN DOCUMENTO VIVO. Los de `historico/` y `notes/` quedan afuera **a proposito**: son
snapshots fechados, y su numero era cierto cuando se escribio. Corregirlos seria reescribir
el registro, que es exactamente lo que este repo no hace. Un documento con fecha se lee como
lo que es; uno vivo se lee como el estado de hoy.

Corre DESDE `lab/`. No gasta cuota.
"""

import re
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.paradigms import CATALOG, REGISTRY, Status, campaign_roster

# La raiz del REPO, no del lab: `README.md`, `CLAUDE.md` y `ui/` tambien son documentos
# vivos y tambien se quedaron viejos.
RAIZ = Path("..").resolve()
FECHADOS = ("historico", "notes", "node_modules", ".git", ".pytest_cache")

NUMEROS = {
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16,
}


def vivos() -> list[Path]:
    return [
        p for p in RAIZ.rglob("*.md")
        if not set(p.parts) & set(FECHADOS)
    ]


def main() -> None:
    catalogo = len(REGISTRY)
    plantel = len(campaign_roster())
    activos = len([n for n, e in CATALOG.items() if e.status is Status.ACTIVE])
    verdad = {catalogo, plantel, activos}
    print(f"El catalogo dice: {catalogo} registrados · {plantel} de campana · "
          f"{activos} activos\n")

    hallazgos: list[str] = []   # derivables: fallan
    sospechas: list[str] = []   # leads: avisan, y se deciden leyendo
    documentos = vivos()

    # 1. CONTEOS. Se busca «N patrones/paradigmas», en digito o en letra, y se acepta solo
    #    si N es uno de los tres numeros que el catalogo sostiene. Cualquier otro es una
    #    afirmacion sobre el catalogo que el catalogo no respalda.
    patron = re.compile(
        r"\b(\d{1,2}|" + "|".join(NUMEROS) + r")\s+(patrones|paradigmas)\b",
        re.IGNORECASE,
    )
    for doc in documentos:
        # `whitepaper/` QUEDA AFUERA DEL CHEQUEO DE CONTEOS, y no es una excepcion de
        # conveniencia: el paper CITA planteles ajenos —Select-then-Solve mide 6
        # paradigmas, `PATTERNS.md` cataloga 10 de la literatura— y esos numeros son de
        # esos trabajos. Exigirles el nuestro seria pedirle al paper que mienta sobre lo
        # que cita. Lo que el paper afirme SOBRE ESTE catalogo se revisa leyendo, que es
        # justo lo que `GATE.md` existe para hacer.
        if "whitepaper" in doc.parts:
            continue
        for i, linea in enumerate(doc.read_text(encoding="utf-8", errors="replace")
                                  .splitlines(), 1):
            for m in patron.finditer(linea):
                crudo = m.group(1).lower()
                n = NUMEROS.get(crudo, None)
                if n is None:
                    try:
                        n = int(crudo)
                    except ValueError:
                        continue
                if n not in verdad:
                    hallazgos.append(
                        f"{doc.relative_to(RAIZ)}:{i}  dice «{m.group(0)}» y el catalogo "
                        f"sostiene {sorted(verdad)}"
                    )

    # 2. ESTADOS. Un documento vivo que llame «activo» a un brazo retirado, o «retirado» a
    #    uno activo, esta diciendo lo contrario de lo que el ejecutable decide.
    contrarios = {
        "activo": (Status.RETIRED, Status.STANDBY),
        "retirado": (Status.ACTIVE,),
        "en standby": (Status.ACTIVE, Status.RETIRED),
        "en `standby`": (Status.ACTIVE, Status.RETIRED),
    }
    # UNA LINEA CON DOS BRAZOS NO SE PUEDE ATRIBUIR. «donde el material entra lo domina
    # `direct`» dentro de la fila que explica por que `map_reduce` esta retirado nombra a
    # los dos, y el barrido le colgaba el estado al equivocado. Se exige UN solo brazo por
    # linea; lo que eso deja pasar es una linea ambigua, que es mejor que un falso positivo
    # con cara de hallazgo.
    for doc in documentos:
        texto = doc.read_text(encoding="utf-8", errors="replace")
        for i, linea in enumerate(texto.splitlines(), 1):
            nombrados = [n for n in REGISTRY if f"`{n}`" in linea]
            if len(nombrados) != 1:
                continue
            nombre = nombrados[0]
            bajo = linea.lower()
            for palabra, estados_malos in contrarios.items():
                if palabra in bajo and CATALOG[nombre].status in estados_malos:
                    sospechas.append(
                        f"{doc.relative_to(RAIZ)}:{i}  llama «{palabra}» a "
                        f"`{nombre}`, que esta {CATALOG[nombre].status.value}"
                    )

    # 3. NUMEROS DE LECCION UNICOS. `LECCIONES.es.md` se cita POR NUMERO desde
    #    `PENDIENTES.es.md` y `DISENO.es.md` —una docena de referencias— asi que un numero
    #    que apunta a dos entradas hace que la cita no signifique nada, y nada avisa: las
    #    dos entradas se leen bien por separado.
    #
    #    Encontrado el 2026-08-29: `5.7` estaba duplicado. La entrada se numera a mano al
    #    escribirla, y con 76 entradas y las secciones apiladas fuera de orden —la §8 tiene
    #    entradas 2.4, 5.3, 6.3, 7.8— nadie puede sostener la unicidad leyendo.
    lecciones = RAIZ / "lab" / "LECCIONES.es.md"
    if lecciones.exists():
        vistos: dict[str, int] = {}
        for i, linea in enumerate(lecciones.read_text(encoding="utf-8").splitlines(), 1):
            m = re.match(r"### (\d+\.\d+[a-z]?) ", linea)
            if not m:
                continue
            numero = m.group(1)
            if numero in vistos:
                hallazgos.append(
                    f"LECCIONES.es.md:{i}  repite el numero «{numero}», ya usado en la "
                    f"linea {vistos[numero]} — y las lecciones se citan por numero"
                )
            vistos[numero] = i

    # 4. ENLACES. Ya no es sobre el catalogo, pero es la misma clase: algo que el documento
    #    afirma y se puede derivar.
    enlace = re.compile(r"\]\(([^)#:]+\.(?:md|py|json|svg))\)")
    for doc in RAIZ.rglob("*.md"):
        if set(doc.parts) & {"node_modules", ".git", ".pytest_cache"}:
            continue
        for i, linea in enumerate(doc.read_text(encoding="utf-8", errors="replace")
                                  .splitlines(), 1):
            for m in enlace.finditer(linea):
                destino = m.group(1)
                if destino.startswith("http"):
                    continue
                if not (doc.parent / destino.replace("\\", "/")).exists():
                    hallazgos.append(
                        f"{doc.relative_to(RAIZ)}:{i}  enlaza a «{destino}», que no existe"
                    )

    print(f"{len(documentos)} documentos vivos revisados "
          f"(los de {'/'.join(FECHADOS[:2])} quedan afuera: son snapshots fechados)\n")
    # LAS SOSPECHAS AVISAN Y NO VOLTEAN. Es la disciplina de `_audit_declarado` —«la lista
    # no es un veredicto, cada caso se decide leyendo»— y aca hace falta mas todavia:
    # «la mejora de `reflection` se retiro como ruido» tiene la palabra y el sujeto NO es el
    # brazo. Un barrido lexico no distingue el sujeto de una oracion, y hacer fallar sobre
    # eso entrenaria a ignorar la salida — que es como muere una guarda.
    if sospechas:
        print(f"{len(sospechas)} LINEAS PARA MIRAR (avisan, no voltean):\n")
        for x in sospechas:
            print(f"  {x}")
        print()

    if hallazgos:
        print(f"HAY {len(hallazgos)} CONTRADICCIONES DERIVABLES:\n")
        for h in hallazgos:
            print(f"  {h}")
        raise SystemExit(1)
    print("Ningun conteo de documento vivo contradice al catalogo, y ningun enlace "
          "esta roto.")


if __name__ == "__main__":
    main()
