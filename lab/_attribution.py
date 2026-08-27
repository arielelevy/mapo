"""Attribute a failure to retrieval or to reasoning.

The tool-usage trace makes a distinction that was previously invisible: a paradigm that
scored zero either never saw the evidence, or saw it and got the answer wrong. Those are
different defects with different fixes, and pooling them was hiding which layer to work
on. `relevant_units_read` separates them.

It also guards a conclusion. "The searching topology lost" means nothing if the searcher
never reached a relevant unit — that is a statement about the tool surface. Only a
failure WITH the evidence in hand is evidence about the topology.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
p = ROOT / "app/metrics.py"
s = p.read_text(encoding="utf-8")

OLD_OBS = '''@dataclass(frozen=True)
class Observation:
    """One (task, paradigm) cell of the cross product."""

    task_id: str
    region: str
    paradigm: str
    utility: float
    cost_tokens: int
    has_oracle: bool'''

NEW_OBS = '''@dataclass(frozen=True)
class Observation:
    """One (task, paradigm) cell of the cross product."""

    task_id: str
    region: str
    paradigm: str
    utility: float
    cost_tokens: int
    has_oracle: bool
    # How many answer-bearing units the paradigm actually read, and how many existed.
    # Optional because studies assembled before the tool trace existed do not have it;
    # absent values are reported as unattributable rather than guessed at.
    relevant_units_read: int | None = None
    relevant_units_available: int | None = None'''

if OLD_OBS not in s:
    sys.exit("FAIL: Observation anchor")
s = s.replace(OLD_OBS, NEW_OBS, 1)

ATTRIBUTION = '''    # -- failure attribution ------------------------------------------------

    def failure_attribution(self, threshold: float = 1.0) -> dict[str, Any]:
        """Split failures into retrieval and reasoning.

        A paradigm that scored below `threshold` either never read an answer-bearing
        unit — a retrieval failure, and a statement about the tool surface — or read one
        and still got it wrong, which is a statement about the topology.

        The distinction decides what a result means. "The searching topology lost" is
        uninterpretable when the searcher never reached the evidence; only a failure
        with the evidence in hand is evidence about the control structure.
        """
        rows: dict[str, dict[str, Any]] = {}
        for paradigm in self.paradigms:
            retrieval = reasoning = unattributable = successes = 0
            for task in self.complete_tasks:
                obs = self._by_task[task][paradigm]
                if self.quality(task, paradigm) >= threshold:
                    successes += 1
                    continue
                if obs.relevant_units_read is None:
                    unattributable += 1
                elif obs.relevant_units_available == 0:
                    # Nothing to find: a failure here cannot be retrieval's fault. The
                    # negative C7 cases are exactly this — the correct answer is to
                    # find nothing and say so.
                    reasoning += 1
                elif obs.relevant_units_read == 0:
                    retrieval += 1
                else:
                    reasoning += 1
            failures = retrieval + reasoning + unattributable
            rows[paradigm] = {
                "successes": successes,
                "failures": failures,
                "retrieval_failures": retrieval,
                "reasoning_failures": reasoning,
                "unattributable": unattributable,
                "retrieval_share": (
                    round(retrieval / failures, 3) if failures else None
                ),
            }
        return rows

'''

s = s.replace(
    "    # -- cost sensitivity --------------------------------------------------",
    ATTRIBUTION + "    # -- cost sensitivity --------------------------------------------------",
    1,
)
s = s.replace(
    '''            "cost_spread": self.cost_spread(),''',
    '''            "failure_attribution": self.failure_attribution(),
            "cost_spread": self.cost_spread(),''',
    1,
)
p.write_text(s, encoding="utf-8")
print("  metrics.py: failure attribution added")

# The runner must feed the trace through into observations.
r = ROOT / "app/runner.py"
rs = r.read_text(encoding="utf-8")
OLD = '''            Observation(
                task_id=task_id,
                region=rows[0]["region"],
                paradigm=paradigm,
                utility=sum(x["utility"] for x in rows) / len(rows),
                cost_tokens=int(sum(x["cost_tokens"] for x in rows) / len(rows)),
                has_oracle=rows[0]["has_oracle"],
            )'''
NEW = '''            Observation(
                task_id=task_id,
                region=rows[0]["region"],
                paradigm=paradigm,
                utility=sum(x["utility"] for x in rows) / len(rows),
                cost_tokens=int(sum(x["cost_tokens"] for x in rows) / len(rows)),
                has_oracle=rows[0]["has_oracle"],
                # Max across replicates, not mean: the question is whether the paradigm
                # was ever in a position to answer, and a single trial that reached the
                # evidence establishes that it could.
                relevant_units_read=max(
                    ((x.get("tool_usage") or {}).get("relevant_units_read") or 0)
                    for x in rows
                ),
                relevant_units_available=self._relevant_count(task_id),
            )'''
if OLD not in rs:
    sys.exit("FAIL: Observation construction anchor")
rs = rs.replace(OLD, NEW, 1)

rs = rs.replace(
    "    def replicates(self, paradigm: str | None = None) -> dict[str, list[float]]:",
    '''    def _relevant_count(self, task_id: str) -> int:
        task = next((t for t in self._tasks if t["task_id"] == task_id), None)
        return len(task.get("relevant_units", [])) if task else 0

    def replicates(self, paradigm: str | None = None) -> dict[str, list[float]]:''',
    1,
)
r.write_text(rs, encoding="utf-8")
print("  runner.py: trace flows into observations")
print("done")
