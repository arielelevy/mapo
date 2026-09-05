"""Workflows del spike. Código determinista: sin I/O, sin reloj del sistema, sin
random. Todo efecto pasa por una actividad."""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    import activities as act
    from shared import (
        AgentBranchInput,
        AgentBranchResult,
        FanOutInput,
        FanOutResult,
        IngestInput,
        IngestResult,
    )

ACT_TIMEOUT = timedelta(seconds=20)
# Sin heartbeat, un worker muerto recién se detecta al vencer start_to_close (20s).
# Con heartbeat_timeout el server lo da por caído en segundos y reprograma.
HEARTBEAT = timedelta(seconds=3)
RETRY = RetryPolicy(initial_interval=timedelta(milliseconds=200), maximum_attempts=4, backoff_coefficient=2.0)


def _rate_limit_until(err: BaseException) -> dt.datetime | None:
    """Si la actividad falló por límite con hora, devuelve esa hora (UTC)."""
    cause = getattr(err, "cause", None)
    if isinstance(cause, ApplicationError) and cause.type == "RateLimited" and cause.details:
        return dt.datetime.fromisoformat(str(cause.details[0]))
    return None


async def _call_with_rate_limit_timer(coro_factory, waited: list[float]):
    """Ejecuta una actividad; si devuelve RateLimited, duerme con un timer DURABLE
    hasta la hora indicada y vuelve a intentar. Es el `not_before` de la work table,
    pero sostenido por el server: sobrevive a un reinicio del worker."""
    while True:
        try:
            return await coro_factory()
        except ActivityError as err:
            until = _rate_limit_until(err)
            if until is None:
                raise
            delay = (until - workflow.now()).total_seconds()
            if delay > 0:
                workflow.logger.info("rate limited; timer durable de %.1fs hasta %s", delay, until.isoformat())
                waited.append(delay)
                await workflow.sleep(delay)


@workflow.defn
class IngestDocumentWorkflow:
    """parse → chunk → embed → index → verify → promote(flip live_pointer).
    El workflow id es el hash de contenido: dos ingestas del mismo PDF son UNA."""

    @workflow.run
    async def run(self, inp: IngestInput) -> IngestResult:
        waited: list[float] = []

        def a(fn, *args):
            return workflow.execute_activity(fn, args=list(args), start_to_close_timeout=ACT_TIMEOUT, heartbeat_timeout=HEARTBEAT, retry_policy=RETRY)

        pages = await a(act.parse, inp)
        chunk_ids = await a(act.chunk, inp, pages)
        n_embedded = await _call_with_rate_limit_timer(lambda: a(act.embed, inp, chunk_ids), waited)
        await a(act.index, inp, chunk_ids)
        ok = await a(act.verify, inp, n_embedded)
        promoted = False
        if ok:
            await a(act.promote, inp)
            promoted = True
        return IngestResult(
            doc_id=inp.doc_id,
            index_version=inp.index_version,
            chunks=len(chunk_ids),
            promoted=promoted,
            waited_for_rate_limit_s=round(sum(waited), 2),
        )


@workflow.defn
class FanOutAgentsWorkflow:
    """N ramas en paralelo (una actividad cada una), reintento por rama, una rama con
    fallo transitorio y otra con límite de uso; fan-in con reduce."""

    @workflow.run
    async def run(self, inp: FanOutInput) -> FanOutResult:
        waited: list[float] = []

        async def branch(i: int) -> AgentBranchResult:
            binp = AgentBranchInput(
                run_id=inp.run_id,
                branch=i,
                fail_transient_once=(i == 1),
                rate_limit_once=(i == 3),
            )
            return await _call_with_rate_limit_timer(
                lambda: workflow.execute_activity(
                    act.agent_step, binp, start_to_close_timeout=ACT_TIMEOUT, heartbeat_timeout=HEARTBEAT, retry_policy=RETRY
                ),
                waited,
            )

        results = list(await asyncio.gather(*(branch(i) for i in range(inp.branches))))
        best = await workflow.execute_activity(
            act.reduce_results, results, start_to_close_timeout=ACT_TIMEOUT, heartbeat_timeout=HEARTBEAT, retry_policy=RETRY
        )
        return FanOutResult(run_id=inp.run_id, results=results, best_branch=best, waited_for_rate_limit_s=round(sum(waited), 2))


ALL = [IngestDocumentWorkflow, FanOutAgentsWorkflow]
