"""Compatibilidad: el blackboard vive en `app/board.py`.

SE MUDO PORQUE `tools.py` LO NECESITA. El board es una herramienta disponible para todos
los patrones (correccion del autor, 2026-08-28), y `app/tools.py` no puede importar de
`app/paradigms/` sin ciclo: `paradigms/__init__` importa `tools`. Un modulo de nivel
superior lo rompe, y este archivo queda para que nada que ya importaba de aca se rompa.
"""

from __future__ import annotations

from ..board import Blackboard

__all__ = ["Blackboard"]
