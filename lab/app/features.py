"""Structural feature extraction (the vector phi).

The central design decision of this module is the split between COMPUTABLE and
DERIVED features.

- COMPUTABLE features are pure functions of the task payload. Same task, same value,
  forever, with no model in the loop.
- DERIVED features need a language model to estimate. They are useful but they are
  *not* replayable from first principles, only from cache.

That split is what makes regulated operation possible. In deterministic mode D2 the
router may read COMPUTABLE features only; a policy rule that needs a DERIVED feature
cannot fire, so confidence is capped and the router abstains to the fallback paradigm.

Determinism and abstention therefore stop being two separate requirements and become
one mechanism: whatever cannot be established deterministically is routed to the safe
default rather than guessed at.

Deliberately NOT here: lexical triggers. Conditioning on surface forms like
"how many" or "extract all" is what produced the false-positive rate that made the
prose-prompt routers lose. Cardinality is counted, never inferred from phrasing.
"""

from __future__ import annotations

import json
import re

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any

from .llm import LLMClient, Usage


class Availability(str, Enum):
    """CUÁNDO se conoce un feature, y por eso si puede o no gobernar una decisión.

    ES UN TIPO Y NO UNA CONVENCIÓN, y esa es la razón de que exista. Una regla sólo puede
    gobernar si se la puede **evaluar al momento de decidir**; partir el espacio sobre algo
    que recién se sabe después de ejecutar descubre una regla verdadera e **inaplicable**.

      `COMPUTABLE`  se saca del request antes de gastar: cantidad de unidades, largo,
                    presupuesto, las banderas que declara el caller
      `DERIVED`     necesita el material o la ejecución. `truth_coupling` es el oráculo
                    del extractor; `iterations` y `cost_tokens` son posteriores

    El descubrimiento de particiones consulta esto y descarta los ejes `DERIVED`. Sin el
    tipo, eso se descubriría recién al cablear la regla y ver que no hay con qué evaluarla.
    """

    COMPUTABLE = "computable"
    DERIVED = "derived"


FEATURE_AVAILABILITY: dict[str, Availability] = {
    "n_units": Availability.COMPUTABLE,
    "has_oracle": Availability.COMPUTABLE,
    "irreversible": Availability.COMPUTABLE,
    "shared_writes": Availability.COMPUTABLE,
    "budget_tokens": Availability.COMPUTABLE,
    "coupling": Availability.DERIVED,
    "horizon_unknown": Availability.DERIVED,
    # FALTABA, y el docstring de arriba dice que el descubrimiento de particiones consulta
    # este mapa para descartar los ejes `DERIVED`. Un campo que no está clasificado no es
    # ninguna de las dos cosas: se cae del filtro en silencio. `continuation` se mide con
    # aritmética sobre el material declarado —recurrencia literal de una forma de token
    # cerrada— así que es COMPUTABLE, la misma clase que contar unidades.
    "continuation": Availability.COMPUTABLE,
    # LOS DOS PREDICTORES MEDIDOS (CP-6, 2026-08-30). `cardinality` la DECLARA el caller, no
    # se infiere del fraseo — que es la regla que este módulo se impuso en su primera línea.
    # `literal` se cuenta sobre el material, igual que `continuation`.
    "cardinality": Availability.COMPUTABLE,
    "literal": Availability.COMPUTABLE,
}

# QUIEN PUEDE ESTABLECER CADA EJE QUE PUEDE FALTAR (EP-3, 2026-08-30)
#
# `Availability` dice CUÁNDO se conoce un feature. Faltaba la otra mitad: **quién lo puede
# ir a buscar si no se conoce**. Sin eso, `missing()` mezcla dos cosas que piden decisiones
# opuestas:
#
#     «no lo sé, y puedo averiguarlo»   -> sondear, y decidir después
#     «no lo sé, y nadie puede»         -> decidir con lo que hay, o abstenerse por eso
#
# Y MEZCLARLAS TIENE UN COSTO MEDIBLE, no es prolijidad. Un eje `DERIVED` sin establecer
# **acota la confianza y empuja al router al fallback**. O sea que un eje que nadie puede
# llenar hace abstenerse al motor **para siempre y sin motivo**.
#
# EL CASO QUE LO DESTAPÓ: `horizon_unknown`. Auditado, hay cinco razones independientes
# para que no sea un feature:
#
#   1. ninguna regla lo requiere — `rules.py` lo ASIENTA y nadie lo lee
#   2. no entra en el vocabulario de región, ni en el anterior ni en el actual
#   3. la sonda no lo mide: `probe.py` establece `coupling` y nada más
#   4. es CONSTANTE en el registro: `False` en las 3.884 filas que lo llevan
#   5. y el docstring de `Row` afirma que está en `True` en las 78 tareas — o sea que la
#      única descripción que existe de este eje dice **lo contrario** del registro
#
# No se saca: la plomería se conserva para poder releer las filas que lo llevan estampado y
# porque un corpus futuro podría hacerlo variar. Lo que se saca es la MENTIRA de que sea un
# hueco que el sistema puede cerrar.
FEATURE_SENSOR: dict[str, str | None] = {
    "coupling": "probe.probe_coupling",
    # Sin sensor, y por eso no cuenta como hueco cerrable. Darle uno o sacarlo es una
    # decisión abierta (`EP-3`); mientras tanto, que no haga abstenerse por nada.
    "horizon_unknown": None,
}

COMPUTABLE_FEATURES = tuple(
    name for name, a in FEATURE_AVAILABILITY.items() if a is Availability.COMPUTABLE
)
DERIVED_FEATURES = tuple(
    name for name, a in FEATURE_AVAILABILITY.items() if a is Availability.DERIVED
)


# Version of the region vocabulary. Bumped when an axis is added or a bucket changes:
# a theta fitted under one vocabulary must never consume regions from another, and the
# EXPLAIN records which one the decision spoke.
REGION_VOCABULARY = "regions/3-literal"

# EL VOCABULARIO ANTERIOR, CONSERVADO. No es nostalgia: 5.932 filas del registro llevan
# `region_vocabulary = "regions/2-continuation"` estampado, y `load_rows` levanta si un
# archivo mezcla dos. Poder recomputar la región vieja es lo que permite leer ese registro
# sin re-correrlo — borrar la función lo volvería irreproducible.
REGION_VOCABULARY_PREVIO = "regions/2-continuation"


def measure_continuation(
    documents: dict[str, str], unit_ids: list[str]
) -> bool | None:
    """Does any identifier-like literal recur across DISTINCT units of this task?

    Pure arithmetic over the declared material — the same epistemic class as counting
    units. The token vocabulary is TYPED and closed: account-style identifiers
    (letters+digits, e.g. AR9911) and unit-style identifiers (word-digits, e.g.
    memo-014). This is not prose parsing: it is literal recurrence of a closed token
    shape, verified by containment.

    A key that appears in (almost) every unit is boilerplate, not a chain: recurrence
    counts only between 2 units and half the scope. Returns None when the material is
    not available to measure — absence of measurement, never a negative.
    """
    ids = [u for u in unit_ids if u in documents]
    if len(ids) < 2:
        return False if ids else None

    token_shape = re.compile(r"\b[A-Z]{2,}\d{2,}\b|\b[a-z]+-\d{2,}\b")
    seen: dict[str, set[str]] = {}
    for unit_id in ids:
        for token in set(token_shape.findall(documents[unit_id])):
            if token == unit_id:
                continue  # a unit naming itself is identity, not continuation
            seen.setdefault(token, set()).add(unit_id)

    ceiling = max(2, len(ids) // 2)
    return any(2 <= len(units) <= ceiling for units in seen.values())


# LA FORMA DE UN LITERAL CITADO EN LA PREGUNTA. Cerrada y tipada, igual que la de
# `measure_continuation`: comillas simples o dobles, o un identificador de cuenta.
_LITERAL_SHAPE = re.compile(r"'([^']{3,40})'|\"([^\"]{3,40})\"|\b([A-Z]{2,}\d{4,})\b")


def measure_question_literal(
    question: str,
    documents: dict[str, str],
    unit_ids: list[str],
    cardinality: str | None = None,
) -> str | None:
    """¿El literal que la pregunta CITA aparece verbatim en el material? Aritmética pura.

    QUÉ LO SEPARA DE UN DISPARADOR LÉXICO, que este módulo prohíbe en su primera línea.
    Un disparador léxico infiere el TIPO de tarea de la forma de la pregunta —«dice
    *how many*, entonces es un conteo»— y ésa es la falla que hizo perder a los routers en
    prosa. Esto no infiere nada de la pregunta: extrae de ella una **cadena entrecomillada**
    y devuelve un hecho **sobre el material**, que es en cuántas unidades aparece. El valor
    de la feature no lo decide el fraseo; lo decide el corpus.

        prohibido   «la pregunta dice X» -> «la tarea es de tipo Y»
        esto        «la pregunta cita X» -> «X está / no está en el material»

    Es la misma clase epistémica que `measure_continuation`: recurrencia literal de una
    forma de token cerrada, verificada por contención, sin modelo en el medio.

    POR QUÉ EXISTE (CP-6). Es el predictor más fuerte que se midió, y no existía. Con la
    política de desempate por costo evaluada leave-one-out, `cardinalidad × literal` da
    **69% de ahorro** con la utilidad dentro del ruido, contra 37% del vocabulario de
    región anterior. La razón mecánica: cuando el término existe verbatim, **el plan
    completo se puede escribir antes de ver un resultado**, y ahí un brazo de dos llamadas
    domina a uno de veinte.

    UNA PREGUNTA BOOLEANA CITA SUS OPCIONES, NO UN TÉRMINO DE BÚSQUEDA (2026-08-30).
    Es un defecto que tuvo esta función desde que se escribió, y lo destapó medir la regla
    que habilita (`EP-5`), no leerla.

    `C7_irreversible` pregunta *«…Answer 'escalate' or 'no escalation'»* y `W1_shared_writes`
    *«…Answer 'safe to write' or 'conflict'»*. Esos literales **no están en el material por
    construcción** —son el vocabulario de la respuesta— así que la función devolvía
    `lit_absent` en las 8 tareas booleanas del panel y decía, sobre el material, algo que en
    realidad era sobre el FORMATO de la pregunta.

        buscado    «la cadena que hay que buscar no está en el corpus»  -> sobre el MATERIAL
        medido     «la pregunta enumera sus opciones»                   -> sobre la PREGUNTA

    Medido: como detector de ausencia daba **precisión 50% y recall 50%**, y sus 8 aciertos
    aparentes eran las booleanas, ni una de `B2_absence`.

    LA GUARDA USA LO QUE EL CALLER DECLARA, no el fraseo. `answer_cardinality == "boolean"`
    dice que la respuesta sale de un conjunto enumerado, o sea que lo entrecomillado son
    opciones. Distinguirlas mirando cómo está redactada la pregunta sería exactamente el
    disparador léxico que este módulo prohíbe en su primera línea; recibirlo del caller es
    lo que ya se hace con `irreversible` y `shared_writes`.

    Devuelve `None` cuando no hay material con qué medir — ausencia de medición, jamás un
    negativo.
    """
    presentes = [u for u in unit_ids if u in documents]
    if not presentes:
        return None
    if cardinality == "boolean":
        # Lo entrecomillado son las opciones de respuesta. No hay término que buscar, y
        # decir `lit_absent` sería afirmar algo sobre el material a partir del formato.
        return "no_lit"
    candidatos = [
        next(g for g in m if g) for m in _LITERAL_SHAPE.findall(question or "")
    ]
    if not candidatos:
        return "no_lit"
    cuerpo = " ".join(documents[u] for u in presentes).lower()
    hallados = sum(1 for c in candidatos if c.lower() in cuerpo)
    if hallados == len(candidatos):
        return "lit_present"
    return "lit_absent" if hallados == 0 else "lit_partial"


@dataclass(frozen=True)
class Features:
    """El vector φ: TODO lo que la capa de decisión sabe de un request antes de gastar.

    ES LA FRONTERA DE LO DECIDIBLE. Una regla sólo puede gobernar sobre lo que está acá, y
    por eso agregar un campo no es agregar un dato: es ampliar lo que el motor puede
    decidir, y quitarlo es reducirlo. De ahí que cada campo declare **cuándo se conoce**
    (`FEATURE_AVAILABILITY`) y no sólo qué tipo tiene.

    `None` SIGNIFICA «NO ESTABLECIDO», JAMÁS UN CERO. Es la invariante que sostiene todo lo
    demás: un consumidor que lea `None` como `False` o como `0` convierte la ausencia de
    conocimiento en conocimiento negativo, que es la forma más silenciosa de mentir. Por eso
    `region()` escribe `?` y no un valor benigno, y por eso `missing()` existe.

    LOS TRES GRUPOS, y la diferencia entre ellos es epistémica, no de implementación:

      **COMPUTABLE del payload**   `n_units`, `has_oracle`, `irreversible`,
                                   `shared_writes`, `budget_tokens`. Funciones puras de lo
                                   que el caller declara. Mismo request, mismo valor, para
                                   siempre, sin modelo en el medio.

      **COMPUTABLE del material**  `continuation`, `literal`. Aritmética sobre los
                                   documentos declarados —recurrencia literal de formas de
                                   token cerradas, verificada por contención—. Cuestan cero
                                   y son deterministas, pero necesitan el material, y por
                                   eso los mide el runner y no el extractor.

      **DERIVED**                  `coupling`, `horizon_unknown`. Necesitan un modelo. Son
                                   útiles y **no son replayables desde primeros
                                   principios**, sólo desde caché. En modo determinista D2
                                   la proyección los borra, la confianza se acota y el
                                   router se abstiene al fallback. Determinismo y abstención
                                   dejan de ser dos requisitos y pasan a ser un mecanismo.

    LO QUE DELIBERADAMENTE NO ESTÁ: disparadores léxicos. Condicionar sobre formas de
    superficie —«dice *how many*, entonces es un conteo»— es lo que produjo la tasa de
    falsos positivos que hizo perder a los routers en prosa. **La cardinalidad se declara,
    nunca se infiere del fraseo**, y `literal` no es una excepción: extrae de la pregunta una
    cadena entrecomillada y devuelve un hecho **sobre el material** —en cuántas unidades
    aparece—, no una interpretación de la pregunta.

    Y LA REGIÓN NO ES UN CAMPO: es la CLAVE con la que se aprende, derivada de estos campos
    por `region()`. Su vocabulario está versionado porque una política ajustada bajo uno no
    puede consumir regiones de otro — `load_rows` levanta si un archivo los mezcla, y el
    EXPLAIN registra cuál habló la decisión.
    """

    # -- computable --------------------------------------------------------
    n_units: int
    has_oracle: bool
    irreversible: bool
    shared_writes: bool
    budget_tokens: int

    # -- derived -----------------------------------------------------------
    coupling: float | None = None
    horizon_unknown: bool | None = None

    # -- computed from the material, when the material is available ---------
    # Whether an identifier literally RECURS across distinct units: the observable
    # stand-in for "this material is chained" (PATRON_REC §5). None means the
    # documents were not available to measure — never that the answer is no. This is
    # the axis P15 showed missing: C5 fell into the same regions as C2/C4 because
    # nothing in φ could tell chained material from independent material.
    continuation: bool | None = None

    # LOS DOS PREDICTORES DE `CP-6`, y los dos son COMPUTABLE.
    #
    # `cardinality` la DECLARA el caller —`singular`, `enumerative`, `boolean`,
    # `aggregate`— y por eso no viola la regla de la primera línea del módulo: no se
    # infiere del fraseo, se recibe. Sola no separa nada (`p = 0,372` contra su nulo);
    # multiplicada por `literal` es el mejor vocabulario medido.
    #
    # `literal` sale de `measure_question_literal`: en cuántas unidades aparece el literal
    # que la pregunta cita. Es el predictor más fuerte por sí solo.
    cardinality: str | None = None
    literal: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def computable_only(self) -> "Features":
        """Projection onto the deterministic subspace (mode D2)."""
        return Features(
            n_units=self.n_units,
            has_oracle=self.has_oracle,
            irreversible=self.irreversible,
            shared_writes=self.shared_writes,
            budget_tokens=self.budget_tokens,
            coupling=None,
            horizon_unknown=None,
            # SOBREVIVEN A LA PROYECCION D2, y ése es medio motivo de haberlos elegido: son
            # COMPUTABLE, así que una regla que los use **sí puede disparar** en modo
            # determinista. El vocabulario anterior dependía de `coupling`, que es DERIVED,
            # y en D2 colapsaba a `unknown` — o sea que la región que gobierna en regulado
            # no era la que se aprendió.
            continuation=self.continuation,
            cardinality=self.cardinality,
            literal=self.literal,
        )

    def missing(self) -> tuple[str, ...]:
        """Los ejes `DERIVED` sin establecer. **Todos**, se puedan llenar o no."""
        return tuple(
            name for name in DERIVED_FEATURES if getattr(self, name) is None
        )

    def fillable_gaps(self) -> tuple[str, ...]:
        """Lo que falta **y se puede ir a buscar**. Es lo que dispara una sonda.

        LA DISTINCIÓN QUE ESTO INTRODUCE, y no es de estilo: «no lo sé y puedo
        averiguarlo» y «no lo sé y nadie puede» piden decisiones **opuestas**. La primera
        dice *sondeá*; la segunda dice *decidí con lo que hay, o abstenete por eso* — pero
        sondear no la va a cerrar nunca.

        Mezclarlas cuesta: un eje `DERIVED` sin establecer acota la confianza y empuja al
        fallback, así que un eje que **nadie** puede llenar hace abstenerse al motor para
        siempre y sin motivo. Medido, `horizon_unknown` es exactamente eso: sin sensor, sin
        regla que lo lea, fuera de la región, y constante en las 3.884 filas que lo llevan.
        """
        return tuple(n for n in self.missing() if FEATURE_SENSOR.get(n))

    def permanent_gaps(self) -> tuple[str, ...]:
        """Lo que falta y **ningún sensor puede establecer**. Informa, no dispara nada."""
        return tuple(n for n in self.missing() if not FEATURE_SENSOR.get(n))

    def region(self) -> str:
        """La región discreta: la clave con la que se aprende. **Medida, no elegida.**

        POR QUÉ CAMBIÓ (`CP-6`, 2026-08-30). El vocabulario anterior —`cardinalidad de
        unidades / oráculo / acoplamiento / cadena`— se eligió por diseño y nunca se
        contrastó contra alternativas. Contrastado con la política de desempate por costo
        evaluada **leave-one-out**, sobre 41 tareas y 7 brazos:

            vocabulario                      regiones  tareas/reg  utilidad    ahorro
            actual: cardinalidad x literal          7         5,9     0,938       69%
            anterior: card/oracle/coup/chain        7         5,9     0,928       37%
            region x literal                        9         4,6     0,951       48%
            literal solo                            3        13,7     0,943       57%

        **A igual granularidad —7 regiones, 5,9 tareas por región— el nuevo gana en los dos
        ejes.** No es un empate que se rompe por gusto: `+0,010` de utilidad y **casi el
        doble de ahorro**.

        Y HAY UNA RAZÓN ESTRUCTURAL ADEMÁS DE LA MEDIDA. El vocabulario anterior dependía de
        `coupling`, que es `DERIVED`: en modo determinista D2 colapsaba a `unknown`, así que
        **la región que gobierna en regulado no era la que se había aprendido**. Los dos ejes
        nuevos son `COMPUTABLE` y sobreviven la proyección.

        LO QUE NO CAMBIÓ: el intercambio de fondo. Aprender por vector exacto nunca junta
        episodios suficientes; binear cambia resolución por tamaño de muestra, y mantiene la
        política chica como para leerla a ojo.

        POR QUÉ **NO** SE ELIGIÓ EL QUE MÁS AHORRA, que es la parte que importa. El mejor
        en costo es `cardinalidad × literal` con 69%, y **deja a la SONDA sin nada que
        resolver**: sus dos ejes son `COMPUTABLE`, así que el ciclo de decisión de dos pasos
        —pagar una sonda barata para establecer un eje `DERIVED` y refinar la región—
        quedaría inerte. Lo destapó `test_science.py` §21, no el análisis.

            Una mejora medida que apaga un subsistema en silencio no es una mejora
            medida: es dos cambios, y uno no se midió.

        Así que se toma el que **domina al anterior sin apagar nada**: `región previa ×
        literal`. Contra el vocabulario que reemplaza, gana en los dos ejes —`+0,023` de
        utilidad y 48% de ahorro contra 37%— y conserva `coupling`, que es el eje que la
        sonda existe para establecer. El 21% de ahorro que se deja sobre la mesa queda
        registrado como decisión abierta del autor en `PENDIENTES.es.md` (`CP-8`), no
        enterrado acá.

        `?` significa **no establecido**, nunca un valor por defecto — un request sin
        cardinalidad declarada cae en su propia región y no se disfraza de `singular`.
        """
        return f"{self.region_previa()}/{self.literal or '?'}"

    def region_previa(self) -> str:
        """La región del vocabulario `regions/2-continuation`, para leer el registro viejo.

        5.932 filas lo llevan estampado. Recomputarla es lo que permite analizarlas sin
        re-correrlas; borrarla volvería irreproducible un registro pago.
        """
        if self.n_units <= 1:
            card = "single"
        elif self.n_units <= 8:
            card = "few"
        elif self.n_units <= 64:
            card = "many"
        else:
            card = "bulk"

        oracle = "oracle" if self.has_oracle else "no_oracle"

        if self.coupling is None:
            coup = "unknown"
        elif self.coupling < 0.33:
            coup = "loose"
        elif self.coupling < 0.66:
            coup = "mixed"
        else:
            coup = "tight"

        if self.continuation is None:
            chain = "c?"
        else:
            chain = "chain" if self.continuation else "flat"

        return f"{card}/{oracle}/{coup}/{chain}"


COUPLING_PROMPT = """You estimate two structural properties of a task. Answer with JSON only.

Task:
{task}

Number of independent input units already counted: {n_units}

Return exactly:
{{"coupling": <float 0..1>, "horizon_unknown": <true|false>}}

coupling = degree to which the sub-results depend on each other.
  0.0 = every unit can be processed alone and results merely concatenated
  1.0 = each step needs the previous step's output (chained / multi-hop)
horizon_unknown = true if the number of steps required cannot be known in advance.

No prose. No markdown fences. JSON only."""


def payload_for(task: dict[str, Any]) -> dict[str, Any]:
    """El vocabulario que el extractor de features consume, construido en UN lugar.

    POR QUE EXISTE. Habia tres sitios armando este diccionario a mano —`runner.py`,
    `serve.py`, y el `as_task()` del request— y **dos ya se habian separado**: los dos
    del banco omitian `has_oracle`, asi que la decision recibia una tarea
    indistinguible de una que no declara detector. El fallo cerrado lo atrapo antes de
    gastar un token, pero atraparlo no es lo mismo que no poder volver a escribirlo.

    LA DIFERENCIA CON UNA TAREA. El extractor habla de `units`; el corpus, de
    `unit_ids`. Ese renombre es toda la traduccion, y es exactamente el tipo de detalle
    que se copia mal la tercera vez.
    """
    return {
        "question": task["question"],
        "units": task["unit_ids"],
        "oracle": task["oracle"],
        "has_oracle": task["has_oracle"],
        "irreversible": task.get("irreversible", False),
        "shared_writes": task.get("shared_writes", False),
        "budget_tokens": task["budget_tokens"],
        # LA CARDINALIDAD LA DECLARA EL CALLER (CP-6). No se infiere del fraseo, que es la
        # regla que este módulo se impuso en su primera línea — se recibe, como
        # `irreversible` o `shared_writes`. `.get` y no `[...]`: un caller que no la declara
        # cae en la región `?`, que es información, no un default.
        "answer_cardinality": task.get("answer_cardinality"),
    }


def has_runtime_detector(task: dict[str, Any]) -> bool:
    """Si existe un detector barato EN RUNTIME — no si el banco tiene clave de respuestas.

    POR QUE ES UNA FUNCION Y NO DOS LINEAS. Esto se leia en dos lugares —el segmento de
    region, aca; y la creencia `has_oracle`, en `rules.py`— y los dos derivaban el valor
    de `bool(task["oracle"])`, o sea del GOLD. Eran la misma idea escrita dos veces, que
    es como empiezan a separarse: una simulacion que piso solo la region reporto CERO
    cambio, porque reetiquetar una region no cambia lo que una regla cree. Ahora hay un
    solo lugar donde vive la definicion.

    POR QUE IMPORTA. Mientras el detector se derivara del gold, toda tarea corregible
    tenia detector — 25 de 26 en cada corpus del registro. Con detector en todas, la
    regla de cascada dispara en prioridad 90 y la de seleccion, en 70, no se evalua
    nunca. El banco no podia medir seleccion porque SER CORREGIBLE IMPLICABA TENER
    DETECTOR. Medido sobre `gold_p17`: leer el campo declarado hace caer la cascada de
    22 a 2 de 26.

    FALLA CERRADA. Una tarea sin el campo declarado levanta excepcion en vez de asumir
    `True`, porque el default era el bug entero.
    """
    if "has_oracle" not in task:
        raise KeyError(
            f"La tarea {task.get('task_id', '?')!r} no declara `has_oracle`. Es la "
            "capacidad de verificacion en RUNTIME, y no se deriva del gold: derivarla "
            "era lo que impedia medir seleccion. Regenerar el corpus con "
            "`--honest-detectors`."
        )
    return bool(task["has_oracle"])


class FeatureExtractor:
    """Builds phi from a task record.

    The COMPUTABLE part reads declared task structure. It does not attempt to parse
    intent out of the prompt text, by design.
    """

    def __init__(self, client: LLMClient | None = None) -> None:
        # None is legitimate and means "computable features only". It is not a
        # degraded mode; it is the deterministic mode.
        self._client = client

    def extract(self, task: dict[str, Any], allow_derived: bool) -> tuple[Features, Usage]:
        usage = Usage()

        units = task.get("units") or []
        base = Features(
            n_units=len(units) if units else 1,
            has_oracle=has_runtime_detector(task),
            irreversible=bool(task.get("irreversible", False)),
            shared_writes=bool(task.get("shared_writes", False)),
            budget_tokens=int(task["budget_tokens"]),
        )

        if not allow_derived or self._client is None:
            return base, usage

        derived, derived_usage = self._derive(task, base.n_units)
        usage.merge(derived_usage)
        if derived is None:
            # Estimation failed. Leaving the fields as None is the honest outcome:
            # it will cap confidence downstream and push the router to abstain.
            return base, usage

        return (
            Features(
                n_units=base.n_units,
                has_oracle=base.has_oracle,
                irreversible=base.irreversible,
                shared_writes=base.shared_writes,
                budget_tokens=base.budget_tokens,
                coupling=derived["coupling"],
                horizon_unknown=derived["horizon_unknown"],
            ),
            usage,
        )

    def _derive(
        self, task: dict[str, Any], n_units: int
    ) -> tuple[dict[str, Any] | None, Usage]:
        prompt = COUPLING_PROMPT.format(task=task["question"], n_units=n_units)
        completion = self._client.complete(
            messages=[{"role": "user", "content": prompt}], max_tokens=200
        )
        try:
            parsed = json.loads(completion.text.strip())
            coupling = float(parsed["coupling"])
            if not 0.0 <= coupling <= 1.0:
                return None, completion.usage
            return (
                {
                    "coupling": coupling,
                    "horizon_unknown": bool(parsed["horizon_unknown"]),
                },
                completion.usage,
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None, completion.usage
