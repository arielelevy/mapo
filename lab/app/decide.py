"""One decision cycle: sense, plan, probe if the plan asks for it, decide again.

WHY IT IS ITS OWN MODULE. `probe_then_decide` is a rule that names two steps, and until
now only one caller ever took the second one. `serve.answer` probed and re-planned;
`Runner.report` called `router.plan` once and scored whatever came back — so on every
task where the probe rule fired, the bench measured a PLACEHOLDER (the cheapest
admissible paradigm, chosen to be tried *after* probing) as if it were a decision. That
is not a small gap: with honest runtime detectors it is 14 of 26 tasks on the held-out
corpus.

Copying the cycle into the bench would have fixed the symptom and started the disease —
two implementations of one decision, free to drift, which is the exact failure this
project spent a day removing from the frozen execution layer. So the cycle lives here
once, and both callers take both steps.

WHAT DECIDING COSTS IS RETURNED, NOT ABSORBED. A probe is a model call. The bench needs
that number to charge governance against the utility it buys, and the product needs it on
the bill. A cycle that hid it would make the governed path look exactly as cheap as the
blind one — which un-measures the only trade-off the whole layer exists to price.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Sequence

from .features import Features, measure_continuation
from .llm import Usage
from .probe import ProbeResult, probe_coupling
from .router import Plan, Router


@dataclass
class Decision:
    """What was decided, how it got there, and what deciding cost."""

    plan: Plan
    features: Features
    probe: ProbeResult | None = None
    plan_before_probe: Plan | None = None
    usage: Usage = field(default_factory=Usage)

    @property
    def probed(self) -> bool:
        return self.probe is not None

    @property
    def changed_by_probe(self) -> bool:
        """Whether the observation actually moved the decision.

        Recorded rather than assumed: a probe that never changes anything is a probe
        that should not be run, and that is an empirical question about a region — the
        kind §6.2's floors learn from.
        """
        if self.plan_before_probe is None:
            return False
        return (
            self.plan.action != self.plan_before_probe.action
            or self.plan.paradigm != self.plan_before_probe.paradigm
        )

    @property
    def unresolved(self) -> bool:
        """The plan still wants evidence nobody produced.

        The paradigm on such a plan is a placeholder the probe rule picked as cheapest
        to try AFTER probing. Executing it as if it were a decision means acting on
        evidence the gate just called insufficient, so every caller must treat this as
        a deferral — never as a choice.
        """
        return bool(self.plan.needs_probe)

    def as_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "action": self.plan.action,
            "paradigm": self.plan.paradigm,
            "region": self.features.region(),
            "probed": self.probed,
            "unresolved": self.unresolved,
            "deciding_usage": self.usage.as_dict(),
        }
        if self.probe is not None:
            body["probe"] = self.probe.as_dict()
            body["changed_by_probe"] = self.changed_by_probe
            if self.plan_before_probe is not None:
                body["plan_before_probe"] = {
                    "action": self.plan_before_probe.action,
                    "paradigm": self.plan_before_probe.paradigm,
                }
        return body


def decide(
    task: dict[str, Any],
    *,
    router: Router,
    features: Features,
    candidates: list[str],
    documents: dict[str, str] | None = None,
    requested: Any = None,
    client: Any = None,
    surface: Any = None,
    probe: bool = True,
    models: "Sequence[Any] | None" = None,
) -> Decision:
    """Plan; if the plan asks for a probe and one can be run, probe and plan again.

    The second plan CONTINUES the first one's belief history (`prior_beliefs`), so the
    observation supersedes the estimate on one record with one digest lineage, and the
    region is rebuilt from what was observed — replanning under the stale region would
    leave the request in the "coupling unknown" bin the probe had just left, which is
    the exact failure P15 measured.

    `probe=False`, or no client/surface to probe with, is not an error: it returns a
    plan whose `needs_probe` is still true, and `Decision.unresolved` says so. What the
    caller does with that is the caller's policy — but pretending it was a decision is
    not one of the options.
    """
    def plan_with(reading: ProbeResult | None, prior=None) -> Plan:
        kwargs: dict[str, Any] = {}
        if reading is not None:
            kwargs["coupling"] = reading.coupling
            kwargs["coupling_provenance"] = reading.provenance
            kwargs["coupling_credence"] = reading.credence
        if prior:
            kwargs["prior_beliefs"] = prior
        if requested is not None:
            kwargs["requested"] = requested
        if documents is not None:
            kwargs["documents"] = documents
        return router.plan(
            task=task,
            candidates=candidates,
            region=features.region(),
            **kwargs,
        )

    first = plan_with(None)
    can_probe = probe and client is not None and surface is not None
    if not (first.needs_probe and can_probe):
        return Decision(plan=first, features=features)

    reading = probe_coupling(client, surface, task)
    features = replace(features, coupling=reading.coupling)
    second = plan_with(
        reading,
        prior=first.verdict.get("beliefs", {}).get("beliefs", []),
    )
    return Decision(
        plan=second,
        features=features,
        probe=reading,
        plan_before_probe=first,
        usage=Usage(
            prompt_tokens=reading.cost_tokens,
            completion_tokens=0,
            calls=reading.calls,
        ),
    )
