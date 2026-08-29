"""Cuantas celdas y cuantos tokens va a costar una corrida — contados del CORPUS.

DE DONDE SALE (leccion 8.9, y otra vez el 2026-08-29). `P26` se estimo en 362k leyendo un
archivo de resultados que era **parcial** —90 filas sobre 6 de 32 tareas— y costo 12,2M:
error de **34x**. El mismo dia, su docstring estimo la corrida entera en 792k contra 12,4M
reales: **18x**. Las dos veces la aritmetica estuvo bien y la ENTRADA estuvo mal.

LA REGLA ES UNA: **el conteo de celdas sale del corpus, nunca de un archivo de resultados.**
`len(tasks.json) x paradigmas x brazos x repeat` es aritmetica que no se puede equivocar
asi. Un archivo de resultados **no declara si esta completo** — no hay campo que diga «esto
es todo», y una corrida que murio a la mitad se lee exactamente igual que una que termino.

QUE SI PUEDE VENIR DEL REGISTRO: el costo POR CELDA de cada paradigma, que es una medida y
no un conteo. Y cuando no hay registro para un paradigma, se dice **SIN N** en vez de
poner un promedio de otros: un paradigma sin medir puede costar 30x lo que el mas barato
—`dag_strategy` contra `rewoo` es exactamente eso— asi que rellenarlo con la media es
inventar el numero que se esta pidiendo.

EL CACHE ES UNA DECLARACION, NO UN SUPUESTO. Cambiar de brazo de recuperacion devuelve
otras unidades, asi que los prompts son otros y el cache **no ayuda**. La estimacion de P26
tenia ese parrafo escrito en su propio docstring y la suma no lo uso. Aca hay que pasarlo,
y el valor viaja adentro del reporte para que quede dicho cual se supuso.
"""

from __future__ import annotations

# Corre DESDE `lab/`, y tambien se importa como `bench._estimate`. El prologo solo resuelve
# los imports de `app.*` cuando esto arranca como script: ahi el que entra a `sys.path` es
# `bench/`, no `lab/`, y `from app.feasibility import check` no encuentra nada.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Estimate:
    cells: int
    tasks: int
    tokens: float | None
    per_paradigm: dict[str, float | None]
    unmeasured: tuple[str, ...]
    cache: str

    def render(self) -> str:
        lines = [
            f"celdas: {self.cells:,}  ({self.tasks} tareas del corpus, contadas del corpus)",
            f"cache supuesto: {self.cache}",
        ]
        for name, cost in sorted(self.per_paradigm.items()):
            if cost is None:
                lines.append(f"  {name:<16} SIN N — nunca se corrio, no se estima")
            else:
                lines.append(f"  {name:<16} {cost:>10,.0f} tokens/celda (mediana medida)")
        if self.tokens is None:
            lines.append(
                "TOTAL: SIN N — "
                f"{len(self.unmeasured)} paradigma(s) sin medir ({', '.join(self.unmeasured)}). "
                "Rellenarlos con la media de los otros inventaria el numero que se pide: "
                "entre el mas caro y el mas barato del catalogo hay ~30x."
            )
        else:
            lines.append(f"TOTAL: {self.tokens:,.0f} tokens")
        return "\n".join(lines)


def count_tasks(corpus: str | Path) -> int:
    """Cuantas tareas tiene el corpus. La UNICA fuente valida del conteo de celdas."""
    path = Path(corpus)
    if path.is_dir():
        path = path / "tasks.json"
    if path.suffix != ".json" or "results" in path.parts:
        # LA GUARDA ES EL PUNTO DEL MODULO. Sin esto, pasar un `.jsonl` de resultados
        # "funciona" y devuelve un numero — que es el modo de falla que costo 34x.
        raise ValueError(
            f"{path} no es un corpus. El conteo de celdas sale de `tasks.json`, nunca de "
            f"un archivo de resultados: un .jsonl no declara si esta completo, y una "
            f"corrida que murio a la mitad se lee igual que una que termino."
        )
    tasks = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(tasks, dict):
        tasks = list(tasks.values())
    return len(tasks)


def measured_cost(rows: Iterable[dict[str, Any]]) -> dict[str, float]:
    """Costo MEDIANO por celda y paradigma, del registro.

    Mediana y no media: una sola celda que se fue de mambo —`dag_strategy` tiene filas de
    176k contra una mediana de ~50k— arrastra la media y la estimacion sale alta justo
    donde no hay que equivocarse. El conteo de celdas NO sale de aca.
    """
    por = defaultdict(list)
    for row in rows:
        if row.get("error") or row.get("infra_error"):
            continue
        por[row["paradigm"]].append(row.get("cost_tokens", 0))
    return {p: statistics.median(v) for p, v in por.items() if v}


def estimate(
    corpus: str | Path,
    paradigms: list[str],
    arms: list[str],
    repeat: int,
    costs: dict[str, float],
    cache: str = "frio",
) -> Estimate:
    """Cota de la corrida. `cache` es una DECLARACION del que llama, no un supuesto de aca.

    `frio` es el default a proposito: es el caso que se subestimo las dos veces. Cambiar de
    brazo devuelve otras unidades, asi que los prompts son otros y no hay cache que valga.
    """
    if repeat < 1:
        raise ValueError("repeat >= 1")
    if cache not in ("frio", "caliente"):
        raise ValueError(f"cache invalido: {cache!r}")
    tasks = count_tasks(corpus)
    cells = tasks * len(paradigms) * len(arms) * repeat
    per = {p: costs.get(p) for p in paradigms}
    unmeasured = tuple(sorted(p for p, c in per.items() if c is None))
    if unmeasured:
        total = None
    else:
        # `caliente` no se modela como un descuento inventado: se declara que las celdas
        # ya pagadas no se recobran, y quien llama decide cuantas son. Sin ese dato el
        # unico numero honesto es la cota SUPERIOR, que es lo que devuelve.
        total = sum(per[p] * tasks * repeat * len(arms) for p in paradigms)
    return Estimate(cells, tasks, total, per, unmeasured, cache)


# -- la campana de hoy, estimada como comando -------------------------------------------
#
# ESTO REEMPLAZA A `bench/runs/_estimate.py`, borrado el 2026-08-29. Eran DOS estimadores
# con contenido distinto, y sólo éste se importaba (`test_science.py` §…). El otro tenía un
# `main()` clavado a `gold_guards` con cuatro paradigmas — la campaña de factores, que ya no
# es el plan. Dos archivos que estiman lo mismo empiezan a estimar cosas distintas, y el que
# nadie importa es el que se queda viejo sin que nadie se entere.

CORPUS_CAMPANA = "corpus/gold_h1"
NO_SE_CORREN = ("cot", "plan_execute")
# ~4 caracteres por token. Sirve para DIMENSIONAR, no para cobrar, y por eso alcanza.
CHARS_POR_TOKEN = 4


def _material_por_tarea(corpus: str | Path) -> dict[str, int]:
    """Tokens de material que declara cada tarea. Del CORPUS, que sí dice su tamaño."""
    raiz = Path(corpus)
    docs = json.loads((raiz / "documents.json").read_text(encoding="utf-8"))
    tareas = json.loads((raiz / "tasks.json").read_text(encoding="utf-8"))
    return {
        t["task_id"]: sum(len(docs[u]) // CHARS_POR_TOKEN for u in t["unit_ids"])
        for t in tareas
    }


def campana(corpus: str | Path = CORPUS_CAMPANA, repeat: int = 3) -> None:
    """La proyeccion de la corrida homogenea, CON la poda aritmetica aplicada.

    POR QUE LA PODA VA ADENTRO DE LA ESTIMACION, y no es un detalle. Sin ella la cuenta da
    395M tokens; con ella, 265M. La diferencia son **264 celdas de 1.014 que la aritmetica
    descarta a costo cero** — `direct` corre 6 tareas de 78, `streaming_scan` y
    `extract_compute` 12, `map_reduce` 24. Ignorarla no es «conservador»: es estimar una
    corrida que el runner no va a hacer.

    POR QUE SE PROYECTA POR FRACCION DE MATERIAL y no por costo medio. El costo por celda
    se mide en `w4`, y `w48` es 12x el material. Multiplicar el costo medio de `w4` por 78
    tareas trataria a una tarea de 455k como si fuera una de 38k. Lo que se transporta
    entre anchos es la FRACCION del material que cada paradigma efectivamente paga —
    `rewoo` paga 0,03 y `react` 0,83, y esa proporcion es propiedad del paradigma.

    LO QUE ESTO NO SABE. Que la fraccion medida en `w4` se sostenga en `w48`. Es la
    suposicion que queda viva, y esta declarada acá en vez de escondida en el numero.
    """
    from app.feasibility import check
    from app.paradigms import REGISTRY
    from app.runner import load_rows

    raiz = Path(corpus)
    docs = json.loads((raiz / "documents.json").read_text(encoding="utf-8"))
    tareas = json.loads((raiz / "tasks.json").read_text(encoding="utf-8"))
    material = _material_por_tarea(corpus)
    roster = sorted(set(REGISTRY) - set(NO_SE_CORREN))

    # El costo por celda sale del registro de la LIGHT, que es el unico que existe sobre
    # este corpus. Es un piso: se midio en `w4`.
    filas = load_rows(Path("results/light/gold_h1_rows.jsonl"))
    fraccion: dict[str, float] = {}
    for p in roster:
        medidas = [f for f in filas if f["paradigm"] == p and not f.get("infeasible")]
        if medidas:
            fraccion[p] = (sum(f["cost_tokens"] for f in medidas)
                           / sum(material[f["task_id"]] for f in medidas))

    sin_medir = [p for p in roster if p not in fraccion]
    if sin_medir:
        # SIN N NO SE INVENTA UN PROMEDIO. Un paradigma sin medir puede costar 30x lo que
        # el mas barato (`dag_strategy` contra `rewoo` es exactamente eso).
        print(f"SIN N, y no se rellenan con la media: {sin_medir}\n")

    total = corren = podadas = 0.0
    print(f"{'paradigma':<16}{'corren':>8}{'podadas':>9}{'tok/material':>14}"
          f"{'proyeccion':>13}")
    for p in roster:
        if p not in fraccion:
            continue
        c = pod = 0
        sub = 0.0
        for t in tareas:
            if check(p, docs, t).feasible:
                c += 1
                sub += fraccion[p] * material[t["task_id"]] * repeat
            else:
                pod += 1
        corren += c
        podadas += pod
        total += sub
        print(f"  {p:<14}{c:>8}{pod:>9}{fraccion[p]:>14.2f}{sub / 1e6:>11.1f}M")

    celdas = corren + podadas
    print(f"\n{int(corren):,} celdas corren · {int(podadas):,} podadas a costo CERO "
          f"({podadas / celdas:.0%} de {int(celdas):,})")
    print(f"PROYECCION: {total / 1e6:,.0f}M tokens  (repeat={repeat}, un brazo)")


def main() -> None:
    print("CAMPANA HOMOGENEA — 13 patrones x 78 tareas x repeat 3, un brazo.\n")
    campana()
    print("\nLa plata sale de `config/tariffs.json`; el reloj, de la experiencia.")


if __name__ == "__main__":
    main()
