"""Estado compartido entre sub-agentes: una DIMENSION, no un paradigma.

POR QUE VIVE ACA Y NO ADENTRO DE `dag.py`. Estaba definido dentro de `dag_strategy` y no
lo usaba nadie mas, y eso tiene una consecuencia medible: `dag_strategy` es el mejor
paradigma fijo en `gold_transfer` —el brazo contra el que el ruteo perdio en P15— y es la
UNICA estructura con blackboard. Asi que lo que el registro llama «el efecto
dag_strategy» es la conjuncion de dos cosas —la topologia de olas y el estado
compartido— y nada en el registro las separa.

Peor: mientras el blackboard viva adentro de un paradigma, la pregunta «¿`react` mejora
con estado compartido?» no se puede ni formular. El catalogo se distingue por ESTRUCTURA
DE CONTROL DE FLUJO; el estado compartido es otra dimension, y soldarla adentro de un
brazo convierte un factor en una propiedad del brazo.

Mover el modulo no mide nada por si solo — el comportamiento es identico y las suites lo
confirman. Lo que habilita es la medicion: `{con blackboard, sin}` x `{react,
dag_strategy}` sobre las celdas donde la descomposicion importa.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PendingItem:
    """Una unidad de trabajo del board: algo que hay que chequear, y si ya se chequeo."""

    label: str
    done: bool = False
    findings: str = ""


# DONDE ES FACTOR, Y UNA CORRECCION DE LO QUE ESCRIBI ANTES.
#
# Escribi que `{board, sin} x {react, dag}` no se podia construir: que en `react` era
# degenerado —un agente en un bucle, su transcripcion ya es el estado— y que en
# `map_reduce` seria otro patron. **Las dos mitades estaban mal**, y lo que las da vuelta
# es que el board sea una HERRAMIENTA disponible para todos (correccion del autor):
#
#   react          NO es redundante con la transcripcion, y el propio registro lo dice:
#                  bajo presupuesto el texto leido sobrevive al 28% hasta la llamada que
#                  responde (`note_retention`). Un board que el modelo escribe sobrevive
#                  la compactacion; la transcripcion no. Eso es un mecanismo, no un
#                  resumen de lo que el prompt ya contiene
#
#   map_reduce     con una TOOL no se vuelve secuencial. Cada map puede postear y el
#                  reduce leer, y ninguna llamada depende de otra salvo que el modelo
#                  elija leer. La topologia queda intacta, que es la definicion de factor
#
#   dag_strategy   ya tenia board estructural —lo escribe el CODIGO en cada ola— y eso es
#                  parte de su patron. La tool es otra cosa y comparte el MISMO objeto: si
#                  fueran dos, un sub-agente que postea no veria los hallazgos que el
#                  codigo asento, y habria dos «estados compartidos» a la vez
#
# ASI QUE SON DOS FACTORES DISTINTOS Y CONVIENE NO FUNDIRLOS:
#
#   shared_state   el board ESTRUCTURAL de dag, que escribe el codigo. Apagarlo deja las
#                  mismas olas y el mismo verify: es una dimension de esa topologia
#   offer_board    la TOOL, ofrecida a todos los patrones por igual. Es la que se cruza
#                  `{con, sin} x {patrones}`, porque es la unica que aplica a todos


@dataclass
class Blackboard:
    """Shared state across sub-agents.

    DOS COSAS DISTINTAS, Y HASTA EL 2026-08-29 SOLO ESTABA LA PRIMERA. Un board puede
    llevar **lo que pasó** —hallazgos, unidades leidas— o **lo que falta** —una cola de
    pendientes con su cobertura—. Son mecanismos distintos y el segundo es el que la
    medicion respalda: el 3,05× de §7.3 salio de una senal que dice *«no viene nada
    nuevo»*, que es una afirmacion sobre el trabajo RESTANTE, no sobre lo acumulado.

    Un board que solo acumula hallazgos no puede decir cobertura porque NO TIENE
    DENOMINADOR, y sin cobertura no puede emitir una directiva. Por eso la cola no es un
    campo mas: es lo que vuelve al board una senal de control en vez de un log.

    LA COLA VA DETRAS DE `queue_mode`, APAGADA POR DEFECTO. Con el flag en `False`,
    `render()` devuelve byte por byte lo que devolvia antes — el registro medido hasta
    hoy sigue siendo comparable, que es la unica forma de agregar una dimension a un
    banco a mitad de campana.
    """

    findings: list[str] = field(default_factory=list)
    visited_units: set[str] = field(default_factory=set)
    # EL LEDGER DE LLAMADAS, QUE ESTABA DECLARADO Y MUERTO. El docstring prometia «un
    # ledger de llamadas a herramientas para evitar trabajo duplicado entre agentes
    # paralelos» y el campo no lo escribia nadie ni lo renderizaba nada: la promesa
    # existia, el mecanismo no. Es la misma forma que «un factor que no llega al modelo
    # no existe», movida un nivel — un campo que no llega al render tampoco.
    tool_calls: list[str] = field(default_factory=list)
    pending: list[PendingItem] = field(default_factory=list)
    queue_mode: bool = False

    def add_finding(self, sub_id: str, text: str) -> None:
        self.findings.append(f"[{sub_id}] {text.strip()}")

    # -- la cola ----------------------------------------------------------

    def seed(self, labels: list[str]) -> None:
        """Sembrar la cola. El DENOMINADOR de la cobertura sale de aca.

        Lo siembra el CODIGO, no el modelo: una cobertura cuyo denominador propone el
        propio agente no es cobertura, es una opinion sobre cuanto queda.
        """
        vistos = {i.label for i in self.pending}
        self.pending.extend(PendingItem(label=l) for l in labels if l not in vistos)

    def close(self, label: str, findings: str = "") -> bool:
        """Cerrar un pendiente. Devuelve si cerro alguno.

        CERRAR NO ABRE. Anotar un hallazgo y abrir una pista eran una sola llamada en la
        capa anterior, asi que registrar algo YA SABIDO abria un item pendiente, bajaba
        la cobertura y disparaba mas insistencia. Una senal de contabilidad tiene que ser
        monotona en la direccion que premia, o castiga al agente por reportar lo que sabe.
        """
        for item in self.pending:
            if item.label == label and not item.done:
                item.done = True
                item.findings = findings[:600]
                return True
        return False

    def record_tool_call(self, name: str, args: str) -> bool:
        """Asentar una llamada. Devuelve `False` si ya estaba — o sea, si es repetida."""
        clave = f"{name}({args})"
        if clave in self.tool_calls:
            return False
        self.tool_calls.append(clave)
        return True

    @property
    def done_count(self) -> int:
        return sum(1 for i in self.pending if i.done)

    @property
    def pending_count(self) -> int:
        return len(self.pending) - self.done_count

    # -- render -----------------------------------------------------------

    def inject(self, messages: list) -> bool:
        """Poner el board en la conversacion, reemplazando el anterior. Devuelve si puso.

        ES LO QUE VUELVE GENERAL A LA COLA, y hasta el 2026-08-29 no existia. El board
        llegaba al modelo por DOS caminos y los dos eran particulares: la plantilla del
        sub-agente de `dag_strategy`, y el valor de retorno de la tool `board` — que el
        modelo tiene que acordarse de llamar, y llamo CERO veces en 46 celdas.

        Asi que un agente SOLO no podia llevar su propia cola de evidencia y pendientes:
        el factor se prendia, corria entero, y media cero. La forma exacta que este repo
        ya pago tres veces — un factor que no llega al modelo no falla, corre y mide su
        ausencia.

        La cola no es una propiedad de `dag`. Un agente en un bucle tiene el mismo
        problema que un grupo: no sabe que le falta, no sabe que ya pidio, y su
        transcripcion se compacta. Que el estado sea COMPARTIDO entre varios agentes o
        PROPIO de uno es una dimension distinta de si existe.

        REEMPLAZA EN VEZ DE APILAR. Un board por iteracion dejaria N copias del mismo
        estado en la ventana, cada una desactualizada, y la mas vieja arriba: el modelo
        leeria primero la version equivocada y el costo crece con el cuadrado de las
        vueltas.
        """
        texto = self.render()
        if not texto:
            return False
        envuelto = f"<estado>\n{texto}\n</estado>"
        for i in range(len(messages) - 1, -1, -1):
            m = messages[i]
            if m.get("role") == "user" and str(m.get("content", "")).startswith("<estado>"):
                messages[i] = {"role": "user", "content": envuelto}
                return True
        messages.append({"role": "user", "content": envuelto})
        return True

    def render(self) -> str:
        if not self.queue_mode:
            # EL CAMINO DE ANTES, INTACTO. No es una rama de conveniencia: el registro
            # medido hasta hoy se produjo con este texto exacto, y cambiarlo volveria
            # incomparables las filas viejas sin que nada lo denunciara.
            if not self.findings:
                return "(blackboard empty — you are the first agent)"
            lines = ["FINDINGS SO FAR (from parallel agents):"]
            lines.extend(f"  {f}" for f in self.findings)
            if self.visited_units:
                lines.append(
                    f"UNITS ALREADY READ: {', '.join(sorted(self.visited_units))}"
                )
            return "\n".join(lines)

        # EL BOARD COMO SENAL DE CONTROL: lo que falta primero, lo acumulado despues.
        total = len(self.pending)
        lines = [f"## Coverage: {self.done_count}/{total} items checked"] if total else []
        faltan = [i.label for i in self.pending if not i.done]
        if faltan:
            lines.append(
                "NOT checked (say so if the answer depends on them): "
                + "; ".join(faltan[:20])
                + (f" ... and {len(faltan) - 20} more" if len(faltan) > 20 else "")
            )
        if self.tool_calls:
            lines.append(f"## Already issued ({len(self.tool_calls)}) — do NOT repeat:")
            lines.extend(f"  - {c}" for c in self.tool_calls[-15:])
        if self.findings:
            lines.append("FINDINGS SO FAR (from parallel agents):")
            lines.extend(f"  {f}" for f in self.findings)
        if self.visited_units:
            lines.append(f"UNITS ALREADY READ: {', '.join(sorted(self.visited_units))}")
        if not lines:
            # EN MODO COLA, NADA QUE DECIR SE DICE CALLANDO. El texto de abajo —«sos el
            # primer agente»— habla de agentes paralelos, y la cola es GENERAL: un agente
            # solo la lleva igual, y ahi esa frase es falsa. Peor, inyectar un mensaje que
            # no informa nada gasta una posicion de la ventana en cada vuelta para decir
            # que no hay estado. `inject()` no pone nada cuando el render sale vacio.
            return ""
        # LA DIRECTIVA, que es lo que separa una senal de un reporte. Un numero de
        # cobertura no le dice al agente que hacer; esto si, y es DERIVADO del numero —
        # no una exhortacion suelta que diga lo mismo en cada iteracion.
        if total:
            lines.append(
                f"{self.pending_count} items remaining. Try DIFFERENT queries."
                if self.pending_count
                else "All items checked. Write your final answer."
            )
        return "\n".join(lines)
