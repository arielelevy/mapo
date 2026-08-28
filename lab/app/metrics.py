"""The measurement layer: the quantities the paper actually claims.

Everything here is computed from a full cross product of tasks x paradigms, so the
oracle is known exactly rather than estimated. That is the whole reason the harness
runs every paradigm on every task even though production would run one.

The headline quantities:

    oracle_gap      E[max_p u] - max_p E[u]      the prize that exists at all
    captured        (V(router) - V(best_fixed)) / oracle_gap
    pi, alpha, beta, G, L                        the terms of Theorem 1
    beta_max        pi*alpha*G / ((1-pi)*L)      Corollary 2's impossibility threshold
    risk-coverage   captured fraction as a function of coverage

A useful identity, and the bridge to published results: with S the set of tasks where
some paradigm beats the best fixed one, and G the mean gain on S,

    oracle_gap == pi * G

So a published router's headline numbers determine its implied beta. The 17.1pp oracle
gap reported by Select-then-Solve IS pi*G for their suite.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, asdict
from typing import Any, Callable, Iterable

import numpy as np


@dataclass(frozen=True)
class Observation:
    """One (task, paradigm) cell of the cross product."""

    task_id: str
    region: str
    paradigm: str
    utility: float
    cost_tokens: int
    # El SPLIT, porque entrada y salida no valen lo mismo y los brazos se diferencian
    # justo en esa proporcion. `cost_tokens` sigue siendo el total y es sobre lo que
    # barre lambda; el split existe para poder convertir a plata sin promediar precios.
    # Con default 0: los estudios armados antes de que la fila lo guardara no lo tienen,
    # y ahi 0 significa "no registrado" — se reporta como tal, no como cero medido.
    prompt_tokens: int = 0
    completion_tokens: int = 0
    has_oracle: bool = True
    # How many answer-bearing units the paradigm actually read, and how many existed.
    # Optional because studies assembled before the tool trace existed do not have it;
    # absent values are reported as unattributable rather than guessed at.
    relevant_units_read: int | None = None
    relevant_units_available: int | None = None


@dataclass
class SelectionTerms:
    """The terms of the Selection Value Theorem, measured rather than assumed.

    Two losses, and the distinction matters. `loss_potential` is a property of the
    TASK DISTRIBUTION: the loss a misroute would cost, averaged over the non-fallback
    paradigms. `loss_realised` is a property of THIS ROUTER: the loss it actually paid
    on the tasks it actually misrouted.

    beta_max must be computed from `loss_potential`. Using the realised loss makes the
    threshold circular, and a perfect router (which misroutes nothing, so realises no
    loss) would report beta_max = infinity and appear to face no constraint at all.
    """

    pi: float
    alpha: float
    beta: float
    gain: float
    loss_potential: float
    loss_realised: float
    loss_p90: float
    beta_max: float
    holds: bool

    def as_dict(self) -> dict[str, Any]:
        def clean(v: Any) -> Any:
            # beta_max is infinite whenever the potential loss is zero, and
            # json.dumps writes bare `Infinity`, which is not valid JSON. Any strict
            # parser rejects the whole report file, so the sentinel becomes null.
            if isinstance(v, float):
                return None if math.isinf(v) or math.isnan(v) else round(v, 5)
            return v

        return {k: clean(v) for k, v in asdict(self).items()}


class Study:
    """A completed cross product, ready to be interrogated.

    `lambda_cost` sets how much quality a unit of relative cost is worth. It is a
    parameter of the ANALYSIS, never of the data: raw quality and raw cost are stored
    unmodified and the trade-off is applied on read, so the same record can be
    interrogated at several preferences and a reader can pick their own.
    """

    def __init__(
        self, observations: Iterable[Observation], lambda_cost: float = 0.0
    ) -> None:
        self._obs = list(observations)
        if not self._obs:
            raise ValueError("A study needs at least one observation.")
        if lambda_cost < 0:
            raise ValueError("lambda_cost must be >= 0.")
        self.lambda_cost = lambda_cost

        self._by_task: dict[str, dict[str, Observation]] = {}
        for o in self._obs:
            self._by_task.setdefault(o.task_id, {})[o.paradigm] = o

        self.paradigms = sorted({o.paradigm for o in self._obs})
        self.tasks = sorted(self._by_task)

        # Cheapest observed cost per task, EXCLUDING zero-cost rows. Normalising by the
        # minimum keeps the penalty scale-free across tasks of very different size and
        # guarantees the cheapest paradigm is never penalised.
        #
        # The exclusion is not defensive tidying. A paradigm that crashed recorded zero
        # tokens, which made the floor 1 and turned every other paradigm's cost RATIO
        # into its raw token count — ratios of 18,000 instead of 6, which flipped the
        # best fixed paradigm to the worst one and produced a curve that looked
        # plausible and was nonsense. A failed run produced no work, so it is not
        # evidence about what the work costs.
        self._min_cost: dict[str, int] = {}
        self._zero_cost_rows = 0
        for task, row in self._by_task.items():
            positive = [o.cost_tokens for o in row.values() if o.cost_tokens > 0]
            self._zero_cost_rows += len(row) - len(positive)
            # A task where nothing succeeded has no cost scale. Its ratios collapse to
            # 1 so it contributes no cost penalty either way, rather than an invented one.
            self._min_cost[task] = min(positive) if positive else 0

        # Only tasks with a complete row can be used: a missing cell would silently
        # bias the oracle downward and inflate every router's apparent skill.
        self.complete_tasks = [
            t for t in self.tasks
            if set(self._by_task[t]) == set(self.paradigms)
        ]

    # -- basic quantities --------------------------------------------------

    def quality(self, task_id: str, paradigm: str) -> float:
        """Raw measured quality. Never adjusted."""
        return self._by_task[task_id][paradigm].utility

    def cost_ratio(self, task_id: str, paradigm: str) -> float:
        """Cost as a multiple of the cheapest SUCCESSFUL paradigm on this task.

        Returns 1.0 — no penalty — for a row that recorded no cost, and for a task
        where nothing succeeded. Both cases carry no information about cost, and
        inventing a penalty for them would be worse than declining to.
        """
        floor = self._min_cost[task_id]
        if floor <= 0:
            return 1.0
        cost = self._by_task[task_id][paradigm].cost_tokens
        if cost <= 0:
            return 1.0
        return cost / floor

    def utility(self, task_id: str, paradigm: str) -> float:
        """Quality net of the cost preference. Identical to quality at lambda = 0."""
        if self.lambda_cost == 0.0:
            return self.quality(task_id, paradigm)
        return self.quality(task_id, paradigm) - self.lambda_cost * (
            self.cost_ratio(task_id, paradigm) - 1.0
        )

    def mean_utility(self, paradigm: str) -> float:
        return float(
            np.mean([self.utility(t, paradigm) for t in self.complete_tasks])
        )

    def best_fixed(self) -> str:
        return max(self.paradigms, key=self.mean_utility)

    def oracle_value(self) -> float:
        return float(
            np.mean([
                max(self.utility(t, p) for p in self.paradigms)
                for t in self.complete_tasks
            ])
        )

    def oracle_gap(self) -> float:
        return self.oracle_value() - self.mean_utility(self.best_fixed())

    # -- Theorem 1 ---------------------------------------------------------

    def selection_terms(self, decide: Callable[[str], str]) -> SelectionTerms:
        """Measure pi, alpha, beta, G, L for a given decision function.

        `decide(task_id) -> paradigm` stands in for any router: ours, a prose prompt,
        an embedding model, or a constant.
        """
        fallback = self.best_fixed()

        in_s: list[str] = []      # specialisation genuinely helps
        out_s: list[str] = []     # it does not
        for t in self.complete_tasks:
            best = max(self.utility(t, p) for p in self.paradigms)
            (in_s if best > self.utility(t, fallback) else out_s).append(t)

        n = len(self.complete_tasks)
        pi = len(in_s) / n if n else 0.0

        gains = [
            max(self.utility(t, p) for p in self.paradigms) - self.utility(t, fallback)
            for t in in_s
        ]
        gain = float(np.mean(gains)) if gains else 0.0

        # alpha / beta are about the ROUTING ACTION, so they are measured on whether
        # the router left the fallback, not on whether it happened to be right.
        routed_in = [t for t in in_s if decide(t) != fallback]
        routed_out = [t for t in out_s if decide(t) != fallback]

        alpha = len(routed_in) / len(in_s) if in_s else 0.0
        beta = len(routed_out) / len(out_s) if out_s else 0.0

        # Realised loss: what THIS router actually paid, on the tasks it actually
        # misrouted. Exact accounting, no independence assumption needed.
        realised = [
            self.utility(t, fallback) - self.utility(t, decide(t))
            for t in routed_out
        ]
        loss_realised = float(np.mean(realised)) if realised else 0.0
        loss_p90 = float(np.percentile(realised, 90)) if realised else 0.0

        # Potential loss: a property of the distribution, independent of any router.
        # Averaged over the non-fallback paradigms, i.e. the expected cost of an
        # arbitrary misroute. This is what beta_max has to be built from.
        alternatives = [p for p in self.paradigms if p != fallback]
        potential = [
            self.utility(t, fallback) - self.utility(t, p)
            for t in out_s
            for p in alternatives
        ]
        loss_potential = float(np.mean(potential)) if potential else 0.0

        beta_max = (
            (pi * alpha * gain) / ((1.0 - pi) * loss_potential)
            if (1.0 - pi) > 0 and loss_potential > 0
            else float("inf")
        )

        return SelectionTerms(
            pi=pi,
            alpha=alpha,
            beta=beta,
            gain=gain,
            loss_potential=loss_potential,
            loss_realised=loss_realised,
            loss_p90=loss_p90,
            beta_max=beta_max,
            # The condition is checked against the REALISED loss, because that is what
            # this router actually paid. beta_max, above, is the distributional bound
            # any router must respect.
            holds=(pi * alpha * gain) > ((1.0 - pi) * beta * loss_realised),
        )

    # -- router valuation --------------------------------------------------

    def router_value(self, decide: Callable[[str], str]) -> float:
        return float(
            np.mean([self.utility(t, decide(t)) for t in self.complete_tasks])
        )

    def captured_fraction(self, decide: Callable[[str], str]) -> float:
        """Share of the oracle gap a router recovers.

        This is the metric that replaces "router accuracy". Select-then-Solve's router
        sits at roughly 0.16-0.37 here depending on the backing model.
        """
        gap = self.oracle_gap()
        if gap <= 0:
            return 0.0
        return (self.router_value(decide) - self.mean_utility(self.best_fixed())) / gap

    def risk_coverage(
        self,
        rank: Callable[[str], float],
        propose: Callable[[str], str],
        steps: int = 21,
    ) -> list[dict[str, float]]:
        """Sweep the deferral threshold and report the curve.

        `rank(task)` is the confidence score; `propose(task)` is the paradigm that
        would be used if the router does not defer. At coverage 0 the curve is pinned
        to the fallback, which is why a selective router can never do worse than its
        fallback: the safety property is structural, not empirical.
        """
        fallback = self.best_fixed()
        scores = sorted({rank(t) for t in self.complete_tasks})
        if not scores:
            return []

        thresholds = np.linspace(min(scores), max(scores), steps)
        curve: list[dict[str, float]] = []

        for tau in thresholds:
            def decide(task_id: str, _tau: float = float(tau)) -> str:
                return propose(task_id) if rank(task_id) > _tau else fallback

            routed = [t for t in self.complete_tasks if rank(t) > tau]
            curve.append({
                "tau": round(float(tau), 5),
                "coverage": round(len(routed) / len(self.complete_tasks), 5),
                "captured": round(self.captured_fraction(decide), 5),
                "value": round(self.router_value(decide), 5),
            })

        return curve

    # -- Cascade Dominance Theorem ----------------------------------------

    def cascade_value(
        self,
        ladder: list[str],
        detector_sensitivity: float = 1.0,
        success_threshold: float = 1.0,
    ) -> dict[str, Any]:
        """Simulate a cost-ordered cascade and compare it to the best fixed paradigm.

        The claim under test: where a cheap failure detector exists, escalating on
        observed failure beats predicting which paradigm to use, because a misstep
        costs tokens instead of answer quality.

        `detector_sensitivity` is the probability that a genuine failure is caught.
        It is the critical variable: an insensitive detector silently returns the
        problem to the router regime with the ladder already paid for. It is applied
        deterministically via a task-id hash rather than sampled, so repeated runs of
        the same study give the same figure.
        """
        # LA ESCALERA PUEDE NOMBRAR BRAZOS QUE ESTE ESTUDIO NO CORRIO, y eso no es un
        # error del estudio: el catalogo tiene trece brazos y una corrida mide cinco. El
        # indexado directo levantaba `KeyError` y volteaba el informe entero — un
        # `report()` sobre un corpus que no incluye el primer peldano moria en vez de
        # decir que no puede evaluar la cascada.
        #
        # Se declara en vez de suponerse: si el peldano no esta, no hay cascada que
        # medir, y el resultado LO DICE en lugar de devolver un cero que se lee como
        # «la cascada no rinde».
        missing = [p for p in ladder if not any(p in self._by_task[t]
                                                for t in self.complete_tasks)]
        if missing:
            return {
                "eligible_tasks": 0,
                "note": (
                    f"la escalera nombra brazos que este estudio no corrio: {missing}. "
                    f"No hay cascada que medir — distinto de una cascada que no rinde."
                ),
            }
        eligible = [
            t for t in self.complete_tasks
            if ladder[0] in self._by_task[t]
            and self._by_task[t][ladder[0]].has_oracle
        ]
        if not eligible:
            return {"eligible_tasks": 0, "note": "no verifiable tasks in this study"}

        total_utility = 0.0
        total_cost = 0
        escalations = 0

        for task in eligible:
            achieved = 0.0
            spent = 0
            best_seen = 0.0
            for depth, paradigm in enumerate(ladder):
                obs = self._by_task[task][paradigm]
                spent += obs.cost_tokens
                current = self.utility(task, paradigm)
                best_seen = max(best_seen, current)
                # When every failure so far was DETECTED, the system retains the
                # answers it collected and may return the best of them — that is
                # the (generous, registered) semantics behind Finding 2's "whole
                # ladder, 100% of the gap, at 4.4x".
                achieved = best_seen

                # The success test uses raw QUALITY, not cost-adjusted utility: a
                # detector checks whether the answer is right, and it cannot see
                # the analyst's cost preference.
                if self.quality(task, paradigm) >= success_threshold:
                    break

                # Failure occurred. Was it detected? Deterministic pseudo-draw —
                # sha256, not hash(): builtin str hashing is salted per process,
                # so the same study gave a different figure on every run.
                digest = hashlib.sha256(f"{task}/{depth}".encode("utf-8")).hexdigest()
                draw = (int(digest, 16) % 1000) / 1000.0
                if draw >= detector_sensitivity:
                    # Missed failure: the system BELIEVES this rung succeeded and
                    # returns THIS answer. Crediting max() here counted a good
                    # earlier answer the system had already discarded, flattering
                    # the cascade exactly when the detector is weak.
                    achieved = current
                    break
                if depth < len(ladder) - 1:
                    escalations += 1

            total_utility += achieved
            total_cost += spent

        n = len(eligible)
        cascade_utility = total_utility / n
        fixed = self.best_fixed()
        fixed_utility = float(np.mean([self.utility(t, fixed) for t in eligible]))
        fixed_cost = float(
            np.mean([self._by_task[t][fixed].cost_tokens for t in eligible])
        )
        oracle = float(
            np.mean([
                max(self.utility(t, p) for p in self.paradigms) for t in eligible
            ])
        )
        gap = oracle - fixed_utility

        return {
            "eligible_tasks": n,
            "ladder": ladder,
            "detector_sensitivity": detector_sensitivity,
            "cascade_utility": round(cascade_utility, 5),
            "best_fixed": fixed,
            "best_fixed_utility": round(fixed_utility, 5),
            "oracle_utility": round(oracle, 5),
            "captured_fraction": (
                round((cascade_utility - fixed_utility) / gap, 5) if gap > 1e-9 else None
            ),
            "cascade_mean_cost": round(total_cost / n, 1),
            "best_fixed_mean_cost": round(fixed_cost, 1),
            "cost_ratio": round((total_cost / n) / fixed_cost, 3) if fixed_cost else None,
            "escalations": escalations,
            "dominates_best_fixed": cascade_utility > fixed_utility,
        }

    # -- failure attribution ------------------------------------------------

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

    # -- cost sensitivity --------------------------------------------------

    def gap_vs_lambda(
        self, lambdas: Iterable[float] = (0.0, 0.02, 0.05, 0.1, 0.2, 0.5)
    ) -> list[dict[str, Any]]:
        """Oracle gap and winner as a function of the cost preference.

        This replaces the choice of a lambda with a figure. At lambda = 0 the gap is the
        pure quality gap — zero when every paradigm answers correctly. As lambda grows,
        cost enters and the best fixed paradigm flips from the thorough and expensive to
        the cheap. The lambda at which it flips is itself the interesting quantity: it
        says how much a user would have to value quality for the expensive topology to
        be worth choosing.
        """
        curve: list[dict[str, Any]] = []
        for lam in lambdas:
            view = Study(self._obs, lambda_cost=lam)
            best = view.best_fixed()
            curve.append({
                "lambda": lam,
                "best_fixed": best,
                "best_fixed_utility": round(view.mean_utility(best), 5),
                "oracle_value": round(view.oracle_value(), 5),
                "oracle_gap": round(view.oracle_gap(), 5),
            })
        return curve

    def cost_spread(self) -> dict[str, Any]:
        """Cost dispersion at equal quality — the thing pure-quality utility hides."""
        rows = {}
        for paradigm in self.paradigms:
            costs = [
                self._by_task[t][paradigm].cost_tokens for t in self.complete_tasks
            ]
            quals = [self.quality(t, paradigm) for t in self.complete_tasks]
            rows[paradigm] = {
                "mean_cost": round(float(np.mean(costs)), 1),
                "mean_quality": round(float(np.mean(quals)), 5),
            }
        cheapest = min(rows.values(), key=lambda r: r["mean_cost"])["mean_cost"]
        for r in rows.values():
            r["cost_multiple"] = round(r["mean_cost"] / max(1.0, cheapest), 2)
        return rows

    # -- measurement noise -------------------------------------------------

    @staticmethod
    def noise_floor(replicates: dict[str, list[float]]) -> dict[str, Any]:
        """The oracle gap produced by measurement noise alone.

        WHY THIS IS NOT OPTIONAL. The oracle takes a maximum over per-task utility
        estimates, and a maximum over noisy estimates is biased upward:

            E[max_p u_hat_p]  >  max_p E[u_p]

        even when every paradigm is identical. So a measured oracle gap always
        contains a noise component, and reporting it as if it were all real would
        overstate the prize and flatter Claim 1. This matters here specifically
        because gpt-5-chat refuses an explicit temperature, so runs are sampled at
        the model default rather than greedily.

        The estimate is direct rather than modelled: take k replicate runs of the
        SAME paradigm on each task, treat the replicates as if they were k distinct
        paradigms, and compute the oracle gap over them. Every point of the result is
        noise by construction, because the "paradigms" are the same thing.

        A real oracle gap is only credible to the extent that it exceeds this floor.
        """
        usable = {t: u for t, u in replicates.items() if len(u) >= 2}
        if not usable:
            return {"tasks": 0, "note": "need >= 2 trials per task to estimate noise"}

        k = min(len(u) for u in usable.values())
        trials = np.array([u[:k] for u in usable.values()])  # tasks x k

        per_trial_means = trials.mean(axis=0)          # each ~ the same quantity
        best_fixed_equivalent = float(per_trial_means.max())
        oracle_equivalent = float(trials.max(axis=1).mean())

        return {
            "tasks": len(usable),
            "trials_per_task": k,
            "noise_oracle_gap": round(oracle_equivalent - best_fixed_equivalent, 5),
            "within_task_sd": round(float(trials.std(axis=1).mean()), 5),
            "per_trial_means": [round(float(x), 5) for x in per_trial_means],
        }

    def credible_oracle_gap(self, replicates: dict[str, list[float]]) -> dict[str, Any]:
        """Measured oracle gap alongside the noise floor it must clear."""
        floor = self.noise_floor(replicates)
        measured = self.oracle_gap()
        noise = floor.get("noise_oracle_gap")
        return {
            "measured_oracle_gap": round(measured, 5),
            "noise_floor": noise,
            "net_of_noise": round(measured - noise, 5) if noise is not None else None,
            # `is not None`, not truthiness: a noise floor of exactly 0.0 is what a
            # deterministic model MEASURES, and reporting it as "not evaluable" threw
            # away the cleanest case the harness can produce.
            "credible": (measured > 2 * noise) if noise is not None else None,
            "detail": floor,
        }

    # -- reporting ---------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        return {
            "lambda_cost": self.lambda_cost,
            "tasks": len(self.tasks),
            "complete_tasks": len(self.complete_tasks),
            "paradigms": self.paradigms,
            "mean_utility": {
                p: round(self.mean_utility(p), 5) for p in self.paradigms
            },
            "mean_cost": {
                p: round(
                    float(np.mean([
                        self._by_task[t][p].cost_tokens for t in self.complete_tasks
                    ])), 1
                )
                for p in self.paradigms
            },
            "best_fixed": self.best_fixed(),
            "oracle_value": round(self.oracle_value(), 5),
            "oracle_gap": round(self.oracle_gap(), 5),
            "zero_cost_rows": self._zero_cost_rows,
            "failure_attribution": self.failure_attribution(),
            "cost_spread": self.cost_spread(),
            "gap_vs_lambda": self.gap_vs_lambda(),
            "verifiable_tasks": sum(
                1 for t in self.complete_tasks
                if self._by_task[t][self.paradigms[0]].has_oracle
            ),
        }
