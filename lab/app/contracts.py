"""Contratos de afirmacion: el proyector que el codigo decide, y su residuo.

Implementa DOS de las tres clases de `CONTRATOS.es.md` §2 — las dos que se pueden cerrar
sin parsear prosa:

  C-NUM       ningun numeral emitido puede ser inventado          `fill()`
  C-COMPLETE  una enumeracion cubre el dominio que declara        `complete()`

C-CITE queda afuera a proposito: verificar una cita contra el indice necesita el indice,
que es infraestructura de producto y no de esta capa.

LA FORMA. El modelo NO escribe digitos. Escribe una plantilla con ranuras nombradas y una
asignacion ranura -> proposicion; el codigo sustituye desde la base de creencias. Asi el
proyector `pi_NUM` no tiene que extraer numeros de un texto —nada que parsear— porque las
ranuras ya vienen enumeradas.

LO QUE GARANTIZA. Ningun numeral de la salida puede ser inventado: cada uno es el
renderizado de un valor sostenido en la base a procedencia >= `floor`. Una ranura cuya
proposicion no llega al piso NO se renderiza — la afirmacion no se emite.

LO QUE NO GARANTIZA, Y ESTA IMPLEMENTADO PARA PODER MEDIRLO. Que la ranura este en el
lugar correcto de la oracion. La asociacion ranura -> posicion la elige el modelo, y eso
queda FUERA de `pi_NUM`. Ese es el residuo, y `redteam.py` lo ataca.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from collections.abc import Sequence
from typing import Any

from .beliefs import Belief, BeliefBase, Provenance

# Vocabulario CERRADO de ranuras: identificadores, no prosa. Se listan y se buscan por
# nombre exacto — no se infiere nada de texto libre.
SLOT = re.compile(r"\{([a-z][a-z0-9_]*)\}")


@dataclass(frozen=True)
class SlotBinding:
    """Una ranura de la plantilla y la proposicion que el modelo le asigno."""

    slot: str
    proposition: str


@dataclass
class NumericVerdict:
    """Que paso con cada ranura, y por que."""

    rendered: str | None
    checked: list[tuple[str, str, Any]] = field(default_factory=list)
    refused: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def emitted(self) -> bool:
        return self.rendered is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "emitted": self.emitted,
            "rendered": self.rendered,
            "checked": [
                {"slot": s, "proposition": p, "value": v} for s, p, v in self.checked
            ],
            "refused": [
                {"slot": s, "proposition": p, "reason": r} for s, p, r in self.refused
            ],
        }


def slots_of(template: str) -> list[str]:
    """Las ranuras que la plantilla declara, en orden de aparicion."""
    return SLOT.findall(template)


def fill(
    template: str,
    bindings: list[SlotBinding],
    base: BeliefBase,
    floor: Provenance = Provenance.COMPUTED,
) -> NumericVerdict:
    """Sustituir cada ranura por el valor de su proposicion, o no emitir nada.

    FALLA CERRADA Y ENTERA. Si una sola ranura no llega al piso, no se emite una version
    parcial: la salida entera se retiene. Emitir la oracion con un hueco —o peor, con el
    nombre de la ranura visible— seria dejar que el lector complete lo que el contrato
    rechazo, que es la version tipografica de afirmar sin evidencia.
    """
    verdict = NumericVerdict(rendered=None)
    declared = {b.slot: b.proposition for b in bindings}
    values: dict[str, Any] = {}

    for slot in slots_of(template):
        proposition = declared.get(slot)
        if proposition is None:
            verdict.refused.append((slot, "", "la plantilla usa una ranura sin asignar"))
            continue
        belief = base.current(proposition)
        if belief is None:
            verdict.refused.append((slot, proposition, "no hay creencia sobre eso"))
            continue
        if belief.provenance.rank < floor.rank:
            verdict.refused.append((
                slot, proposition,
                f"procedencia {belief.provenance.value} por debajo de {floor.value}",
            ))
            continue
        values[slot] = belief.value
        verdict.checked.append((slot, proposition, belief.value))

    if verdict.refused:
        return verdict

    verdict.rendered = SLOT.sub(lambda m: str(values[m.group(1)]), template)
    return verdict


# --- C-COMPLETE ---------------------------------------------------------------------
#
# POR QUE ESTA CLASE, Y POR QUE RECIEN AHORA. Estaba escrita en `CONTRATOS.es.md` §2 desde
# el principio y no implementada, porque no habia nada que dijera que hacia falta. Lo hay
# desde el 2026-08-28 (`_analyze_demands2.py`, leccion 8.6):
#
#   sobre celdas de cobertura EXIGIDA, leer mas NO mejora la utilidad
#   (corr +0,018, mediana -0,055, contra +0,259 donde la cobertura no se exige)
#
# El arreglo intuitivo frente a una enumeracion incompleta es "que lea todo", y el registro
# dice que no funciona: lo dificil no es haber visto, es COMPONER lo visto. Entonces la
# completitud no se compra con presupuesto de lectura — hace falta verificarla, y
# verificarla es aritmetica sobre un dominio declarado.
#
# LA FORMA, Y ES LA MISMA DISCIPLINA QUE C-NUM. El modelo NO escribe una lista en prosa
# para que alguien despues la parsee. Escribe CLAVES de un vocabulario que el codigo ya
# enumero, mas la proposicion que define el dominio. Entonces `pi_COMPLETE` no extrae nada
# de un texto: compara dos conjuntos.
#
# LO QUE GARANTIZA. Que los items enumerados cubren EXACTAMENTE el dominio declarado —
# nada falta y nada sobra. Las dos mitades importan y son distintas: lo que falta es una
# respuesta incompleta que parece bien formada; lo que sobra es un item que el dominio no
# admite.
#
# LO QUE NO GARANTIZA, Y SE REPORTA EN EL VEREDICTO. Que el dominio coincida con el mundo.
# Completitud sobre lo recuperado no es completitud sobre lo que existe, y la unica forma
# honesta de manejarlo es que el veredicto lleve la procedencia del dominio encima en vez
# de que el llamador la suponga.
#
# EL RESIDUO, que es el mismo hallazgo que el de C-NUM. Una enumeracion puede cubrir su
# dominio entero y estar mal: alcanza con que la ORACION que la envuelve diga otra cosa
# ("ninguno de estos", "todos menos", "los que quedan"). La prosa conectiva sigue sin
# ocupar ninguna ranura, asi que C-COMPLETE tampoco puede contradecirla. No es un defecto
# de esta implementacion — es la frontera de la familia entera, medida en `redteam.py`.


@dataclass
class CompletenessVerdict:
    """Que se enumero, contra que dominio, y que falto o sobro."""

    emitted: bool
    domain_proposition: str
    domain_provenance: str | None = None
    covered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    extraneous: list[str] = field(default_factory=list)
    refused: str | None = None

    @property
    def scope_is_declared_not_world(self) -> bool:
        """SIEMPRE cierto, y por eso es una propiedad y no un flag opcional.

        La garantia es relativa al dominio que la tarea declara. Que ese dominio sea el
        mundo es una afirmacion sobre la ingesta y la recuperacion, no sobre el contrato,
        y esta capa no tiene con que sostenerla.
        """
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "emitted": self.emitted,
            "domain": self.domain_proposition,
            "domain_provenance": self.domain_provenance,
            "covered": list(self.covered),
            "missing": list(self.missing),
            "extraneous": list(self.extraneous),
            "refused": self.refused,
            "scope": "dominio declarado, no el mundo",
        }


def complete(
    items: list[str],
    domain_proposition: str,
    base: BeliefBase,
    floor: Provenance = Provenance.COMPUTED,
) -> CompletenessVerdict:
    """Verificar que `items` cubre el dominio que `domain_proposition` sostiene.

    FALLA CERRADA Y ENTERA, como C-NUM. Una enumeracion a la que le falta un item no se
    emite recortada ni con una advertencia al lado: no se emite. Emitirla con una nota
    seria dejarle al lector la decision que el contrato existe para tomar — y el modo de
    falla de una enumeracion incompleta es justamente que PARECE completa.
    """
    verdict = CompletenessVerdict(emitted=False, domain_proposition=domain_proposition)

    belief = base.current(domain_proposition)
    if belief is None:
        verdict.refused = "no hay creencia que defina el dominio"
        return verdict

    verdict.domain_provenance = belief.provenance.value
    if belief.provenance.rank < floor.rank:
        verdict.refused = (
            f"el dominio se sostiene a {belief.provenance.value}, por debajo de "
            f"{floor.value}: una completitud sobre un dominio supuesto no es completitud"
        )
        return verdict

    if not isinstance(belief.value, (list, tuple, set, frozenset)):
        verdict.refused = (
            f"el dominio no es enumerable: {type(belief.value).__name__}. La cardinalidad "
            f"es aritmetica y no hay aritmetica sobre un valor que no se puede recorrer"
        )
        return verdict

    domain = list(dict.fromkeys(str(v) for v in belief.value))
    seen = list(dict.fromkeys(str(v) for v in items))

    verdict.covered = [k for k in domain if k in seen]
    verdict.missing = [k for k in domain if k not in seen]
    verdict.extraneous = [k for k in seen if k not in domain]

    if verdict.missing or verdict.extraneous:
        parts = []
        if verdict.missing:
            parts.append(f"faltan {len(verdict.missing)}")
        if verdict.extraneous:
            parts.append(f"sobran {len(verdict.extraneous)}")
        verdict.refused = " y ".join(parts)
        return verdict

    verdict.emitted = True
    return verdict


def addressed(answer: str, domain_keys: list[str]) -> list[str]:
    """Las claves del dominio que la respuesta MENCIONA, en orden de dominio.

    POR QUE ESTO NO ES PARSEAR PROSA, que es lo que este proyecto no acepta como sensor.
    No se extrae nada del texto: se toma un vocabulario CERRADO Y DECLARADO —las claves
    que el caller enuncio— y se pregunta por cada una si esta presente. La direccion
    importa: buscar una lista conocida adentro de un texto es contencion sobre un conjunto
    finito; extraer entidades de un texto para ver cuales hay es lo otro, y no se hace.

    LO QUE VERIFICA Y LO QUE NO. Verifica que la respuesta ATIENDA a cada elemento del
    dominio. NO verifica que lo que dice de cada uno sea correcto — eso es `C-CITE`, y
    necesita el indice. Un enunciado que nombra a los cinco y le erra a cuatro cuentas
    pasa esta verificacion y falla la otra: son contratos distintos a proposito.

    Y NO VE LO QUE SOBRA, que es una asimetria estructural y no una omision. Esta funcion
    busca las claves DECLARADAS adentro del texto, asi que un nombre que el dominio no
    contiene nunca entra en `items` y la pertenencia no es observable desde aca. Detectarlo
    exigiria extraer entidades de la prosa — justo lo que este proyecto no acepta como
    sensor. `complete()`, que recibe el conjunto ya enumerado, si la ve.
    """
    lowered = " ".join(answer.lower().split())
    return [k for k in domain_keys if " ".join(str(k).lower().split()) in lowered]


def complete_answer(
    answer: str,
    domain_keys: list[str],
    base: BeliefBase | None = None,
    proposition: str = "el dominio declarado por el caller",
) -> CompletenessVerdict:
    """`C-COMPLETE` sobre una respuesta en prosa contra un dominio declarado.

    Atajo sobre `complete()` para el caso `from_question`: el dominio viene enunciado, asi
    que se asienta como `COMPUTED` —el caller lo declaro, igual que declara `irreversible`,
    y credencia 1.0 porque no hay nada que estimar— y se compara contra lo que la respuesta
    atiende.
    """
    if base is None:
        base = BeliefBase()
        base.assert_(Belief(proposition, list(domain_keys), 1.0, Provenance.COMPUTED))
    return complete(addressed(answer, domain_keys), proposition, base)


def verify_coverage(task: dict[str, Any], answer: str) -> dict[str, Any] | None:
    """`C-COMPLETE` sobre una tarea, cuando corresponde. `None` cuando NO corresponde.

    EL DISPARADOR, TIPADO. Son DOS condiciones y ninguna alcanza sola:

      la tarea EXIGE cobertura        `coverage_demanded == "exhaustive"`
      y su dominio es ENUMERABLE      `completeness_domain == "from_question"`

    La primera sin la segunda es el caso que la leccion 8.7 midio y que no tiene salida:
    en una celda de dominio `semantic` —«listame todos los que tienen el rol R»— enumerar
    el dominio ES la extraccion, asi que el contrato no verificaria al paradigma, lo
    reemplazaria. Y en una de dominio `from_scope` el dominio barato son las unidades,
    que se midio que NO predice correccion (`+0,018`).

    La segunda sin la primera es una tarea que enumera algo y no pide exhaustividad: ahi
    exigir cobertura es pagar de mas por nada.

    `None` significa **sin contrato**, y se distingue de un contrato cumplido: un
    booleano las volveria indistinguibles y son opuestas — «nadie verifico» contra «se
    verifico y paso».

    RETROCOMPATIBLE POR DISENO. Una tarea de un corpus anterior a `REQUEST_DEMANDS` no
    declara los ejes; ahi el disparador se cae a la presencia de `domain_keys`, que es lo
    unico que se puede saber de ella, y NO se supone la demanda.
    """
    domain = task.get("domain_keys") or []
    if not domain:
        return None

    demanded = task.get("coverage_demanded")
    enumerable = task.get("completeness_domain")
    if demanded and enumerable:
        if demanded != "exhaustive" or enumerable != "from_question":
            return None

    return complete_answer(answer, list(domain)).as_dict()

# Cuantos reintentos dirigidos se PROPONEN. Uno, y acotado por el codigo.
#
# POR QUE UNO Y POR QUE PROPUESTO. `P20` midio que una accion que el modelo puede repetir
# por su cuenta deja de ser control de flujo del codigo: rechazada una busqueda, la
# re-emitia con otras palabras el 69% de las veces. Un reintento automatico tiene la misma
# forma — el sistema gastando presupuesto que nadie autorizo, con la posibilidad de volver
# a fallar igual. Asi que el codigo PROPONE y el llamador decide.
# ---------------------------------------------------------------------------
# C-ABSENCE — afirmar que algo NO esta
# ---------------------------------------------------------------------------
#
# EL DE PEOR RELACION DAÑO/ATENCION de la familia entera. Una ausencia afirmada desde una
# muestra produce una respuesta que PARECE NORMAL: «no hay ninguna clausula de rescision»
# se lee igual de segura leyendo 3 unidades que leyendo las 40. Un error de presencia se
# cae solo —el lector busca el dato y no esta— y uno de ausencia no deja rastro, porque no
# hay nada que buscar.
#
# LA ASIMETRIA ES LA REGLA, y es la unica pieza que hace falta:
#
#   presencia   UN testigo alcanza. Encontrada la clausula, el resto del corpus no
#               cambia el veredicto
#   ausencia    hace falta el DOMINIO ENTERO. Cualquier unidad sin leer puede contener
#               justo lo que se esta negando
#
# La sonda ya tiene esta asimetria, pero solo del lado del MATERIAL —cuanto queda por
# recuperar—. Del lado de la RESPUESTA no existia: nada distinguia un enunciado que
# afirma de uno que niega, asi que los dos se emitian con la misma evidencia.
#
# COMO SE SABE QUE LA RESPUESTA NIEGA, SIN PARSEAR PROSA. No se lee el texto. El agente
# declara la polaridad en un campo TIPADO de vocabulario cerrado, igual que declara
# `status` en el handoff. Un enum de dos valores no es un parseo: es una eleccion entre
# opciones enumeradas, y el codigo la trata como proposicion del modelo —o sea ELICITED—
# mientras que la cobertura contra la que se verifica es aritmetica sobre el registro de
# lectura, o sea COMPUTED.
POLARITY = frozenset({"present", "absent"})

# Las obligaciones que una tarea puede EXIGIR. Vocabulario cerrado: una tarea que pide una
# obligacion que nadie definio es un error de corpus, no una obligacion nueva.
OBLIGATIONS = frozenset({"absence", "presupposition"})


# LA SEGUNDA PRUEBA DE AUSENCIA, Y ES GRATIS (CP-1, 2026-08-30)
#
# La regla de arriba dice que una ausencia necesita el DOMINIO ENTERO, y es correcta. Pero
# tenía una sola forma de conseguirlo —leerlo— y para una ausencia **de término** hay otra
# que cuesta cero tokens y es igual de concluyente:
#
#     si la cadena no aparece en NINGUNA unidad del alcance, no aparece.
#
# Eso es aritmética sobre el material, `COMPUTED`, y no exige haber leído una sola unidad.
# Es exactamente lo mismo que `presupposition()` ya hace un poco más abajo —contención de
# una cadena que el agente enunció, contra el texto— con el signo dado vuelta: allá se
# busca que ESTÉ, acá que NO esté.
#
# DE DÓNDE SALIÓ: derivando a mano el camino de las 78 preguntas. Las nueve de
# `B2_absence` tienen cero unidades relevantes, y medido sobre `b2-000-w16`,
# `keyword_search('trustee')` devuelve **0 unidades** mientras `'director'` devuelve 5 como
# control. La prueba estaba disponible y ningún brazo la usaba: `rewoo` (u=0,00) llamó
# `search` 19 veces contra 12 de `keyword_search`, y `search` es el ranking **fusionado**,
# que nunca vuelve vacío — no puede testimoniar una ausencia. El que ganaba la ausencia era
# `handoff` (u=0,92) **leyendo 19 unidades**: la respuesta cara a una pregunta que tenía
# una respuesta aritmética.
#
# Y POR ESO VA EN LA CAPA DE DECISIÓN Y NO EN UN PATRÓN. Quien elige la herramienta es el
# modelo, y el modelo prefiere buscar antes que probar que no hay. Una regla que depende de
# que el modelo elija bien no es una regla.
#
# HASTA DÓNDE LLEGA, dicho con precisión, porque es una prueba con un límite real:
#
#   prueba          que el TÉRMINO no está en el material
#   NO prueba       que la COSA no esté, si el material la nombraría de otra manera
#
# De ahí las dos guardas. La de largo mínimo es la misma que la presuposición: una cadena
# de tres caracteres aparece en cualquier lado y autorizaría siempre. La de **cantidad de
# palabras** es la que hace honesto al límite — una paráfrasis larga ausente prueba que la
# paráfrasis está ausente, que no es lo que se está afirmando. Un término es un término.
MIN_TERM_CHARS = 4
MAX_TERM_WORDS = 4

TERM_FLOOR_PROPOSAL = Provenance.ELICITED
TERM_FLOOR_AUTHORISATION = Provenance.COMPUTED


@dataclass
class TermProof:
    """Si la ausencia de una cadena está PROBADA sobre el alcance, sin leer nada.

    `proves_absence` es lo único que autoriza; los demás campos están para que el registro
    diga por qué, que es lo que permite auditar una autorización después.
    """

    term: str
    occurrences: int
    units_scanned: int
    proves_absence: bool
    refused: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "occurrences": self.occurrences,
            "units_scanned": self.units_scanned,
            "proves_absence": self.proves_absence,
            "refused": self.refused,
        }


def term_absence(
    term: str, documents: dict[str, str], unit_ids: Sequence[str]
) -> TermProof:
    """¿Está esta cadena en ALGUNA unidad del alcance? Aritmética pura, cero llamadas.

    LA DIRECCIÓN IMPORTA, igual que en `presupposition()`: buscar una cadena conocida
    adentro de un texto es finito; extraer del texto qué cadenas hay es lo otro. El agente
    propone la cadena —`ELICITED`, su lectura de qué está negando— y esto la autoriza o no
    contra el material, que es `COMPUTED`.

    FALLA CERRADA en las tres formas de no poder probar: dominio vacío, término demasiado
    corto, término demasiado largo para ser un término. Ninguna emite con advertencia.
    """
    limpio = " ".join((term or "").lower().split())
    proof = TermProof(term=limpio, occurrences=0, units_scanned=len(unit_ids),
                      proves_absence=False)
    if not unit_ids:
        proof.refused = (
            "el alcance esta vacio: sobre cero unidades no se puede probar que algo falte"
        )
        return proof
    if len(limpio) < MIN_TERM_CHARS:
        proof.refused = (
            f"{limpio!r} tiene menos de {MIN_TERM_CHARS} caracteres. Una cadena tan corta "
            f"aparece en cualquier lado, asi que su ausencia tampoco significaria nada"
        )
        return proof
    if len(limpio.split()) > MAX_TERM_WORDS:
        proof.refused = (
            f"{limpio!r} tiene {len(limpio.split())} palabras y el maximo es "
            f"{MAX_TERM_WORDS}. Esto prueba la ausencia de un TERMINO; una parafrasis "
            f"larga ausente solo prueba que la parafrasis esta ausente, que no es lo que "
            f"se esta afirmando"
        )
        return proof
    proof.occurrences = sum(
        1 for u in unit_ids
        if limpio in " ".join(documents.get(u, "").lower().split())
    )
    proof.proves_absence = proof.occurrences == 0
    if not proof.proves_absence:
        proof.refused = (
            f"{limpio!r} aparece en {proof.occurrences} de {len(unit_ids)} unidades, asi "
            f"que el material NO sostiene que falte"
        )
    return proof


@dataclass
class AbsenceVerdict:
    """Si un enunciado de ausencia tiene con que sostenerse."""

    emitted: bool
    polarity: str
    units_read: int
    units_available: int
    refused: str | None = None
    # POR QUE VIA se autorizo. Dos rutas distintas a la misma conclusion no se pueden
    # colapsar en un booleano: auditar una autorizacion exige saber si detras hay un
    # dominio leido o una cadena que no esta.
    via: str | None = None
    proof: "TermProof | None" = None

    @property
    def exhaustive(self) -> bool:
        return self.units_available > 0 and self.units_read >= self.units_available

    def as_dict(self) -> dict[str, Any]:
        return {
            "emitted": self.emitted,
            "polarity": self.polarity,
            "units_read": self.units_read,
            "units_available": self.units_available,
            "exhaustive": self.exhaustive,
            "refused": self.refused,
            "via": self.via,
            "proof": self.proof.as_dict() if self.proof else None,
        }


def absence(
    polarity: str,
    units_read: int,
    units_available: int,
    proof: "TermProof | None" = None,
) -> AbsenceVerdict:
    """La carga de prueba que le toca a esta polaridad.

    FALLA CERRADA, como el resto de la familia: una ausencia sin dominio completo NO se
    emite con una advertencia al lado. Emitirla anotada le deja al lector la decision que
    el contrato existe para tomar, y el modo de falla es que el lector no la toma.

    `units_available == 0` es un dominio VACIO, y ahi no se puede afirmar nada —ni
    presencia ni ausencia—. Es distinto de un dominio leido entero: cero de cero no es
    exhaustivo, es que no habia con que.
    """
    if polarity not in POLARITY:
        raise ValueError(
            f"Polaridad {polarity!r} fuera del vocabulario {sorted(POLARITY)}. Es un enum "
            f"declarado, no texto: un valor nuevo seria una polaridad que nadie definio."
        )
    verdict = AbsenceVerdict(
        emitted=False, polarity=polarity,
        units_read=units_read, units_available=units_available,
    )
    if units_available <= 0:
        verdict.refused = (
            "el dominio esta vacio: no se puede afirmar presencia ni ausencia sobre cero "
            "unidades, y cero de cero no es exhaustivo"
        )
        return verdict
    if polarity == "present":
        # UN TESTIGO ALCANZA. No se exige cobertura: encontrada la cosa, lo que quede sin
        # leer no puede desmentirla. Exigir exhaustividad aca seria simetria falsa.
        verdict.emitted = True
        verdict.via = "testigo"
        return verdict
    if verdict.exhaustive:
        verdict.emitted = True
        verdict.via = "dominio_leido"
        return verdict
    # LA SEGUNDA RUTA AL MISMO DOMINIO. No se leyo todo, pero si la cadena que se niega no
    # esta en NINGUNA unidad del alcance, el dominio quedo cubierto igual — por aritmetica
    # y no por lectura. Es la misma carga de prueba conseguida por el camino barato, no una
    # carga mas floja: `term_absence` recorre TODAS las unidades, no una muestra.
    if proof is not None and proof.proves_absence:
        verdict.emitted = True
        verdict.via = "termino_ausente"
        verdict.proof = proof
        return verdict
    # NO SE PUDO POR NINGUNA VIA. La prueba fallida se guarda igual: saber POR QUE no
    # alcanzo —termino corto, parafrasis larga, o el termino si estaba— es lo que permite
    # que el reintento dirigido proponga otro, en vez de repetir el mismo.
    if proof is not None:
        verdict.proof = proof
    verdict.refused = (
        f"ausencia afirmada leyendo {units_read} de {units_available} unidades"
        + (f", y el termino propuesto no prueba nada: {proof.refused}"
           if proof is not None and proof.refused
           else " y sin termino propuesto que verificar")
        + ". Cualquier unidad sin leer puede contener justo lo que se niega, asi que esto "
          "es una muestra presentada como un hecho sobre el dominio"
    )
    return verdict


# ---------------------------------------------------------------------------
# C-PRESUPPOSITION — la pregunta da algo por sentado
# ---------------------------------------------------------------------------
#
# «Cuando renuncio Valerio?» da por sentado que renuncio. Si no renuncio, TODA respuesta a
# la pregunta como esta formulada es falsa, incluida «no se»: contestar con una fecha o con
# un «no consta la fecha» ratifica igual la premisa.
#
# ES EL MAS FACIL DE LA FAMILIA Y NO ESTABA, porque una presuposicion YA TIENE FORMA DE
# PROPOSICION: el mecanismo para verificarla existe entero —es `BeliefBase` con su piso de
# procedencia— y lo unico que faltaba era extraerla.
#
# Y EXTRAERLA NO ES PARSEAR PROSA. Es el patron del handoff, que ya esta medido: el agente
# PROPONE la presuposicion como una cadena tipada —su lectura, `ELICITED`— y el codigo
# AUTORIZA verificando que esa cadena aparezca LITERAL en el material, que es un hecho
# computable, `COMPUTED`. La direccion importa: buscar una cadena conocida adentro de un
# documento es finito; extraer del documento que cadenas hay es lo otro.
PRESUPPOSITION_FLOOR_PROPOSAL = Provenance.ELICITED
PRESUPPOSITION_FLOOR_AUTHORISATION = Provenance.COMPUTED

# Misma guarda de especificidad que la sonda y el handoff: una cadena de tres caracteres
# aparece en cualquier lado y ratificaria cualquier premisa.
MIN_PRESUPPOSITION_CHARS = 4


@dataclass
class PresuppositionVerdict:
    """Si la premisa que la pregunta da por sentada esta sostenida."""

    emitted: bool
    presupposition: str
    supported: bool
    witness: str | None = None
    refused: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "emitted": self.emitted,
            "presupposition": self.presupposition,
            "supported": self.supported,
            "witness": self.witness,
            "refused": self.refused,
        }


def presupposition(
    claim: str, documents: dict[str, str], scope: list[str], base: BeliefBase
) -> PresuppositionVerdict:
    """Verificar la premisa ANTES de contestar la pregunta que la asume.

    Deja las dos creencias asentadas con SU procedencia, no con la del que las pidio: la
    propuesta del agente entra `ELICITED` y la verificacion sobre el material `COMPUTED`.
    Heredar la del proponente fue el error que `P-4` costo.

    NO SE EMITE si la premisa no esta sostenida, y eso incluye no emitir un «no se»: una
    respuesta que declina la fecha ratifica igual que hubo renuncia.
    """
    verdict = PresuppositionVerdict(
        emitted=False, presupposition=claim, supported=False
    )
    needle = " ".join(claim.lower().split())
    if len(needle) < MIN_PRESUPPOSITION_CHARS:
        verdict.refused = (
            f"la premisa {claim!r} tiene menos de {MIN_PRESUPPOSITION_CHARS} caracteres: "
            f"una cadena asi aparece en cualquier lado y ratificaria cualquier pregunta"
        )
        return verdict

    base.assert_(Belief(
        proposition="presupposition_claimed",
        value=claim,
        credence=0.8,
        provenance=PRESUPPOSITION_FLOOR_PROPOSAL,
        evidence=f"el agente declaro que la pregunta da por sentado {claim!r}",
    ))

    for unit in scope:
        if needle in " ".join(documents[unit].lower().split()):
            verdict.supported = True
            verdict.witness = unit
            break

    if not verdict.supported:
        verdict.refused = (
            f"la pregunta da por sentado {claim!r} y el material no lo sostiene. "
            f"Contestarla —con un dato o con un «no consta»— ratifica la premisa igual, "
            f"asi que lo que corresponde es rechazarla, no responderla"
        )
        return verdict

    base.assert_(Belief(
        proposition="presupposition_supported",
        value=claim,
        credence=1.0,
        provenance=PRESUPPOSITION_FLOOR_AUTHORISATION,
        evidence=f"{claim!r} aparece literal en {verdict.witness}",
    ))
    verdict.emitted = True
    return verdict


# ---------------------------------------------------------------------------
# El puente: como llegan las dos declaraciones desde la respuesta
# ---------------------------------------------------------------------------
#
# LAS DOS SON DECLARACIONES TIPADAS, NO PROSA LEIDA. Y las dos se leen distinto, a
# proposito:
#
#   POLARITY       vocabulario CERRADO de dos valores. Un valor fuera de la lista no se
#                  corrige ni se adivina: se trata como no declarado
#   PRESUPPOSES    una cadena que el agente enuncia y que NO se interpreta. Se busca
#                  LITERAL en el material, que es la direccion barata: buscar una cadena
#                  conocida adentro de un documento es finito
#
# EL CONTRATO EXTENDIDO ES UN FACTOR. Agregar estas lineas cambia el prompt de todos los
# brazos, asi que sus filas NO son comparables con las de una corrida sin el. Va apagado
# por defecto, cruzado `{con, sin} x {patrones}`, como `terse_tools` y `offer_read_all`.
OBLIGATIONS_CONTRACT = (
    "Before the ANSWER line, declare these, each on its own line:\n"
    "POLARITY: present   — if you are asserting that something IS in the material\n"
    "POLARITY: absent    — if you are asserting that something is NOT there\n"
    "NEGATES: <term>     — with POLARITY: absent, the SHORT term you are saying is not "
    "there (e.g. the role, the status, the field name). At most "
    f"{MAX_TERM_WORDS} words. It is looked up literally in every unit in scope, so if it "
    "appears nowhere your absence claim is proved without reading anything.\n"
    "PRESUPPOSES: <text> — if the question takes something for granted, quote the "
    "EXACT string from the material that establishes it; omit the line if it takes "
    "nothing for granted.\n"
    "All are looked up mechanically. A paraphrase finds nothing."
)

_POLARITY_LINE = re.compile(
    r"^POLARITY:\s*(" + "|".join(sorted(POLARITY)) + r")\s*$",
    flags=re.MULTILINE | re.IGNORECASE,
)
_PRESUPPOSES_LINE = re.compile(r"^PRESUPPOSES:\s*(.+)$", flags=re.MULTILINE)
_NEGATES_LINE = re.compile(r"^NEGATES:\s*(.+)$", flags=re.MULTILINE)


def declared_polarity(text: str) -> str | None:
    """La polaridad que la respuesta declara, o `None` si no declaro una valida.

    LA REGEX CORRE SOBRE UN VOCABULARIO ENUMERADO, que es la unica forma que este
    proyecto acepta: la alternancia se construye desde `POLARITY`, asi que agregar un
    valor al enum lo agrega al patron y no hay dos listas que se puedan desincronizar.

    `None` es NO DECLARADA, y no es `present`. Caer al valor benigno le regalaria a toda
    respuesta sin declarar la carga de prueba mas facil, que es exactamente al reves de
    para que existe el contrato.
    """
    found = _POLARITY_LINE.findall(text)
    # La ultima gana, igual que `ANSWER:`: un paradigma que revisa su respuesta emite la
    # linea mas de una vez, y la que vale es la que queda.
    return found[-1].lower() if found else None


def declared_presupposition(text: str) -> str | None:
    """La premisa que la respuesta dice que la pregunta da por sentada, sin interpretar."""
    found = _PRESUPPOSES_LINE.findall(text)
    if not found:
        return None
    claim = found[-1].strip()
    return claim or None


def declared_negated_term(text: str) -> str | None:
    """El término que la respuesta dice que NO está, sin interpretar nada.

    Misma forma que `declared_presupposition`: una cadena que el agente enuncia y que el
    código verifica LITERAL contra el material. La dirección importa — buscar una cadena
    conocida adentro de un texto es finito; extraer del texto qué cadenas hay es lo otro.
    """
    found = _NEGATES_LINE.findall(text)
    if not found:
        return None
    return found[-1].strip() or None


def verify_obligations(
    task: dict[str, Any],
    answer_text: str,
    documents: dict[str, str],
    units_read: int,
    base: BeliefBase,
) -> dict[str, Any] | None:
    """Las obligaciones que esta tarea EXIGE, verificadas. `None` cuando no exige ninguna.

    EL DISPARADOR ES TIPADO Y LO DECLARA LA TAREA, igual que en `verify_coverage`. Una
    tarea declara `obligations` con valores de `OBLIGATIONS`; lo que no esta declarado no
    se verifica, y no verificarlo se distingue de verificarlo y pasar.

    `None` significa SIN CONTRATO. Un booleano volveria indistinguible «nadie verifico» de
    «se verifico y paso», que son opuestos.
    """
    demanded = [o for o in (task.get("obligations") or []) if o in OBLIGATIONS]
    if not demanded:
        return None
    if not answer_text.strip():
        raise ValueError(
            f"{task.get('task_id')}: la tarea exige {demanded} y el texto crudo llego "
            f"vacio. Un paradigma que no carga `raw_text` haria que TODA respuesta "
            f"figurara como no declarada, y eso se leeria como incumplimiento del modelo "
            f"cuando es un defecto de plomeria. Se levanta en vez de inventar el fallo."
        )

    report: dict[str, Any] = {}

    if "absence" in demanded:
        polarity = declared_polarity(answer_text)
        if polarity is None:
            # NO DECLARADA NO ES `present`. La tarea exigia declararla y la respuesta no
            # lo hizo, asi que el contrato no se puede evaluar y eso ES el incumplimiento.
            report["absence"] = {
                "emitted": False,
                "polarity": None,
                "refused": (
                    "la tarea exige declarar polaridad y la respuesta no declaro una "
                    "valida. No declarada no es `present`: caer al valor benigno le "
                    "regala la carga de prueba mas facil a quien no declaro"
                ),
            }
        else:
            # LA SEGUNDA RUTA SE INTENTA SIEMPRE Y NO CAMBIA LA CARGA DE PRUEBA. Si el
            # agente declaro que niega, se verifica esa cadena contra TODAS las unidades
            # del alcance; si no la declaro, `None` y queda la ruta de siempre. Una
            # ausencia sigue exigiendo el dominio entero — lo unico que cambia es que
            # ahora hay una forma de cubrirlo que no cuesta tokens.
            termino = declared_negated_term(answer_text) if polarity == "absent" else None
            prueba = (
                term_absence(termino, documents, list(task.get("unit_ids") or []))
                if termino else None
            )
            report["absence"] = absence(
                polarity, units_read, len(task.get("unit_ids") or []), prueba
            ).as_dict()

    if "presupposition" in demanded:
        claim = declared_presupposition(answer_text)
        if claim is None:
            report["presupposition"] = {
                "emitted": False,
                "presupposition": None,
                "supported": False,
                "refused": (
                    "la tarea declara que la pregunta da algo por sentado y la respuesta "
                    "no enuncio que. Contestarla sin verificar la premisa la ratifica"
                ),
            }
        else:
            report["presupposition"] = presupposition(
                claim, documents, list(task.get("unit_ids") or []), base
            ).as_dict()

    return report or None


MAX_DIRECTED_RETRIES = 1


def retention(verdict: CompletenessVerdict, retries_left: int = MAX_DIRECTED_RETRIES,
              contract: str = "C-COMPLETE") -> dict[str, Any] | None:
    """Que informar y que proponer cuando el contrato retiene una respuesta.

    `None` si emitio: no hay nada que informar.

    LO QUE HACE UTIL A ESTO es que el contrato **nombra** lo que falta. No se informa
    «algo salio mal»: se informa que falto `Valeria Arrieta`, porque `C-COMPLETE` lo
    declara sin tener que buscarlo. Un reintento sobre eso es **dirigido** — sabe que
    pedir— y no re-correr a ciegas.

    Y la accion propuesta depende de si queda margen: sin reintentos, lo honesto es
    ofrecer aceptar incompleto **sabiendo que esta incompleto**, que es exactamente lo
    que sin contrato no se podia saber.
    """
    if verdict.emitted:
        return None
    faltan = list(verdict.missing) + [f"sobra:{k}" for k in verdict.extraneous]
    return {
        "contract": contract,
        "missing": faltan,
        "reason": verdict.refused or "el contrato retuvo la respuesta",
        "proposed": "retry" if retries_left > 0 else "accept_incomplete",
        "retries_left": retries_left,
    }
