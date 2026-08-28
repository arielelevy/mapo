"""Atomic file writes, in one place.

Every cache and store in this harness used to `write_text` straight to the final
path. That is a torn-write bug wearing four different hats: a crash (or two workers
racing) leaves a truncated JSON at the final path, and from then on every run —
resumed and sealed included — explodes on `json.loads`, which the runner records as
a paradigm failure. The record poisons itself and the statistic, silently, forever.

The fix is the standard one and it is the same everywhere: write to a uniquely named
sibling, then `os.replace`, which is atomic on POSIX and on NTFS. Readers handle the
one remaining case — a file truncated by a write that predates this module — by
treating undecodable JSON as a miss, not as data.
"""

from __future__ import annotations

import errno
import os
import threading
from contextlib import contextmanager
from pathlib import Path


class AlreadyRunning(RuntimeError):
    """Otra corrida tiene tomado este archivo de resultados."""


@contextmanager
def exclusive(path: Path, owner: str = ""):
    """Un solo escritor por archivo de resultados, entre procesos.

    POR QUE NO ES PARANOIA. Dos corridas sobre el mismo corpus escriben las MISMAS
    celdas `(tarea, paradigma, trial)` en el mismo `.jsonl`, y `study()` promedia por
    celda contando cada fila: la celda duplicada pesa el doble y ninguna estadistica lo
    denuncia. No es una carrera de escritura que rompe el archivo — es una que lo deja
    perfectamente valido y silenciosamente mal ponderado, que es peor.

    `O_CREAT | O_EXCL` es atomico en NTFS y en POSIX, asi que el que gana crea el lock y
    el que pierde recibe una excepcion en vez de duplicar trabajo. El PID queda adentro
    para que un lock huerfano se pueda diagnosticar sin adivinar.
    """
    lock = path.with_name(f".{path.name}.lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
        held = ""
        try:
            held = lock.read_text(encoding="utf-8").strip()
        except OSError:
            pass
        raise AlreadyRunning(
            f"{path.name} ya lo tiene otra corrida ({held or 'sin datos'}). "
            f"Si es un lock huerfano, borrar {lock}."
        ) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as sink:
            sink.write(f"pid={os.getpid()} {owner}".strip())
        yield
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def write_atomic(path: Path, text: str) -> None:
    """Write `text` to `path` so that `path` never holds a partial file."""
    tmp = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
