"""P41: prepare, estimate, run and analyse a bounded declared-domain repair experiment.

Run from lab: py bench/runs/_run_p41_repair.py --prepare / --estimate / --run / --analyse
No benchmark labels enter the repair controller. Base generations are shared across controls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import statistics as stats
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import grading
from app.completion_repair import RepairRequest, VERSION, repair_once
from app.config import Settings
from app.fsio import write_atomic, exclusive
from app.llm import LLMClient, SeededClient
from app.paradigms import REGISTRY
from app.runner import Runner, _is_infrastructure
from corpus.generate import (GENERATOR_VERSION, Generator, apply_honest_detectors,
                             apply_request_demands)

SEEDS = tuple(range(202609050, 202609062))
ARMS = ("react", "rewoo")
REPEAT = 3
CONDITIONS = ("base", "retain", "generic", "directed")
OUT = Path("results/luna/p41")
ROWS = OUT / "rows.jsonl"
MAX_BASE_CALLS = 16
MAX_BASE_CHARS = 320_000
MAX_OUTPUT = 1024
LIMITS = dict(evidence_chars=24_000, max_completion_tokens=MAX_OUTPUT,
              max_input_chars=40_000, max_units=6)


def dump(path, value):
    write_atomic(path, json.dumps(value, ensure_ascii=False, indent=2))


def corpus_path(seed):
    return Path("corpus") / f"gold_p41_{seed}"


def prepare():
    for index, seed in enumerate(SEEDS):
        root = corpus_path(seed)
        if root.exists():
            raise ValueError(f"Refusing to overwrite existing corpus: {root}")
        generator = Generator(seed)
        generator.build_world(48)
        generator.build_documents_hard()
        generator.inflate_units(1024)
        task = generator.task_c9_roster(0, (16, 48)[index % 2])
        task.question += " Include each individual's full name next to their account."
        task = apply_request_demands(apply_honest_detectors([task]))[0]
        root.mkdir(parents=True)
        dump(root / "documents.json", generator.documents)
        dump(root / "tasks.json", [task.as_dict()])
        dump(root / "entities.json", generator.entity_gold())
        dump(root / "manifest.json", {"generator_version": GENERATOR_VERSION,
                                     "seed": seed, "people": 48, "unit_tokens": 1024,
                                     "hard": True, "tasks": 1, "experiment": "P41",
                                     "question_contract": "full_name_and_account"})
        subprocess.run([sys.executable, "corpus/verify.py", "--corpus", str(root)], check=True)


def estimate():
    scopes, chars, units = [], 0, 0
    for seed in SEEDS:
        root = corpus_path(seed)
        tasks = json.loads((root / "tasks.json").read_text(encoding="utf-8"))
        docs = json.loads((root / "documents.json").read_text(encoding="utf-8"))
        if len(tasks) != 1:
            raise ValueError("P41 requires one task per independent world")
        scopes.append(len(tasks[0]["unit_ids"]))
        chars += sum(len(docs[u]) for u in tasks[0]["unit_ids"])
        units += len(tasks[0]["unit_ids"])
    bases = len(SEEDS) * len(ARMS) * REPEAT
    report = {"worlds": len(SEEDS), "base_executions": bases,
              "max_repair_calls": bases * 2, "replicas": REPEAT, "scope_units": scopes,
              "scoped_material_chars": chars, "scoped_material_units": units,
              "approx_material_tokens": chars // 4,
              "max_generation_input_chars": bases * (MAX_BASE_CHARS + 2 * LIMITS["max_input_chars"]),
              "max_generation_output_tokens": bases * (MAX_BASE_CALLS + 2) * MAX_OUTPUT,
              "estimate_note": "Input uses chars/4 only as planning estimate; actual tokens are metered. "
                               "Embeddings add up to corpus material, plus queries; cached values reduce calls.",
              "approx_generation_ceiling_tokens": bases * (
                  MAX_BASE_CHARS // 4 + MAX_BASE_CALLS * MAX_OUTPUT
                  + 2 * (LIMITS["max_input_chars"] // 4 + MAX_OUTPUT))}
    print(json.dumps(report, indent=2), flush=True)
    return report


class BaseBudgetReached(Exception):
    pass


class BoundedClient:
    """Bound input characters and calls before spending; retain metering on exceptions."""
    def __init__(self, seeded):
        self.seeded, self.input_chars, self.calls = seeded, 0, 0

    @property
    def spent(self):
        return self.seeded.spent

    @property
    def fingerprint(self):
        return self.seeded.fingerprint

    @property
    def cache_root(self):
        return self.seeded.cache_root

    def complete(self, messages, tools=None, max_tokens=None):
        n = len(json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False))
        if self.calls >= MAX_BASE_CALLS or self.input_chars + n > MAX_BASE_CHARS:
            raise BaseBudgetReached("base call/input budget reached")
        self.calls += 1
        self.input_chars += n
        return self.seeded.complete(messages, tools, min(max_tokens or MAX_OUTPUT, MAX_OUTPUT))


def settings():
    base = Settings.from_env()
    return replace(base, endpoint=os.environ["MAPO_NANO_ENDPOINT"].rstrip("/"),
                   api_key=os.environ["MAPO_NANO_KEY"], chat_deployment="gpt-5.6-luna",
                   reasoning_effort="none", max_tokens=MAX_OUTPUT,
                   results_dir=base.results_dir / "luna" / "p41")


def identity(config):
    paths = [Path("app/completion_repair.py"), Path(__file__),
             Path("app/contracts.py"), Path("app/llm.py"), Path("app/runner.py"),
             Path("app/retrieval.py"), Path("app/tools.py"), Path("app/grading.py")]
    paths += sorted(Path("app/paradigms").glob("*.py"))
    paths += [corpus_path(s) / f for s in SEEDS
              for f in ("documents.json", "tasks.json", "manifest.json")]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    digest.update(json.dumps({"seeds": SEEDS, "arms": ARMS, "repeat": REPEAT,
                              "limits": LIMITS, "fingerprint": config.fingerprint(),
                              "account": config.account_tag()}, sort_keys=True).encode())
    return digest.hexdigest()


def read_rows():
    if not ROWS.exists():
        return []
    rows = [json.loads(line) for line in ROWS.read_text(encoding="utf-8").splitlines() if line]
    seen = set()
    for row in rows:
        key = row["world"], row["paradigm"], row["trial"], row["condition"]
        if not row.get("infra_error"):
            if key in seen:
                raise ValueError(f"Duplicate measured row: {key}")
            seen.add(key)
    return rows


def run(sealed=False):
    estimate()
    config = settings()
    OUT.mkdir(parents=True, exist_ok=True)
    current_identity = identity(config)
    manifest = OUT / "run.json"
    record = {"identity": current_identity, "version": VERSION, "fingerprint": config.fingerprint(),
              "limits": LIMITS, "replicas": REPEAT, "worlds": list(SEEDS)}
    if manifest.exists():
        if json.loads(manifest.read_text(encoding="utf-8")) != record:
            raise ValueError("Code, corpus or configuration changed: use a separately registered experiment")
    else:
        dump(manifest, record)
    with exclusive(ROWS, owner="P41 paired repair"):
        existing = read_rows()
        done = {(r["world"], r["paradigm"], r["trial"], r["condition"]): r
                for r in existing if not r.get("infra_error")}
        client = LLMClient(config, sealed=sealed)
        with ROWS.open("a", encoding="utf-8") as sink:
            def save(row):
                row["experiment_identity"] = current_identity
                sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                sink.flush()
                if not row.get("infra_error"):
                    done[(row["world"], row["paradigm"], row["trial"], row["condition"])] = row
                print(f"{len(done)}/{len(SEEDS)*len(ARMS)*REPEAT*4} "
                      f"{row['world']} {row['paradigm']} t{row['trial']} {row['condition']} "
                      f"{row['status']} u={row.get('utility')} tok={row.get('cost_tokens')}", flush=True)

            for world in SEEDS:
                runner = Runner(config, corpus_path(world).name, sealed=sealed,
                                retriever_arm="hybrid", surface_variant="basic")
                task = runner._tasks[0]
                # Explicit public request projection; no gold reaches paradigms or controller.
                public = {k: task[k] for k in ("task_id", "question", "unit_ids", "budget_tokens",
                                              "domain_keys", "coverage_demanded", "completeness_domain")}
                request = RepairRequest(task["question"], tuple(task["domain_keys"]),
                                        tuple(task["unit_ids"]), **LIMITS)
                for arm in ARMS:
                    for trial in range(REPEAT):
                        key = world, arm, trial
                        common = dict(world=world, task_id=task["task_id"], paradigm=arm,
                                      trial=trial, fingerprint=config.fingerprint())
                        if (*key, "base") not in done:
                            metered = BoundedClient(SeededClient(client, config.seed + trial))
                            try:
                                result = REGISTRY[arm](metered, runner.surface_for(public, metered), public)
                                answer, raw, status = result.answer, result.raw_text, "generated"
                            except BaseBudgetReached:
                                answer, raw, status = "", "", "budget_exhausted"
                            except Exception as exc:
                                if not _is_infrastructure(exc):
                                    raise
                                save({**common, "condition": "base", "infra_error": True,
                                      "status": type(exc).__name__, "cost_tokens": metered.spent.total_tokens})
                                raise
                            save({**common, "condition": "base", "answer": answer, "raw_text": raw,
                                  "candidate": answer, "status": status, "emitted": bool(answer),
                                  "utility": grading.score(answer, task["oracle"]),
                                  "candidate_utility": grading.score(answer, task["oracle"]),
                                  "cost_tokens": metered.spent.total_tokens,
                                  "usage": metered.spent.as_dict()})
                        base = done[(*key, "base")]
                        # Alternate repair execution order by trial to avoid a fixed time confound.
                        modes = ("retain", "generic", "directed") if trial % 2 == 0 else (
                            "retain", "directed", "generic")
                        for mode in modes:
                            if (*key, mode) in done:
                                continue
                            metered = SeededClient(client, config.seed + trial)
                            try:
                                repaired = repair_once(request, base["answer"], runner._documents,
                                                       metered, mode=mode)
                            except Exception as exc:
                                if not _is_infrastructure(exc):
                                    raise
                                save({**common, "condition": mode, "infra_error": True,
                                      "status": type(exc).__name__, "cost_tokens": metered.spent.total_tokens})
                                raise
                            save({**common, "condition": mode, **repaired.as_dict(),
                                  "emitted": repaired.answer is not None,
                                  "utility": grading.score(repaired.answer or "", task["oracle"]),
                                  "candidate_utility": grading.score(repaired.candidate, task["oracle"]),
                                  "cost_tokens": base["cost_tokens"] + repaired.usage.total_tokens})


def interval(values, rng, repeats=5000):
    bootstrap = sorted(stats.mean(rng.choices(values, k=len(values))) for _ in range(repeats))
    return [bootstrap[int(.025 * repeats)], bootstrap[int(.975 * repeats)]]


def analyse():
    rows = read_rows()
    clean = {(r["world"], r["paradigm"], r["trial"], r["condition"]): r
             for r in rows if not r.get("infra_error")}
    # Require entire worlds, not survivor pairs selected by which request succeeded.
    worlds = [w for w in SEEDS if all((w, a, t, c) in clean for a in ARMS
                                     for t in range(REPEAT) for c in CONDITIONS)]
    if not worlds:
        raise ValueError("No complete worlds to analyse")
    rng = random.Random(20260905)
    selected = [r for r in clean.values() if r["world"] in worlds]
    summary = {}
    for condition in CONDITIONS:
        sample = [r for r in selected if r["condition"] == condition]
        emitted = [r for r in sample if r["emitted"]]
        successes = [all(clean[(w, a, t, condition)]["utility"] >= 1 - 1e-9
                         for t in range(REPEAT)) for w in worlds for a in ARMS]
        summary[condition] = {"n": len(sample), "utility": stats.mean(r["utility"] for r in sample),
                              "candidate_utility": stats.mean(r["candidate_utility"] for r in sample),
                              "coverage": len(emitted) / len(sample), "pass3": stats.mean(successes),
                              "conditional_loss": 1 - stats.mean(r["utility"] for r in emitted) if emitted else None,
                              "tokens": stats.mean(r["cost_tokens"] for r in sample),
                              "repair_calls": sum(r.get("usage", {}).get("calls", 0) for r in sample)
                              if condition != "base" else 0,
                              "regressions": sum(r["utility"] < clean[(r["world"], r["paradigm"],
                                                                       r["trial"], "base")]["utility"] - 1e-9
                                                 for r in sample)}
    contrasts = {}
    for reference in ("base", "generic"):
        differences, net = [], []
        for world in worlds:
            ds, ns = [], []
            for arm in ARMS:
                for trial in range(REPEAT):
                    a, b = clean[(world, arm, trial, "directed")], clean[(world, arm, trial, reference)]
                    delta = a["utility"] - b["utility"]
                    ds.append(delta)
                    ns.append(delta - .05 * (a["cost_tokens"] - b["cost_tokens"]) / 100_000)
            differences.append(stats.mean(ds))
            net.append(stats.mean(ns))
        contrasts[reference] = {"delta": stats.mean(differences), "ic95": interval(differences, rng),
                                "net_delta": stats.mean(net), "net_ic95": interval(net, rng)}
    # Same-condition pseudo-arms: resampled means of 3 trials, never the real observed gap.
    cells = [(w, a) for w in worlds for a in ARMS]
    floors = {}
    null_gaps = []
    pseudo_by_cell = {}
    for world, arm in cells:
        draws = []
        for _ in range(1000):
            condition = rng.choice(("base", "generic", "directed"))
            utilities = [clean[(world, arm, t, condition)]["utility"] for t in range(REPEAT)]
            draws.append(tuple(stats.mean(rng.choices(utilities, k=REPEAT)) for _ in range(2)))
        pseudo_by_cell[(world, arm)] = draws
        local = sorted(abs(x - y) / 2 for x, y in draws)
        floors[f"{world}/{arm}"] = {"mean": stats.mean(local), "p95": local[950]}
    for i in range(1000):
        draws = [pseudo_by_cell[c][i] for c in cells]
        null_gaps.append(stats.mean(max(x, y) for x, y in draws)
                         - max(stats.mean(x for x, _ in draws), stats.mean(y for _, y in draws)))
    null_gaps.sort()
    floor95 = null_gaps[950]
    triggered = [w for w in worlds if any(clean[(w, a, t, "directed")]["status"] != "unchanged"
                                        for a in ARMS for t in range(REPEAT))]
    if len(worlds) != len(SEEDS):
        verdict = "INCOMPLETE: no final verdict until every registered world is measured"
    elif len(triggered) < 6:
        verdict = "INCONCLUSIVE: fewer than six worlds triggered repair"
    elif (all(contrasts[c]["ic95"][0] > 0 for c in ("base", "generic"))
          and contrasts["generic"]["delta"] > floor95 and contrasts["generic"]["net_delta"] > 0):
        verdict = "SUCCESS on P41; not a validation against the full paradigm catalog"
    else:
        verdict = "NOT ESTABLISHED: the preregistered improvement criterion was not met"
    report = {"experiment": "P41", "complete_worlds": worlds, "triggered_worlds": triggered,
              "infra_attempts": sum(bool(r.get("infra_error")) for r in rows),
              "summary": summary, "directed_vs": contrasts,
              "noise_floor": {"mean": stats.mean(null_gaps), "p95": floor95, "per_cell": floors},
              "verdict": verdict,
              "limits": ["synthetic new worlds from the same generator", "declared-name coverage is not fact verification",
                         "only two base executors", "base and repairs use explicit budgets distinct from historical campaign"]}
    dump(OUT / "report.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "noise_floor"}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    for action in ("prepare", "estimate", "run", "analyse"):
        actions.add_argument(f"--{action}", action="store_true")
    parser.add_argument("--sealed", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.estimate:
        estimate()
    elif args.run:
        run(args.sealed)
    else:
        analyse()


if __name__ == "__main__":
    main()
