"""EL PRIMER EJE `LEARNABLE`: si lo que este pedido establece va a volver a pedirse.

QUÉ PREGUNTA CONTESTA, Y POR QUÉ NO ES UNA PREGUNTA SOBRE ESTE PEDIDO. Toda la ontología
de `ONTOLOGIA_PREGUNTAS.es.md` mira **hacia atrás** —`C1` pregunta qué alcance heredó este
request del anterior— y nunca hacia adelante. Falta el eje simétrico: *¿lo que este request
deja establecido lo va a consumir otro?* Ningún sensor lo puede medir, porque no es una
propiedad del material ni del enunciado: es una propiedad de la **población de pedidos**, y
el único lugar donde vive es el ledger.

DE DÓNDE SALE EL EJE, Y ESTÁ MEDIDO POR OTROS. `Memory Depth, Not Memory Access`
(arXiv 2606.26806) mide un *depth flip* con la misma forma que todo lo que este banco
encuentra: ningún brazo gana los dos lados.

    tarea                                    escritura selectiva      recuperación
    recall factual corto                        0,463 - 0,483      **0,956 - 0,973**
    persistencia de meta tras descargar       **0,812 - 0,904**      0,394 - 0,398

Leído como resultado de memoria, dice «depende». Leído como resultado de RUTEO —que es lo
que este repo sostiene— dice otra cosa: **el ganador lo determina un eje, y el eje no está
en φ**. Es exactamente la forma de `P15`, donde θ perdió `−0,087` porque el vocabulario no
representaba continuidad ni horizonte. Éste es el horizonte, del lado que faltaba.

POR QUÉ NO ES UN FEATURE, y ésta es la decisión de diseño del módulo. Meterlo en `Features`
lo haría entrar a `region()` y a la proyección D2, y sobre todo lo declararía como una
creencia sobre ESTE request cuando es una frecuencia sobre pedidos parecidos. Es el mismo
error de categoría que `Scope` existe para impedir, y el mismo que `association.py` tuvo que
justificar a mano. Acá se declara con el tipo: `Acquisition.LEARNABLE`, que resuelve a
`COMPUTED` sobre `POPULATION`.

Y ESO LO DEJA ESTRUCTURALMENTE FUERA DE LO IRREVERSIBLE sin agregar ninguna guarda.
`admissible_for_action` ya exige `Scope.REQUEST`: por bien medida que esté la tasa, no puede
gatear una acción que no se puede deshacer. La guarda ya estaba; faltaba la declaración.

QUÉ DEVUELVE HOY SOBRE EL REGISTRO DE ESTE BANCO: **nada, y eso es la medición.** El corpus
es de turno único y `Episode` no lleva sesión, así que no hay dos pedidos encadenados de los
que sacar una tasa. `ONTOLOGIA_PREGUNTAS.es.md` avisa en su encabezado que el corpus ya
decidió en silencio tres veces qué hipótesis podían ponerse a prueba —el detector heredado
del gold, las entidades sin ambigüedad, el turno único— «y este documento existe en parte
para que la cuarta no pase desapercibida». Ésta es la cuarta. Se implementa, se corre y se
mide su ausencia, que es como §76 dejó establecido que se tratan estos casos.

LO QUE ESTE MÓDULO NO HACE, dicho antes de que alguien lo asuma. No decide nada: no hay
regla que lea `reuse_horizon`, y meterle una sin medirla repetiría el defecto de
`horizon_unknown`, que se asentaba y nadie leía. Tampoco implementa la compuerta de
escritura —consolidar sólo bajo error de predicción, que es la mitad que la biología tiene y
la industria no— y ésa es la apuesta siguiente, registrada en `P42` y no acá.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from .beliefs import Acquisition, Belief, Provenance, Scope

# LA PROPOSICIÓN, con su vía de adquisición declarada. Es el registro que `Acquisition`
# existe para tener: la base de creencias puede contestar «no lo sé, y así se sabría».
PROPOSITION = "reuse_horizon"
ACQUISITION: dict[str, Acquisition] = {PROPOSITION: Acquisition.LEARNABLE}

# EL MISMO PISO QUE θ, y por la misma razón. Una tasa sacada de tres observaciones no es una
# tasa: es ruido con dos decimales. `policy.MIN_EPISODES_FOR_CONFIDENCE` vale 8 y se replica
# el número a propósito en vez de importarlo — son dos decisiones distintas que hoy coinciden,
# y atarlas haría que mover una moviera la otra sin que nadie lo decidiera.
MIN_OBSERVACIONES = 8


@dataclass(frozen=True)
class Trace:
    """Un pedido, ubicado en su secuencia. La unidad mínima para que el eje exista.

    `session` ES EL CAMPO QUE EL BANCO NO TIENE, y por eso este dataclass no es `Episode`
    con un campo más: es el reconocimiento de que medir esto necesita un registro de otra
    forma. Un ledger de tareas independientes no se puede reparar agregándole una columna
    vacía; hay que correr pedidos encadenados.

    `orden` es la posición dentro de la sesión. No se usa un timestamp porque lo que importa
    es la precedencia, y dos pedidos del mismo segundo siguen teniendo un orden.
    """

    session: str
    orden: int
    region: str


@dataclass
class TasaDeReuso:
    """Lo aprendido sobre una región: cuántas veces se la volvió a pedir en la misma sesión."""

    observaciones: int = 0
    reusos: int = 0

    @property
    def tasa(self) -> float:
        return 0.0 if not self.observaciones else self.reusos / self.observaciones

    @property
    def suficiente(self) -> bool:
        return self.observaciones >= MIN_OBSERVACIONES

    def as_dict(self) -> dict[str, Any]:
        return {
            "observaciones": self.observaciones,
            "reusos": self.reusos,
            "tasa": round(self.tasa, 5),
            "suficiente": self.suficiente,
        }


@dataclass
class ModeloDeReuso:
    """El eje aprendido, por región, con lo que le faltó para aprenderse.

    `sin_sesion` NO ES UN CONTADOR DE ERRORES: es el resultado. Sobre un registro de turno
    único vale el total de las filas, y eso es la afirmación medible de que este eje **no
    se puede establecer en este banco**. Un modelo vacío con `sin_sesion = 0` significaría
    otra cosa —hubo secuencias y ninguna región se repitió— y confundir las dos es
    exactamente la clase de silencio que §78 arregló.
    """

    por_region: dict[str, TasaDeReuso] = field(default_factory=dict)
    sin_sesion: int = 0
    sesiones: int = 0
    # SESIONES DESCARTADAS POR ORDEN AMBIGUO. Una sesión con dos pedidos en la misma
    # posición no tiene precedencia definida, y este eje **es** una afirmación sobre
    # precedencia: «más adelante en la misma sesión». Ordenar por un campo empatado deja que
    # el orden del archivo decida quién vino antes, y eso mediría cómo se escribió el JSONL.
    # Se descarta la sesión entera y se cuenta, en vez de adivinar en silencio.
    sesiones_sin_orden: int = 0

    @property
    def establecible(self) -> bool:
        """Si el registro tiene la forma que este eje necesita. Independiente del resultado."""
        return (
            self.sesiones > 0
            and self.sin_sesion == 0
            and self.sesiones_sin_orden == 0
        )

    def belief_for(self, region: str) -> Belief | None:
        """La creencia sobre una región, o `None` si no se ganó el derecho a emitirla.

        `None` POR DOS MOTIVOS DISTINTOS y a propósito indistinguibles desde acá: la región
        no se observó, o se observó menos de `MIN_OBSERVACIONES` veces. Los dos significan
        «no hay creencia», y una creencia débil emitida con una credencia baja invita a
        confiar en lo que no se ganó — que es la advertencia que `beliefs.py` deja escrita
        sobre las credencias elicitadas mal calibradas. Quien quiera el detalle lee
        `por_region`; quien quiera decidir usa esto.

        SALE `COMPUTED` SOBRE `POPULATION`, y las dos mitades son honestas. `COMPUTED`
        porque es una división entre dos enteros contados sobre un ledger, sin modelo en el
        medio, y el retículo exige credencia 1,0 para esa procedencia — la incertidumbre no
        está en el número, está en que el número es sobre otros pedidos. `POPULATION` dice
        exactamente eso, y es lo que la deja afuera de cualquier acción irreversible.
        """
        stat = self.por_region.get(region)
        if stat is None or not stat.suficiente:
            return None
        return Belief(
            proposition=PROPOSITION,
            value=stat.tasa,
            credence=1.0,
            provenance=Provenance.COMPUTED,
            evidence=(
                f"{stat.reusos}/{stat.observaciones} pedidos de la región `{region}` "
                f"volvieron a pedirse en la misma sesión, sobre {self.sesiones} sesiones"
            ),
            scope=Scope.POPULATION,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "proposition": PROPOSITION,
            # SALE DEL REGISTRO, no de una constante repetida acá. Si alguien cambiara la
            # vía declarada, esta salida cambiaría con ella en vez de mentir en silencio.
            "acquisition": ACQUISITION[PROPOSITION].value,
            "establecible": self.establecible,
            "sesiones": self.sesiones,
            "sin_sesion": self.sin_sesion,
            "sesiones_sin_orden": self.sesiones_sin_orden,
            "por_region": {r: s.as_dict() for r, s in sorted(self.por_region.items())},
        }

    def porque_no(self) -> str:
        """El EXPLAIN de un eje que no se pudo establecer. Una frase, no un stacktrace."""
        if self.sin_sesion and not self.sesiones:
            return (
                f"registro de turno único: {self.sin_sesion:,} filas sin sesión y ninguna "
                f"secuencia. El eje no es medible en este corpus, por construcción del corpus"
            )
        if self.sin_sesion:
            return (
                f"registro mezclado: {self.sesiones:,} sesiones y {self.sin_sesion:,} filas "
                f"sin sesión. Una tasa sobre una muestra sesgada por quién trae la columna "
                f"no es una tasa"
            )
        if self.sesiones_sin_orden:
            return (
                f"{self.sesiones_sin_orden:,} sesiones descartadas por orden ambiguo: dos "
                f"pedidos en la misma posición no tienen precedencia, y este eje afirma "
                f"precedencia. Falta `turn` en la fila"
            )
        flacas = [r for r, s in self.por_region.items() if not s.suficiente]
        if flacas:
            return (
                f"{len(flacas)} de {len(self.por_region)} regiones por debajo del piso de "
                f"{MIN_OBSERVACIONES} observaciones: {', '.join(sorted(flacas)[:5])}"
            )
        return ""


def learn_reuse(traces: Iterable[Trace]) -> ModeloDeReuso:
    """Aprende la tasa de reuso por región. Aritmética sobre el ledger, cero llamadas.

    LA DEFINICIÓN OPERATIVA, y es la parte discutible que se escribe en vez de esconderse.
    Un pedido «se reusa» si **más adelante en la misma sesión** hay otro pedido de la misma
    región. No es la definición ideal —lo ideal sería que el segundo pedido consumiera lo
    que el primero estableció, y eso exige trazar la evidencia, no la región— pero es la que
    se puede contar sin un modelo en el medio, y es la que el ledger puede sostener.

    Con esa definición el ÚLTIMO pedido de cada sesión nunca cuenta como reusado, que es
    correcto: no hay nada después. Y una sesión de un solo pedido aporta una observación con
    cero reusos, que también es correcto — es evidencia de que esa región no encadena.

    Es el término `need` de Mattar & Daw (Nat Neuro 2018) computado sobre el registro: qué
    tan probable es que este estado haga falta después. Lo que falta para tener su `gain`
    —cuánto mejora una decisión futura por haberlo guardado— es la mitad que `P42` apuesta.
    """
    modelo = ModeloDeReuso()
    por_sesion: dict[str, list[Trace]] = defaultdict(list)

    for t in traces:
        if not t.session:
            modelo.sin_sesion += 1
            continue
        if not t.region:
            # Sin etiqueta no hay región, y aprender ahí sería fabricar una. Misma regla
            # que `policy.descartes`: no se cuenta como sesión ni como observación.
            continue
        por_sesion[t.session].append(t)

    for clave, pedidos in list(por_sesion.items()):
        ordenes = [t.orden for t in pedidos]
        if len(set(ordenes)) != len(ordenes):
            # Precedencia ambigua: ver `sesiones_sin_orden`. No se adivina, se descarta.
            modelo.sesiones_sin_orden += 1
            del por_sesion[clave]

    modelo.sesiones = len(por_sesion)
    for pedidos in por_sesion.values():
        pedidos.sort(key=lambda t: t.orden)
        for i, pedido in enumerate(pedidos):
            stat = modelo.por_region.setdefault(pedido.region, TasaDeReuso())
            stat.observaciones += 1
            if any(p.region == pedido.region for p in pedidos[i + 1:]):
                stat.reusos += 1

    return modelo


def traces_from_rows(rows: Iterable[dict[str, Any]]) -> list[Trace]:
    """Las trazas que un registro de resultados puede aportar. Hoy, ninguna con sesión.

    NO INVENTA LA COLUMNA. La tentación obvia es usar `task_id` como sesión, y sería una
    mentira con forma de dato: dos réplicas de la misma tarea no son dos pedidos
    encadenados, son la misma pregunta hecha de nuevo. Contarlas como reuso mediría el
    diseño del banco y lo reportaría como una propiedad del mundo.

    Una fila sin `session_id` entra con sesión vacía, y `learn_reuse` la cuenta en
    `sin_sesion`. Eso es lo que hace que la ausencia sea visible en vez de silenciosa.
    """
    return [
        Trace(
            session=str(r.get("session_id") or ""),
            orden=int(r.get("turn") or 0),
            region=str(r.get("region") or ""),
        )
        for r in rows
    ]
