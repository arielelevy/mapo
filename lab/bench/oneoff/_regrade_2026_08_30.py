"""Re-puntúa el registro tras el arreglo del grader del 2026-08-30. CERO llamadas al modelo.

QUÉ SE ARREGLÓ, y por qué había que re-puntuar en vez de re-correr. Dos defectos del grader
hacían que **9 de las 78 tareas dieran 0,00 sobre todo el plantel**:

  `D1_presupposition`   el oráculo es `'no transfer is recorded'` —UNA redacción de un
                        rechazo— y se comparaba por igualdad de cadenas. Los nueve brazos
                        contestaron bien («Not stated in the source documents», «The date
                        cannot be determined…») y los nueve sacaron cero
  `C9_declared_roster`  la pregunta pide *«para cada individuo, reportá la cuenta»*, el
                        oráculo son las cuatro cuentas sueltas, y las respuestas traían las
                        cuatro correctas **emparejadas con su nombre**. La intersección de
                        conjuntos no cruza `ar9263415718` con `marta arrieta ar9263415718`

**Las respuestas están guardadas en las filas**, así que corregir no cuesta un token: se
recomputa `utility` desde el `answer` almacenado contra el oráculo del corpus. Es el mismo
procedimiento que `_fix_grading_regrade.py` ya estableció para el arreglo del substring
bidireccional.

QUÉ NO TOCA: las filas `infeasible` e `infra_error`. Su 0,0 no viene del grader, y
recomputarlo las convertiría en mediciones.

QUÉ ESPERABA DEL DELTA, Y EN QUÉ ME EQUIVOQUÉ. Predije que el defecto deprimía a *todos los
brazos por igual* y que por lo tanto el ORDEN casi no se movería. **Falso**: 12 de 15 brazos
cambian de puesto.

La razón se ve en cuanto se mira el delta por brazo, y en retrospectiva era obvia — **la
corrección sólo puede tocar a quien CORRIÓ las tareas afectadas**:

    handoff  +0,138 · pointer_chase +0,128 · supervisor +0,116 · reflection +0,099
    cot      +0,000 · direct        +0,000 · streaming_scan +0,000 · map_reduce +0,000

Los que suben cero no es que hayan resistido: es que la factibilidad los podó de `C9` y `D1`,
o corrieron muy pocas. **Un defecto uniforme sobre las TAREAS no es uniforme sobre los
BRAZOS**, porque los brazos no corren el mismo conjunto de tareas — la factibilidad decide
eso antes. Es la misma confusión entre numerador y denominador que la lección 8.16 ya nombra.

Lo que sí se sostuvo: **ningún delta es negativo** —el cambio agrega crédito y no saca
ninguno— y las tres familias que se mueven son exactamente las predichas (`c9` +0,825,
`d1` +1,000, `c2` +0,044).

Corre DESDE `lab/`:  py bench/oneoff/_regrade_2026_08_30.py [--escribir]
"""

from __future__ import annotations

import collections
import json
import shutil
import sys as _sys
import time
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.grading import score
from app.verify import EMPTY_ANSWERS, normalise, split_items

STAMP = time.strftime("%Y%m%d-%H%M%S")


def score_previo(answer: str, oracle: list[str]) -> float:
    """El grader SIN los dos caminos de crédito nuevos. Es la referencia de la guarda.

    POR QUÉ HACE FALTA UNA RÉPLICA Y NO ALCANZA EL VALOR GUARDADO. La primera versión de
    la guarda comparaba contra `utility` de la fila, y abortó en
    `gold_p16 / c2-001-w48 / rewoo`, que **baja** de 0,875 a 0,824. Investigado: no es
    contaminación de corpus — el oráculo son 7 nombres, los aciertos son los mismos, y lo
    que cambió es `len(predicted)`, o sea el SPLIT. **El registro abarca varias versiones
    del grader**, así que el valor guardado no dice qué habría dado el grader de ayer.

        Comparar contra un número que produjo otro programa no prueba nada sobre este
        cambio. La única referencia honesta es el mismo programa sin el cambio.

    Esto replica exactamente el camino viejo —intersección de conjuntos, sin crédito por
    rechazo y sin emparejamiento clave-valor— y la guarda exige `nuevo >= previo` fila por
    fila. Eso SÍ es una propiedad del cambio: agrega caminos de crédito y no saca ninguno,
    así que ninguna fila puede bajar. Si alguna baja, el cambio hace algo que no dice.
    """
    truth = {n for n in (normalise(o) for o in oracle) if n}
    if not truth:
        stated = split_items(answer)
        explicit = {normalise(a) for a in EMPTY_ANSWERS}
        return 1.0 if answer.strip() and stated <= explicit else 0.0
    predicted = split_items(answer)
    if not predicted:
        return 0.0
    if len(truth) == 1:
        only = next(iter(truth))
        if predicted == {only}:
            return 1.0
        if len(predicted) == 1:
            return 1.0 if only in next(iter(predicted)) else 0.0
        return 0.0
    hits = len(truth & predicted)
    if hits == 0:
        return 0.0
    precision = hits / len(predicted)
    recall = hits / len(truth)
    return 2 * precision * recall / (precision + recall)


def main() -> None:
    escribir = "--escribir" in sys.argv

    # EL ORACULO SE INDEXA POR (CORPUS, TAREA), Y ESO NO ES UN DETALLE.
    #
    # La primera version de este script indexaba solo por `task_id` con `setdefault` sobre
    # `corpus/*/tasks.json`. **El mismo `task_id` existe en varios corpus con oraculos
    # DISTINTOS** —`c1-000` esta en `gold_v2`, `gold_wide`, `gold_deep`, `gold_h1`…— asi que
    # se quedaba con el primero que encontrara y corregia filas de un corpus contra el
    # oraculo de otro.
    #
    # El ensayo lo delato en un renglon: **1.758 filas cambiando, con deltas de -1,000** en
    # `c1`, `c3`, `c5` y `c8`, y los 15 brazos cambiando de puesto —`cot` de 0,970 a 0,167—.
    # El arreglo del grader solo puede SUBIR puntajes, porque agrega caminos de credito y no
    # saca ninguno. Un delta negativo era imposible, y por eso se vio.
    #
    #     Es la misma trampa que el repo ya nombra en otro lado: **un `.jsonl` no declara de
    #     que corpus salio**. Aca la declara el nombre del archivo, y hay que usarla.
    por_corpus: dict[str, dict[str, list[str]]] = {}
    for tareas in _Path("corpus").glob("*/tasks.json"):
        por_corpus[tareas.parent.name] = {
            t["task_id"]: t["oracle"]
            for t in json.loads(tareas.read_text(encoding="utf-8"))
        }

    def corpus_de(archivo: _Path) -> str | None:
        """El corpus al que pertenece un archivo de filas, por el prefijo de su nombre.

        `gold_h1_rows.jsonl` -> `gold_h1`; `gold_p17_stop3_rows.jsonl` -> `gold_p17`. Se
        elige el nombre de corpus MAS LARGO que sea prefijo, o `gold_p17` se comeria a
        `gold_p17b`.
        """
        base = archivo.name[: -len("_rows.jsonl")]
        candidatos = [c for c in por_corpus if base == c or base.startswith(c + "_")]
        return max(candidatos, key=len) if candidatos else None

    archivos = sorted(_Path("results").rglob("*_rows.jsonl"))
    cambios: list[tuple[str, str, float, float]] = []
    por_brazo_antes = collections.defaultdict(list)
    por_brazo_despues = collections.defaultdict(list)
    sin_oraculo = 0
    tocados = 0

    deriva: list[tuple[str, str, str, float, float]] = []
    sin_corpus: list[str] = []
    for archivo in archivos:
        corpus = corpus_de(archivo)
        if corpus is None:
            # FALLA CERRADA: un archivo cuyo corpus no se puede identificar NO se corrige
            # a las adivinanzas. Se nombra y se saltea.
            sin_corpus.append(archivo.name)
            continue
        oraculos = por_corpus[corpus]
        lineas = [l for l in archivo.read_text(encoding="utf-8").splitlines() if l.strip()]
        filas = [json.loads(l) for l in lineas]
        cambio_en_archivo = False
        for f in filas:
            if f.get("infeasible") or f.get("infra_error"):
                continue
            oracle = oraculos.get(f["task_id"])
            if oracle is None:
                sin_oraculo += 1
                continue
            antes = f.get("utility")
            despues = score(f.get("answer") or "", oracle)
            por_brazo_antes[f["paradigm"]].append(antes or 0.0)
            por_brazo_despues[f["paradigm"]].append(despues)
            # LA GUARDA, CONTRA EL GRADER VIEJO RECOMPUTADO Y NO CONTRA EL VALOR
            # GUARDADO. El cambio solo AGREGA caminos de credito, asi que ninguna fila
            # puede bajar respecto del mismo programa sin el cambio. Esa es una propiedad
            # del cambio y se puede exigir; «no bajar respecto de lo guardado» no lo es,
            # porque el registro abarca varias versiones del grader.
            previo = score_previo(f.get("answer") or "", oracle)
            if despues < previo - 1e-9:
                raise SystemExit(
                    f"{archivo.name}: {f['task_id']}/{f['paradigm']} baja de {previo:.3f} "
                    f"(grader viejo) a {despues:.3f}. El cambio solo puede subir: esto es "
                    f"un defecto del cambio, no una re-puntuacion."
                )
            # LA DERIVA CONTRA LO GUARDADO SE CUENTA, no se aborta ni se ignora. Una fila
            # cuyo valor guardado no coincide con el grader viejo la puntuo OTRA version
            # del grader; es informacion sobre el registro, no sobre este cambio.
            if antes is not None and abs(antes - previo) > 1e-9:
                deriva.append((archivo.name, f["task_id"], f["paradigm"], antes, previo))
            if antes is None or abs(antes - despues) > 1e-9:
                cambios.append((f["task_id"], f["paradigm"], antes or 0.0, despues))
                f["utility"] = despues
                cambio_en_archivo = True
                tocados += 1
        if cambio_en_archivo and escribir:
            shutil.copy2(archivo, archivo.with_suffix(f".jsonl.bak-{STAMP}"))
            archivo.write_text(
                "\n".join(json.dumps(f, ensure_ascii=False) for f in filas) + "\n",
                encoding="utf-8",
            )

    print("=" * 92)
    print(f"RE-PUNTUACION {'ESCRITA' if escribir else '(ENSAYO — no escribe nada)'}")
    print("=" * 92)
    if sin_corpus:
        print(f"\n  !! {len(sin_corpus)} archivos SIN corpus identificable, no se tocan: "
              f"{sorted(sin_corpus)[:4]}")
    print(f"\n  {len(archivos)} archivos · {tocados} filas cambian"
          f"{f' · {sin_oraculo} sin oraculo en el corpus (se saltean)' if sin_oraculo else ''}")

    if deriva:
        peor = max(deriva, key=lambda d: abs(d[3] - d[4]))
        print(f"\n  DERIVA DE GRADER: {len(deriva)} filas cuyo `utility` guardado no lo "
              f"produjo el grader inmediatamente anterior.")
        print(f"  No es este cambio — el registro abarca varias versiones. La peor: "
              f"{peor[1]}/{peor[2]} en {peor[0]}, guardado {peor[3]:.3f} contra "
              f"{peor[4]:.3f} del grader viejo.")

    por_celda = collections.Counter()
    for tid, _, a, d in cambios:
        por_celda[tid.split("-")[0]] += 1
    print(f"\n  filas que cambian, por familia de tarea:")
    for celda, n in por_celda.most_common():
        subida = [d - a for tid, _, a, d in cambios if tid.startswith(celda + "-")]
        print(f"    {celda:8s} {n:5d} filas · delta medio {sum(subida)/len(subida):+.3f}")

    print(f"\n  {'brazo':16s} {'antes':>7s} {'despues':>8s} {'delta':>7s}   "
          f"{'orden antes':>11s} {'orden despues':>13s}")
    orden_antes = sorted(por_brazo_antes,
                         key=lambda p: -sum(por_brazo_antes[p]) / len(por_brazo_antes[p]))
    orden_despues = sorted(por_brazo_despues,
                           key=lambda p: -sum(por_brazo_despues[p]) / len(por_brazo_despues[p]))
    for p in orden_despues:
        a = sum(por_brazo_antes[p]) / len(por_brazo_antes[p])
        d = sum(por_brazo_despues[p]) / len(por_brazo_despues[p])
        print(f"  {p:16s} {a:7.3f} {d:8.3f} {d - a:+7.3f}   "
              f"{orden_antes.index(p) + 1:11d} {orden_despues.index(p) + 1:13d}")

    movidos = sum(1 for i, p in enumerate(orden_despues) if orden_antes.index(p) != i)
    # LA PROSA TIENE QUE SEGUIR AL NUMERO, y esta no lo hacia: el texto afirmaba «y NO es lo
    # que yo esperaba» pasara lo que pasara, asi que en la segunda pasada —la de los
    # marcadores de rechazo, donde no se movio nadie— imprimia «0 de 15 cambian de puesto, y
    # NO es lo que esperaba» contra su propio docstring, que decia que esperaba justo eso.
    # Una conclusion cableada dentro de un script de medicion es una afirmacion sin medida.
    print(f"\n  {movidos} de {len(orden_despues)} brazos cambian de puesto.")
    if movidos:
        print("  La correccion solo puede tocar a quien CORRIO las tareas afectadas, y la")
        print("  factibilidad poda a unos brazos de esas celdas y a otros no: un defecto")
        print("  uniforme sobre las TAREAS no es uniforme sobre los BRAZOS.")
    else:
        print("  El arreglo agrega credito en pocas filas y a brazos que ya estaban")
        print("  separados por mas que el delta, asi que el orden aguanta. Eso NO dice que")
        print("  el arreglo sea menor: dice que su efecto no alcanza a cruzar dos brazos.")
    def _media(d, p):
        return sum(d[p]) / len(d[p])

    negativos = [p for p in orden_despues
                 if _media(por_brazo_despues, p) < _media(por_brazo_antes, p) - 1e-9]
    print(f"  Deltas negativos: {negativos or 'ninguno'}"
          + ("" if not negativos else "   <-- REVISAR: el arreglo no deberia sacar credito"))

    if not escribir:
        print("\n  Nada se escribio. Para aplicar:  py bench/oneoff/_regrade_2026_08_30.py "
              "--escribir")


if __name__ == "__main__":
    main()
