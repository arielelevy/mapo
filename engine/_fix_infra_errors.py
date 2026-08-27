"""Separar un fallo de infraestructura de un fallo del paradigma.

EL DEFECTO. `_run_one` atrapa toda excepcion y graba utility=0.0, con el comentario de que
"un paradigma que explota saca cero y esa es la utilidad honesta". Es cierto para un bug
del paradigma y FALSO para un 429: puntuar `reflection` en 0,000 porque Azure limito la
cuota del endpoint de embeddings es atribuirle una cuota a una topologia. Y como `study()`
promedia todas las filas de una celda, una fila envenenada arrastra la media hacia abajo.

Tres arreglos:

  1. embeddings.py respeta `Retry-After`. Azure dice exactamente cuanto esperar; hacer
     backoff de 2s cuando pidio 60 garantiza el proximo 429. Y agrega jitter, porque con
     workers=4 los cuatro hilos reintentaban en lockstep y volvian a colisionar.

  2. Row lleva `infra_error`, y `study()` excluye esas filas en vez de puntuarlas. La fila
     se sigue grabando -- que el fallo haya ocurrido es parte del registro -- pero no es
     una medicion.

  3. Purga las filas ya envenenadas.
"""

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent


def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for label, old, new in pairs:
        if old not in s:
            sys.exit(f"FAIL {path}/{label}: ancla ausente")
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print(f"  {path}: {len(pairs)} bloques")


# ---------------------------------------------------------------- 1. embeddings

patch("app/embeddings.py", [
    (
        "retry-after",
        """            if response.status_code not in RETRYABLE_STATUS or attempt == MAX_ATTEMPTS:
                break
            time.sleep(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))""",
        """            if response.status_code not in RETRYABLE_STATUS or attempt == MAX_ATTEMPTS:
                break
            # Azure states how long to wait on a 429. Backing off 2 seconds when it asked
            # for 60 guarantees the next 429, so the header wins when it is present.
            wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
            hinted = response.headers.get("retry-after")
            if hinted:
                try:
                    wait = max(wait, float(hinted))
                except ValueError:
                    pass
            # Jitter: with several workers the threads back off on the same schedule and
            # collide again on the retry. Spreading them is what actually clears a burst.
            time.sleep(wait * (1.0 + random.random() * 0.5))""",
    ),
    (
        "import-random",
        "import math",
        "import math\nimport random",
    ),
])

# ---------------------------------------------------------------- 2. runner

patch("app/runner.py", [
    (
        "row-field",
        "    truth_coupling: float\n    error: str = \"\"",
        "    truth_coupling: float\n    error: str = \"\"\n"
        "    # An infrastructure failure is not a measurement. A 429 from the embedding\n"
        "    # endpoint says nothing about the topology, so these rows are recorded and\n"
        "    # then excluded from every statistic rather than scored as a wrong answer.\n"
        "    infra_error: bool = False",
    ),
    (
        "classifier",
        "@dataclass\nclass Row:",
        '''def _is_infrastructure(exc: BaseException) -> bool:
    """Whether this failure belongs to the transport rather than to the paradigm.

    Deliberately narrow. Anything not clearly infrastructural stays a paradigm failure
    and still scores zero, because the opposite mistake -- excusing a real bug as a
    network blip -- flatters the paradigm, which is the error this harness exists to
    avoid.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return isinstance(exc, (httpx.TransportError, httpx.StreamError))


@dataclass
class Row:''',
    ),
    (
        "imports",
        "from .config import Settings",
        "import httpx\n\nfrom .config import Settings\nfrom .llm import RETRYABLE_STATUS",
    ),
    (
        "error-row",
        """        except Exception as exc:  # noqa: BLE001
            # A paradigm that blows up on a task scores zero for that task. That is
            # the honest utility, and hiding the failure would flatter the paradigm.
            return Row(""",
        """        except Exception as exc:  # noqa: BLE001
            # A paradigm that blows up on a task scores zero for that task. That is the
            # honest utility, and hiding the failure would flatter the paradigm -- but
            # only when the failure is the paradigm's. A rate limit or a dropped
            # connection is the transport's, and scoring it as a wrong answer attributes
            # someone else's quota to a topology.
            infra = _is_infrastructure(exc)
            return Row(""",
    ),
    (
        "error-row-field",
        """                error=f"{type(exc).__name__}: {exc}"[:300],
            )""",
        """                error=f"{type(exc).__name__}: {exc}"[:300],
                infra_error=infra,
            )""",
    ),
    (
        "study-exclusion",
        """        cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for r in self.load_rows():
            cells.setdefault((r["task_id"], r["paradigm"]), []).append(r)""",
        """        cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
        dropped = 0
        for r in self.load_rows():
            # An infrastructure failure is not evidence about a paradigm. Averaging it in
            # would drag the cell down by however much of the quota someone else used.
            if r.get("infra_error"):
                dropped += 1
                continue
            cells.setdefault((r["task_id"], r["paradigm"]), []).append(r)
        if dropped:
            print(
                f"  [study] {dropped} filas excluidas por fallo de infraestructura "
                f"(no son mediciones)"
            )""",
    ),
])

# ---------------------------------------------------------------- 3. purga

print()
purged = 0
for f in sorted((ROOT / "results").glob("*_rows.jsonl")):
    rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    keep = []
    for r in rows:
        err = r.get("error") or ""
        poisoned = bool(err) and r.get("cost_tokens", 0) == 0 and not r.get("infeasible")
        if poisoned and re.search(r"429|Too Many Requests|Timeout|ConnectError|ReadError", err):
            purged += 1
            continue
        keep.append(r)
    if len(keep) != len(rows):
        f.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in keep) + "\n",
            encoding="utf-8",
        )
        print(f"  {f.name}: {len(rows) - len(keep)} filas envenenadas purgadas "
              f"({len(keep)} quedan)")
print(f"\ntotal purgado: {purged}")
print("listo")
