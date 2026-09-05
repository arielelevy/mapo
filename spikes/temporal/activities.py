"""Actividades del spike. Son stubs: no llaman a ningún modelo ni a Weaviate. Lo que
sí hacen es lo que el spike mide: registrar cada ejecución en el ledger, fallar de
forma controlada (transitoria o por límite con hora de reset) y hacer el flip del
`live_pointer` como último paso."""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import os
import random

from temporalio import activity
from temporalio.exceptions import ApplicationError

import shared
from shared import AgentBranchInput, AgentBranchResult, IngestInput

RATE_LIMIT_WAIT_S = 6.0  # el "try again at" del spike. En producción viene del 429.


def _wid() -> str:
    activity.heartbeat()  # el SDK lo throttlea; alcanza con marcar que el worker vive
    return activity.info().workflow_id


def _attempt() -> int:
    return activity.info().attempt


def _rate_limited(step: str) -> ApplicationError:
    retry_at = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=RATE_LIMIT_WAIT_S)
    # non_retryable: el reintento ciego del RetryPolicy no sirve acá. La hora la
    # decide el workflow con un timer durable, igual que haría con un Retry-After.
    return ApplicationError(
        f"{step}: usage limit, try again at {retry_at.isoformat()}",
        retry_at.isoformat(),
        type="RateLimited",
        non_retryable=True,
    )


# ---------------------------------------------------------------------------
# Ingesta: parse → chunk → embed → index → verify → promote
# ---------------------------------------------------------------------------

@activity.defn
async def parse(inp: IngestInput) -> int:
    shared.log_step(_wid(), "parse", _attempt())
    await asyncio.sleep(0.2)
    return 12  # páginas


@activity.defn
async def chunk(inp: IngestInput, pages: int) -> list[str]:
    shared.log_step(_wid(), "chunk", _attempt())
    await asyncio.sleep(0.2)
    return [hashlib.sha1(f"{inp.content_hash}:{i}".encode()).hexdigest()[:12] for i in range(pages * 3)]


@activity.defn
async def embed(inp: IngestInput, chunk_ids: list[str]) -> int:
    shared.log_step(_wid(), "embed", _attempt())
    if inp.rate_limit_once and _attempt() == 1 and not _seen(_wid(), "embed_rate_limited"):
        _mark(_wid(), "embed_rate_limited")
        raise _rate_limited("embed")
    await asyncio.sleep(0.3)
    return len(chunk_ids)


@activity.defn
async def index(inp: IngestInput, chunk_ids: list[str]) -> int:
    shared.log_step(_wid(), "index", _attempt())
    await asyncio.sleep(0.2)
    return shared.upsert_chunks(inp.index_version, chunk_ids, inp.content_hash)


@activity.defn
async def verify(inp: IngestInput, expected: int) -> bool:
    shared.log_step(_wid(), "verify", _attempt())
    await asyncio.sleep(0.2)
    return True


@activity.defn
async def promote(inp: IngestInput) -> int:
    # Punto de caída simulado: el worker muere ANTES de tocar el pointer, una sola vez.
    if shared.CRASH_FLAG.exists():
        shared.CRASH_FLAG.unlink()
        shared.log_step(_wid(), "promote:CRASH", _attempt())
        os._exit(3)
    shared.log_step(_wid(), "promote", _attempt())
    shared.flip_live_pointer(inp.index_version)
    return inp.index_version


# ---------------------------------------------------------------------------
# Fan-out de agentes: una rama = una actividad
# ---------------------------------------------------------------------------

@activity.defn
async def agent_step(inp: AgentBranchInput) -> AgentBranchResult:
    step = f"agent[{inp.branch}]"
    shared.log_step(_wid(), step, _attempt())
    if inp.fail_transient_once and _attempt() == 1:
        raise RuntimeError(f"{step}: fallo transitorio simulado")  # lo reintenta el RetryPolicy
    if inp.rate_limit_once and not _seen(_wid(), f"{step}_rate_limited"):
        _mark(_wid(), f"{step}_rate_limited")
        raise _rate_limited(step)
    await asyncio.sleep(random.uniform(0.2, 0.8))
    return AgentBranchResult(branch=inp.branch, score=round(random.random(), 3), attempts=_attempt(), worker_pid=os.getpid())


@activity.defn
async def reduce_results(results: list[AgentBranchResult]) -> int:
    shared.log_step(_wid(), "reduce", _attempt())
    return max(results, key=lambda r: r.score).branch


# ---------------------------------------------------------------------------
# marcas "una sola vez" fuera del proceso, para que el fallo simulado no se repita
# cuando el worker se reinicia
# ---------------------------------------------------------------------------

def _mark_path(wid: str, key: str):
    safe = hashlib.sha1(f"{wid}:{key}".encode()).hexdigest()[:16]
    return shared.HERE / f".mark_{safe}"


def _seen(wid: str, key: str) -> bool:
    return _mark_path(wid, key).exists()


def _mark(wid: str, key: str) -> None:
    _mark_path(wid, key).touch()


ALL = [parse, chunk, embed, index, verify, promote, agent_step, reduce_results]
