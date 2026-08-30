"""P15, RECOMPUTADA por el camino arreglado. Cero llamadas al modelo.

POR QUÉ HAY QUE REHACERLA. El veredicto «P15 REFUTADA: θ pierde −0,087 neto contra el mejor
fijo» salió de `Runner.report`, y `report` no le pasaba `coupling` a `router.plan`. Medido:
**23 de 46 tareas —la mitad justa— volvían con `needs_probe`**, y `report` devolvía
`plan.paradigm` sin sondear. En un plan con `needs_probe` ese paradigma es el **placeholder**
—el admisible más barato, elegido para probarse DESPUÉS de sondear—.

    O sea que la mitad del corpus se puntuó sobre marcadores de posición, y de ahí salió
    el número que refutó la tesis del producto.

QUÉ HACE ESTE ARCHIVO: recomputa los términos de selección con las dos funciones de decisión
—la vieja y la arreglada— sobre el MISMO registro, para que la diferencia sea atribuible a la
decisión y a nada más.

**No predigo que P15 se dé vuelta.** El diferimiento artificial mandaba las tareas al
placeholder, que es *el admisible más barato*, y en este corpus el barato no es el que gana
utilidad. Lo esperable es que θ mejore algo; lo que importa es que el número deje de venir de
un camino roto.

Corre DESDE `lab/`:  py bench/analysis/_p15_recomputada.py
"""

from __future__ import annotations

import collections
import json
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.assurance import PROFILES, Assurance
from app.beliefs import Provenance
from app.metrics import Observation, Study
from app.policy import PolicyBundle
from app.router import Router
from app.runner import COST_PRIORS, FALLBACK, load_rows

COUP = {"loose": 0.15, "mixed": 0.5, "tight": 0.85}


def main() -> None:
    tareas = {t["task_id"]: t for t in json.loads(
        _Path("corpus/gold_h1/tasks.json").read_text(encoding="utf-8"))}
    # NO SE FILTRAN LAS `infeasible`, y eso NO es un descuido: `Runner.study` tampoco las
    # filtra —solo saca `infra_error`— asi que un brazo podado entra como utilidad 0. Si
    # aca se filtraran, `complete_tasks` caeria de 46 a 4 y la comparacion mediria otra
    # cosa. La regla es replicar la construccion, no mejorarla: lo que se compara es la
    # DECISION, y todo lo demas tiene que ser identico.
    filas = [f for f in load_rows(_Path("results/luna/gold_h1_rows.jsonl"))
             if not f.get("infra_error")]

    rows = collections.defaultdict(dict)
    region = {}
    for f in filas:
        rows[f["task_id"]][f["paradigm"]] = f
        region[f["task_id"]] = f.get("region", "")

    # Se agregan las replicas a una `Observation` por celda, igual que `Runner.study`.
    # No se reimplementa la metrica: se le da la MISMA entrada, o la comparacion no
    # sostendria nada.
    celdas: dict[tuple[str, str], list] = {}
    for f in filas:
        celdas.setdefault((f["task_id"], f["paradigm"]), []).append(f)
    study = Study(
        Observation(
            task_id=tid, region=rs[0]["region"], paradigm=par,
            utility=sum(x["utility"] for x in rs) / len(rs),
            cost_tokens=int(sum(x.get("cost_tokens") or 0 for x in rs) / len(rs)),
            has_oracle=rs[0].get("has_oracle", True),
        )
        for (tid, par), rs in celdas.items()
    )
    router = Router(PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3),
                    COST_PRIORS, FALLBACK)

    def coup_de(tid: str) -> tuple[float | None, float]:
        for parte in region[tid].split("/"):
            if parte in COUP:
                return COUP[parte], 1.0
        return None, 0.0

    def hacer_decide(con_creencia: bool, assurance: Assurance):
        diferidas: list[str] = []

        def decide(task_id: str) -> str:
            c, cr = coup_de(task_id) if con_creencia else (None, 0.0)
            plan = router.plan(
                task=tareas[task_id], candidates=sorted(rows[task_id]),
                region=region[task_id], requested=assurance,
                coupling=c, coupling_provenance=Provenance.ELICITED,
                coupling_credence=cr,
            )
            if getattr(plan, "needs_probe", False):
                diferidas.append(task_id)
            return plan.paradigm

        return decide, diferidas

    print("=" * 96)
    print("P15 RECOMPUTADA — el mismo registro, dos funciones de decision")
    print("=" * 96)
    print(f"\n  {len(study.complete_tasks)} tareas completas · mejor fijo "
          f"`{study.best_fixed()}`\n")

    for etiqueta, con in (("VIEJA  (sin pasar la creencia)", False),
                          ("NUEVA  (con la creencia del registro)", True)):
        for assurance in (Assurance.STANDARD, Assurance.CERTIFIED):
            decide, diferidas = hacer_decide(con, assurance)
            terms = study.selection_terms(decide).as_dict()
            capt = study.captured_fraction(decide)
            n_dif = len(set(diferidas))
            print(f"  {etiqueta:38s} {assurance.name}")
            print(f"    diferidas (placeholder puntuado)  {n_dif:3d} de "
                  f"{len(study.complete_tasks)}")
            print(f"    pi={terms['pi']:.3f}  alpha={terms['alpha']:.3f}  "
                  f"beta={terms['beta']:.3f}  G={terms['gain']:.3f}")
            print(f"    brecha capturada por el router    {capt:+.4f}")
            print(f"    el teorema se sostiene            {terms['holds']}\n")

    print("=" * 96)
    print("EL RESULTADO")
    print("=" * 96)
    print("""
  P15 **NO se da vuelta**. Con la creencia recuperada, en STANDARD:

      beta (rutear donde NO ayuda)   0,556 -> 0,472
      alpha (rutear donde SI ayuda)  0,800 -> 0,600
      brecha capturada               -4,46 -> -3,74

  El router mejora de forma material y **sigue perdiendo**. El veredicto se sostiene; lo
  que estaba mal era la magnitud y el camino, no la conclusion.

  Y se ve por que no puede ganar: **pi = 0,217**. En el 78% de las tareas la
  especializacion NO ayuda —el mejor fijo ya es optimo— asi que el router solo puede
  perder ahi, y con beta = 0,47 pierde en la mitad de ese 78%.

  LO QUE ESTOS NUMEROS NO SON. Corren con un bundle FRIO (`cold_start`), no con la theta
  ajustada que `report()` aprende de los episodios. La COMPARACION es valida —cambia una
  sola cosa, la funcion de decision— pero los valores absolutos **no son comparables al
  -0,087 publicado**. Para eso hay que correr `report()` entero, que ahora ya no puntua
  placeholders.
""")

    print("=" * 96)
    print("COMO LEER ESTO")
    print("=" * 96)
    print("""
  La comparacion honesta es VIEJA-STANDARD contra NUEVA-STANDARD: mismo registro, mismo
  dial, misma theta fria — lo unico que cambia es si la decision recibe la creencia que la
  campania ya habia pagado derivar.

  Y en CERTIFIED los diferimientos SIGUEN, con creencia y todo. Eso no es un defecto: una
  estimacion `ELICITED` no sostiene una decision con piso `OBSERVED`, y ahi lo correcto es
  diferir. Lo que ese renglon dice es que **en regulado el ciclo epistemico si haria falta
  de verdad** — y nunca se corrio.

  LO QUE ESTE ARCHIVO NO HACE: sondear. Con la sonda ejecutandose de verdad, las 23
  diferidas de CERTIFIED se resolverian a una decision real, y ESE es el numero que nunca
  se midio. Cuesta 23 llamadas chicas.""")


if __name__ == "__main__":
    main()
