"""Consolida cada N minutos MIENTRAS la campaña corre, y dice si θ está aprendiendo algo.

POR QUE SE PUEDE, Y NO ES UN TRUCO. La consolidación es **replay contrafáctico sobre el
registro**: el producto cruzado ya está en disco, así que no cuesta una sola llamada al
modelo. `Runner.consolidate` lo dice en su docstring. Correrla en paralelo a la campaña no
compite por cuota — compite por CPU, y nada más.

QUE CORRIGE. Es fácil creer que la campaña «entrena el motor mientras corre». No lo hace:
`run_cross_product` escribe filas y nada más. El aprendizaje —θ, los pisos, las asociaciones
Hebbianas— es una pasada aparte sobre esas filas, **y se puede correr cuando uno quiera, con
las filas que haya**. Más tokens no compran más entrenamiento: compran más episodios.

PARA QUE SIRVE DE VERDAD. Para ver, gratis y en vivo, si el registro está produciendo señal
— o si se está gastando cuota para que la guarda de promoción siga diciendo que no hay nada.
Eso es una decisión de cuánto correr, y hoy se toma a ciegas.

LAS DOS GUARDAS QUE NECESITA, y las dos salen de que el archivo está VIVO:

  la ultima linea puede estar a medio escribir  -> se descarta y se dice cuantas
  el registro crece entre pasadas               -> se reporta el delta, no solo el valor

Corre DESDE `lab/`:  py bench/_consolidar_vivo.py --modelo luna --cada 10
"""

import argparse
import json
import sys as _sys
import time
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import sys
from dataclasses import replace
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import Settings
from app.policy import (Discarded, Episode, Plasticity, PolicyBundle,
                        learnable_rows)

# Lo descartado en la ultima pasada. LA LINEA DE ESTADO LO DICE: «141 episodios»
# sin decir sobre cuantas filas se computo deja al lector suponiendo que fueron
# todas, y hoy una de cada cinco es una celda que nunca ejecuto.
ULTIMO_DESCARTE: list[Discarded] = []
from app.runner import Runner

CORPUS = "gold_h1"


def leer_vivo(path: Path) -> tuple[list[dict], int]:
    """Las filas completas de un archivo que alguien está appendeando.

    La ultima linea puede estar a medio escribir: el escritor hace `write` + `flush` por
    fila, pero nada garantiza que el lector caiga entre las dos. Se descarta y se cuenta —
    saltearla en silencio convertiria una carrera en un numero levemente distinto cada vez.
    """
    if not path.exists():
        return [], 0
    filas, rotas = [], 0
    for linea in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not linea.strip():
            continue
        try:
            filas.append(json.loads(linea))
        except json.JSONDecodeError:
            rotas += 1
    return filas, rotas


def episodios(filas: list[dict]) -> list[Episode]:
    """Filas -> episodios. UN EPISODIO ES UNA CELDA, no un trial.

    Las replicas son mediciones repetidas de lo mismo. Contarlas por separado es
    pseudorreplicacion, y computar «fue el mejor» sobre trials crudos deja que una replica
    con suerte cobre el refuerzo que la media de su paradigma nunca gano.
    """
    celdas: dict[tuple[str, str], list[dict]] = {}
    aptas, descartadas = learnable_rows(filas)
    ULTIMO_DESCARTE.append(descartadas)
    for f in aptas:
        celdas.setdefault((f["task_id"], f["paradigm"]), []).append(f)

    # El mejor de cada tarea se decide sobre la MEDIA de sus replicas, no sobre un trial.
    medias: dict[str, dict[str, float]] = {}
    for (tarea, paradigma), fs in celdas.items():
        medias.setdefault(tarea, {})[paradigma] = sum(
            x["utility"] for x in fs) / len(fs)

    out = []
    for (tarea, paradigma), fs in celdas.items():
        u = medias[tarea][paradigma]
        mejor = max(medias[tarea].values())
        out.append(Episode(
            task_id=tarea,
            region=fs[0].get("region", ""),
            paradigm=paradigma,
            utility=u,
            cost_tokens=int(sum(x["cost_tokens"] for x in fs) / len(fs)),
            was_best=abs(u - mejor) < 1e-9,
        ))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--modelo", default="luna")
    ap.add_argument("--cada", type=int, default=10, help="minutos entre pasadas")
    ap.add_argument("--una", action="store_true", help="una sola pasada y salir")
    args = ap.parse_args()

    base = Settings.from_env()
    path = base.results_dir / args.modelo / f"{CORPUS}_rows.jsonl"
    print(f"mirando {path}")
    print(f"cada {args.cada} min. NO gasta cuota: es replay sobre lo ya pagado.\n")

    previo = 0
    while True:
        filas, rotas = leer_vivo(path)
        eps = episodios(filas)
        regiones = {e.region for e in eps}
        # La candidata se ajusta sobre lo que hay. `cold_start` + plasticidad es la misma
        # maquinaria que `report()`; no se promueve nada — esto MIRA, no instala.
        frio = PolicyBundle.cold_start(fallback="react", tau=0.3)
        cand = Plasticity.candidate(frio, eps, tau=0.3, notes="vivo")
        con_evidencia = [
            (r, p) for r in regiones for p in {e.paradigm for e in eps}
            if (st := cand.stat(r, p)) and st.episodes > 0
        ]
        decidibles = [
            (r, p) for r, p in con_evidencia if cand.stat(r, p).episodes >= 3
        ]
        d = ULTIMO_DESCARTE[-1] if ULTIMO_DESCARTE else None
        # «141 episodios» sobre «539 filas» invita a suponer que las 539 se midieron, y
        # hoy una de cada cinco es una celda que la aritmetica podo antes de correr.
        print(f"[{time.strftime('%H:%M')}] {len(filas):>5} filas "
              f"(+{len(filas) - previo}, {d.total if d else 0} no medidas)  "
              f"{len(eps):>4} episodios  "
              f"{len(regiones):>2} regiones  "
              f"{len(con_evidencia):>3} pares con evidencia  "
              f"{len(decidibles):>3} con n>=3"
              + (f"  [{rotas} linea a medio escribir]" if rotas else ""), flush=True)
        previo = len(filas)
        if args.una:
            return
        time.sleep(args.cada * 60)


if __name__ == "__main__":
    main()
