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

import os
import threading
from pathlib import Path


def write_atomic(path: Path, text: str) -> None:
    """Write `text` to `path` so that `path` never holds a partial file."""
    tmp = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
