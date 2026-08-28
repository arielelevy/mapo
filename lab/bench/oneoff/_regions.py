"""Re-derivar la region de un episodio viejo bajo la regla y el vocabulario de hoy.

POR QUE HACE FALTA. La `region` que cada fila trae grabada se computo cuando la fila se
escribio: tres segmentos (`cardinalidad/oraculo/acoplamiento`) y el detector derivado del
gold. Hoy el vocabulario tiene cuatro —se agrego continuidad— y el detector se declara.
Comparar un registro viejo contra una decision de hoy sin re-derivar seria comparar dos
vocabularios distintos y llamarlo transferencia.

POR QUE NO SE REESCRIBEN LAS FILAS. Una fila es el registro de lo que paso. Se lee, no se
edita. La region, en cambio, es una FUNCION de los features — nunca fue un dato de la
corrida, y tenerla congelada adentro de la fila es lo que hizo que el problema pasara
desapercibido.

QUE SE CONSERVA Y QUE SE CORRIGE. El acoplamiento se CONSERVA del registro viejo: es lo
unico de esa etiqueta que costo una medicion, y volver a estimarlo seria inventarlo o
pagarlo de nuevo. Se corrige el segmento de oraculo (pasa a leer el detector declarado) y
se agrega el de continuidad, que es funcion pura del material y sale gratis.
"""


from __future__ import annotations

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
from functools import lru_cache
from typing import Any

from app.features import has_runtime_detector, measure_continuation


@lru_cache(maxsize=None)
def _corpus(corpus: str) -> tuple[dict, dict]:
    docs = json.load(open(f"corpus/{corpus}/documents.json", encoding="utf-8"))
    tasks = json.load(open(f"corpus/{corpus}/tasks.json", encoding="utf-8"))
    return docs, {t["task_id"]: t for t in tasks}


def continuation_segment(corpus: str, task_id: str) -> str:
    docs, tasks = _corpus(corpus)
    task = tasks.get(task_id)
    if task is None:
        return "c?"
    value = measure_continuation(docs, task["unit_ids"])
    return "c?" if value is None else ("chain" if value else "flat")


def rederive(corpus: str, task_id: str, recorded_region: str) -> str:
    """La region de hoy para un episodio de ayer.

    `recorded_region` aporta la cardinalidad y —lo importante— el ACOPLAMIENTO MEDIDO.
    El detector sale de la tarea, que ahora lo declara. La continuidad se computa.
    """
    parts = recorded_region.split("/")
    if len(parts) < 3:
        # Un registro mas viejo todavia: no hay acoplamiento que conservar.
        parts = parts + ["unknown"] * (3 - len(parts))
    cardinality, _stale_oracle, coupling = parts[0], parts[1], parts[2]

    _, tasks = _corpus(corpus)
    task = tasks.get(task_id)
    detector = "oracle" if (task and has_runtime_detector(task)) else "no_oracle"

    return f"{cardinality}/{detector}/{coupling}/{continuation_segment(corpus, task_id)}"


def rederived_episodes(runner: Any, corpus: str) -> list:
    """Los episodios de un corpus, con la region de hoy."""
    from dataclasses import replace as _replace

    return [
        _replace(e, region=rederive(corpus, e.task_id, e.region))
        for e in runner.episodes()
    ]
