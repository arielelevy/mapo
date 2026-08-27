"""Validate the sleep cycle, and above all that it does not confabulate.

The dangerous stage is abstraction. A search over many candidate partitions will find
something in pure noise if it is allowed to, and a discovered "truth" that is really a
multiple-comparisons artefact is worse than no discovery: it arrives wearing the
authority of evidence. So the central test here is the NEGATIVE one - given a record
where utility is independent of every attribute, the cycle must report nothing.

Run: py tests\\test_consolidation.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

# The Windows console defaults to cp1252 and raises on any non-Latin-1
# character, which turns a reporting nicety into a crash mid-suite.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.assurance import (  # noqa: E402
    Assurance,
    learn_floors,
    required_floor,
)
from app.beliefs import (  # noqa: E402
    Belief,
    BeliefBase,
    Governance,
    Provenance,
    Rejection,
    Requirement,
    Rule,
)
from app.consolidation import (  # noqa: E402
    audit_propositions,
    discover_partitions,
    homeostasis,
    prioritised_replay,
    sleep_cycle,
)
from app.policy import (  # noqa: E402
    WEIGHT_MIN,
    Episode,
    PolicyBundle,
    Stat,
    promote,
)

PARADIGMS = ["react", "map_reduce", "plan_execute"]


def check(label: str, condition: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))
    return condition


def make_rows(signal: bool, n_tasks: int = 40, seed: int = 11) -> list[dict]:
    """Build a record with, or without, a real dependence on truth_coupling.

    With signal: coupling > 0.5 favours plan_execute, otherwise map_reduce. Noise is
    added so the effect has to be found, not read off.
    Without signal: utility is drawn from the same distribution regardless of coupling,
    so any 'discovery' is an artefact.
    """
    rng = random.Random(seed)
    rows: list[dict] = []
    for i in range(n_tasks):
        coupling = round(rng.random(), 3)
        for paradigm in PARADIGMS:
            if signal:
                if coupling > 0.5:
                    base = 0.85 if paradigm == "plan_execute" else 0.55
                else:
                    base = 0.85 if paradigm == "map_reduce" else 0.55
            else:
                base = 0.7
            rows.append({
                "task_id": f"t{i:03d}",
                "paradigm": paradigm,
                "trial": 0,
                "region": "many/oracle/unknown",
                "utility": max(0.0, min(1.0, base + rng.gauss(0, 0.08))),
                "cost_tokens": 1000 + rng.randint(0, 500),
                "iterations": rng.randint(1, 6),
                "cross_unit_lookups": rng.randint(0, 5),
                "has_oracle": True,
                "truth_coupling": coupling,
            })
    return rows


def rows_to_episodes(rows: list[dict]) -> list[Episode]:
    best: dict[str, float] = {}
    for r in rows:
        best[r["task_id"]] = max(best.get(r["task_id"], 0.0), r["utility"])
    return [
        Episode(
            task_id=r["task_id"],
            region=r["region"],
            paradigm=r["paradigm"],
            utility=r["utility"],
            cost_tokens=r["cost_tokens"],
            was_best=r["utility"] >= best[r["task_id"]] - 1e-9,
        )
        for r in rows
    ]


def _belief_record(task_id: str, region: str, refused: bool) -> dict:
    """One belief-log entry, in the shape the runner writes."""
    return {
        "context": {
            "task_id": task_id,
            "region": region,
            "elicited_offered": True,
            "gate_rejections": (
                [
                    {
                        "proposition": "coupling_tight",
                        "rejection": "provenance",
                        "held": "elicited",
                        "needed": "observed",
                    }
                ]
                if refused
                else []
            ),
        }
    }


def check_assurance_floor_learns(ok: bool) -> bool:
    """Paper 6.2: a request class whose elicited assertions are repeatedly refused
    by the gate is a class whose floor should rise."""
    print("\n6. El piso de garantia que aprende (paper 6.2)")

    # --- the rejection is TYPED, not parsed out of the explanation
    base = BeliefBase()
    base.assert_(Belief(
        proposition="coupling_tight",
        value=True,
        credence=0.9,
        provenance=Provenance.ELICITED,
        evidence="the model said so",
    ))
    rule = Rule(
        name="needs_observed",
        requires=[Requirement(
            proposition="coupling_tight",
            expected=True,
            min_credence=0.7,
            min_provenance=Provenance.OBSERVED,
        )],
        then="specialise",
    )
    verdict = Governance([rule], default_action="defer").decide(base)
    refusals = verdict.gate_rejections()
    ok &= check("un rechazo por procedencia se registra TIPADO",
                len(refusals) == 1
                and refusals[0].rejection is Rejection.PROVENANCE
                and refusals[0].held is Provenance.ELICITED,
                str(refusals[0].rejection.value if refusals else "-"))
    ok &= check("un rechazo por CREDENCE no cuenta como rechazo del gate",
                not Governance([Rule(
                    name="needs_credence",
                    requires=[Requirement(
                        proposition="coupling_tight",
                        expected=True,
                        min_credence=0.99,
                        min_provenance=Provenance.ELICITED,
                    )],
                    then="specialise",
                )], default_action="defer").decide(base).gate_rejections())

    # --- una region con rechazos repetidos sube; una sin rechazos, no
    hot = [_belief_record(f"t{i}", "many/no_oracle/tight", True) for i in range(9)]
    cold = [_belief_record(f"c{i}", "few/oracle/loose", False) for i in range(9)]
    floors, notes = learn_floors(hot + cold)
    ok &= check("la region con rechazos repetidos sube el piso",
                floors.get("many/no_oracle/tight") == Assurance.ACCOUNTABLE,
                notes[0][:80] if notes else "sin notas")
    ok &= check("la region sin rechazos NO sube",
                "few/oracle/loose" not in floors)

    # --- el piso nunca llega a CERTIFIED: eso restringiria patrones
    ok &= check("el piso aprendido no alcanza CERTIFIED",
                all(level <= Assurance.ACCOUNTABLE for level in floors.values()))

    # --- pocos requests no alcanzan, por mas que la tasa sea 1.0
    few = [_belief_record(f"f{i}", "single/oracle/loose", True) for i in range(3)]
    floors_few, _ = learn_floors(few)
    ok &= check("con pocos requests no se aprende nada",
                "single/oracle/loose" not in floors_few, "3 requests")

    # --- el denominador excluye requests que nunca ofrecieron nada elicited
    silent = [
        {"context": {"task_id": f"s{i}", "region": "R", "elicited_offered": False,
                     "gate_rejections": []}}
        for i in range(50)
    ]
    hot_r = [_belief_record(f"h{i}", "R", True) for i in range(9)]
    floors_r, _ = learn_floors(silent + hot_r)
    ok &= check("los requests que no ofrecieron creencia elicited no diluyen la tasa",
                floors_r.get("R") == Assurance.ACCOUNTABLE, "9 de 9, no 9 de 59")

    # --- y el piso llega al ruteo: sube el nivel efectivo del request
    floor, reasons = required_floor(
        BeliefBase(), learned={"R": Assurance.ACCOUNTABLE}, region="R"
    )
    ok &= check("el piso aprendido eleva el nivel del request",
                floor == Assurance.ACCOUNTABLE,
                reasons[-1][:80] if reasons else "")
    floor_other, _ = required_floor(
        BeliefBase(), learned={"R": Assurance.ACCOUNTABLE}, region="OTRA"
    )
    ok &= check("y no toca a las demas regiones",
                floor_other == Assurance.EXPLORATORY)

    # --- monotono: no baja aunque el registro nuevo no muestre rechazos
    kept, _ = learn_floors(cold, incumbent={"few/oracle/loose": Assurance.ACCOUNTABLE})
    ok &= check("un piso ya aprendido no baja solo",
                kept["few/oracle/loose"] == Assurance.ACCOUNTABLE)
    return ok


def main() -> int:
    ok = True

    print("\n1. Abstraction finds a real partition")
    rows = make_rows(signal=True)
    tasks = sorted({r["task_id"] for r in rows})
    a, b = int(len(tasks) * 0.5), int(len(tasks) * 0.75)
    search = [r for r in rows if r["task_id"] in set(tasks[:a])]
    validate = [r for r in rows if r["task_id"] in set(tasks[a:b])]

    found = discover_partitions(search, validate, ("truth_coupling", "cost_tokens",
                                                   "iterations", "cross_unit_lookups"))
    survivors = [f for f in found if f.survives]
    ok &= check("something survived validation", bool(survivors),
                f"{len(survivors)} of {len(found)} candidates")
    if survivors:
        top = survivors[0]
        ok &= check("the surviving split is on truth_coupling",
                    top.attribute == "truth_coupling", top.attribute)
        ok &= check("its threshold is near 0.5",
                    0.35 <= top.threshold <= 0.65, f"{top.threshold:.3f}")
        ok &= check("and it flips the winning paradigm",
                    top.best_low != top.best_high,
                    f"{top.best_low} -> {top.best_high}")
        ok &= check("it retained separation out of sample",
                    top.retained >= 0.5, f"retained {top.retained:.2f}")

    print("\n2. ⭐ Abstraction finds NOTHING in noise (the confabulation guard)")
    noise = make_rows(signal=False, seed=99)
    ntasks = sorted({r["task_id"] for r in noise})
    na, nb = int(len(ntasks) * 0.5), int(len(ntasks) * 0.75)
    nsearch = [r for r in noise if r["task_id"] in set(ntasks[:na])]
    nvalidate = [r for r in noise if r["task_id"] in set(ntasks[na:nb])]
    spurious = [
        f for f in discover_partitions(
            nsearch, nvalidate,
            ("truth_coupling", "cost_tokens", "iterations", "cross_unit_lookups"))
        if f.survives
    ]
    ok &= check("no spurious proposition survives", not spurious,
                f"{len(spurious)} survived" if spurious else "clean")

    print("\n3. Replay is ordered by surprise, not chronology")
    cold = PolicyBundle.cold_start(fallback="react", tau=0.3)
    episodes = rows_to_episodes(rows)
    ordered = prioritised_replay(episodes, cold)
    ok &= check("all episodes retained", len(ordered) == len(episodes),
                f"{len(ordered)}")
    surprises = [
        abs(e.utility - cold.stat(e.region, e.paradigm).mean_utility) for e in ordered
    ]
    ok &= check("surprise is non-increasing",
                all(surprises[i] >= surprises[i + 1] - 1e-9
                    for i in range(len(surprises) - 1)))
    ok &= check("the order actually differs from the input",
                [e.paradigm for e in ordered] != [e.paradigm for e in episodes])

    print("\n4. Homeostasis downscales but preserves ordering, and prunes only the unused")
    stats = {
        "r1": {"react": Stat(weight=0.9, episodes=20, utility_sum=14, wins=10),
               "map_reduce": Stat(weight=0.8, episodes=15, utility_sum=9, wins=4)},
        "r2": {"cot": Stat(weight=WEIGHT_MIN, episodes=0),
               "direct": Stat(weight=WEIGHT_MIN, episodes=5, utility_sum=1, wins=0)},
    }
    before = stats["r1"]["react"].weight > stats["r1"]["map_reduce"].weight
    result = homeostasis(stats, floor=WEIGHT_MIN)
    after = stats["r1"]["react"].weight > stats["r1"]["map_reduce"].weight
    ok &= check("ordering of weights survives rescaling", before and after,
                f"{stats['r1']['react'].weight:.3f} > {stats['r1']['map_reduce'].weight:.3f}")
    ok &= check("the never-used stat is pruned", "r2/cot" in result.pruned,
                str(result.pruned))
    ok &= check("a stat WITH episodes is kept even at the floor",
                "direct" in stats.get("r2", {}),
                "evidence is evidence, however unfavourable")

    print("\n5. Audit gives per-proposition calibration")
    log = []
    for i in range(40):
        log.append({"beliefs": [
            # well calibrated: claims 0.9, right 90% of the time
            {"proposition": "is_bulk", "value": True, "credence": 0.9,
             "provenance": Provenance.ELICITED.value},
            {"proposition": "is_bulk", "value": True if i % 10 else False,
             "credence": 1.0, "provenance": Provenance.OBSERVED.value},
            # badly calibrated: claims 0.9, right half the time
            {"proposition": "coupling_tight", "value": True, "credence": 0.9,
             "provenance": Provenance.ELICITED.value},
            {"proposition": "coupling_tight", "value": i % 2 == 0,
             "credence": 1.0, "provenance": Provenance.OBSERVED.value},
        ]})
    audits = audit_propositions(log)
    ok &= check("both propositions audited", len(audits) == 2, str(sorted(audits)))
    if len(audits) == 2:
        good, bad = audits["is_bulk"], audits["coupling_tight"]
        ok &= check("the well-calibrated one is trusted", good.trustworthy,
                    f"ECE={good.ece}")
        ok &= check("the badly-calibrated one is NOT trusted", not bad.trustworthy,
                    f"ECE={bad.ece}, {bad.contradictions} contradictions")
        ok &= check("and they are distinguished per proposition",
                    good.trustworthy != bad.trustworthy,
                    "a single global switch could not express this")

    print("\n6. The cycle is copy-on-write and gated by the promotion guard")
    from app.paradigms import COST_PRIORS  # noqa: PLC0415
    from app.router import Router  # noqa: PLC0415

    incumbent = PolicyBundle.cold_start(fallback="react", tau=0.3)
    signature_before = incumbent.signature
    version_before = incumbent.version

    def promote_fn(inc, cand, holdout):
        return promote(
            inc, cand, holdout,
            lambda bundle, eps: Router(bundle, COST_PRIORS, "react").value_on(eps),
        )

    # Two regions in the belief log, and only one of them says the same thing on both
    # halves of the split. REPLICA replicates; SOLO qualifies on the search half alone,
    # which is exactly the shape a floor learned from its own proposal would have.
    all_tasks = sorted({r["task_id"] for r in rows})
    cut_a, cut_b = int(len(all_tasks) * 0.5), int(len(all_tasks) * 0.75)
    search_tasks = all_tasks[:cut_a]
    validate_tasks = all_tasks[cut_a:cut_b]
    floor_log = list(log)
    for i, tid in enumerate(search_tasks):
        floor_log.append(_belief_record(tid, "REPLICA", True))
        floor_log.append(_belief_record(tid, "SOLO", True))
    for tid in validate_tasks:
        floor_log.append(_belief_record(tid, "REPLICA", True))
        floor_log.append(_belief_record(tid, "SOLO", False))

    result_bundle, report = sleep_cycle(
        incumbent=incumbent,
        rows=rows,
        episodes=episodes,
        belief_log=floor_log,
        promote_fn=promote_fn,
        cycle=1,
    )
    ok &= check(
        "el piso que REPLICA en la mitad de validacion se instala",
        report.floors.get("REPLICA") == "A2_ACCOUNTABLE",
        f"search={len(search_tasks)} validate={len(validate_tasks)}",
    )
    ok &= check(
        "el piso que NO replica no se instala",
        "SOLO" not in report.floors,
        "propuesto en search, desmentido en validate",
    )
    ok &= check(
        "el piso instalado viaja en el bundle FIRMADO",
        result_bundle.verify()
        and (
            result_bundle.floors.get("REPLICA") == 2
            or incumbent.floors.get("REPLICA") is None
        ),
    )
    ok &= check("incumbent was not mutated",
                incumbent.signature == signature_before
                and incumbent.version == version_before)
    ok &= check("incumbent still verifies", incumbent.verify())
    ok &= check("a candidate was built", report.candidate_version >= version_before)
    ok &= check("the cycle reports a promotion verdict",
                "accepted" in report.promotion, str(report.promotion.get("reason", ""))[:70])
    ok &= check("returned bundle verifies", result_bundle.verify())
    ok &= check("discovered propositions are reported",
                isinstance(report.discovered, list),
                f"{len(report.discovered)} candidates")
    ok &= check("audit is reported", len(report.audit) == 2)

    print("\n  notes from the cycle:")
    for note in report.notes:
        print(f"    - {note[:96]}")

    ok = check_assurance_floor_learns(ok)

    print("\n" + ("ALL CHECKS PASSED" if ok else "THERE ARE FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
