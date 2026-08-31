"""EL PANEL: qué tareas y qué brazos entran en una comparación. En UN solo lugar.

POR QUÉ EXISTE. Cinco análisis y un test definían el rectángulo cada uno por su cuenta, con
la misma regla escrita seis veces: «los brazos presentes en ≥95% de las tareas medidas, y
después las tareas donde están todos». Funcionó mientras la cobertura fue pareja.

**Dejó de funcionar en el momento en que un brazo tuvo MÁS cobertura que el resto.** Al
re-correr `rewoo` sobre las 78 tareas —mientras los otros once seguían en 46— la regla
amplió el conjunto de tareas a 78, y entonces **ningún otro brazo llegaba al 95%**: el panel
colapsó a `rewoo` solo. Los cinco análisis empezaron a comparar un brazo contra sí mismo y el
marcador reportó `oráculo = mejor fijo = política`, todo `0,692`, sin quejarse de nada.

    Una regla de selección escrita seis veces se rompe seis veces, el mismo día, por la
    misma razón — y ninguna de las seis lo dice.

LA REGLA, y el orden importa:

  1. **primero las tareas RICAS**: las que tienen al menos `MIN_BRAZOS` brazos medidos. Es lo
     que impide que una tarea que corrió un solo brazo arrastre la definición
  2. después los brazos que cubren casi todas ESAS
  3. y al final las tareas donde están todos esos brazos

El paso 1 es el que faltaba. Sin él, la cobertura desigual de un brazo redefine el universo.

Y DEVUELVE EL DESCARTE, no sólo el rectángulo: un panel que se achica sin decir cuánto es un
panel que miente por omisión — hoy son 41 de 78 tareas, y esa proporción es la que acota toda
conclusión que salga de acá.
"""

from __future__ import annotations

import collections
from dataclasses import dataclass, field
from typing import Any, Sequence

# Cuántos brazos tiene que tener una tarea para contar como medida de verdad. Ocho de los
# doce brazos corren siempre; por debajo de siete, la tarea la corrió un experimento
# parcial y no la campaña.
MIN_BRAZOS = 7

# Qué fracción de las tareas ricas tiene que cubrir un brazo para entrar.
COBERTURA_MINIMA = 0.95


@dataclass(frozen=True)
class Panel:
    """El rectángulo de una comparación, y lo que quedó afuera.

    `tareas` × `brazos` es sobre lo que se puede comparar. `descartadas` y `motivo` están
    para que ninguna conclusión se reporte sin su denominador.
    """

    tareas: list[str]
    brazos: list[str]
    descartadas: list[str] = field(default_factory=list)
    total_medidas: int = 0

    @property
    def cobertura(self) -> float:
        return len(self.tareas) / self.total_medidas if self.total_medidas else 0.0

    def descripcion(self) -> str:
        return (f"{len(self.tareas)} tareas x {len(self.brazos)} brazos "
                f"({self.cobertura:.0%} de las {self.total_medidas} medidas)")


def rectangulo(
    filas: Sequence[dict[str, Any]],
    roster: Sequence[str] | None = None,
    excluir: set[str] | None = None,
    min_brazos: int = MIN_BRAZOS,
) -> Panel:
    """El mayor rectángulo comparable del registro. Ver el docstring del módulo.

    `filas` son filas ya cargadas con `load_rows` (que ya excluye `infra_error`). Las
    `infeasible` se descartan acá: un brazo podado no midió nada, y contarlo como presente
    haría que una tarea pareciera cubierta por brazos que no corrieron.
    """
    excluir = excluir or set()
    por_tarea: dict[str, set[str]] = collections.defaultdict(set)
    for f in filas:
        if f.get("infeasible"):
            continue
        por_tarea[f["task_id"]].add(f["paradigm"])

    medidas = {t: b for t, b in por_tarea.items() if t not in excluir}
    # PASO 1, el que faltaba: sólo las tareas que corrió la campaña, no las de un
    # experimento parcial. Sin esto, un brazo con más cobertura redefine el universo.
    ricas = {t: b for t, b in medidas.items() if len(b) >= min_brazos}
    if not ricas:
        return Panel([], [], sorted(medidas), len(medidas))

    candidatos = roster or sorted({p for b in ricas.values() for p in b})
    brazos = [p for p in candidatos
              if sum(p in b for b in ricas.values()) >= COBERTURA_MINIMA * len(ricas)]
    tareas = sorted(t for t, b in ricas.items() if all(p in b for p in brazos))
    descartadas = sorted(set(medidas) - set(tareas))
    return Panel(tareas, sorted(brazos), descartadas, len(medidas))
