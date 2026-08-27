"""The experiment harness: run every paradigm on every task, then measure.

The full cross product is the point. Production would run one paradigm per task, but
the study needs the oracle, and the oracle is only knowable by having run them all.
That is what makes the numbers here checkable rather than asserted.

Results are appended incrementally and keyed by (task, paradigm, trial), so an
interrupted run resumes without redoing work. With `workers > 1` the ORDER of rows in
the file is nondeterministic: every row is self-contained so analysis is unaffected, but
the file is no longer a chronological log and must not be read as one. Wall-clock per
row also stops being a latency measurement once workers contend — token counts and
quality stay exact.
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import feasibility, grading
import httpx

from .config import Settings
from .llm import RETRYABLE_STATUS
from .features import FeatureExtractor, Features
from .llm import LLMClient, SealedCacheMiss, SeededClient, Usage
from .metrics import Observation, Study
from .paradigms import COST_PRIORS, FALLBACK, REGISTRY, Infeasible
from .embeddings import EmbeddingClient
from .retrieval import CorpusView, Retriever, build_arms
from .tools import VARIANTS, ToolSurface
from .assurance import Assurance
from .policy import Episode, Plasticity, PolicyBundle, promote
from .store import LearningStore


class _RetiredTaskCorpus:
    """Corpus view scoped to one task's units, with a pluggable retriever.

    Scoping matters: a paradigm must not be able to reach units the task did not
    supply, or high-cardinality tasks would leak into low-cardinality ones and the
    cardinality dial would stop meaning anything.

    The retriever is injected rather than hard-coded because retrieval quality decides
    which paradigm wins. Two of the seven search and four read, so a weak retriever
    handicaps the searchers and a perfect one makes reading pointless — either way the
    result would be about the tool rather than the topology. It is a controlled
    variable, recorded on every row.
    """

    def __init__(
        self,
        documents: dict[str, str],
        unit_ids: list[str],
        retriever: Retriever | None = None,
        task_id: str = "",
        relevant_units: list[str] | None = None,
    ) -> None:
        self._documents = documents
        self._unit_ids = list(unit_ids)
        self._retriever = retriever or LexicalRetriever()
        self._view = CorpusView(
            task_id=task_id,
            documents=documents,
            unit_ids=list(unit_ids),
            relevant_units=list(relevant_units or []),
        )

    def unit_ids(self) -> list[str]:
        return list(self._unit_ids)

    def read(self, unit_id: str) -> str:
        if unit_id not in self._unit_ids:
            # Not an empty string: a paradigm reaching outside its units is a bug we
            # want to see, not silently absorb.
            raise KeyError(f"Unit {unit_id} is not part of this task.")
        return self._documents[unit_id]

    def search(self, query: str, limit: int) -> list[tuple[str, str]]:
        ranked = self._retriever.rank(self._view, query, limit)
        return [(unit_id, self._documents[unit_id][:400]) for unit_id in ranked]


def _is_infrastructure(exc: BaseException) -> bool:
    """Whether this failure belongs to the transport rather than to the paradigm.

    Deliberately narrow. Anything not clearly infrastructural stays a paradigm failure
    and still scores zero, because the opposite mistake -- excusing a real bug as a
    network blip -- flatters the paradigm, which is the error this harness exists to
    avoid.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return isinstance(exc, (httpx.TransportError, httpx.StreamError))


@dataclass
class Row:
    task_id: str
    cell: str
    paradigm: str
    trial: int
    region: str
    utility: float
    cost_tokens: int
    calls: int
    wall_seconds: float
    iterations: int
    cross_unit_lookups: int
    hallucinated_units: int
    tool_usage: dict[str, Any]
    infeasible: bool
    retriever: str
    has_oracle: bool
    answer: str
    truth_coupling: float
    error: str = ""
    # An infrastructure failure is not a measurement. A 429 from the embedding
    # endpoint says nothing about the topology, so these rows are recorded and
    # then excluded from every statistic rather than scored as a wrong answer.
    infra_error: bool = False

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class Runner:
    def __init__(
        self,
        settings: Settings,
        corpus_name: str,
        sealed: bool = False,
        retriever_arm: str = "hybrid",
        surface_variant: str = "basic",
    ) -> None:
        # Hybrid is the default because it is what a real deployment has. The degraded
        # arms exist to test whether the conclusion depends on retrieval quality, not to
        # produce the headline number.
        embedder = EmbeddingClient(
            settings, settings.embedding_deployment, sealed=sealed
        )
        arms = build_arms(embedder=embedder)
        if retriever_arm not in arms:
            raise ValueError(
                f"Unknown retriever arm {retriever_arm!r}. Available: {sorted(arms)}"
            )
        if surface_variant not in VARIANTS:
            raise ValueError(
                f"Unknown surface variant {surface_variant!r}. Use one of {VARIANTS}."
            )
        self.surface_variant = surface_variant
        self.retriever_arm = retriever_arm
        self._retriever = arms[retriever_arm]
        # Kept so the surface can expose lexical and dense SEPARATELY alongside the
        # fused entry point. Offering only the fused view took the choice of modality
        # away from the agent, and that choice is part of the topology.
        self._arms = arms
        self._settings = settings
        self._client = LLMClient(settings, sealed=sealed)
        self._extractor = FeatureExtractor(self._client)

        root = settings.corpus_dir / corpus_name
        self._documents: dict[str, str] = json.loads(
            (root / "documents.json").read_text(encoding="utf-8")
        )
        self._tasks: list[dict[str, Any]] = json.loads(
            (root / "tasks.json").read_text(encoding="utf-8")
        )
        self._corpus_name = corpus_name
        # One file per (corpus, retriever arm). Pooling arms would average over the
        # very variable the arms exist to separate.
        suffix = "" if retriever_arm == "hybrid" else f"_{retriever_arm}"
        if surface_variant != "basic":
            suffix += f"_{surface_variant}"
        self._results_path = (
            settings.results_dir / f"{corpus_name}{suffix}_rows.jsonl"
        )
        self.store = LearningStore(settings.results_dir, corpus_name)

    # -- features ----------------------------------------------------------

    def features_for(self, task: dict[str, Any], allow_derived: bool) -> Features:
        payload = {
            "question": task["question"],
            "units": task["unit_ids"],
            "oracle": task["oracle"],
            "irreversible": task.get("irreversible", False),
            "shared_writes": task.get("shared_writes", False),
            "budget_tokens": task["budget_tokens"],
        }
        features, _ = self._extractor.extract(payload, allow_derived=allow_derived)
        return features

    # -- execution ---------------------------------------------------------

    def existing_keys(self) -> set[tuple[str, str, int]]:
        if not self._results_path.exists():
            return set()
        keys: set[tuple[str, str, int]] = set()
        for line in self._results_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            keys.add((row["task_id"], row["paradigm"], row.get("trial", 0)))
        return keys

    def run_cross_product(
        self,
        paradigms: list[str] | None = None,
        limit: int | None = None,
        resume: bool = True,
        repeat: int = 1,
        task_ids: list[str] | None = None,
        workers: int = 1,
    ) -> list[Row]:
        """Run the cross product, `repeat` times per cell.

        repeat > 1 is what makes the noise floor measurable. Since gpt-5-chat refuses
        an explicit temperature, one trial per cell cannot separate a real paradigm
        difference from sampling noise, and the oracle is biased upward by that noise.
        """
        if repeat < 1:
            raise ValueError("repeat must be >= 1")
        selected = paradigms or sorted(REGISTRY)
        # An explicit task list beats `limit`: probing whether a specific feature cell
        # discriminates needs those tasks, not the first N in generation order.
        if task_ids:
            missing = set(task_ids) - {t["task_id"] for t in self._tasks}
            if missing:
                raise ValueError(f"Unknown task ids: {sorted(missing)}")
            tasks = [t for t in self._tasks if t["task_id"] in set(task_ids)]
        else:
            tasks = self._tasks[:limit] if limit else self._tasks
        done = self.existing_keys() if resume else set()

        if workers < 1:
            raise ValueError("workers must be >= 1")

        rows: list[Row] = []
        total = len(tasks) * len(selected) * repeat
        completed = 0
        sink_lock = threading.Lock()
        counter_lock = threading.Lock()

        with self._results_path.open("a", encoding="utf-8") as sink:
            for task in tasks:
                # Derived features are computed once per task, not once per paradigm:
                # the feature vector describes the task, and recomputing it per
                # paradigm would charge the same estimate six times.
                features = self.features_for(task, allow_derived=True)
                # A fresh surface per task: the usage trace must not accumulate
                # across tasks, or every paradigm would inherit the previous task's
                # reads and the trace would stop describing what it actually did.
                def make_surface() -> ToolSurface:
                    view = CorpusView(
                        task_id=task["task_id"],
                        documents=self._documents,
                        unit_ids=task["unit_ids"],
                        relevant_units=task.get("relevant_units", []),
                    )
                    return ToolSurface(
                        view=view,
                        hybrid=self._retriever,
                        semantic=self._arms["semantic"],
                        lexical=self._arms["lexical"],
                        variant=self.surface_variant,
                        budget_tokens=int(task["budget_tokens"]),
                    )

                # The grid of cells for this task. Tasks stay sequential because each
                # begins with one feature extraction that the whole grid shares.
                # Feasibility is arithmetic over what the task already declares, so it
                # costs nothing and is checked before any token is spent. A paradigm that
                # cannot run is RECORDED as infeasible rather than run into a wall or
                # silently skipped: the record has to show it was considered and why it
                # could not go.
                _, verdicts = feasibility.admissible(selected, self._documents, task)

                cells = [
                    (trial, name)
                    for trial in range(repeat)
                    for name in selected
                    if (task["task_id"], name, trial) not in done
                ]
                skipped = len(selected) * repeat - len(cells)
                with counter_lock:
                    completed += skipped

                def execute(cell: tuple[int, str]) -> Row:
                    trial, name = cell
                    verdict = verdicts[name]
                    if not verdict.feasible:
                        return self._infeasible_row(task, name, features, trial, verdict)
                    # One seed per trial, shared by every paradigm in that trial, so
                    # paradigms are compared under the same sampling conditions.
                    client = SeededClient(self._client, self._settings.seed + trial)
                    return self._run_one(
                        task, name, features, make_surface(), trial, client
                    )

                def record(row: Row, trial: int, name: str) -> None:
                    nonlocal completed
                    with counter_lock:
                        completed += 1
                        seen = completed
                    with sink_lock:
                        sink.write(json.dumps(row.as_dict(), ensure_ascii=False) + "\n")
                        sink.flush()
                    status = row.error or f"u={row.utility:.3f}"
                    # flush=True: stdout is block-buffered when redirected, so a
                    # background run would show no progress until it finished.
                    print(
                        f"[{seen}/{total}] {task['task_id']:<14} "
                        f"{name:<14} t{trial} {status:<24} tok={row.cost_tokens}",
                        flush=True,
                    )

                if workers == 1:
                    for trial, name in cells:
                        row = execute((trial, name))
                        rows.append(row)
                        record(row, trial, name)
                else:
                    with ThreadPoolExecutor(max_workers=workers) as pool:
                        futures = {
                            pool.submit(execute, cell): cell for cell in cells
                        }
                        for future in as_completed(futures):
                            trial, name = futures[future]
                            row = future.result()
                            rows.append(row)
                            record(row, trial, name)

        return rows

    def _infeasible_row(
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

    def _run_one(
        self,
        task: dict[str, Any],
        paradigm: str,
        features: Features,
        surface: ToolSurface,
        trial: int,
        client: Any,
    ) -> Row:
        started = time.perf_counter()
        try:
            result = REGISTRY[paradigm](client, surface, task)
            utility = grading.score(result.answer, task["oracle"])
            return Row(
                task_id=task["task_id"],
                cell=task["cell"],
                paradigm=paradigm,
                trial=trial,
                region=features.region(),
                utility=utility,
                cost_tokens=result.usage.total_tokens,
                calls=result.usage.calls,
                wall_seconds=round(time.perf_counter() - started, 3),
                iterations=result.iterations,
                cross_unit_lookups=result.cross_unit_lookups,
                hallucinated_units=result.hallucinated_units,
                tool_usage=result.tool_usage,
                infeasible=False,
                retriever=self.retriever_arm,
                # Declared, never inferred from `bool(oracle)`: a task whose correct
                # answer is the empty set still HAS a cheap oracle, and inferring it
                # would mislabel exactly those tasks as unverifiable.
                has_oracle=bool(task.get("has_oracle", True)),
                answer=result.answer[:500],
                truth_coupling=task.get("truth_coupling", 0.0),
            )
        except Infeasible as reason:
            # Recorded as a distinct outcome. It scores no utility — nothing was
            # answered — but it is not a wrong answer, and its zero cost must not enter
            # the cost model as if the paradigm had run cheaply.
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
                tool_usage={"infeasible": str(reason)},
                infeasible=True,
                retriever=self.retriever_arm,
                has_oracle=bool(task.get("has_oracle", True)),
                answer="",
                truth_coupling=task.get("truth_coupling", 0.0),
            )
        except SealedCacheMiss:
            # Never swallowed: a sealed replay that silently went live would not be a
            # replay at all.
            raise
        except Exception as exc:  # noqa: BLE001
            # A paradigm that blows up on a task scores zero for that task. That is the
            # honest utility, and hiding the failure would flatter the paradigm -- but
            # only when the failure is the paradigm's. A rate limit or a dropped
            # connection is the transport's, and scoring it as a wrong answer attributes
            # someone else's quota to a topology.
            infra = _is_infrastructure(exc)
            # The tokens the paradigm burned before blowing up are gone from its own
            # Usage (it never returned one), but the client metered them. Recording 0
            # here would teach the cost model that this paradigm fails cheaply.
            spent = getattr(client, "spent", None) or Usage()
            return Row(
                task_id=task["task_id"],
                cell=task["cell"],
                paradigm=paradigm,
                trial=trial,
                region=features.region(),
                utility=0.0,
                cost_tokens=spent.total_tokens,
                calls=spent.calls,
                wall_seconds=round(time.perf_counter() - started, 3),
                iterations=0,
                cross_unit_lookups=0,
                hallucinated_units=0,
                tool_usage={},
                infeasible=False,
                retriever=self.retriever_arm,
                has_oracle=bool(task.get("has_oracle", True)),
                answer="",
                truth_coupling=task.get("truth_coupling", 0.0),
                error=f"{type(exc).__name__}: {exc}"[:300],
                infra_error=infra,
            )

    # -- analysis ----------------------------------------------------------

    def load_rows(self, include_infra: bool = False) -> list[dict[str, Any]]:
        """Rows for analysis. `infra_error` rows are excluded BY DEFAULT.

        They are recorded — the file keeps them — but they are not measurements:
        a 429 that outlived the retry budget says nothing about the paradigm.
        Excluding them only in `study()` let them leak into `episodes()` (theta
        learned that a paradigm "fails" wherever the quota ran dry), `replicates()`
        (zeros inflating the noise floor) and `consolidate()`. One gate, here.
        """
        if not self._results_path.exists():
            return []
        rows = [
            json.loads(line)
            for line in self._results_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if include_infra:
            return rows
        return [r for r in rows if not r.get("infra_error")]

    def study(self, lambda_cost: float = 0.0) -> Study:
        """Study over trial-averaged cells.

        Averaging across trials BEFORE taking the oracle is what shrinks the upward
        bias in `max`. Feeding raw trials in would let the oracle pick each paradigm's
        luckiest sample and inflate the gap.
        """
        cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
        dropped = 0
        for r in self.load_rows():
            # An infrastructure failure is not evidence about a paradigm. Averaging it in
            # would drag the cell down by however much of the quota someone else used.
            if r.get("infra_error"):
                dropped += 1
                continue
            cells.setdefault((r["task_id"], r["paradigm"]), []).append(r)
        if dropped:
            print(
                f"  [study] {dropped} filas excluidas por fallo de infraestructura "
                f"(no son mediciones)"
            )

        return Study(
            (Observation(
                task_id=task_id,
                region=rows[0]["region"],
                paradigm=paradigm,
                utility=sum(x["utility"] for x in rows) / len(rows),
                cost_tokens=int(sum(x["cost_tokens"] for x in rows) / len(rows)),
                has_oracle=rows[0]["has_oracle"],
                # Max across replicates, not mean: the question is whether the paradigm
                # was ever in a position to answer, and one trial that reached the
                # evidence establishes that it could.
                relevant_units_read=max(
                    ((x.get("tool_usage") or {}).get("relevant_units_read") or 0)
                    for x in rows
                ),
                relevant_units_available=self._relevant_count(task_id),
            )
            for (task_id, paradigm), rows in cells.items()),
            lambda_cost=lambda_cost,
        )

    def _relevant_count(self, task_id: str) -> int:
        task = next((t for t in self._tasks if t["task_id"] == task_id), None)
        return len(task.get("relevant_units", [])) if task else 0

    def replicates(self, paradigm: str | None = None) -> dict[str, list[float]]:
        """Per-task replicate utilities for one paradigm, for the noise floor.

        Defaults to the fallback: it is the paradigm every task runs, and the one whose
        variance the deferral decision is measured against.
        """
        target = paradigm or FALLBACK
        out: dict[str, list[float]] = {}
        for r in self.load_rows():
            if r["paradigm"] == target:
                out.setdefault(r["task_id"], []).append(r["utility"])
        return out

    def episodes(self) -> list[Episode]:
        """Convert rows into learning episodes.

        `was_best` is computed per task against the whole row, so the reinforcement
        signal answers 'was this the right paradigm here', not 'did it produce
        something'. That distinction is what the router actually needs to estimate.
        """
        rows = self.load_rows()
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
                was_best=(r["utility"] >= best[r["task_id"]] > 0.0),
            )
            for r in rows
        ]

    # -- the report --------------------------------------------------------

    def report(
        self,
        assurance: Assurance = Assurance.STANDARD,
        lambda_cost: float = 0.0,
    ) -> dict[str, Any]:
        from .assurance import PROFILES  # local imports: avoid a cycle via policy
        from .router import Router

        study = self.study(lambda_cost=lambda_cost)
        episodes = self.episodes()

        # Learn theta from the observed episodes, then evaluate the router it implies.
        # Persisted, not discarded: a theta that only ever existed inside this call
        # could not be audited, diffed against its successor, or promoted. Persisted
        # in `fitted/`, OUTSIDE the glob that `latest_theta_path()` treats as the
        # live policy: a report is a reading, and a reading must not install an
        # unpromoted bundle as production — that path goes through `promote()` only.
        cold = PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3)
        learned = Plasticity.candidate(
            cold, episodes, tau=0.3, notes=f"fitted from {len(episodes)} episodes"
        )
        fitted_dir = self.store.policy_dir / "fitted"
        fitted_dir.mkdir(parents=True, exist_ok=True)
        learned.save(fitted_dir)
        router = Router(learned, COST_PRIORS, FALLBACK)
        profile = PROFILES[assurance]

        rows_by_task: dict[str, dict[str, Any]] = {}
        for r in self.load_rows():
            rows_by_task.setdefault(r["task_id"], {})[r["paradigm"]] = r

        def task_of(task_id: str) -> dict[str, Any]:
            return next(t for t in self._tasks if t["task_id"] == task_id)

        def region_of(task_id: str) -> str:
            return next(iter(rows_by_task[task_id].values()))["region"]

        def decide(task_id: str) -> str:
            plan = router.plan(
                task=task_of(task_id),
                candidates=sorted(rows_by_task[task_id]),
                region=region_of(task_id),
                requested=assurance,
            )
            # This is what makes `log_belief_base` mean something. The flag was declared
            # on the A2 and A3 profiles and nothing acted on it, so no belief base was
            # ever written, so calibration could never be computed, so elicited
            # credence could never earn trust. Honouring the flag closes that loop.
            if profile.log_belief_base:
                self.store.append_belief_base(
                    plan.verdict.get("beliefs", {}),
                    context={
                        "task_id": task_id,
                        "assurance": assurance.label,
                        "action": plan.action,
                        "paradigm": plan.paradigm,
                        "theta_version": plan.theta_version,
                    },
                )
            return plan.paradigm

        def rank(task_id: str) -> float:
            # The confidence that drives the risk-coverage sweep is theta's margin:
            # a fact about the bundle, not a credence about the world.
            return router.theta_assertions(
                region_of(task_id), sorted(rows_by_task[task_id])
            )[1]

        ladder = sorted(REGISTRY, key=lambda p: COST_PRIORS[p])

        calibration = self.store.rebuild_calibration()

        return {
            "corpus": self._corpus_name,
            "assurance": assurance.label,
            "learning_state": self.store.summary(),
            "calibration": calibration,
            "settings": self._settings.fingerprint(),
            "theta_version": learned.version,
            "theta_signature": learned.signature,
            "summary": study.summary(),
            "oracle_gap_credibility": study.credible_oracle_gap(self.replicates()),
            "selection_terms": study.selection_terms(decide).as_dict(),
            "router_captured_fraction": round(study.captured_fraction(decide), 5),
            "risk_coverage": study.risk_coverage(rank, decide),
            "cascade": study.cascade_value(ladder, detector_sensitivity=1.0),
            "cascade_weak_detector": study.cascade_value(ladder, detector_sensitivity=0.6),
        }

    def consolidate(self, tau: float = 0.3) -> dict[str, Any]:
        """Run one sleep cycle over the recorded episodes and persist the result.

        Costs nothing in inference: the cross product is already on disk, so
        consolidation is counterfactual replay over the record.

        Copy-on-write. The incumbent theta is never mutated; a candidate is built and
        installed only if the promotion guard says it does not regress on held-out
        episodes. Discovered propositions are persisted so that being re-proposed on a
        different split across cycles becomes visible — one discovery may be an
        artefact, three in a row is a finding.
        """
        from .assurance import Assurance  # local import: avoids a cycle
        from .consolidation import sleep_cycle
        from .router import Router

        rows = self.load_rows()
        if not rows:
            raise RuntimeError("Nothing to consolidate: no execution record yet.")

        latest = self.store.latest_theta_path()
        incumbent = (
            PolicyBundle.load(latest) if latest
            else PolicyBundle.cold_start(fallback=FALLBACK, tau=tau)
        )
        if latest is None:
            incumbent.save(self.store.policy_dir)

        def promote_fn(inc: PolicyBundle, cand: PolicyBundle, holdout: list[Episode]):
            return promote(
                inc, cand, holdout,
                lambda bundle, eps: Router(
                    bundle, COST_PRIORS, FALLBACK
                ).value_on(eps, requested=Assurance.STANDARD),
            )

        cycle = self.store.next_cycle()
        installed, report = sleep_cycle(
            incumbent=incumbent,
            rows=rows,
            episodes=self.episodes(),
            belief_log=self.store.belief_log(),
            promote_fn=promote_fn,
            cycle=cycle,
            tau=tau,
        )

        body = report.as_dict()
        body["discoveries_persisted"] = self.store.record_discoveries(
            report.discovered, cycle
        )
        if installed.signature != incumbent.signature:
            body["installed_theta"] = str(installed.save(self.store.policy_dir))
        else:
            body["installed_theta"] = None

        self.store.save_dream(body)
        body["learning_state"] = self.store.summary()
        return body

    def save_report(self, report: dict[str, Any]) -> Path:
        path = self._settings.results_dir / f"{self._corpus_name}_report.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
