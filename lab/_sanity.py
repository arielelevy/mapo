"""Cotas que un numero derivado tiene que pasar ANTES de reportarse.

DE DONDE SALE. De cinco errores propios en un solo dia, y los cinco de la misma forma:
un numero derivado, plausible a la vista, reportado antes de chequear una cota que lo
refutaba — y en los cinco casos la cota estaba a una linea de distancia.

  «la declaracion de tools es el 43% del gasto de `rewoo`»
        refutable por: una declaracion NO PUEDE superar al prompt que la contiene.
        Real: 0%. La estimacion suponia que toda llamada lleva tools, y de 27 sitios
        que llaman al modelo, uno.

  «la brecha de oraculo cae a cero al descontar»
        refutable por: la utilidad esta ACOTADA. El calculo daba -463, y eso solo
        podia venir de un divisor aplastado por un recorte propio.

  «la senal de estancamiento no discrimina»
        refutable por: la clave estaba AUSENTE, no en cero. `.get(clave, 0)` vuelve
        indistinguible «se midio y dio cero» de «nunca se guardo», y son diagnosticos
        opuestos — uno cierra la linea, el otro dice que hay que instrumentar.

LO QUE ESTE MODULO NO ES. No es validacion de entrada ni manejo de errores. Es el
equivalente, para un numero, de lo que el verificador de corpus es para una tarea: una
segunda derivacion barata que se NIEGA cuando lo derivado no puede ser cierto.

POR QUE LEVANTA Y NO AVISA. Un aviso al lado de un numero imposible sigue publicando el
numero. Y el modo de falla que esto ataca no es que el calculo se caiga: es que
DEVUELVA ALGO PLAUSIBLE. Un error que rompe cuesta una corrida; uno que devuelve un
numero cuesta una conclusion, y no se sabe cual.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


class Impossible(ValueError):
    """Un valor derivado que no puede ser cierto, sea cual sea el dato."""


def share(part: float, whole: float, name: str) -> float:
    """`part/whole`, negandose si la parte supera al todo.

    La cota que habria atajado el 43%: una fraccion de algo no puede ser mayor que ese
    algo. Cuando lo es, el numerador y el denominador no miden lo mismo.
    """
    if whole <= 0:
        raise Impossible(
            f"{name}: el total es {whole}, asi que no hay fraccion que calcular. "
            f"Un 0 acá suele ser una columna que no se registro, no una medicion."
        )
    if part > whole:
        raise Impossible(
            f"{name}: la parte ({part:,.0f}) supera al todo ({whole:,.0f}). "
            f"No es un dato raro: es que numerador y denominador no miden lo mismo."
        )
    return part / whole


def bounded(value: float, lo: float, hi: float, name: str) -> float:
    """El valor, negandose si sale del rango que su definicion permite.

    La cota que habria atajado el -463: la utilidad vive en un rango conocido, asi que
    un valor afuera no es un hallazgo — es una division contra un piso aplastado.
    """
    if not lo <= value <= hi:
        raise Impossible(
            f"{name}: {value:,.4f} esta fuera de [{lo}, {hi}], que es lo que su "
            f"definicion permite. Un valor asi no es un hallazgo: es un calculo roto, "
            f"y lo mas comun es un divisor recortado a mano."
        )
    return value


def required(row: Mapping[str, Any], key: str, where: str) -> Any:
    """El valor, negandose si la clave no esta. AUSENTE NO ES CERO.

    La cota que habria atajado «la senal no discrimina». `.get(key, 0)` vuelve
    indistinguible «se midio y dio cero» de «nunca se guardo».
    """
    if key not in row:
        raise Impossible(
            f"{where}: falta `{key}`. Ausente NO es cero — «se midio y dio cero» y "
            f"«nunca se guardo» son diagnosticos opuestos: uno cierra la linea de "
            f"investigacion y el otro dice que hay que instrumentar."
        )
    return row[key]


def all_present(rows: Iterable[Mapping[str, Any]], key: str, where: str) -> list[Any]:
    """Los valores de `key` en todas las filas, o se niega nombrando cuantas faltan.

    Promediar sobre las filas que SI lo tienen es la version silenciosa del mismo
    error: el promedio sale, y no dice sobre que poblacion.
    """
    rows = list(rows)
    faltan = sum(1 for r in rows if key not in r)
    if faltan:
        raise Impossible(
            f"{where}: `{key}` falta en {faltan} de {len(rows)} filas. Promediar sobre "
            f"las que lo tienen daria un numero que no dice sobre que poblacion es."
        )
    return [r[key] for r in rows]


def paired(a: Mapping[Any, Any], b: Mapping[Any, Any], name: str) -> list[Any]:
    """Las claves comunes, negandose si la comparacion no es pareada de verdad.

    Una comparacion «pareada» sobre conjuntos distintos mide composicion y no efecto.
    Se exige que la interseccion no este vacia y se DECLARA cuanto se descarto.
    """
    comunes = sorted(set(a) & set(b))
    if not comunes:
        raise Impossible(
            f"{name}: los dos lados no comparten una sola clave. No hay comparacion "
            f"pareada que hacer, y una no pareada mide composicion, no efecto."
        )
    perdidas = (len(a) - len(comunes)) + (len(b) - len(comunes))
    if perdidas:
        print(f"  [aviso] {name}: {len(comunes)} claves pareadas, {perdidas} descartadas "
              f"por no estar en los dos lados.")
    return comunes
