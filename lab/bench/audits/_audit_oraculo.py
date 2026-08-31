"""¿Cuántos de nuestros ceros son del brazo, y cuántos del corrector? CERO llamadas al modelo.

POR QUÉ EXISTE. OpenAI auditó a mano los fallos de o3 en SWE-bench Verified y encontró que
el **59,4%** no eran fallos del modelo sino defectos del arnés de test. Es el pitfall más
caro de todos, porque **no se ve desde adentro**: un cero se lee igual venga de donde venga,
y una tabla de utilidades con el corrector roto es indistinguible de una con el corrector
bien. Nosotros ya lo vivimos dos veces en dos días:

  · el corrector comparaba rechazos por igualdad de cadenas y ponía 0,00 a **9 de 78
    tareas sobre los doce brazos** — los nueve habían contestado bien
  · el vocabulario de rechazo se había derivado de UNA celda (`D1`), así que le faltaban
    tres formas —«not on file», «not identified», «not determinable»— y las destapó `C3`,
    no `D1`

Las dos veces el hallazgo fue por accidente. Este archivo lo hace a propósito.

CÓMO. Barre TODA respuesta con utilidad 0,0 y busca las señales de que el cero es del
corrector y no del brazo. Ninguna prueba es concluyente sola —por eso el resultado son
SOSPECHAS ordenadas por fuerza, no un veredicto— pero todas son baratas y ninguna llama al
modelo:

  `contiene_el_oraculo`   la respuesta contiene el literal del oráculo y sacó cero igual.
                          Es la señal más fuerte que existe: si el dato está, el cero es
                          del emparejamiento
  `parcial_no_creditado`  respuesta multi-ítem que trae ALGUNOS de los ítems del oráculo y
                          saca 0,0 en vez de una fracción
  `rechazo_no_reconocido` la respuesta parece una negativa —y la verdad TAMBIÉN lo es—
                          pero `is_refusal` no la reconoce. Es el defecto exacto que ya
                          apareció dos veces
  `numero_equivalente`    el oráculo es numérico y la respuesta trae el mismo número con
                          otro formato (separadores, decimales, moneda)

LO QUE NO HACE, Y HAY QUE DECIRLO. No prueba que el corrector esté mal: prueba que hay
respuestas que MERECEN una mirada humana. La auditoría de OpenAI fue a mano y ésta también
tiene que terminar a mano — lo que este archivo compra es no tener que leer 1.868 filas para
encontrar las doce que importan.

Corre DESDE `lab/`:  py bench/audits/_audit_oraculo.py [--corpus gold_h1] [--mostrar 15]
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

_sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.runner import load_rows
from app.verify import is_refusal, normalise, split_items

_NUMERO = re.compile(r"-?\d[\d.,]*")


def _numeros(texto: str) -> set[str]:
    """Los números del texto, normalizados: sin separadores y sin ceros decimales sobrantes.

    `1.234,00`, `1234` y `1,234` son el mismo número escrito de tres formas, y un corrector
    por subcadena los ve distintos. Es la clase de defecto que sólo se ve contando.
    """
    salida = set()
    for m in _NUMERO.finditer(texto or ""):
        crudo = m.group(0).rstrip(".,")
        limpio = crudo.replace(".", "").replace(",", "")
        if not limpio.lstrip("-").isdigit():
            continue
        salida.add(limpio.lstrip("0") or "0")
    return salida


def sospechas(respuesta: str, oraculo: set[str]) -> list[str]:
    """Qué señales de «el cero es del corrector» tiene esta respuesta. Puede haber varias."""
    if not oraculo:
        return []
    r = normalise(respuesta or "")
    if not r.strip():
        # UNA RESPUESTA VACIA NO ES SOSPECHOSA: es un cero legitimo, y confundirlos haria
        # que la auditoria denunciara al corrector por el unico caso en que tiene razon.
        return []
    marcas: list[str] = []
    ors = {normalise(o) for o in oraculo}
    if any(o and o in r for o in ors):
        # CONTENER EL ORACULO NO ALCANZA, y la primera version de esta auditoria gritaba
        # lobo por eso: `Tomas Peralta; Ignacio Juarez` contra oraculo `[Tomas Peralta]`
        # contiene el oraculo y su cero es CORRECTO — el brazo nombro a dos cuando se pedia
        # uno. Eso es sobre-responder, no un defecto del emparejamiento.
        #
        # La senal fuerte es contenerlo SIN sobrantes: ahi el dato pedido esta, no hay nada
        # de mas, y el cero solo puede venir de como se comparan las cadenas.
        sobrantes = [i for i in split_items(respuesta)
                     if not any(normalise(i) in o or o in normalise(i) for o in ors if o)]
        marcas.append("contiene_el_oraculo" if not sobrantes else "responde_de_mas")
    if len(ors) > 1:
        presentes = sum(1 for o in ors if o and o in r)
        if 0 < presentes < len(ors):
            marcas.append("parcial_no_creditado")
    if is_refusal(respuesta) and any(is_refusal(o) for o in oraculo):
        marcas.append("rechazo_no_reconocido")
    elif not is_refusal(respuesta) and any(is_refusal(o) for o in oraculo):
        # La verdad es un rechazo y la respuesta no lo parece — pero puede SER un rechazo
        # que el vocabulario no cubre. Se marca aparte, mas debil.
        if len(respuesta.strip()) < 120 and not _numeros(respuesta):
            marcas.append("posible_rechazo_no_cubierto")
    nums_o = set().union(*(_numeros(o) for o in oraculo)) if oraculo else set()
    if nums_o and nums_o & _numeros(respuesta) and "contiene_el_oraculo" not in marcas:
        marcas.append("numero_equivalente")
    return marcas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="gold_h1")
    ap.add_argument("--mostrar", type=int, default=12)
    args = ap.parse_args()

    tareas = {t["task_id"]: t for t in json.loads(
        (Path("corpus") / args.corpus / "tasks.json").read_text(encoding="utf-8"))}
    archivos = sorted(Path("results").glob(f"*/{args.corpus}_rows.jsonl"))
    if not archivos:
        raise SystemExit(f"sin registro para `{args.corpus}`")

    ceros = 0
    total = 0
    marcadas: list[tuple[str, str, str, str, list[str]]] = []
    por_marca: Counter[str] = Counter()
    por_celda: dict[str, Counter[str]] = defaultdict(Counter)

    for ruta in archivos:
        for f in load_rows(ruta):
            if f.get("infeasible"):
                continue
            total += 1
            if (f.get("utility") or 0.0) > 0.0:
                continue
            ceros += 1
            t = tareas.get(f["task_id"])
            if not t:
                continue
            marcas = sospechas(f.get("answer") or "", set(t.get("oracle") or []))
            if marcas:
                for m in marcas:
                    por_marca[m] += 1
                    por_celda[t["cell"]][m] += 1
                marcadas.append((ruta.parent.name, f["task_id"], f["paradigm"],
                                 (f.get("answer") or "")[:96], marcas))

    print("=" * 92)
    print(f"AUDITORIA DEL ORACULO — {args.corpus}")
    print("=" * 92)
    print(f"\n  {total:,} filas factibles · {ceros:,} con utilidad 0,0 "
          f"({ceros / max(total, 1):.0%})")
    # EL TITULAR SEPARA FUERTE DE DEBIL, y la primera version no lo hacia: sumaba las cuatro
    # senales y anunciaba «18 ceros son del corrector» cuando 14 de esas 18 eran
    # `responde_de_mas`, cuyo cero esta BIEN. Una auditoria que infla su propio hallazgo se
    # desactiva sola la segunda vez que alguien la corre.
    FUERTES = ("contiene_el_oraculo", "rechazo_no_reconocido", "parcial_no_creditado")
    fuertes = [m for m in marcadas if any(x in FUERTES for x in m[4])]
    print(f"  {len(fuertes)} con senal FUERTE de defecto del corrector "
          f"({len(fuertes) / max(ceros, 1):.1%} de los ceros)")
    print(f"  {len(marcadas) - len(fuertes)} con senal debil — casi siempre ceros")
    print(f"  correctos del brazo, se miran despues\n")

    if not marcadas:
        print("  >>> LIMPIO. Ningun cero levanta sospecha con estas cuatro pruebas.")
        print("      Eso NO prueba que el corrector este bien: prueba que estas cuatro")
        print("      pruebas no lo agarran. La de OpenAI fue a mano y encontro el 59,4%.")
        return

    print(f"  {'senal':<32}{'casos':>8}")
    for m, n in por_marca.most_common():
        print(f"  {m:<32}{n:>8}")

    print(f"\n  ── por celda, para ver si el defecto es de UNA forma de pregunta ─────────")
    for celda in sorted(por_celda, key=lambda c: -sum(por_celda[c].values())):
        detalle = ", ".join(f"{m}={n}" for m, n in por_celda[celda].most_common())
        print(f"  {celda:<34}{detalle}")

    print(f"\n  ── las {min(args.mostrar, len(marcadas))} primeras, para mirarlas a mano ──")
    # EL ORDEN ES POR FUERZA DE LA SENAL, y `responde_de_mas` va ULTIMO a proposito: casi
    # siempre su cero es correcto, y ponerlo arriba haria que la revision a mano empiece por
    # lo que menos importa.
    orden = {"contiene_el_oraculo": 0, "rechazo_no_reconocido": 1,
             "parcial_no_creditado": 2, "numero_equivalente": 3,
             "posible_rechazo_no_cubierto": 4, "responde_de_mas": 9}
    marcadas.sort(key=lambda x: min(orden.get(m, 9) for m in x[4]))
    for modelo, tid, p, ans, marcas in marcadas[:args.mostrar]:
        t = tareas[tid]
        print(f"\n  [{modelo}] {tid} · {p} · {t['cell']}")
        print(f"    oraculo:   {t.get('oracle')}")
        print(f"    respuesta: {ans!r}")
        print(f"    senales:   {', '.join(marcas)}")

    print(f"""
  ── QUE HACER CON ESTO ────────────────────────────────────────────────────────
  Una senal NO es un veredicto, y estan ordenadas por fuerza. `contiene_el_oraculo` —el
  dato pedido esta y no sobra nada— es casi siempre un defecto real del emparejamiento.
  `responde_de_mas` casi nunca lo es: el brazo nombro de mas y su cero esta bien.
  `numero_equivalente` puede ser el numero correcto en una frase equivocada. Se miran a mano, se arregla `verify.py` si corresponde, y se RE-PUNTUA con
  `bench/oneoff/_regrade_2026_08_30.py`, que recomputa desde las respuestas guardadas y no
  cuesta un token.

  Y la guarda de siempre: **ningun delta puede ser negativo**. Arreglar el corrector agrega
  credito; si le saca a alguien, el arreglo esta mal.
""")


if __name__ == "__main__":
    main()
