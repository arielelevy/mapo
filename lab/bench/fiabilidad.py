"""`pass^k`: la fracción de celdas que aciertan en TODAS las réplicas. En un solo lugar.

QUÉ MIDE, Y POR QUÉ NO ES LO MISMO QUE LA UTILIDAD MEDIA. `pass@1` —el promedio sobre
réplicas, que es lo que todo el banco reporta— responde «¿cuántas veces acierta?». `pass^k`
responde **«¿se puede confiar en que acierte?»**, y son preguntas distintas: un brazo que
acierta 2 de 3 en muchas celdas y otro que acierta 3 de 3 en menos pueden tener el mismo
`pass@1` y comportarse al revés en producción.

DE DÓNDE SALE. Es la métrica que `tau2-bench` (Sierra, 2025) puso como acompañante estándar
de `pass@1` para agentes multi-turno, precisamente porque un agente que hace herramientas
compone su varianza: `pass@1 = 0,90` puede dar `pass^8 = 0,57`.

POR QUÉ FALTABA ACÁ, Y QUÉ DESTAPÓ. El banco tiene `repeat >= 3` desde el principio y usa
las réplicas para el **piso de ruido** —o sea, para saber si una diferencia entre brazos es
real—. Nunca las había usado para la pregunta inversa: cuánta de esa varianza vive DENTRO de
una celda. Medido sobre el registro completo, entre el **20% y el 31%** de las celdas de cada
brazo cambian de resultado entre réplicas.

Y ESO CORRIGE UNA AFIRMACIÓN NUESTRA. `CLAUDE.md` decía «determinismo casi al token
verificado» a partir de un smoke de UNA llamada por modelo. Es cierto **por llamada** y falso
**por trayectoria**: un bucle de herramientas amplifica cualquier desvío, porque una elección
distinta en el paso uno cambia todo lo que sigue. Se vio en vivo en `C3` h3: con la misma
huella y los mismos hits, la réplica 0 eligió `memo-058` (cadena entera, u=1,000) y las
réplicas 1 y 2 eligieron `memo-054` (u=0,000).

    `pass@1` dice si el brazo sabe. `pass^k` dice si el sistema es un sistema.

LO QUE NO MIDE. No distingue una celda que falla siempre de una que no se corrió: las dos
quedan fuera del numerador. Por eso `perfil()` devuelve también `n` y `inestables`, y ninguna
conclusión debería citar `pass^k` sin su denominador.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

# EL UMBRAL DE «ACERTÓ». Una celda con utilidad parcial —enumeró 3 de 4— no acertó, y
# tratarla como acierto convertiría `pass^k` en otro promedio. Se exige el máximo.
ACIERTO = 0.999


@dataclass(frozen=True)
class Fiabilidad:
    """El perfil de un brazo: cuánto acierta, y cuánto se puede contar con ello."""

    paradigma: str
    pass_1: float
    pass_k: float
    k: int
    n_celdas: int
    inestables: int

    @property
    def caida(self) -> float:
        """Cuánto se pierde al exigir consistencia. Es el número que importa."""
        return self.pass_k - self.pass_1

    @property
    def fraccion_inestable(self) -> float:
        return self.inestables / self.n_celdas if self.n_celdas else 0.0

    def linea(self) -> str:
        return (f"{self.paradigma:<16}{self.pass_1:>9.3f}{self.pass_k:>9.3f}"
                f"{self.caida:>+9.3f}{self.fraccion_inestable:>13.0%}{self.n_celdas:>8}")


def _por_celda(filas: Iterable[dict[str, Any]]) -> dict[tuple[str, str], list[float]]:
    celdas: dict[tuple[str, str], list[float]] = defaultdict(list)
    for f in filas:
        if f.get("infeasible") or f.get("infra_error"):
            continue
        celdas[(f["task_id"], f["paradigm"])].append(f.get("utility", 0.0))
    return celdas


def perfil(
    filas: Iterable[dict[str, Any]],
    k: int = 3,
    tareas: Sequence[str] | None = None,
    brazos: Sequence[str] | None = None,
) -> list[Fiabilidad]:
    """`pass@1` y `pass^k` por brazo, sobre las celdas que tienen al menos `k` réplicas.

    `tareas` y `brazos` son el panel: se pasan para que esto compare el mismo rectángulo
    que el resto del análisis. Sin ellos compara lo que haya, que es útil para diagnóstico
    y no para el marcador — la misma distinción que `bench/panel.py` existe para hacer
    cumplir.
    """
    celdas = _por_celda(filas)
    if tareas is not None or brazos is not None:
        ts = set(tareas) if tareas is not None else None
        bs = set(brazos) if brazos is not None else None
        celdas = {kk: v for kk, v in celdas.items()
                  if (ts is None or kk[0] in ts) and (bs is None or kk[1] in bs)}

    por_brazo: dict[str, list[list[float]]] = defaultdict(list)
    for (_, p), us in celdas.items():
        # SOLO LAS CELDAS CON `k` REPLICAS. Una celda con dos no puede contestar la
        # pregunta de `pass^3`, y rellenarla con lo que hay la contestaria que si.
        if len(us) >= k:
            por_brazo[p].append(us[:k])

    salida: list[Fiabilidad] = []
    for p, celdas_p in por_brazo.items():
        p1 = statistics.mean(statistics.mean(us) for us in celdas_p)
        pk = sum(1 for us in celdas_p if all(u >= ACIERTO for u in us)) / len(celdas_p)
        inest = sum(1 for us in celdas_p if 0.0 < statistics.mean(us) < 1.0)
        salida.append(Fiabilidad(p, p1, pk, k, len(celdas_p), inest))
    return sorted(salida, key=lambda f: -f.pass_1)


def imprimir(perfiles: Sequence[Fiabilidad], titulo: str = "") -> None:
    """La tabla, con el encabezado que explica cómo leerla."""
    if titulo:
        print(titulo)
    k = perfiles[0].k if perfiles else 3
    print(f"  {'brazo':<16}{'pass@1':>9}{f'pass^{k}':>9}{'caida':>9}"
          f"{'inestables':>13}{'celdas':>8}")
    for f in perfiles:
        print("  " + f.linea())
    if perfiles:
        peor = min(perfiles, key=lambda f: f.caida)
        print(f"\n  `pass@1` es cuantas veces acierta; `pass^{k}` es en cuantas celdas "
              f"acierta SIEMPRE.")
        print(f"  La caida es la varianza que vive DENTRO de una celda, con t=0 y la misma "
              f"huella —")
        print(f"  o sea la que ningun piso de ruido entre brazos muestra. La peor es "
              f"`{peor.paradigma}` ({peor.caida:+.3f}).")
