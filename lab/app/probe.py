"""The reconnaissance slice: one cheap read that turns an opinion into an observation.

WHY THIS EXISTS. `router.plan()` has always been able to say `needs_probe`, and the rule
`probe_before_deciding_on_bulk` has always been able to demand it, and nothing ever ran
one. That was survivable while every floor admitted ELICITED evidence. It stopped being
survivable when the assurance floor learned to raise itself (§6.2): a rule that demands
OBSERVED provenance in a region where nothing can ever produce OBSERVED provenance is not
strict, it is unsatisfiable, and the request falls to the fallback for a reason that has
nothing to do with the request.

WHAT IT MEASURES. Coupling: whether answering needs a value that is not in the unit you
are holding. One unit is read — locally, for free — and the model is asked, as a SENSOR,
to emit two typed facts about it: does the question need something this unit does not
contain, and does the unit NAME where that something lives.

WHY THE ANSWER CAN BE OBSERVED. Because the code checks it. A named dependency is
verified against the unit ids actually in scope: if the model says "this points at
memo-014" and memo-014 is in scope, the pointer is real and the coupling is measured, not
asserted. That check is what separates this from asking the model for a number and
believing it.

WHY A NEGATIVE STAYS ELICITED. The asymmetry is not an oversight. From one unit, code can
confirm that a dependency EXISTS -- the pointer resolves -- but it cannot confirm that no
dependency exists anywhere in the other forty-seven units it did not read. "I saw the
link" is an observation; "I saw no link" is one unit's worth of silence. Recording the
second as OBSERVED would be the layer lying to itself in exactly the direction that
costs the most: it would let a coupled task be routed as if it were independent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .beliefs import Provenance

# The threshold `rules.sense` uses to call coupling tight is 0.66. A verified pointer is
# evidence of tightness, and one that the model named but could not be resolved is not
# evidence of anything -- it is the sensor being wrong, which is the case this layer was
# built to survive.
COUPLED = 0.85
UNCOUPLED = 0.15

PROBE_PROMPT = """You are a sensor, not a decision maker. Report what you observe.

Question: {question}

You are holding ONE unit of the material. There are {n_units} units in total; you cannot
see the others.

Unit {unit_id}:
{unit_text}

Answer with JSON only, no prose:
{{"self_contained": true|false,
  "references": ["exact identifiers this unit names that live in OTHER units, verbatim"]}}

`self_contained` is true when this unit alone contains what the question asks for.
`references` lists identifiers written IN THIS UNIT that point elsewhere -- an account
number, a memo id, a person named as the holder of something described elsewhere. Copy
them exactly as they appear. Empty list if there are none."""


@dataclass(frozen=True)
class ProbeResult:
    """What the probe measured, and how much it is worth believing."""

    coupling: float
    provenance: Provenance
    credence: float
    evidence: str
    unit_id: str
    resolved: list[str]
    claimed: list[str]
    cost_tokens: int = 0
    calls: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "coupling": round(self.coupling, 3),
            "provenance": self.provenance.value,
            "credence": round(self.credence, 3),
            "evidence": self.evidence,
            "unit_id": self.unit_id,
            "resolved_references": self.resolved,
            "claimed_references": self.claimed,
            "cost_tokens": self.cost_tokens,
            "calls": self.calls,
        }


def _extract_json(raw: str) -> dict[str, Any]:
    """The sensor's payload, or an empty reading.

    A sensor that returns something unparseable has not reported; it has failed. That is
    a reading of nothing, not a reading of zero.
    """
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
    except ValueError:
        return {}
    try:
        payload = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve(references: list[str], scope: list[str], unit_text: str) -> list[str]:
    """Which of the named references actually point at another unit in scope.

    Two ways to resolve, both by code:
      - the reference IS a unit id in scope, and not the unit we are holding;
      - the reference is a literal string that appears in this unit and names an id.
    A reference that resolves to nothing is dropped: the model may have invented it, and
    an invented pointer must not raise a provenance.
    """
    in_scope = set(scope)
    resolved = []
    for reference in references:
        if not isinstance(reference, str):
            continue
        candidate = reference.strip()
        if not candidate:
            continue
        if candidate in in_scope and candidate in unit_text:
            resolved.append(candidate)
        elif candidate in in_scope:
            resolved.append(candidate)
    return sorted(set(resolved))


def probe_coupling(
    client: Any,
    surface: Any,
    task: dict[str, Any],
    unit_id: str | None = None,
) -> ProbeResult:
    """Read one unit, ask the sensor, verify the answer against the scope.

    The unit is chosen deterministically (the first in the task's own order) so that two
    runs of the same task probe the same unit: a probe that sampled would make the
    decision it feeds unreproducible, which is the one thing this layer promises.
    """
    scope = list(surface.unit_ids())
    if not scope:
        return ProbeResult(
            coupling=UNCOUPLED,
            provenance=Provenance.ASSUMED,
            credence=0.0,
            evidence="nothing in scope to probe",
            unit_id="",
            resolved=[],
            claimed=[],
        )

    target = unit_id or scope[0]
    unit_text = surface.read_one(target)

    completion = client.complete(
        messages=[
            {
                "role": "user",
                "content": PROBE_PROMPT.format(
                    question=task["question"],
                    n_units=len(scope),
                    unit_id=target,
                    unit_text=unit_text,
                ),
            }
        ]
    )
    payload = _extract_json(completion.text)
    usage = completion.usage

    if not payload:
        return ProbeResult(
            coupling=UNCOUPLED,
            provenance=Provenance.ASSUMED,
            credence=0.0,
            evidence="the sensor returned nothing parseable: no reading",
            unit_id=target,
            resolved=[],
            claimed=[],
            cost_tokens=usage.total_tokens,
            calls=usage.calls,
        )

    claimed = payload.get("references") or []
    claimed = [r for r in claimed if isinstance(r, str)]
    resolved = _resolve(claimed, scope, unit_text)

    if resolved:
        # Verified by code against the scope: the unit names something that is really
        # somewhere else. This is the only branch that earns OBSERVED.
        return ProbeResult(
            coupling=COUPLED,
            provenance=Provenance.OBSERVED,
            credence=1.0,
            evidence=(
                f"unit {target} names {len(resolved)} identifier(s) that resolve to "
                f"other units in scope ({', '.join(resolved[:3])}): the dependency was "
                "verified, not asserted"
            ),
            unit_id=target,
            resolved=resolved,
            claimed=claimed,
            cost_tokens=usage.total_tokens,
            calls=usage.calls,
        )

    self_contained = bool(payload.get("self_contained"))
    if claimed and not resolved:
        # The sensor named pointers and none of them exist. That is not evidence of
        # coupling and it is not evidence of independence either -- it is a sensor
        # reading that failed verification, and it is recorded as such.
        return ProbeResult(
            coupling=UNCOUPLED,
            provenance=Provenance.ELICITED,
            credence=0.2,
            evidence=(
                f"unit {target}: the sensor named {len(claimed)} reference(s), none of "
                "which resolve to a unit in scope — the reading did not verify"
            ),
            unit_id=target,
            resolved=[],
            claimed=claimed,
            cost_tokens=usage.total_tokens,
            calls=usage.calls,
        )

    return ProbeResult(
        coupling=UNCOUPLED if self_contained else COUPLED,
        provenance=Provenance.ELICITED,
        credence=0.6,
        evidence=(
            f"unit {target} was reported {'self-contained' if self_contained else 'incomplete'} "
            "and named no resolvable pointer: one unit of silence is not a measurement "
            "of the other units, so this stays elicited"
        ),
        unit_id=target,
        resolved=[],
        claimed=claimed,
        cost_tokens=usage.total_tokens,
        calls=usage.calls,
    )
