"""Check feasibility before running, and prune the plan space with it."""

import pathlib
import sys

ROOT = pathlib.Path(__file__).parent


def patch(path: str, pairs: list[tuple[str, str]]) -> None:
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in s:
            sys.exit(f"FAIL {path}: anchor missing ->\n{old[:170]}")
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print(f"  patched {path}")


patch("app/paradigms/dag.py", [
    (
        "    unit_ids = surface.unit_ids()\n    iterations = 0",
        "    unit_ids = surface.unit_ids()\n    iterations = 0\n"
        "    # The blackboard renders every finding into every sub-agent prompt, so its\n"
        "    # size is a context cost that grows with the number of sub-questions. Capped\n"
        "    # for the same reason map_reduce's reduce step is: accumulation scales until\n"
        "    # it does not.\n"
        "    max_board_chars = int(task[\"budget_tokens\"]) * 4 // 3",
    ),
    (
        "                board.add_finding(sub[\"id\"], text[:600])",
        "                if len(board.render()) < max_board_chars:\n"
        "                    board.add_finding(sub[\"id\"], text[:600])",
    ),
])

patch("app/runner.py", [
    (
        "from . import grading",
        "from . import feasibility, grading",
    ),
    (
        """                for trial in range(repeat):""",
        """                # Feasibility is arithmetic over what the task already declares, so
                # it costs nothing and is checked before any token is spent. A paradigm
                # that cannot run is recorded as infeasible rather than run into a wall
                # or silently skipped: the record has to show it was considered and why
                # it could not go.
                _, verdicts = feasibility.admissible(selected, self._documents, task)

                for trial in range(repeat):""",
    ),
    (
        """                def execute(cell: tuple[int, str]) -> Row:
                    trial, name = cell""",
        """                def execute(cell: tuple[int, str]) -> Row:
                    trial, name = cell
                    verdict = verdicts[name]
                    if not verdict.feasible:
                        return self._infeasible_row(
                            task, name, features, trial, verdict
                        )""",
    ),
    (
        """    def _run_one(""",
        '''    def _infeasible_row(
        self,
        task: dict[str, Any],
        paradigm: str,
        features: Features,
        trial: int,
        verdict: Any,
    ) -> Row:
        """A paradigm that cannot run this task, recorded rather than omitted."""
        return Row(
            task_id=task["task_id"],
            cell=task["cell"],
            paradigm=paradigm,
            trial=trial,
            region=features.region(),
            utility=0.0,
            cost_tokens=0,
            calls=0,
            wall_seconds=0.0,
            iterations=0,
            cross_unit_lookups=0,
            hallucinated_units=0,
            tool_usage={"infeasible": verdict.reason, **verdict.as_dict()},
            infeasible=True,
            retriever=self.retriever_arm,
            has_oracle=bool(task.get("has_oracle", True)),
            answer="",
            truth_coupling=task.get("truth_coupling", 0.0),
        )

    def _run_one(''',
    ),
])

# The router must not propose a paradigm that cannot run.
patch("app/router.py", [
    (
        "from .beliefs import BeliefBase, Calibration, Provenance, Verdict",
        "from . import feasibility\nfrom .beliefs import BeliefBase, Calibration, Provenance, Verdict",
    ),
    (
        """    def plan(
        self,
        task: dict[str, Any],
        candidates: list[str],
        region: str,""",
        """    def plan(
        self,
        task: dict[str, Any],
        candidates: list[str],
        region: str,
        documents: dict[str, str] | None = None,""",
    ),
    (
        """        if not candidates:
            raise ValueError("No candidate paradigms were supplied.")""",
        """        if not candidates:
            raise ValueError("No candidate paradigms were supplied.")

        # Feasibility prunes first, and for free. A learned policy that spends episodes
        # discovering that map_reduce loses on 500-unit tasks is learning arithmetic the
        # hard way — the cap was computable from the task before any token was spent.
        infeasible: dict[str, str] = {}
        if documents is not None:
            runnable, verdicts = feasibility.admissible(candidates, documents, task)
            infeasible = {
                p: v.reason for p, v in verdicts.items() if not v.feasible
            }
            if not runnable:
                raise ValueError(
                    f"No candidate can run this task: "
                    f"{ {p: r[:60] for p, r in infeasible.items()} }"
                )
            candidates = runnable""",
    ),
    (
        """        if excluded:
            notes.append(""",
        """        if infeasible:
            notes.append(
                "pruned as infeasible before any selection: "
                + "; ".join(f"{p} ({r})" for p, r in sorted(infeasible.items()))
            )
        if excluded:
            notes.append(""",
    ),
    (
        "        infeasible: dict[str, str] = {}\n        if documents is not None:",
        "        infeasible: dict[str, str] = {}\n        if documents is not None:",
    ),
])

# _materialise needs the infeasible map.
p = ROOT / "app/router.py"
s = p.read_text(encoding="utf-8")
s = s.replace(
    "        return self._materialise(\n            verdict, decision, profile, admissible, excluded, best\n        )",
    "        return self._materialise(\n"
    "            verdict, decision, profile, admissible, excluded, best, infeasible\n"
    "        )",
)
s = s.replace(
    "        excluded: list[str],\n        theta_best: str | None,\n    ) -> Plan:",
    "        excluded: list[str],\n        theta_best: str | None,\n"
    "        infeasible: dict[str, str] | None = None,\n    ) -> Plan:",
)
s = s.replace(
    '        """Turn a rule action into a concrete plan under the assurance profile."""\n        notes: list[str] = []',
    '        """Turn a rule action into a concrete plan under the assurance profile."""\n'
    "        notes: list[str] = []\n        infeasible = infeasible or {}",
)
p.write_text(s, encoding="utf-8")
print("  router prunes infeasible candidates first")
print("done")
