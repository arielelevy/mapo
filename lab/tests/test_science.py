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
         "oracle": task["oracle"], "irreversible": False, "shared_writes": False,
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

    print("\n" + ("ALL CHECKS PASSED" if ok else "THERE ARE FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
