"""Validate the measurement layer against synthetic data with known answers.

These are not plumbing tests. Each one pins a quantity the paper claims, on a
distribution constructed so the correct value is known by hand. If the identity
oracle_gap == pi*G ever stops holding, every number in the paper is suspect, and that
should fail loudly here rather than be discovered by a reviewer.

Run: py -m tests.test_science   (from D:\\Apps\\lab)
"""

from __future__ import annotations

import pathlib
import sys
from pathlib import Path

# The Windows console defaults to cp1252 and raises on any non-Latin-1
# character, which turns a reporting nicety into a crash mid-suite.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import grading  # noqa: E402
from app.metrics import Observation, Study  # noqa: E402
from app.policy import (  # noqa: E402
    Episode,
    Plasticity,
    PolicyBundle,
    promote,
)

# ---------------------------------------------------------------------------
# A world with known terms.
#
#   100 tasks. Fallback 'react' scores 0.7 everywhere.
#   'map_reduce' scores 1.0 on the first 20 tasks and 0.3 on the rest.
#   'direct' and 'cot' are weak everywhere.
#
# By hand:
#   pi = 0.20              (map_reduce beats react on 20 of 100)
#   G  = 0.30              (1.0 - 0.7)
#   best fixed = react, mean 0.70
#   oracle     = 0.2*1.0 + 0.8*0.7 = 0.76
#   gap        = 0.06 = pi*G
#
# Two distinct losses, and conflating them is easy:
#   L_realised  = 0.40     what a router that picks map_reduce actually pays off S
#   L_potential = 0.45     mean over ALL alternatives off S:
#                          direct 0.5, cot 0.45, map_reduce 0.4  ->  1.35/3
#   beta_max    = pi*1*G / ((1-pi)*L_potential) = 0.06 / 0.36 = 0.16667
#
# beta_max uses L_potential because it is a bound on the PROBLEM, not on a router.
# ---------------------------------------------------------------------------

N = 100
S_SIZE = 20
UTILITY = {
    "react": lambda i: 0.7,
    "map_reduce": lambda i: 1.0 if i < S_SIZE else 0.3,
    "direct": lambda i: 0.2,
    "cot": lambda i: 0.25,
}
COST = {"direct": 500, "cot": 700, "react": 3000, "map_reduce": 9000}


ROOT = pathlib.Path(__file__).resolve().parent.parent


def build_study(has_oracle: bool = True) -> Study:
    return Study(
        Observation(
            task_id=f"t{i:03d}",
            region="many/oracle/loose" if i < S_SIZE else "single/oracle/loose",
            paradigm=paradigm,
            utility=fn(i),
            cost_tokens=COST[paradigm],
            has_oracle=has_oracle,
        )
        for i in range(N)
        for paradigm, fn in UTILITY.items()
    )


def approx(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def check(label: str, condition: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))
    return condition


def check_probe(ok: bool) -> bool:
    """La rebanada de reconocimiento (PATTERNS 2.2): una lectura barata que convierte
    una opinion en una observacion -- y que se NIEGA a convertirla cuando no puede."""
    from dataclasses import dataclass  # noqa: PLC0415

    from app.beliefs import Provenance  # noqa: PLC0415
    from app.probe import probe_coupling  # noqa: PLC0415

    print("\n16. La sonda: cuando una creencia puede pasar a OBSERVED")

    @dataclass
    class _Usage:
        total_tokens: int = 120
        calls: int = 1

    @dataclass
    class _Completion:
        text: str
        usage: _Usage

    class _Sensor:
        def __init__(self, text: str) -> None:
            self._text = text

        def complete(self, messages, **kwargs):
            return _Completion(self._text, _Usage())

    class _Surface:
        def __init__(self, units: dict) -> None:
            self._units = units

        def unit_ids(self):
            return list(self._units)

        def read_one(self, unit_id: str) -> str:
            return self._units[unit_id]

    units = {
        "memo-001": "Settlement account AR9911 is held by the party named in memo-014.",
        "memo-014": "unrelated content",
    }
    task = {"question": "who holds the flagged account?"}

    verified = probe_coupling(
        _Sensor('{"self_contained": false, "references": ["memo-014"]}'),
        _Surface(units), task,
    )
    ok &= check("un puntero que RESUELVE contra el scope da OBSERVED",
                verified.provenance is Provenance.OBSERVED
                and verified.credence == 1.0
                and verified.coupling >= 0.66,
                verified.evidence[:70])

    invented = probe_coupling(
        _Sensor('{"self_contained": false, "references": ["memo-999"]}'),
        _Surface(units), task,
    )
    ok &= check("un puntero INVENTADO no sube la procedencia",
                invented.provenance is Provenance.ELICITED and invented.credence <= 0.3,
                "el sensor puede equivocarse; el codigo lo verifica")

    silent = probe_coupling(
        _Sensor('{"self_contained": true, "references": []}'),
        _Surface(units), task,
    )
    ok &= check("una unidad 'auto-contenida' se queda en ELICITED",
                silent.provenance is Provenance.ELICITED,
                "una unidad de silencio no mide a las otras 47")

    broken = probe_coupling(_Sensor("no soy json"), _Surface(units), task)
    ok &= check("un sensor ilegible es una NO-lectura, no un cero",
                broken.provenance is Provenance.ASSUMED and broken.credence == 0.0)

    # determinismo: la misma tarea sondea la misma unidad
    first = probe_coupling(
        _Sensor('{"self_contained": true, "references": []}'), _Surface(units), task)
    second = probe_coupling(
        _Sensor('{"self_contained": true, "references": []}'), _Surface(units), task)
    ok &= check("la sonda elige la unidad de forma determinista",
                first.unit_id == second.unit_id == "memo-001",
                "si sampleara, la decision que alimenta no seria reproducible")

    # y la observacion alcanza el piso que 6.2 puede exigir
    from app.beliefs import Belief, BeliefBase  # noqa: PLC0415

    base = BeliefBase()
    base.assert_(Belief(
        proposition="coupling_tight",
        value=verified.coupling >= 0.66,
        credence=verified.credence,
        provenance=verified.provenance,
        evidence=verified.evidence,
    ))

    # --- F2.2: la unidad se elige por recuperacion, no por posicion
    class _Lex:
        def rank(self, view, query, limit):
            return ["memo-014"]

    class _RankedSurface(_Surface):
        def __init__(self, units: dict) -> None:
            super().__init__(units)
            self.lexical = _Lex()
            self.view = object()

    ranked = probe_coupling(
        _Sensor('{"self_contained": true, "references": []}'),
        _RankedSurface(units), task,
    )
    ok &= check("la sonda lee la unidad que la recuperacion senala",
                ranked.unit_id == "memo-014",
                "lexico, gratis y determinista - no la primera del scope")

    # --- F2.1: sin span literal no hay observacion
    ghost = probe_coupling(
        _Sensor('{"self_contained": false, "references": ["memo-014"]}'),
        _Surface({"memo-001": "no menciona a nadie", "memo-014": "x"}), task,
    )
    ok &= check("un id en scope que el texto NO contiene no se resuelve",
                ghost.provenance is Provenance.ELICITED and not ghost.resolved,
                "el modelo puede nombrar una unidad que sabe que existe")

    selfp = probe_coupling(
        _Sensor('{"self_contained": false, "references": ["memo-001"]}'),
        _Surface(units), task,
    )
    ok &= check("una unidad que se apunta a si misma no es una dependencia",
                selfp.provenance is Provenance.ELICITED and not selfp.resolved)

    ok &= check("la observacion registra el span literal",
                "@" in verified.evidence,
                verified.evidence[verified.evidence.find("("):][:40])

    ok &= check("lo observado satisface una regla que exige OBSERVED",
                base.satisfies("coupling_tight", 0.7, Provenance.OBSERVED),
                "que es lo que un piso aprendido de 6.2 puede llegar a exigir")
    return ok


def check_product_path(ok: bool) -> bool:
    """El camino de producto: un request real entra, y el vocabulario del banco sale
    DERIVADO de el -- nunca al reves."""
    from app.features import FeatureExtractor  # noqa: PLC0415
    from app.paradigms import COST_PRIORS, FALLBACK, REGISTRY  # noqa: PLC0415
    from app.policy import PolicyBundle  # noqa: PLC0415
    from app.router import Router  # noqa: PLC0415
    from app.serve import Request  # noqa: PLC0415

    print("\n17. El camino de producto: request -> decision -> ejecucion")

    request = Request(
        question="who holds the flagged account?",
        documents={"memo-002": "irrelevant", "memo-001": "account AR9911 is flagged"},
        budget_tokens=60_000,
        oracle=["AR9911"],
    )
    task = request.as_task()
    ok &= check("un request sin id se identifica por CONTENIDO",
                task["task_id"] == request.as_task()["task_id"]
                and task["task_id"].startswith("req-"),
                task["task_id"])
    ok &= check("el mismo request dos veces es la MISMA linea del registro",
                Request(question=request.question, documents=dict(request.documents),
                        budget_tokens=request.budget_tokens,
                        oracle=list(request.oracle)).identity() == request.identity())
    ok &= check("los unit_ids salen ordenados, no en orden de dict",
                task["unit_ids"] == ["memo-001", "memo-002"],
                "dos corridas iguales no pueden armar dos prompts distintos")

    features, _ = FeatureExtractor().extract(
        {"question": request.question, "units": task["unit_ids"],
         "oracle": task["oracle"], "has_oracle": task["has_oracle"],
         "irreversible": False, "shared_writes": False,
         "budget_tokens": request.budget_tokens},
        allow_derived=False,
    )
    ok &= check("phi se computa sin red y sin cliente", bool(features.region()),
                features.region())

    bundle = PolicyBundle.cold_start(fallback="react", tau=0.3)
    router = Router(bundle, COST_PRIORS, FALLBACK)

    irreversible = Request(question="close the account", documents={"m1": "x"},
                           budget_tokens=60_000, irreversible=True)
    it = irreversible.as_task()
    fi, _ = FeatureExtractor().extract(
        {"question": it["question"], "units": it["unit_ids"], "oracle": [],
         "has_oracle": False,
         "irreversible": True, "shared_writes": False, "budget_tokens": 60_000},
        allow_derived=False,
    )
    gated = router.plan(task=it, candidates=sorted(REGISTRY), region=fi.region())
    ok &= check("un request irreversible queda GATED antes de ejecutar nada",
                gated.gated and gated.action == "gate_then_fallback",
                "la consecuencia la firma un humano, no el ruteo")

    ok &= check("regulated viaja del request a la base de creencias",
                Request(question="q", documents={"m": "x"}, budget_tokens=1000,
                        regulated=True).as_task()["regulated"] is True)
    return ok


def check_belief_history(ok: bool) -> bool:
    """REC F1: una sola historia de creencias por solicitud, con supersesion."""
    from app.beliefs import Belief, BeliefBase, Provenance  # noqa: PLC0415

    print("\n18. La historia de creencias es UNA, y supersede en orden")

    base = BeliefBase()
    base.assert_(Belief(
        proposition="coupling_tight", value=False, credence=0.6,
        provenance=Provenance.ELICITED, evidence="estimated",
    ))
    # reconstruccion desde el registro: la historia viaja entre planes
    rebuilt = BeliefBase.from_dicts(base.as_dict()["beliefs"])
    ok &= check("la base se reconstruye desde su registro con el MISMO digest",
                rebuilt.digest() == base.digest())

    rebuilt.assert_(Belief(
        proposition="coupling_tight", value=True, credence=1.0,
        provenance=Provenance.OBSERVED, evidence="probe: verified pointer",
    ))
    current = rebuilt.current("coupling_tight")
    ok &= check("lo OBSERVADO supersede a lo estimado en la misma historia",
                current.provenance is Provenance.OBSERVED and current.value is True)
    ok &= check("la estimacion superada sigue en el registro",
                len([b for b in rebuilt.all()
                     if b.proposition == "coupling_tight"]) == 2,
                "append-only: el digest cubre la historia entera")

    # empate exacto: gana la re-medicion, no la primera
    tie = BeliefBase()
    tie.assert_(Belief(proposition="p", value="vieja", credence=0.6,
                       provenance=Provenance.ELICITED, evidence="antes"))
    tie.assert_(Belief(proposition="p", value="nueva", credence=0.6,
                       provenance=Provenance.ELICITED, evidence="despues"))
    ok &= check("en empate de procedencia y credencia gana la MAS RECIENTE",
                tie.value("p") == "nueva",
                "re-medir con la misma confianza tiene que poder supersede")
    return ok


def check_rec_solver(ok: bool) -> bool:
    """REC F3: que cambio minimo en una creencia habria alterado el plan — replay puro,
    sin modelo, sin corpus, y sin tocar jamas la base factual."""
    from app.beliefs import BeliefBase, Provenance  # noqa: PLC0415
    from app.rec import (  # noqa: PLC0415
        AcquisitionClause,
        diagnose,
        verify_key_recurrence,
    )
    from app.rules import BeliefPolicy, sense  # noqa: PLC0415

    print("\n19. REC: el deficit contrafactual minimo")

    task = {"task_id": "t", "question": "q",
            "unit_ids": [f"u{i}" for i in range(20)],
            "budget_tokens": 60_000, "oracle": [], "has_oracle": False}

    # --- el caso con la forma de P15: bulk sin coupling medido -> probe_then_decide
    policy = BeliefPolicy(derived_floor=Provenance.OBSERVED, tau=0.3)
    base = sense(task, policy, theta_best="rewoo", theta_confidence=0.9)
    records = base.as_dict()["beliefs"]
    digest_before = base.digest()

    d = diagnose(records, policy, fallback="react")
    ok &= check("el plan original se re-deriva del registro, sin modelo",
                d.original.action == "probe_then_decide")
    minimal = d.minimal
    ok &= check("encuentra el deficit con la forma de P15",
                minimal is not None
                and minimal.interventions[0].proposition == "coupling_tight",
                "coupling resuelto => el plan cambia")
    ok &= check("el requisito sigue al piso: bajo OBSERVED exige OBSERVED",
                minimal.required_provenance is Provenance.OBSERVED,
                "una hipotesis ELICITED no puede apagar una regla que exige medir")

    lax = BeliefPolicy(derived_floor=Provenance.ELICITED, tau=0.3)
    base_lax = sense(task, lax, theta_best="rewoo", theta_confidence=0.9)
    d_lax = diagnose(base_lax.as_dict()["beliefs"], lax, fallback="react")
    ok &= check("bajo un piso ELICITED el requisito baja con el piso",
                d_lax.minimal is not None
                and d_lax.minimal.required_provenance is Provenance.ELICITED)

    # --- invariante 2 de PATRON_REC 9: la hipotesis JAMAS entra a la base factual
    ok &= check("la base factual queda byte-identica tras diagnosticar",
                BeliefBase.from_dicts(records).digest() == digest_before
                and base.digest() == digest_before)

    # --- una decision que ninguna creencia admitida cambia: sin deficits
    small = {"task_id": "s", "question": "q", "unit_ids": ["u1"],
             "budget_tokens": 60_000, "oracle": ["x"], "has_oracle": True}
    base_small = sense(small, policy)
    d_small = diagnose(base_small.as_dict()["beliefs"], policy, fallback="react")
    ok &= check("una decision insensible a creencias adquiribles reporta 0 deficits",
                not d_small.deficits and d_small.minimal is None,
                d_small.original.action)

    # --- clausulas: borrador != promovida, y el digest excluye el certificado
    draft = AcquisitionClause(
        clause_id="rec-coupling-1", target_proposition="coupling_tight",
        region_prefixes=("many/",), probe_kind="unit_read_pointer",
        verifier="key-recurrence/1", reachable=Provenance.OBSERVED,
        max_reads=1, max_calls=1, max_tokens=4_000, safe_exit="defer",
    )
    ok &= check("una clausula sin certificado es BORRADOR y no puede ejecutar",
                not draft.promoted)
    promoted = AcquisitionClause.from_dict({**draft.as_dict(), "certificate": "cert-x"})
    ok &= check("la clausula viaja por registro con la MISMA identidad",
                AcquisitionClause.from_dict(draft.as_dict()).digest() == draft.digest())
    ok &= check("el certificado NO integra el digest: firma a la clausula, no al reves",
                promoted.digest() == draft.digest() and promoted.promoted)
    ok &= check("la clausula aplica solo a su deficit y su region",
                promoted.applies_to(minimal, "many/oracle/loose")
                and not promoted.applies_to(minimal, "few/oracle/loose"))

    # --- verificador de recurrencia de clave (PATRON_REC 5)
    docs = {
        "filing-01": "Settlement account AR9911 was flagged for review.",
        "memo-14": "Account AR9911 is held by V. Simoni.",
        "memo-99": "unrelated content",
    }
    scope = list(docs)
    hit = verify_key_recurrence("AR9911", "filing-01", docs, scope)
    ok &= check("la clave que RECURRE en otra unidad produce evidencia OBSERVED",
                hit is not None and hit["provenance"] == "observed"
                and hit["source"]["unit_id"] == "filing-01"
                and hit["target"]["unit_id"] == "memo-14")
    ok &= check("la evidencia lleva spans, hashes y version del verificador",
                hit["source"]["span_offset"] >= 0
                and len(hit["source"]["content_sha256"]) == 64
                and hit["verifier"] == "key-recurrence/1")
    ok &= check("una clave que NO recurre devuelve None, no una negacion",
                verify_key_recurrence("ZZ0000", "filing-01", docs, scope) is None,
                "el silencio de un scope acotado no demuestra nada global")
    ok &= check("la misma unidad no cuenta como recurrencia",
                verify_key_recurrence("AR9911", "filing-01",
                                      {"filing-01": docs["filing-01"]},
                                      ["filing-01"]) is None)
    return ok


def check_continuation_axis(ok: bool) -> bool:
    """El eje que P15 senalo: continuidad como funcion PURA del material."""
    from app.features import (  # noqa: PLC0415
        Features,
        REGION_VOCABULARY,
        measure_continuation,
    )

    print("\n20. El eje de continuidad (regions/2)")

    chained = {
        "filing-01": "Settlement account AR9911 was flagged.",
        "memo-14": "Account AR9911 is held by V. Simoni.",
        "memo-99": "unrelated",
    }
    ok &= check("una clave que recurre entre unidades distintas = encadenado",
                measure_continuation(chained, list(chained)) is True)
    flat = {"a": "uno solo", "b": "otro distinto", "c": "tercero"}
    ok &= check("sin recurrencia = plano",
                measure_continuation(flat, list(flat)) is False)
    ok &= check("sin material = None, nunca un no",
                measure_continuation({}, ["a", "b"]) is None)
    boiler = {f"u{i}": f"HEADER XX99 unidad {i}" for i in range(8)}
    ok &= check("una clave en TODAS las unidades es boilerplate, no cadena",
                measure_continuation(boiler, list(boiler)) is False,
                "recurrencia cuenta entre 2 y la mitad del scope")
    ok &= check("una unidad que se nombra a si misma no encadena",
                measure_continuation(
                    {"memo-01": "esto es memo-01", "b": "nada"}, ["memo-01", "b"]
                ) is False)

    f = Features(n_units=20, has_oracle=True, irreversible=False,
                 shared_writes=False, budget_tokens=60_000,
                 coupling=0.2, continuation=True)
    ok &= check("la region habla el vocabulario nuevo, con 4 segmentos",
                f.region() == "many/oracle/loose/chain"
                and REGION_VOCABULARY == "regions/2-continuation")
    ok &= check("continuidad sin medir queda visible en la region",
                Features(n_units=2, has_oracle=False, irreversible=False,
                         shared_writes=False,
                         budget_tokens=1000).region().endswith("/c?"))
    return ok


def check_decision_cycle(ok: bool) -> bool:
    """El ciclo de dos pasos: sondear y DESPUES decidir — una sola implementacion."""
    from dataclasses import dataclass  # noqa: PLC0415

    from app.decide import decide  # noqa: PLC0415
    from app.features import Features  # noqa: PLC0415
    from app.paradigms import COST_PRIORS, FALLBACK  # noqa: PLC0415
    from app.policy import Plasticity, PolicyBundle  # noqa: PLC0415
    from app.router import Router  # noqa: PLC0415

    print("\n21. El ciclo de decision de dos pasos")

    @dataclass
    class _Usage:
        total_tokens: int = 140
        calls: int = 1

    @dataclass
    class _Completion:
        text: str
        usage: _Usage

    class _Sensor:
        def __init__(self, text): self._text = text
        def complete(self, messages, **kwargs): return _Completion(self._text, _Usage())

    class _Surface:
        def __init__(self, units): self._units = units
        def unit_ids(self): return list(self._units)
        def read_one(self, uid): return self._units[uid]

    units = {f"u{i:02d}": "relleno" for i in range(20)}
    units["u00"] = "la cuenta AR9911 figura en u07"
    units["u07"] = "AR9911 pertenece a alguien"
    task = {"task_id": "t", "question": "quien es el titular de AR9911?",
            "unit_ids": sorted(units), "budget_tokens": 60_000, "oracle": [],
            "has_oracle": False}

    bundle = PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3)
    router = Router(bundle, COST_PRIORS, FALLBACK)
    features = Features(n_units=len(units), has_oracle=False, irreversible=False,
                        shared_writes=False, budget_tokens=60_000, continuation=True)
    candidates = ["react", "rewoo", "map_reduce", "dag_strategy"]

    # sin cliente: el plan pide sonda y NADIE la resuelve
    blind = decide(task, router=router, features=features, candidates=candidates)
    ok &= check("sin sonda el plan queda SIN RESOLVER, no decidido",
                blind.unresolved and blind.plan.action == "probe_then_decide"
                and not blind.probed,
                "el paradigma del plan es un placeholder para DESPUES de sondear")
    ok &= check("una decision no resuelta no cuesta nada",
                blind.usage.total_tokens == 0 and blind.usage.calls == 0)

    # con sensor: se sondea y se vuelve a decidir
    resolved = decide(
        task, router=router, features=features, candidates=candidates,
        client=_Sensor('{"self_contained": false, "references": ["u07"]}'),
        surface=_Surface(units),
    )
    ok &= check("con sensor la sonda corre y el plan se vuelve a derivar",
                resolved.probed and resolved.plan_before_probe is not None)
    ok &= check("la sonda deja de pedirse: la necesidad quedo resuelta",
                not resolved.unresolved,
                resolved.plan.action)
    ok &= check("decidir CUESTA, y el costo viaja en la decision",
                resolved.usage.total_tokens == 140 and resolved.usage.calls == 1,
                "una sonda fuera de la factura des-mide el trade-off")
    ok &= check("la region se recompone con lo observado",
                resolved.features.coupling is not None
                and resolved.features.region() != features.region(),
                f"{features.region()} -> {resolved.features.region()}")
    ok &= check("el efecto de la sonda sobre la decision queda registrado",
                "changed_by_probe" in resolved.as_dict())

    # una lectura que NO verifica no resuelve la necesidad: sigue sin decidirse
    unreadable = decide(
        task, router=router, features=features, candidates=candidates,
        client=_Sensor("el sensor devolvio prosa"), surface=_Surface(units),
    )
    ok &= check("una sonda ILEGIBLE no resuelve nada y el plan sigue sin decidir",
                unreadable.probed and unreadable.unresolved,
                "sondear no es lo mismo que haber medido")
    ok &= check("y esa sonda fallida igual se cobra",
                unreadable.usage.total_tokens == 140,
                "la evidencia que no llego tambien costo")
    return ok


# =====================================================================================
# 22. LA COTA NATIVA DEL RATCHET (T-4)
# =====================================================================================
# Reemplaza el prestamo del Teorema 10.1 de v1, que acotaba VARIANZA BAJO OSCILACION. El
# piso que aprende no puede oscilar: es monotono y con techo, asi que ese teorema acotaba
# algo que el mecanismo no puede hacer — se cumplia trivialmente y no decia nada. Error de
# categoria, no cita floja.
#
# Lo que un ratchet SI necesita que se le acote es cuanto dano acumulado puede hacer antes
# de detenerse, y eso es un conteo. Derivacion completa en `COTA_RATCHET.es.md`.
def check_ratchet_bound(ok: bool) -> bool:
    from math import comb

    from app.assurance import (
        Assurance,
        LEARNED_FLOOR_CEILING,
        MIN_REJECTION_RATE,
        MIN_REQUESTS_PER_REGION,
    )

    print("\n--- 22. la cota nativa del ratchet ---")

    levels = list(Assurance)
    ceiling = levels.index(LEARNED_FLOOR_CEILING)

    # Proposicion 1: el numero de subidas por region esta acotado por los niveles que
    # quedan por encima de su base. No hay nada probabilistico: una secuencia monotona
    # sobre un orden total finito cambia a lo sumo esa cantidad de veces.
    per_base = {a.name: max(0, ceiling - levels.index(a)) for a in levels}
    ok &= check("el techo aprendido no llega a CERTIFIED - una estadistica sobre "
                "evidencia no es evidencia sobre certificabilidad",
                LEARNED_FLOOR_CEILING is not Assurance.CERTIFIED,
                LEARNED_FLOOR_CEILING.name)
    ok &= check("subidas acotadas por region: a lo sumo 2, desde el piso mas bajo",
                max(per_base.values()) == 2, str(per_base))
    ok &= check("una region que ya esta en el techo no puede volver a endurecer",
                per_base[LEARNED_FLOOR_CEILING.name] == 0)

    # Proposicion 2: endurecimiento espurio. Los dos splits son conjuntos de TAREAS
    # disjuntos, asi que condicionados en q son independientes y la probabilidad de que
    # una region sana endurezca es el producto.
    def qualifies(n: int, q: float) -> float:
        need = -(-n // 2)  # techo de n/2, que es lo que exige MIN_REJECTION_RATE=0.5
        return sum(comb(n, i) * q**i * (1 - q) ** (n - i) for i in range(need, n + 1))

    n = MIN_REQUESTS_PER_REGION
    p_clean = qualifies(n, 0.10) ** 2
    p_edge = qualifies(n, 0.45) ** 2
    ok &= check("MIN_REJECTION_RATE es la mitad, asi que 'califica' es 'mayoria rechazo'",
                abs(MIN_REJECTION_RATE - 0.5) < 1e-9)
    ok &= check("la replicacion es fuerte lejos del umbral (q=0.10: menos de 1 en 10.000)",
                p_clean < 1e-4, f"1 en {1 / p_clean:,.0f}")
    ok &= check("y DEBIL cerca del umbral (q=0.45: peor que 1 en 5) - se reporta, "
                "no se esconde",
                p_edge > 0.2, f"1 en {1 / p_edge:,.1f}")

    # Y la conjuncion de las dos: aun con la guarda debil, el dano total esta acotado.
    ok &= check("la monotonia acota el dano de su propia tasa de falsos positivos: "
                "<= 2 subidas por region, para siempre",
                max(per_base.values()) * 1 == 2)
    return ok


# --- 23. las demandas tipadas del request ------------------------------------------------
#
# POR QUE ES UN TEST Y NO UN COMENTARIO. `REQUEST_DEMANDS` es una tabla, y una tabla que el
# generador puede dejar atras es exactamente la falla que `has_oracle` ya costo: una celda
# nueva tomaba un default silencioso y volvia inmedible lo que la celda existia para medir.
# Aca el default no existe —`apply_request_demands` levanta— pero el test lo fija: si
# manana entra C9 y nadie declara su par, esto falla ANTES de generar un corpus.
#
# Y fija tambien el hallazgo que hace falta el par: hay celdas SINGULARES que exigen lectura
# total (C5, C8). Si alguien "simplifica" la tabla a un solo eje, esto lo agarra.
def check_request_demands(ok: bool) -> bool:
    from corpus.generate import (
        CARDINALITY,
        COMPLETENESS_DOMAIN,
        COVERAGE,
        HONEST_DETECTORS,
        REQUEST_DEMANDS,
        Generator,
        apply_request_demands,
    )

    print("\n--- 23. las demandas tipadas del request ---")

    ok &= check("toda terna declarada usa el vocabulario cerrado",
                all(c in CARDINALITY and v in COVERAGE and d in COMPLETENESS_DOMAIN
                    for c, v, d in REQUEST_DEMANDS.values()))

    # Toda celda que el generador PUEDE producir tiene que estar declarada.
    gen = Generator(seed=1)
    gen.build_world(12)
    gen.build_documents()
    tasks = gen.build_tasks(per_cell=1, widths=(4,))
    produced = {t.cell.split("_")[0] for t in tasks}
    undeclared = produced - set(REQUEST_DEMANDS)
    ok &= check("toda celda que el generador produce declara sus demandas",
                not undeclared, f"sin declarar: {sorted(undeclared)}" if undeclared
                else f"{len(produced)} celdas")

    apply_request_demands(tasks)
    ok &= check("aplicarlas deja los tres campos poblados en toda tarea",
                all(t.answer_cardinality and t.coverage_demanded
                    and t.completeness_domain for t in tasks))

    # El hallazgo de O-4: la cardinalidad NO implica la cobertura. Sin al menos una celda
    # singular-exhaustiva, el par es redundante y alguien lo va a colapsar.
    singular_exhaustive = [c for c, (card, cov, _) in REQUEST_DEMANDS.items()
                           if card == "singular" and cov == "exhaustive"]
    ok &= check("hay celdas SINGULARES que exigen lectura total - por eso son dos ejes "
                "y no uno", len(singular_exhaustive) >= 1, ", ".join(singular_exhaustive))

    # El quinto punto ciego, y el test que impide que vuelva. Antes de C9 la interseccion
    # entre "exige cobertura total" y "tiene dominio verificable barato" era VACIA, asi que
    # `C-COMPLETE` no tenia donde ejercitarse. Si alguien saca C9, esto falla y dice por que.
    verifiable = {c for c, (_, cov, dom) in REQUEST_DEMANDS.items()
                  if cov == "exhaustive" and dom == "from_question"}
    ok &= check("existe al menos una celda que exige cobertura Y cuyo dominio esta "
                "ENUNCIADO - sin eso C-COMPLETE no se puede medir en ningun lado",
                bool(verifiable), ", ".join(sorted(verifiable)) or "NINGUNA")

    # Y el eje sigue siendo necesario: `from_scope` es barato de enumerar y 8.6 midio que
    # no predice correccion. Si todo fuera `from_scope`, el eje seria decorativo.
    scopes = {dom for _, _, dom in REQUEST_DEMANDS.values()}
    ok &= check("el eje de dominio distingue mas de un valor entre las celdas",
                len(scopes) >= 3, ", ".join(sorted(scopes)))

    # `has_oracle` y el dominio de completitud NO son el mismo hecho. C9 no tiene detector
    # de correccion y si tiene dominio verificable; colapsarlos repetiria la conflacion que
    # `has_oracle` ya costo una vez.
    ok &= check("C9 declara dominio verificable SIN declarar detector de correccion - "
                "verificar completitud y verificar correccion son cosas distintas",
                REQUEST_DEMANDS["C9"][2] == "from_question"
                and HONEST_DETECTORS["C9"] is False)

    # Fail-closed, verificado y no supuesto.
    class _Fake:
        cell = "C99_invented"
        answer_cardinality = ""
        coverage_demanded = ""

    try:
        apply_request_demands([_Fake()])
        raised = False
    except ValueError:
        raised = True
    ok &= check("una celda no declarada FALLA en vez de tomar un default", raised)

    return ok


# --- 24. C-COMPLETE: la completitud se verifica, no se compra leyendo mas ----------------
#
# POR QUE EXISTE ESTA CLASE. `_analyze_demands2.py` midio que sobre celdas de cobertura
# exigida leer mas NO mejora la utilidad (corr +0,018, mediana -0,055, contra +0,259 donde
# no se exige). El arreglo intuitivo — "que lea todo" — esta refutado sobre 1.214 filas.
# Entonces la completitud necesita verificacion estructural, y verificarla es aritmetica.
#
# Lo que este test fija es lo que la implementacion NO puede degradar: fallar cerrado y
# ENTERO, distinguir lo que falta de lo que sobra, y no emitir sobre un dominio supuesto.
def check_completeness_contract(ok: bool) -> bool:
    from app.beliefs import Belief, BeliefBase, Provenance
    from app.contracts import complete

    print("\n--- 24. C-COMPLETE ---")

    base = BeliefBase()
    domain = "las unidades en alcance"
    base.assert_(Belief(domain, ["u-01", "u-02", "u-03"], 1.0, Provenance.COMPUTED))

    exact = complete(["u-01", "u-02", "u-03"], domain, base)
    ok &= check("una enumeracion que cubre el dominio se emite", exact.emitted)

    short = complete(["u-01", "u-02"], domain, base)
    ok &= check("a la que le falta un item NO se emite - una enumeracion incompleta es "
                "el modo de falla que PARECE bien formado",
                not short.emitted and short.missing == ["u-03"], short.refused or "")

    over = complete(["u-01", "u-02", "u-03", "u-99"], domain, base)
    ok &= check("un item fuera del dominio tampoco emite, y se reporta aparte de lo que "
                "falta - son dos fallas distintas",
                not over.emitted and over.extraneous == ["u-99"] and not over.missing)

    # El orden no es informacion: enumerar es un conjunto, no una secuencia.
    shuffled = complete(["u-03", "u-01", "u-02"], domain, base)
    ok &= check("el orden no cambia el veredicto", shuffled.emitted)

    # Repetir un item no compra cobertura.
    dup = complete(["u-01", "u-01", "u-02"], domain, base)
    ok &= check("repetir un item no cubre lo que falta",
                not dup.emitted and dup.missing == ["u-03"])

    # --- el piso de procedencia --------------------------------------------------------
    weak = BeliefBase()
    weak.assert_(Belief(domain, ["u-01"], 0.9, Provenance.ELICITED))
    guessed = complete(["u-01"], domain, weak)
    ok &= check("completitud sobre un dominio SUPUESTO no se emite - lo que el modelo cree "
                "que estaba en alcance no define el alcance",
                not guessed.emitted, guessed.refused or "")

    empty = complete(["u-01"], "un dominio sobre el que nadie dijo nada", base)
    ok &= check("sin creencia que defina el dominio, no hay contrato", not empty.emitted)

    scalar = BeliefBase()
    scalar.assert_(Belief(domain, 3, 1.0, Provenance.COMPUTED))
    counted = complete(["u-01", "u-02", "u-03"], domain, scalar)
    ok &= check("un dominio no enumerable se rechaza - un conteo no es un conjunto y "
                "coincidir en cardinalidad no es cubrir",
                not counted.emitted, counted.refused or "")

    # --- el residuo, declarado y no escondido -------------------------------------------
    #
    # La misma frontera que `_redteam_binding.py` encontro en C-NUM: la enumeracion cubre
    # su dominio entero y la ORACION que la envuelve dice lo contrario. "Ninguno de estos
    # tres figura en el registro" pasa el contrato con los tres items correctos, porque la
    # negacion vive en la prosa conectiva y la prosa conectiva no ocupa ninguna ranura.
    ok &= check("el contrato emite igual bajo una envoltura que lo niega - RESIDUO "
                "declarado, no un test que falla", exact.emitted)
    ok &= check("y la garantia se declara relativa al dominio, nunca al mundo",
                exact.scope_is_declared_not_world
                and exact.as_dict()["scope"] == "dominio declarado, no el mundo")

    return ok


# --- 25. el registro es autodescriptivo, y no mezcla modelos -----------------------------
#
# LO QUE ESTO CUESTA CUANDO FALTA, MEDIDO. `config.py` dice desde el principio que la
# huella de decodificacion «goes into every cache key and every result row». En la fila NO
# ESTABA: lo unico que separaba a `gpt-5-chat` de `gpt-5.4-nano` era en que carpeta habia
# caido el archivo.
#
# R-1 quedo meses como «intentado, no concluyente» por eso. Un replay sellado reconstruyo
# los ajustes con `Settings.from_env()` —que devuelve el primer modelo, congelado— y fallo
# el 100% de las claves. La clave de cache es `sha256(fingerprint, payload)`, asi que con
# otro modelo no acierta una sola entrada aunque el cache este intacto, y nada en el error
# lo dice. Con la huella EN la fila, el replay la lee del registro en vez de adivinarla.
#
# Y hay DOS invariantes distintos, que el primer intento de esta guarda confundio:
#   (1) un archivo no puede mezclar decodificaciones -> es un error, levanta;
#   (2) que el LECTOR coincida no hace falta para analizar -> avisa, no levanta.
def check_record_is_self_describing(ok: bool) -> bool:
    import json
    import tempfile
    from dataclasses import replace

    from app.config import Settings
    from app.runner import Row, Runner

    print("\n--- 25. el registro dice con que modelo se produjo ---")

    ok &= check("Row declara la huella de decodificacion",
                "fingerprint" in Row.__dataclass_fields__)

    base = Settings.from_env()
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        settings = replace(base, results_dir=scratch)
        runner = Runner(settings, "gold_p19", retriever_arm="hybrid",
                        surface_variant="basic")
        path = scratch / "gold_p19_rows.jsonl"

        def write(fps: list[str]) -> None:
            path.write_text("\n".join(
                json.dumps({"task_id": f"t{i}", "paradigm": "react", "trial": 0,
                            "utility": 1.0, "fingerprint": fp})
                for i, fp in enumerate(fps)
            ) + "\n", encoding="utf-8")

        mine = settings.fingerprint()
        write([mine, mine])
        ok &= check("un archivo de una sola decodificacion se lee",
                    len(runner.load_rows()) == 2)

        write([mine, "otro-modelo|otra-version|t=0.0|seed=7|max=4096"])
        try:
            runner.load_rows()
            raised = False
        except ValueError:
            raised = True
        ok &= check("un archivo que MEZCLA decodificaciones levanta - promediar entre "
                    "modelos no mide un paradigma, mide el modelo", raised)

        # Filas sin huella son anteriores a que se estampara. Negarlas volveria ilegible
        # todo el registro ya pagado, asi que pasan.
        path.write_text(json.dumps(
            {"task_id": "viejo", "paradigm": "react", "trial": 0, "utility": 1.0}
        ) + "\n", encoding="utf-8")
        ok &= check("una fila sin huella - anterior al estampado - se sigue leyendo",
                    len(runner.load_rows()) == 1)

        # Y el caso que costo R-1: el archivo es coherente pero el LECTOR es otro modelo.
        # No levanta, porque analizar no llama al modelo.
        Runner._warned_fingerprint = False  # noqa: SLF001
        write(["gpt-5.4-nano|2025-04-01-preview|t=0.0|seed=7|max=4096"] * 2)
        try:
            n = len(runner.load_rows())
            fine = n == 2
        except ValueError:
            fine = False
        ok &= check("un lector con OTROS ajustes puede analizar igual - avisa, no levanta",
                    fine)

    return ok


# --- 26. el contador de malformaciones tiene que poder dispararse -------------------------
#
# POR QUE ESTE TEST EXISTE. El replay sellado del registro completo dio CERO malformaciones
# en 336 filas y cinco brazos, y ese cero es un resultado util —descarta que algun paradigma
# pierda utilidad por no acertar el FORMATO en vez de por no resolver la tarea—. Pero un cero
# de un contador que nunca se cablea es indistinguible de un cero real, y leerlo como
# hallazgo seria exactamente el error que este banco no comete.
#
# Asi que el cero se apoya en dos cosas: que el contador SE DISPARA cuando corresponde, y que
# los sitios de llamada le pasan la superficie.
def check_malformation_counter(ok: bool) -> bool:
    import inspect

    from app.paradigms import dag, modern
    from app.paradigms.parsing import extract_json, well_formed

    print("\n--- 26. el contador de malformaciones ---")

    class _Sink:
        def __init__(self):
            self.malformed = 0
            self.dropped = 0

        def note_malformed(self):
            self.malformed += 1

        def note_dropped(self, n):
            self.dropped += n

    # Se dispara donde el modelo NO entrego la forma.
    sink = _Sink()
    extract_json("no hay json aca", sink=sink)
    extract_json('{"a": 1}', "b", sink=sink)          # clave ausente
    extract_json("{roto", sink=sink)                   # json invalido
    extract_json("", sink=sink)                        # respuesta vacia
    ok &= check("cuenta las cuatro formas de no entregar la forma pedida",
                sink.malformed == 4, f"conto {sink.malformed}")

    # NO se dispara cuando el modelo si entrego.
    clean = _Sink()
    extract_json('{"a": 1}', "a", sink=clean)
    extract_json('texto y despues {"ok": true} y mas texto', sink=clean)
    ok &= check("no cuenta cuando el modelo SI entrego la forma", clean.malformed == 0)

    # Los descartados van aparte: forma correcta con elementos incompletos.
    drop = _Sink()
    well_formed([{"id": 1, "q": "a"}, {"id": 2}, "no soy dict"], "id", "q", sink=drop)
    ok &= check("los elementos incompletos se cuentan APARTE de la malformacion",
                drop.dropped == 2 and drop.malformed == 0, f"dropped={drop.dropped}")

    # Y lo que hace que el cero medido signifique algo: que los sitios de llamada de los
    # paradigmas que PARSEAN JSON le pasen la superficie. Un sitio sin `sink=` no cuenta
    # nunca, y su cero no dice nada.
    unwired = []
    for module in (dag, modern):
        src = inspect.getsource(module)
        for line_no, line in enumerate(src.splitlines(), 1):
            if "extract_json(" in line and "sink=" not in line and "def " not in line:
                # Puede estar partido en dos lineas: se mira la siguiente tambien.
                nxt = src.splitlines()[line_no] if line_no < len(src.splitlines()) else ""
                if "sink=" not in nxt:
                    unwired.append(f"{module.__name__}:{line_no}")
    ok &= check("todo sitio que parsea JSON del modelo pasa la superficie - sin eso su "
                "cero no significa cero, significa sin instrumentar",
                not unwired, ", ".join(unwired) if unwired else "todos cableados")

    return ok


# --- 27. el dial impone lo que declara ---------------------------------------------------
#
# `theta_may_learn_online` vivia en el perfil de garantia y NO LO LEIA NADIE. La invariante
# «nada aprende adentro de un request» se cumplia porque `Plasticity.apply` solo se llama
# desde el camino offline — o sea, por casualidad.
#
# Una invariante que se cumple por casualidad no es una invariante: es una coincidencia que
# el proximo cambio rompe sin que nada avise. Y la que esta en juego es la nuclear: si theta
# aprendiera adentro del request, dos requests identicos decidirian distinto, que es
# exactamente lo que «misma base de creencias => misma decision» promete que no pasa.
def check_dial_is_enforced(ok: bool) -> bool:
    from app.assurance import PROFILES, Assurance
    from app.policy import (
        Episode,
        OnlineLearningRefused,
        Plasticity,
        no_online_learning,
    )

    print("\n--- 27. el dial impone lo que declara ---")

    episode = Episode(task_id="t", region="r", paradigm="react",
                      utility=1.0, cost_tokens=1, was_best=True)

    stats = {}
    Plasticity.apply(stats, episode)
    ok &= check("offline, acumular esta PERMITIDO - es donde el aprendizaje debe ocurrir",
                bool(stats))

    try:
        with no_online_learning():
            Plasticity.apply({}, episode)
        refused = False
    except OnlineLearningRefused:
        refused = True
    ok &= check("adentro de un request, acumular LEVANTA", refused)

    after = {}
    Plasticity.apply(after, episode)
    ok &= check("saliendo del bloque vuelve a permitir - la guarda no es global",
                bool(after))

    # Y que el perfil siga declarando lo mismo que la guarda impone, o vuelve a haber dos
    # fuentes de la misma decision.
    declared = {a: p.theta_may_learn_online for a, p in PROFILES.items()}
    ok &= check("ningun nivel por encima del mas bajo declara aprendizaje en linea",
                not any(v for a, v in declared.items() if a is not Assurance.EXPLORATORY),
                ", ".join(f"{a.name}={v}" for a, v in declared.items()))

    return ok


# --- 28. la consolidacion es idempotente, y el peso firmado es el que decide -------------
#
# DOS DEFECTOS QUE SE TAPABAN ENTRE SI, y salieron juntos al probar lo primero.
#
# (a) `candidate` partia de una copia de las estadisticas del incumbente y le REAPLICABA la
#     lista entera de episodios, sin saber cuales ya estaban adentro. Correr la
#     consolidacion dos veces sobre el mismo registro movia el peso el doble hacia su punto
#     fijo e inflaba `episodes` — que es la cuenta que decide si una region tiene con que
#     decidir. La evidencia crecia por repetir un proceso, no por haber medido mas.
#
# (b) El peso se redondeaba al SERIALIZAR y no al aplicar, asi que lo que se FIRMA no era
#     lo que DECIDE: un bundle recargado desde disco resolvia con un numero distinto del
#     que tenia en memoria el proceso que lo escribio. Y como `candidate` copia via
#     `from_dict(as_dict())`, cada ciclo perdia un poco mas.
def check_consolidation_is_idempotent(ok: bool) -> bool:
    from app.policy import Episode, Plasticity, PolicyBundle, Stat

    print("\n--- 28. consolidar dos veces no cuenta dos veces ---")

    episodes = [
        Episode(task_id=f"t{i}", region="r", paradigm="react",
                utility=1.0, cost_tokens=10, was_best=True)
        for i in range(3)
    ]
    base = PolicyBundle(version=0, created_at="x", fallback="react", tau=0.0).sign()
    once = Plasticity.candidate(base, episodes, tau=0.0)
    twice = Plasticity.candidate(once, episodes, tau=0.0)

    a, b = once.stat("r", "react"), twice.stat("r", "react")
    ok &= check("el peso no se mueve al reaplicar el mismo registro",
                a.weight == b.weight, f"{a.weight} vs {b.weight}")
    ok &= check("la cuenta de evidencia tampoco - es la que decide si una region puede "
                "decidir", a.episodes == b.episodes == 3, f"{a.episodes} vs {b.episodes}")
    ok &= check("y el bundle DECLARA que salteo", "already absorbed" in twice.notes,
                twice.notes)

    # Un episodio NUEVO si entra: la guarda no puede congelar el aprendizaje.
    fresh = episodes + [Episode(task_id="t9", region="r", paradigm="react",
                                utility=1.0, cost_tokens=10, was_best=True)]
    third = Plasticity.candidate(twice, fresh, tau=0.0)
    ok &= check("un episodio NUEVO si se absorbe - la guarda no congela el aprendizaje",
                third.stat("r", "react").episodes == 4)

    # Lo firmado es lo que decide.
    ok &= check("el peso round-tripea EXACTO por su propia serializacion",
                Stat.from_dict(a.as_dict()).weight == a.weight)

    return ok


# --- 29. la promocion decide sobre un intervalo ------------------------------------------
#
# LA GUARDA COMPARABA DOS PUNTOS, y eso no es una guarda: es una moneda con sesgo. Sobre un
# holdout chico, un candidato que gana por 0,001 gana por RUIDO la mitad de las veces — y
# una vez promovido queda como incumbente que el siguiente ciclo tiene que superar, asi que
# el error se hereda en vez de corregirse.
#
# Y HAY UNA TRAMPA AL PROBARLO, que este test evita a proposito: si el ruido se agrega igual
# a los dos bundles, el bootstrap PAREADO lo cancela — correctamente— y el intervalo colapsa
# a un punto. Para poner a prueba la guarda, lo que tiene que variar por episodio es la
# DIFERENCIA entre los dos, no el nivel de cada uno.
def check_promotion_has_an_interval(ok: bool) -> bool:
    import random

    from app.policy import Episode, PolicyBundle, promote

    print("\n--- 29. la promocion decide sobre un intervalo ---")

    holdout = [
        Episode(task_id=f"t{i}", region="r", paradigm="react",
                utility=1.0, cost_tokens=10, was_best=True)
        for i in range(20)
    ]
    incumbent = PolicyBundle(version=1, created_at="x", fallback="react", tau=0.0).sign()
    candidate = PolicyBundle(version=2, created_at="x", fallback="react", tau=0.0).sign()

    def valuer(gains):
        def fn(bundle, sample):
            if bundle.version == 1:
                return 0.0
            return sum(gains[e.task_id] for e in sample) / len(sample)
        return fn

    rng = random.Random(7)
    noisy = {e.task_id: rng.gauss(0.02, 0.5) for e in holdout}
    solid = {e.task_id: 0.02 + abs(rng.gauss(0, 0.005)) for e in holdout}

    v_noise = promote(incumbent, candidate, holdout, valuer(noisy))
    ok &= check("una ganancia que se da en promedio pero se pierde en muchos episodios "
                "NO promueve", not v_noise.accepted,
                f"[{v_noise.gain_low:+.4f}, {v_noise.gain_high:+.4f}]")
    ok &= check("y el intervalo cruza el cero, que es la razon",
                v_noise.gain_low is not None and v_noise.gain_low < 0 < v_noise.gain_high)

    v_real = promote(incumbent, candidate, holdout, valuer(solid))
    ok &= check("una ganancia chica pero presente en TODOS los episodios SI promueve",
                v_real.accepted,
                f"[{v_real.gain_low:+.4f}, {v_real.gain_high:+.4f}]")
    ok &= check("y su intervalo no toca el cero", v_real.gain_low > 0)

    # Deterministico: promover tiene que ser tan reproducible como rutear.
    again = promote(incumbent, candidate, holdout, valuer(solid))
    ok &= check("dos corridas sobre el mismo holdout dan el MISMO intervalo",
                (again.gain_low, again.gain_high) == (v_real.gain_low, v_real.gain_high))

    # Sin holdout no se promueve nada, y sin intervalo se DICE.
    empty = promote(incumbent, candidate, [], valuer(solid))
    ok &= check("sin holdout se rechaza: no se promueve politica sin verificar",
                not empty.accepted)
    one = promote(incumbent, candidate, holdout[:1], valuer(solid))
    ok &= check("con un solo episodio no hay intervalo, y la razon LO DICE",
                one.gain_low is None and "SIN INTERVALO" in one.reason, one.reason)

    return ok


# --- 30. la regla de parada -------------------------------------------------------------
#
# HOY EL ESTANCAMIENTO ES UNA NOTA AL MODELO: «las ultimas 3 busquedas no trajeron nada,
# considera leer». Eso es persuasion, y el invariante del producto dice que el LLM es sensor
# y NO maneja flujo de control. Un rechazo tipado si es flujo de control decidido por
# codigo.
#
# Lo que este test fija es que el rechazo sea QUIRURGICO: quita la accion que el registro
# muestra que no compra nada —buscar otra vez cuando ya no aparece nada nuevo— y deja
# intactas las productivas. Un rechazo que ademas bloqueara leer convertiria una regla de
# ahorro en una regla de fallar.
def check_stopping_rule(ok: bool) -> bool:
    import json

    from app.retrieval import LexicalRetriever
    from app.tools import CorpusView, ToolSurface

    print("\n--- 30. la regla de parada ---")

    docs = {f"u-{i}": f"unidad {i} sin nada que ver con la consulta" for i in range(4)}
    view = CorpusView(task_id="t", documents=docs, unit_ids=list(docs),
                      relevant_units=[])
    lex = LexicalRetriever()

    def surface(limit: int) -> ToolSurface:
        return ToolSurface(view=view, hybrid=lex, semantic=lex, lexical=lex,
                           variant="basic", budget_tokens=60_000,
                           stop_on_barren=limit)

    # Apagada: el default no cambia nada, que es lo que deja intacto el registro ya pagado.
    off = surface(0)
    for _ in range(6):
        off.dispatch("search", {"query": "zzzz-inexistente"})
    ok &= check("apagada por defecto, nada se rechaza", off.barren_refusals == 0)

    # Encendida: rechaza a partir del umbral.
    on = surface(2)
    results = [on.dispatch("search", {"query": "zzzz-inexistente"}) for _ in range(5)]
    refused = [r for r in results if '"refused"' in r]
    ok &= check("encendida, rechaza cuando la busqueda dejo de traer nada nuevo",
                on.barren_refusals > 0, f"{on.barren_refusals} rechazos de 5 busquedas")

    if refused:
        body = json.loads(refused[0])
        ok &= check("el rechazo DICE la alternativa - uno que no la dice deja al modelo "
                    "reintentando lo mismo con otras palabras, que es el mismo gasto",
                    "read" in body.get("available", []), str(body.get("available")))
        ok &= check("y dice QUE queda sin leer, no solo cuanto",
                    isinstance(body.get("unread_unit_ids"), list))

    # Quirurgico: leer y responder siguen disponibles.
    try:
        on.dispatch("read", {"unit_ids": "u-0"})
        reads = True
    except Exception:  # noqa: BLE001 — cualquier fallo aca es el defecto que se busca
        reads = False
    ok &= check("leer sigue disponible despues del rechazo - la regla ahorra, no falla",
                reads)

    # LA CORRECCION QUE P20 OBLIGO: retirar, no rechazar. Un rechazo lo esquiva el modelo
    # re-emitiendo con otras palabras —69% de las veces, medido— asi que la regla agregaba
    # una vuelta en vez de quitar el desperdicio. Quitar la decision es no ofrecer la
    # accion.
    from app.tools import SEARCH_TOOLS, specs_for

    fresh = surface(2)
    antes = {t["function"]["name"] for t in specs_for("basic", drop=fresh.withdrawn())}
    ok &= check("al empezar, las busquedas se ofrecen",
                set(SEARCH_TOOLS) <= antes, ", ".join(sorted(antes)))
    for _ in range(3):
        fresh.dispatch("search", {"query": "zzzz-inexistente"})
    despues = {t["function"]["name"] for t in specs_for("basic", drop=fresh.withdrawn())}
    ok &= check("pasado el limite DEJAN DE OFRECERSE - el modelo no puede pedir una "
                "accion que no existe", not (set(SEARCH_TOOLS) & despues),
                ", ".join(sorted(despues)))
    ok &= check("y leer sigue ofreciendose, que es lo que hace segura la regla - P20b "
                "midio que cortar la busqueda no cuesta utilidad", "read" in despues)

    # Las tres busquedas quedan cubiertas: rechazar solo una deja la fuga abierta.
    for tool in ("keyword_search", "semantic_search"):
        probe = surface(1)
        probe.dispatch("search", {"query": "zzzz-inexistente"})
        out = probe.dispatch(tool, {"query": "zzzz-inexistente"})
        ok &= check(f"`{tool}` tambien queda cubierto", '"refused"' in out)

    # Y la llamada rechazada QUEDA en la secuencia: el modelo la pidio.
    ok &= check("una busqueda rechazada sigue en la secuencia - una traza que solo guarda "
                "lo que se ejecuto describe una politica que nadie tomo",
                on.sequence.count("search") == 5, str(on.sequence.count("search")))

    return ok


# --- 31. disponibilidad y guarda son cosas distintas -------------------------------------
#
# DOS PREGUNTAS QUE SE MEZCLABAN. «¿Esta tool EXISTE en esta variante?» y «¿esta llamada
# CABE?» son distintas y se resuelven en lugares distintos: la primera es una funcion, la
# segunda es aritmetica sobre el presupuesto declarado.
#
# La primera estaba decidida en tres `if self.variant ...` desparramados adentro de
# `dispatch`, cada uno con su forma y ninguno cerca de `specs_for`, que es quien decide que
# se le OFRECE al modelo. El comentario de `ACCOUNTING_VARIANTS` ya advertia que las dos
# listas podian separarse; una advertencia en prosa no lo impide y este test si.
def check_availability_and_guard(ok: bool) -> bool:
    import json

    from app.retrieval import LexicalRetriever
    from app.tools import (
        VARIANTS,
        CorpusView,
        ToolFailure,
        ToolSurface,
        available,
        specs_for,
    )

    print("\n--- 31. disponibilidad y guarda ---")

    # (1) Lo ofrecido ES lo despachable, en TODA variante. Ofrecer una tool que dispatch
    #     despues rechaza le hace gastar al modelo una vuelta en algo que nunca iba a
    #     andar, y el brazo paga ese token como si fuera suyo.
    drift = []
    for variant in VARIANTS:
        offered = sorted(t["function"]["name"] for t in specs_for(variant))
        dispatchable = [n for n in offered if available(n, variant)]
        if offered != dispatchable:
            drift.append(f"{variant}: {sorted(set(offered) - set(dispatchable))}")
    ok &= check("en toda variante, lo ofrecido es exactamente lo despachable",
                not drift, "; ".join(drift) if drift else f"{len(VARIANTS)} variantes")

    # (2) Llamar a lo no ofrecido es un error DEL MODELO, no del harness: `ToolFailure`,
    #     que el loop compartido atrapa. Con `ValueError` la misma llamada mataba la tarea
    #     en unos paradigmas y degradaba en otros — dos brazos puntuados distinto por el
    #     mismo error del modelo.
    docs = {"u-0": "texto corto"}
    view = CorpusView(task_id="t", documents=docs, unit_ids=["u-0"], relevant_units=[])
    lex = LexicalRetriever()
    basic = ToolSurface(view=view, hybrid=lex, semantic=lex, lexical=lex,
                        variant="basic", budget_tokens=60_000)
    try:
        basic.dispatch("read_all", {})
        typed = False
    except ToolFailure:
        typed = True
    except Exception:  # noqa: BLE001
        typed = False
    ok &= check("una tool no ofrecida levanta ToolFailure, no una excepcion del harness",
                typed)

    # (3) LA GUARDA es otra cosa: donde la tool existe, decide GRANULARIDAD por tamano.
    small = ToolSurface(view=view, hybrid=lex, semantic=lex, lexical=lex,
                        variant="accounting", budget_tokens=60_000)
    body = json.loads(small.dispatch("read_all", {}))
    ok &= check("documento chico: la guarda deja pasar el texto completo",
                body["granularity"] == "full_text", body["granularity"])

    big_docs = {f"u-{i}": "x" * 40_000 for i in range(20)}
    big_view = CorpusView(task_id="t", documents=big_docs, unit_ids=list(big_docs),
                          relevant_units=[])
    big = ToolSurface(view=big_view, hybrid=lex, semantic=lex, lexical=lex,
                      variant="accounting", budget_tokens=8_000)
    body = json.loads(big.dispatch("read_all", {}))
    ok &= check("documento grande: NO trunca en silencio - devuelve resumenes de TODAS "
                "las unidades y dice por que",
                body["granularity"] == "summaries"
                and len(body["units"]) == len(big_docs)
                and "reason" in body)
    ok &= check("y el rechazo de granularidad queda CONTADO",
                big.bulk_read_refusals == 1)

    return ok


# --- 32. la confianza en credencia elicitada es politica, y va FIRMADA -------------------
#
# EL ROUTER RECIBIA UN OBJETO QUE NADIE LE PASABA. Cinco sitios construyen `Router` y
# ninguno pasaba `calibration`, asi que `trustworthy` era False siempre.
#
# Y el efecto no era neutro. Sin confianza, el piso derivado sube a OBSERVED en A2+: o sea
# que **A2 con piso ELICITED era inalcanzable por construccion**. La evidencia para ganarlo
# se computaba desde el log, se persistia, y se tiraba.
#
# La correccion no fue pasar el parametro en los cinco sitios: un parametro se puede
# olvidar, y se olvido en los cinco. Vive en el BUNDLE FIRMADO, por la misma razon que los
# pisos aprendidos — cambia lo que un request puede hacer, asi que es politica, tiene que
# estar versionada y firmada, y no debe poder instalarse por fuera de la promocion.
def check_trust_is_signed_policy(ok: bool) -> bool:
    import copy
    import json
    import tempfile
    from pathlib import Path as _Path

    from app.policy import PolicyBundle

    print("\n--- 32. la confianza elicitada es politica firmada ---")

    bundle = PolicyBundle(version=1, created_at="x", fallback="react", tau=0.0,
                          trusts_elicited=True).sign()
    ok &= check("un bundle con confianza ganada firma y verifica", bundle.verify())

    with tempfile.TemporaryDirectory() as tmp:
        path = _Path(tmp) / "theta.json"
        path.write_text(json.dumps(bundle.as_dict(), ensure_ascii=False),
                        encoding="utf-8")
        back = PolicyBundle.load(path)
        ok &= check("sobrevive el round-trip por disco y sigue verificando",
                    back.trusts_elicited is True and back.verify())

    tampered = copy.deepcopy(bundle)
    tampered.trusts_elicited = False
    ok &= check("editarla INVALIDA la firma - no se puede bajar la confianza sin pasar "
                "por la promocion", not tampered.verify())

    # El default es NO confiar: la confianza se gana, no se supone.
    fresh = PolicyBundle(version=1, created_at="x", fallback="react", tau=0.0).sign()
    ok &= check("por defecto NO se confia - se gana, no se supone",
                fresh.trusts_elicited is False)

    # Y el router la lee de ahi, no de un parametro que se pueda olvidar.
    import inspect

    from app.router import Router

    sig = inspect.signature(Router.__init__)
    ok &= check("el router ya NO toma la confianza por parametro - la lee del bundle",
                "calibration" not in sig.parameters
                and "trusts_elicited" not in sig.parameters,
                ", ".join(sig.parameters))

    return ok


# --- 33. el horizonte tiene evidencia propia ---------------------------------------------
#
# `horizon_unknown` llevaba la credencia Y la procedencia de `coupling`. El propio texto lo
# decia: «estimated alongside coupling». Dos consecuencias, y la segunda es una violacion
# del reticulo:
#
#   (1) El horizonte no tenia evidencia propia. La calibracion es POR PROPOSICION
#       justamente porque un modelo puede ser confiable sobre una cosa y pesimo sobre otra,
#       y compartir credencia vuelve esa distincion inexpresable.
#
#   (2) Tras una sonda, `coupling_provenance` es OBSERVED — y el horizonte lo heredaba. Una
#       proposicion que NADIE midio alcanzaba el piso que las acciones irreversibles exigen.
#       La sonda lee una unidad para testear ACOPLAMIENTO: no toca el horizonte.
#
# Y el eje importa: P15 senalo al horizonte como la dimension que le faltaba a la region.
# Construirlo sobre una credencia prestada lo vuelve inmedible.
def check_horizon_has_its_own_evidence(ok: bool) -> bool:
    from app.assurance import Assurance, resolve
    from app.beliefs import Provenance
    from app.rules import ELICITED_PRIOR_CREDENCE, BeliefPolicy, sense

    print("\n--- 33. el horizonte tiene evidencia propia ---")

    task = {
        "task_id": "t", "question": "q", "unit_ids": ["u-0"],
        "budget_tokens": 60_000, "has_oracle": True,
    }
    policy = BeliefPolicy.from_trust(False, 0.05)

    # El caso que importa: la sonda OBSERVO el acoplamiento y NO el horizonte.
    base = sense(
        task, policy,
        coupling=0.9, coupling_provenance=Provenance.OBSERVED, coupling_credence=0.95,
        horizon_unknown=True,
        horizon_provenance=Provenance.ELICITED,
        horizon_credence=ELICITED_PRIOR_CREDENCE,
    )
    ok &= check("el acoplamiento queda OBSERVED - la sonda si lo midio",
                base.provenance("coupling_tight") is Provenance.OBSERVED)
    ok &= check("el horizonte NO sube a OBSERVED con la evidencia de la sonda",
                base.provenance("horizon_unknown") is Provenance.ELICITED,
                base.provenance("horizon_unknown").value)
    ok &= check("y su credencia es la suya, no la de la sonda",
                base.credence("horizon_unknown") == ELICITED_PRIOR_CREDENCE,
                f"{base.credence('horizon_unknown')} vs sonda 0.95")

    # Sin credencia propia no se asienta: una credencia prestada era peor que ninguna.
    silent = sense(
        task, policy,
        coupling=0.9, coupling_provenance=Provenance.OBSERVED, coupling_credence=0.95,
        horizon_unknown=True, horizon_credence=0.0,
    )
    ok &= check("sin credencia propia, el horizonte NO se asienta - una prestada era "
                "peor que ninguna", silent.current("horizon_unknown") is None)

    # Y el prior elicitado es una constante DECLARADA, no un numero suelto.
    ok &= check("el prior elicitado esta declarado con nombre y esta por debajo de 1",
                0.0 < ELICITED_PRIOR_CREDENCE < 1.0, str(ELICITED_PRIOR_CREDENCE))

    # LO QUE HACE LEGITIMO AL PRIOR, y ata P-3 con P-4: el piso EFECTIVO, no el
    # declarado. `PROFILES[ACCOUNTABLE].derived_floor` ES `ELICITED` — a proposito: ese
    # nivel admite credencia elicitada CUANDO la calibracion se gano. Sin ganarla,
    # `resolve` lo sube a OBSERVED, que es exactamente el mecanismo de P-3.
    #
    # Chequear el perfil estatico habria dado un falso negativo sobre el codigo correcto.
    for trusted, expected in ((False, Provenance.OBSERVED), (True, Provenance.ELICITED)):
        decision = resolve(base, requested=Assurance.ACCOUNTABLE,
                           calibration_trustworthy=trusted)
        ok &= check(
            f"en ACCOUNTABLE con calibracion {'ganada' if trusted else 'sin ganar'}, "
            f"el piso efectivo es {expected.value.upper()}",
            decision.profile.derived_floor is expected,
            decision.profile.derived_floor.value,
        )
    certified = resolve(base, requested=Assurance.CERTIFIED,
                        calibration_trustworthy=True)
    ok &= check("y en CERTIFIED no admite ELICITED ni con calibracion ganada - una "
                "estadistica sobre evidencia no es evidencia",
                certified.profile.derived_floor.rank > Provenance.ELICITED.rank,
                certified.profile.derived_floor.value)

    return ok


# --- 34. las entradas de analisis giran --------------------------------------------------
#
# OCHO METODOS PUBLICOS DEL RUNNER NO TENIAN UNA SOLA PRUEBA: `study`, `replicates`,
# `report`, `consolidate`, `save_report`, `decide_for`, `surface_for`, `features_for`. Son
# exactamente los que producen todos los veredictos del banco.
#
# No es hipotetico: en el mismo dia dos defectos pasaron por ese agujero. Uno era un kwarg
# que ya no existia y dejaba `report()` roto de plano; el otro, un `KeyError` cuando la
# escalera de cascada nombra brazos que el estudio no corrio — el catalogo tiene trece y una
# corrida mide cinco. Los dos aparecieron usando el codigo a mano, no probandolo.
#
# HERMETICO A PROPOSITO. El registro es sintetico y va a un directorio temporal: lo que se
# verifica es que la maquina GIRE, no los numeros. Un test atado al registro pagado seria un
# test que cambia de veredicto cuando cambia el dato, que es lo contrario de una prueba.
def check_analysis_entrypoints(ok: bool) -> bool:
    import json
    import tempfile
    from dataclasses import replace as dc_replace
    from pathlib import Path as _Path

    from app.assurance import Assurance
    from app.config import Settings
    from app.runner import Runner

    print("\n--- 34. las entradas de analisis giran ---")

    base = Settings.from_env()
    with tempfile.TemporaryDirectory() as tmp:
        settings = dc_replace(base, results_dir=_Path(tmp))
        runner = Runner(settings, "gold_p19", retriever_arm="hybrid",
                        surface_variant="basic")

        # Un registro sintetico sobre las tareas REALES del corpus, con solo DOS brazos:
        # asi la escalera de cascada nombra brazos ausentes, que es el caso que rompia.
        tasks = runner._tasks[:8]  # noqa: SLF001
        rows = []
        for i, task in enumerate(tasks):
            for paradigm in ("react", "rewoo"):
                for trial in range(2):
                    rows.append({
                        "task_id": task["task_id"], "cell": task["cell"],
                        "paradigm": paradigm, "trial": trial,
                        "region": "many/oracle/loose",
                        "utility": 1.0 if (i + trial) % 2 == 0 else 0.0,
                        "cost_tokens": 1000 + i * 100,
                        "calls": 3, "wall_seconds": 0.1, "iterations": 3,
                        "cross_unit_lookups": 1, "hallucinated_units": 0,
                        "tool_usage": {"tooled_calls": 3, "units_read": 2},
                        "infeasible": False, "retriever": "hybrid",
                        "has_oracle": bool(task.get("has_oracle", True)),
                        "answer": "x", "truth_coupling": 0.3,
                        "n_units": len(task["unit_ids"]),
                        "phi_coupling": 0.3, "phi_continuation": 0.2,
                    })
        runner._results_path.write_text(  # noqa: SLF001
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
            encoding="utf-8",
        )

        ok &= check("load_rows lee el registro", len(runner.load_rows()) == len(rows))

        study = runner.study()
        ok &= check("study arma celdas promediadas por trial",
                    set(study.paradigms) == {"react", "rewoo"},
                    ", ".join(sorted(study.paradigms)))
        ok &= check("y elige un mejor fijo entre los que CORRIERON",
                    study.best_fixed() in ("react", "rewoo"), study.best_fixed())

        ok &= check("replicates da varianza por celda", bool(runner.replicates()))
        ok &= check("episodes promedia por celda antes del oraculo",
                    len(runner.episodes()) == len(tasks) * 2)

        # Lo que rompia: la escalera nombra brazos que este estudio no corrio.
        cascade = study.cascade_value(["direct", "react"], detector_sensitivity=1.0)
        ok &= check("la cascada con un brazo ausente NO levanta - lo DICE, que es "
                    "distinto de devolver un cero que se lee como «no rinde»",
                    "note" in cascade and "no corrio" in cascade["note"],
                    str(cascade.get("note", ""))[:60])

        # Y las dos entradas completas, en los dos diales que importan.
        # El contrato del informe, nombrado: son las piezas sobre las que se decide.
        # Chequear "que devuelva un dict" no habria agarrado ninguno de los dos defectos;
        # exigir las claves si, porque cada una viene de un camino distinto.
        REQUIRED = {"summary", "cascade", "selection_terms", "risk_coverage",
                    "oracle_gap_credibility", "calibration", "theta_signature"}
        for dial in (Assurance.STANDARD, Assurance.ACCOUNTABLE):
            report = runner.report(assurance=dial)
            missing = REQUIRED - set(report)
            ok &= check(f"report({dial.name}) corre entero y trae todas sus piezas",
                        isinstance(report, dict) and not missing,
                        f"faltan {sorted(missing)}" if missing
                        else f"{len(report)} claves")

        # `save_report` era la ultima entrada sin tocar, y escribe lo que se lee despues.
        written = runner.save_report(runner.report())
        ok &= check("save_report deja el informe en disco y legible",
                    _Path(str(written)).exists()
                    and isinstance(json.loads(_Path(str(written)).read_text(
                        encoding="utf-8")), dict))

        # A2 declara `log_belief_base`, y honrarlo es lo que cierra el bucle de
        # calibracion. Que el flag exista y nadie lo lea fue P-10; que se lea y no
        # escriba nada seria lo mismo con otro disfraz.
        ok &= check("en A2 el log de creencias se ESCRIBE - es lo unico que puede "
                    "alimentar la calibracion",
                    runner.store.belief_log_path.exists()
                    and sum(1 for _ in runner.store.iter_belief_log()) > 0)

        # Y las tres entradas por-tarea.
        task = tasks[0]
        ok &= check("features_for computa phi sin llamar al modelo",
                    runner.features_for(task, allow_derived=False).n_units > 0)
        ok &= check("surface_for construye la superficie de esa tarea",
                    bool(runner.surface_for(task).unit_ids()))

    return ok


# --- 35. el producto deja rastro ---------------------------------------------------------
#
# `serve.py` DECIDIA, EJECUTABA, RESPONDIA — Y NO ESCRIBIA NADA. Dos consecuencias, y son
# las mismas que el banco ya pago tres veces hoy:
#
#   sin registro de la decision  el EXPLAIN existe solo mientras dura la respuesta. Un
#                                artefacto de explicacion que no se puede consultar despues
#                                no explica: decora.
#   sin log de creencias         la calibracion nunca se computa en produccion, asi que
#                                `trusts_elicited` no se gana NUNCA — la misma cadena que
#                                dejo a A2 con piso ELICITED inalcanzable (leccion 7.14).
#
# Y este test existe ademas porque NADA ejercitaba `serve.answer()`. Un residuo de otra
# correccion —un kwarg que ya no existe— quedo ahi y ningun test lo agarro, en el mismo dia
# en que el mismo residuo aparecio en `report()`. Dos veces el mismo descuido, dos caminos
# sin cubrir.
def check_product_leaves_a_trace(ok: bool) -> bool:
    import inspect
    import tempfile
    from pathlib import Path as _Path

    from app import serve
    from app.assurance import PROFILES, Assurance
    from app.store import LearningStore

    print("\n--- 35. el producto deja rastro ---")

    # (a) Que el camino sea INVOCABLE. Es lo que el residuo rompia.
    sig = inspect.signature(serve.answer)
    ok &= check("`answer` acepta un store para dejar rastro",
                "store" in sig.parameters, ", ".join(sig.parameters))
    src = inspect.getsource(serve)
    ok &= check("y ya no llama a la funcion que no existe - el residuo de otra "
                "correccion, en el segundo lugar donde aparecio",
                "_trusts_elicited(" not in src)

    # (b) Que el rastro se escriba y se pueda LEER de vuelta.
    with tempfile.TemporaryDirectory() as tmp:
        store = LearningStore(_Path(tmp), "produccion")
        plan = {
            "assurance": {"level": Assurance.ACCOUNTABLE},
            "region": "many/oracle/loose", "action": "specialise",
            "paradigm": "react", "theta_version": 3,
            "beliefs": {"coupling_tight": {"value": True, "credence": 0.8,
                                           "provenance": "elicited"}},
        }

        class _Res:
            def __init__(self):
                self.plan = plan
                self.answer = "respuesta"
                self.citations = []
                self.usage = None

        class _Req:
            def identity(self):
                return "req-1"

        serve._record(store, _Req(), _Res(), Assurance.STANDARD)  # noqa: SLF001

        decisions = list(store.iter_decisions())
        ok &= check("la decision queda en el ledger y se relee",
                    len(decisions) == 1 and decisions[0]["request_id"] == "req-1")
        ok &= check("con el PLAN entero adentro - sin el, no hay EXPLAIN que consultar",
                    decisions[0]["plan"]["action"] == "specialise")

        # (c) El nivel EFECTIVO, no el pedido. Se pidio A1 y el plan resolvio A2.
        logged = list(store.iter_belief_log())
        ok &= check("en A2 la base de creencias se escribe - es lo unico que puede "
                    "alimentar la calibracion", len(logged) == 1)
        if logged:
            ok &= check("y el registro dice el nivel EFECTIVO, no el pedido - registrar "
                        "el pedido diria que se decidio bajo una garantia mas floja",
                        logged[0]["context"]["assurance"]
                        == Assurance.ACCOUNTABLE.label,
                        logged[0]["context"]["assurance"])

    # (d) Y en un nivel que NO declara el log, no se escribe.
    with tempfile.TemporaryDirectory() as tmp:
        store = LearningStore(_Path(tmp), "produccion")
        plan_low = dict(plan, assurance={"level": Assurance.STANDARD})

        class _ResLow(_Res):
            def __init__(self):
                super().__init__()
                self.plan = plan_low

        serve._record(store, _Req(), _ResLow(), Assurance.STANDARD)  # noqa: SLF001
        ok &= check("en A1 el log de creencias NO se escribe - el perfil lo declara y "
                    "honrarlo es la mitad que faltaba",
                    not PROFILES[Assurance.STANDARD].log_belief_base
                    and not store.belief_log_path.exists())
        ok &= check("pero la decision SI queda: auditar no depende del dial",
                    len(list(store.iter_decisions())) == 1)

    return ok


# --- 36. el deficit que el contrato ya nombra --------------------------------------------
#
# LA ASIMETRIA. `rec.diagnose` BUSCA: prueba intervenciones de a una y de a pares hasta dar
# con la mas barata que cambie la decision, porque el registro no dice que le falto. Un
# contrato rechazado YA LO DICE — `C-COMPLETE` nombra las claves ausentes y `C-NUM` nombra
# la ranura cuya proposicion no llego al piso.
#
# Y buscar donde ya hay respuesta no es solo redundante: es PEOR. La busqueda esta acotada a
# un esquema chico —una enumeracion abierta seria una busqueda de historias, y esto es una
# busqueda de evidencia— asi que un deficit real que no este en el esquema no se
# encontraria, y el resultado diria «no hay intervencion que lo cambie» cuando la hay y el
# contrato la nombro.
def check_contract_names_its_deficit(ok: bool) -> bool:
    from app.beliefs import Belief, BeliefBase, Provenance
    from app.contracts import SlotBinding, complete_answer, fill
    from app.rec import deficit_from_contract

    print("\n--- 36. el deficit que el contrato ya nombra ---")

    domain = ["Marta Arrieta", "Ignacio Arrieta", "Lucia Arrieta"]

    emitted = complete_answer(
        "Marta Arrieta AR1, Ignacio Arrieta AR2, Lucia Arrieta AR3", domain)
    ok &= check("un contrato que EMITE no produce deficit - no falta nada",
                deficit_from_contract(emitted, "C-COMPLETE") is None)

    short = complete_answer("Marta Arrieta AR1, Ignacio Arrieta AR2", domain)
    deficit = deficit_from_contract(short, "C-COMPLETE")
    ok &= check("uno que rechaza nombra EXACTAMENTE lo que falta, sin buscar",
                deficit is not None and deficit.missing == ("Lucia Arrieta",),
                str(deficit.missing) if deficit else "None")
    ok &= check("y declara que NO hubo busqueda - distinguirlo importa: un deficit "
                "buscado puede no existir, uno declarado por el contrato existe",
                deficit.as_dict()["searched"] is False)

    # LO QUE SOBRA: el nivel de conjunto lo ve, el de prosa NO PUEDE, y la diferencia es
    # estructural y no un defecto. `complete_answer` busca las claves DECLARADAS adentro
    # del texto; un nombre que el dominio no contiene nunca entra en `items`, asi que la
    # pertenencia no es observable desde ahi. `complete`, que recibe el conjunto ya
    # enumerado, si la ve.
    from app.contracts import complete

    base_dom = BeliefBase()
    base_dom.assert_(Belief("dominio", list(domain), 1.0, Provenance.COMPUTED))
    over = complete(list(domain) + ["Pedro Gomez"], "dominio", base_dom)
    d_over = deficit_from_contract(over, "C-COMPLETE")
    ok &= check("a nivel CONJUNTO, lo que sobra se nombra aparte de lo que falta",
                d_over is not None and any(m.startswith("sobra:") for m in d_over.missing),
                str(d_over.missing) if d_over else "None")

    prose = complete_answer(
        "Marta Arrieta, Ignacio Arrieta, Lucia Arrieta y tambien Pedro Gomez", domain)
    ok &= check("a nivel PROSA no puede verlo, y emite - es estructural: solo busca las "
                "claves declaradas, asi que un nombre ajeno no es observable",
                prose.emitted and not prose.extraneous)

    # Y funciona con el otro contrato, que nombra ranuras y no claves.
    base = BeliefBase()
    base.assert_(Belief("el total del ejercicio", 1200, 1.0, Provenance.COMPUTED))
    verdict = fill(
        "El total fue {total} y el margen {margen}.",
        [SlotBinding("total", "el total del ejercicio"),
         SlotBinding("margen", "el margen, que nadie midio")],
        base,
    )
    d_num = deficit_from_contract(verdict, "C-NUM")
    ok &= check("C-NUM nombra la RANURA que no llego al piso, no la clave",
                d_num is not None and d_num.missing == ("margen",),
                str(d_num.missing) if d_num else "None")

    # Un rechazo que no nombra nada NO es un deficit vacio: es un contrato que no puede
    # decir que le falto, y devolverlo vacio lo haria pasar por «no falta nada».
    class _Mudo:
        emitted = False
        missing: list = []
        extraneous: list = []
        refused = "sin detalle"

    ok &= check("un rechazo que no nombra nada NO se reporta como deficit vacio",
                deficit_from_contract(_Mudo(), "C-COMPLETE") is None)

    return ok


# --- 37. sobre QUE es una creencia, no solo como se obtuvo ------------------------------
#
# EL RETICULO ORDENABA UNA DIMENSION Y HACIAN FALTA DOS. `Provenance` dice **como** se
# obtuvo una creencia, y alcanzaba mientras todo lo que entraba a la base fuera sobre el
# request de adelante.
#
# Una asociacion APRENDIDA rompe eso: es aritmetica exacta sobre un ledger —por procedencia
# ES `COMPUTED`— y sin embargo no dice nada sobre este pedido. Dice que en pedidos
# parecidos, antes, tal transicion acompaño al exito.
#
#   entrarla como COMPUTED    dejaria que una regularidad estadistica gatee una accion
#                             irreversible, que es lo que el piso existe para impedir
#   bajarla a ELICITED        mentiria en el otro sentido: no es la opinion de un modelo,
#                             es una frecuencia medida y reproducible
#
# El problema no era que faltara un casillero en la escala: era que la escala mide una cosa
# y hacian falta dos.
def check_scope_is_a_second_axis(ok: bool) -> bool:
    from app.association import AssociationTable
    from app.beliefs import Belief, Provenance, Scope, admissible_for_action

    print("\n--- 37. el alcance como segundo eje ---")

    aqui = Belief("la unidad dice X", "X", 1.0, Provenance.COMPUTED)
    ok &= check("una creencia sobre ESTE request al piso puede sostener una accion",
                admissible_for_action(aqui, Provenance.OBSERVED))

    prior = Belief("frecuencia en casos parecidos", 0.9, 1.0, Provenance.COMPUTED,
                   scope=Scope.POPULATION)
    ok &= check("un prior sobre la POBLACION no puede, con la misma procedencia - «en "
                "casos parecidos esto funciono» no es «acá esto es cierto»",
                not admissible_for_action(prior, Provenance.OBSERVED))
    ok &= check("y no hizo falta degradarle la procedencia para lograrlo: sigue siendo "
                "COMPUTED, porque lo es", prior.provenance is Provenance.COMPUTED)

    ok &= check("el default es REQUEST - que es lo que era todo antes de que existieran "
                "las asociaciones aprendidas", aqui.scope is Scope.REQUEST)

    # Y la asociacion aprendida ya puede entrar a la base.
    table = AssociationTable()
    for _ in range(4):
        table.observe("c2", ["search", "read", "answer"], was_good=True)
    table.observe("c2", ["search", "search", "answer"], was_good=False)
    beliefs = table.as_beliefs("c2", "search")
    ok &= check("una asociacion aprendida se convierte en creencias", bool(beliefs))

    if beliefs:
        b = beliefs[0]
        # LA PROPOSICION ES LA MEDICION, NO LA RECOMENDACION. El invariante de `Belief`
        # —COMPUTED exige credencia 1,0— es lo que obligo a verlo: lo que el ledger
        # sostiene con certeza no es que convenga la transicion, es que su fuerza medida
        # vale lo que vale.
        ok &= check("afirma la MEDICION y no la recomendacion - por eso puede ser "
                    "COMPUTED con credencia 1,0 sin mentir",
                    b.credence == 1.0 and b.provenance is Provenance.COMPUTED
                    and "fuerza medida" in b.proposition, b.proposition)
        ok &= check("la fuerza va en el VALOR, que es donde una regla la puede leer",
                    isinstance(b.value, float) and 0.0 <= b.value <= 1.0, str(b.value))
        ok &= check("y ninguna de ellas puede gatear una accion irreversible",
                    not any(admissible_for_action(x, Provenance.OBSERVED)
                            for x in beliefs))
        ok &= check("la evidencia dice el conteo, no una adjetivacion",
                    "episodios" in b.evidence, b.evidence[:48])

    return ok


# --- 38. cuando corresponde verificar cobertura, y cuando NO -----------------------------
#
# EL DISPARADOR SON DOS CONDICIONES Y NINGUNA ALCANZA SOLA. La tarea tiene que EXIGIR
# cobertura (`exhaustive`) **y** su dominio tiene que ser ENUMERABLE (`from_question`).
#
# La primera sin la segunda es el caso que la leccion 8.7 midio y que no tiene salida: en
# una celda de dominio `semantic` —«listame todos los que tienen el rol R»— enumerar el
# dominio ES la extraccion, asi que el contrato no verificaria al paradigma, LO
# REEMPLAZARIA. Y en una de dominio `from_scope` el dominio barato son las unidades, que se
# midio que no predice correccion (+0,018): verificaria lo que no importa.
#
# La segunda sin la primera es una tarea que enumera algo y no pide exhaustividad — ahi
# exigir cobertura es pagar de mas por nada.
def check_coverage_trigger(ok: bool) -> bool:
    from app.contracts import verify_coverage

    print("\n--- 38. el disparador del contrato ---")

    def task(**kw):
        return {"domain_keys": ["Ana", "Beto"], **kw}

    fires = verify_coverage(
        task(coverage_demanded="exhaustive", completeness_domain="from_question"),
        "solo Ana")
    ok &= check("exige cobertura Y el dominio esta enunciado: DISPARA",
                fires is not None and fires["emitted"] is False
                and fires["missing"] == ["Beto"], str(fires and fires["missing"]))

    for dominio, por_que in (("semantic", "enumerarlo ES resolver la tarea"),
                             ("from_scope", "verificaria lo que no predice correccion")):
        out = verify_coverage(
            task(coverage_demanded="exhaustive", completeness_domain=dominio),
            "solo Ana")
        ok &= check(f"exige cobertura pero el dominio es `{dominio}`: NO dispara - "
                    f"{por_que}", out is None)

    ok &= check("no exige cobertura: NO dispara - forzarla es pagar de mas por nada",
                verify_coverage(
                    task(coverage_demanded="sufficient",
                         completeness_domain="from_question"), "solo Ana") is None)

    # U-7: QUE SE INFORMA Y QUE SE PROPONE cuando el contrato retiene la respuesta.
    from app.contracts import MAX_DIRECTED_RETRIES, complete_answer, retention

    dominio = ["Ana", "Beto", "Cora"]
    ok &= check("una respuesta que pasa no informa nada - no hay que retener",
                retention(complete_answer("Ana, Beto y Cora", dominio)) is None)

    r = retention(complete_answer("Ana y Beto", dominio))
    ok &= check("una retenida NOMBRA lo que falta - no «algo salio mal», sino que falto "
                "Cora, porque el contrato lo declara sin buscarlo",
                r is not None and r["missing"] == ["Cora"], str(r and r["missing"]))
    ok &= check("y PROPONE reintentar, que es dirigido porque sabe que pedir",
                r["proposed"] == "retry" and r["retries_left"] == MAX_DIRECTED_RETRIES)

    agotado = retention(complete_answer("Ana y Beto", dominio), retries_left=0)
    ok &= check("agotados los reintentos propone aceptar incompleto SABIENDO que lo "
                "esta - que es justo lo que sin contrato no se podia saber",
                agotado["proposed"] == "accept_incomplete")

    ok &= check("el tope de reintentos lo fija el CODIGO y es uno - un reintento que el "
                "sistema puede repetir solo deja de ser control de flujo del codigo, que "
                "es lo que P20 midio", MAX_DIRECTED_RETRIES == 1)

    ok &= check("sin dominio declarado no hay nada contra que verificar",
                verify_coverage({}, "cualquier cosa") is None)

    # Retrocompatible: una tarea anterior a los ejes no los declara, y ahi lo unico que
    # se puede saber de ella es que trae `domain_keys`. NO se supone la demanda.
    ok &= check("una tarea legacy sin los ejes cae a la presencia de `domain_keys` y no "
                "supone la demanda", verify_coverage(task(), "solo Ana") is not None)

    return ok


# --- 39. el handoff, y quien autoriza la transferencia -----------------------------------
#
# LOS TRES FRAMEWORKS CONSULTADOS HACEN LO MISMO: el handoff ES una herramienta que el
# modelo llama, `transfer_to_<agente>()`. O sea, flujo de control decidido por el modelo,
# que es exactamente lo que el invariante de este producto prohibe.
#
# Aca el agente PROPONE y una regla determinista AUTORIZA. Y hay una leccion de P20 adentro:
# rechazar una llamada no le quita la decision al modelo —la re-emite con otras palabras el
# 69% de las veces—, asi que el agente NO TIENE una herramienta de transferencia que se le
# pueda rechazar. La accion no existe.
def check_handoff_authorisation(ok: bool) -> bool:
    from app.beliefs import Belief, BeliefBase, Provenance
    from app.paradigms import CATALOG, COST_PRIORS, REGISTRY
    from app.paradigms.handoff import SCOPES, _authorises, _scopes, _sub_surface
    from app.retrieval import CorpusView, LexicalRetriever
    from app.tools import ToolFailure, ToolSurface

    print("\n--- 39. el handoff ---")

    ok &= check("esta en el catalogo y en el registry, con prior de costo",
                "handoff" in REGISTRY and "handoff" in CATALOG
                and "handoff" in COST_PRIORS)

    docs = {
        f"u-{i}": ("el puente Marta Arrieta vive aca" if i == 5 else f"relleno {i}")
        for i in range(8)
    }
    view = CorpusView(task_id="t", documents=docs, unit_ids=sorted(docs),
                      relevant_units=[])
    lex = LexicalRetriever()
    surface = ToolSurface(view=view, hybrid=lex, semantic=lex, lexical=lex,
                          variant="basic", budget_tokens=60_000)

    scopes = _scopes(sorted(docs), SCOPES)
    ok &= check("el reparto es con PASO, no en bloques contiguos - un bloque agrupa "
                "unidades vecinas y mediria localidad del indice, no alcance",
                scopes[0] == ["u-0", "u-2", "u-4", "u-6"], str(scopes[0]))

    # EL ALCANCE ES DE LA VISTA, NO DEL PROMPT. Un agente no puede leer afuera porque las
    # unidades NO ESTAN, no porque se le haya pedido que no lo haga.
    sub = _sub_surface(surface, scopes[0])
    ok &= check("el agente ve solo su alcance", sub.unit_ids() == scopes[0])
    try:
        sub.dispatch("read", {"unit_ids": scopes[1][0]})
        blocked = False
    except ToolFailure:
        blocked = True
    ok &= check("y NO PUEDE leer fuera de el - el alcance es de la vista, no una "
                "instruccion en el prompt", blocked)

    # LA REGLA. Dos condiciones, y ninguna alcanza sola.
    base = BeliefBase()
    ok &= check("sin que el agente lo pida, no hay transferencia - el codigo no la "
                "inventa", not _authorises(base, "Marta Arrieta", scopes[1], docs))

    base.assert_(Belief("handoff_requested", "Marta Arrieta", 0.8, Provenance.ELICITED))
    ok &= check("pedido Y presente literal en un alcance posterior: AUTORIZA",
                _authorises(base, "Marta Arrieta", scopes[1], docs))
    ok &= check("pedido pero NO presente: no autoriza - la propuesta del agente es su "
                "lectura, no un hecho",
                not _authorises(base, "Pedro Gomez", scopes[1], docs))
    ok &= check("una cadena demasiado corta no autoriza - misma guarda de especificidad "
                "que la sonda: tres caracteres aparecen en cualquier lado",
                not _authorises(base, "de", scopes[1], docs))

    # Y lo que lo separa de los frameworks: no hay tool de transferencia que ofrecer.
    import inspect

    from app.paradigms import handoff as mod

    src = inspect.getsource(mod)
    ok &= check("no existe una herramienta de transferencia que el modelo pueda llamar - "
                "quitar la decision es no ofrecer la accion, no rechazarla",
                "transfer_to" not in src)

    return ok


def check_tariffs_are_data(ok: bool) -> bool:
    """§53: los aranceles son DATOS y se leen de un JSON, no constantes en un .py.

    POR QUE. Un precio es una clausula del contrato con el proveedor: cambia sin avisar, no
    lo decide nadie de este lado, y actualizarlo no deberia tocar codigo. Mientras fueron
    constantes fueron **referencia inventada** —0,05/0,40 para nano cuando el real es
    0,20/1,25, un error de 4x en entrada— y nada podia notarlo, porque un numero puesto a
    mano se lee igual de seguro que uno verificado.

    Y EL CARGADOR FALLA FUERTE. Un arancel sin fecha no se puede auditar; uno sin precio
    haria parecer gratis a un modelo que no lo es; un papel sin declarar decidiria el
    precio del producto en silencio. Los tres levantan.
    """
    import json
    import tempfile
    from app.tariffs import (
        DECLARADOS, DEEP, DETAILS, EMBEDDINGS, NANO, VERIFIED_ON, _build, breakeven,
    )

    print("\n--- 53. los aranceles son datos ---")

    ok &= check("se leen del JSON y traen fecha de verificacion",
                bool(VERIFIED_ON) and len(VERIFIED_ON) == 10)
    ok &= check("la fecha viaja adentro del nombre, asi que el reporte la estampa",
                NANO.name.endswith(VERIFIED_ON))
    ok &= check("los cuatro modelos estan, con su deployment real",
                {d.deployment for d in DETAILS.values()} >= {
                    "gpt-5.4-nano", "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"})
    ok &= check("`luna` cuesta lo mismo que `nano`: NO es el caro, es clase nano",
                DECLARADOS["luna"].prompt_per_mtok
                == DECLARADOS["nano"].prompt_per_mtok)
    ok &= check("y los caros son caros: terra ~10x, sol ~24x",
                9.0 < breakeven(NANO, DECLARADOS["terra"], 0.15) < 11.0
                and 23.0 < breakeven(NANO, DECLARADOS["sol"], 0.15) < 26.0)
    ok &= check("el papel `deep` es una DECISION declarada en el JSON, no una derivacion",
                DEEP is DECLARADOS["terra"])
    ok &= check("los ejes que el calculo no usa se CONSERVAN en vez de perderse",
                DETAILS["sol"].cache_write == 6.25
                and DETAILS["terra"].long_context_prompt == 4.00)
    ok &= check("y nano no cobra escritura de cache, que es la asimetria menos obvia",
                DETAILS["nano"].cache_write is None
                and DETAILS["sol"].cache_write is not None)
    ok &= check("los embeddings tambien: HyDE los paga aparte de su llamada",
                EMBEDDINGS.get("text-embedding-3-large") == 0.143)

    for roto, porque in (
        ({"tariffs": {"x": {"prompt": 1, "completion": 2, "deployment": "d"}}},
         "sin fecha"),
        ({"verified_on": "2026-01-01",
          "tariffs": {"x": {"completion": 2, "deployment": "d"}}}, "sin precio"),
        ({"verified_on": "2026-01-01", "tariffs": {}}, "sin ningun arancel"),
    ):
        try:
            _build(roto)
            ok &= check(f"un JSON {porque} levanta", False)
        except ValueError:
            ok &= check(f"un JSON {porque} LEVANTA en vez de inventar el numero", True)
    return ok


def check_model_pool(ok: bool) -> bool:
    """§52: un cliente POR MODELO, una huella del conjunto, y el bloqueante de tools.

    POR QUE NO UN CLIENTE QUE CAMBIA DE DEPLOYMENT. La huella es la IDENTIDAD DE
    DECODIFICACION y va adentro de la clave de cache y de cada fila. Un solo cliente
    alternando deployment tendria UNA huella y DOS identidades atras: dos respuestas de
    modelos distintos compartirian clave de cache. Un cliente por modelo hace la
    correspondencia 1:1 por construccion.

    Y POR QUE EL POOL TIENE HUELLA PROPIA. `load_rows` se niega a leer un archivo que
    mezcla decodificaciones. Una corrida RUTEADA usa dos modelos a proposito, asi que sus
    filas tendrian dos huellas. La salida no es debilitar la guarda: la UNIDAD DE ANALISIS
    cambio — en una grilla fija se mide un paradigma con el modelo constante; en una
    ruteada se mide el ROUTER.

    DOS CORRECCIONES QUE ESTE TEST FIJA, porque me equivoque dos veces seguidas. Primero
    lei la documentacion —«no soportan Chat Completions y tools a la vez»— y declare que
    no se podian usar: el pool LEVANTABA. Despues probe con un prompt TRIVIAL, medi cero
    tokens de razonamiento, y declare que corrian «con el razonamiento apagado».

    Las dos veces concluí desde algo que no podia contradecirme. Con un prompt DIFICIL:
    `terra` razona al default (70 tokens), razona tambien con herramientas (66), y lo
    unico que rechaza es el NIVEL explicito junto con tools. `nano` no razona al default
    pero SI acepta el nivel con tools (`low` -> 35 tokens).
    """
    from dataclasses import replace as _replace
    from app.config import Settings, _optional_deployments
    from app import models as _models
    from app.pool import ModelPool

    print("\n--- 52. un cliente por modelo, y el bloqueante de tools ---")

    try:
        base = Settings.from_env()
    except Exception:
        ok &= check("sin entorno no se puede construir un pool — SIN N, y se dice", True)
        return ok

    s = _replace(base, temperature=0.0)
    solo = ModelPool(s, {"fast": "d-fast"})
    ok &= check("un pool de un modelo se construye y su huella es del CONJUNTO",
                solo.fingerprint().startswith("pool[fast]#"))
    ok &= check("la huella del pool no es la del miembro",
                solo.fingerprint() not in {
                    m["fingerprint"] for m in solo.describe()["members"].values()})

    dos = ModelPool(s, {"fast": "d-fast", "deep": "d-deep"})
    # LO QUE SE REGISTRA NO ES UNA CARENCIA SINO UNA PERDIDA DE CONTROL. Medido con un
    # prompt dificil: `terra` corre con herramientas Y RAZONANDO al default (66 tokens de
    # razonamiento). Lo que rechaza es que se le pase el NIVEL explicito junto con tools.
    # Asi que el esfuerzo —y por lo tanto parte del costo, porque esos tokens se facturan
    # como salida— lo decide el modelo y no la configuracion.
    ok &= check("un modelo que no deja fijar el esfuerzo con tools se REGISTRA, no se "
                "rechaza: correr, corre — y razonando",
                "deep" in dos.describe()["effort_not_controllable_with_tools"])
    ok &= check("y el que si acepta el nivel con herramientas no figura",
                "fast" not in dos.describe()["effort_not_controllable_with_tools"])
    ok &= check("las dos propiedades del modelo estan medidas, no leidas: nano no razona "
                "al default y terra si",
                _models.FAST.reasons_by_default is False
                and _models.DEEP.reasons_by_default is True)

    original = _models.CATALOG
    try:
        _models.CATALOG = (_models.FAST, _models.DEEP)
        ok &= check("el catalogo efectivo son los que TIENEN deployment",
                    [m.name for m in dos.models] == ["fast", "deep"])
        ok &= check("ordenado de menor capacidad a mayor: el empate cae del lado barato",
                    dos.models[0].capability < dos.models[1].capability)
        ok &= check("cada modelo tiene SU cliente, y son objetos distintos",
                    dos.client_for("fast") is not dos.client_for("deep"))
        ok &= check("y su propia huella: la correspondencia huella-modelo es 1:1",
                    len({m["fingerprint"]
                         for m in dos.describe()["members"].values()}) == 2)
        ok &= check("dos pools distintos dan huellas distintas — un archivo ruteado sigue "
                    "siendo incomparable con uno de un solo modelo",
                    dos.fingerprint() != solo.fingerprint())
        ok &= check("y no depende del orden de configuracion",
                    ModelPool(s, {"deep": "d-deep", "fast": "d-fast"}).fingerprint()
                    == dos.fingerprint())
        try:
            dos.client_for("gigante")
            ok &= check("un modelo sin deployment levanta", False)
        except ValueError as exc:
            ok &= check("un modelo sin deployment LEVANTA: un plan que dice `deep` y "
                        "corre en `fast` es un registro que miente", "miente" in str(exc))
    finally:
        _models.CATALOG = original

    try:
        ModelPool(s, {"turbo": "x"})
        ok &= check("un nombre fuera del catalogo levanta", False)
    except ValueError:
        ok &= check("un nombre fuera del catalogo levanta: sin capacidad ni arancel la "
                    "decision no lo puede podar ni gatear", True)
    try:
        ModelPool(s, {})
        ok &= check("un pool vacio levanta", False)
    except ValueError:
        ok &= check("un pool vacio levanta, no cae al modelo de la base", True)

    import os
    for malo in ("fast", "fast=,deep=x", "fast=a,fast=b"):
        os.environ["_MAPO_TEST_DEP"] = malo
        try:
            _optional_deployments("_MAPO_TEST_DEP")
            ok &= check(f"{malo!r} deberia levantar", False)
        except ValueError:
            pass
    os.environ.pop("_MAPO_TEST_DEP", None)
    ok &= check("una variable mal formada levanta en vez de perder un deployment en el "
                "parseo", True)
    ok &= check("y sin variable el sistema corre con UN modelo, que es el regimen medido",
                _optional_deployments("_MAPO_NO_EXISTE") == {})

    ok &= check("las ventanas son de ENTRADA, no la total: 272k nano, 922k los 5.6",
                _models.FAST.context_tokens == 272_000
                and _models.DEEP.context_tokens == 922_000)
    return ok


def check_tariffs_are_data(ok: bool) -> bool:
    """§53: los aranceles son DATOS y se leen de un JSON, no constantes en un .py.

    POR QUE. Un precio es una clausula del contrato con el proveedor: cambia sin avisar, no
    lo decide nadie de este lado, y actualizarlo no deberia tocar codigo. Mientras fueron
    constantes fueron **referencia inventada** —0,05/0,40 para nano cuando el real es
    0,20/1,25, un error de 4x en entrada— y nada podia notarlo, porque un numero puesto a
    mano se lee igual de seguro que uno verificado.

    Y EL CARGADOR FALLA FUERTE. Un arancel sin fecha no se puede auditar; uno sin precio
    haria parecer gratis a un modelo que no lo es; un papel sin declarar decidiria el
    precio del producto en silencio. Los tres levantan.
    """
    import json
    import tempfile
    from app.tariffs import (
        DECLARADOS, DEEP, DETAILS, EMBEDDINGS, NANO, VERIFIED_ON, _build, breakeven,
    )

    print("\n--- 53. los aranceles son datos ---")

    ok &= check("se leen del JSON y traen fecha de verificacion",
                bool(VERIFIED_ON) and len(VERIFIED_ON) == 10)
    ok &= check("la fecha viaja adentro del nombre, asi que el reporte la estampa",
                NANO.name.endswith(VERIFIED_ON))
    ok &= check("los cuatro modelos estan, con su deployment real",
                {d.deployment for d in DETAILS.values()} >= {
                    "gpt-5.4-nano", "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"})
    ok &= check("`luna` cuesta lo mismo que `nano`: NO es el caro, es clase nano",
                DECLARADOS["luna"].prompt_per_mtok
                == DECLARADOS["nano"].prompt_per_mtok)
    ok &= check("y los caros son caros: terra ~10x, sol ~24x",
                9.0 < breakeven(NANO, DECLARADOS["terra"], 0.15) < 11.0
                and 23.0 < breakeven(NANO, DECLARADOS["sol"], 0.15) < 26.0)
    ok &= check("el papel `deep` es una DECISION declarada en el JSON, no una derivacion",
                DEEP is DECLARADOS["terra"])
    ok &= check("los ejes que el calculo no usa se CONSERVAN en vez de perderse",
                DETAILS["sol"].cache_write == 6.25
                and DETAILS["terra"].long_context_prompt == 4.00)
    ok &= check("y nano no cobra escritura de cache, que es la asimetria menos obvia",
                DETAILS["nano"].cache_write is None
                and DETAILS["sol"].cache_write is not None)
    ok &= check("los embeddings tambien: HyDE los paga aparte de su llamada",
                EMBEDDINGS.get("text-embedding-3-large") == 0.143)

    for roto, porque in (
        ({"tariffs": {"x": {"prompt": 1, "completion": 2, "deployment": "d"}}},
         "sin fecha"),
        ({"verified_on": "2026-01-01",
          "tariffs": {"x": {"completion": 2, "deployment": "d"}}}, "sin precio"),
        ({"verified_on": "2026-01-01", "tariffs": {}}, "sin ningun arancel"),
    ):
        try:
            _build(roto)
            ok &= check(f"un JSON {porque} levanta", False)
        except ValueError:
            ok &= check(f"un JSON {porque} LEVANTA en vez de inventar el numero", True)
    return ok


def check_coverage_precondition_abstains(ok: bool) -> bool:
    """§51: cuando la precondicion de cobertura no se puede imponer, el dial decide.

    LA HISTORIA, porque el error importa mas que el arreglo. `U-2` pidio combinar demanda
    x material. Primer intento: una regla de `GATE`, que mataba a `C2` entera. Segundo:
    una precondicion estructural que poda por `TRAVERSES_SCOPE` — correcta, con test, y
    **doblemente inerte**: ningun corpus declaraba `coverage_demanded`, y la interseccion
    entre los brazos que recorren y la fila activa es VACIA. La cerre como hecha.

    LO QUE FALTABA ERA UNA DECISION DE PRODUCTO, no codigo. Ninguna topologia admisible
    recorre el alcance, asi que la garantia no se puede imponer. Que se hace con eso
    DEPENDE DEL DIAL:

      A0/A1   se sigue. Una respuesta desde una muestra es aceptable a ese nivel, y el
              registro dice que la precondicion no se pudo imponer
      A2/A3   se GATEA. No se sostiene una afirmacion sobre un dominio entero sin ninguna
              topologia capaz de recorrerlo, y a esos niveles lo que se afirma hay que
              poder defenderlo

    ABSTENERSE ES EL PRODUCTO, no un fallo: la curva riesgo-cobertura se reporta.
    """
    import json
    from app.assurance import Assurance
    from app.paradigms import COST_PRIORS, TRAVERSES_SCOPE
    from app.policy import PolicyBundle
    from app.router import Router

    print("\n--- 51. la precondicion de cobertura se abstiene por dial ---")

    raiz = Path("corpus/gold_guards")
    if not (raiz / "tasks.json").exists():
        # SIN CORPUS NO SE INVENTA UNO. Se declara y se sigue: un test que fabrica su
        # propio mundo para pasar no prueba que el mundo real lo dispare, que es
        # exactamente lo que `_audit_inerte.py` existe para atrapar.
        ok &= check("corpus `gold_guards` ausente — SIN N, y se dice", True)
        return ok

    tasks = json.loads((raiz / "tasks.json").read_text(encoding="utf-8"))
    docs = json.loads((raiz / "documents.json").read_text(encoding="utf-8"))
    C = ["react", "dag_strategy", "rewoo", "gist_reader"]
    router = Router(PolicyBundle.cold_start("react", 0.0).sign(), COST_PRIORS, "react")

    disparan = [
        t for t in tasks
        if t.get("coverage_demanded") == "exhaustive" and len(t["unit_ids"]) > 8
    ]
    ok &= check(f"el corpus DESPIERTA la precondicion ({len(disparan)} tareas): una "
                f"guarda que nunca disparo no es una guarda", len(disparan) >= 1)
    ok &= check("y ningun candidato de la fila activa recorre el alcance, que es lo que "
                "hace inimponible a la garantia",
                not (set(C) & set(TRAVERSES_SCOPE)))

    def gateadas(nivel):
        n = 0
        for t in disparan:
            try:
                n += router.plan(t, region="many/nooracle/loose", candidates=C,
                                 documents=docs, requested=nivel).gated
            except ValueError:
                pass
        return n

    ok &= check("A1 sigue: una respuesta desde una muestra es aceptable ahi",
                gateadas(Assurance.STANDARD) == 0)
    ok &= check(f"A2 GATEA las {len(disparan)}: lo que se afirma hay que poder defenderlo",
                gateadas(Assurance.ACCOUNTABLE) == len(disparan))
    ok &= check("A3 tambien", gateadas(Assurance.CERTIFIED) == len(disparan))

    plan = router.plan(disparan[0], region="many/nooracle/loose", candidates=C,
                       documents=docs, requested=Assurance.ACCOUNTABLE)
    ok &= check("y el motivo dice POR QUE, no solo que se gateo",
                any("recorre el alcance" in n for n in plan.notes))
    ok &= check("el EXPLAIN lo lleva: una abstencion que no se registra no se audita",
                plan.explain()["gated"] is True)
    return ok


def check_board_is_a_tool_for_everyone(ok: bool) -> bool:
    """§50: el blackboard es una HERRAMIENTA, ofrecida a todos los patrones por igual.

    CORRECCION DE LO QUE ESCRIBI ANTES (indicacion del autor). Habia dicho que
    `{board, sin} x {react, dag}` no se podia construir: que en `react` el board era
    redundante con la transcripcion y que en `map_reduce` seria otro patron. Las dos
    mitades estaban mal, y lo que las da vuelta es que el board sea una TOOL:

      react       NO es redundante, y el propio registro lo desmiente: bajo presupuesto el
                  texto leido sobrevive al 28% hasta la llamada que responde. Un apunte en
                  el board sobrevive la compactacion; la transcripcion no. Para un agente
                  solo, el board es DURABILIDAD
      map_reduce  con una tool no se vuelve secuencial: cada map puede postear y el reduce
                  leer, y ninguna llamada depende de otra salvo que el modelo elija leer

    NO ES FLUJO DE CONTROL. Escribir y leer estado compartido es una ACCION, como buscar.
    El invariante prohibe que el modelo decida que paradigma corre o si un gate pasa, no
    que tome notas.

    Y SON DOS FACTORES, no uno: `shared_state` gobierna el board ESTRUCTURAL de dag —el que
    escribe el codigo— y `offer_board` la tool. Fundirlos mediria dos cosas con un
    interruptor.
    """
    import json
    from app.retrieval import CorpusView, LexicalRetriever
    from app.tools import ToolFailure, ToolSurface, VARIANTS, available, specs_for

    print("\n--- 50. el board es una tool para todos ---")

    docs = {f"u{i}": f"unidad {i}" for i in range(5)}
    view = CorpusView(task_id="t", documents=docs, unit_ids=list(docs),
                      relevant_units=["u1"])

    def surface(**kw):
        return ToolSurface(view=view, hybrid=LexicalRetriever(),
                           semantic=LexicalRetriever(), lexical=LexicalRetriever(),
                           variant=kw.pop("variant", "basic"), budget_tokens=40_000, **kw)

    faltan = [
        v for v in VARIANTS
        if "post" not in {
            t["function"]["name"]
            for t in specs_for(v, False, frozenset(), offer_board=True)
        }
    ]
    ok &= check(f"se ofrece en TODAS las variantes, no en una ({VARIANTS})", not faltan)
    ok &= check("y apagado no esta en ninguna: el default es el regimen ya medido",
                all("post" not in {t["function"]["name"]
                                   for t in specs_for(v, False, frozenset())}
                    for v in VARIANTS))
    ok &= check("la disponibilidad sigue a la oferta, como `read_all`",
                available("post", "basic", offer_board=True)
                and not available("post", "basic"))

    s = surface(offer_board=True)
    ok &= check("postear devuelve cuantas entradas hay, no solo «ok»",
                json.loads(s.dispatch("post", {"finding": "AC-7741 es de Valerio"}))
                == {"posted": True, "entries": 1})
    ok &= check("un apunte vacio NO se guarda y se dice: un board con ruido hace que el "
                "conteo mienta sobre cuanto estado hay",
                json.loads(s.dispatch("post", {"finding": "   "}))["posted"] is False)
    leido = json.loads(s.dispatch("board", {}))
    ok &= check("leer devuelve lo posteado, y sigue siendo una sola entrada",
                leido["entries"] == 1 and "AC-7741" in leido["board"])
    ok &= check("los contadores entran al reporte: un factor que se enciende y no se "
                "puede medir es una capacidad declarada y no ejecutada",
                s.usage()["board_posts"] == 1 and s.usage()["board_reads"] == 1)

    try:
        surface().dispatch("post", {"finding": "x"})
        ok &= check("sin el factor la tool no existe", False)
    except ToolFailure:
        ok &= check("sin el factor la tool no existe: se rechaza, no se ignora", True)

    # UN SOLO BOARD POR CELDA: el que `dag` escribe desde el codigo es el mismo que la
    # tool. Dos serian dos estados compartidos a la vez.
    from app.board import Blackboard
    ok &= check("la superficie ES la duena del board, asi que dag y la tool comparten uno",
                isinstance(surface().board_state, Blackboard))

    from app.tools import ToolSurface as TS
    ok &= check("los dos factores estan separados y no se funden en un interruptor",
                "shared_state" in TS.__dataclass_fields__
                and "offer_board" in TS.__dataclass_fields__)
    return ok


def check_retrieval_is_a_factor(ok: bool) -> bool:
    """§49: la recuperacion es un FACTOR cruzado, y un brazo que llama al modelo se cobra.

    TRES PROPIEDADES, y las tres fallaban de formas distintas antes de hoy:

      construccion  un brazo que llama al modelo se arma POR CELDA, con el cliente de esa
                    celda. Compartido, la generacion de la primera tarea subsidia a todas
                    y su memo de consultas cruza tareas
      cobro         la fila cobra el MEDIDOR DE LA CELDA y no la contabilidad del
                    paradigma. `hybrid_hyde` genera una hipotetica por consulta y ese
                    gasto no aparece en `result.usage` por construccion — el paradigma
                    nunca lo vio— asi que se comparaba una recuperacion gratis contra una
                    paga y se llamaba «mejor» a la diferencia
      separacion    dos brazos no se promedian. El sufijo del archivo lo separa, y la
                    guarda de lectura lo atrapa si alguien concatena a mano — que es el
                    unico caso que queda, porque la huella y el vocabulario COINCIDEN
                    entre brazos
    """
    import json
    import tempfile
    from app.retrieval import MODEL_CALLING_ARMS, build_arm, build_arms
    from app.runner import load_rows

    print("\n--- 49. la recuperacion es un factor, y se cobra ---")

    ok &= check("HyDE es un BRAZO y no una herramienta: el modelo no puede invocarlo",
                "hybrid_hyde" not in {
                    t["function"]["name"]
                    for t in __import__("app.tools", fromlist=["TOOL_SPECS"]).TOOL_SPECS
                })
    ok &= check("y esta declarado como uno de los que llaman al modelo",
                "hybrid_hyde" in MODEL_CALLING_ARMS
                and "hybrid_reranked" in MODEL_CALLING_ARMS)

    puros = set(build_arms()) - MODEL_CALLING_ARMS
    ok &= check(f"los brazos puros no llaman al modelo y se comparten ({sorted(puros)})",
                "lexical" in puros and "oracle" in puros)

    try:
        build_arm("no-existe", None, None)
        ok &= check("un brazo desconocido levanta", False)
    except ValueError as exc:
        ok &= check("un brazo desconocido levanta, no cae al lexico callado",
                    "desconocido" in str(exc))

    base = {"task_id": "t", "paradigm": "p", "fingerprint": "A",
            "region_vocabulary": "V", "retriever": "hybrid"}

    def escribir(filas):
        f = Path(tempfile.mkdtemp()) / "r.jsonl"
        f.write_text(chr(10).join(json.dumps(x) for x in filas), encoding="utf-8")
        return f

    ok &= check("un archivo de un solo brazo se lee sin quejarse",
                len(load_rows(escribir([base, dict(base, task_id="u")]))) == 2)
    try:
        load_rows(escribir([base, dict(base, retriever="hybrid_hyde")]))
        ok &= check("mezclar brazos levanta", False)
    except ValueError as exc:
        ok &= check("mezclar brazos levanta — la huella y el vocabulario COINCIDEN, "
                    "asi que esta es la unica guarda que queda",
                    "brazos de recuperacion" in str(exc))

    from app.runner import Row
    ok &= check("la fila separa el gasto de recuperacion del gasto del paradigma",
                "retrieval_tokens" in Row.__dataclass_fields__)

    # F-2: el estado compartido es una DIMENSION, y su cruce tiene una celda vacia POR
    # CONSTRUCCION. Que este vacia no es un hueco del banco.
    from app.tools import ToolSurface
    ok &= check("el estado compartido es un factor de la superficie, no de una topologia",
                "shared_state" in ToolSurface.__dataclass_fields__)
    ok &= check("y `None` significa «como cada patron viene de fabrica», que se distingue "
                "de haberlo elegido",
                ToolSurface.__dataclass_fields__["shared_state"].default is None)
    return ok


def check_the_code_draws_the_graph(ok: bool) -> bool:
    """§48: D-3, la forma del DAG la deriva el CODIGO, no la propone el modelo.

    Hasta hoy el planificador proponia `sub_questions` con sus dependencias y
    `_assign_waves` solo topologizaba lo que el modelo dijo, con dos constantes fijas —4 y
    3— iguales para una tarea de 3 unidades y para una de 400. Es la version estructural de
    `D-1`: el invariante dice que el modelo es SENSOR y no maneja flujo de control, y un
    grafo de control es flujo de control.
    """
    # ALIASADO a proposito: `feasibility.check` tapa al `check` de este archivo, y el
    # sombreado no falla al importar — falla adentro del primer aserto, con un TypeError
    # que no menciona el nombre. Un import que redefine el verificador del test es la
    # clase de error que hace pasar un test que no probo nada.
    from app.feasibility import MAX_ORCHESTRATION_CALLS, check as feasibility_check
    from app.paradigms.dag import (
        DAG_MAX_REPLAN_ITERATIONS, DAG_MAX_SUB_QUESTIONS, dag_shape, projected_calls,
    )

    print("\n--- 48. el codigo dibuja el grafo (D-3) ---")

    def forma(n: int):
        return dag_shape({"unit_ids": [f"u{i}" for i in range(n)],
                          "budget_tokens": 40_000})

    ok &= check("una unidad da UNA rama: un DAG de un nodo, y se dice",
                forma(1).max_sub_questions == 1
                and "un nodo" in forma(1).reason)
    ok &= check("la forma escala con el material y no con una constante",
                [forma(n).max_sub_questions for n in (1, 2, 3, 4)] == [1, 2, 3, 4])
    ok &= check("y no crece mas alla del tope fijo por mucho material que haya",
                forma(400).max_sub_questions == DAG_MAX_SUB_QUESTIONS)

    # LA PROPIEDAD QUE IMPORTA: la forma derivada nunca excede la cota que la factibilidad
    # impone. Si se derivara con aritmetica propia, podria elegir un grafo que su propia
    # cota prohibe, y el registro tendria un paradigma admitido corriendo una forma
    # infactible.
    excesos = [
        n for n in (1, 2, 3, 4, 10, 40, 400)
        if projected_calls(forma(n).max_sub_questions, forma(n).max_replans)
        > MAX_ORCHESTRATION_CALLS
    ]
    ok &= check("ninguna forma derivada excede la cota de llamadas de factibilidad",
                not excesos)

    docs = {f"u{i}": "x" * 400 for i in range(40)}
    v = feasibility_check("dag_strategy", docs,
                          {"unit_ids": list(docs), "budget_tokens": 40_000})
    ok &= check("y usa la MISMA formula que factibilidad proyecta, no una paralela",
                projected_calls(DAG_MAX_SUB_QUESTIONS, DAG_MAX_REPLAN_ITERATIONS)
                == v.projected_calls)

    ok &= check("el hueco se REGISTRA: el acoplamiento no llega al paradigma",
                forma(40).governed_by_coupling is False)
    ok &= check("y la forma lleva su motivo, no un numero pelado",
                "ramas" in forma(40).reason or "rama" in forma(40).reason)
    return ok


def check_who_sets_the_dial(ok: bool) -> bool:
    """§47: T-5, quien fija el dial. Tres fuentes y una regla: el MAXIMO gana.

    `max` no es conveniencia: es la unica composicion que hace que cada fuente solo pueda
    ENDURECER. Con `min` o un promedio, agregar una fuente podria ablandar el resultado, y
    entonces una fuente nueva seria un riesgo en vez de una garantia. Enunciado completo en
    `EL_DIAL.es.md`.
    """
    from app.assurance import Assurance, PROFILES, required_floor, resolve
    from app.beliefs import Belief, BeliefBase, Provenance

    print("\n--- 47. quien fija el dial (T-5) ---")

    def con(**props) -> BeliefBase:
        b = BeliefBase()
        for k, v in props.items():
            b.assert_(Belief(k, v, 1.0, Provenance.COMPUTED, "declarado por el caller"))
        return b

    vacia = con()
    ok &= check("sin nada que imponga, gana lo PEDIDO",
                resolve(vacia, requested=Assurance.EXPLORATORY).level
                is Assurance.EXPLORATORY)
    ok &= check("el llamador puede SUBIR: conoce cosas que no estan en el material",
                resolve(vacia, requested=Assurance.CERTIFIED).level
                is Assurance.CERTIFIED)

    irr = con(irreversible=True)
    ok &= check("una accion irreversible impone A3 aunque se pida el minimo",
                resolve(irr, requested=Assurance.EXPLORATORY).level
                is Assurance.CERTIFIED)
    ok &= check("`shared_writes` impone A2, que es otro piso y no el mismo",
                resolve(con(shared_writes=True),
                        requested=Assurance.EXPLORATORY).level
                is Assurance.ACCOUNTABLE)

    aprendido = {"R": Assurance.ACCOUNTABLE}
    ok &= check("el piso APRENDIDO tambien sube, y solo sube",
                resolve(vacia, requested=Assurance.EXPLORATORY,
                        learned=aprendido, region="R").level
                is Assurance.ACCOUNTABLE)
    ok &= check("y no baja lo que el request ya impuso: el maximo gana",
                resolve(irr, requested=Assurance.EXPLORATORY,
                        learned={"R": Assurance.STANDARD}, region="R").level
                is Assurance.CERTIFIED)
    ok &= check("un piso aprendido de otra region no toca esta",
                resolve(vacia, requested=Assurance.EXPLORATORY,
                        learned=aprendido, region="OTRA").level
                is Assurance.EXPLORATORY)

    # LA PROPIEDAD, y es la que hace seguro agregar una fuente: el nivel efectivo es
    # monotono en cada fuente por separado. Se verifica sobre el producto entero.
    from itertools import product
    fallas = []
    for pedido, piso_ap in product(Assurance, Assurance):
        alto = resolve(vacia, requested=pedido, learned={"R": piso_ap}, region="R").level
        for menor in Assurance:
            if menor > pedido:
                continue
            bajo = resolve(vacia, requested=menor, learned={"R": piso_ap},
                           region="R").level
            if bajo > alto:
                fallas.append((pedido.label, menor.label, piso_ap.label))
    ok &= check("MONOTONO en cada fuente: bajar lo pedido nunca sube el nivel efectivo "
                f"({len(list(product(Assurance, Assurance)))} combinaciones)", not fallas)

    # LA CUARTA FUENTE, que no es un nivel: A2 sin calibracion endurece la PROCEDENCIA
    # dentro del nivel en vez de bajar el nivel.
    sin_cal = resolve(vacia, requested=Assurance.ACCOUNTABLE,
                      calibration_trustworthy=False)
    con_cal = resolve(vacia, requested=Assurance.ACCOUNTABLE,
                      calibration_trustworthy=True)
    ok &= check("A2 sin calibracion exige OBSERVED, y NO baja de nivel",
                sin_cal.level is Assurance.ACCOUNTABLE
                and sin_cal.profile.derived_floor is Provenance.OBSERVED)
    ok &= check("con calibracion ganada, A2 admite ELICITED como su perfil declara",
                con_cal.profile.derived_floor is Provenance.ELICITED)

    # EL HALLAZGO DE MARGINALIZAR: tres de las cuatro posiciones no restringen patrones.
    inertes = [
        lvl.label for lvl in Assurance
        if PROFILES[lvl].admissible_patterns is None
    ]
    ok &= check(f"el dial no restringe PATRONES hasta A3 — {inertes} no filtran ninguno, "
                f"y por eso marginalizar dice cual escalon se paga",
                inertes == ["A0_EXPLORATORY", "A1_STANDARD", "A2_ACCOUNTABLE"])
    ok &= check("pero no es inerte en los otros ejes: A2 exige theta firmado y A1 no",
                PROFILES[Assurance.ACCOUNTABLE].require_signed_theta
                and not PROFILES[Assurance.STANDARD].require_signed_theta)

    floor, razones = required_floor(irr)
    ok &= check("el piso viene con su motivo escrito, no como un numero pelado",
                floor is Assurance.CERTIFIED and any("irreversible" in r for r in razones))
    return ok


def check_assembler_soundness(ok: bool) -> bool:
    """§46: T-3, el teorema de soundness del ensamblador. Exhaustivo, no por casos.

    Si `fill` emite, entonces para TODA ranura existe una creencia vigente sobre la
    proposicion asignada, con procedencia >= piso, y la subcadena emitida es exactamente
    `str(valor)`. Enunciado y limites en `SOUNDNESS.es.md`.

    SE RECORRE EL ESPACIO ENTERO Y NO CASOS ELEGIDOS. Cuatro procedencias por cuatro pisos
    son dieciseis puntos: enumerarlos es exacto y cuesta lo mismo que elegir tres. Elegir
    casos es donde se esconde el que falta.
    """
    from itertools import product
    from app.beliefs import Belief, BeliefBase, Provenance
    from app.contracts import fill, SlotBinding, slots_of

    print("\n--- 46. soundness del ensamblador (T-3) ---")

    PLANTILLA = "El saldo de {cuenta} es {monto} al {fecha}."
    ranuras = slots_of(PLANTILLA)
    ok &= check("las ranuras salen de la PLANTILLA, no de una lista paralela",
                ranuras == ["cuenta", "monto", "fecha"])

    VALORES = {"cuenta": "AC-77", "monto": 1234.5, "fecha": "2026-08-28"}
    BINDINGS = [SlotBinding(slot=s, proposition=f"p_{s}") for s in ranuras]

    def base_con(procedencias: dict[str, Provenance]) -> BeliefBase:
        b = BeliefBase()
        for s, prov in procedencias.items():
            b.assert_(Belief(f"p_{s}", VALORES[s], 1.0, prov, "de prueba"))
        return b

    # EXHAUSTIVO sobre (procedencia de la ranura critica) x (piso pedido).
    fallas = []
    for prov, piso in product(Provenance, Provenance):
        procs = {s: Provenance.COMPUTED for s in ranuras}
        procs["monto"] = prov
        v = fill(PLANTILLA, BINDINGS, base_con(procs), floor=piso)
        deberia = prov.rank >= piso.rank and all(
            p.rank >= piso.rank for p in procs.values()
        )
        if bool(v.rendered) != deberia:
            fallas.append((prov.value, piso.value, bool(v.rendered), deberia))
        if v.rendered:
            # Condicion 3: la subcadena es exactamente `str(valor)`, sin formatear.
            for s in ranuras:
                if str(VALORES[s]) not in v.rendered:
                    fallas.append((s, "subcadena ausente", v.rendered, ""))
            if "{" in v.rendered or "}" in v.rendered:
                fallas.append(("", "ranura sin sustituir", v.rendered, ""))
    ok &= check(f"emite exactamente cuando toda ranura llega al piso "
                f"({len(list(product(Provenance, Provenance)))} combinaciones)",
                not fallas)

    # Falla cerrada y ENTERA: una sola ranura floja retiene la salida completa.
    flojo = {s: Provenance.COMPUTED for s in ranuras}
    flojo["fecha"] = Provenance.ASSUMED
    v = fill(PLANTILLA, BINDINGS, base_con(flojo), floor=Provenance.COMPUTED)
    ok &= check("una ranura floja retiene la salida ENTERA, no emite una parcial",
                v.rendered is None and len(v.refused) == 1)
    ok &= check("y el motivo nombra la ranura y su proposicion, no solo «fallo»",
                v.refused[0][0] == "fecha" and v.refused[0][1] == "p_fecha")

    # Sin creencia no es lo mismo que creencia floja, y el motivo lo distingue.
    b = base_con({s: Provenance.COMPUTED for s in ranuras if s != "monto"})
    v = fill(PLANTILLA, BINDINGS, b, floor=Provenance.COMPUTED)
    ok &= check("«no hay creencia» se distingue de «procedencia baja» en el motivo",
                v.rendered is None and "no hay creencia" in v.refused[0][2])

    # Una ranura sin asignar es un error de la PLANTILLA, y tampoco emite.
    v = fill(PLANTILLA, BINDINGS[:2], base_con(
        {s: Provenance.COMPUTED for s in ranuras}), floor=Provenance.COMPUTED)
    ok &= check("una ranura sin asignacion no emite y lo dice",
                v.rendered is None and "sin asignar" in v.refused[0][2])

    # VIGENTE, no historica: una creencia posterior supersede.
    b = base_con({s: Provenance.COMPUTED for s in ranuras})
    b.assert_(Belief("p_monto", 999.0, 1.0, Provenance.COMPUTED, "corregido"))
    v = fill(PLANTILLA, BINDINGS, b, floor=Provenance.COMPUTED)
    ok &= check("el teorema habla de la creencia VIGENTE: la nueva es la que se emite",
                v.rendered is not None and "999.0" in v.rendered
                and "1234.5" not in v.rendered)

    # EL LIMITE, dicho en el teorema: la prosa que envuelve no esta cubierta.
    NEGADA = "El saldo de {cuenta} NO supera {monto}."
    v = fill(NEGADA, BINDINGS[:2], base_con(
        {s: Provenance.COMPUTED for s in ranuras}), floor=Provenance.COMPUTED)
    ok &= check("una plantilla que NIEGA emite sound y falso: el alcance es la ranura, "
                "no la oracion — y por eso el limite esta EN el teorema",
                v.rendered is not None and "NO supera" in v.rendered)
    return ok


def check_absence_and_presupposition(ok: bool) -> bool:
    """§45: las dos obligaciones que faltaban, y la asimetria que las separa.

    C-ABSENCE. Una ausencia afirmada desde una muestra produce una respuesta que PARECE
    NORMAL, y ese es el peor modo de falla de la familia: un error de presencia se cae solo
    —el lector busca el dato y no esta— y uno de ausencia no deja rastro. La regla es la
    asimetria: presencia con UN testigo, ausencia con el DOMINIO ENTERO.

    C-PRESUPPOSITION. «Cuando renuncio X?» da por sentado que renuncio. Si no renuncio,
    toda respuesta a la pregunta como esta formulada es falsa, INCLUIDA «no consta»:
    declinar el dato ratifica la premisa igual que darlo.

    Y NINGUNA DE LAS DOS PARSEA PROSA. La polaridad es un enum de dos valores, y la
    regex se CONSTRUYE desde el vocabulario, asi que no hay dos listas que se desincronicen.
    La premisa es una cadena que el agente enuncia y que el codigo NO interpreta: la busca
    literal en el material, que es la direccion barata.
    """
    from app.beliefs import BeliefBase, Provenance
    from app.contracts import (
        OBLIGATIONS, POLARITY, absence, declared_polarity, presupposition,
        verify_obligations,
    )

    print("\n--- 45. ausencia y presuposicion ---")

    ok &= check("presencia: UN testigo alcanza, no se exige cobertura",
                absence("present", 3, 40).emitted)
    ok &= check("ausencia con muestra: NO se emite, y dice por que",
                not absence("absent", 3, 40).emitted
                and "sin leer" in (absence("absent", 3, 40).refused or ""))
    ok &= check("ausencia con el dominio entero: se emite",
                absence("absent", 40, 40).emitted)
    ok &= check("dominio vacio: no se afirma nada, ni presencia ni ausencia",
                not absence("present", 0, 0).emitted)
    try:
        absence("maybe", 1, 1)
        ok &= check("una polaridad fuera del enum levanta", False)
    except ValueError:
        ok &= check("una polaridad fuera del enum levanta, no se adivina", True)

    ok &= check("la regex de polaridad se construye DESDE el vocabulario",
                all(declared_polarity(f"POLARITY: {p}\nANSWER: x") == p for p in POLARITY))
    ok &= check("no declarada es None, JAMAS `present` — el benigno no es el default",
                declared_polarity("ANSWER: x") is None
                and declared_polarity("POLARITY: maybe\nANSWER: x") is None)
    ok &= check("la ultima gana, igual que ANSWER: un brazo que revisa emite dos veces",
                declared_polarity("POLARITY: present\nPOLARITY: absent\nA") == "absent")

    docs = {"u1": "Valerio renuncio el 3 de marzo.", "u2": "otra cosa"}
    base = BeliefBase()
    v = presupposition("Valerio renuncio", docs, ["u1", "u2"], base)
    props = {b.proposition: b.provenance for b in base.all()}
    ok &= check("premisa sostenida: se emite y nombra el testigo",
                v.emitted and v.witness == "u1")
    ok &= check("el agente PROPONE elicited y el codigo AUTORIZA computed — no hereda",
                props.get("presupposition_claimed") is Provenance.ELICITED
                and props.get("presupposition_supported") is Provenance.COMPUTED)

    base2 = BeliefBase()
    v2 = presupposition("Valerio fue despedido", docs, ["u1", "u2"], base2)
    ok &= check("premisa falsa: NO se emite, y el motivo dice que un «no se» la ratifica",
                not v2.emitted and "ratifica" in (v2.refused or ""))
    ok &= check("y la propuesta queda asentada sin autorizacion: el registro no la pierde",
                [b.proposition for b in base2.all()] == ["presupposition_claimed"])

    corto = presupposition("ab", docs, ["u1"], BeliefBase())
    ok &= check("una premisa de tres caracteres no ratifica nada: guarda de especificidad",
                not corto.emitted and not [b for b in BeliefBase().all()])

    task = {"task_id": "t", "unit_ids": ["u1", "u2"], "obligations": sorted(OBLIGATIONS)}
    ok &= check("sin obligaciones declaradas no hay contrato, y None no es «paso»",
                verify_obligations({"task_id": "t"}, "x", docs, 0, BeliefBase()) is None)
    try:
        verify_obligations(task, "   ", docs, 2, BeliefBase())
        ok &= check("texto crudo vacio levanta", False)
    except ValueError as exc:
        ok &= check("sin texto crudo LEVANTA: un fallo de plomeria no se reporta como "
                    "incumplimiento del modelo", "plomeria" in str(exc))

    r = verify_obligations(
        task, "POLARITY: absent\nPRESUPPOSES: Valerio renuncio\nANSWER: ninguno",
        docs, 2, BeliefBase(),
    )
    ok &= check("las dos corren en la misma respuesta y no se pisan",
                r["absence"]["emitted"] and r["presupposition"]["emitted"])
    return ok


def check_model_is_an_action(ok: bool) -> bool:
    """§44: el modelo es ACCION, y el espacio de decision es el par (modelo, paradigma).

    LA TRAMPA QUE SE EVITA. Meter el modelo en el VOCABULARIO DE REGION seria el error
    opuesto y esta medido lo que cuesta: un cuarto segmento le costo a theta toda su
    confianza —cada episodio cayo en un bin demasiado chico para cruzar el piso de
    evidencia— y ese fue el mecanismo de `P15`. La region es lo que la tarea ES; la accion
    es lo que el motor HACE. El modelo se elige.

    EL ORDEN DE LAS COTAS ES EL RESULTADO. Dial primero —una precondicion— y plata
    despues. Al reves, un descuento suficiente compraria permiso para rutear al modelo mas
    barato lo que el dial prohibe, que es exactamente lo que el dial existe para impedir.
    """
    from app.assurance import Assurance, PROFILES
    from app.feasibility import admissible_pairs, check_pair
    from app.models import CATALOG, DEEP, FAST, Capability, by_name
    from app.paradigms import COST_PRIORS
    from app.policy import PolicyBundle
    from app.router import Router

    print("\n--- 44. el modelo es una accion, no un estado ---")

    docs = {f"u{i}": "x" * 4000 for i in range(30)}
    base = {"unit_ids": list(docs), "budget_tokens": 120_000, "question": "q",
            "task_id": "t1", "has_oracle": True}
    C = ["react", "map_reduce", "dag_strategy"]
    router = Router(PolicyBundle.cold_start("react", 0.0).sign(), COST_PRIORS, "react")

    def plan(task, **kw):
        return router.plan(task, region="many/oracle/loose", candidates=C,
                           documents=docs, **kw)

    ok &= check("sin catalogo el plan no inventa un modelo: dice vacio",
                plan(base).model == "")
    ok &= check("con catalogo elige, y entre admisibles gana el barato",
                plan(base, models=CATALOG).model == "fast")
    ok &= check("A3 exige capacidad y deja solo el caro — irreversible ya eleva a A3",
                plan(base, models=CATALOG, requested=Assurance.CERTIFIED).model == "deep")

    barato = dict(base, budget_usd=0.02)
    ok &= check("un presupuesto en plata mata pares que en tokens entraban",
                plan(barato, models=CATALOG).model == "fast")
    try:
        plan(barato, models=CATALOG, requested=Assurance.CERTIFIED)
        ok &= check("el dial no se compra con un descuento", False)
    except ValueError as exc:
        ok &= check("dial primero y plata despues: se ABSTIENE, no baja de modelo",
                    "capacidad" in str(exc))

    _, vp = admissible_pairs(CATALOG, ["direct"], docs, barato)
    ok &= check("el mismo paradigma vive en un modelo y muere en el otro",
                vp[("fast", "direct")].feasible and not vp[("deep", "direct")].feasible)
    ok &= check("y el motivo dice en que eje murio",
                vp[("deep", "direct")].axis == "money")

    # AUSENTE NO ES CERO, en la proyeccion. `dag_strategy` no proyecta tokens, y cobrarle
    # 0 lo declaraba admisible en el modelo caro justo al brazo que mide 59x `direct`.
    dag = check_pair(DEEP, "dag_strategy", docs, barato)
    ok &= check("un paradigma sin proyeccion no se cobra gratis: se declara no evaluado",
                dag.axis == "money_unevaluated" and dag.projected_tokens is None)

    ok &= check("la capacidad es ORDINAL, no un puntaje que se compense con costo",
                FAST.capability < DEEP.capability
                and not PROFILES[Assurance.CERTIFIED].permits_model(Capability.FAST))
    try:
        by_name("no-existe")
        ok &= check("un modelo fuera del catalogo levanta", False)
    except ValueError:
        ok &= check("un modelo fuera del catalogo levanta, no cae al barato callado", True)

    ok &= check("el EXPLAIN lleva el modelo: una accion que no se registra no se replica",
                plan(base, models=CATALOG).explain()["model"] == "fast")
    return ok


def check_measurement_and_state_are_two_trees(ok: bool) -> bool:
    """§43: `results/` es medicion y `state/` es el ledger, y son dos arboles.

    HASTA HOY ERAN UNO. El ledger de creencias vivia en `results/<modelo>/beliefs/`, junto
    a las filas de ejecucion, y un `rglob("*.jsonl")` sobre resultados lo levantaba como
    si fueran mediciones. Ya paso: un analizador de costos se comio 207 lineas del ledger.
    Revento al buscarles `task_id`, y **reventar fue suerte** — con las mismas claves las
    habria promediado callado.

    La distincion es de VIDA UTIL, no de prolijidad: una medicion sin su ledger sigue
    siendo una medicion; el ledger se puede reconstruir entero volviendo a consolidar.

    Y LA GUARDA VA EN EL SEAM. El layout se rompe con un `mv`, asi que `load_rows` verifica
    la forma antes que nada — antes que las guardas de mezcla, que inspeccionan claves y
    sobre un archivo de otra forma no encuentran ninguna y pasan.
    """
    import json
    import tempfile
    from app.runner import load_rows
    from app.store import LearningStore, state_dir_for

    print("\n--- 43. medicion y estado son dos arboles ---")

    ok &= check("la convencion saca el ledger del arbol de resultados",
                state_dir_for(Path("lab/results")) == Path("lab/state")
                and state_dir_for(Path("lab/results/nano")) == Path("lab/state/nano"))
    ok &= check("sin componente `results` no levanta: da una ruta distinta y determinista",
                state_dir_for(Path("/tmp/x")) == Path("/tmp/x_state"))
    ok &= check("con `results` dos veces sustituye el de ABAJO",
                state_dir_for(Path("a/results/b/results/c")) == Path("a/results/b/state/c"))

    raiz = Path(tempfile.mkdtemp())
    store = LearningStore(state_dir_for(raiz / "results"), "c")
    ok &= check("el store recibe su directorio y no lo adivina desde el nombre",
                (raiz / "results") not in store.belief_log_path.parents)

    ledger = raiz / "ledger.jsonl"
    ledger.write_text(json.dumps({"seq": 0, "prev": None, "beliefs": []}), encoding="utf-8")
    try:
        load_rows(ledger)
        ok &= check("leer un ledger como filas levanta", False)
    except ValueError as exc:
        ok &= check("leer un ledger como filas levanta, y nombra los dos arboles",
                    "task_id" in str(exc) and "state/" in str(exc))
    return ok


def check_money_is_a_unit_not_a_number(ok: bool) -> bool:
    """§41: convertir la escala de costo a plata, y que la referencia no decida.

    EL ARANCEL ES REFERENCIA, NO MEDICION. Es un precio puesto a mano, asi que ninguna
    conclusion puede depender de su valor. Lo que se testea no son numeros en dolares:
    son las tres propiedades que hacen que la conversion sea confiable igual.

      identidad     con entrada y salida al MISMO precio, la plata reproduce los tokens.
                    Si no, la conversion metio algo suyo
      ausente       una fila sin split registrado no se convierte a cero: se NIEGA. El
                    default 0 significa «no registrado», y regalarle costo la haria ganar
      sin piso      el multiplo del mas barato es 1,0 en cualquier unidad. `max(1.0, x)`
                    era un piso disfrazado de guard, y en plata aplastaba todo a 0,0
    """
    from app.metrics import Observation, Study, Tariff

    print("\n--- 41. la plata es una unidad, no un numero ---")

    obs = [
        Observation("t1", "R", "barato", 1.0, 1000, prompt_tokens=900, completion_tokens=100),
        Observation("t1", "R", "entrada", 1.0, 3000, prompt_tokens=2900, completion_tokens=100),
        Observation("t1", "R", "salida", 1.0, 3000, prompt_tokens=1500, completion_tokens=1500),
    ]

    plano = Tariff(name="ref/x1", prompt_per_mtok=1.0, completion_per_mtok=1.0)
    en_tokens = Study(obs).cost_spread()
    en_plano = Study(obs, tariff=plano).cost_spread()
    ok &= check(
        "a igual precio de entrada y salida, la plata reproduce los tokens exacto",
        all(en_tokens[k]["cost_multiple"] == en_plano[k]["cost_multiple"] for k in en_tokens),
    )

    caro = Tariff(name="ref/x8", prompt_per_mtok=1.0, completion_per_mtok=8.0)
    en_caro = Study(obs, tariff=caro).cost_spread()
    ok &= check(
        "en tokens los dos brazos de 3000 son indistinguibles",
        en_tokens["entrada"]["cost_multiple"] == en_tokens["salida"]["cost_multiple"],
    )
    ok &= check(
        "con la salida cara se separan, y el que emite salida es el mas caro",
        en_caro["salida"]["cost_multiple"] > en_caro["entrada"]["cost_multiple"],
    )

    ok &= check(
        "el mas barato vale 1,0 en las tres unidades — sin piso que lo aplaste",
        all(t["barato"]["cost_multiple"] == 1.0 for t in (en_tokens, en_plano, en_caro)),
    )

    sin_split = [Observation("t2", "R", "vieja", 1.0, 500)]
    try:
        Study(sin_split, tariff=caro).cost_ratio("t2", "vieja")
        ok &= check("una fila sin split se niega a convertirse", False)
    except ValueError as exc:
        ok &= check("una fila sin split se NIEGA — ausente no es cero",
                    "no es cero" in str(exc).lower() or "Ausente" in str(exc))

    ok &= check("el reporte estampa la unidad, con la fecha de la referencia adentro",
                Study(obs, tariff=caro).summary()["cost_unit"] == "usd@ref/x8"
                and Study(obs).summary()["cost_unit"] == "tokens")

    # ESTE ASERTO CAMBIO CUANDO LLEGARON LOS PRECIOS REALES, y el cambio es la leccion.
    # Antes exigia UN SOLO valor: con los aranceles inventados NANO y DEEP eran
    # exactamente proporcionales —25x en entrada y en salida— asi que la mezcla no movia
    # nada. Eso era una propiedad de mis numeros, no del mundo, y el test la habia
    # convertido en invariante. Con los reales (nano 0,20/1,25 = 6,25x; terra 2/12 = 6,0x)
    # la mezcla si mueve, un 4%.
    #
    # Lo que se afirma ahora es lo que DECIDE: que la mezcla no cambia el orden de
    # magnitud, asi que «el caro necesita usar como una decima parte de los tokens» vale
    # sin saber la mezcla. Un aserto de igualdad exacta sobre precios de terceros es un
    # test que se rompe cada vez que alguien actualiza una tarifa.
    from app.tariffs import DEEP, NANO, breakeven
    ratios = [breakeven(NANO, DEEP, r) for r in (0.0, 0.25, 0.5, 1.0)]
    dispersion = (max(ratios) - min(ratios)) / min(ratios)
    ok &= check(
        f"la mezcla mueve el punto de equilibrio menos del 10% "
        f"({min(ratios):.2f}x a {max(ratios):.2f}x, dispersion {dispersion:.1%}), asi que "
        f"el orden de magnitud del intercambio no depende de suponerla",
        dispersion < 0.10,
    )
    ok &= check(
        "y el caro es caro de verdad: el equilibrio esta muy por encima de 1",
        min(ratios) > 5.0,
    )
    return ok


def check_load_rows_guards_the_analyst(ok: bool) -> bool:
    """§42: las guardas de mezcla protegen a QUIEN ANALIZA, no solo a quien corre.

    Vivian adentro de `Runner`, y todo analizador lee el `.jsonl` con `json.loads`. Una
    guarda por un camino que nadie toma es la forma que busca el barrido de la 7.17 —
    cometida en la correccion misma, porque la del vocabulario se escribio el mismo dia.
    """
    import json
    import tempfile
    from app.runner import load_rows

    print("\n--- 42. load_rows es del modulo, y guarda al analista ---")

    def escribir(filas):
        f = Path(tempfile.mkdtemp()) / "r.jsonl"
        f.write_text("\n".join(json.dumps(x) for x in filas), encoding="utf-8")
        return f

    base = {"task_id": "t", "paradigm": "p", "fingerprint": "A",
            "region_vocabulary": "V1"}
    ok &= check("un archivo coherente se lee sin quejarse",
                len(load_rows(escribir([base, dict(base, task_id="u")]))) == 2)

    for campo, valor, que in (("fingerprint", "B", "decodificaciones"),
                              ("region_vocabulary", "V2", "vocabularios")):
        try:
            load_rows(escribir([base, dict(base, **{campo: valor})]))
            ok &= check(f"mezclar {que} levanta", False)
        except ValueError as exc:
            ok &= check(f"mezclar {que} levanta, desde el analisis y no solo al correr",
                        que[:6] in str(exc).lower())

    ok &= check(
        "las de infra_error se excluyen por defecto y se pueden pedir",
        len(load_rows(escribir([base, dict(base, infra_error=True)]))) == 1
        and len(load_rows(escribir([base, dict(base, infra_error=True)]),
                          include_infra=True)) == 2,
    )
    return ok


def check_measured_cost_supersedes_prior(ok: bool) -> bool:
    """§40: el costo medido supersede al prior, y hasta hoy no lo hacia.

    EL COMENTARIO LO PROMETIA Y NADIE LO IMPLEMENTABA. El constructor del router decia
    «measured mean_cost supersedes them once theta has data», y `mean_cost` solo aparecia
    en `as_dict` y en un formato de impresion: el prior ordenaba la cascada PARA SIEMPRE.

    Y el prior erra 2-7x (leccion 5.6). `reflection` declara 5,0 y mide 1,6, asi que la
    cascada nunca lo probaba primero aunque fuera de los mas baratos — y la cascada es el
    mecanismo al que el paper le acredita el 100% de la brecha.

    El costo medido ademas no necesita referencia: son tokens absolutos. El prior esta
    escalado contra `direct`, que solo es factible donde todo entra en ventana.
    """
    from app.paradigms import COST_PRIORS
    from app.policy import MIN_EPISODES_FOR_CONFIDENCE, PolicyBundle, Stat
    from app.router import Router

    print("\n--- 40. el costo medido supersede al prior ---")

    REGION = "many/oracle/loose"
    brazos = ["react", "reflection", "dag_strategy"]

    ok &= check("por prior, `react` seria el mas barato",
                min(brazos, key=lambda p: COST_PRIORS[p]) == "react")

    def orden(bundle) -> list[str]:
        router = Router(bundle, COST_PRIORS, "react")
        return sorted(brazos, key=lambda p: router._cost_key(REGION, p))  # noqa: SLF001

    con = PolicyBundle(version=1, created_at="x", fallback="react", tau=0.0, stats={
        REGION: {
            "react": Stat(episodes=MIN_EPISODES_FOR_CONFIDENCE, cost_sum=8 * 21000),
            "reflection": Stat(episodes=MIN_EPISODES_FOR_CONFIDENCE, cost_sum=8 * 16000),
            "dag_strategy": Stat(episodes=MIN_EPISODES_FOR_CONFIDENCE, cost_sum=8 * 40000),
        }}).sign()
    ok &= check("con evidencia, la cascada arranca por el mas barato MEDIDO y no por el "
                "que el prior dice", orden(con)[0] == "reflection", ", ".join(orden(con)))

    sin = PolicyBundle(version=1, created_at="x", fallback="react", tau=0.0, stats={
        REGION: {p: Stat(episodes=1, cost_sum=999) for p in brazos}}).sign()
    ok &= check("bajo el piso de evidencia cae al prior - una media sobre un episodio es "
                "ruido con nombre de medicion", orden(sin)[0] == "react",
                ", ".join(orden(sin)))

    vacio = PolicyBundle(version=1, created_at="x", fallback="react", tau=0.0).sign()
    ok &= check("sin region conocida tambien cae al prior, y no levanta",
                orden(vacio)[0] == "react")

    return ok


def main() -> int:
    ok = True
    study = build_study()

    print("\n1. Basic quantities")
    ok &= check("best fixed is react", study.best_fixed() == "react", study.best_fixed())
    ok &= check("react mean is 0.70", approx(study.mean_utility("react"), 0.70))
    ok &= check("oracle value is 0.76", approx(study.oracle_value(), 0.76),
                f"{study.oracle_value():.4f}")
    ok &= check("oracle gap is 0.06", approx(study.oracle_gap(), 0.06),
                f"{study.oracle_gap():.4f}")

    print("\n2. The identity oracle_gap == pi * G")
    perfect = study.selection_terms(
        lambda t: "map_reduce" if int(t[1:]) < S_SIZE else "react"
    )
    ok &= check("pi is 0.20", approx(perfect.pi, 0.20), f"{perfect.pi:.4f}")
    ok &= check("G is 0.30", approx(perfect.gain, 0.30), f"{perfect.gain:.4f}")
    ok &= check("pi*G equals the oracle gap",
                approx(perfect.pi * perfect.gain, study.oracle_gap()))

    print("\n3. A perfect router captures the whole gap")
    ok &= check("alpha is 1.0", approx(perfect.alpha, 1.0))
    ok &= check("beta is 0.0", approx(perfect.beta, 0.0))
    ok &= check("captured fraction is 1.0",
                approx(study.captured_fraction(
                    lambda t: "map_reduce" if int(t[1:]) < S_SIZE else "react"), 1.0))
    ok &= check("theorem condition holds", perfect.holds)
    ok &= check("potential loss is 0.45", approx(perfect.loss_potential, 0.45),
                f"{perfect.loss_potential:.4f}")
    ok &= check("a perfect router realises no loss",
                approx(perfect.loss_realised, 0.0))
    ok &= check("beta_max is 0.16667 and stays finite",
                approx(perfect.beta_max, 0.06 / 0.36, tol=1e-6),
                f"{perfect.beta_max:.5f}")

    print("\n4. Corollary 2: a router above beta_max must lose")
    # Perfect recall, but it also fires on 25% of the off-S tasks (beta = 0.25 > 0.1875).
    def sloppy(task_id: str) -> str:
        i = int(task_id[1:])
        if i < S_SIZE:
            return "map_reduce"
        return "map_reduce" if (i - S_SIZE) % 4 == 0 else "react"

    sloppy_terms = study.selection_terms(sloppy)
    ok &= check("realised loss is 0.40 for a map_reduce misroute",
                approx(sloppy_terms.loss_realised, 0.40),
                f"{sloppy_terms.loss_realised:.4f}")
    ok &= check("beta exceeds beta_max",
                sloppy_terms.beta > sloppy_terms.beta_max,
                f"beta={sloppy_terms.beta:.4f} > {sloppy_terms.beta_max:.4f}")
    ok &= check("theorem condition fails", not sloppy_terms.holds)
    ok &= check("captured fraction is negative",
                study.captured_fraction(sloppy) < 0,
                f"{study.captured_fraction(sloppy):.4f}")

    print("\n5. Deferral never loses: coverage 0 pins to the fallback")
    curve = study.risk_coverage(
        rank=lambda t: 1.0 if int(t[1:]) < S_SIZE else 0.0,
        propose=lambda t: "map_reduce",
    )
    ok &= check("curve produced", len(curve) > 1, f"{len(curve)} points")
    zero_coverage = [p for p in curve if p["coverage"] == 0.0]
    ok &= check("at coverage 0 nothing is captured",
                all(approx(p["captured"], 0.0) for p in zero_coverage) if zero_coverage else True)
    best = max(curve, key=lambda p: p["captured"])
    ok &= check("an interior optimum exists below full coverage",
                best["coverage"] < 1.0,
                f"best captured={best['captured']:.3f} at coverage={best['coverage']:.2f}")

    print("\n6. Cascade Dominance: quality loss becomes cost loss")
    ladder = ["direct", "cot", "react", "map_reduce"]
    cascade = study.cascade_value(ladder, detector_sensitivity=1.0, success_threshold=1.0)
    ok &= check("cascade beats the best fixed paradigm",
                cascade["dominates_best_fixed"],
                f"{cascade['cascade_utility']:.4f} vs {cascade['best_fixed_utility']:.4f}")
    ok &= check("cascade captures the full gap",
                approx(cascade["captured_fraction"], 1.0, tol=1e-6),
                f"{cascade['captured_fraction']}")
    ok &= check("and it pays for it in tokens",
                cascade["cost_ratio"] > 1.0,
                f"cost ratio {cascade['cost_ratio']}x")

    weak = study.cascade_value(ladder, detector_sensitivity=0.6, success_threshold=1.0)
    ok &= check("a weak detector degrades the cascade",
                weak["captured_fraction"] <= cascade["captured_fraction"],
                f"{weak['captured_fraction']} <= {cascade['captured_fraction']}")

    print("\n7. Verifiability partition: no oracle means no cascade")
    unverifiable = build_study(has_oracle=False)
    result = unverifiable.cascade_value(ladder)
    ok &= check("cascade declines to run without a detector",
                result["eligible_tasks"] == 0, str(result.get("note", "")))

    print("\n8. Policy bundle: signature, plasticity, promotion guard")
    cold = PolicyBundle.cold_start(fallback="react", tau=0.3)
    ok &= check("cold bundle verifies", cold.verify())
    cold.tau = 0.99
    ok &= check("tampering invalidates the signature", not cold.verify())

    episodes = [
        Episode(
            task_id=f"t{i:03d}",
            region="many/oracle/loose" if i < S_SIZE else "single/oracle/loose",
            paradigm=paradigm,
            utility=fn(i),
            cost_tokens=COST[paradigm],
            was_best=(fn(i) >= max(g(i) for g in UTILITY.values())),
        )
        for i in range(N)
        for paradigm, fn in UTILITY.items()
    ]
    fresh = PolicyBundle.cold_start(fallback="react", tau=0.3)
    learned = Plasticity.candidate(fresh, episodes, tau=0.3)
    ok &= check("learned bundle verifies", learned.verify())
    ok &= check("version advanced", learned.version == fresh.version + 1)

    high = learned.stat("many/oracle/loose", "map_reduce")
    low = learned.stat("single/oracle/loose", "map_reduce")
    ok &= check("plasticity separated the regions",
                high.weight > low.weight,
                f"w(many)={high.weight:.3f} > w(single)={low.weight:.3f}")

    from app.router import Router  # noqa: PLC0415
    from app.paradigms import COST_PRIORS  # noqa: PLC0415

    def value_fn(bundle: PolicyBundle, eps: list[Episode]) -> float:
        return Router(bundle, COST_PRIORS, "react").value_on(eps)

    ok &= check("promotion refuses an empty holdout",
                not promote(fresh, learned, [], value_fn).accepted)
    verdict = promote(fresh, learned, episodes, value_fn)
    ok &= check("promotion reaches a recorded verdict",
                isinstance(verdict.accepted, bool), verdict.reason)

    print("\n8b. Cost-aware utility, and the zero-cost trap")
    from app.metrics import Observation as Ob  # noqa: PLC0415

    # Two paradigms priced 100 and 400, plus one that crashed and recorded nothing.
    poisoned = Study([
        Ob("z1", "r", "cheap", 1.0, 100, True),
        Ob("z1", "r", "dear", 1.0, 400, True),
        Ob("z1", "r", "crashed", 0.0, 0, True),
    ], lambda_cost=0.1)
    ok &= check("a zero-cost row does not become the normaliser",
                approx(poisoned.cost_ratio("z1", "dear"), 4.0),
                f"ratio(dear)={poisoned.cost_ratio('z1', 'dear'):.2f}, expected 4.0")
    ok &= check("the crashed row itself carries no cost penalty",
                approx(poisoned.cost_ratio("z1", "crashed"), 1.0))
    ok &= check("failures are surfaced, not hidden",
                poisoned.summary()["zero_cost_rows"] == 1)

    clean = Study([
        Ob("z1", "r", "cheap", 1.0, 100, True),
        Ob("z1", "r", "dear", 1.0, 400, True),
    ], lambda_cost=0.1)
    ok &= check("lambda=0 is exactly pure quality",
                approx(Study(clean._obs).utility("z1", "dear"), 1.0))  # noqa: SLF001
    ok &= check("at lambda=0.1 the dearer paradigm loses 0.3",
                approx(clean.utility("z1", "dear"), 1.0 - 0.1 * 3.0),
                f"{clean.utility('z1', 'dear'):.3f}")
    ok &= check("the cheapest is never penalised",
                approx(clean.utility("z1", "cheap"), 1.0))
    ok &= check("and the cheap one wins once cost counts",
                clean.best_fixed() == "cheap", clean.best_fixed())

    print("\n9. Grading")
    ok &= check("exact singleton", approx(grading.score("ANSWER: AR123", ["AR123"]), 1.0))
    ok &= check("substring credit on a committed answer",
                approx(grading.score("account AR123", ["AR123"]), 1.0))
    ok &= check("a scattergun list gets no singleton credit",
                approx(grading.score("AR123; AR999; AR777", ["AR123"]), 0.0))
    f1 = grading.score("Ana Perez; Luis Gomez", ["Ana Perez", "Luis Gomez", "Eva Diaz"])
    ok &= check("set F1 is partial", approx(f1, 0.8), f"{f1:.4f}")
    ok &= check("wrong answer scores zero",
                approx(grading.score("nobody", ["Ana Perez"]), 0.0))

    print("")
    print("14. El reintento del cliente")
    from app.llm import backoff_seconds, MAX_BACKOFF_SECONDS as CAP
    import re as _re

    # Las tres propiedades se rompieron una vez cada una: un Retry-After sin tope que
    # parecio un cuelgue, un jitter que podia esperar MENOS de lo que el servidor pidio,
    # y un tope aplicado despues del jitter que colapsaba la dispersion justo cuando
    # todos los workers recibian el mismo hint grande.
    floors = all(
        min(backoff_seconds(3, str(h)) for _ in range(200)) >= min(CAP, h) - 1e-9
        for h in (1.0, 10.0, 30.0, 60.0, 300.0, 1e9)
    )
    ok &= check("Retry-After es un piso: nunca se espera menos", floors)

    worst = max(backoff_seconds(a, str(h)) for a in range(1, 9) for h in (1, 60, 10**9))
    ok &= check("toda espera esta acotada", worst <= CAP * 1.5 + 1e-9, f"max {worst:.1f}s")

    spreads = {h: len({backoff_seconds(4, h) for _ in range(300)})
               for h in (None, "1", "60", "99999")}
    ok &= check("hay jitter en todos los caminos, tope incluido",
                all(v > 250 for v in spreads.values()), str(spreads))

    dated = [backoff_seconds(2, "Wed, 21 Oct 2026 07:28:00 GMT") for _ in range(20)]
    ok &= check("un Retry-After con fecha cae al exponencial sin romper",
                all(0 < w <= CAP * 1.5 for w in dated))

    llm_src = (ROOT / "app" / "llm.py").read_text(encoding="utf-8")
    emb_src = (ROOT / "app" / "embeddings.py").read_text(encoding="utf-8")
    defs = len(_re.findall(r"def request_with_retry", llm_src + emb_src))
    imported = bool(_re.search(r"from \.llm import .*request_with_retry", emb_src))
    own_loop = bool(_re.search(r"for attempt in range|attempt \+= 1", emb_src))
    ok &= check("un solo bucle de reintento en los dos clientes",
                defs == 1 and imported and not own_loop,
                f"defs={defs}, embeddings importa={imported}, bucle propio={own_loop}")

    print("")
    print("15. El regulador adaptativo del cliente")
    from app.llm import (THROTTLE, estimate_tokens, RETRY_BUDGET_SECONDS,
                         _INITIAL_TOKENS_PER_SECOND as CEIL,
                         _MIN_TOKENS_PER_SECOND as FLOOR)
    import threading as _th

    # Reintentar no alcanza contra una cuota AGOTADA: los cinco intentos caen dentro de
    # la misma ventana. El cliente tiene que marcar el paso, y como no sabemos la cuota
    # del deployment, la aprende del unico dato confiable que hay: el 429.
    rate0 = THROTTLE.describe()["tokens_per_second"]
    for _ in range(6):
        THROTTLE.on_rate_limited()
    dropped = THROTTLE.describe()["tokens_per_second"]
    ok &= check("un 429 baja el paso multiplicativamente", dropped < rate0,
                f"{rate0:.0f} -> {dropped:.0f} tok/s")
    ok &= check("hay piso: no se degrada a cero", dropped >= FLOOR, f"{dropped:.0f} >= {FLOOR:.0f}")

    for _ in range(200):
        THROTTLE.on_success()
    recovered = THROTTLE.describe()["tokens_per_second"]
    ok &= check("recupera con exitos, sin pasarse del techo",
                dropped < recovered <= CEIL + 1e-9, f"{recovered:.0f} <= {CEIL:.0f}")

    # Una sola llamada mas grande que el burst entero no debe colgar. map_reduce sobre
    # 483k tokens hace exactamente eso.
    done = []
    t = _th.Thread(target=lambda: (THROTTLE.acquire(10**7), done.append(True)), daemon=True)
    t.start(); t.join(timeout=45)
    ok &= check("una llamada mayor que el burst no deadlockea", bool(done), str(done))

    ok &= check("estima tokens del payload",
                estimate_tokens({"messages": [{"role": "u", "content": "x" * 4000}],
                                 "max_completion_tokens": 100}) == 1100)
    ok &= check("el presupuesto de reintento es tiempo, no intentos",
                RETRY_BUDGET_SECONDS >= 300, f"{RETRY_BUDGET_SECONDS:.0f}s")

    ok = check_probe(ok)
    ok = check_product_path(ok)
    ok = check_belief_history(ok)
    ok = check_rec_solver(ok)
    ok = check_continuation_axis(ok)
    ok = check_decision_cycle(ok)
    ok = check_ratchet_bound(ok)
    ok = check_request_demands(ok)
    ok = check_completeness_contract(ok)
    ok = check_record_is_self_describing(ok)
    ok = check_malformation_counter(ok)
    ok = check_dial_is_enforced(ok)
    ok = check_consolidation_is_idempotent(ok)
    ok = check_promotion_has_an_interval(ok)
    ok = check_stopping_rule(ok)
    ok = check_availability_and_guard(ok)
    ok = check_trust_is_signed_policy(ok)
    ok = check_horizon_has_its_own_evidence(ok)
    ok = check_analysis_entrypoints(ok)
    ok = check_product_leaves_a_trace(ok)
    ok = check_contract_names_its_deficit(ok)
    ok = check_scope_is_a_second_axis(ok)
    ok = check_coverage_trigger(ok)
    ok = check_handoff_authorisation(ok)
    ok = check_measured_cost_supersedes_prior(ok)
    ok = check_money_is_a_unit_not_a_number(ok)
    ok = check_load_rows_guards_the_analyst(ok)
    ok = check_measurement_and_state_are_two_trees(ok)
    ok = check_model_is_an_action(ok)
    ok = check_absence_and_presupposition(ok)
    ok = check_assembler_soundness(ok)
    ok = check_who_sets_the_dial(ok)
    ok = check_the_code_draws_the_graph(ok)
    ok = check_retrieval_is_a_factor(ok)
    ok = check_board_is_a_tool_for_everyone(ok)
    ok = check_coverage_precondition_abstains(ok)
    ok = check_model_pool(ok)
    ok = check_tariffs_are_data(ok)

    print("\n" + ("ALL CHECKS PASSED" if ok else "THERE ARE FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
