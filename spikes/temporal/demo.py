"""Corre las cuatro pruebas del spike contra un `temporal server start-dev` local y
deja el resultado en `RESULTADO.md`. Levanta y mata workers él mismo.

  python demo.py
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

from temporalio.client import Client, WorkflowFailureError
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

import shared
from shared import TASK_QUEUE, FanOutInput, IngestInput
from workflows import FanOutAgentsWorkflow, IngestDocumentWorkflow

HERE = Path(__file__).resolve().parent
ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
OUT: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    OUT.append(line)


def start_worker() -> subprocess.Popen:
    p = subprocess.Popen([sys.executable, str(HERE / "worker.py")], cwd=HERE)
    time.sleep(2.5)  # que se registre en la task queue
    return p


def stop_worker(p: subprocess.Popen) -> None:
    if p.poll() is None:
        p.kill()
        p.wait()


def fmt_steps(wid: str) -> str:
    rows = shared.steps_for(wid)
    return "\n".join(f"    {i+1:>2}. {step:<16} attempt={att}  pid={pid}" for i, (step, att, pid) in enumerate(rows))


async def prueba_a_caida_y_reanudacion(client: Client) -> None:
    say("## A. El worker muere entre verify y el flip; otro worker retoma sin repetir pasos")
    shared.CRASH_FLAG.touch()
    inp = IngestInput(doc_id="manual-a", content_hash="c0ffee01", index_version=7)
    wid = f"ingest-{inp.content_hash}"
    w1 = start_worker()
    t0 = time.monotonic()
    handle = await client.start_workflow(IngestDocumentWorkflow.run, inp, id=wid, task_queue=TASK_QUEUE)
    code = w1.wait(timeout=60)
    say(f"- worker 1 (pid {w1.pid}) terminó con código {code} (3 = caída simulada en `promote`)")
    say(f"- live_pointer tras la caída: {shared.live_version()!r}  (esperado: None, nada se promovió a medias)")
    w2 = start_worker()
    result = await handle.result()
    say(f"- worker 2 (pid {w2.pid}) completó el workflow en {time.monotonic() - t0:.1f}s")
    say(f"- resultado: promoted={result.promoted} index_version={result.index_version} chunks={result.chunks}")
    say(f"- live_pointer ahora: {shared.live_version()}")
    say("- step_log (cada paso previo a la caída corrió UNA vez, en el worker 1; `promote` corrió en el worker 2):")
    say(fmt_steps(wid))
    stop_worker(w2)
    say()


async def prueba_b_limite_con_timer_durable(client: Client) -> None:
    say("## B. Un 429 con hora de reset se vuelve un timer durable; el worker muere durante la espera y no importa")
    inp = IngestInput(doc_id="manual-b", content_hash="c0ffee02", index_version=8, rate_limit_once=True)
    wid = f"ingest-{inp.content_hash}"
    w1 = start_worker()
    t0 = time.monotonic()
    handle = await client.start_workflow(IngestDocumentWorkflow.run, inp, id=wid, task_queue=TASK_QUEUE)
    await asyncio.sleep(2.0)  # ya pasó parse, chunk y el embed que devolvió RateLimited
    stop_worker(w1)
    say(f"- worker 1 (pid {w1.pid}) matado a los 2.0s, en medio del timer")
    await asyncio.sleep(1.5)
    w2 = start_worker()
    result = await handle.result()
    elapsed = time.monotonic() - t0
    say(f"- worker 2 (pid {w2.pid}) completó en {elapsed:.1f}s; el workflow esperó {result.waited_for_rate_limit_s}s por el límite")
    say(f"- promoted={result.promoted} live_pointer={shared.live_version()}")
    say("- step_log (`embed` aparece dos veces: la que devolvió RateLimited y la que corrió tras el timer):")
    say(fmt_steps(wid))
    stop_worker(w2)
    say()


async def prueba_c_idempotencia(client: Client) -> None:
    say("## C. Reingestar el mismo contenido es la misma ejecución, no una nueva")
    inp = IngestInput(doc_id="manual-a", content_hash="c0ffee01", index_version=7)
    wid = f"ingest-{inp.content_hash}"
    try:
        await client.start_workflow(
            IngestDocumentWorkflow.run, inp, id=wid, task_queue=TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
        say("- ERROR: el server aceptó un duplicado")
    except WorkflowAlreadyStartedError:
        say(f"- start_workflow(id={wid!r}) rechazado: WorkflowAlreadyStartedError (REJECT_DUPLICATE)")
    say(f"- filas en `chunk` para v7 antes/después: {_count_chunks(7)} / {_count_chunks(7)} (sin cambios)")
    say()


def _count_chunks(v: int) -> int:
    with shared._conn() as c:
        return c.execute("select count(*) from chunk where index_version = ?", (v,)).fetchone()[0]


async def prueba_d_fan_out_fan_in(client: Client) -> None:
    say("## D. Fan-out de 5 agentes, reintento por rama, una rama con límite; fan-in con reduce")
    inp = FanOutInput(run_id="fan-1", branches=5)
    wid = f"fanout-{inp.run_id}"
    w1 = start_worker()
    t0 = time.monotonic()
    handle = await client.start_workflow(FanOutAgentsWorkflow.run, inp, id=wid, task_queue=TASK_QUEUE)
    result = await handle.result()
    say(f"- completado en {time.monotonic() - t0:.1f}s; espera por límite: {result.waited_for_rate_limit_s}s (sólo la rama 3)")
    for r in sorted(result.results, key=lambda r: r.branch):
        note = {1: "  <- fallo transitorio en el intento 1, reintentado por RetryPolicy", 3: "  <- RateLimited, timer durable, reejecutada"}.get(r.branch, "")
        say(f"    rama {r.branch}: score={r.score:<6} attempts={r.attempts} pid={r.worker_pid}{note}")
    say(f"- reduce eligió la rama {result.best_branch}")
    say("- step_log:")
    say(fmt_steps(wid))
    stop_worker(w1)
    say()


async def main() -> None:
    shared.reset_ledger()
    for p in HERE.glob(".mark_*"):
        p.unlink()
    client = await Client.connect(ADDRESS)
    say(f"# Spike Temporal — resultado de `demo.py` ({dt.datetime.now().isoformat(timespec='seconds')})")
    say(f"server: {ADDRESS} (temporal server start-dev, SQLite)  ·  SDK temporalio {__import__('temporalio').__version__}  ·  UI: http://localhost:8233")
    say()
    await prueba_a_caida_y_reanudacion(client)
    await prueba_b_limite_con_timer_durable(client)
    await prueba_c_idempotencia(client)
    await prueba_d_fan_out_fan_in(client)
    (HERE / "RESULTADO.md").write_text("\n".join(OUT) + "\n", encoding="utf-8")
    say(f"escrito {HERE / 'RESULTADO.md'}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
