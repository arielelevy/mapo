"""S-1: ¿por que la sonda corrio 14 veces y resolvio cero? Cero tokens nuevos.

P17b quedo refutada de la manera mas informativa posible: la sonda disparo en las 14
tareas que la pedian, costo 83.539 tokens, y NO RESOLVIO NINGUNA. Las catorce quedaron
`unresolved`, asi que la accion honesta fue diferir — y el ruteo degenero al fallback en
20 de 22 tareas del cohorte.

Eso no es pre-empcion: es la cuarta y ultima traba, y es de otra clase. La cascada no
estorba (2 de 26) y la regla de sonda dispara como fue disenada (14 de 26). Lo que falla
es que **la evidencia que la sonda trae no llega al piso que la regla exige**.

DOS ARREGLOS OPUESTOS, Y HAY QUE SEPARARLOS ANTES DE TOCAR NADA.

  (a) LA SONDA ES DEBIL. Mira una sola unidad, elegida por recuperacion lexica, y pide un
      puntero literal. Si el acoplamiento existe pero no esta escrito en esa unidad, la
      sonda no lo ve por poco — y el arreglo es mirar mejor.

  (b) EL PISO ES CORRECTO Y LA RESPUESTA ES «NO SE». Si el modelo mayormente contesta
      «autocontenida», eso vale `ELICITED` 0,6 a proposito: una unidad de silencio no es
      una medicion de las otras 47. Entonces la sonda esta funcionando y lo que hay que
      cambiar es que se le pida.

Bajar el piso para que «resuelva» seria el peor arreglo posible: convertiria una
abstencion honesta en una decision tomada sobre evidencia que el gate acaba de declarar
insuficiente. Este script decide cual de las dos es, mirando QUE devolvio la sonda.

Corre SELLADO: las llamadas ya se pagaron durante el veredicto, asi que un miss seria un
error duro y jamas una llamada viva.
"""

import json
import sys
from collections import Counter
from dataclasses import replace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from _regions import rederived_episodes
from app.config import Settings
from app.features import Features, has_runtime_detector
from app.llm import SeededClient
from app.paradigms import COST_PRIORS, FALLBACK
from app.assurance import PROFILES, Assurance
from app.policy import Plasticity, PolicyBundle
from app.probe import probe_coupling
from app.router import Router
from app.rules import COUPLING_CREDENCE_FLOOR
from app.runner import Runner

base = Settings.from_env()
settings = replace(base, results_dir=base.results_dir / "nano")

CORPUS = "gold_p17"
TRAIN = ("gold_deep", "gold_holdout", "gold_v2", "gold_transfer")


def main() -> None:
    episodes = []
    for corpus in TRAIN:
        runner = Runner(settings, corpus, retriever_arm="hybrid", surface_variant="basic")
        episodes += rederived_episodes(runner, corpus)
    theta = Plasticity.candidate(
        PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3), episodes, tau=0.3
    )
    router = Router(theta, COST_PRIORS, FALLBACK)

    target = Runner(settings, CORPUS, retriever_arm="hybrid",
                    surface_variant="basic", sealed=True)
    tasks = {t["task_id"]: t for t in target._tasks}  # noqa: SLF001
    rows_by_task: dict[str, dict] = {}
    for row in target.load_rows():
        rows_by_task.setdefault(row["task_id"], {})[row["paradigm"]] = row
    documents = json.load(open(f"corpus/{CORPUS}/documents.json", encoding="utf-8"))

    client = SeededClient(target._client, settings.seed)  # noqa: SLF001
    # El piso es del PERFIL de garantia, no del bundle: cada nivel A0-A3 declara el
    # suyo, y es lo que la regla consulta.
    floor = PROFILES[Assurance.STANDARD].derived_floor

    print(f"piso exigido por la regla: procedencia >= {floor.value}, "
          f"credencia >= {COUPLING_CREDENCE_FLOOR}\n")

    needed = []
    for task_id in sorted(rows_by_task):
        task = tasks[task_id]
        features = Features(
            n_units=len(task["unit_ids"]),
            has_oracle=has_runtime_detector(task),
            irreversible=bool(task.get("irreversible", False)),
            shared_writes=bool(task.get("shared_writes", False)),
            budget_tokens=int(task["budget_tokens"]),
        )
        plan = router.plan(task=task, candidates=sorted(rows_by_task[task_id]),
                           region=features.region(), documents=documents)
        if plan.needs_probe:
            needed.append(task_id)

    print(f"tareas que piden sonda: {len(needed)}\n")
    print(f"  {'tarea':<16}{'procedencia':>13}{'cred':>7}{'coupling':>10}"
          f"{'¿alcanza?':>11}  lo que devolvio")

    reasons: Counter = Counter()
    provenances: Counter = Counter()
    for task_id in needed:
        task = tasks[task_id]
        surface = target.surface_for(task)
        try:
            reading = probe_coupling(client, surface, task)
        except Exception as exc:  # noqa: BLE001
            print(f"  {task_id:<16}{type(exc).__name__}")
            reasons["miss de cache"] += 1
            continue
        enough = (reading.provenance.rank >= floor.rank
                  and reading.credence >= COUPLING_CREDENCE_FLOOR)
        provenances[reading.provenance.value] += 1
        why = getattr(reading, "reason", "") or getattr(reading, "evidence", "") or ""
        reasons[(reading.provenance.value, round(reading.credence, 2))] += 1
        print(f"  {task_id:<16}{reading.provenance.value:>13}{reading.credence:>7.2f}"
              f"{str(reading.coupling):>10}{('SI' if enough else 'no'):>11}  {why[:44]}")

    print("")
    print("  reparto por procedencia:", dict(provenances))
    print("  reparto (procedencia, credencia):")
    for k, n in reasons.most_common():
        print(f"    {k}: {n}")

    print("")
    print("=" * 76)
    elicited = sum(n for (prov, _), n in reasons.items()
                   if isinstance(prov, str) and prov == "elicited")
    observed = sum(n for (prov, _), n in reasons.items()
                   if isinstance(prov, str) and prov == "observed")
    if observed and not elicited:
        print("  (a) LA SONDA MIRA BIEN: devuelve observaciones. Si aun asi no alcanza,")
        print("      el problema es el umbral de credencia y no la evidencia.")
    elif elicited and not observed:
        print("  (b) LA SONDA NO ENCUENTRA PUNTERO. Devuelve elicited en todas: el modelo")
        print("      no halla una referencia literal en la unidad que se le mostro.")
        print("")
        print("      Eso NO es un piso mal puesto. Es la sonda mirando una sola unidad")
        print("      elegida por recuperacion lexica, y pidiendo un puntero explicito que")
        print("      esa unidad puede sencillamente no contener. Bajar el piso convertiria")
        print("      una abstencion honesta en una decision sobre evidencia insuficiente.")
    else:
        print(f"  MIXTO: {observed} observadas y {elicited} elicitadas. Hay que mirar por")
        print("  celda antes de decidir cual de los dos arreglos corresponde.")
    print("=" * 76)

    out = settings.results_dir / "probe_diagnosis.json"
    out.write_text(json.dumps({
        "corpus": CORPUS, "needed": len(needed),
        "floor_provenance": floor.value, "floor_credence": COUPLING_CREDENCE_FLOOR,
        "by_provenance": dict(provenances),
        "detail": {str(k): v for k, v in reasons.items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nreporte: {out}")


if __name__ == "__main__":
    main()
