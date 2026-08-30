"""Acuerdo entre una respuesta y un criterio: el verificador DEL PRODUCTO.

POR QUE EXISTE SEPARADO DEL BANCO. `serve.py` necesitaba un verificador para correr la
cascada —escalar ante una falla observada exige observar la falla— y lo tomaba de
`grading`, que es el modulo de MEDICION. Eso invertia la dependencia que ordena el repo:
**el banco importa al producto; el producto jamas sabe que el banco existe.**

Y no son el mismo concepto aunque hoy computen lo mismo. El del banco puntua paradigmas
contra el GOLD y tiene que quedar congelado para que el registro siga siendo comparable a
lo largo del tiempo. El del producto compara contra un criterio que **aporta el llamador**
y puede evolucionar con lo que un llamador sepa expresar. Dos razones distintas para
cambiar es la definicion de dos modulos.

La relocacion es PURA: el cuerpo se movio tal cual, sin tocar una linea de logica, porque
cambiar la puntuacion cambiaria la utilidad de cada fila del registro entero.
"""

from __future__ import annotations

import re
import unicodedata

_PUNCT = re.compile(r"[^\w\s]", flags=re.UNICODE)
_SPACE = re.compile(r"\s+")

# Leading articles and hedges a model may prepend to an otherwise correct item.
_STRIP_PREFIX = re.compile(r"^(the|a|an|el|la|los|las|un|una)\s+", flags=re.IGNORECASE)


def normalise(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = _PUNCT.sub(" ", text)
    text = _SPACE.sub(" ", text).strip().lower()
    return _STRIP_PREFIX.sub("", text)


def split_items(answer: str) -> set[str]:
    """Split a model answer into items.

    The answer contract asks for '; ' separation, but models drift to commas and
    newlines. Accepting all three is tolerance of format, not of content: a wrong
    item still scores zero. Being strict about separators would measure instruction
    following rather than control structure.
    """
    parts = re.split(r"[;\n]|,(?![^(]*\))", answer)
    items = {normalise(p) for p in parts if normalise(p)}
    return {i for i in items if i not in {"none", "nothing", "n a", "na"}}


EMPTY_ANSWERS = {"none", "nothing", "no one", "nobody", "n a", "na", "empty", "0 items"}

# UN RECHAZO ES UN VEREDICTO, NO UNA CADENA (2026-08-30)
#
# EL DEFECTO. Las tareas de `D1_presupposition` tienen la premisa FALSA —no hubo
# transferencia— y su oraculo es **una** redaccion del rechazo: `no transfer is recorded`.
# Medido sobre `d1-000-w4`, los NUEVE brazos contestaron correctamente y los nueve sacaron
# **0,00**:
#
#     "Not stated in the source documents"          "Not specified"
#     "The date cannot be determined from the..."   "Not stated"
#     "No date recorded in the available records"   "Cannot be determined from..."
#
# Ninguna contiene la cadena del oraculo, y hay infinitas formas correctas de rechazar una
# premisa. Se estaba puntuando la REDACCION de un rechazo con igualdad de strings, que es
# como pedirle a doce topologias que adivinen una frase.
#
# QUE TAN GRANDE ERA: 9 de las 78 tareas del corpus —las 4 medidas de `D1` y las 5 de
# `C9`— daban maximo 0,00 sobre TODO el plantel. Que doce topologias fallen las mismas
# nueve preguntas era mas consistente con un grader roto que con doce fracasos, y lo era.
#
# LA CONDICION SALE DEL ORACULO, NO DE UN FLAG. `score` solo ve `(answer, oracle)`, y esta
# bien que asi sea: si el permiso para aceptar un rechazo viniera de afuera, una tarea con
# oraculo de VALOR podria recibirlo por error y entonces "no se" puntuaria como la
# respuesta correcta. Aca la regla se auto-verifica — **solo si el oraculo mismo es un
# rechazo** se acepta otra forma de rechazar.
REFUSAL_MARKERS = (
    "no transfer", "not recorded", "no record", "not stated", "not specified",
    "not provided", "not found", "not available", "unavailable", "cannot be determined",
    "can not be determined", "unable to determine", "no date", "not mentioned",
    "not in the", "no evidence", "not documented", "does not appear",
    "no such", "did not", "never",
)

# Un año de cuatro digitos, una fecha numerica, o un mes con nombre. Es lo que la pregunta
# de `D1` PIDE, y por lo tanto lo que un rechazo no puede traer adentro.
_DATE_SHAPE = re.compile(
    r"\b(1[89]\d\d|20\d\d)\b"
    r"|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
    r"|\b(january|february|march|april|may|june|july|august|september|october"
    r"|november|december|enero|febrero|marzo|abril|mayo|junio|julio|agosto"
    r"|septiembre|octubre|noviembre|diciembre)\b",
    flags=re.IGNORECASE,
)


def is_refusal(text: str) -> bool:
    """Si el texto RECHAZA en vez de contestar. Vocabulario cerrado, no interpretacion.

    LAS DOS CONDICIONES, y la segunda es la que lo vuelve seguro: tiene que traer un marcador
    de rechazo **y no traer el dato que la premisa falsa pedia**. Sin la segunda, una
    respuesta como «no figura la fecha exacta, pero fue el 12 de marzo de 2024» contaria como
    rechazo — y esa respuesta ratifica la premisa, que es exactamente el modo de falla que
    `D1` existe para medir.

    Es la misma forma que `EMPTY_ANSWERS`: una categoria de respuesta reconocida por una
    lista cerrada, no un juez ni una similitud.
    """
    if not text or not text.strip():
        return False
    plano = normalise(text)
    if not any(m in plano for m in REFUSAL_MARKERS):
        return False
    # Un rechazo que igual entrega una fecha no es un rechazo: es una premisa ratificada
    # con un descargo adelante.
    return not _DATE_SHAPE.search(text)


def score(answer: str, oracle: list[str]) -> float:
    """Set F1 in [0, 1].

    An EMPTY oracle is a real and important question — "list every X" where no X
    exists — and it tests whether a paradigm invents items that are not there. It used
    to raise, which meant the exception was swallowed upstream and every paradigm
    scored zero on a task that several would have answered correctly.
    """
    # Only items with normalised CONTENT. An oracle of pure punctuation (";;;") used to
    # normalise to {""}, and the empty string is a substring of everything: every
    # single-item answer scored a perfect 1.0 against it. Now it is what it is -- an
    # empty oracle -- and takes the explicit-emptiness path below.
    truth = {n for n in (normalise(o) for o in oracle) if n}
    if not truth:
        stated = split_items(answer)
        explicit = {normalise(a) for a in EMPTY_ANSWERS}
        # Credit only an explicit statement of emptiness. Silence is not an answer:
        # a paradigm that returned nothing because it crashed must not score the same
        # as one that looked and reported finding nothing. `answer.strip()` is required
        # unconditionally — an earlier version short-circuited on the second clause and
        # handed an empty string full credit.
        return 1.0 if answer.strip() and stated <= explicit else 0.0

    # EL ORACULO ES UN RECHAZO -> se acepta CUALQUIER forma de rechazar. Ver
    # `REFUSAL_MARKERS`: puntuar la redaccion de un rechazo con igualdad de cadenas hacia
    # que las nueve respuestas correctas de `D1` sacaran cero. La condicion se lee del
    # oraculo, asi que una tarea con oraculo de VALOR no puede recibir este credito.
    if len(truth) == 1 and is_refusal(next(iter(truth))):
        return 1.0 if is_refusal(answer) else 0.0

    predicted = split_items(answer)
    if not predicted:
        return 0.0

    # A singleton oracle is a single-answer question. Requiring the prediction to be
    # that one item stops a paradigm from scoring by listing every candidate it saw,
    # which set F1 alone would partially reward.
    if len(truth) == 1:
        only = next(iter(truth))
        if predicted == {only}:
            return 1.0
        # Substring credit covers 'AR123' inside 'account AR123' without rewarding a
        # scattergun list: it applies only when the model committed to one item, and
        # only in that direction. The reverse test ('candidate in only') handed 1.0
        # to every prefix of the right answer — '4' scored perfect against '42'.
        if len(predicted) == 1:
            candidate = next(iter(predicted))
            return 1.0 if only in candidate else 0.0
        return 0.0

    # UNA RESPUESTA QUE EMPAREJA CLAVE Y VALOR NO ES UNA RESPUESTA EQUIVOCADA (2026-08-30)
    #
    # EL DEFECTO. `C9_declared_roster` pregunta *«para cada uno de estos individuos, reporta
    # la cuenta»*, y el oraculo son las cuatro cuentas sueltas. Los brazos contestaron
    #
    #     Marta Arrieta - AR9263415718; Ignacio Ybarra - AR6534161716; ...
    #
    # con **las cuatro cuentas correctas**, y sacaron 0,00 en las cinco tareas medidas: la
    # interseccion de conjuntos no cruza `ar9263415718` con `marta arrieta ar9263415718`.
    # **La pregunta pide el emparejamiento y el grader lo prohibia.**
    #
    # El credito por substring ya existia y estaba limitado a los oraculos de UN item. Acá
    # se extiende a los enumerativos con las dos guardas que lo mantienen honesto:
    #
    #   uno a uno       cada item predicho absorbe a lo sumo UN item del oraculo, asi que
    #                   una respuesta que enumera todo no cosecha varios aciertos con un
    #                   solo item
    #   frontera        la contencion tiene que caer en frontera de palabra, o `AR123`
    #                   acertaria adentro de `AR1234` — es la misma trampa que el comentario
    #                   de arriba ya nombra para el caso singleton («4» contra «42»)
    #
    # Y la PRECISION sigue castigando el exceso: el denominador es `len(predicted)`, asi que
    # contestar de mas baja el F1 igual que antes.
    exactos = truth & predicted
    libres = predicted - exactos
    emparejados = set()
    for objetivo in sorted(truth - exactos):
        for cand in sorted(libres):
            if cand in emparejados:
                continue
            if re.search(rf"(?<![0-9a-z]){re.escape(objetivo)}(?![0-9a-z])", cand):
                emparejados.add(cand)
                exactos.add(objetivo)
                break
    hits = len(exactos)
    if hits == 0:
        return 0.0
    precision = hits / len(predicted)
    recall = hits / len(truth)
    return 2 * precision * recall / (precision + recall)
