"""Behavioral checks of the intervention, without models or gold in the controller."""
from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.completion_repair import RepairRequest, repair_once
from app.llm import Usage


class Client:
    def __init__(self, text="ANSWER: Ana A: 11; Beto B: 22", error=None):
        self.text, self.error, self.calls = text, error, []

    def complete(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text, usage=Usage(prompt_tokens=100,
                                                          completion_tokens=10, calls=1))


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.request = RepairRequest("Accounts for Ana A and Beto B", ("Ana A", "Beto B"),
                                     ("a", "b"), 1000, 100, 3000, 2)
        self.docs = {"a": "Ana A account 11", "b": "Beto B account 22",
                     "private": "Beto B account 99"}

    def run_repair(self, client, mode="directed", original="Ana A: 11", request=None):
        return repair_once(request or self.request, original, self.docs, client, mode=mode)

    def test_complete_does_not_call_or_change_answer(self):
        client = Client(error=AssertionError("must not call"))
        result = self.run_repair(client, original="Ana A: 11; Beto B: 22")
        self.assertEqual(result.status, "unchanged")
        self.assertEqual(result.answer, result.original)
        self.assertEqual(client.calls, [])

    def test_deficit_changes_retrieval_and_keeps_scope(self):
        client = Client()
        result = self.run_repair(client)
        event = next(e for e in result.events if e["node"] == "retrieve")
        self.assertEqual(event["queries"], ["Beto B"])
        self.assertEqual(event["units"][0], "b")
        self.assertNotIn("private", event["units"])
        self.assertEqual(result.status, "repaired")
        self.assertEqual(result.usage.total_tokens, 110)
        self.assertEqual(len(client.calls), 1)

    def test_generic_has_same_trigger_limits_and_template(self):
        directed, generic = Client(), Client()
        a, b = self.run_repair(directed), self.run_repair(generic, "generic")
        self.assertEqual(a.events[0], b.events[0])
        self.assertEqual(b.events[1]["queries"], [self.request.question])
        self.assertEqual(a.events[1]["limits"], b.events[1]["limits"])
        self.assertEqual(directed.calls[0]["max_tokens"], generic.calls[0]["max_tokens"])

    def test_new_omission_defers_without_second_retry(self):
        client = Client("ANSWER: Beto B: 22")
        result = self.run_repair(client)
        self.assertIsNone(result.answer)
        self.assertEqual(result.candidate, "Beto B: 22")
        self.assertEqual(result.original, "Ana A: 11")
        self.assertEqual(result.events[-2]["verdict"]["missing"], ["Ana A"])
        self.assertEqual(len(client.calls), 1)

    def test_budget_and_retention_do_not_call(self):
        for mode, req in [("retain", self.request),
                          ("directed", replace(self.request, evidence_chars=1)),
                          ("directed", replace(self.request, max_input_chars=1))]:
            client = Client(error=AssertionError("must not call"))
            self.assertIsNone(self.run_repair(client, mode, request=req).answer)
            self.assertEqual(client.calls, [])

    def test_unavailable_scope_and_unknown_mode_fail(self):
        with self.assertRaises(ValueError):
            self.run_repair(Client(), request=replace(self.request, unit_ids=("unknown",)))
        with self.assertRaises(ValueError):
            self.run_repair(Client(), "unknown")

    def test_infrastructure_error_is_not_abstention(self):
        with self.assertRaisesRegex(ConnectionError, "offline"):
            self.run_repair(Client(error=ConnectionError("offline")))

    def test_same_state_same_decision_trace(self):
        self.assertEqual(self.run_repair(Client()).as_dict(),
                         self.run_repair(Client()).as_dict())

    def test_coverage_does_not_claim_fact_checking(self):
        result = self.run_repair(Client("ANSWER: Ana A: WRONG; Beto B: WRONG"))
        self.assertEqual(result.status, "repaired")  # Deliberately exposes the residual.

    def test_round_robin_reads_for_multiple_missing_keys(self):
        client = Client()
        result = self.run_repair(client, original="", request=replace(self.request, max_units=2))
        retrieval = next(e for e in result.events if e["node"] == "retrieve")
        self.assertEqual(retrieval["queries"], ["Ana A", "Beto B"])
        self.assertEqual(set(retrieval["units"]), {"a", "b"})

    def test_base_budget_stops_before_spending(self):
        from bench.runs._run_p41_repair import BoundedClient, BaseBudgetReached, MAX_BASE_CHARS
        client = Client()
        bounded = BoundedClient(client)
        with self.assertRaises(BaseBudgetReached):
            bounded.complete([{"role": "user", "content": "x" * MAX_BASE_CHARS}])
        self.assertEqual(client.calls, [])

    def test_duplicate_or_empty_domain_is_rejected(self):
        for domain in [("",), ("Ana A", "Ana A")]:
            with self.assertRaises(ValueError):
                replace(self.request, domain=domain)

    def test_analysis_distinguishes_effect_from_missing_exposure(self):
        from bench.runs import _run_p41_repair as bench
        rows = []
        for world in bench.SEEDS:
            for arm in bench.ARMS:
                for trial in range(bench.REPEAT):
                    for condition, value in (("base", .4), ("retain", 0),
                                             ("generic", .5), ("directed", 1)):
                        rows.append(dict(world=world, paradigm=arm, trial=trial,
                                         condition=condition, utility=value,
                                         candidate_utility=value, emitted=condition != "retain",
                                         cost_tokens=1000, status="repaired", usage={"calls": 1}))
        reports = []
        with patch.object(bench, "read_rows", return_value=rows), \
             patch.object(bench, "dump", side_effect=lambda path, value: reports.append(value)), \
             patch("builtins.print"):
            bench.analyse()
            self.assertTrue(reports[-1]["verdict"].startswith("SUCCESS"))
            self.assertEqual(reports[-1]["noise_floor"]["p95"], 0)
            self.assertAlmostEqual(reports[-1]["directed_vs"]["generic"]["delta"], .5)
            for row in rows:
                row["status"] = "unchanged"
            bench.analyse()
            self.assertTrue(reports[-1]["verdict"].startswith("INCONCLUSIVE"))
            rows.pop()  # One missing condition invalidates the entire last world.
            bench.analyse()
            self.assertEqual(len(reports[-1]["complete_worlds"]), len(bench.SEEDS) - 1)
            self.assertTrue(reports[-1]["verdict"].startswith("INCOMPLETE"))


if __name__ == "__main__":
    unittest.main()
