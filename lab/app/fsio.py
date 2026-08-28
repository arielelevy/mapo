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


def _claim(lock: Path, owner: str) -> int:
    """Crear el lock de forma atomica y dejar adentro quien lo tiene."""
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, f"pid={os.getpid()} {owner}".strip().encode("utf-8"))
    except OSError:
        pass
    return fd


def _alive(held: str) -> bool:
    """Si el proceso que dice tener el lock sigue existiendo.

    Ante la duda devuelve True: reclamar un lock de una corrida VIVA duplicaria celdas,
    que es exactamente el dano que el lock existe para impedir. Errar hacia "sigue
    tomado" cuesta un borrado manual; errar hacia "esta libre" corrompe el registro.

    El riesgo residual es reciclado de PID: el sistema puede haberle dado ese numero a
    otro proceso. Se acepta a conciencia — la alternativa sería no reclamar nunca, y eso
    ya se probó hoy y bloqueó una reanudacion.
    """
    if not held.startswith("pid="):
        return True
    try:
        pid = int(held.split()[0].removeprefix("pid="))
    except (ValueError, IndexError):
        return True
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)  # senal 0: no hace nada, solo chequea existencia
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # existe y es de otro usuario
    except OSError as exc:
        # Windows no levanta ProcessLookupError para un PID inexistente: levanta
        # OSError con winerror 87 (ERROR_INVALID_PARAMETER). Sin este caso, un lock
        # huerfano se lee como vivo y no se reclama nunca — que es exactamente el
        # bloqueo que esta funcion existe para evitar, sobreviviendo al arreglo.
        if getattr(exc, "winerror", None) == 87:
            return False
        return True
    return True


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
        fd = _claim(lock, owner)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
        held = ""
        try:
            held = lock.read_text(encoding="utf-8").strip()
        except OSError:
            pass
        # HUERFANO. Una corrida que muere —matada, cortada, o el proceso que se cae—
        # deja el lock puesto, y sin esto un `Ctrl-C` bloquea TODAS las corridas
        # siguientes hasta que alguien borre un archivo oculto a mano. Eso convierte
        # una guarda contra duplicacion en una trampa, y se descubre en el peor momento:
        # justo cuando se quiere reanudar lo que se corto.
        if not _alive(held):
            try:
                lock.unlink()
                fd = _claim(lock, owner)
            except OSError:
                raise AlreadyRunning(
                    f"{path.name}: lock huerfano de {held or 'origen desconocido'} que "
                    f"no se pudo reclamar. Borrar {lock}."
                ) from exc
        else:
            raise AlreadyRunning(
                f"{path.name} ya lo tiene otra corrida VIVA ({held}). "
                f"Si estuviera equivocado, borrar {lock}."
            ) from exc
    try:
        os.close(fd)
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
