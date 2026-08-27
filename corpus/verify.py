"""Independent verification of corpus ground truth.

This re-derives every task's oracle by PARSING THE DOCUMENTS, with no access to the
generator's in-memory world. That independence is the whole point: a check that reuses
the generator's own state would confirm the generator agrees with itself, which is not
the property in question.

It exists because the first generated corpus had silently wrong answers. Amendment
units were named `memo-NNN-alt`, which matched the `memo-` prefix scan, so every task
built after the first C5 task had its unit list shifted and its oracle quietly became
incorrect. Nothing crashed. A whole study would have been run on bad labels.

Run this after every regeneration. A corpus that has not passed it is not a corpus.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# One regex per assertion phrasing. The corpus varies the surface form on purpose —
# a single fixed template made every fact findable with one keyword search, which
# neutralised the cardinality dial — so the verifier has to understand all of them or it
# cannot re-derive the ground truth independently, which is its whole job.
#
# The near-miss lines must match NONE of these. That is asserted, not assumed: see
# `assert_near_misses_rejected` below. A near miss silently parsed as an assertion would
# corrupt every oracle in the corpus while every check still reported PASS.
# Two words, plus an optional numeric discriminator. Past the 396 unique first/surname
# combinations the generator appends one ("Tomas Arrieta 2"), and a two-word-only pattern
# silently failed to parse those memos — so at 400 people four memos vanished from the
# recount and every C4 oracle in the corpus was off by however many of them shared the
# target city. The failure was invisible except through this verifier.
_NAME = r"[\w'-]+ [\w'-]+(?: \d+)?"
_PLACE = r"[\w ]+?"
_ROLE = r"[\w ]+?"

FACT_PATTERNS = (
    re.compile(
        rf"^(?P<name>{_NAME}), based in (?P<city>{_PLACE}), "
        rf"acts as (?P<role>{_ROLE}) for (?P<firm>.+)\.$",
        re.MULTILINE,
    ),
    re.compile(
        rf"^(?P<name>{_NAME}) serves as (?P<role>{_ROLE}) at (?P<firm>.+); "
        rf"domiciled in (?P<city>{_PLACE})\.$",
        re.MULTILINE,
    ),
    re.compile(
        rf"^Appointed (?P<role>{_ROLE}) of (?P<firm>.+): (?P<name>{_NAME}), "
        rf"resident of (?P<city>{_PLACE})\.$",
        re.MULTILINE,
    ),
    re.compile(
        rf"^(?P<name>{_NAME}) \((?P<city>{_PLACE})\) holds the position of "
        rf"(?P<role>{_ROLE}) within (?P<firm>.+)\.$",
        re.MULTILINE,
    ),
    re.compile(
        rf"^In the capacity of (?P<role>{_ROLE}) for (?P<firm>.+), "
        rf"(?P<name>{_NAME}) operates from (?P<city>{_PLACE})\.$",
        re.MULTILINE,
    ),
)

# Every near-miss shape the generator emits. Kept here so the rejection can be proved
# rather than argued for.
NEAR_MISS_SAMPLES = (
    "Marta Ochoa reports to the director of Boreal Trading.",
    "Marta Ochoa was formerly director of Boreal Trading; the position was vacated.",
    "Marta Ochoa is not recorded as director for any entity.",
    "Correspondence regarding the director appointment was filed in Rosario.",
    "A prior filing listed no director for the Rosario branch.",
)


def match_fact(text: str):
    """First assertion found, under any phrasing."""
    for pattern in FACT_PATTERNS:
        found = pattern.search(text)
        if found:
            return found
    return None


def assert_near_misses_rejected() -> None:
    """Fail loudly if any near miss parses as an assertion.

    This runs before any task is checked. If a near miss were accepted, roles and
    cities that nobody asserted would enter the recomputed answers, the oracles would
    disagree with them, and the failure would look like a generator bug rather than a
    verifier bug — sending the search in the wrong direction.
    """
    for line in NEAR_MISS_SAMPLES:
        found = match_fact(line)
        if found:
            sys.exit(
                "FATAL: a near-miss line parses as an assertion, so the verifier "
                f"cannot be trusted.\n  line:    {line}\n  matched: {found.groupdict()}"
            )
ACCOUNT = re.compile(r"Settlement account on file: (?P<account>AR\d+)\.")
REPORTS = re.compile(r"Reports to (?P<supervisor>[\w'-]+ [\w'-]+) for all authorisations\.")
# The supplementary filing names an ACCOUNT and never the person, so verifying it
# requires the same two hops the task requires: read the restated domicile, then find
# who holds that account.
AMENDED = re.compile(
    r"domicile of record associated with settlement account (?P<account>AR\d+)\s+"
    r"is (?P<city>[\w ]+)\.",
    re.IGNORECASE,
)
TRIGGER = re.compile(r"requires escalation for freezing", re.IGNORECASE)


def parse_unit(text: str) -> dict[str, Any] | None:
    """Extract the structured claim a base memo makes, or None for a non-memo."""
    fact = match_fact(text)
    if not fact:
        return None
    account = ACCOUNT.search(text)
    reports = REPORTS.search(text)
    return {
        "name": fact.group("name"),
        "city": fact.group("city").strip(),
        "role": fact.group("role").strip(),
        "account": account.group("account") if account else None,
        "supervisor": reports.group("supervisor") if reports else None,
    }


class Verifier:
    def __init__(self, documents: dict[str, str]) -> None:
        self.documents = documents
        self.parsed: dict[str, dict[str, Any]] = {}
        self.amendments: dict[str, dict[str, Any]] = {}
        self.triggers: set[str] = set()

        for unit_id, text in documents.items():
            claim = parse_unit(text)
            if claim:
                self.parsed[unit_id] = claim
                continue
            amended = AMENDED.search(text)
            if amended:
                self.amendments[unit_id] = {
                    "account": amended.group("account"),
                    "city": amended.group("city").strip(),
                }
                continue
            if TRIGGER.search(text):
                self.triggers.add(unit_id)

        # Name -> supervisor, taken across the whole corpus, since a chain question
        # may traverse units outside the task's own list.
        self.supervisor_of = {
            c["name"]: c["supervisor"] for c in self.parsed.values()
        }
        self.city_of = {c["name"]: c["city"] for c in self.parsed.values()}
        self.account_of = {c["name"]: c["account"] for c in self.parsed.values()}
        self.holder_of = {
            c["account"]: c["name"] for c in self.parsed.values() if c["account"]
        }

    def units(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        return [self.parsed[u] for u in task["unit_ids"] if u in self.parsed]

    # -- per cell ----------------------------------------------------------

    def check(self, task: dict[str, Any]) -> tuple[bool, str]:
        cell = task["cell"]
        handler = {
            "C1_single_verifiable": self._c1,
            "C2_bulk_independent": self._c2,
            "C3_coupled_chain": self._c3,
            "C4_aggregate_full_coverage": self._c4,
            "C5_unknown_horizon": self._c5,
            "C7_irreversible": self._c7,
        }.get(cell)
        if handler is None:
            return False, f"no verifier for cell {cell}"
        return handler(task)

    def _c1(self, task: dict[str, Any]) -> tuple[bool, str]:
        if len(task["unit_ids"]) != 1:
            return False, f"expected 1 unit, got {len(task['unit_ids'])}"
        claim = self.parsed.get(task["unit_ids"][0])
        if not claim:
            return False, "unit is not a parseable memo"
        name = re.search(rf"for ({_NAME})\?", task["question"]).group(1)
        if claim["name"] != name:
            return False, f"unit describes {claim['name']}, question asks {name}"
        if [claim["account"]] != task["oracle"]:
            return False, f"account {claim['account']} != oracle {task['oracle']}"
        return True, "ok"

    def _c2(self, task: dict[str, Any]) -> tuple[bool, str]:
        role = re.search(r"role is '([^']+)'", task["question"]).group(1)
        recomputed = sorted({
            c["name"] for c in self.units(task) if c["role"] == role
        })
        if recomputed != sorted(task["oracle"]):
            return False, f"recomputed {recomputed} != oracle {sorted(task['oracle'])}"
        return True, f"ok ({len(recomputed)} names over {len(task['unit_ids'])} units)"

    def _c3(self, task: dict[str, Any]) -> tuple[bool, str]:
        match = re.search(
            rf"Starting from ({_NAME}), follow the reporting line upward (\d+)",
            task["question"],
        )
        name, hops = match.group(1), int(match.group(2))
        current = name
        for _ in range(hops):
            nxt = self.supervisor_of.get(current)
            if not nxt:
                return False, f"chain from {name} breaks at {current}"
            current = nxt
        account = self.account_of.get(current)
        if [account] != task["oracle"]:
            return False, f"terminal {current} has {account} != oracle {task['oracle']}"
        # The whole point of the account-valued oracle is that it cannot be guessed,
        # so a chain of length zero would make the task trivial again.
        if hops < 1:
            return False, "a zero-hop chain makes the coupling axis vacuous"
        return True, f"ok ({name} -> {current}, {hops} hop(s), unique account)"

    def _c4(self, task: dict[str, Any]) -> tuple[bool, str]:
        city = re.search(r"based in ([\w ]+)\?", task["question"]).group(1).strip()
        recount = sum(1 for c in self.units(task) if c["city"] == city)
        if [str(recount)] != task["oracle"]:
            return False, f"recount {recount} != oracle {task['oracle']}"
        return True, f"ok ({recount} of {len(task['unit_ids'])} units)"

    def _c5(self, task: dict[str, Any]) -> tuple[bool, str]:
        amended = [
            self.amendments[u] for u in task["unit_ids"] if u in self.amendments
        ]
        if len(amended) != 1:
            return False, f"expected exactly 1 amendment unit, found {len(amended)}"

        target = amended[0]
        holder = self.holder_of.get(target["account"])
        if holder is None:
            return False, f"account {target['account']} has no holder in the corpus"

        base = {c["name"]: c["city"] for c in self.units(task)}
        if holder not in base:
            return False, f"holder {holder} has no base memo among this task's units"
        if base[holder] == target["city"]:
            return False, f"filing for {holder} restates the same city, no conflict"
        if [holder] != task["oracle"]:
            return False, f"resolved holder {holder} != oracle {task['oracle']}"

        # The filing must not name the person: if it did, the task would collapse from
        # two hops to one and the horizon claim would be false.
        text = self.documents[
            next(u for u in task["unit_ids"] if u in self.amendments)
        ]
        if holder in text:
            return False, f"the filing names {holder} directly, collapsing it to one hop"

        others = [
            self.holder_of.get(a["account"])
            for u, a in self.amendments.items()
            if u in task["unit_ids"] and self.holder_of.get(a["account"]) != holder
        ]
        if any(others):
            return False, f"question promises one contradiction, found also {others}"
        return True, f"ok (2 hops: account -> {holder}, promise holds)"

    def _c7(self, task: dict[str, Any]) -> tuple[bool, str]:
        if not task.get("irreversible"):
            return False, "C7 task is not flagged irreversible"

        present = [u for u in task["unit_ids"] if u in self.triggers]

        if task["oracle"] == ["escalate"]:
            if len(present) != 1:
                return False, (
                    f"a positive case needs exactly one trigger unit, found {len(present)}"
                )
            return True, f"ok (trigger in {present[0]}; escalation is correct)"

        if task["oracle"] == ["no escalation"]:
            if present:
                return False, f"a negative case must contain no trigger, found {present}"
            return True, "ok (no trigger; the conservative answer is correct)"

        return False, f"unexpected oracle {task['oracle']}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify corpus ground truth.")
    parser.add_argument("--corpus", type=str, required=True)
    args = parser.parse_args()

    root = Path(args.corpus)
    documents = json.loads((root / "documents.json").read_text(encoding="utf-8"))
    tasks = json.loads((root / "tasks.json").read_text(encoding="utf-8"))

    # Before checking anything, prove the parser cannot be fooled by the distractors.
    assert_near_misses_rejected()

    verifier = Verifier(documents)
    failures: list[tuple[str, str]] = []
    per_cell: dict[str, list[int]] = {}

    for task in tasks:
        ok, message = verifier.check(task)
        counts = per_cell.setdefault(task["cell"], [0, 0])
        counts[0] += 1
        if ok:
            counts[1] += 1
        else:
            failures.append((task["task_id"], message))

    print(f"documents parsed : {len(verifier.parsed)} memos, "
          f"{len(verifier.amendments)} amendments, "
          f"{len(verifier.triggers)} triggers")
    print("near-miss guard  : PASS (no distractor parses as an assertion)")
    print(f"tasks checked    : {len(tasks)}")
    print()
    for cell in sorted(per_cell):
        total, passed = per_cell[cell]
        mark = "PASS" if passed == total else "FAIL"
        print(f"  [{mark}] {cell:<32} {passed}/{total}")

    if failures:
        print(f"\n{len(failures)} FAILURES:")
        for task_id, message in failures[:25]:
            print(f"  {task_id}: {message}")
        return 1

    print("\nAll ground truth verified independently from the documents.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
