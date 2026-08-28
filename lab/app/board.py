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


class Blackboard:
    """Shared state across sub-agents.

    Only what the control structure actually reads: findings, visited units, and a
    tool-call ledger used to avoid duplicated work between parallel agents.
    """

    findings: list[str] = field(default_factory=list)
    visited_units: set[str] = field(default_factory=set)
    tool_calls: set[str] = field(default_factory=set)

    def add_finding(self, sub_id: str, text: str) -> None:
        self.findings.append(f"[{sub_id}] {text.strip()}")

    def render(self) -> str:
        if not self.findings:
            return "(blackboard empty — you are the first agent)"
        lines = ["FINDINGS SO FAR (from parallel agents):"]
        lines.extend(f"  {f}" for f in self.findings)
        if self.visited_units:
            lines.append(f"UNITS ALREADY READ: {', '.join(sorted(self.visited_units))}")
        return "\n".join(lines)
