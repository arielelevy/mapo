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
        Availability,
        FEATURE_AVAILABILITY,
        Features,
        REGION_VOCABULARY,
        REGION_VOCABULARY_PREVIO,
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
    # EL VOCABULARIO CAMBIO (CP-6, 2026-08-30): `regions/2-continuation` ->
    # `regions/3-literal`, que es el anterior x el eje `literal`. No fue una eleccion de
    # diseno: con la politica de desempate por costo evaluada leave-one-out sobre 41 tareas
    # y 7 brazos, el nuevo gana en los DOS ejes contra el que reemplaza — utilidad 0,951
    # contra 0,928 y 48% de ahorro contra 37%.
    ok &= check("la region habla el vocabulario nuevo, y CONSERVA los cuatro segmentos "
                "anteriores como prefijo",
                f.region() == "many/oracle/loose/chain/?"
                and f.region_previa() == "many/oracle/loose/chain"
                and REGION_VOCABULARY == "regions/3-literal")
    ok &= check("el eje `literal` entra al final, medido sobre el material",
                Features(n_units=20, has_oracle=True, irreversible=False,
                         shared_writes=False, budget_tokens=60_000, coupling=0.2,
                         continuation=True,
                         literal="lit_present").region().endswith("/lit_present"))
    ok &= check("continuidad sin medir queda visible en la region",
                "/c?/" in Features(n_units=2, has_oracle=False, irreversible=False,
                                   shared_writes=False, budget_tokens=1000).region())

    # EL VOCABULARIO ANTERIOR SE CONSERVA, y no por nostalgia: 5.932 filas del registro lo
    # llevan estampado y `load_rows` levanta si un archivo mezcla dos. Poder recomputarlo
    # es lo que permite leer ese registro sin re-correrlo.
    ok &= check("el vocabulario anterior sigue siendo recomputable — sin eso, 5.932 filas "
                "pagas quedan irreproducibles",
                REGION_VOCABULARY_PREVIO == "regions/2-continuation"
                and f.region_previa() == "many/oracle/loose/chain")

    # LA SONDA SIGUE TENIENDO QUE RESOLVER. El vocabulario que MAS ahorraba —
    # `cardinalidad x literal`, 69% contra 48% — es puramente COMPUTABLE, y por eso deja al
    # ciclo de decision de dos pasos sin nada que establecer. Se descarto por eso, y este
    # chequeo impide que vuelva a entrar sin que alguien lo note.
    ok &= check("la region conserva un eje DERIVED, o la sonda no tiene que resolver",
                any(FEATURE_AVAILABILITY.get(n) is Availability.DERIVED
                    for n in ("coupling", "horizon_unknown"))
                and f.region() != f.computable_only().region())

    # LOS DOS PREDICTORES NUEVOS SON COMPUTABLE, y eso es medio motivo de haberlos elegido:
    # sobreviven la proyeccion D2, asi que una regla que los use SI puede disparar en modo
    # determinista.
    ok &= check("`literal` y `cardinality` sobreviven la proyeccion determinista",
                Features(n_units=1, has_oracle=True, irreversible=False,
                         shared_writes=False, budget_tokens=8000,
                         cardinality="singular", literal="lit_present")
                .computable_only().region().endswith("/lit_present"))
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
def check_noise_floor_detects_a_real_prize(ok: bool) -> bool:
    """El piso de ruido tiene que dejar pasar un premio que existe.

    LA FALLA QUE ESTO IMPIDE (revision externa, 2026-09-01). `_predictores.py` estimaba el
    piso remuestreando las replicas de cada celda REAL y recalculando la brecha: eso es la
    distribucion bootstrap del propio estadistico, cuya media es >= la brecha observada por
    construccion. Con ese "piso", brecha - piso salia <= 0 con CUALQUIER dato, y el paper
    reporto como negativo un held-out que con el estimador correcto es positivo.

    El estimador correcto (`metrics.noise_floor`, y su version emparejada por numero de
    brazos) construye pseudo-brazos con replicas del MISMO brazo: toda brecha entre ellos es
    ruido. Sobre un sintetico con premio real conocido, el piso correcto tiene que quedar
    muy por debajo del premio, y el bootstrap del estadistico tiene que quedar pegado a la
    brecha observada. Las dos cosas se comprueban aca.
    """
    import random
    import statistics

    from app.metrics import Study

    print("\n--- 60. el piso de ruido deja pasar un premio real ---")
    rng = random.Random(2026)
    n_tasks, n_arms, n_rep, sd = 60, 3, 3, 0.15
    # tres brazos con premio real de oraculo: cada tarea la resuelve uno solo (u=1), los
    # otros dan 0,5. El mejor fijo vale ~0,667 y el oraculo ~1,0: premio real ~+0,33.
    truth = {}
    for t in range(n_tasks):
        ganador = t % n_arms
        for p in range(n_arms):
            truth[(t, p)] = 1.0 if p == ganador else 0.5
    reps = {k: [min(1.0, max(0.0, v + rng.gauss(0, sd))) for _ in range(n_rep)]
            for k, v in truth.items()}
    U = {k: statistics.mean(v) for k, v in reps.items()}
    tids, brazos = range(n_tasks), range(n_arms)
    ora = statistics.mean(max(U[(t, p)] for p in brazos) for t in tids)
    fijo = max(statistics.mean(U[(t, p)] for t in tids) for p in brazos)
    brecha = ora - fijo

    # (a) el estimador defectuoso: bootstrap del estadistico
    sesgos = []
    for _ in range(200):
        falso = {(t, p): statistics.mean(rng.choice(reps[(t, p)]) for _ in range(n_rep))
                 for t in tids for p in brazos}
        o = statistics.mean(max(falso[(t, p)] for p in brazos) for t in tids)
        f_ = max(statistics.mean(falso[(t, p)] for t in tids) for p in brazos)
        sesgos.append(o - f_)
    piso_malo = statistics.mean(sesgos)

    # (b) el estimador correcto: pseudo-brazos del MISMO brazo, tantos como brazos compara el
    # panel, y cada uno vale la MEDIA de n_rep replicas remuestreadas, porque la brecha
    # observada se computa sobre medias de celda. Una replica suelta por pseudo-brazo tiene
    # sqrt(n_rep) mas desvio e infla el piso (eso hace `Study.noise_floor`, que por eso es
    # una cota conservadora y no el estimador calibrado).
    def piso_pseudo(rep_dict):
        vals = []
        for p in brazos:
            for _ in range(150):
                pseudo = {t: [statistics.mean(rng.choice(rep_dict[(t, p)]) for _ in range(n_rep))
                              for _ in range(n_arms)] for t in tids}
                o = statistics.mean(max(pseudo[t]) for t in tids)
                f_ = max(statistics.mean(pseudo[t][j] for t in tids) for j in range(n_arms))
                vals.append(o - f_)
        return statistics.mean(vals)

    piso_bueno = piso_pseudo(reps)
    piso_conservador = statistics.mean(
        Study.noise_floor({t: reps[(t, p)] for t in tids})["noise_oracle_gap"] for p in brazos)

    ok &= check("el premio real del sintetico es grande (>= 0,25)", brecha >= 0.25,
                f"brecha {brecha:+.3f}")
    ok &= check("el bootstrap del estadistico NO sirve de piso: queda pegado a la brecha",
                abs(piso_malo - brecha) < 0.05,
                f"piso_bootstrap {piso_malo:+.3f} vs brecha {brecha:+.3f}")
    ok &= check("el estimador por pseudo-brazos deja pasar el premio: piso < brecha/3",
                piso_bueno < brecha / 3,
                f"piso {piso_bueno:+.3f} -> neto {brecha - piso_bueno:+.3f}")
    ok &= check("Study.noise_floor es mas conservador que el calibrado (replicas sueltas)",
                piso_conservador >= piso_bueno, f"{piso_conservador:+.3f} >= {piso_bueno:+.3f}")
    # y sobre brazos identicos el piso calibrado tiene que estar cerca de la brecha observada
    reps0 = {(t, p): [0.5 + rng.gauss(0, sd) for _ in range(n_rep)] for t in tids for p in brazos}
    U0 = {k: statistics.mean(v) for k, v in reps0.items()}
    brecha0 = (statistics.mean(max(U0[(t, p)] for p in brazos) for t in tids)
               - max(statistics.mean(U0[(t, p)] for t in tids) for p in brazos))
    piso0 = piso_pseudo(reps0)
    ok &= check("sobre brazos identicos, brecha - piso queda dentro de +-0,03",
                abs(brecha0 - piso0) < 0.03, f"brecha {brecha0:+.3f} piso {piso0:+.3f}")
    return ok


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
    from app.paradigms.handoff import SCOPES, _authorises, _scopes
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
    sub = surface.scoped(scopes[0])
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


def check_second_policy(ok: bool) -> bool:
    """§54: la SEGUNDA politica —que modelo por paradigma— y su orden respecto de las cotas.

    POR QUE DOS POLITICAS Y NO UNA CON UN EJE MAS. `P27e` midio que la ventaja del modelo
    caro vive en el PARADIGMA (+0,8755 en `react`, +0,0912 en `rewoo`) y que la REGION no
    explica nada (dispersion +0,1667 contra una sd interna de 0,5046). Meter el modelo
    adentro de `stats` —indexado por region— pagaria la multiplicacion de bins sin comprar
    discriminacion, que es exactamente el mecanismo por el que `P15` fracaso. Contado sobre
    2.494 episodios: `modelo x paradigma` son 13 bins con el 100% de los episodios
    visibles, contra 134 bins con el 90% si se agrega la region.

    EL ORDEN ES PRECONDICION -> ARITMETICA -> APRENDIDO, y no es negociable. Theta puede
    preferir el caro y el dial haberlo prohibido, o el presupuesto haberlo podado. Un
    aprendizaje que pudiera levantar una precondicion no seria una preferencia: seria una
    manera de evadirla.

    Y TRES `None` QUE SON TRES COSAS DISTINTAS: sin datos, con un solo modelo por encima
    del piso de evidencia —un modelo solo no es una comparacion—, y con margen por debajo
    de tau. En los tres, quien llama cae a su regla y el registro dice que theta no opino,
    que NO es lo mismo que haber opinado a favor del barato.
    """
    from app.models import CATALOG
    from app.paradigms import COST_PRIORS
    from app.policy import MIN_EPISODES_FOR_CONFIDENCE, PolicyBundle, Stat
    from app.router import Router

    print("\n--- 54. la segunda politica: que modelo por paradigma ---")

    def st(n, u):
        return Stat(episodes=n, utility_sum=u * n)

    piso = MIN_EPISODES_FOR_CONFIDENCE
    b = PolicyBundle.cold_start("react", 0.05)
    b.model_stats = {
        "react": {"fast": st(piso + 4, 0.20), "deep": st(piso + 4, 0.88)},
        "rewoo": {"fast": st(piso + 4, 0.56), "deep": st(piso + 4, 0.60)},
        "gist_reader": {"fast": st(piso - 5, 0.90), "deep": st(piso + 4, 0.10)},
    }
    b.model_version = 1
    b.sign()

    ok &= check("va ADENTRO del payload firmado, como `floors` y `trusts_elicited`",
                b.verify())
    b.model_stats["react"]["deep"] = st(piso + 4, 0.01)
    ok &= check("editarla invalida la firma: no se instala por fuera de la promocion",
                not b.verify())
    b.model_stats["react"]["deep"] = st(piso + 4, 0.88)
    b.sign()

    # CON TOLERANCIA Y NO IGUALDAD EXACTA. El margen es una resta de medias en punto
    # flotante y da 0,6799999999999999: un aserto de igualdad exacta sobre eso falla por
    # la representacion y no por el comportamiento — un test que miente en contra.
    nombre, margen = b.best_model("react", b.tau)
    ok &= check("con margen, theta nombra el modelo y dice por cuanto",
                nombre == "deep" and abs(margen - 0.68) < 1e-9)
    ok &= check("con margen por debajo de tau, NO opina — 0,04 < 0,05",
                b.best_model("rewoo", b.tau)[0] is None)
    ok &= check("con un solo modelo por encima del piso tampoco: uno solo no es una "
                "comparacion, y promediar el otro le prestaria confianza que no tiene",
                b.best_model("gist_reader", b.tau)[0] is None)
    ok &= check("y sobre un paradigma nunca visto tampoco",
                b.best_model("no_visto", b.tau)[0] is None)

    ok &= check("su version es SEPARADA: revertir una no obliga a revertir la otra",
                b.model_version == 1 and b.version != b.model_version)

    docs = {f"u{i}": "x" * 4000 for i in range(30)}
    base = {"unit_ids": list(docs), "budget_tokens": 200_000, "question": "q",
            "task_id": "t", "has_oracle": True}
    router = Router(b, COST_PRIORS, "react")

    def plan(task, **kw):
        return router.plan(task, region="many/oracle/loose", candidates=["react"],
                           documents=docs, **kw)

    con = plan(base, models=CATALOG)
    ok &= check("el router la CONSUME: sin catalogo seria una politica que nadie lee",
                con.model == "deep")
    ok &= check("y el EXPLAIN dice que fue theta y por cuanto margen",
                any("theta lo prefiere" in n for n in con.notes))

    podado = plan(dict(base, budget_usd=0.02), models=CATALOG)
    ok &= check("el presupuesto GANA sobre lo aprendido: la cota no se negocia",
                podado.model == "fast")
    ok &= check("y se registra que theta opino y NO se pudo seguir — distinto de no haber "
                "opinado, y sin eso nadie ve que lo aprendido no gobierna nada",
                any("NO es admisible" in n for n in podado.notes))

    vacio = PolicyBundle.cold_start("react", 0.05).sign()
    sin = Router(vacio, COST_PRIORS, "react").plan(
        base, region="many/oracle/loose", candidates=["react"], documents=docs,
        models=CATALOG,
    )
    ok &= check("sin nada aprendido cae a la regla —el mas barato que el dial admite—",
                sin.model == "fast")
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

    s = _replace(base, reasoning_effort='none')
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
    # EL TEST PRUEBA EL MECANISMO, NO EL MAPEO. Fijaba `fast` = nano y se rompio el dia que
    # el autor cambio `roles.fast` a luna — que es un cambio de CONFIGURACION, dato externo,
    # y no puede romper una suite. Lo que tiene que valer es que el pool registre la
    # propiedad de cada modelo tal como el arancel la declara, sea cual sea el mapeo.
    registrados = set(dos.describe()["effort_not_controllable_with_tools"])
    esperados = {m.name for m in (_models.FAST, _models.DEEP)
                 if not m.explicit_effort_with_tools}
    ok &= check(f"el pool registra exactamente los que NO aceptan el nivel con tools "
                f"({sorted(esperados)})", registrados == esperados)
    ok &= check("las dos propiedades salen del arancel, que es donde vive lo MEDIDO: una "
                "llamada real por modelo, no documentacion leida",
                isinstance(_models.FAST.reasons_by_default, bool)
                and isinstance(_models.DEEP.reasons_by_default, bool))

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

    # LA VENTANA ES DE ENTRADA, NO LA TOTAL, y eso es lo que el test tiene que fijar — no
    # el numero de un modelo en particular. `check_pair` compara contra tokens de PROMPT;
    # usar la total (que incluye 128.000 de salida) admitiria planes que no entran.
    # Fijaba `FAST == 272_000` y se rompio al cambiar `roles.fast` a luna: un cambio de
    # configuracion externa no puede romper una suite.
    import json as _json
    _tar = _json.loads(Path("config/tariffs.json").read_text(encoding="utf-8"))
    for papel, modelo in (("fast", _models.FAST), ("deep", _models.DEEP)):
        declarada = _tar["tariffs"][_tar["roles"][papel]]["context_input_tokens"]
        ok &= check(f"la ventana de `{papel}` es la de ENTRADA declarada en el arancel "
                    f"({declarada:,}), no la total",
                    modelo.context_tokens == declarada)
    ok &= check("y ninguna incluye los 128.000 de salida: la total nunca es la ventana "
                "contra la que se admite un plan",
                all(m.context_tokens % 1000 == 0 and m.context_tokens < 1_050_000
                    for m in (_models.FAST, _models.DEEP)))
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

    # `seal_replay` DEJA DE SER UNA GARANTIA DECLARADA SIN LECTOR (`X-5h`, 2026-08-29).
    #
    # A3 dice «Replay sealed from cache» y el campo existia desde siempre con CERO lectores
    # fuera de `assurance.py`. Es la familia de `theta_may_learn_online`, y peor: aquella
    # invariante se cumplia por casualidad —`Plasticity.apply` solo corre offline— y esta
    # no se cumplia.
    from app.assurance import PROFILES
    from app.config import Settings
    from app.llm import LLMClient, SealedCacheMiss

    ok &= check("solo A3 declara replay sellado — si lo declarara otro nivel, sellar en "
                "replay dejaria de significar «certificado»",
                [a for a, pr in PROFILES.items() if pr.seal_replay]
                == [Assurance.CERTIFIED])

    vivo = LLMClient(Settings.from_env())
    sellado = vivo.sealed_view()
    ok &= check("la vista sellada esta sellada", sellado._sealed)  # noqa: SLF001
    ok &= check("Y EL ORIGINAL NO: sellar no se contagia. El pool devuelve el MISMO "
                "objeto por modelo, asi que mutar el flag dejaria sellado al cliente de "
                "todos los requests siguientes — un sellado que se contagia aparece en "
                "un request que no lo pidio",
                not vivo._sealed and sellado is not vivo)  # noqa: SLF001
    ok &= check("sellar dos veces es sellar una: devuelve el mismo objeto",
                sellado.sealed_view() is sellado)
    ok &= check("y comparten cache y namespace — lo unico que cambia es que un miss deja "
                "de ser una llamada",
                sellado.cache_root == vivo.cache_root
                and sellado.fingerprint == vivo.fingerprint)
    try:
        sellado.complete(messages=[{"role": "user",
                                    "content": "esto no puede estar en ningun cache"}])
        ok &= check("un miss sellado levanta", False)
    except SealedCacheMiss:
        ok &= check("un miss sellado LEVANTA en vez de llamar en vivo: eso es lo que "
                    "hace que un replay de A3 no pueda tocar el modelo en silencio", True)


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


def check_estimates_come_from_the_corpus(ok: bool) -> bool:
    """§55: el conteo de celdas sale del CORPUS, nunca de un archivo de resultados (P-16).

    Dos errores del mismo dia, las dos veces con la aritmetica bien y la ENTRADA mal: P26
    estimado en 362k leyendo un .jsonl parcial (90 filas sobre 6 de 32 tareas) contra 12,2M
    reales — 34x — y su docstring en 792k contra 12,4M — 18x.

    LO QUE ESTE TEST FIJA NO ES UN NUMERO, ES DE DONDE SALE. Un archivo de resultados no
    declara si esta completo, y una corrida que murio a la mitad se lee igual que una que
    termino, asi que pasarle uno tiene que LEVANTAR y no devolver un numero plausible.
    """
    from bench._estimate import count_tasks, estimate, measured_cost

    print()
    print("--- 55. estimar contra el corpus, no contra el registro ---")

    ok &= check("cuenta las tareas del corpus", count_tasks("corpus/gold_p18") == 32)
    try:
        count_tasks("results/nano/gold_p18_rows.jsonl")
        ok &= check("un archivo de resultados como fuente de conteo LEVANTA", False)
    except ValueError:
        ok &= check("un archivo de resultados como fuente de conteo LEVANTA: es el modo "
                    "de falla que costo 34x, y devolver un numero plausible es peor que "
                    "romper", True)

    costos = {"a": 100.0, "b": 10.0}
    e = estimate("corpus/gold_p18", ["a", "b"], ["x", "y"], repeat=3, costs=costos)
    ok &= check("las celdas son tareas x paradigmas x brazos x repeat, aritmetica pura",
                e.cells == 32 * 2 * 2 * 3)
    ok &= check("y el total usa el costo medido de CADA paradigma, no un promedio",
                e.tokens == (100.0 + 10.0) * 32 * 3 * 2)

    sin_n = estimate("corpus/gold_p18", ["a", "nuevo"], ["x"], 3, costos)
    ok &= check("un paradigma sin medir deja el total en SIN N — rellenarlo con la media "
                "inventaria el numero que se pide: hay ~30x entre el mas caro y el mas "
                "barato del catalogo",
                sin_n.tokens is None and sin_n.unmeasured == ("nuevo",))
    ok &= check("pero las celdas se cuentan igual: el conteo no depende de haber medido",
                sin_n.cells == 32 * 2 * 3)

    # MEDIANA Y NO MEDIA: una celda que se fue de mambo arrastra la media justo donde no
    # hay que equivocarse.
    filas = [{"paradigm": "p", "cost_tokens": c} for c in (10, 10, 10, 10, 10_000)]
    ok &= check("el costo por celda es la MEDIANA: una celda descontrolada no arrastra "
                "la estimacion", measured_cost(filas)["p"] == 10)
    filas.append({"paradigm": "p", "cost_tokens": 9, "infra_error": True})
    ok &= check("y un infra_error no entra: no es parte de la evaluacion",
                measured_cost(filas)["p"] == 10)

    ok &= check("el cache es una DECLARACION del que llama, y `frio` es el default porque "
                "es el caso que se subestimo las dos veces", e.cache == "frio")
    return ok


def check_factors_reach_the_model(ok: bool) -> bool:
    """S56: un factor que no llega a la declaracion de tools NO EXISTE (D-1c, F-2b).

    `_run_tool_loop` es el UNICO sitio del repo que manda `tools` al modelo, y llamaba a
    `specs_for` sin pasar `terse` ni `offer_board`. Los dos factores tenian test sobre
    `specs_for` y ninguno sobre el CAMINO, asi que los dos estaban implementados y ninguno
    ejecutado: `offer_board=True` se habria corrido entero y medido CERO —la tool jamas
    aparece en la lista que el modelo ve— y F-2b habria concluido «el board no compra
    nada» por un defecto de cableado.

    LA PRUEBA ES EL CAMINO, no la funcion. Un test sobre `specs_for` seguia pasando con el
    bug puesto, que es exactamente por que no lo encontro.
    """
    from app.paradigms import _run_tool_loop
    from app.retrieval import CorpusView, LexicalRetriever
    from app.tools import ToolSurface

    print()
    print("--- 56. los factores llegan a la declaracion de tools ---")

    vistas = []

    # EL `Usage` REAL, no uno falso: un doble que no implementa `merge` esconde justo el
    # acoplamiento que este test recorre.
    from app.llm import Usage as _RealUsage

    class _Completion:
        def __init__(self):
            self.text, self.usage, self.tool_calls = "listo", _RealUsage(), []

    class _Espia:
        def complete(self, messages, tools=None, **kw):
            vistas.append([t["function"]["name"] for t in (tools or [])])
            return _Completion()

    docs = {f"u{i}": f"unidad {i}" for i in range(4)}
    view = CorpusView(task_id="t", documents=docs, unit_ids=list(docs),
                      relevant_units=["u1"])

    def correr(**kw):
        vistas.clear()
        s = ToolSurface(view=view, hybrid=LexicalRetriever(), semantic=LexicalRetriever(),
                        lexical=LexicalRetriever(), variant="basic",
                        budget_tokens=40_000, **kw)
        _run_tool_loop(_Espia(), s, [{"role": "user", "content": "x"}], 1)
        return vistas[0]

    base = correr()
    ok &= check("sin factores, el board NO se ofrece: es el regimen ya medido",
                "post" not in base and "board" not in base)
    con_board = correr(offer_board=True)
    ok &= check("con `offer_board` la tool LLEGA al modelo — esto es lo que fallaba, y su "
                "ausencia habria dado «el board no compra nada» por cableado",
                "post" in con_board and "board" in con_board)
    ok &= check("y `offer_read_all` tambien viaja por el mismo camino",
                "read_all" in correr(offer_read_all=True))

    # `terse` no cambia QUE tools hay, cambia su descripcion: se mide por tamano.
    largo = ToolSurface(view=view, hybrid=LexicalRetriever(), semantic=LexicalRetriever(),
                        lexical=LexicalRetriever(), variant="basic", budget_tokens=40_000)
    corto = ToolSurface(view=view, hybrid=LexicalRetriever(), semantic=LexicalRetriever(),
                        lexical=LexicalRetriever(), variant="basic", budget_tokens=40_000,
                        terse_tools=True)
    import json as _json
    tam = []
    for sup in (largo, corto):
        vistas.clear()
        espia = _Espia()
        original = espia.complete
        capt = []

        def complete(messages, tools=None, _c=capt, **kw):
            _c.append(_json.dumps(tools))
            return _Completion()
        espia.complete = complete
        _run_tool_loop(espia, sup, [{"role": "user", "content": "x"}], 1)
        tam.append(len(capt[0]))
    ok &= check(f"`terse_tools` acorta la spec que el modelo REALMENTE recibe "
                f"({tam[0]} -> {tam[1]} chars)", tam[1] < tam[0])
    return ok


def check_ingest_is_its_own_measurement(ok: bool) -> bool:
    """S57: el NER agrupa, y la ingesta se mide APARTE de la ejecucion (G-4, G-1, K-6).

    DOS MECANISMOS QUE SE SOSTIENEN MUTUAMENTE. Con el corpus de entidades, un extractor
    que no clusteriza devuelve «m. cavallero» de una unidad y «marta cavallero» de otra:
    dos nodos, y el grafo partido justo entre las unidades que habia que conectar. Y un
    indice que se construye adentro del request le cobra a una fila arbitraria un costo que
    ninguna otra fila del mismo brazo vuelve a pagar.

    LA CLUSTERIZACION ES CONSERVADORA Y ESO SE PRUEBA. Unir de mas es peor que unir de
    menos: dos personas fundidas en un nodo dan una respuesta con la confianza de una
    travesia y el contenido de una confusion, y nada aguas abajo lo detecta.
    """
    from app.ingest import canonical_form, cluster

    print()
    print("--- 57. el NER agrupa y la ingesta se mide aparte ---")

    ok &= check("la inicial mas apellido es la misma entidad",
                canonical_form("m. cavallero", "marta cavallero"))
    ok &= check("el apellido solo tambien", canonical_form("cavallero", "marta cavallero"))
    ok &= check("y nombre mas inicial", canonical_form("marta c.", "marta cavallero"))
    ok &= check("dos personas distintas NO se unen",
                not canonical_form("marta arrieta", "marta cavallero"))

    r = cluster({"marta cavallero": ["m1"], "m. cavallero": ["m2"], "duarte x": ["m3"]},
                {"marta cavallero": ["duarte x"], "m. cavallero": ["duarte x"]})
    ok &= check("las variantes colapsan a UN nodo, con las unidades de las dos",
                r["entity_units"].get("marta cavallero") == ["m1", "m2"])
    ok &= check("el representante es la forma mas LARGA, no la mas frecuente: la mas larga "
                "es la mas especifica", "m. cavallero" not in r["entity_units"])
    ok &= check("las aristas se deduplican al representante — dos aristas a la misma "
                "entidad no son grado 2",
                r["edges"].get("marta cavallero") == ["duarte x"])
    ok &= check("y queda escrito QUE se fusiono con que, o un grafo raro no se diagnostica",
                r["aliases"] == {"m. cavallero": "marta cavallero"})

    # EL CASO QUE DECIDE: apellido compartido. Unir seria inventar una desambiguacion.
    amb = cluster({"marta cavallero": ["m1"], "ignacio cavallero": ["m2"],
                   "cavallero": ["m3"]}, {})
    ok &= check("con el apellido compartido por DOS personas, la forma corta no se une a "
                "ninguna: unir de mas produce una confusion que nada aguas abajo detecta",
                sorted(amb["entity_units"]) == ["cavallero", "ignacio cavallero",
                                                "marta cavallero"])

    # LA INGESTA NO SE COBRA EN LA EJECUCION.
    from app.retrieval import CorpusView, LexicalRetriever
    from app.tools import ToolSurface
    docs = {"u0": "texto"}
    view = CorpusView(task_id="t", documents=docs, unit_ids=["u0"], relevant_units=[])
    sup = ToolSurface(view=view, hybrid=LexicalRetriever(), semantic=LexicalRetriever(),
                      lexical=LexicalRetriever(), variant="basic", budget_tokens=1000)
    ok &= check("la superficie arranca sin gasto de ingesta", sup.usage()["ingest_tokens"] == 0)
    sup.ingest_tokens = 5000
    ok &= check("y lo reporta cuando lo hay, en su propia columna",
                sup.usage()["ingest_tokens"] == 5000)
    from app.runner import Row
    ok &= check("la fila tiene la columna, separada de `cost_tokens`",
                "ingest_tokens" in Row.__dataclass_fields__)
    return ok


def check_every_paradigm_runs_offline(ok: bool) -> bool:
    """S58: cada paradigma del registro corre de punta a punta contra un cliente falso.

    DE DONDE SALE. Mover el indice de entidades a `app/ingest.py` se llevo `WALK_DEPTH` con
    las constantes vecinas, y `graph_traverse` quedo con un `NameError` **en tiempo de
    ejecucion, no de import** — asi que compilaba, importaba, y ningun test lo veia. Lo
    encontro un smoke que costo tokens. Este no cuesta ninguno.

    QUE PRUEBA Y QUE NO. No prueba que respondan bien: el cliente falso devuelve siempre lo
    mismo. Prueba que el camino ENTERO se ejecuta — que no hay nombre sin definir, firma
    cambiada ni campo que explote al construir el `Result`. Es el piso mas barato que
    existe, y el unico que atrapa esta clase de defecto antes de gastar.
    """
    from app.llm import Usage as _RealUsage
    from app.paradigms import Infeasible, REGISTRY, RETIRED
    from app.retrieval import CorpusView, LexicalRetriever
    from app.tools import ToolSurface

    print()
    print("--- 58. los paradigmas corren de punta a punta, sin gastar ---")

    class _Completion:
        def __init__(self, texto):
            self.text, self.usage, self.tool_calls = texto, _RealUsage(), []

    # EL CACHE VA A UN TEMPORAL, no al repo. `graph_traverse` construye su indice al vuelo
    # cuando la ingesta falta, y con `cache_root = Path(".")` lo escribia en `lab/ingest/`:
    # un test que deja artefactos en el arbol de trabajo.
    import tempfile

    _tmp = Path(tempfile.mkdtemp(prefix="mapo-test-"))

    class _Cliente:
        """Devuelve un JSON que satisface a todos: plan, sub-preguntas, respuesta y fin."""
        fingerprint = "fake|t=0"
        cache_root = _tmp
        spent = _RealUsage()

        def complete(self, messages, **kw):
            return _Completion(
                '{"sub_questions": [{"id": "sq_001", "question": "q", "depends_on": []}], '
                '"steps": [], "plan": [], "read": [], "entities": [], "relations": [], '
                '"status": "complete", "partial": "AR1", "answer": "AR1", '
                '"dispatch": "una sub-pregunta", "done": false}'
                + chr(10) + "ANSWER: AR1"
            )

    docs = {f"u{i}": f"unidad {i}: Marta Arrieta, account AR100{i}." for i in range(6)}
    tarea = {
        "task_id": "t", "question": "What is the account for Marta Arrieta?",
        "cell": "C1_single_verifiable", "budget_tokens": 40_000,
        "unit_ids": list(docs), "oracle": ["AR1000"], "has_oracle": True,
        "irreversible": False, "shared_writes": False,
        "truth_n_units": 1, "truth_coupling": 0.0, "truth_horizon_unknown": False,
    }

    fallos = []
    for nombre in sorted(REGISTRY):
        view = CorpusView(task_id="t", documents=docs, unit_ids=list(docs),
                          relevant_units=["u0"])
        surface = ToolSurface(view=view, hybrid=LexicalRetriever(),
                              semantic=LexicalRetriever(), lexical=LexicalRetriever(),
                              variant="basic", budget_tokens=40_000)
        try:
            resultado = REGISTRY[nombre](_Cliente(), surface, tarea)
            if not hasattr(resultado, "answer"):
                fallos.append(f"{nombre}: no devolvio un Result")
        except Infeasible:
            # `Infeasible` NO ES UNA EXPLOSION: es un resultado. El brazo dice que su
            # mecanismo no puede correr sobre esta tarea, el runner lo asienta como fila
            # infactible, y ninguna estadistica lo puntua. `direct` lo levanta cuando el
            # material no entra en el presupuesto y `graph_traverse` cuando la caminata no
            # alcanza ninguna unidad — y este cliente de mentira no produce entidades, asi
            # que aca lo levanta siempre.
            #
            #     Contar la infactibilidad como falla borraria justamente la distincion que
            #     este banco defiende en todos lados: «no pudo» no es «contesto mal».
            pass
        except Exception as exc:  # noqa: BLE001 — el punto es atrapar CUALQUIER cosa
            fallos.append(f"{nombre}: {type(exc).__name__}: {exc}")

    ok &= check(f"los {len(REGISTRY)} del registro corren sin explotar" +
                (f" — FALLAN: {fallos}" if fallos else ""), not fallos)
    ok &= check("y estan TODOS, incluidos los retirados: un brazo que no se corre igual se "
                "replaya, y un replay sobre codigo roto falla igual",
                set(REGISTRY) >= RETIRED)
    return ok


def check_no_factor_is_unreachable(ok: bool) -> bool:
    """S59: todo factor de la superficie tiene camino desde el runner hasta el modelo.

    TRES VECES EN UN DIA APARECIO ESTE DEFECTO, y siempre con la misma forma: un factor
    implementado, con test propio, que **no se podia encender**.

      offer_board / terse_tools   `_run_tool_loop` llamaba a `specs_for` sin pasarlos, asi
                                  que `offer_board=True` habria corrido entero y medido
                                  CERO — la tool nunca aparece en la lista que el modelo ve
      compact_material            el runner no lo pasaba a la superficie: no habia forma de
                                  encenderlo desde una corrida
      terse/board en sub-agentes  `_sub_surface` de `handoff` no los propagaba, asi que
                                  adentro de un sub-agente no existian

    Un factor inalcanzable no falla: **corre y mide su ausencia**, y el resultado se lee
    igual que un efecto nulo medido. Por eso la guarda es estructural y no un test por
    factor: un factor nuevo queda cubierto sin que nadie se acuerde de agregarlo.
    """
    import inspect

    from app.runner import Runner
    from app.tools import ToolSurface

    print()
    print("--- 59. ningun factor queda inalcanzable ---")

    booleanos = {
        n for n, f in ToolSurface.__dataclass_fields__.items()
        if f.type in ("bool", "bool | None")
    }
    src = inspect.getsource(Runner.surface_for)
    huerfanos = sorted(c for c in booleanos if f"{c}=" not in src)
    ok &= check(f"los {len(booleanos)} factores booleanos llegan del runner" +
                (f" — NO LLEGAN: {huerfanos}" if huerfanos else ""), not huerfanos)

    # Y los que gobiernan la DECLARACION de tools tienen que llegar al unico sitio que la
    # manda. Un factor que llega a la superficie y no a `specs_for` sigue siendo inerte.
    loop = inspect.getsource(_paradigms_loop())
    for factor in ("terse", "offer_board", "offer_read_all"):
        ok &= check(f"`{factor}` viaja hasta la declaracion de tools", factor in loop)

    # La copia por alcance no puede perder ninguno: `scoped` usa `replace`, que los lleva
    # todos, y este check impide que alguien lo vuelva a escribir campo por campo.
    scoped = inspect.getsource(ToolSurface.scoped)
    ok &= check("`scoped` copia la superficie entera con `replace`, no campo por campo — "
                "un olvido en una copia a mano es invisible", "replace(" in scoped)
    return ok


def _paradigms_loop():
    from app.paradigms import _run_tool_loop
    return _run_tool_loop


def check_mixed_model_execution_is_measurable(ok: bool) -> bool:
    """S60: una ejecucion que usa DOS modelos tiene que poder convertirse a plata.

    LA PREGUNTA DEL AUTOR (2026-08-29): «tiene sentido cuando se combinan dos LLMs, barato
    y caro, en la misma ejecucion... el costo ahi es importante porque los tokens no valen
    lo mismo». Es correcto y el banco no lo soportaba: `cost_tokens` es UN entero, y un
    token de `terra` cuesta **10x** uno de `luna` en entrada y 10x en salida — mas el
    escalon de contexto largo, que a partir de 272k duplica la entrada de los dos.

    Sumarlos en un entero produce un numero que no se puede convertir a plata **ni
    comparar con nada**. Por eso `Usage.by_model` y `Row.tokens_by_model`.

    VACIO SIGNIFICA UN SOLO MODELO, que es el regimen medido hasta hoy — no se rellena con
    un nombre por defecto, porque «no ruteado» y «ruteado a uno solo» son cosas distintas y
    un default las confundiria.
    """
    from app.llm import Usage
    from app.runner import Row

    print()
    print("--- 60. una ejecucion con dos modelos se puede cobrar ---")

    u = Usage()
    ok &= check("sin rutear, el desglose esta VACIO — distinto de {modelo: 0}", not u.by_model)

    u.charge("gpt-5.6-luna", 1000, 50)
    u.charge("gpt-5.6-luna", 500, 20)
    otro = Usage()
    otro.charge("gpt-5.6-terra", 2000, 300)
    u.merge(otro)
    ok &= check("acumula por modelo, y `merge` no los funde",
                u.by_model["gpt-5.6-luna"] == {"prompt": 1500, "completion": 70, "calls": 2}
                and u.by_model["gpt-5.6-terra"]["prompt"] == 2000)

    # LA PRUEBA QUE IMPORTA: con el desglose la plata se puede calcular, sin el no.
    precios = {"gpt-5.6-luna": (0.20, 1.20), "gpt-5.6-terra": (2.00, 12.00)}
    plata = sum(
        (c["prompt"] * precios[m][0] + c["completion"] * precios[m][1]) / 1_000_000
        for m, c in u.by_model.items()
    )
    total_tokens = sum(c["prompt"] + c["completion"] for c in u.by_model.values())
    plata_ingenua = (total_tokens * precios["gpt-5.6-luna"][0]) / 1_000_000
    ok &= check(f"la plata real ({plata:.6f}) no es la que daria tratar todo como el "
                f"barato ({plata_ingenua:.6f}) — {plata / plata_ingenua:.1f}x",
                plata > plata_ingenua * 3)
    ok &= check("y la fila lo lleva, o el desglose muere en el proceso",
                "tokens_by_model" in Row.__dataclass_fields__)
    return ok


def check_two_kinds_of_reading(ok: bool) -> bool:
    """§54: la lectura ESTRUCTURAL y la ELECTA se cuentan aparte (auditoria C-1).

    `read_one` no pasa por `dispatch`: no cuenta como llamada, no descuenta presupuesto y
    no dispara `stop_on_barren`. Eso esta bien —ninguna de las tres gobierna una linea de
    codigo— pero hasta hoy tampoco dejaba RASTRO, y ocho de trece paradigmas leen el corpus
    por ahi. Una lectura invisible se lee igual que una lectura que no ocurrio, asi que
    `units_read` no significaba lo mismo entre paradigmas y ningun promedio lo denunciaba.

    LA PRUEBA ES QUE SEAN DOS Y NO SE SUMEN. Si esto se «arreglara» sumando la lectura
    estructural a `units_read`, todos los numeros publicados se moverian y la distincion
    se perderia — que es el escenario que este test existe para impedir.
    """
    from app.retrieval import CorpusView, LexicalRetriever
    from app.tools import ToolSurface

    print()
    print("--- 54. dos clases de lectura, contadas aparte ---")

    docs = {f"u{i}": f"unidad {i} con texto suficiente" for i in range(5)}
    view = CorpusView(task_id="t", documents=docs, unit_ids=list(docs),
                      relevant_units=["u1", "u2"])
    s = ToolSurface(view=view, hybrid=LexicalRetriever(), semantic=LexicalRetriever(),
                    lexical=LexicalRetriever(), variant="basic", budget_tokens=40_000)

    s.read_one("u0")
    s.read_one("u1")
    u = s.usage()
    ok &= check("`read_one` deja rastro: la lectura estructural se cuenta",
                u["units_read_structural"] == 2)
    ok &= check("y NO toca `units_read`, que sigue siendo lo que el modelo eligio — si lo "
                "tocara, todo numero publicado se moveria", u["units_read"] == 0)
    ok &= check("tampoco cuenta como llamada ni entra a la secuencia: no fue una decision "
                "del modelo", not u["calls"] and not u["sequence"])

    s.dispatch("read", {"unit_ids": "u1, u3"})
    u = s.usage()
    ok &= check("la lectura por tool sigue contando donde siempre", u["units_read"] == 2)
    ok &= check("la union NO es la suma: u1 se leyo de las dos formas y se cuenta UNA vez "
                "— sumarlas inventaria lectura", u["units_read_any"] == 3)
    # u2 es PORTADORA y solo la ve la lectura estructural — que es exactamente el caso que
    # subestimaba el recall: `gist_reader` lee todas las unidades desde su codigo y su
    # `relevant_units_read` no las contaba.
    s.read_one("u2")
    u = s.usage()
    ok &= check("el recall ELECTO no ve la unidad portadora que solo leyo el codigo",
                u["relevant_units_read"] == 1)
    ok &= check("y el recall sobre la UNION si la ve — es el unico comparable entre un "
                "paradigma que lee por codigo y uno que lee por tool",
                u["relevant_units_read_any"] == 2)

    # --- C-2: la dosis de brazo. El brazo sustituye `hybrid`, o sea la tool `search`;
    # `keyword_search` y `semantic_search` son CONSTANTES entre brazos. Asi que la
    # exposicion al tratamiento no es igual para todos y hay que poder leerla.
    from app.metrics import arm_dose
    ok &= check("sin ninguna busqueda la dosis es None, no 0,0: un paradigma que no busca "
                "no recibio tratamiento cero, no recibio tratamiento",
                arm_dose({"calls": {"read": 3}}) is None)
    ok &= check("buscando solo por `search` la dosis es 1,0",
                arm_dose({"calls": {"search": 4}}) == 1.0)
    ok &= check("buscando solo por `keyword_search` la dosis es 0,0 — y ESO si es cero "
                "medido: busco y nunca por el brazo",
                arm_dose({"calls": {"keyword_search": 4}}) == 0.0)
    ok &= check("y mezclado, es la fraccion que pasa por el brazo",
                arm_dose({"calls": {"search": 1, "keyword_search": 3}}) == 0.25)
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

    # UN 429 NO PUEDE BLOQUEAR SU PROPIO REINTENTO (2026-08-29). Toda fila se appendea al
    # `.jsonl`, incluidas las de infraestructura, y `existing_keys` las contaba como hechas:
    # una celda caida por cuota quedaba salteada PARA SIEMPRE en el resume.
    #
    # Lo grave es que el sistema esta construido sobre la promesa contraria —
    # `BENCHMARK.es.md` dice que un error de cuota «debe quedar elegible para completar el
    # trial faltante»— y `load_rows` ya las excluia de toda estadistica. La fila no puntuaba
    # Y bloqueaba su reintento, en silencio, porque el conteo de celdas seguia dando
    # completo. En una campaña de horas eso no es un caso raro: es como termina con huecos.
    import tempfile as _tmp
    from app.runner import Runner

    class _RunnerFalso:
        """Sólo el metodo bajo prueba: construir un `Runner` real exige corpus y red."""
        def __init__(self, path):
            self._results_path = path
        existing_keys = Runner.existing_keys

    def _escribir(filas):
        f = Path(_tmp.mkdtemp()) / "r.jsonl"
        f.write_text(chr(10).join(json.dumps(x) for x in filas), encoding="utf-8")
        return f

    buena = {"task_id": "t1", "paradigm": "react", "trial": 0}
    caida = {"task_id": "t2", "paradigm": "react", "trial": 0, "infra_error": True}
    fallada = {"task_id": "t3", "paradigm": "react", "trial": 0,
               "error": "ToolFailure: el paradigma se equivoco"}

    claves = _RunnerFalso(_escribir([buena, caida, fallada])).existing_keys()
    ok &= check("una celda medida cuenta como hecha",
                ("t1", "react", 0) in claves)
    ok &= check("una celda caida por INFRAESTRUCTURA no cuenta: tiene que poder "
                "reintentarse, o un 429 la pierde para siempre",
                ("t2", "react", 0) not in claves)
    ok &= check("y una que FALLO DE VERDAD si cuenta — el paradigma se equivoco y ese "
                "cero es la medicion, no un hueco",
                ("t3", "react", 0) in claves)

    # Al reintentar quedan DOS filas con la misma clave. Aguas abajo tiene que sobrevivir
    # una sola, o la celda pesaria el doble.
    from app.runner import load_rows as _lr
    dos = _escribir([dict(caida, cost_tokens=10, fingerprint="A", region_vocabulary="V",
                          retriever="hybrid", analyzer="v2-stopwords"),
                     dict(caida, infra_error=False, cost_tokens=20, fingerprint="A",
                          region_vocabulary="V", retriever="hybrid",
                          analyzer="v2-stopwords")])
    ok &= check("tras el reintento el archivo tiene las dos filas y el analisis ve UNA: "
                "`load_rows` excluye las de infraestructura por defecto",
                len(_lr(dos)) == 1 and _lr(dos)[0]["cost_tokens"] == 20)


    # EL EFECTO DE BRAZO SE ESTRATIFICA POR DOSIS, O NO SE PROMEDIA (`AR-5`, 2026-08-29).
    #
    # `arm_dose` existia y la usaba UN analizador. Tener la funcion no es tener la guarda:
    # mientras nada la exija, la comparacion por defecto sigue siendo el promedio. Y la
    # dispersion medida sobre el registro es enorme — `react` 70,1%, `dag_strategy` 16,3%,
    # `gist_reader` 0% — asi que un promedio no estima el efecto del brazo: estima el
    # efecto mezclado con la composicion del plantel, y cambiar el plantel lo mueve sin que
    # el brazo cambie.
    from app.metrics import arm_effect

    def _fila(par, tarea, util, search, otras, **extra):
        return {"paradigm": par, "task_id": tarea, "trial": 0, "utility": util,
                "tool_usage": {"calls": {"search": search, "keyword_search": otras}},
                **extra}

    # Dosis parejas: 3/4 y 4/5 son 75% y 80%, cinco puntos de diferencia.
    base = [_fila("react", "t1", 0.0, 3, 1), _fila("rewoo", "t1", 0.0, 4, 1)]
    trat = [_fila("react", "t1", 1.0, 3, 1), _fila("rewoo", "t1", 0.5, 4, 1)]
    efecto = arm_effect(base, trat)
    ok &= check("con dosis parejas el efecto se promedia",
                abs(efecto.pooled() - 0.75) < 1e-9)
    ok &= check("y cada paradigma lleva su dosis al lado, no un promedio anonimo",
                abs(efecto.per_paradigm["react"][1] - 0.75) < 1e-9)

    # El caso MEDIDO: `react` 70% contra `dag_strategy` 16%. 54 puntos de dispersion.
    base = [_fila("react", "t1", 0.0, 7, 3), _fila("dag_strategy", "t1", 0.0, 16, 84)]
    trat = [_fila("react", "t1", 1.0, 7, 3), _fila("dag_strategy", "t1", 1.0, 16, 84)]
    efecto = arm_effect(base, trat)
    try:
        efecto.pooled()
        ok &= check("promediar sobre dosis dispares levanta", False)
    except ValueError as exc:
        ok &= check("promediar sobre dosis dispares LEVANTA, no avisa al lado: un aviso "
                    "junto a un promedio invalido publica el promedio",
                    "dispersion" in str(exc) and "react" in str(exc))
    ok &= check("y el estrato sigue disponible aunque el promedio se niegue",
                len(efecto.treated) == 2)

    # `gist_reader` nunca busca: su delta no es evidencia sobre el brazo.
    base = [_fila("react", "t1", 0.0, 4, 1), _fila("gist_reader", "t1", 0.0, 0, 0)]
    trat = [_fila("react", "t1", 1.0, 4, 1), _fila("gist_reader", "t1", 1.0, 0, 0)]
    efecto = arm_effect(base, trat)
    ok &= check("un paradigma que NUNCA busca queda fuera de los tratados: no recibio "
                "tratamiento cero, no recibio tratamiento",
                efecto.untreated == ("gist_reader",))
    ok &= check("y el promedio se calcula solo sobre los tratados — meterlo diluiria el "
                "efecto con una celda que el brazo no toco",
                abs(efecto.pooled() - 1.0) < 1e-9)

    # Buscar SOLO por las tools que el brazo no sustituye tambien es sin tratar.
    base = [_fila("dag_strategy", "t1", 0.0, 0, 9)]
    trat = [_fila("dag_strategy", "t1", 1.0, 0, 9)]
    ok &= check("buscar solo por las tools constantes entre brazos tampoco es tratamiento",
                arm_effect(base, trat).untreated == ("dag_strategy",))
    try:
        arm_effect(base, trat).pooled()
        ok &= check("sin ningun tratado, promediar levanta", False)
    except ValueError as exc:
        ok &= check("sin ningun tratado no hay efecto que promediar, y lo dice",
                    "Ningun paradigma recibio tratamiento" in str(exc))

    # Una celda podada no entra: comparar por posicion desalinearia las listas.
    base = [_fila("direct", "t1", 0.0, 0, 0, infeasible=True),
            _fila("react", "t1", 0.0, 4, 1)]
    trat = [_fila("direct", "t1", 0.0, 0, 0, infeasible=True),
            _fila("react", "t1", 1.0, 4, 1)]
    ok &= check("las celdas infactibles no entran a la comparacion: no ejecutaron, asi "
                "que no pueden mostrar efecto de brazo",
                set(arm_effect(base, trat).per_paradigm) == {"react"})


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

    # LA CUARTA GUARDA DE MEZCLA — el analizador lexico — y su falso positivo.
    #
    # Que dos analizadores no se promedien esta bien y se prueba abajo. Lo que estaba mal
    # es a QUIEN le exigia declararlo: una fila podada por aritmetica no ejecuta, no busca
    # y no tokeniza, asi que no tiene analizador que declarar. La guarda la leia como «del
    # regimen viejo» y levantaba. Con dos `direct` infactibles —lo normal en cualquier
    # corrida— volteaba el archivo entero, y el mensaje hablaba de tokenizadores.
    con_analizador = dict(base, analyzer="v2-stopwords")
    ok &= check("un archivo de un solo analizador se lee sin quejarse",
                len(load_rows(escribir([con_analizador,
                                        dict(con_analizador, task_id="u")]))) == 2)
    ok &= check("una fila INFACTIBLE sin analizador no cuenta como mezcla: no ejecuto, "
                "asi que no tiene tokenizador que declarar",
                len(load_rows(escribir([
                    con_analizador,
                    dict(base, task_id="u", infeasible=True),
                ]))) == 2)
    try:
        load_rows(escribir([con_analizador,
                            dict(con_analizador, task_id="u",
                                 analyzer="v1-longitud")]))
        ok &= check("mezclar analizadores levanta", False)
    except ValueError as exc:
        ok &= check("mezclar analizadores levanta — el tokenizador decide QUE encuentra "
                    "BM25 y no deja rastro en ningun otro campo",
                    "analizadores lexicos" in str(exc))
    try:
        load_rows(escribir([con_analizador, dict(base, task_id="u")]))
        ok &= check("una fila EJECUTADA sin analizador sigue levantando", False)
    except ValueError as exc:
        ok &= check("una fila EJECUTADA sin analizador sigue levantando: esa si es del "
                    "regimen viejo, y es lo que la guarda existe para atrapar",
                    "analizadores lexicos" in str(exc))

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

    `max` no es la unica funcion monotona: es la composicion punto a punto menos restrictiva
    entre las que dominan cada fuente. Con `min` o un promedio, una fuente podria ablandar el
    resultado. Enunciado completo en `EL_DIAL.es.md`.
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

    fuentes = list(product(Assurance, repeat=3))
    contraejemplos = []
    for valores in fuentes:
        minimo_admisible = max(valores)
        for candidato in Assurance:
            domina_cada_fuente = all(candidato >= valor for valor in valores)
            if domina_cada_fuente and candidato < minimo_admisible:
                contraejemplos.append((valores, candidato))
    ok &= check("el maximo es el MENOR nivel que domina cada fuente, no la unica "
                "funcion monotona", not contraejemplos,
                f"{len(fuentes)} ternas exhaustivas")

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


def check_stochasticity_confinement(ok: bool) -> bool:
    """S47b: la Proposicion 4 sobre brazos REALES del catalogo, y la 5 en instancia finita.

    QUE PRUEBA. Dos sensores falsos que responden DISTINTO —otro numero, y otra unidad
    cuando se les deja elegir— corren cada brazo sobre el mismo material. La trayectoria
    es la secuencia de nodos que la superficie registra: cada lectura estructural
    (`read_one`, la hace el codigo) y cada llamada del modelo (`dispatch`, con sus
    argumentos). Un brazo con `d(T)=0` tiene que recorrer los mismos nodos con los dos
    sensores y puede contestar distinto: V_T=0 con V_Y>0. Un brazo que delega la lectura
    al modelo diverge cuando el modelo elige otra unidad. Y `pointer_chase`, al que §6.1.4
    del paper le saco el ancla al modelo, recorre los mismos nodos: la intervencion del
    paper queda en la suite, no solo en la prosa.

    QUE NO PRUEBA. Nada del stack de servicio real ni de cuanto V_T hay en la campana; eso
    es §8.2 del paper. Es la instancia operativa de la proposicion, no su medicion.

    ANTES ERA UN JUGUETE: comparaba tuplas de strings escritas a mano y no importaba nada
    de `app`. El paper lo citaba como «instancia operativa», y no lo era.
    """
    import json
    import tempfile
    from itertools import product

    from app.llm import Usage as _RealUsage
    from app.paradigms import Infeasible, REGISTRY
    from app.retrieval import CorpusView, LexicalRetriever
    from app.tools import ToolSurface

    print("\n--- 47b. confinamiento de estocasticidad, sobre el catalogo ---")

    _tmp = Path(tempfile.mkdtemp(prefix="mapo-test-"))

    class _Completion:
        def __init__(self, texto, tool_calls=None):
            self.text, self.usage = texto, _RealUsage()
            self.tool_calls = tool_calls or []
            self.from_cache, self.model_version = False, ""

    class _Sensor:
        """Responde `respuesta`; si se le ofrecen tools y todavia no leyo, pide `unidad`."""
        fingerprint = "fake|t=0"
        cache_root = _tmp
        spent = _RealUsage()

        def __init__(self, respuesta, unidad=None):
            self.respuesta, self.unidad = respuesta, unidad

        def complete(self, messages, **kw):
            ya_leyo = any(m.get("role") == "tool" for m in messages)
            if kw.get("tools") and self.unidad and not ya_leyo:
                return _Completion("", [{"id": "c1", "type": "function", "function": {
                    "name": "read", "arguments": json.dumps({"unit_ids": self.unidad})}}])
            r = self.respuesta
            return _Completion(
                '{"sub_questions": [{"id": "sq_001", "question": "q", "depends_on": []}], '
                '"steps": [], "plan": [], "read": [], "entities": [], "relations": [], '
                f'"status": "complete", "partial": "{r}", "answer": "{r}", '
                '"dispatch": "una sub-pregunta", "done": false}'
                + chr(10) + f"ANSWER: {r}")

    docs = {f"u{i}": f"unidad {i}: Marta Arrieta, account AR100{i}." for i in range(6)}
    tarea = {
        "task_id": "t", "question": "What is the account for Marta Arrieta?",
        "cell": "C1_single_verifiable", "budget_tokens": 40_000,
        "unit_ids": list(docs), "oracle": ["AR1000"], "has_oracle": True,
        "irreversible": False, "shared_writes": False,
        "truth_n_units": 1, "truth_coupling": 0.0, "truth_horizon_unknown": False,
    }

    def trayectoria(nombre, sensor):
        """(secuencia de nodos, respuesta). La secuencia se toma en la SUPERFICIE, que es
        el unico lugar por donde pasa todo lo que un brazo lee o llama."""
        view = CorpusView(task_id="t", documents=docs, unit_ids=list(docs),
                          relevant_units=["u0"])
        surface = ToolSurface(view=view, hybrid=LexicalRetriever(),
                              semantic=LexicalRetriever(), lexical=LexicalRetriever(),
                              variant="basic", budget_tokens=40_000)
        nodos = []
        despacho, lectura = surface.dispatch, surface.read_one

        def dispatch(name, args):
            nodos.append(("tool", name, json.dumps(args, sort_keys=True)))
            return despacho(name, args)

        def read_one(uid):
            nodos.append(("read", uid))
            return lectura(uid)

        surface.dispatch, surface.read_one = dispatch, read_one
        try:
            respuesta = REGISTRY[nombre](sensor, surface, tarea).answer
        except Infeasible:
            return ("INFEASIBLE",), None
        # La tupla se arma DESPUES de correr: antes de la llamada esta vacia.
        return tuple(nodos), respuesta

    A, B = _Sensor("AR1000", "u0"), _Sensor("AR2000", "u3")

    # 1. d(T)=0. El codigo fija QUE se lee y CUANDO; el modelo solo pone contenido.
    FIJOS = ("direct", "cot", "map_reduce", "extract_compute", "streaming_scan")
    rompen, mudos = [], []
    for nombre in FIJOS:
        t_a, y_a = trayectoria(nombre, A)
        t_b, y_b = trayectoria(nombre, B)
        if not t_a or t_a != t_b:
            rompen.append(nombre)
        if y_a == y_b:
            mudos.append(nombre)
    ok &= check(f"d(T)=0 => V_T=0: {len(FIJOS)} brazos de flujo fijado por codigo recorren los "
                "mismos nodos bajo dos sensores que responden distinto"
                + (f" — ROMPEN: {rompen}" if rompen else ""), not rompen)
    ok &= check("y V_T=0 no fuerza V_Y=0: los mismos nodos, otra respuesta, en los cinco"
                + (f" — MUDOS: {mudos}" if mudos else ""), not mudos)

    # 2. Delegar la lectura abre el canal: otra eleccion del modelo, otra trayectoria.
    DELEGAN = ("react", "reflection", "dag_strategy")
    iguales = [n for n in DELEGAN if trayectoria(n, A)[0] == trayectoria(n, B)[0]]
    ok &= check("delegar la lectura al modelo abre el canal: react, reflection y dag_strategy "
                "divergen cuando el sensor elige otra unidad"
                + (f" — NO DIVERGEN: {iguales}" if iguales else ""), not iguales)

    # 3. El reciproco que la proposicion NO afirma: d>0 con la rama coincidiendo de hecho.
    t_a, _ = trayectoria("react", A)
    t_a2, y_a2 = trayectoria("react", _Sensor("AR2000", "u0"))
    ok &= check("d(T)>0 no fuerza V_T>0: `react` con la misma eleccion y otra respuesta recorre "
                "los mismos nodos", t_a == t_a2 and y_a2 == "AR2000")

    # 4. La intervencion de §6.1.4: el ancla la resuelve el codigo, no el modelo.
    t_a, _ = trayectoria("pointer_chase", A)
    t_b, _ = trayectoria("pointer_chase", B)
    herramientas = [n[1] for n in t_a if n[0] == "tool"]
    ok &= check("`pointer_chase` resuelve el ancla por codigo (paper §6.1.4): misma busqueda y "
                "misma lectura bajo los dos sensores",
                t_a == t_b and herramientas[:2] == ["search", "read"],
                f"nodos del modelo: {herramientas}")

    # 5. La premisa de la proposicion, sobre el banco: el stack no-modelo es determinista.
    inestables = [n for n in sorted(REGISTRY)
                  if trayectoria(n, A)[0] != trayectoria(n, A)[0]]
    ok &= check(f"el stack del banco es determinista: el mismo sensor dos veces da la misma "
                f"trayectoria en los {len(REGISTRY)} brazos del registro"
                + (f" — INESTABLES: {inestables}" if inestables else ""), not inestables)

    # 6. Proposicion 5, instancia finita ABSTRACTA: no hay brazo que ejecutar, es la clave.
    emisiones = ("alpha", "beta", "gamma")

    def desacuerdo(valores) -> float:
        pares = list(product(valores, repeat=2))
        return sum(a != b for a, b in pares) / len(pares)

    computadas = ["dag" if k[0] > 8 and k[1] else "react"
                  for k in [(12, True, False) for _ in emisiones]]
    elicitadas = ["dag" if e == "alpha" else "react" for e in emisiones]
    ok &= check("Prop. 5, instancia finita: una clave COMPUTED conserva la decision respecto "
                "de Z", desacuerdo(computadas) == 0.0)
    ok &= check("y una clave ELICITED puede reabrir el canal hacia la politica",
                desacuerdo(elicitadas) > 0.0)
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

    # AUSENTE NO ES CERO, en la proyeccion. Este aserto CAMBIO, y el cambio es la
    # historia: fijaba que `dag_strategy` no proyectaba tokens y por eso su cota de plata
    # se declaraba «no evaluada». Era correcto — y estaba fijando un DEFECTO, no una
    # propiedad. `X-5h` lleno las tres proyecciones que faltaban, asi que hoy TODOS los
    # paradigmas se pueden cotizar.
    #
    # El mecanismo tiene que seguir probado igual: un paradigma nuevo puede nacer sin
    # proyeccion, y entonces cobrarle cero lo declararia admisible en el modelo caro por
    # no saber cuanto gasta. Se prueba sobre la funcion, no sobre un brazo que la dispare.
    from app.feasibility import check as _feasibility_check
    sin_proyeccion = [
        p for p in ("direct", "react", "map_reduce", "dag_strategy", "rewoo",
                    "gist_reader", "reflection", "handoff")
        if _feasibility_check(p, docs, barato).projected_tokens is None
    ]
    ok &= check("hoy TODOS los paradigmas proyectan: no queda ninguno sin cotizar",
                not sin_proyeccion)

    class _SinProyectar:
        feasible, reason, axis = True, "", ""
        projected_calls, projected_tokens = 3, None

    import app.feasibility as _feas
    _orig = _feas.check
    try:
        _feas.check = lambda *a, **k: _SinProyectar()
        v = _feas.check_pair(DEEP, "inventado", docs, barato)
        ok &= check("y si alguno naciera sin proyeccion, NO se cobra gratis: la cota de "
                    "plata se declara no evaluada en vez de aprobar por no saber",
                    v.axis == "money_unevaluated" and v.projected_tokens is None
                    and v.feasible)
    finally:
        _feas.check = _orig

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


def check_surfacing_is_recorded_apart_from_reading(ok: bool) -> bool:
    """§80: lo que la recuperacion SACO A LA SUPERFICIE se registra aparte de lo leido.

    ERAN DOS PREGUNTAS Y LA FILA CONTESTABA UNA. `surfaced` existia desde siempre —lo usan
    los contadores de agotamiento del retriever— y **no salia en la fila**. Asi que el
    registro podia decir cuantas unidades se LEYERON pero no cuales la busqueda habia
    llegado a ofrecer, y no son lo mismo: un recuperador puede traer la unidad correcta y
    que el paradigma no la lea.

    LO QUE ESO IMPEDIA MEDIR, y es concreto. `HydeFused` es una rama **exploratoria**: su
    trabajo no es rankear mejor, es **ensanchar**. Medida por utilidad da nulo —43 de 43
    celdas identicas— y por lectura tambien —`units_read` igual en las 43—. Pero ninguna de
    las dos es su vara:

        la pregunta correcta para una rama exploratoria no es «¿gana?»
        sino «¿trae lo que la base no trae?», y eso vive en `surfaced`.

    POR QUE SE GUARDAN LOS IDS Y NO SOLO EL CONTEO: la comparacion que decide es de
    CONJUNTOS entre brazos —lo que trae HyDE menos lo que trae la base— y **dos conjuntos
    disjuntos pueden tener el mismo tamano**. Un conteo no distingue «trajo otras cuatro»
    de «trajo las mismas cuatro».
    """
    from app.retrieval import CorpusView, LexicalRetriever
    from app.tools import ToolSurface

    print("\n--- 80. surgir no es leer, y se registran por separado ---")

    docs = {f"u{i}": f"memo {i}: Marta Arrieta, director, cuenta AR{i:07d}"
            for i in range(6)}
    v = CorpusView(task_id="t", documents=docs, unit_ids=list(docs),
                   relevant_units=["u1", "u3"])
    s = ToolSurface(view=v, hybrid=LexicalRetriever(), semantic=LexicalRetriever(),
                    lexical=LexicalRetriever(), variant="basic", budget_tokens=50_000)

    s.dispatch("keyword_search", {"query": "director", "limit": 4})
    u = s.usage()
    ok &= check(f"una busqueda deja rastro de lo que SURGIO ({u['surfaced_units']} unidades)",
                u["surfaced_units"] == 4)
    ok &= check("y de cuantas de esas eran relevantes — el recall del RECUPERADOR",
                u["surfaced_relevant"] == 2)
    ok &= check("surgir NO es leer: la misma busqueda deja `units_read` en cero",
                u["units_read"] == 0)
    ok &= check("los IDS se guardan, no solo el conteo — dos conjuntos DISJUNTOS pueden "
                "tener el mismo tamano, y la comparacion entre brazos es de conjuntos",
                u["surfaced_ids"] == ["u0", "u1", "u2", "u3"])

    s.dispatch("read", {"unit_ids": "u1"})
    u = s.usage()
    ok &= check(f"y los dos recalls se separan: recuperacion {u['surfaced_relevant']} "
                f"contra lectura {u['relevant_units_read']} — un brazo puede tener 100% de "
                f"uno y 50% del otro, y hasta hoy se veian iguales desde la fila",
                u["surfaced_relevant"] == 2 and u["relevant_units_read"] == 1)

    # ES DE LA TAREA, NO DEL SUB-AGENTE. `surfaced` ya se compartia por referencia —es lo
    # que arreglo la v2 de la superficie— y el reporte tiene que heredarlo o `handoff` y
    # `supervisor` reportarian el ensanchamiento de su ultimo sub-agente.
    sub = s.scoped(["u0", "u1"])
    sub.dispatch("keyword_search", {"query": "marta", "limit": 2})
    ok &= check("lo que surge adentro de un sub-agente cuenta para la TAREA",
                s.usage()["surfaced_units"] >= u["surfaced_units"]
                and sub.surfaced is s.surfaced)
    return ok


def check_hyde_branch_is_separable(ok: bool) -> bool:
    """§79: la rama HyDE se puede medir SIN fusionar, que es la pregunta previa.

    `HydeFused` esta medido y es INERTE. Sobre `gold_h1`, **43 de 43 celdas con utilidad
    identica**, y el mecanismo del nulo esta a la vista: `units_read` es igual en las 43, o
    sea que **la rama nunca cambio que unidades se leyeron**. Sobre `gold_p18`, 115 celdas
    pareadas, `+0,017` a 1,06x el costo, con 13 mejoras y 6 empeoramientos — lo que da el
    azar.

    Y SU PROPIO DOCSTRING EXPLICA POR QUE, sin darse cuenta: defiende la fusion como
    seguridad —«hace que ese error tenga que VENCER al ranking base en vez de
    reemplazarlo»—. Es cierto, y tiene un costo que no estaba medido:

        la misma fusion que la protege de equivocarse es la que la deja muda.
        Con RRF contra un ranking base fuerte, la rama nunca gana.

    `hyde_only` contesta la pregunta PREVIA a discutir como exponerla: **¿la rama tiene
    senal propia?** Si reemplazando el ranking tampoco le gana nunca a `hybrid`, no hay nada
    que fusionar mejor ni nada que exponer como herramienta.

    NO ES UN CANDIDATO A PRODUCCION, y este chequeo lo fija: reemplazar el ranking es
    exactamente lo peligroso que la fusion evita. Es un instrumento de diagnostico.
    """
    import inspect

    from app.embeddings import EmbeddingClient
    from app.retrieval import (MODEL_CALLING_ARMS, HydeFused, HydeOnly, build_arms)

    print("\n--- 79. la rama HyDE se puede medir sin fusionar ---")

    ok &= check("`hyde_only` HEREDA de `hybrid_hyde`: misma generacion, misma cache por "
                "consulta, mismo costo — lo unico que cambia es la fusion, que es la "
                "variable bajo prueba",
                issubclass(HydeOnly, HydeFused))
    fuente = inspect.getsource(HydeOnly.rank)
    ok &= check("y su `rank` NO fusiona: el ranking sale de la hipotetica y nada mas",
                "fused" not in fuente and "RRF_K" not in fuente)
    ok &= check("una generacion vacia cae al brazo base, no a un ranking vacio — sin "
                "fusion no hay red debajo, asi que importa mas que en el fusionado",
                "self._base.rank(" in fuente)

    ok &= check("esta declarado como brazo que LLAMA AL MODELO: su costo y su piso de "
                "ruido propio no se pueden esconder",
                "hyde_only" in MODEL_CALLING_ARMS)

    # LLEGA AL CATALOGO, y solo con cliente. La misma guarda de §59, un nivel mas abajo:
    # un brazo que no se construye no se puede correr, y su ausencia se leeria como un
    # efecto nulo medido.
    class _Emb:
        def embed(self, textos):  # noqa: D401
            return [[0.0] for _ in textos]

    sin = build_arms(embedder=_Emb())
    ok &= check("sin cliente NO existe — no se puede generar una hipotetica sin modelo",
                "hyde_only" not in sin)

    d = HydeOnly.describe(HydeOnly.__new__(HydeOnly)) if False else None
    ok &= check("`describe()` declara `fusion: None`, o las dos filas se leerian iguales",
                "d[\"fusion\"] = None" in inspect.getsource(HydeOnly.describe))
    return ok


def check_gaps_that_nobody_can_close(ok: bool) -> bool:
    """§78: un hueco que nadie puede cerrar no es un hueco — y el literal es una creencia.

    EL OBJETIVO DEL PRODUCTO es decidir con creencias y, si falta una variable, ir a
    buscarla. Auditado contra el codigo, la superficie de «que puede faltar» tenia DOS
    elementos y la sonda podia establecer UNO.

    `horizon_unknown` NO ES UN FEATURE, y hay cinco razones independientes:

      1. ninguna regla lo requiere — `rules.py` lo ASIENTA y nadie lo lee
      2. no entra en el vocabulario de region, ni en el anterior ni en el actual
      3. la sonda no lo mide: `probe.py` establece `coupling` y nada mas
      4. es CONSTANTE en el registro: `False` en las **3.884** filas que lo llevan
      5. y el docstring de `Row` afirmaba que esta en `True` en las 78 tareas — la unica
         descripcion que existia del eje decia **lo contrario** del registro

    Y NO ES DECORACION INOFENSIVA, que es lo que lo hace importar: un eje `DERIVED` sin
    establecer **acota la confianza y empuja al router al fallback**. Un eje que nadie puede
    llenar hace abstenerse al motor para siempre y sin motivo.

        «no lo se, y puedo averiguarlo»  -> sondear, y decidir despues
        «no lo se, y nadie puede»        -> decidir con lo que hay, o abstenerse por eso

    Son decisiones OPUESTAS y `missing()` las devolvia mezcladas. `FEATURE_SENSOR` las
    separa: declara quien puede establecer cada eje, y `None` es una respuesta valida.

    Y `literal_absent` ES LA CREENCIA QUE FALTABA (EP-4). `measure_question_literal` ya
    existia y su valor ya entraba a la region, pero **no estaba en el vocabulario de
    proposiciones**: ninguna regla podia razonar sobre el. Tener la pieza no es tener el
    ciclo. Es `COMPUTED` —contencion de una cadena conocida contra el material, sin modelo
    en el medio— asi que satisface el piso mas alto que cualquier regla puede pedir.
    """
    from app.assurance import PROFILES, Assurance
    from app.beliefs import Provenance
    from app.features import (DERIVED_FEATURES, FEATURE_SENSOR, Features)
    from app.rules import sense

    print("\n--- 78. un hueco que nadie puede cerrar no es un hueco ---")

    f = Features(n_units=10, has_oracle=True, irreversible=False, shared_writes=False,
                 budget_tokens=9000)
    ok &= check("todo eje DERIVED declara QUIEN lo puede establecer, `None` incluido",
                set(FEATURE_SENSOR) == set(DERIVED_FEATURES))
    ok &= check(f"lo que falta y SE PUEDE ir a buscar: {f.fillable_gaps()}",
                f.fillable_gaps() == ("coupling",))
    ok &= check(f"lo que falta y NADIE puede cerrar: {f.permanent_gaps()}",
                f.permanent_gaps() == ("horizon_unknown",))
    ok &= check("y `missing()` sigue devolviendo los dos — la distincion se agrega, no "
                "se reemplaza: quien quiera saber que NO esta establecido lo sigue teniendo",
                set(f.missing()) == {"coupling", "horizon_unknown"})
    ok &= check("un eje establecido deja de ser hueco por las dos vias",
                not Features(n_units=1, has_oracle=True, irreversible=False,
                             shared_writes=False, budget_tokens=1, coupling=0.5,
                             horizon_unknown=False).missing())

    # `horizon_unknown` ES CONSTANTE EN EL REGISTRO. Se comprueba contra el registro real,
    # que es de donde salio la razon para no tratarlo como variable.
    import glob as _glob
    import json as _json
    vistos = set()
    _por_clave: dict[tuple[str, str], set] = {}
    n = 0
    for ruta in _glob.glob("results/**/*_rows.jsonl", recursive=True):
        for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
            if not linea.strip():
                continue
            fila = _json.loads(linea)
            if "phi_horizon_unknown" in fila:
                vistos.add(fila["phi_horizon_unknown"])
                n += 1
                clave = (ruta, fila["task_id"])
                _por_clave.setdefault(clave, set()).add(fila["phi_horizon_unknown"])
    # DEJO DE SER CONSTANTE, y la variacion mide otra cosa que la que este chequeo buscaba.
    # `horizon_unknown` salio `False` en 5.792 filas y `True` en 12 — y esas 12 son UNA tarea
    # (`w1-001-neg`) corrida con la SEGUNDA familia de modelo. El corpus declara `False` para
    # esa tarea. O sea que la variacion no viene del mundo: viene de que el eje se ELICITA del
    # modelo, y dos modelos lo sensan distinto.
    #
    # Lo que se chequea ahora es lo que importa: que la variacion sea ATRIBUIBLE al modelo y no
    # a la tarea. Si un dia dos filas del MISMO modelo sobre la MISMA tarea discreparan, eso si
    # seria un defecto y este chequeo lo levanta.
    if n:
        ok &= check(
            f"la variacion de `horizon_unknown` ({vistos} en {n:,} filas) es entre MODELOS, "
            f"no dentro de uno: un eje elicitado no es una propiedad de la tarea",
            not [k for k, v in _por_clave.items() if len(v) > 1],
        )

    # ── `literal_absent`: la creencia con sensor ──
    tarea = {"question": "x", "unit_ids": ["u1"], "budget_tokens": 9000,
             "has_oracle": True, "oracle": ["x"]}
    politica = PROFILES[Assurance.STANDARD]

    def creencia(base, nombre):
        for b in base.as_dict()["beliefs"]:
            if b["proposition"] == nombre:
                return b
        return None

    b = creencia(sense(tarea, politica, literal="lit_absent"), "literal_absent")
    ok &= check("`literal_absent` se asienta cuando el literal no esta en el alcance",
                b is not None and b["value"] is True)
    ok &= check("y es COMPUTED — aritmetica sobre el material, asi que satisface el piso "
                "mas alto que una regla puede pedir, incluido el de una accion irreversible",
                b["provenance"] == Provenance.COMPUTED.value and b["credence"] == 1.0)
    b2 = creencia(sense(tarea, politica, literal="lit_present"), "literal_absent")
    ok &= check("con el literal presente, la misma creencia se asienta en False",
                b2 is not None and b2["value"] is False)
    ok &= check("y sin literal NO se asienta: una creencia sin evidencia no se inventa en "
                "un valor benigno",
                creencia(sense(tarea, politica), "literal_absent") is None)

    # LLEGA HASTA `sense` O NO EXISTE. La misma guarda que §59 y §76.
    import inspect
    from app.router import Router
    ok &= check("el router la propaga hasta `sense` — una creencia que el router no pasa "
                "es una que ninguna regla puede ver",
                "literal: str | None" in inspect.getsource(Router.plan)
                and "literal=literal" in inspect.getsource(Router.plan))
    return ok


def check_report_does_not_score_placeholders(ok: bool) -> bool:
    """§77: un plan que pide sonda es un DIFERIMIENTO, y no se puntua como decision.

    EL DEFECTO, y es el mas grande que encontro esta sesion porque toca el numero que
    refuto la tesis del producto. `Router.plan()` recibe `coupling` como argumento y el
    `decide()` de `Runner.report` **no se lo pasaba**: quedaba en `None` con credencia 0,
    asi que `coupling_unmeasured` era verdadero SIEMPRE, la regla
    `probe_before_deciding_on_bulk` disparaba, y el plan volvia con `needs_probe`.

    Medido por el camino exacto de `report()`: **23 de 46 tareas — la mitad justa — en los
    cuatro diales.** Y `report()` devolvia `plan.paradigm` sin sondear; en un plan con
    `needs_probe` ese paradigma es el PLACEHOLDER, el admisible mas barato elegido para
    probarse DESPUES de sondear.

        O sea que en la mitad del corpus `report()` no puntuaba una decision: puntuaba un
        marcador de posicion. Y `report()` es lo que produce `selection_terms`,
        `router_captured_fraction` y `risk_coverage` — los numeros con los que se refuto
        P15.

    ES LA CORRECCION QUE QUEDO A MEDIO APLICAR. El docstring de `decide.py` describe este
    defecto **como cerrado**: «`Runner.report` llamaba a `router.plan` una vez y puntuaba
    lo que viniera». Se creo `decide_for` con el ciclo de dos pasos y **este llamador nunca
    migro**. Un modulo que declara una propiedad que su llamador no tiene es peor que uno
    que no la declara: se lee como garantia.

    Y LA CAUSA NO ERA QUE FALTARA SONDEAR. La campana YA PAGO derivar `coupling` con una
    llamada al extractor, y el valor esta en la region de cada fila. Tirarlo y despues
    declarar que falta es **inventarse una carencia**. Recuperarlo cuesta cero:

        EXPLORATORY / STANDARD   23 diferimientos -> 0   la estimacion alcanza
        ACCOUNTABLE / CERTIFIED  23 diferimientos -> 23  sigue haciendo falta sondear

    Los primeros eran artificiales; los segundos son REALES y correctos — una estimacion
    elicitada no sostiene una decision certificada. La diferencia entre los dos casos es
    justamente lo que este chequeo protege.
    """
    import collections
    import inspect
    import json as _json

    from app.assurance import PROFILES, Assurance
    from app.beliefs import Provenance
    from app.policy import PolicyBundle
    from app.router import Router
    from app.runner import COST_PRIORS, FALLBACK, Runner, load_rows

    print("\n--- 77. un diferimiento no se puntua como decision ---")

    fuente = inspect.getsource(Runner.report)
    ok &= check("`report()` le pasa a `router.plan` la creencia que el registro ya tiene",
                "coupling=coup" in fuente and "coupling_credence=cred" in fuente)
    ok &= check("y la asienta como ELICITED — es la estimacion de un modelo, no una "
                "observacion, y en CERTIFIED no puede alcanzar",
                "coupling_provenance=Provenance.ELICITED" in fuente)
    ok &= check("los planes que piden sonda se REGISTRAN como diferidos",
                "needs_probe" in fuente and "diferidas.append" in fuente)
    ok &= check("y el reporte los publica, o no se podria auditar la decision",
                '"deferred_for_probe"' in fuente and '"deferred_fraction"' in fuente)

    # CONTRA EL REGISTRO REAL, que es donde el defecto vivia.
    ruta = Path("results/luna/gold_h1_rows.jsonl")
    if not ruta.exists():
        ok &= check("(sin registro para contrastar: se saltea)", True)
        return ok

    tareas = {t["task_id"]: t for t in _json.loads(
        Path("corpus/gold_h1/tasks.json").read_text(encoding="utf-8"))}
    rows, region = collections.defaultdict(dict), {}
    for f in load_rows(ruta):
        if not f.get("infeasible"):
            rows[f["task_id"]][f["paradigm"]] = f
            region[f["task_id"]] = f.get("region", "")

    # EL PANEL SE PIDE, NO SE DEDUCE. La regla ingenua —«los brazos que cubren el 95% de
    # las tareas medidas»— colapsa en cuanto UN brazo tiene mas cobertura que el resto: al
    # re-correr `rewoo` sobre las 78 mientras los otros seguian en 46, el universo de tareas
    # se amplio a 78 y ningun otro brazo llegaba al 95%. El panel quedo en un solo brazo y
    # este chequeo se cayo con un `ValueError` que no hablaba de paneles.
    #
    # `bench.panel.rectangulo` mira PRIMERO las tareas ricas —las que corrio la campana— y
    # recien despues los brazos. Vive en un solo lugar porque la misma regla estaba escrita
    # en cinco analisis y un test, y se rompio en los seis el mismo dia.
    from bench.panel import rectangulo
    panel = rectangulo(list(load_rows(ruta)))
    rows = {t: rows[t] for t in panel.tareas}
    region = {t: region[t] for t in panel.tareas}
    ok &= check(f"el panel se arma sin colapsar: {panel.descripcion()}",
                len(panel.brazos) >= 5 and len(panel.tareas) >= 20)

    router = Router(PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3),
                    COST_PRIORS, FALLBACK)
    COUP = {"loose": 0.15, "mixed": 0.5, "tight": 0.85}

    def coup_de(tid):
        for parte in region[tid].split("/"):
            if parte in COUP:
                return COUP[parte], 1.0
        return None, 0.0

    ok &= check(f"el `coupling` derivado se puede recuperar de la region en las "
                f"{len(rows)} tareas — la campana ya lo pago",
                all(coup_de(t)[0] is not None for t in rows))

    def sondas(a, con_creencia):
        n = 0
        for tid in rows:
            c, cr = coup_de(tid) if con_creencia else (None, 0.0)
            plan = router.plan(task=tareas[tid], candidates=sorted(rows[tid]),
                               region=region[tid], requested=a, coupling=c,
                               coupling_provenance=Provenance.ELICITED,
                               coupling_credence=cr)
            n += bool(getattr(plan, "needs_probe", False))
        return n

    sin = sondas(Assurance.STANDARD, False)
    con = sondas(Assurance.STANDARD, True)
    ok &= check(f"sin pasar la creencia, HALF el corpus pedia sonda ({sin} de {len(rows)}) "
                f"— y se puntuaba el placeholder", sin >= len(rows) // 2)
    ok &= check(f"pasandola, en STANDARD no queda ninguno ({con}): el diferimiento era "
                f"ARTIFICIAL, la evidencia estaba y se tiraba", con == 0)

    # Y EL DIFERIMIENTO REAL SOBREVIVE. Si esto diera 0 tambien, el arreglo habria
    # aflojado el gate en vez de dejar de tirar evidencia — que es el error opuesto y peor.
    cert = sondas(Assurance.CERTIFIED, True)
    ok &= check(f"pero en CERTIFIED sigue pidiendo sonda ({cert}): una estimacion "
                f"ELICITED no sostiene una decision con piso OBSERVED",
                cert > 0
                and PROFILES[Assurance.CERTIFIED].derived_floor is Provenance.OBSERVED)
    return ok


def check_new_predictors_reach_the_decision(ok: bool) -> bool:
    """§76: los dos predictores medidos LLEGAN a la región, y el literal no es un léxico.

    LA GUARDA QUE ESTE REPO YA PAGÓ TRES VECES EN UN DÍA: un eje que no llega **no falla,
    corre y mide su ausencia**, y el resultado se lee igual que un efecto nulo medido. §59
    lo impide para las herramientas; esto lo impide para las features. Y acá el camino es
    largo —`payload_for` → extractor → `features_for` → `region()`— con tres sitios donde
    un campo se puede caer sin que nada se ponga rojo.

    DE DÓNDE SALEN (`CP-6`). Se midieron con la política de desempate por costo evaluada
    leave-one-out sobre 41 tareas × 7 brazos: `región × literal` da **+0,021 de utilidad y
    47% de ahorro** contra el mejor fijo, donde el vocabulario anterior daba `−0,002` y 37%.

    Y LA DISTINCIÓN QUE HAY QUE CUSTODIAR. Este módulo prohíbe los disparadores léxicos en
    su primera línea, porque inferir el TIPO de tarea del fraseo es lo que hizo perder a los
    routers en prosa. `literal` **no** hace eso:

        prohibido   «la pregunta dice *how many*»  ->  «es un conteo»
        esto        «la pregunta cita 'director'»  ->  «'director' está en el material»

    El valor no lo decide el fraseo: lo decide el corpus. Es la misma clase epistémica que
    `measure_continuation` — contención de una cadena conocida, sin modelo en el medio.
    """
    from app.features import (Availability, FEATURE_AVAILABILITY, Features,
                              REGION_VOCABULARY, measure_question_literal, payload_for)

    print("\n--- 76. los predictores nuevos llegan a la decision ---")

    docs = {"u1": "Marta Arrieta is director. Account AR9263415718.",
            "u2": "Tomas Peralta, city Rosario."}
    ids = ["u1", "u2"]

    ok &= check("un literal citado que ESTA en el material",
                measure_question_literal("role is 'director'", docs, ids) == "lit_present")
    ok &= check("uno que NO esta — y es el caso que decide, porque es el barato",
                measure_question_literal("role is 'trustee'", docs, ids) == "lit_absent")
    ok &= check("un identificador de cuenta cuenta como literal",
                measure_question_literal("account AR9263415718?", docs, ids)
                == "lit_present")
    ok &= check("sin literal citado se dice `no_lit`, que no es lo mismo que ausente",
                measure_question_literal("Name the individual.", docs, ids) == "no_lit")
    ok &= check("y sin material, `None`: ausencia de MEDICION, nunca un negativo",
                measure_question_literal("role is 'x'", {}, ["zz"]) is None)

    # UNA PREGUNTA BOOLEANA CITA SUS OPCIONES, NO UN TERMINO DE BUSQUEDA. Es un defecto que
    # esta funcion tuvo desde que se escribio y lo destapo MEDIR la regla que habilita
    # (`EP-5`), no leerla: `C7` pregunta «Answer 'escalate' or 'no escalation'» y esos
    # literales no estan en el material POR CONSTRUCCION, asi que devolvia `lit_absent` en
    # las 8 tareas booleanas del panel — afirmando algo sobre el MATERIAL a partir del
    # FORMATO de la pregunta. Como detector de ausencia daba precision 50% y recall 50%, y
    # sus 8 aciertos aparentes eran booleanas, ni una de `B2_absence`.
    #
    # La guarda usa lo que el CALLER DECLARA (`answer_cardinality`), no el fraseo:
    # distinguirlas mirando como esta redactada la pregunta seria el disparador lexico que
    # este modulo prohibe en su primera linea.
    q_bool = "Decide whether to escalate. Answer 'escalate' or 'no escalation'."
    ok &= check("una pregunta BOOLEANA cita sus opciones: no se lee como termino ausente",
                measure_question_literal(q_bool, docs, ids, cardinality="boolean")
                == "no_lit")
    ok &= check("y sin declarar la cardinalidad reaparece el defecto — la guarda depende "
                "de que el caller declare, que es como se reciben `irreversible` y "
                "`shared_writes`",
                measure_question_literal(q_bool, docs, ids) == "lit_absent")
    ok &= check("una enumerativa con un termino real sigue midiendo el MATERIAL",
                measure_question_literal("role is 'director'", docs, ids,
                                         cardinality="enumerative") == "lit_present")

    # NO ES UN DISPARADOR LEXICO. La prueba: la MISMA pregunta da valores distintos segun
    # el material. Un disparador lexico daria siempre lo mismo, porque solo mira el texto.
    q = "list every individual whose role is 'trustee'"
    ok &= check("la MISMA pregunta cambia de valor si cambia el material — un disparador "
                "lexico no podria, porque no mira el corpus",
                measure_question_literal(q, docs, ids) == "lit_absent"
                and measure_question_literal(q, {"u1": "Ana is trustee"}, ["u1"])
                == "lit_present")

    # LOS DOS SON COMPUTABLE, y eso es medio motivo de haberlos elegido: sobreviven la
    # proyeccion D2, asi que una regla que los use SI puede disparar en modo determinista.
    for eje in ("literal", "cardinality", "continuation"):
        ok &= check(f"`{eje}` esta clasificado y es COMPUTABLE",
                    FEATURE_AVAILABILITY.get(eje) is Availability.COMPUTABLE)

    # EL CAMINO COMPLETO, que es lo que §59 enseño a probar: del payload a la region.
    tarea = {"question": "role is 'director'", "unit_ids": ids, "oracle": ["x"],
             "has_oracle": True, "budget_tokens": 9000,
             "answer_cardinality": "enumerative"}
    ok &= check("`payload_for` lleva la cardinalidad DECLARADA por el caller",
                payload_for(tarea)["answer_cardinality"] == "enumerative")

    import inspect
    from app.runner import Runner
    fuente = inspect.getsource(Runner.features_for)
    ok &= check("`features_for` mide los TRES ejes del material en un solo lugar — "
                "olvidar uno no falla, corre y mide su ausencia",
                all(x in fuente for x in ("measure_continuation(",
                                          "measure_question_literal(",
                                          "answer_cardinality")))

    f = Features(n_units=2, has_oracle=True, irreversible=False, shared_writes=False,
                 budget_tokens=9000, coupling=0.2, continuation=True,
                 cardinality="enumerative", literal="lit_present")
    ok &= check(f"y la region los lleva puestos ({f.region()})",
                f.region().endswith("/lit_present")
                and REGION_VOCABULARY == "regions/3-literal")
    return ok


def check_grading_scores_the_answer_not_its_wording(ok: bool) -> bool:
    """§75: se puntua LA RESPUESTA, no su redaccion ni su formato.

    DOS DEFECTOS QUE HACIAN QUE **9 DE 78** TAREAS DIERAN CERO SOBRE TODO EL PLANTEL. Salio
    de derivar el camino a mano: que DOCE topologias fallen las mismas nueve preguntas es
    mas consistente con un grader roto que con doce fracasos, y lo era.

    1. `D1_presupposition` — LA PREMISA ES FALSA Y EL ORACULO ERA UNA REDACCION. El oraculo
       es `'no transfer is recorded'`. Medido sobre `d1-000-w4`, los NUEVE brazos
       contestaron correctamente y los nueve sacaron **0,00**:

           "Not stated in the source documents"   "Not specified"
           "The date cannot be determined..."     "Cannot be determined from the evidence"

       Hay infinitas formas correctas de rechazar una premisa, y se estaba puntuando la
       eleccion de palabras con igualdad de cadenas.

    2. `C9_declared_roster` — LA PREGUNTA PIDE EL EMPAREJAMIENTO Y EL GRADER LO PROHIBIA.
       Pregunta *«para cada uno de estos individuos, reporta la cuenta»*, el oraculo son las
       cuatro cuentas sueltas, y las respuestas traian **las cuatro correctas** emparejadas
       con su nombre. La interseccion de conjuntos no cruza `ar9263415718` con
       `marta arrieta ar9263415718`, asi que las cinco tareas medidas daban 0,00.

    POR QUE IMPORTA MAS DE LO QUE PARECE. Deprime a todos los brazos por igual, asi que el
    RANKING comparativo sobrevive — pero saca 9 tareas del conjunto que discrimina, y sobre
    ese conjunto se calculan la brecha de oraculo y el piso de ruido. Un cero que no es del
    sistema medido contamina las dos.

    Y LAS DOS CORRECCIONES SE AUTO-LIMITAN, que es lo que impide que esto sea aflojar:
    el credito por rechazo se lee **del oraculo** —solo si el oraculo mismo es un rechazo—
    asi que una tarea con oraculo de VALOR no lo puede recibir; y el emparejamiento exige
    frontera de palabra y asignacion uno a uno.
    """
    from app.grading import score
    from app.verify import is_refusal

    print("\n--- 75. se puntua la respuesta, no su redaccion ---")

    # ── D1: un rechazo es un VEREDICTO, no una cadena ──
    ora = ["no transfer is recorded"]
    for texto, esperado in (
        ("Not stated in the source documents", 1.0),
        ("The date cannot be determined from the provided text.", 1.0),
        ("Not specified", 1.0),
        ("Marta Arrieta is custodian, account AR9263415718, but no transfer date "
         "is provided", 1.0),
    ):
        ok &= check(f"un rechazo correcto puntua 1,0 — {texto[:44]!r}",
                    score(texto, ora) == esperado)

    ok &= check("y entregar la fecha que la premisa falsa pedia puntua 0",
                score("The transfer occurred on 2024-03-12", ora) == 0.0)
    ok &= check("un rechazo que IGUAL entrega la fecha no es un rechazo: es una premisa "
                "ratificada con un descargo adelante",
                score("no transfer date on file, but it was March 2024", ora) == 0.0
                and score("not recorded; see 12/03/2024", ora) == 0.0)
    ok &= check("el silencio no es un rechazo — un brazo que se cayo no puede puntuar "
                "igual que uno que miro y reporto",
                score("", ora) == 0.0 and not is_refusal(""))

    # LA GUARDA QUE IMPIDE QUE ESTO SEA AFLOJAR. La condicion se lee del ORACULO: si el
    # oraculo es un valor, «no se» sigue valiendo cero. Sin esto, un permiso pasado desde
    # afuera podria caerle a una tarea de valor y convertir la evasion en la respuesta.
    ok &= check("con un oraculo de VALOR, una evasiva sigue puntuando 0",
                score("not stated", ["AR9263415718"]) == 0.0
                and score("cannot be determined", ["Rosario"]) == 0.0)

    # ── C9: emparejar clave y valor no es equivocarse ──
    ora9 = ["AR5597141797", "AR6534161716", "AR7602773472", "AR9263415718"]
    emparejada = ("Marta Arrieta - AR9263415718; Ignacio Ybarra - AR6534161716; "
                  "Lucia Vallejos - AR5597141797; Tomas Peralta - AR7602773472")
    ok &= check("la respuesta que empareja nombre y cuenta puntua 1,0 — es lo que la "
                "pregunta pide",
                score(emparejada, ora9) == 1.0)
    ok &= check("y la que da las cuatro sueltas tambien, o el formato decidiria",
                score("AR9263415718; AR6534161716; AR5597141797; AR7602773472", ora9)
                == 1.0)
    ok &= check("faltar una baja el puntaje, no lo anula",
                0.0 < score("Marta - AR9263415718; Ignacio - AR6534161716; "
                            "Lucia - AR5597141797", ora9) < 1.0)
    ok &= check("y contestar `unavailable` en las cuatro sigue siendo cero",
                score("Marta - unavailable; Ignacio - unavailable; Lucia - unavailable; "
                      "Tomas - unavailable", ora9) == 0.0)

    # LAS DOS GUARDAS DEL EMPAREJAMIENTO.
    ok &= check("la contencion cae en FRONTERA de palabra — `AR1234` no acierta adentro "
                "de `AR12345`, la misma trampa que «4» contra «42»",
                score("AR12345; AR99999", ["AR1234", "AR9999"]) == 0.0)
    ok &= check("y es UNO A UNO: un solo item predicho no puede cosechar dos aciertos",
                score("AR1111 AR2222", ["AR1111", "AR2222"]) < 1.0)

    # NO SE AFLOJO NADA MAS. Los casos que ya andaban tienen que seguir igual.
    ok &= check("un oraculo vacio sigue exigiendo decir que no hay",
                score("none", []) == 1.0 and score("Marta Arrieta", []) == 0.0
                and score("", []) == 0.0)
    ok &= check("y un oraculo singleton de valor sigue con su credito por substring",
                score("account AR9263415718", ["AR9263415718"]) == 1.0
                and score("4", ["42"]) == 0.0)
    return ok


def check_absence_has_a_second_proof(ok: bool) -> bool:
    """§74: una ausencia se puede probar sin leer nada, y el contrato viejo era VACIO.

    EL HALLAZGO, que salio de derivar a mano el camino de las 78 preguntas. `C-ABSENCE`
    exigia el DOMINIO ENTERO para admitir un enunciado de ausencia, y la regla es correcta:
    cualquier unidad sin leer puede contener justo lo que se niega. Pero tenia **una sola
    forma** de conseguirlo —leerlo— y para una ausencia de TERMINO hay otra que cuesta cero
    tokens y es igual de concluyente: si la cadena no aparece en ninguna unidad del
    alcance, no aparece.

    Y ESO IMPORTABA MAS DE LO QUE PARECIA. Medido sobre las nueve tareas de `B2_absence`:

        material   40.234 · 160.982 · 482.961 tokens   segun el ancho
        presupuesto                        40.000      en las nueve

    **En 9 de 9 la ruta exhaustiva NO ENTRA en el presupuesto de la tarea.** O sea que el
    contrato no era estricto: era **insatisfacible**. Ninguna respuesta correcta —y la
    correcta es siempre «ninguno», porque las nueve tienen cero unidades relevantes— podia
    ser admitida jamas, y no por estar mal sino porque la unica prueba aceptada costaba mas
    que la tarea.

    NUNCA SE DISPARO porque `demand_obligations` esta apagado por defecto. Pero el factor
    existe justamente para medir `C-ABSENCE`, asi que la primera corrida con el encendido
    habria dado **cero ausencias admitidas** y se habria leido como «el modelo no puede
    establecer ausencia» cuando era «el contrato no se puede satisfacer». Es la cuarta vez
    que aparece la forma de la leccion 8.16 —un cero de exposicion disfrazado de conducta—
    y la primera que se agarra ANTES de correr.

    LA PRUEBA NUEVA NO AFLOJA LA CARGA. `term_absence` recorre TODAS las unidades del
    alcance, no una muestra: es el mismo dominio entero, conseguido por aritmetica en vez
    de por lectura. Y mantiene el limite dicho: prueba que el TERMINO no esta, no que la
    COSA no este si el material la nombraria de otra forma — de ahi las dos guardas, largo
    minimo y cantidad maxima de palabras.
    """
    from app.beliefs import BeliefBase
    from app.contracts import (MAX_TERM_WORDS, MIN_TERM_CHARS, absence,
                               declared_negated_term, term_absence,
                               verify_obligations)

    print("\n--- 74. la ausencia tiene una segunda prueba, y cuesta cero ---")

    docs = {"u1": "Marta Arrieta is director.", "u2": "Tomas Peralta, signatory."}
    ids = ["u1", "u2"]

    pr = term_absence("trustee", docs, ids)
    ok &= check("una cadena que no esta en NINGUNA unidad prueba su ausencia",
                pr.proves_absence and pr.occurrences == 0 and pr.units_scanned == 2)
    ok &= check("y una que SI esta no prueba nada — el material la desmiente",
                not term_absence("director", docs, ids).proves_absence)

    # LAS TRES FORMAS DE NO PODER PROBAR, todas cerradas.
    ok &= check(f"un termino de menos de {MIN_TERM_CHARS} caracteres no prueba: una cadena "
                "tan corta aparece en cualquier lado",
                not term_absence("ab", docs, ids).proves_absence)
    ok &= check(f"ni una parafrasis de mas de {MAX_TERM_WORDS} palabras — su ausencia "
                "prueba que la PARAFRASIS falta, que no es lo que se afirma",
                not term_absence("una clausula de rescision anticipada unilateral",
                                 docs, ids).proves_absence)
    ok &= check("ni nada sobre un alcance vacio: cero de cero no es exhaustivo",
                not term_absence("trustee", docs, []).proves_absence)

    # LAS TRES RUTAS AL MISMO VEREDICTO, y se distinguen en el registro.
    ok &= check("presencia: un testigo alcanza",
                absence("present", 0, 2).via == "testigo")
    ok &= check("ausencia leyendo el dominio entero: la ruta de siempre",
                absence("absent", 2, 2).via == "dominio_leido")
    ok &= check("ausencia por termino ausente: el dominio cubierto sin leer una unidad",
                absence("absent", 0, 2, term_absence("trustee", docs, ids)).via
                == "termino_ausente")
    ok &= check("y sin ninguna de las tres se REHUSA, como toda esta familia",
                not absence("absent", 1, 2).emitted)

    # LA VIA QUEDA EN EL REGISTRO. Dos rutas a la misma conclusion no se colapsan en un
    # booleano: auditar una autorizacion exige saber si detras hay lectura o aritmetica.
    v = absence("absent", 0, 2, term_absence("trustee", docs, ids)).as_dict()
    ok &= check("el veredicto dice POR QUE VIA se autorizo, y guarda la prueba",
                v["via"] == "termino_ausente" and v["proof"]["occurrences"] == 0)

    # EL CAMINO ENTERO: el agente declara, el codigo verifica.
    tarea = {"task_id": "t", "unit_ids": ids, "obligations": ["absence"]}
    for etiqueta, texto, esperado in (
        ("declara y la prueba sale", "POLARITY: absent\nNEGATES: trustee\nANSWER: none",
         True),
        ("declara algo que SI esta", "POLARITY: absent\nNEGATES: director\nANSWER: none",
         False),
        ("no declara termino", "POLARITY: absent\nANSWER: none", False),
    ):
        r = verify_obligations(tarea, texto, docs, 0, BeliefBase())["absence"]
        ok &= check(f"camino completo — {etiqueta}: emitida={r['emitted']}",
                    r["emitted"] is esperado)

    ok &= check("el termino se lee de una linea TIPADA, no de la prosa",
                declared_negated_term("POLARITY: absent\nNEGATES: trustee\nANSWER: none")
                == "trustee"
                and declared_negated_term("no hay ningun trustee") is None)

    # Y EL CONTRATO SE LO DICE AL MODELO, o la linea no la escribe nadie. Es la misma
    # guarda que §59 impone para las tools: un campo que no llega al prompt no existe.
    from app.contracts import OBLIGATIONS_CONTRACT
    ok &= check("y el contrato que ve el modelo declara la linea `NEGATES`",
                "NEGATES:" in OBLIGATIONS_CONTRACT)

    # EL CONTRATO VIEJO ERA INSATISFACIBLE EN EL CORPUS ENTERO. Se comprueba contra el
    # corpus real, que es donde la regla se aplica.
    import json as _json
    ruta = Path("corpus/gold_h1/tasks.json")
    if ruta.exists():
        documentos = _json.loads(
            Path("corpus/gold_h1/documents.json").read_text(encoding="utf-8"))
        tareas = [t for t in _json.loads(ruta.read_text(encoding="utf-8"))
                  if t["cell"] == "B2_absence"]
        no_entra = sum(
            1 for t in tareas
            if sum(len(documentos[u]) for u in t["unit_ids"]) // 4 > t["budget_tokens"])
        ok &= check(f"y en el corpus la ruta exhaustiva no entra en el presupuesto en "
                    f"{no_entra} de {len(tareas)} tareas de ausencia — el contrato viejo "
                    f"no era estricto, era VACIO", no_entra == len(tareas))
    return ok


def check_effort_balance_is_reachable(ok: bool) -> bool:
    """§73: el balance de esfuerzo se puede ENCENDER, y apagado no cambia nada.

    EL DEFECTO QUE CIERRA, y es el mas grande de los encontrados desafiando las guardas:
    `guards.ventana_sub_agente()` y `guards.presupuesto_de_esfuerzo()` estaban escritas,
    documentadas, y **no las llamaba nadie**. `test_science.py` §67 las ejercitaba
    directamente —asi que pasaba— pero el runner nunca las tocaba y el factor del que
    cuelgan, `effort_balanced`, no existia en ningun archivo del repo.

    O sea: no habia forma de encenderlas. Y `PENDIENTES.es.md` lo tenia anotado como «lo
    que queda para medir es la corrida», que da por hecho que se puede correr.

        Es la forma exacta que este repo ya nombra como su falla recurrente —un factor que
        no llega no falla, **corre y mide su ausencia**— cometida esta vez sobre la guarda
        en vez de sobre la tool. §59 prueba que un factor llega a la DECLARACION DE TOOLS;
        este prueba que llega al FLUJO DE CONTROL, que es el otro camino y no tenia guarda.

    LAS DOS MITADES QUE EXIGE:

      que ENCENDIDO cambie algo   la ventana escala con el alcance; hay tope en tokens
      que APAGADO no cambie NADA  el registro ya pagado tiene que seguir siendo comparable,
                                  y eso solo vale si el default es identico al de antes
    """
    import inspect

    from app import guards as G
    from app.retrieval import CorpusView
    from app.runner import Runner
    from app.tools import ToolSurface

    print("\n--- 73. el balance de esfuerzo se puede encender ---")

    ok &= check("el runner acepta el factor, o no hay forma de correrlo",
                "effort_balanced" in inspect.signature(Runner.__init__).parameters)

    runner_src = Path("app/runner.py").read_text(encoding="utf-8")
    ok &= check("y lo pasa a la superficie — un factor que el runner acepta y no propaga "
                "corre entero midiendo su ausencia",
                "effort_balanced=self.effort_balanced" in runner_src)
    ok &= check("y separa el archivo, como todo factor que cambia comportamiento: "
                "promediar dos condiciones en un `.jsonl` mide dos experimentos",
                '"_balanced"' in runner_src)

    v = CorpusView(task_id="t", documents={"u0": "x"}, unit_ids=["u0"],
                   relevant_units=[])

    def superficie(balanceado: bool) -> ToolSurface:
        return ToolSurface(view=v, hybrid=None, semantic=None, lexical=None,
                           variant="basic", budget_tokens=40_000,
                           effort_balanced=balanceado)

    ok &= check("el sub-agente lo HEREDA — `supervisor` corre todo adentro de `scoped()`, "
                "asi que un factor que no cruza esa frontera no existe donde importa",
                superficie(True).scoped(["u0"]).effort_balanced)

    # QUIEN LO CONSUME. Las dos funciones tienen que estar llamadas desde el codigo que
    # corre, no solo desde este archivo: un test que las invoca directamente prueba la
    # aritmetica y no el cableado, que es justo lo que fallaba.
    sup = Path("app/paradigms/supervisor.py").read_text(encoding="utf-8")
    bucle = Path("app/paradigms/__init__.py").read_text(encoding="utf-8")
    ok &= check("`supervisor` saca su ventana de `guards`, no de la constante fija",
                "guards.ventana_sub_agente(" in sup
                and "rank(surface.view, sub, SUB_SCOPE_UNITS)" not in sup)
    ok &= check("el bucle compartido consulta el tope de esfuerzo",
                "guards.presupuesto_de_esfuerzo(" in bucle)
    ok &= check("y corta ANTES de llamar — la ultima vuelta de un bucle largo es la mas "
                "cara, porque arrastra la conversacion entera",
                "usage.total_tokens >= tope_tokens" in bucle)

    # APAGADO NO CAMBIA NADA. Es la mitad que protege el registro ya pagado.
    ok &= check("apagado, la ventana es la historica",
                G.ventana_sub_agente(60, False) == G.SUPERVISOR_SCOPE_UNITS
                == G.ventana_sub_agente(3, False))
    ok &= check("apagado, no hay tope y se dice con `None` — un numero grande se leeria "
                "como una decision y es lo contrario, es la ausencia de una",
                G.presupuesto_de_esfuerzo(40_000, False) is None)
    ok &= check("y el default de la superficie es apagado",
                not superficie(False).effort_balanced
                and not ToolSurface(view=v, hybrid=None, semantic=None, lexical=None,
                                    variant="basic",
                                    budget_tokens=1).effort_balanced)

    # ENCENDIDO CAMBIA ALGO, o seria un factor decorativo.
    ok &= check(f"encendido, la ventana escala: 60 unidades -> "
                f"{G.ventana_sub_agente(60, True)}, 5 -> {G.ventana_sub_agente(5, True)}",
                G.ventana_sub_agente(60, True) > G.ventana_sub_agente(5, True))
    ok &= check("y nunca deja de aislar sobre un alcance grande",
                G.ventana_sub_agente(60, True) < 60)
    return ok


def check_measuring_is_not_reading(ok: bool) -> bool:
    """§71: medir el largo de una unidad no es haberla leido, y una falla se cuenta por tipo.

    CINCO SITIOS LLAMABAN A `read_one` PARA QUEDARSE CON `len(...)`. Y `read_one` deja
    rastro —suma a `served_chars`, mete la unidad en `units_read_structural`— asi que
    estimar el costo de algo lo cobraba como lectura. Ninguno cambiaba lo que el modelo ve,
    y por eso era invisible: la topologia estaba bien y la medida estaba mal.

    LO QUE ESO INVERTIA, medido sobre las filas que tienen el contador:

      · `pointer_chase` daba `units_read_structural == n_units` en **170 de 170 celdas**,
        el alcance ENTERO, porque promediaba el largo de todas las unidades antes del
        primer salto. Es el brazo que se define por seguir UN puntero desde UN ancla, y la
        unica metrica que mostraria si lo hace decia que abria el corpus completo. El
        veredicto de P14a sobrevive porque se calculo sobre `units_read` —las lecturas del
        MODELO— pero `relevant_units_read_any` decia lo contrario
      · `streaming_scan` cobraba el corpus DOS veces. Su docstring dice que cada token
        entra al modelo exactamente una vez y que es el unico brazo del catalogo con esa
        garantia; la garantia se cumplia y la contabilidad la desmentia
      · `gist_reader` cobraba cada unidad seleccionada TRES veces: gist, estimacion, lectura

    Y LAS SIETE FORMAS DE FALLAR, CONTADAS. La superficie contaba UNA —el id inexistente—
    y era ciega a las otras seis: no se le podia preguntar al registro con que frecuencia
    el modelo erraba una llamada ni de que manera.

    MAS EL DEFECTO QUE ESO DESTAPO, que es el mismo que ya tuvo `barren`: `hallucinated`
    era un `int`, y `scoped()` comparte por referencia pero `replace` copia los enteros por
    valor. Medido: `handoff` (773 llamadas) y `supervisor` (1.583) daban **CERO** ids
    alucinados, contra 5 de `react` y 9 de `dag_strategy`. `dag_strategy` tambien
    descompone y si contaba, porque le pasa al sub-agente la superficie del padre — ese
    contraste es la prueba de que el cero era la copia por valor y no la conducta.
    """
    import re

    from app.paradigms import PISTA_POR_TIPO
    from app.retrieval import CorpusView
    from app.tools import CHARS_PER_TOKEN, ToolFailure, ToolSurface

    print("\n--- 71. medir no es leer, y una falla se cuenta por tipo ---")

    docs = {f"u{i}": "x" * 400 for i in range(5)}

    def superficie() -> ToolSurface:
        v = CorpusView(task_id="t", documents=docs, unit_ids=list(docs),
                       relevant_units=["u0"])
        return ToolSurface(view=v, hybrid=None, semantic=None, lexical=None,
                           variant="basic", budget_tokens=50_000)

    s = superficie()
    largo = s.unit_chars("u0")
    ok &= check("`unit_chars` da el largo y NO deja rastro de lectura",
                largo == 400 and not s.units_read_structural and s.served_chars == 0)
    ok &= check(f"`unit_tokens` usa `CHARS_PER_TOKEN` ({CHARS_PER_TOKEN}), la misma "
                "aritmetica con que la factibilidad PODA — no un `// 4` suelto",
                s.unit_tokens("u0") == largo // CHARS_PER_TOKEN)

    # NINGUN SITIO PUEDE VOLVER A USAR `read_one` COMO REGLA. Se mira el codigo: un
    # `len(...read_one...)` es la forma exacta del defecto, y volveria a ser invisible.
    fuente = Path("app/paradigms/modern.py").read_text(encoding="utf-8")
    ok &= check("ningun paradigma mide un largo con `len(read_one(...))`",
                not re.search(r"len\(\s*surface\.read_one", fuente))
    # Se mira el CODIGO y no la prosa: el unico `// 4` que queda es el del comentario que
    # explica por que ya no se usa, y un chequeo que no distingue las dos cosas obliga a
    # borrar la explicacion para que pase.
    codigo = [l.split("#")[0] for l in fuente.splitlines()]
    ok &= check("ni estima tokens con un `// 4` escrito a mano",
                not any("// 4" in l for l in codigo))

    # LAS SIETE FORMAS, CONTADAS POR TIPO Y NO SOLO UNA.
    s = superficie()
    for nombre, args in (("read", {"unit_ids": "no-existe,tampoco"}),
                         ("read", {}),
                         ("inventada", {}),
                         ("coverage", {})):
        try:
            s.dispatch(nombre, args)
        except ToolFailure:
            pass
    ok &= check(f"cada forma de fallar se cuenta por separado ({dict(s.tool_failures)})",
                s.tool_failures == {"id_inexistente": 1, "argumento": 1,
                                    "desconocida": 1, "no_ofrecida": 1})
    ok &= check("y los IDS inventados se cuentan aparte de las LLAMADAS que fallaron — "
                "una sola llamada puede inventar varios",
                s.hallucinated == 2 and s.tool_failures["id_inexistente"] == 1)
    ok &= check("la fila los lleva, o no existen",
                s.usage()["tool_failures_total"] == 4)

    # SE CUENTA EN EL CUELLO. Un contador que hay que acordarse de tocar en cada `raise`
    # deja de ser cierto en la primera prisa.
    tools_src = Path("app/tools.py").read_text(encoding="utf-8")
    ok &= check("el conteo vive en `dispatch` y no repartido por los `raise`",
                "def _dispatch(self" in tools_src
                and tools_src.count("self.tool_failures[tipo]") == 1)

    # LO QUE ERRA UN SUB-AGENTE ES DE LA TAREA. Mismo defecto que `barren`, otro contador.
    s = superficie()
    sub = s.scoped(["u0", "u1"])
    ok &= check("`scoped` comparte el objeto de fallas, no una copia",
                sub.fallas is s.fallas)
    try:
        sub.dispatch("read", {"unit_ids": "fantasma"})
    except ToolFailure:
        pass
    ok &= check("y lo que erra el sub-agente LLEGA al padre — `handoff` y `supervisor` "
                "daban 0 en 2.356 llamadas por la copia por valor",
                s.hallucinated == 1 and s.tool_failures.get("id_inexistente") == 1)

    # LA PISTA SALE DEL TIPO. Una sola pista fija para las siete apunta al arreglo
    # equivocado en seis, y una pista equivocada es peor que ninguna porque se sigue.
    ok &= check("hay una pista distinta por forma de fallar",
                len(set(PISTA_POR_TIPO.values())) == len(PISTA_POR_TIPO) >= 6)
    ok &= check("la del batch habla de PARTIR la llamada, no de ids",
                "Split" in PISTA_POR_TIPO["batch"])
    bucle = Path("app/paradigms/__init__.py").read_text(encoding="utf-8")
    ok &= check("y el bucle compartido la busca por tipo en vez de pegar una fija",
                "PISTA_POR_TIPO.get(" in bucle
                and '"hint": "Use only unit ids returned by a search."' not in bucle)
    return ok


def check_every_arm_has_a_named_ceiling(ok: bool) -> bool:
    """§72: los doce brazos tienen techo nombrado, incluidos los que NO tienen techo fijo.

    `guards.py` dice en su primera linea que tiene «todos los limites de todos los
    patrones», y no era cierto: los cuatro brazos clasicos llevaban los suyos escritos a
    mano adentro de `paradigms/__init__.py` —un `20`, un `10`, un `8`, un `4`— y ninguno
    aparecia en el modulo ni en `TECHO_LLAMADAS`.

    Y NO ERAN LOS CHICOS. `reflection` es el brazo mas caro del catalogo (118.911 tokens
    por celda) y sus dos topes eran los que nadie habia nombrado; `react` es el FALLBACK,
    o sea contra el que se mide la brecha de oraculo de todo el banco, y su `20` era un
    literal en medio de una llamada. Que el limite del patron mas caro y el del patron de
    referencia fueran los dos invisibles no es casualidad: son los que nadie movio nunca.

    Y LOS QUE NO TIENEN TECHO FIJO SE DECLARAN, no se omiten. `map_reduce` hace una llamada
    por unidad: su techo **es el alcance**, de 1 a 60 sobre el corpus. Un patron ausente de
    la tabla se lee como un olvido, y un olvido invita a inventarle un numero.
    """
    from app import guards as G
    from app.paradigms import REGISTRY

    print("\n--- 72. todos los brazos tienen su techo nombrado ---")

    cubiertos = set(G.TECHO_LLAMADAS) | set(G.SIN_TECHO_FIJO)
    faltan = set(REGISTRY) - cubiertos
    ok &= check(f"los {len(REGISTRY)} del REGISTRY estan cubiertos "
                f"(faltan: {sorted(faltan) or 'ninguno'})", not faltan)
    ok &= check("ninguno esta en las dos tablas — o tiene techo fijo o no lo tiene",
                not (set(G.TECHO_LLAMADAS) & set(G.SIN_TECHO_FIJO)))
    ok &= check("el del brazo mas caro esta nombrado: borrador + critica + revision",
                G.TECHO_LLAMADAS["reflection"]
                == G.REFLECTION_DRAFT_ITERATIONS + 1 + G.REFLECTION_REVISE_ITERATIONS)
    ok &= check("y el del FALLBACK tambien, que es contra el que se mide todo",
                G.TECHO_LLAMADAS["react"] == G.REACT_ITERATIONS)

    # NINGUN LIMITE SUELTO EN EL ARCHIVO DEL PATRON. Es la unica forma de que la
    # centralizacion siga siendo cierta: si se puede escribir un numero a mano, se escribe.
    import re
    fuente = Path("app/paradigms/__init__.py").read_text(encoding="utf-8")
    sueltos = re.findall(r"max_iterations=(\d+)", fuente)
    ok &= check(f"ningun `max_iterations` literal quedo en el catalogo clasico "
                f"({sueltos or 'ninguno'})", not sueltos)
    return ok


def check_every_tool_works_in_isolation(ok: bool) -> bool:
    """§70: cada herramienta, probada de a una contra una vista real, y por su EFECTO.

    NO EXISTIA, y su ausencia dejo pasar el defecto mas caro de la sesion: `rewoo` llamaba
    a `read` en 130 de 138 celdas y leia CERO unidades. Los tests probaban los paradigmas
    de punta a punta y las auditorias miraban el registro; **ninguno probaba una herramienta
    sola**.

    LA DIFERENCIA ENTRE ESTO Y «QUE NO REVIENTE»: cada caso verifica el EFECTO observable —
    que `read` aumente `units_read`, que un id inexistente cuente como alucinado, que un
    argumento faltante degrade y no mate. Una herramienta que devuelve algo plausible sin
    haber hecho nada es exactamente lo que no se ve desde arriba.

    Y CUBRE LAS TRES FORMAS DE FALLA que el registro distingue:
      · argumento ausente        -> `ToolFailure`, recuperable por el modelo
      · id que no existe         -> `ToolFailure` Y se cuenta como alucinado
      · nombre desconocido       -> `ToolFailure`, no `ValueError`: un nombre inventado
                                    mataba la celda en unos paradigmas y degradaba en
                                    otros, asi que dos brazos se puntuaban distinto por el
                                    mismo error del modelo
    """
    from app.retrieval import CorpusView
    from app.tools import ToolFailure, ToolSurface

    print("\n--- 70. cada herramienta anda, probada sola ---")

    docs = {f"memo-{i:03d}": f"Memo {i}. Marta Arrieta es directora. "
                             f"Cuenta AR{i:07d}. Ciudad Rosario." for i in range(6)}

    def superficie(variant: str = "basic") -> ToolSurface:
        v = CorpusView(task_id="t", documents=docs, unit_ids=list(docs),
                       relevant_units=["memo-002"])
        return ToolSurface(view=v, hybrid=None, semantic=None, lexical=None,
                           variant=variant, budget_tokens=60_000)

    # `read` — el efecto es que la unidad quede LEIDA, no que devuelva algo.
    s = superficie()
    salida = s.dispatch("read", {"unit_ids": "memo-002"})
    ok &= check("`read` devuelve el texto Y marca la unidad como leida",
                "AR0000002" in salida and s.units_read == {"memo-002"})

    s = superficie()
    s.dispatch("read", {"unit_ids": "memo-001,memo-003"})
    ok &= check("`read` en batch lee TODAS las que se le piden",
                s.units_read == {"memo-001", "memo-003"})

    # UN ID QUE NO EXISTE: falla visible Y contada. Devolver vacio en silencio seria lo
    # que dejo pasar el defecto de `rewoo` durante toda la campaña.
    s = superficie()
    try:
        s.dispatch("read", {"unit_ids": "no-existe"})
        ok &= check("un id inexistente falla", False)
    except ToolFailure as e:
        ok &= check("un id inexistente levanta `ToolFailure` y se CUENTA como alucinado",
                    s.hallucinated == 1 and "no-existe" in str(e))

    # ARGUMENTO FALTANTE: degrada, no mata, y el mensaje nombra el argumento.
    s = superficie()
    try:
        s.dispatch("read", {})
        ok &= check("un argumento obligatorio faltante falla", False)
    except ToolFailure as e:
        ok &= check("un argumento faltante levanta `ToolFailure` y NOMBRA el argumento",
                    "unit_ids" in str(e))

    # NOMBRE DESCONOCIDO: `ToolFailure`, no `ValueError`. El bucle compartido atrapa solo
    # `ToolFailure`, asi que un `ValueError` mata la celda en unos brazos y degrada en
    # otros — y `rewoo` toma el nombre de un JSON escrito por el modelo.
    s = superficie()
    try:
        s.dispatch("inventada", {})
        ok &= check("un nombre desconocido falla", False)
    except ToolFailure as e:
        ok &= check("un nombre desconocido degrada como `ToolFailure` y lista el catalogo",
                    "no existe" in str(e) and "read" in str(e))
    except ValueError:
        ok &= check("un nombre desconocido NO puede ser `ValueError`: mata la celda en "
                    "unos paradigmas y degrada en otros", False)

    # UNA HERRAMIENTA NO OFRECIDA EN LA VARIANTE tampoco mata.
    s = superficie("basic")
    try:
        s.dispatch("coverage", {})
        ok &= check("`coverage` no existe en `basic` y falla", False)
    except ToolFailure:
        ok &= check("una herramienta de otra variante degrada, no mata", True)

    # LA SECUENCIA REGISTRA LO QUE SE PIDIO, aunque falle: una politica que solo guarda
    # los aciertos describe algo que nadie ejecuto.
    s = superficie()
    for nombre, args in (("read", {"unit_ids": "memo-000"}), ("read", {}),
                         ("inventada", {})):
        try:
            s.dispatch(nombre, args)
        except ToolFailure:
            pass
    ok &= check("la secuencia guarda las llamadas que FALLARON tambien",
                s.sequence == ["read", "read", "inventada"])
    return ok


def check_each_pattern_has_the_tools_it_needs(ok: bool) -> bool:
    """§69: que un patron NO use una herramienta se decide leyendo, no borrando.

    LA REGLA DEL AUTOR (2026-08-30): antes de sacarle una herramienta a un patron, fijarse
    si **deberia** usarla. Una no-adopcion puede ser tres cosas distintas y se ven iguales
    desde el registro — que no la necesite, que no se la ofrezcan, o que la plomeria este
    rota. Las tres piden respuestas opuestas.

    EL ANALISIS A MANO, sobre las 1.284 celdas, y su veredicto por patron:

      rewoo             search+keyword+read, SIN semantica   -> FALTABA. Planifica a
                        ciegas: no puede corregir una consulta que no matcheo. La lexica
                        exige el termino exacto; la semantica tolera el parafraseo. Para un
                        brazo que reacciona, que falte una modalidad cuesta una vuelta mas;
                        para uno que NO reacciona, cuesta la tarea. **Se agrego.**
      pointer_chase     idem, sin semantica                  -> correcto: sigue punteros,
                        que son identificadores y nombres propios, y ahi gana el lexico
      graph_traverse    solo `read`                          -> correcto, y ES su
                        definicion: el grafo le dice a donde ir. Darle busqueda lo
                        convertiria en `react` con prior de grafo
      gist_reader       solo `read`                          -> correcto: ya ve todos los
                        gists. Buscar sirve para encontrar donde mirar, y el mira todo
      direct/extract/scan  ninguna                           -> correcto: el codigo les
                        sirve el material
      los cinco con bucle  las cuatro                        -> correcto: ven resultados

    QUE FIJA ESTE TEST: que un patron que planifica sin ver resultados tenga TODA la
    recuperacion disponible, porque es el que menos puede recuperarse de elegir mal.
    """
    import re
    from app.paradigms.modern import REWOO_TOOLS
    from app.tools import TOOL_SPECS

    print("\n--- 69. cada patron tiene las herramientas que su mecanismo necesita ---")

    disponibles = {t["function"]["name"] for t in TOOL_SPECS}
    declaradas = set(re.findall(r"- (\w+)\(", REWOO_TOOLS))
    faltan = disponibles - declaradas
    ok &= check(f"`rewoo` planifica a ciegas y ve TODA la recuperacion "
                f"(falta: {sorted(faltan) or 'ninguna'})", not faltan)
    ok &= check("y la semantica esta explicada por que sirve, no solo listada — una "
                "herramienta cuyo criterio de uso no se dice, no se usa",
                "tolerates paraphrase" in REWOO_TOOLS)

    # LOS QUE NO BUSCAN, NO BUSCAN POR DISEÑO. Se fija que sigan sin hacerlo: si mañana
    # alguien le agrega busqueda a `graph_traverse`, deja de ser el patron que se midio.
    import inspect
    from app.paradigms import REGISTRY
    for nombre, motivo in (("graph_traverse", "el grafo le dice a donde ir"),
                           ("gist_reader", "ya ve todas las unidades en gist")):
        src = inspect.getsource(REGISTRY[nombre])
        busca = bool(re.search(r'dispatch\(\s*["\']?(search|keyword_search|semantic_search)',
                               src))
        ok &= check(f"`{nombre}` sigue sin buscar — {motivo}", not busca)
    return ok


def check_rewoo_can_actually_read(ok: bool) -> bool:
    """§68: un argumento que pide un IDENTIFICADOR recibe ids, no texto.

    EL DEFECTO QUE CIERRA. La sustitucion de evidencia de ReWOO es textual —`#E1` se
    reemplaza por la salida del paso 1— y para una `query` eso esta bien. Para `unit_ids`
    esta mal: a `read` le llegaba el **JSON entero de la busqueda** truncado, donde
    esperaba un id.

    Medido antes del arreglo, sobre 138 celdas: `rewoo` llamaba a `read` en **130** y leia
    **CERO** unidades, y era el unico brazo del plantel con ids alucinados —**36**, contra
    0 de los otros ocho—. Contestaba desde los snippets y nunca abria un documento: ganaba
    donde el resumen alcanzaba (enumerar roles, u=1,00) y sacaba **0,00 en las nueve
    replicas** de la celda mas simple del corpus —una unidad, un numero de cuenta— porque
    el resumen no trae el numero.

    LO ENCONTRO EL CAMINO PERFECTO A MANO, no un test: predije `rewoo` para esa celda
    porque no hay nada que buscar, dio cero, y la contradiccion entre «deberia ser trivial»
    y «da cero» fue lo que obligo a mirar.

    Y EL ORDEN IMPORTA, que fue el segundo defecto —mio, al arreglar el primero—: los
    resultados vienen RANKEADOS, y con `MAX_BATCH_READ` recortando, invertirlos no
    reordena: DESCARTA los mejores.
    """
    import json
    from app.paradigms.modern import ARGS_DE_ID, _ids_de
    from app.tools import MAX_BATCH_READ

    print("\n--- 68. un argumento de identificador recibe ids, no texto ---")

    busqueda = json.dumps({"results": [
        {"unit_id": f"memo-{i:03d}", "summary": "texto largo que no es un id"}
        for i in range(12)]})

    ids = _ids_de(busqueda).split(",")
    ok &= check("extrae los `unit_id` de una salida de busqueda",
                ids[0] == "memo-000" and all(i.startswith("memo-") for i in ids))
    ok &= check("CONSERVA el orden del ranking — recortar sobre una lista invertida "
                "descarta los mejores, no reordena",
                ids[:3] == ["memo-000", "memo-001", "memo-002"])
    ok &= check(f"y recorta en `MAX_BATCH_READ` ({MAX_BATCH_READ})",
                len(ids) == MAX_BATCH_READ)

    # SIN IDS, CADENA VACIA: un paso de lectura sin nada que leer tiene que fallar visible,
    # no leer cualquier cosa.
    ok &= check("una salida sin ids da vacio, no basura",
                _ids_de("no soy json") == "" and _ids_de('{"results":[]}') == "")

    ok &= check("`unit_ids` esta declarado como argumento de identificador",
                "unit_ids" in ARGS_DE_ID)

    # LA SUSTITUCION, sobre el codigo: un arg de id recibe ids y los demas texto.
    fuente = Path("app/paradigms/modern.py").read_text(encoding="utf-8")
    ok &= check("la sustitucion distingue por NOMBRE de argumento",
                "if k in ARGS_DE_ID" in fuente)
    ok &= check("y admite `#E1.ids` explicito, que es lo que un plan bien escrito dice",
                '#{key}.ids' in fuente)
    ok &= check("el prompt del plan lo explica, o el modelo no puede aprovecharlo",
                "resolves to the unit ids" in fuente)
    return ok


def check_effort_ceilings_bind(ok: bool) -> bool:
    """§67: el techo total de cada patron esta NOMBRADO, y ata contra lo observado.

    DOS DEFECTOS QUE ESTO CIERRA, los dos encontrados desafiando las guardas:

    1. NINGUN NOMBRE ACOTABA EL TOTAL. Cada constante acotaba una parte y la suma era
       emergente. Deduje el techo de `supervisor` multiplicando sus constantes —4 x 3 = 12—
       y el real es **17**, porque el patron hace ademas una llamada de plan por despacho y
       una final que ninguna constante nombraba. La formula estaba solo en la forma del
       codigo, y por eso la medi mal.

    2. UN TECHO QUE NUNCA SE ALCANZA NO ES UN TECHO. El de `dag_strategy` era 160 y el
       maximo observado en 138 celdas es 19: ocho veces por encima de todo lo que pasa. Un
       tope asi no restringe nada y esconde lo que realmente corta al patron, que es el
       umbral de rendimiento decreciente.

    QUE EXIGE: que cada techo declarado este por encima de lo observado —o seria una
    guarda que el registro viola— y **no absurdamente por encima**, o seria decoracion.
    """
    from app import guards as G

    print("\n--- 67. los techos de esfuerzo estan nombrados y atan ---")

    ok &= check("hay un techo total nombrado por patron con sub-agentes",
                set(G.TECHO_LLAMADAS) >= {"rewoo", "handoff", "supervisor",
                                          "dag_strategy"})
    ok &= check("el de `supervisor` incluye sus llamadas propias: "
                "DISPATCHES x (1 + TURNS) + 1, que su producto ingenuo no da",
                G.TECHO_LLAMADAS["supervisor"]
                == G.SUPERVISOR_DISPATCHES * (1 + G.SUPERVISOR_TURNS_PER_SUB) + 1)
    ok &= check("y el de `rewoo` es estructural: dos llamadas, planificar y resolver",
                G.TECHO_LLAMADAS["rewoo"] == 2)

    # CONTRA EL REGISTRO ENTERO, y ese "entero" es el tercer defecto que esto cierra.
    #
    # Miraba UN archivo —`results/luna/gold_h1_rows.jsonl`— que es exactamente el archivo
    # del que habian salido los numeros de los techos. **Un umbral calibrado sobre una
    # muestra y verificado contra esa misma muestra no puede fallar.** Medido al ampliar el
    # barrido: el techo de `dag_strategy` valia 24 porque el maximo de `gold_h1` es 19, y
    # sobre el registro completo el maximo es **38** — la guarda estaba violada por 858
    # filas y este chequeo la daba por buena.
    #
    # Es la misma forma que ya tuvo `_potencia_corpus.py`, cuyo umbral de 1,0 aprobaba al
    # corpus que lo habia motivado. Un test que solo mira donde ya se miro no prueba nada.
    import collections
    import glob as _glob
    from app.runner import load_rows
    obs = collections.defaultdict(int)
    vistos = 0
    for ruta in _glob.glob("results/**/*_rows.jsonl", recursive=True):
        for f in load_rows(Path(ruta)):
            if f.get("infeasible"):
                continue
            vistos += 1
            obs[f["paradigm"]] = max(obs[f["paradigm"]], f.get("calls", 0) or 0)
    if not vistos:
        ok &= check("(sin registro para contrastar: se saltea)", True)
        return ok

    viola = [f"{b}: techo {t} < observado {obs[b]}"
             for b, t in G.TECHO_LLAMADAS.items() if b in obs and obs[b] > t]
    ok &= check(f"ningun techo lo viola el registro ({viola or 'ninguno'})", not viola)

    flojos = [f"{b}: techo {t} contra maximo {obs[b]} ({t/max(obs[b],1):.0f}x)"
              for b, t in G.TECHO_LLAMADAS.items()
              if b in obs and obs[b] and t > 4 * obs[b]]
    ok &= check(f"y ninguno es decoracion — mas de 4x sobre lo observado "
                f"({flojos or 'ninguno'})", not flojos)

    # LA VENTANA ESCALA CON EL ALCANCE cuando se balancea, y no cuando no.
    ok &= check("apagado, la ventana es la historica y el registro sigue comparable",
                all(G.ventana_sub_agente(n, False) == G.SUPERVISOR_SCOPE_UNITS
                    for n in (1, 5, 20, 60)))
    ok &= check("encendido, escala: un alcance de 60 no se mira con la misma ventana "
                "que uno de 5",
                G.ventana_sub_agente(60, True) > G.ventana_sub_agente(5, True))
    ok &= check("y nunca deja de aislar: sobre 60 unidades no ve mas que una fraccion",
                G.ventana_sub_agente(60, True) < 60)

    # `None` NO ES UN NUMERO GRANDE. Distinguir «sin tope» de «tope alto» es la misma
    # distincion que la factibilidad hace entre `None` y `0` en sus proyecciones.
    ok &= check("sin balance no hay tope de esfuerzo, y se dice con `None`",
                G.presupuesto_de_esfuerzo(60_000, False) is None)
    ok &= check("con balance, el tope sale del presupuesto DECLARADO de la tarea",
                G.presupuesto_de_esfuerzo(60_000, True) == 60_000)
    return ok


def check_guard_policy_is_central(ok: bool) -> bool:
    """§66: los limites de los patrones viven en UN lugar, y siguen viviendo ahi.

    DE DONDE SALE. Los diecisiete numeros que gobiernan el catalogo estaban cada uno en el
    archivo de su patron. Cada uno se leia solo y ninguno se podia comparar — y TRES de
    ellos son la misma decision tomada tres veces: `handoff` corta el alcance en 2,
    `dag_strategy` en 4 sub-preguntas, `supervisor` despacha 4 veces sobre ventanas de 8.
    Tres respuestas a «¿en cuantos pedazos se corta esto?», elegidas por separado, en tres
    archivos, y ninguna medida jamas como factor.

    LA MUDANZA NO CAMBIO NINGUN VALOR, y este test lo fija: `app/guards.py` define, cada
    patron importa, y el alias local conserva el nombre viejo para que ningun sitio de uso
    cambie. Una mudanza que altera comportamiento no es una mudanza.

    QUE IMPIDE HACIA ADELANTE: que el proximo patron defina su tope en su propio archivo.
    El barrido busca asignaciones numericas de nombre en MAYUSCULAS dentro de
    `app/paradigms/`, que es la forma que tiene una guarda.
    """
    import re
    from app import guards

    print("\n--- 66. la politica de guardas esta centralizada ---")

    # Ningun archivo de patron define un numero de guarda por su cuenta.
    sueltas = []
    for f in sorted(Path("app/paradigms").glob("*.py")):
        if f.name in ("__init__.py", "_diagramas.py", "parsing.py", "blackboard.py"):
            continue
        for linea in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^([A-Z][A-Z_]{3,})\s*(?::\s*\w+\s*)?=\s*([0-9][0-9_.]*)\s*$",
                         linea)
            if m:
                sueltas.append(f"{f.name}:{m.group(1)} = {m.group(2)}")
    ok &= check(f"ningun patron define su propio limite numerico "
                f"({sueltas or 'ninguno'})", not sueltas)

    # Y los que se mudaron siguen valiendo lo mismo: la mudanza no toca comportamiento.
    ESPERADO = {
        "HANDOFF_SCOPES": 2, "DAG_SUB_QUESTIONS": 4, "SUPERVISOR_DISPATCHES": 4,
        "SUPERVISOR_SCOPE_UNITS": 8, "GRAPH_WALK_DEPTH": 2, "SCAN_CHUNK_TOKENS": 6_000,
        "HANDOFF_TURNS_PER_AGENT": 6, "SUPERVISOR_TURNS_PER_SUB": 3,
        "DAG_SUB_AGENT_ITERATIONS": 10, "REWOO_PLAN_STEPS": 8,
        "DAG_REPLAN_ITERATIONS": 3, "DAG_READY_THRESHOLD": 0.8,
        "DAG_DIMINISHING_RETURNS": 0.05, "SCAN_CARRY_CHARS": 6_000,
        "CHASE_LEDGER_FACT_CHARS": 400, "REWOO_EVIDENCE_ITEM_CHARS": 32_000,
        "REWOO_SUBSTITUTION_CHARS": 800,
    }
    mal = [f"{k}={getattr(guards, k, None)} (esperado {v})"
           for k, v in ESPERADO.items() if getattr(guards, k, None) != v]
    ok &= check(f"los {len(ESPERADO)} valores son los de antes de la mudanza "
                f"({mal or 'todos'})", not mal)

    # Los alias siguen resolviendo, o sea que los sitios de uso no cambiaron.
    import importlib
    alias = [("app.paradigms.dag", "DAG_MAX_SUB_QUESTIONS", 4),
             ("app.paradigms.handoff", "SCOPES", 2),
             ("app.paradigms.supervisor", "SUB_SCOPE_UNITS", 8),
             ("app.paradigms.modern", "MAX_PLAN_STEPS", 8)]
    rotos = [n for mod, n, v in alias
             if getattr(importlib.import_module(mod), n, None) != v]
    ok &= check(f"los alias locales siguen resolviendo ({rotos or 'todos'})", not rotos)

    # LA TABLA TIENE QUE DECIR POR QUE, no solo cuanto. Un numero sin motivo es lo que
    # habia antes, con mejor direccion postal.
    doc = Path("app/guards.py").read_text(encoding="utf-8")
    ok &= check("y el modulo explica que gobierna cada grupo, no solo el valor",
                doc.count("# ─") >= 5 and "MISMA decisión tomada tres veces" in doc)
    return ok


def check_every_module_and_class_declares_itself(ok: bool) -> bool:
    """§65: todo modulo y toda clase de `app/` dicen QUE SON. La spec vive en el codigo.

    POR QUE ES UN TEST Y NO UNA CONVENCION. Este repo se lee mas de lo que se escribe: la
    mitad de los defectos de hoy —el board que no llegaba a nadie, el guard que no
    disparaba, el agotamiento invisible en un sub-agente— se encontraron LEYENDO, y una
    clase sin docstring es una que nadie puede auditar sin reconstruirla de memoria.

    Al 2026-08-29 faltaban **20 clases**, entre ellas `Row` y `Runner`: la unidad del
    registro y la clase que lo produce. Estaban sin declarar y todo el resto del repo las
    referencia.

    QUE EXIGE, Y QUE NO. Exige que exista y que no sea un renglon de compromiso —«hace X»
    no es una spec—. No exige que sea correcta: eso no lo puede saber un test, se sabe
    leyendo, y para eso tiene que estar escrita.
    """
    import ast

    # Una clase de mas de 80 lineas es MAQUINARIA, no un registro de datos, y tiene que
    # decir que hace, que decide, y que NO hace. 250 caracteres es un parrafo: el piso mas
    # bajo con el que se puede decir las tres cosas.
    GRANDE, SPEC_MINIMA = 80, 250

    print("\n--- 65. todo modulo y toda clase declaran que son ---")

    sin_modulo, sin_clase, cortas = [], [], []
    modulos = clases = 0
    for f in sorted(Path("app").rglob("*.py")):
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        modulos += 1
        doc = ast.get_docstring(arbol)
        if not doc:
            sin_modulo.append(str(f))
        for n in ast.walk(arbol):
            if not isinstance(n, ast.ClassDef):
                continue
            clases += 1
            d = ast.get_docstring(n)
            if not d:
                sin_clase.append(f"{f.name}:{n.name}")
            elif n.end_lineno - n.lineno > GRANDE and len(d) < SPEC_MINIMA:
                # EL PISO LO FIJA EL TAMANO DE LA CLASE, no un numero plano, y la primera
                # version de esta guarda lo tenia plano y estaba mal. Un renglon alcanza
                # para `AlreadyRunning` —una excepcion— o para `Link`, y NO alcanza para
                # `ToolSurface`, que tenia 778 lineas y 70 caracteres de documentacion.
                #
                # Exigirle prosa a un contenedor de tres campos produce comentarios de
                # relleno, que es peor que no tenerlos: le enseñan al lector que la
                # documentacion de este repo no dice nada.
                cortas.append(f"{f.name}:{n.name} "
                              f"({n.end_lineno - n.lineno} lineas, {len(d)} chars)")

    ok &= check(f"los {modulos} modulos de `app/` tienen docstring "
                f"({sin_modulo or 'ninguno falta'})", not sin_modulo)
    ok &= check(f"las {clases} clases tambien ({sin_clase or 'ninguna falta'})",
                not sin_clase)
    ok &= check(f"y ninguna clase de mas de {GRANDE} lineas se despacha con un renglon "
                f"({cortas or 'ninguna'})", not cortas)
    return ok


def check_surface_version_guards_the_sensitive_arms(ok: bool) -> bool:
    """§64: la QUINTA guarda de mezcla — la version de la superficie, y es POR BRAZO.

    `X-8` cambio comportamiento medido: un sub-agente ahora VE el agotamiento del
    retriever, y antes arrancaba creyendo que nadie habia buscado nada. **Ninguna de las
    cuatro guardas anteriores lo detecta** —miran decodificacion, brazo de recuperacion,
    analizador y vocabulario de region— y la huella tampoco lo lleva: es modelo, api,
    esfuerzo, seed y max. Un `.jsonl` habria mezclado dos regimenes en silencio.

    POR BRAZO Y NO POR ARCHIVO, y esa es la decision que la vuelve usable: `scoped()` lo
    llaman `handoff` y `supervisor` y nadie mas. Levantar sobre el archivo entero
    convertiria un registro valido de 900 filas en inservible por un cambio que a diez de
    los doce brazos no los toca — y una guarda asi se termina desactivando, que es peor
    que no tenerla.
    """
    import json
    import tempfile
    from app.runner import load_rows
    from app.tools import SURFACE_SENSITIVE_ARMS, SURFACE_VERSION

    print("\n--- 64. la version de la superficie, guardada por brazo ---")

    def escribir(filas):
        f = Path(tempfile.mkdtemp()) / "r.jsonl"
        f.write_text("\n".join(json.dumps(x) for x in filas), encoding="utf-8")
        return f

    base = {"task_id": "t", "fingerprint": "A", "region_vocabulary": "V1",
            "analyzer": "v2-stopwords"}
    viejo = dict(base, paradigm="handoff")
    nuevo = dict(base, task_id="u", paradigm="handoff",
                 surface_version=SURFACE_VERSION)

    ok &= check("`handoff` y `supervisor` son los brazos sensibles, y son los que llaman "
                "a `scoped()`",
                set(SURFACE_SENSITIVE_ARMS) == {"handoff", "supervisor"})
    ok &= check("un archivo todo del regimen viejo se lee sin quejarse: la AUSENCIA del "
                "campo no levanta sola", len(load_rows(escribir([viejo, dict(viejo, task_id='v')]))) == 2)
    ok &= check("y uno todo del nuevo tambien",
                len(load_rows(escribir([nuevo, dict(nuevo, task_id='w')]))) == 2)
    try:
        load_rows(escribir([viejo, nuevo]))
        ok &= check("mezclar versiones en un brazo sensible levanta", False)
    except ValueError as exc:
        ok &= check("mezclar versiones en un brazo sensible levanta, y dice cual",
                    "handoff" in str(exc) and "superficie" in str(exc).lower())

    # LO QUE LA GUARDA NO PUEDE HACER: voltear el registro por brazos que no cambiaron.
    r_viejo = dict(base, paradigm="react")
    r_nuevo = dict(base, task_id="u", paradigm="react", surface_version=SURFACE_VERSION)
    ok &= check("un brazo NO sensible mezcla versiones sin levantar: el cambio no lo "
                "toca, y voltear 900 filas por eso vuelve inutil a la guarda",
                len(load_rows(escribir([r_viejo, r_nuevo]))) == 2)

    # Y UNA INFACTIBLE NO DECLARA SUPERFICIE PORQUE NO EJECUTO — el mismo matiz que la
    # guarda del analizador tuvo que aprender.
    inf = dict(base, task_id="z", paradigm="handoff", infeasible=True)
    ok &= check("una fila infactible no cuenta: no ejecuto, no tiene superficie que "
                "declarar", len(load_rows(escribir([nuevo, inf]))) == 2)
    return ok


def check_retriever_exhaustion_is_of_the_task(ok: bool) -> bool:
    """§63: el agotamiento del retriever es de la TAREA, no del sub-agente.

    LO ENCONTRO EL REGISTRO, con un cero que no era chico sino estructural:

        supervisor    370 busquedas,   0 esteriles   (0,0%)
        handoff       158 busquedas,   0 esteriles   (0,0%)
        dag_strategy  661 busquedas, 413 esteriles  (62,5%)

    `scoped()` reata por REFERENCIA todo lo que es de la tarea, y no reataba `surfaced`
    —lo que alguna busqueda ya trajo— ni los contadores de racha. Asi que cada
    sub-agente arrancaba con el conjunto vacio y **toda busqueda suya parecia traer algo
    nuevo**, aunque el padre ya la hubiera hecho. Los `int` ademas no se pueden reatar:
    `replace` los copia por valor, asi que ahora viven en un objeto.

    Y NO ES SOLO CONTABILIDAD. El aviso «las ultimas N busquedas no trajeron nada nuevo»
    —la senal que midio 3,05x de reduccion de costo, el resultado mas fuerte del banco—
    no podia dispararse adentro de un sub-agente. Ese resultado esta medido solo sobre
    los brazos que NO descomponen, y los que descomponen son los que mas buscan.
    """
    from app.retrieval import CorpusView
    from app.tools import ToolSurface

    print("\n--- 63. el agotamiento del retriever es de la tarea ---")

    docs = {f"u{i}": "texto " * 50 for i in range(6)}
    def superficie():
        v = CorpusView(task_id="t", documents=docs, unit_ids=list(docs),
                       relevant_units=["u0"])
        return ToolSurface(view=v, hybrid=None, semantic=None, lexical=None,
                           variant="basic", budget_tokens=50_000)

    s = superficie()
    s._note_search(["u0", "u1"])
    ok &= check("una busqueda que trae algo nuevo no cuenta como esteril",
                s.barren_total == 0 and s.barren_searches == 0)
    s._note_search(["u0"])
    ok &= check("repetir lo ya visto SI cuenta", s.barren_total == 1)

    sub = s.scoped(["u2", "u3"])
    ok &= check("el sub-agente comparte `surfaced`: lo que el padre ya vio, ya esta visto",
                sub.surfaced is s.surfaced)
    ok &= check("y comparte los contadores POR REFERENCIA — un `int` no se puede reatar, "
                "`replace` lo copia por valor", sub.barren is s.barren)

    sub._note_search(["u0"])
    ok &= check("una busqueda del sub que repite lo del padre es ESTERIL, y antes "
                "parecia nueva", s.barren_total == 2)
    sub._note_search(["u2"])
    ok &= check("y lo que el sub descubre vuelve al padre: sin eso, el padre repetiria "
                "la busqueda que su sub-agente ya hizo", "u2" in s.surfaced)
    ok &= check("la racha del padre se reinicia cuando el SUB encuentra algo",
                s.barren_searches == 0)

    fuente = Path("app/tools.py").read_text(encoding="utf-8")
    ok &= check("y queda atado en `scoped`, que es el unico sitio donde olvidarlo es "
                "invisible", "sub.surfaced = self.surfaced" in fuente
                and "sub.barren = self.barren" in fuente)
    return ok


def check_guard_bounds_and_rescues(ok: bool) -> bool:
    """§62: el guard acota la ventana y RESCATA lo que expulsa — la otra mitad del board.

    LAS DOS COMPACTACIONES QUE YA HABIA **DEGRADAN**: `compact_history` a un stub y solo
    para lo que el modelo anoto (1 nota en 28 filas), `manage_history` a un gist
    incondicional (61 llamadas sobre `w4`, 0 mensajes degradados). Ninguna **produce**
    contenido nuevo. Y sin produccion el board sostiene solo lo que el modelo se acuerde
    de postear: 1 de cada 125 llamadas.

    EL TEST PRUEBA EL MECANISMO Y LO QUE NO SE PUEDE TOCAR: que dispare por CRECIMIENTO y
    no por tamano absoluto —un umbral absoluto castiga al que lee mucho de entrada y no
    toca al que crece despacio hasta el mismo lugar—, que expulse DE A UNO, que no se
    coma el prompt ni el batch corriente, y que la extraccion **se cobre**.
    """
    from app.board import Blackboard
    from app.context_guard import ContextGuard
    from app.llm import Usage

    print("\n--- 62. el guard acota por crecimiento y rescata el hallazgo ---")

    class _Falso:
        """Un cliente que devuelve lo que se le dice y cobra lo que se le dice."""

        def __init__(self, texto, tokens=50):
            self.texto, self.tokens, self.llamadas = texto, tokens, 0

        def complete(self, messages, **kw):
            self.llamadas += 1
            self.visto = messages[0]["content"]
            return SimpleNamespace(
                text=self.texto,
                usage=Usage(prompt_tokens=self.tokens, completion_tokens=10),
                tool_calls=None,
            )

    from types import SimpleNamespace

    g = ContextGuard(threshold=1_000)
    ok &= check("la primera mirada sobre una ventana grande YA es crecimiento",
                g.needs_eviction([{"content": "x" * 5_000}]))
    ok &= check("y sin crecimiento no dispara aunque la ventana siga siendo grande",
                not g.needs_eviction([{"content": "x" * 5_100}]))

    def conversacion():
        return [
            {"role": "system", "content": "sos un agente"},
            {"role": "user", "content": "quien firmo el memo"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "1"}]},
            {"role": "tool", "content": "A" * 8_000},
            {"role": "tool", "content": "B" * 8_000},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "2"}]},
            {"role": "tool", "content": "C" * 8_000},
        ]

    msgs, board, usage = conversacion(), Blackboard(), Usage()
    cli = _Falso("Lo firmo M. Cavallero el 3 de marzo.")
    g = ContextGuard(threshold=1_000)
    ok &= check("expulsa y deja el hallazgo EN EL BOARD",
                g.evict(msgs, board, cli, "quien firmo el memo", usage)
                and len(board.findings) == 1
                and "Cavallero" in board.findings[0])
    ok &= check("y la extraccion SE COBRA: un ahorro que no cuenta lo que gasta no se "
                "puede evaluar", usage.prompt_tokens == 50)
    ok &= check("expulso UNO, no la ventana: vaciarla de golpe le saca al modelo el "
                "batch sobre el que todavia no razono",
                sum(1 for m in msgs if len(str(m.get("content") or "")) > 1_000) == 2)
    ok &= check("no toca el prompt ni la pregunta",
                msgs[0]["content"] == "sos un agente"
                and msgs[1]["content"] == "quien firmo el memo")
    ok &= check("ni el batch corriente — el que sigue al ultimo assistant con tool calls",
                msgs[-1]["content"] == "C" * 8_000)
    ok &= check("la extraccion ve la PREGUNTA: sin ella el resumen seria generico, que "
                "es lo que la expulsion no se puede permitir",
                "quien firmo el memo" in cli.visto)

    # NO HABER ENCONTRADO NADA ES UN DATO SOBRE LA RECUPERACION, no un no-evento.
    msgs2, board2, usage2 = conversacion(), Blackboard(), Usage()
    g2 = ContextGuard(threshold=1_000)
    g2.evict(msgs2, board2, _Falso("NOTHING"), "otra pregunta", usage2)
    ok &= check("un texto que no aporta se marca y NO ensucia el board",
                not board2.findings and g2.nothing == 1 and g2.extracted == 0)
    ok &= check("los numeros salen separados: expulsiones, rescates y vacios",
                g2.as_dict() == {"evictions": 1, "extracted": 0,
                                 "evicted_nothing": 1, "extraction_failed": 0})

    # UNA EXTRACCION QUE FALLA NO ES UN TEXTO IRRELEVANTE, y el probe sobre el corpus las
    # encontro en el mismo contador. Son opuestas: «no aporta» habla del RETRIEVER, «no
    # devolvio nada» habla del extractor. Y una falla NO puede borrar evidencia.
    msgs3, board3, usage3 = conversacion(), Blackboard(), Usage()
    g3 = ContextGuard(threshold=1_000)
    g3.evict(msgs3, board3, _Falso(""), "otra pregunta", usage3)
    ok &= check("una extraccion vacia se cuenta aparte de un texto irrelevante",
                g3.as_dict()["extraction_failed"] == 1
                and g3.as_dict()["evicted_nothing"] == 0)
    ok &= check("y NO borra el texto: perder evidencia por una falla del extractor es "
                "el dano exacto que este mecanismo existe para evitar",
                msgs3[3]["content"] == "A" * 8_000)

    # EL FACTOR LLEGA, por los mismos caminos donde el board se habia perdido.
    from app.tools import ToolSurface
    ok &= check("`context_guard` y `question` son campos de la superficie",
                "context_guard" in ToolSurface.__dataclass_fields__
                and "question" in ToolSurface.__dataclass_fields__)
    bucle = Path("app/paradigms/__init__.py").read_text(encoding="utf-8")
    ok &= check("corre en el bucle compartido, ANTES de inyectar el board: al reves el "
                "modelo veria un board una vuelta atrasado respecto de la ventana",
                bucle.index("guard.evict(") < bucle.index("board_state.inject("))
    fuente = Path("app/tools.py").read_text(encoding="utf-8")
    ok &= check("el sub-agente hereda guard y pregunta",
                "sub.context_guard = self.context_guard" in fuente
                and "sub.question = self.question" in fuente)
    ok &= check("y sus numeros llegan a la FILA: un mecanismo cuyo efecto no llega al "
                "registro se evalua adivinando",
                'f"guard_{k}"' in fuente and '"board_pending"' in fuente)
    runner = Path("app/runner.py").read_text(encoding="utf-8")
    ok &= check("el runner lo propaga con la pregunta de la tarea, y lo declara en el "
                "nombre del archivo",
                'question=task["question"]' in runner and "_guard" in runner)
    return ok


def check_board_carries_what_is_left(ok: bool) -> bool:
    """§61: un board puede llevar lo ACUMULADO o lo que FALTA, y son dos mecanismos.

    DE DONDE SALE. El board del banco era un log de hallazgos: `findings`,
    `visited_units`, y un `tool_calls` que el docstring prometia como «ledger para evitar
    trabajo duplicado» y **que no escribia nadie ni renderizaba nada**. La capa de
    ejecucion anterior —congelada, la unica que corrio contra un indice real— llevaba lo
    otro: cola de pendientes, cobertura `N/M`, lista de consultas ya emitidas, y una
    directiva DERIVADA del numero.

    Y ESA MITAD ES LA QUE LA MEDICION RESPALDA: el 3,05× de las senales de contabilidad
    salio de decir «no viene nada nuevo», que es una afirmacion sobre el trabajo
    RESTANTE. Un board que solo acumula no puede decir cobertura porque no tiene
    denominador, y sin cobertura no puede emitir una directiva.

    EL TEST PRUEBA EL MECANISMO Y LAS DOS TRAMPAS QUE LO RODEAN: que apagado el render
    sea IDENTICO al de antes (o el registro medido deja de ser comparable), y que el
    factor LLEGUE —`offer_board` se corrio entero midiendo cero porque no llegaba a la
    declaracion de tools, y un campo que no llega al render falla igual de callado—.
    """
    from app.board import Blackboard
    from app.tools import ToolSurface

    print("\n--- 61. el board lleva lo que falta, no solo lo que paso ---")

    b = Blackboard()
    ok &= check("apagado, un board vacio dice lo de siempre",
                b.render() == "(blackboard empty — you are the first agent)")
    b.add_finding("a", "encontre X")
    ok &= check("apagado, el render es el de antes — byte por byte, o el registro "
                "medido deja de ser comparable",
                b.render() == "FINDINGS SO FAR (from parallel agents):\n  [a] encontre X")
    b.seed(["u1", "u2"])
    ok &= check("y sembrar la cola con el modo apagado no cambia una coma",
                b.render() == "FINDINGS SO FAR (from parallel agents):\n  [a] encontre X")

    q = Blackboard(queue_mode=True)
    q.seed(["u1", "u2", "u3"])
    q.seed(["u1"])
    ok &= check("sembrar dos veces no duplica: el denominador tiene que ser estable",
                len(q.pending) == 3)
    ok &= check("cobertura con denominador", "0/3 items checked" in q.render())
    ok &= check("y la directiva sale DERIVADA del numero, no suelta",
                q.render().endswith("3 items remaining. Try DIFFERENT queries."))

    ok &= check("una llamada nueva se asienta", q.record_tool_call("search", "quien"))
    ok &= check("y la repetida se detecta — el campo estaba declarado y muerto",
                not q.record_tool_call("search", "quien"))
    ok &= check("y ahora SI se renderiza, que es la mitad que faltaba",
                "do NOT repeat" in q.render() and "search(quien)" in q.render())

    ok &= check("cerrar un pendiente lo cierra", q.close("u1", "lo encontre"))
    ok &= check("cerrar dos veces el mismo NO vuelve a contar", not q.close("u1"))
    q.close("u2"); q.close("u3")
    ok &= check("y con todo cerrado la directiva cambia de sentido",
                q.render().endswith("All items checked. Write your final answer."))

    # CERRAR NO ABRE, que es la trampa que la capa anterior pago: anotar un hallazgo y
    # abrir una pista eran una sola llamada, asi que registrar algo YA SABIDO bajaba la
    # cobertura y disparaba mas insistencia.
    antes = q.pending_count
    q.add_finding("a", "otra cosa que ya sabia")
    ok &= check("anotar un hallazgo NO abre un pendiente: una senal de contabilidad "
                "tiene que ser monotona, o castiga al agente por reportar lo que sabe",
                q.pending_count == antes)

    # EL FACTOR LLEGA. Dos caminos, y los dos fallaron antes en este repo por separado.
    ok &= check("`board_queue` es un campo de la superficie",
                "board_queue" in ToolSurface.__dataclass_fields__)
    fuente = Path("app/tools.py").read_text(encoding="utf-8")
    ok &= check("el sub-agente lo hereda: un factor que muere en el reparto mide su "
                "propia ausencia", "sub.board_queue = self.board_queue" in fuente)
    ok &= check("el dispatch asienta la llamada, y ANTES de la comprobacion de "
                "disponibilidad", "self.board_state.record_tool_call(" in fuente)
    ok &= check("y la cola se cierra en los TRES caminos de lectura, no en uno",
                fuente.count("self._close_queue(") == 3)
    # LA COLA ES GENERAL, NO DE `dag`. Un agente solo tiene el mismo problema que un
    # grupo: no sabe que le falta, no sabe que ya pidio, y su transcripcion se compacta.
    # Que el estado sea COMPARTIDO entre varios o PROPIO de uno es otra dimension.
    b = Blackboard(queue_mode=True)
    b.seed(["u1", "u2"])
    msgs = [{"role": "system", "content": "sos un agente"},
            {"role": "user", "content": "la pregunta"}]
    ok &= check("el board se inyecta en la conversacion de cualquier agente",
                b.inject(msgs) and len(msgs) == 3
                and "Coverage: 0/2" in msgs[-1]["content"])
    b.close("u1")
    b.inject(msgs)
    ok &= check("y REEMPLAZA en vez de apilar: N copias desactualizadas, la mas vieja "
                "arriba, y el costo crece con el cuadrado de las vueltas",
                len(msgs) == 3 and "Coverage: 1/2" in msgs[-1]["content"])
    ok &= check("un board vacio no inyecta nada", not Blackboard(queue_mode=True).inject([]))

    bucle = Path("app/paradigms/__init__.py").read_text(encoding="utf-8")
    ok &= check("y se inyecta en el BUCLE COMPARTIDO, que es el unico del repo que manda "
                "la declaracion de tools — inyectar ahi alcanza a todo paradigma "
                "iterativo, no solo a `dag_strategy`",
                "surface.board_state.inject(messages)" in bucle)
    dag = Path("app/paradigms/dag.py").read_text(encoding="utf-8")
    ok &= check("la cola NO depende de la plantilla de `dag`: ese camino sigue existiendo "
                "para su board estructural, y no es por donde la cola llega",
                "blackboard=board.render()" in dag)

    runner = Path("app/runner.py").read_text(encoding="utf-8")
    ok &= check("el runner lo propaga y siembra la cola desde el CODIGO",
                "board_queue=self.board_queue" in runner
                and "surface.board_state.seed(" in runner)
    ok &= check("y el archivo de resultados lo declara en su nombre: dos regimenes en "
                "un mismo `.jsonl` es la mezcla que ninguna guarda ve",
                '"_boardqueue"' in runner or "_boardqueue" in runner)
    return ok


def check_learning_discriminates_non_measurements(ok: bool) -> bool:
    """§60: lo que no es una medicion no entra al aprendizaje, y hay UN solo porton.

    HABIA TRES CONSTRUCTORES DE EPISODIOS CON TRES FILTROS. Los dos scripts de analisis
    descartaban infactibles y de infraestructura; `Runner.episodes()` —el camino del
    PRODUCTO— descartaba solo las de infraestructura. La guarda vivia en el banco y le
    faltaba al producto, que es la inversion exacta de la regla del repo.

    Y LO QUE COLABA NO ERA MARGINAL, medido sobre la campana del 2026-08-29: 39 de 180
    episodios (21,7%) venian de celdas que nunca ejecutaron. El sesgo no es aleatorio —cae
    sobre los brazos caros, que son los que la poda alcanza— y lo grave es el CONTEO: los
    episodios son lo que cruza el piso de confianza, asi que un par podia ganar confianza
    con celdas donde el brazo nunca corrio.

    EL TEST PRUEBA EL MECANISMO, NO EL DEFECTO DEL DIA: que cada clase se descarte por su
    propio motivo, que se CUENTE en vez de desaparecer, y —lo que evita el error opuesto—
    que un fracaso ejecutado SI entre.
    """
    from app.policy import Discarded, learnable_rows

    print("\n--- 60. el aprendizaje discrimina lo que no es una medicion ---")

    base = {"task_id": "t", "paradigm": "p", "region": "R", "utility": 1.0,
            "answer": "42", "cost_tokens": 10}
    filas = [
        base,
        dict(base, task_id="u", infra_error=True),
        dict(base, task_id="v", infeasible=True, utility=0.0, answer=""),
        dict(base, task_id="w", region=""),
    ]
    aptas, d = learnable_rows(filas)
    ok &= check("las tres clases se descartan, cada una por su motivo",
                len(aptas) == 1 and d.infra == 1 and d.infactible == 1
                and d.sin_region == 1 and d.total == 3)
    ok &= check("y se CUENTAN: un filtro silencioso es la version peor del problema",
                "descartadas" in str(d) and "3" in str(d) and d.filas == 1)
    ok &= check("sin nada que descartar lo dice, no calla",
                learnable_rows([base])[1].total == 0)

    # EL ERROR OPUESTO, y es el que un filtro entusiasta comete: entrenar solo con exitos.
    fracasos = [dict(base, task_id="x", utility=0.0, answer=""),          # ejecuto y fallo
                dict(base, task_id="y", utility=0.0, answer="Unknown"),   # el modelo no supo
                dict(base, task_id="z", utility=0.0, answer="7")]         # respondio mal
    aptas2, d2 = learnable_rows(fracasos)
    ok &= check("un fracaso EJECUTADO es una medicion y entra: una politica entrenada "
                "solo con exitos aprende que todo funciona",
                len(aptas2) == 3 and d2.total == 0)

    # UN SOLO PORTON: ningun constructor de episodios puede tener su propio filtro.
    # LOS CUATRO QUE APRENDEN. El de asociaciones se colaba por otra puerta: se apoyaba
    # en que una fila infactible no trae `sequence`. Es cierto y es ACCIDENTAL — la guarda
    # dependia de un campo vacio en vez de decir que la fila no ejecuto, y una guarda
    # accidental deja de valer en cuanto el campo cambia de forma.
    fuentes = [Path("app/runner.py"), Path("bench/_consolidar_vivo.py"),
               Path("bench/analysis/_analyze_tau.py"),
               Path("bench/analysis/_analyze_associations.py")]
    huella = 'get("infeasible") or f.get("infra_error")'
    propios = [f.name for f in fuentes if huella in f.read_text(encoding="utf-8")]
    ok &= check("ningun constructor de episodios filtra por su cuenta "
                f"(sospechosos: {propios or 'ninguno'})", not propios)
    for f in fuentes:
        ok &= check(f"{f.name} pasa por `learnable_rows`",
                    "learnable_rows" in f.read_text(encoding="utf-8"))
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
    ok = check_stochasticity_confinement(ok)
    ok = check_the_code_draws_the_graph(ok)
    ok = check_retrieval_is_a_factor(ok)
    ok = check_board_is_a_tool_for_everyone(ok)
    ok = check_coverage_precondition_abstains(ok)
    ok = check_model_pool(ok)
    ok = check_tariffs_are_data(ok)
    ok = check_second_policy(ok)
    ok = check_two_kinds_of_reading(ok)
    ok = check_estimates_come_from_the_corpus(ok)
    ok = check_factors_reach_the_model(ok)
    ok = check_ingest_is_its_own_measurement(ok)
    ok = check_every_paradigm_runs_offline(ok)
    ok = check_no_factor_is_unreachable(ok)
    ok = check_mixed_model_execution_is_measurable(ok)
    ok = check_learning_discriminates_non_measurements(ok)
    ok = check_board_carries_what_is_left(ok)
    ok = check_guard_bounds_and_rescues(ok)
    ok = check_retriever_exhaustion_is_of_the_task(ok)
    ok = check_surface_version_guards_the_sensitive_arms(ok)
    ok = check_every_module_and_class_declares_itself(ok)
    ok = check_guard_policy_is_central(ok)
    ok = check_effort_ceilings_bind(ok)
    ok = check_rewoo_can_actually_read(ok)
    ok = check_each_pattern_has_the_tools_it_needs(ok)
    ok = check_every_tool_works_in_isolation(ok)
    ok = check_measuring_is_not_reading(ok)
    ok = check_every_arm_has_a_named_ceiling(ok)
    ok = check_effort_balance_is_reachable(ok)
    ok = check_absence_has_a_second_proof(ok)
    ok = check_grading_scores_the_answer_not_its_wording(ok)
    ok = check_new_predictors_reach_the_decision(ok)
    ok = check_report_does_not_score_placeholders(ok)
    ok = check_gaps_that_nobody_can_close(ok)
    ok = check_hyde_branch_is_separable(ok)
    ok = check_surfacing_is_recorded_apart_from_reading(ok)
    ok = check_noise_floor_detects_a_real_prize(ok)

    print("\n" + ("ALL CHECKS PASSED" if ok else "THERE ARE FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
