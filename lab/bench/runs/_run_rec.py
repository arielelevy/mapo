"""REC: el ciclo de certificacion, corrido SIN GASTAR (REC-2, REC-3, REC-4).

POR QUE SE PUEDE CORRER GRATIS. El ciclo no llama al modelo: lee utilidades por tarea de un
registro ya pagado, re-deriva la base de creencias que el router habria sensado, diagnostica
que proposicion habria cambiado la decision, y mide el beneficio de repararla. Todo eso es
funcion del registro. Lo que cuesta tokens es EJECUTAR la clausula promovida en produccion,
no decidir si merece promoverse.

LOS TRES MUNDOS SALEN DE PARTIR UN CORPUS, y son disjuntos por identidad de tarea — que es
lo que `WorldManifest.overlaps` verifica y rechaza. La particion es determinista (orden de
task_id, tercios) y no aleatoria: un split que cambia entre corridas hace que el mismo
registro produzca veredictos distintos, y entonces el veredicto describe el split.

REC-2 VA ADENTRO Y NO AL LADO. Congelar politica, presupuesto, umbrales y regla ANTES de
mirar el mundo final es el punto entero del diseno, y un congelamiento que vive en la cabeza
del que corre el script no congela nada. Aca el preregistro se escribe primero, se le saca
un digest, y ese digest entra al certificado: quien lo audite puede ver contra que criterio
se decidio, no contra cual se dice que se decidio.
"""

# Corre DESDE `lab/`.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import collections
import hashlib
import json
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.beliefs import Provenance
from app.rules import BeliefPolicy
from app.certify import FinalLedger, World, certify_clause
from app.rec import AcquisitionClause

CORPUS = "gold_transfer"
# EL REGISTRO ARCHIVADO, y a proposito (decision del autor: REC se apoya en las mediciones
# viejas). El ciclo NO llama al modelo: lee utilidades y costos ya pagados, asi que el
# cambio de tokenizador —que hace irreplayables esas filas— no lo afecta. Lo que importa
# aca es que las utilidades sean las que se midieron, y lo son.
#
# Lo que SI seria un error es mezclarlas con filas nuevas, y eso lo impide `load_rows`.
REGISTRO = "results/archivo-2026-08-29-pre-K6/gold_transfer_rows.jsonl"
FALLBACK = "react"
# LO QUE CUESTA SONDEAR **UNA** TAREA. `P17b` dice «0 de 14: la sonda corrio, costo 83k
# tokens y no resolvio ninguna»: los 83k son el TOTAL sobre 14 tareas, no el costo de una.
# La primera version de este script uso los 83k como si fueran por tarea e inflo el
# beneficio **14x** — un agregado leido como un por-unidad, que es la forma exacta de error
# que `_sanity.py` existe para atajar: «un numero derivado se verifica en la granularidad
# donde vive».
PROBE_TOKENS = 83_000 // 14
# La convencion del banco: lambda opera sobre la RAZON de costo contra el mas barato de la
# tarea, no sobre tokens absolutos. Se barre, no se elige uno.
LAMBDAS = (0.0, 0.02, 0.05, 0.10, 0.20)
# EL LAMBDA CON EL QUE SE DECIDE, congelado en el preregistro. Se elige ANTES de ver el
# barrido: elegirlo despues seria leer los numeros y quedarse con el que conviene.
LAMBDA_DECISION = 0.05


def cargar() -> tuple[dict, dict, dict]:
    """Tareas del CORPUS, utilidades del registro.

    LA TAREA NO SE RECONSTRUYE DEL REGISTRO, y la primera version lo intentaba. La fila no
    guarda `irreversible`, `shared_writes` ni `unit_ids`, asi que rellenarlos con defaults
    hacia que `sense()` viera **todas** las tareas como el caso trivial —una unidad, nada
    irreversible— incluidas las de `C7_irreversible`. El ciclo corria entero y devolvia
    **cero deficits en los tres mundos**: un veredicto perfectamente plausible producido por
    una entrada inventada.

    Es la misma forma que `P-16`: el registro no declara lo que no guarda, y completarlo con
    defaults produce numeros que se leen igual que los medidos.
    """
    tareas_corpus = json.loads(
        (Path("corpus") / CORPUS / "tasks.json").read_text(encoding="utf-8")
    )
    if isinstance(tareas_corpus, dict):
        tareas_corpus = list(tareas_corpus.values())
    tareas = {t["task_id"]: t for t in tareas_corpus}

    filas = collections.defaultdict(list)
    regiones: dict[str, str] = {}
    for line in Path(REGISTRO).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("error") or r.get("infeasible"):
            continue
        tid = r["task_id"]
        if tid not in tareas:
            continue
        filas[(tid, r["paradigm"])].append((r["utility"], r.get("cost_tokens", 0)))
        regiones.setdefault(tid, r.get("region", ""))
    utilidades: dict[str, dict[str, float]] = collections.defaultdict(dict)
    costos: dict[str, dict[str, float]] = collections.defaultdict(dict)
    for (tid, par), v in filas.items():
        utilidades[tid][par] = statistics.mean(u for u, _ in v)
        costos[tid][par] = statistics.mean(c for _, c in v)
    return tareas, regiones, dict(utilidades), dict(costos)


def partir(ids: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Tercios deterministas. Un split aleatorio haria que el veredicto describa el split."""
    n = len(ids) // 3
    return ids[:n], ids[n:2 * n], ids[2 * n:]


def preregistro(politica: BeliefPolicy, piso: float, draft: AcquisitionClause) -> dict:
    """REC-2: lo que se congela ANTES de mirar el mundo final.

    El digest NO lleva fecha, igual que el resto de los digests del repo: una fecha adentro
    hace que el mismo criterio produzca identidades distintas, y entonces el digest deja de
    poder probar que dos corridas decidieron con la misma regla.
    """
    cuerpo = {
        "criterion": ("validate benefit > noise_floor with >= min_tasks deficit tasks, "
                      "THEN final benefit > noise_floor with >= min_tasks"),
        "noise_floor": round(piso, 6),
        "min_tasks": 2,
        "lambdas": list(LAMBDAS),
        "lambda_decision": LAMBDA_DECISION,
        "probe_tokens": PROBE_TOKENS,
        "fallback": FALLBACK,
        "policy": politica.as_dict() if hasattr(politica, "as_dict") else str(politica),
        "candidate_clause": draft.as_dict(),
    }
    blob = json.dumps(cuerpo, sort_keys=True, ensure_ascii=False)
    cuerpo["digest"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return cuerpo


def main() -> None:
    tareas, regiones, utilidades, costos = cargar()
    ids = sorted(utilidades)
    print(f"registro: {len(ids)} tareas, "
          f"{len({p for u in utilidades.values() for p in u})} paradigmas\n")

    a, b, c = partir(ids)
    mundos = tuple(
        World(corpus=CORPUS,
              tasks={t: tareas[t] for t in grupo},
              regions={t: regiones[t] for t in grupo},
              utilities={t: utilidades[t] for t in grupo},
              costs={t: costos[t] for t in grupo})
        for grupo in (a, b, c)
    )
    print(f"mundos disjuntos: propose={len(a)}  validate={len(b)}  final={len(c)}")

    # EL PISO DE RUIDO SE MIDE, no se elige. Es la dispersion entre replicas del mismo
    # punto — la unica que no puede deberse a la clausula.
    por = collections.defaultdict(list)
    for line in Path(REGISTRO).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("error") or r.get("infeasible"):
            continue
        por[(r["task_id"], r["paradigm"])].append(r["utility"])
    disp = [statistics.pstdev(v) for v in por.values() if len(v) > 1]
    piso = statistics.mean(disp) if disp else 0.0
    print(f"piso de ruido medido: {piso:.4f}\n")

    # EL PISO DE PROCEDENCIA ES `OBSERVED`, que es el regimen bajo el que REC tiene sentido:
    # con un piso mas laxo la opinion del modelo ya satisface la regla y no hay deficit que
    # reparar — la clausula no tendria a que aplicarse. `tau` es el del bundle ajustado.
    politica = BeliefPolicy(derived_floor=Provenance.OBSERVED, tau=0.3)
    draft = AcquisitionClause(
        clause_id="acq_coupling_v1",
        target_proposition="coupling_tight",
        region_prefixes=("",),
        probe_kind="unit_read_pointer",
        verifier="key-recurrence/1",
        reachable=Provenance.OBSERVED,
        max_reads=2,
        max_calls=2,
        max_tokens=5_000,
        safe_exit="defer",
    )

    # --- REC-2: congelar ANTES.
    pre = preregistro(politica, piso, draft)
    salida = Path("results/nano/rec_prereg.json")
    salida.write_text(json.dumps(pre, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"REC-2 preregistro congelado: digest={pre['digest']}  -> {salida}")
    print(f"  criterio: {pre['criterion']}")
    print(f"  piso: {pre['noise_floor']}  min_tasks: {pre['min_tasks']}\n")

    def theta_assert(region: str, paradigms: list[str]):
        """Sin politica ajustada: no opina. Es el regimen que el registro tiene."""
        return None, 0.0

    # SE BARRE LAMBDA, no se elige uno. El veredicto que importa es a que precio del token
    # la clausula empieza a valer — decir "vale" o "no vale" sin ese numero esconde la
    # mitad de la respuesta.
    from app.certify import _benefit_on, _diagnose_world
    print("BARRIDO DE LAMBDA (beneficio en el mundo de validate):")
    for lam in LAMBDAS:
        d = _diagnose_world(mundos[1], politica, theta_assert, FALLBACK,
                            draft.target_proposition)
        b, n = _benefit_on(mundos[1], d, FALLBACK, lambda_cost=lam,
                           probe_tokens=PROBE_TOKENS, clause_tokens=draft.max_tokens)
        marca = "  <- supera el piso" if b > piso else ""
        print(f"  lambda={lam:<5} beneficio {b:+.4f}  (n={n}){marca}")
    print()

    ledger = FinalLedger(Path("results/nano/rec_final_ledger.jsonl"))
    clausula, cert = certify_clause(
        draft=draft,
        incumbent_digest=pre["digest"],
        worlds=mundos,
        policy=politica,
        theta_assert=theta_assert,
        fallback=FALLBACK,
        noise_floor=piso,
        ledger=ledger,
        model_fingerprint="gpt-5.4-nano|t=0|seed=7",
        authorizer="bench/_run_rec.py",
        claim_id=f"rec-{pre['digest']}",
        lambda_cost=LAMBDA_DECISION,
        probe_tokens=PROBE_TOKENS,
    )
    d = cert.as_dict()
    print("VEREDICTO")
    print(f"  aceptada         : {d['accepted']}")
    print(f"  beneficio propose: {d['propose_benefit']:+.4f}  (no decide nada)")
    print(f"  beneficio validate: {d['validate_benefit']:+.4f}")
    print(f"  beneficio final   : {d['final_benefit']:+.4f}")
    print(f"  tareas con deficit: {d['deficit_tasks']}")
    print(f"  clausula promovida: {clausula is not None}")
    Path("results/nano/rec_certificate.json").write_text(
        json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\ncertificado -> results/nano/rec_certificate.json")


if __name__ == "__main__":
    main()
