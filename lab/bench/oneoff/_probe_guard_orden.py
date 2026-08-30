"""El guard y la cola sobre una tarea REAL del corpus, con cliente guionado.

QUE VALIDA, Y POR QUE NO ALCANZA CON EL TEST. `test_science.py` §62 prueba el guard sobre
una conversacion inventada: sirve para el mecanismo y NO para el ORDEN. Lo que puede
fallar en produccion y ningun unitario ve es la secuencia — que el guard corra antes de
inyectar, que el board que el modelo lee ya tenga el hallazgo recien rescatado, y que
nada se saltee entre una vuelta y la siguiente.

CERO COSTO Y CERO COLISION. El cliente es guionado: no hay llamada al modelo, no se toca
`results/`, y se puede correr con la campana en curso. Dos procesos appendeando al mismo
`.jsonl` es la falla que este repo ya se comio; esto no escribe ninguno.

QUE MIRA, en este orden:

  1. la SECUENCIA por vuelta: que vio el modelo, en que posicion, y de que tamano
  2. cuando disparo el guard, que expulso, y que hallazgo dejo
  3. que el board que el modelo lee en la vuelta N incluya lo rescatado en la vuelta N
  4. que NADA quede leido a medias: unidades leidas contra unidades cerradas en la cola

Corre DESDE `lab/`:  py bench/oneoff/_probe_guard_orden.py
"""

from __future__ import annotations

import json
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys
from dataclasses import dataclass, field
from typing import Any

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.llm import Usage
from app.runner import Runner

CORPUS = "gold_h1"


@dataclass
class _Completion:
    text: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    usage: Usage = field(default_factory=Usage)


class ClienteGuionado:
    """Devuelve un guion fijo. Cobra un poco, para que el gasto del guard se vea."""

    def __init__(self, guion: list[Any]) -> None:
        self.guion = guion
        self.vistas: list[list[dict[str, Any]]] = []
        self.i = 0

    def complete(self, messages, tools=None, **kw):
        # Se guarda una COPIA de lo que el modelo vio: la lista se muta en el lugar, asi
        # que guardar la referencia daria la version final en todas las vueltas — un
        # espejo que miente sobre el pasado.
        self.vistas.append([dict(m) for m in messages])
        paso = self.guion[min(self.i, len(self.guion) - 1)]
        self.i += 1
        if isinstance(paso, str):
            return _Completion(text=paso,
                               usage=Usage(prompt_tokens=120, completion_tokens=30))
        llamadas = [
            {"id": f"c{n}", "type": "function",
             "function": {"name": nombre, "arguments": json.dumps(args)}}
            for n, (nombre, args) in enumerate(paso)
        ]
        return _Completion(tool_calls=llamadas,
                           usage=Usage(prompt_tokens=120, completion_tokens=30))


def main() -> None:
    settings = Settings.from_env()
    tareas = json.loads(
        (_Path("corpus") / CORPUS / "tasks.json").read_text(encoding="utf-8")
    )
    tarea = next(t for t in tareas if "w16" in t["task_id"])
    print(f"tarea real: {tarea['task_id']} · {len(tarea['unit_ids'])} unidades")
    print(f"pregunta: {tarea['question'][:90]}\n")

    for etiqueta, kw in (("SIN guard ni cola", {}),
                         ("CON guard y cola", {"context_guard": True,
                                               "board_queue": True})):
        runner = Runner(settings, CORPUS, retriever_arm="hybrid",
                        surface_variant="basic", **kw)
        # LA MISMA superficie que construye la grilla. Una segunda construccion aca
        # seria una segunda definicion de lo que el agente puede ver.
        surface = runner.surface_for(tarea)

        unidades = list(surface.view.unit_ids)[:6]
        guion = [
            [("read", {"unit_ids": ",".join(unidades[:3])})],
            [("read", {"unit_ids": ",".join(unidades[3:6])})],
            [("search", {"query": "quien firmo"})],
            "la respuesta final",
        ]
        cliente = ClienteGuionado(guion)
        mensajes = [
            {"role": "system", "content": "sos un agente"},
            {"role": "user", "content": tarea["question"]},
        ]
        from app.paradigms import _run_tool_loop

        _run_tool_loop(cliente, surface, mensajes, max_iterations=6)

        print("=" * 74)
        print(f"{etiqueta}")
        print("=" * 74)
        for n, vista in enumerate(cliente.vistas, 1):
            tam = sum(len(str(m.get("content") or "")) for m in vista)
            board = [m for m in vista
                     if str(m.get("content") or "").startswith("<estado>")]
            expulsados = sum(1 for m in vista
                             if "[evicted" in str(m.get("content") or ""))
            print(f"  vuelta {n}: {len(vista):>2} mensajes · {tam:>7,} chars · "
                  f"board={'si' if board else 'no'} · expulsados={expulsados}")
            if board:
                primera = board[0]["content"].splitlines()[1:3]
                for l in primera:
                    print(f"            | {l[:80]}")
        g = surface.guard_stats or {}
        b = surface.board_state
        print(f"\n  guard: {g or '(apagado)'}")
        print(f"  board: {len(b.findings)} hallazgos · cola {b.done_count}/"
              f"{len(b.pending)} · {len(b.tool_calls)} llamadas asentadas")
        print(f"  unidades leidas: {len(surface.units_read)}")
        # LA GUARDA DE COHERENCIA: la cola no puede decir que cerro mas de lo que se
        # leyo. Si lo dijera, la cobertura estaria mintiendo y la directiva con ella.
        if b.queue_mode:
            coherente = b.done_count <= len(surface.units_read)
            print(f"  cerrados <= leidos: {'OK' if coherente else 'INCOHERENTE'}"
                  f"  ({b.done_count} <= {len(surface.units_read)})")
        print()


if __name__ == "__main__":
    main()
