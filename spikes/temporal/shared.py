"""Tipos y ledger del spike. Nada de esto es producto: es lo mínimo para que las
pruebas del README sean verificables contra un archivo y no contra la consola."""

from __future__ import annotations

import datetime as dt
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

TASK_QUEUE = "mapo-spike"
HERE = Path(__file__).resolve().parent
LEDGER_PATH = HERE / "spike_ledger.db"
CRASH_FLAG = HERE / ".crash_after_verify"


# ---------------------------------------------------------------------------
# Contratos de datos (serializables por el converter por defecto del SDK)
# ---------------------------------------------------------------------------

@dataclass
class IngestInput:
    doc_id: str
    content_hash: str
    index_version: int
    rate_limit_once: bool = False  # simula un 429 con hora de reset en `embed`


@dataclass
class IngestResult:
    doc_id: str
    index_version: int
    chunks: int
    promoted: bool
    waited_for_rate_limit_s: float


@dataclass
class AgentBranchInput:
    run_id: str
    branch: int
    fail_transient_once: bool = False
    rate_limit_once: bool = False


@dataclass
class AgentBranchResult:
    branch: int
    score: float
    attempts: int
    worker_pid: int


@dataclass
class FanOutInput:
    run_id: str
    branches: int = 5


@dataclass
class FanOutResult:
    run_id: str
    results: list[AgentBranchResult] = field(default_factory=list)
    best_branch: int = -1
    waited_for_rate_limit_s: float = 0.0


# ---------------------------------------------------------------------------
# Ledger: hace las veces del Postgres del producto para lo que el spike mide
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(LEDGER_PATH, timeout=10)
    c.execute("pragma journal_mode=wal")
    c.execute(
        """create table if not exists step_log (
             seq integer primary key autoincrement,
             workflow_id text not null,
             step text not null,
             attempt integer not null,
             worker_pid integer not null,
             at text not null)"""
    )
    c.execute(
        """create table if not exists live_pointer (
             id integer primary key check (id = 1),
             index_version integer not null,
             flipped_at text not null)"""
    )
    c.execute(
        """create table if not exists chunk (
             index_version integer not null,
             chunk_id text not null,
             content_hash text not null,
             primary key (index_version, chunk_id))"""
    )
    return c


def log_step(workflow_id: str, step: str, attempt: int) -> None:
    with _conn() as c:
        c.execute(
            "insert into step_log(workflow_id, step, attempt, worker_pid, at) values (?,?,?,?,?)",
            (workflow_id, step, attempt, os.getpid(), dt.datetime.now(dt.UTC).isoformat(timespec="milliseconds")),
        )


def steps_for(workflow_id: str) -> list[tuple[str, int, int]]:
    with _conn() as c:
        return c.execute(
            "select step, attempt, worker_pid from step_log where workflow_id = ? order by seq", (workflow_id,)
        ).fetchall()


def upsert_chunks(index_version: int, chunk_ids: list[str], content_hash: str) -> int:
    """Idempotente: reingestar el mismo contenido no crea filas nuevas."""
    with _conn() as c:
        before = c.execute("select count(*) from chunk where index_version = ?", (index_version,)).fetchone()[0]
        c.executemany(
            "insert or ignore into chunk(index_version, chunk_id, content_hash) values (?,?,?)",
            [(index_version, cid, content_hash) for cid in chunk_ids],
        )
        after = c.execute("select count(*) from chunk where index_version = ?", (index_version,)).fetchone()[0]
    return after - before


def flip_live_pointer(index_version: int) -> None:
    with _conn() as c:
        c.execute(
            "insert into live_pointer(id, index_version, flipped_at) values (1, ?, ?) "
            "on conflict(id) do update set index_version = excluded.index_version, flipped_at = excluded.flipped_at",
            (index_version, dt.datetime.now(dt.UTC).isoformat(timespec="milliseconds")),
        )


def live_version() -> int | None:
    with _conn() as c:
        row = c.execute("select index_version from live_pointer where id = 1").fetchone()
    return row[0] if row else None


def reset_ledger() -> None:
    if LEDGER_PATH.exists():
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(LEDGER_PATH) + suffix)
            if p.exists():
                p.unlink()
    if CRASH_FLAG.exists():
        CRASH_FLAG.unlink()
