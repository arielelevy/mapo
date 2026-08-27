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

from app.beliefs import Provenance  # noqa: E402
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

    result_bundle, report = sleep_cycle(
        incumbent=incumbent,
        rows=rows,
        episodes=episodes,
        belief_log=log,
        promote_fn=promote_fn,
        cycle=1,
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

    print("\n" + ("ALL CHECKS PASSED" if ok else "THERE ARE FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
