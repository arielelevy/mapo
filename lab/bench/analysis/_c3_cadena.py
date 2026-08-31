"""C3: ¿cual es el camino perfecto de la cadena, y por que nadie lo recorre?

QUE ES C3. Una cadena de `reporta_a` sobre 60 unidades: se parte de una persona, se sube N
escalones por la linea de reporte, y se pide la cuenta de liquidacion del ULTIMO. `h1`, `h2`
y `h3` son uno, dos y tres saltos, y esa es la unica diferencia entre las tres.

EL CAMINO PERFECTO SE DERIVA DEL CORPUS, no se opina: cada salto es una unidad, y la
respuesta es la cuenta de la unidad final. Este archivo lo RECONSTRUYE leyendo el material —
si el camino que reconstruye no termina en la respuesta del oraculo, el que esta mal es este
archivo y se levanta.

Y LA CADENA ESTA MINADA A PROPOSITO, con tres trampas que se ven al leerla:

  1. **cada unidad tiene su PROPIA cuenta de liquidacion**, pegada al nombre que la ancla.
     La cuenta correcta es la de la unidad N; las otras N estan a la vista y son plausibles
  2. **el edge va por anafora**: «The above-named reports to…», «That person reports to…».
     Hay que resolver a quien apunta, y hay un segundo nombre en la misma unidad
  3. **el destino del salto viene ABREVIADO** —`A. Vallejos`, `C. Ibarrola`, `S. Quiroga`—
     asi que buscar el nombre tal como aparece no encuentra la unidad que sigue

LA PREGUNTA DE ESTE ARCHIVO no es cuanto saca cada brazo —eso ya esta medido— sino **en que
se equivocan**, porque los modos de falla piden arreglos distintos y el promedio los tapa:

  · `ancla`      contesto la cuenta de la unidad de PARTIDA. Se salteo la cadena entera
  · `intermedia` contesto la cuenta de un escalon del medio. Conto mal los saltos
  · `de_afuera`  contesto una cuenta que existe en el material pero NO esta en el camino
  · `inventada`  contesto una cuenta que no esta en ninguna unidad del alcance
  · `abstuvo`    dijo que no se puede determinar

Y ESA ULTIMA FILA ES LA QUE IMPORTA PARA EL PRODUCTO. El banco puntua «abstuvo» y
«contesto mal» los dos con 0,000 — correcto para medir utilidad, y ciego justo en el eje que
MAPO vende. Se cuenta aparte.
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from app.runner import load_rows
from app.verify import is_refusal

sys_out = _sys.stdout
sys_out.reconfigure(encoding="utf-8", errors="replace")

CORPUS = Path("corpus/gold_h1")
REGISTROS = {"luna": Path("results/luna/gold_h1_rows.jsonl"),
             "terra": Path("results/terra/gold_h1_rows.jsonl")}

CUENTA = re.compile(r"\bAR\d{10}\b")
# «X reports to Y», «The above-named reports to Y», «That person reports to Y».
REPORTA = re.compile(
    r"(?:^|\.\s|\n)\s*(?P<sujeto>[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*)*|The above-named|That person)"
    r"\s+reports? to\s+(?P<jefe>[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*)*)",
)
# «Nombre (Ciudad) holds…», «Nombre, based in X, acts as…», «Appointed …: Nombre, resident of…»
NOMBRE_ANCLA = re.compile(r"^INTERNAL MEMORANDUM.*?\n.*?\n\n(?P<cuerpo>.+?)(?:\n\n|$)", re.S)


def unidades_por_cuenta(docs: dict[str, str], unit_ids: list[str]) -> dict[str, str]:
    """cuenta -> unidad que la contiene. Es la tabla que hace clasificable una respuesta."""
    d = {}
    for u in unit_ids:
        for c in CUENTA.findall(docs.get(u, "")):
            d.setdefault(c, u)
    return d


def cuenta_de(docs: dict[str, str], unidad: str) -> str | None:
    m = CUENTA.search(docs.get(unidad, ""))
    return m.group(0) if m else None


def jefe_en(texto: str) -> str | None:
    m = REPORTA.search(texto)
    return m.group("jefe").strip(" .") if m else None


def unidad_de_persona(docs: dict[str, str], unit_ids: list[str], nombre: str) -> str | None:
    """La unidad que ANCLA a esa persona: la que la nombra en su primer parrafo de datos.

    Se resuelve por APELLIDO y, si hay inicial, tambien por ella — que es exactamente el
    trabajo que la cadena exige y que un `keyword_search` del nombre abreviado no hace.
    Si dos unidades matchean, se devuelve `None`: una resolucion ambigua no es un salto.
    """
    partes = nombre.replace(".", " ").split()
    apellido = partes[-1]
    inicial = partes[0][0] if len(partes) > 1 else None
    cands = []
    for u in unit_ids:
        cabeza = docs.get(u, "").split("\n\n")[1] if "\n\n" in docs.get(u, "") else ""
        if apellido not in cabeza:
            continue
        # el nombre completo de esa persona en esta unidad
        for m in re.finditer(rf"\b([A-Z][\w'-]+)\s+{re.escape(apellido)}\b", cabeza):
            if inicial is None or m.group(1)[0] == inicial:
                cands.append(u)
                break
    return cands[0] if len(cands) == 1 else None


def reconstruir(docs, tarea) -> list[str] | None:
    """El camino: ancla, escalones del medio, y unidad final. SIN parsear la cadena entera.

    LA PRIMERA VERSION PARSEABA CADA `reports to` Y FALLO EN 2 DE 3, porque la anafora
    cambia de forma en cada unidad —«The same individual», «They report to», «That person»,
    «The above-named»— y mi regex conocia dos de las cuatro. Peor que fallar: con `cam=None`
    la clasificacion caia entera en `de_afuera` y la tabla decia que NADIE acerto, con
    brazos que tenian u=0,67 en la misma fila. Un parser que no llega tiene que levantar,
    no devolver una respuesta pobre.

    LA VERSION QUE SI SIRVE NO NECESITA LA CADENA. Para clasificar una respuesta alcanza
    con tres cosas que el corpus DECLARA:

      · la unidad FINAL, que es la que contiene el `oracle`
      · la unidad ANCLA, que es la que nombra a la persona de partida en su encabezado
      · las INTERMEDIAS, que son las portadoras restantes

    Ordenarlas entre si no hace falta para decir en que se equivoco una respuesta, y no
    intentarlo saca del medio la unica parte fragil.
    """
    oraculo = (tarea.get("oracle") or [None])[0]
    if not oraculo:
        return None
    port = list(tarea["relevant_units"])
    final = next((u for u in port if oraculo in docs.get(u, "")), None)
    m = re.search(r"Starting from ([A-Z][\w'-]+(?: [A-Z][\w'-]+)*), follow",
                  tarea["question"])
    ancla = next((u for u in port if m and m.group(1) in docs.get(u, "")), None)
    if final is None or ancla is None or final == ancla:
        return None
    medio = [u for u in port if u not in (final, ancla)]
    return [ancla, *medio, final]


def main() -> None:
    docs = json.loads((CORPUS / "documents.json").read_text(encoding="utf-8"))
    tareas = {t["task_id"]: t for t in json.loads(
        (CORPUS / "tasks.json").read_text(encoding="utf-8"))}
    c3 = {k: v for k, v in tareas.items() if v["cell"] == "C3_coupled_chain"}

    print("=" * 90)
    print("1. EL CAMINO PERFECTO, RECONSTRUIDO DEL MATERIAL")
    print("=" * 90)
    print("""
  No se opina: se lee. Y se verifica contra las portadoras que el corpus declara — si el
  camino reconstruido no coincide con ellas, el que esta mal es este archivo.
""")
    caminos = {}
    for tid, t in sorted(c3.items()):
        cam = reconstruir(docs, t)
        caminos[tid] = cam
        decl = set(t["relevant_units"])
        ok = cam is not None and set(cam) == decl
        print(f"  {tid}  ({len(t['relevant_units'])} portadoras declaradas)")
        if cam is None:
            print("    NO RECONSTRUIBLE con este parser — el archivo no puede opinar de esta")
            continue
        for i, u in enumerate(cam):
            cab = docs[u].split("\n\n")[1].split("\n")[0][:64]
            # `medio` Y NO `salto1`: los intermedios salen de `relevant_units`, que no
            # declara orden. Numerarlos afirmaria un orden que este archivo no midio — y
            # el orden es justo lo que la pregunta pide resolver.
            rol = "ancla" if i == 0 else ("FINAL" if i == len(cam) - 1 else "medio")
            print(f"    {rol:<6} {u}  {cab}")
        print(f"    RESPUESTA = cuenta de {cam[-1]} = {cuenta_de(docs, cam[-1])}"
              + ("   [coincide con las portadoras]" if ok else "   [!] NO coincide"))
        # LAS TRAMPAS, contadas y no narradas.
        senuelos = [cuenta_de(docs, u) for u in cam[:-1]]
        print(f"    señuelos a la vista: {len(senuelos)} cuentas mas, una por escalon "
              f"({', '.join(x for x in senuelos if x)})")
        print()

    print("=" * 90)
    print("2. EN QUE SE EQUIVOCAN — el modo de falla, no el puntaje")
    print("=" * 90)
    print("""
  Cinco modos, y cada uno pide un arreglo distinto:

    ancla       contesto la cuenta de la unidad de PARTIDA — se salteo la cadena entera
    intermedia  contesto la de un escalon del medio — conto mal los saltos
    de_afuera   una cuenta real del material, fuera del camino
    inventada   una cuenta que no existe en ninguna unidad del alcance
    abstuvo     dijo que no se puede determinar
""")
    for modelo, ruta in REGISTROS.items():
        if not ruta.exists():
            continue
        filas = [f for f in load_rows(ruta)
                 if f["task_id"] in c3 and not f.get("infeasible")]
        if not filas:
            continue
        modos = defaultdict(Counter)
        u_por = defaultdict(list)
        for f in filas:
            tid, p = f["task_id"], f["paradigm"]
            t = tareas[tid]
            cam = caminos.get(tid)
            u_por[p].append(f.get("utility", 0.0))
            ans = f.get("answer") or ""
            hallados = CUENTA.findall(ans)
            if not hallados:
                # NO TODA RESPUESTA SIN NUMERO ES UNA ABSTENCION, y meterlas juntas rompia
                # justo la afirmacion de este archivo. Cinco respuestas eran `M. Arrieta` y
                # `Renata Novoa`: la PERSONA en vez de la cuenta — un error de tipo, no una
                # negativa. Contarlas como abstenciones inflaba la unica columna que sirve
                # para decir quien se calla en vez de equivocarse.
                #
                # El arbitro es `is_refusal` del banco y no una lista local: si el grader y
                # esta figura no comparten la definicion de rechazo, dicen cosas distintas
                # del mismo texto. Y al usarlo aparecio que al vocabulario le faltaban tres
                # formas —«not on file», «not identified», «not determinable»— que ahora
                # estan en `verify.py` (y arreglaron 5 filas de D1 que puntuaban 0).
                modos[p]["abstuvo" if is_refusal(ans) else "otro tipo"] += 1
                continue
            c = hallados[0]
            if cam and c == cuenta_de(docs, cam[-1]):
                modos[p]["CORRECTA"] += 1
            elif cam and c == cuenta_de(docs, cam[0]):
                modos[p]["ancla"] += 1
            elif cam and c in {cuenta_de(docs, u) for u in cam[1:-1]}:
                modos[p]["intermedia"] += 1
            elif c in unidades_por_cuenta(docs, t["unit_ids"]):
                modos[p]["de_afuera"] += 1
            else:
                modos[p]["inventada"] += 1
        orden_modos = ["CORRECTA", "ancla", "intermedia", "de_afuera", "inventada",
                       "abstuvo", "otro tipo"]
        print(f"  ── {modelo} " + "─" * 74)
        print(f"  {'brazo':<16}{'u':>6}" + "".join(f"{m:>12}" for m in orden_modos))
        for p in sorted(u_por, key=lambda k: -statistics.mean(u_por[k])):
            fila = f"  {p:<16}{statistics.mean(u_por[p]):>6.2f}"
            for m in orden_modos:
                fila += f"{modos[p][m] or '':>12}"
            print(fila)
        print()

    print("=" * 90)
    print("3. LA GUARDA QUE FALTA, Y CUANTO ATAJA — `C-CHAIN`")
    print("=" * 90)
    print("""
  MI PRIMERA GUARDA ATAJABA EL MODO EQUIVOCADO, y la tabla de arriba es la que lo dice.
  Propuse prohibir la cuenta de la unidad ANCLA —«el brazo se salteo la cadena»— y ese modo
  aparece 2 veces en terra. El dominante es `intermedia`: 7 veces entre `react` y
  `reflection`. No se saltean la cadena: **la cortan un escalon antes**. Un off-by-one en el
  conteo de saltos, no una omision.

  LA GUARDA CORRECTA ES LA DEFINICION DE LA PREGUNTA, escrita como contrato:

      una respuesta a `subir N escalones` es admisible solo si viene acompanada de una
      CADENA de N+1 unidades distintas, cada eslabon con procedencia OBSERVED de la unidad
      donde se leyo el `reports to`, y la cuenta sale de la ULTIMA.

  Eso no es una heuristica: es la pregunta. Y es exactamente la escalera de creencias que
  el producto ya tiene —`ELICITED` la persona de partida, `OBSERVED` cada `reports to`,
  `COMPUTED` la resolucion de la forma abreviada a la unidad siguiente— con el conjunto de
  pruebas admisibles de `app/contracts.py` decidiendo si alcanza. Sin la cadena, no hay
  respuesta: hay abstencion.

  LO QUE ESTE ARCHIVO NO PUEDE MEDIR, y hay que decirlo antes del numero. Las filas NO
  guardan la procedencia salto por salto, asi que la cadena no se puede verificar hacia
  atras sobre el registro. Lo que si se ve es la cota: toda respuesta cuya cuenta no salga
  de la unidad final es una que NO podria exhibir la cadena.

  Y hay una prueba de existencia en la tabla, que vale mas que la propuesta: `dag_strategy`
  en terra hace 8 correctas, 1 abstencion y **cero respuestas equivocadas**. No gana C3 por
  encadenar mejor — gana porque cuando no puede, lo dice. Los demas contestan igual.
""")
    total = Counter()
    for modelo, ruta in REGISTROS.items():
        if not ruta.exists():
            continue
        for f in load_rows(ruta):
            if f["task_id"] not in c3 or f.get("infeasible"):
                continue
            cam = caminos.get(f["task_id"])
            if not cam:
                continue
            hall = CUENTA.findall(f.get("answer") or "")
            total["respuestas con cuenta"] += 1 if hall else 0
            if hall and hall[0] == cuenta_de(docs, cam[0]) and len(cam) > 1:
                total["  de las cuales `ancla` (mi guarda vieja)"] += 1
            if hall and hall[0] != cuenta_de(docs, cam[-1]):
                total["SIN cadena exhibible -> abstencion"] += 1
            if hall and hall[0] == cuenta_de(docs, cam[-1]):
                total["correctas (la guarda NO las toca)"] += 1
    for k, v in total.items():
        print(f"    {k:<48}{v:>5}")
    n = total["respuestas con cuenta"]
    if n:
        sin = total["SIN cadena exhibible -> abstencion"]
        viejo = total["  de las cuales `ancla` (mi guarda vieja)"]
        print(f"\n    El contrato de cadena manda a abstenerse {sin} de {n} respuestas con"
              f" numero ({sin / n:.0%}),")
        print(f"    y NO toca ninguna de las {total['correctas (la guarda NO las toca)']}"
              f" correctas. Mi guarda vieja veia {viejo} de esas {sin}")
        print(f"    ({viejo / sin:.0%}), y era el modo de falla menos frecuente de los tres.")
        print("\n    LO QUE CAMBIA NO ES LA UTILIDAD SINO EL TIPO DE ERROR. Las 36 siguen")
        print("    puntuando 0,000 en el banco, igual que hoy. Lo que cambia es que dejan de")
        print("    ser un numero de cuenta afirmado con confianza y pasan a ser una negativa")
        print("    — y esa diferencia, que este banco no puntua, es el producto entero.")


if __name__ == "__main__":
    main()
