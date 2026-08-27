"""Structural feature extraction (the vector phi).

The central design decision of this module is the split between COMPUTABLE and
DERIVED features.

- COMPUTABLE features are pure functions of the task payload. Same task, same value,
  forever, with no model in the loop.
- DERIVED features need a language model to estimate. They are useful but they are
  *not* replayable from first principles, only from cache.

That split is what makes regulated operation possible. In deterministic mode D2 the
router may read COMPUTABLE features only; a policy rule that needs a DERIVED feature
cannot fire, so confidence is capped and the router abstains to the fallback paradigm.

Determinism and abstention therefore stop being two separate requirements and become
one mechanism: whatever cannot be established deterministically is routed to the safe
default rather than guessed at.

Deliberately NOT here: lexical triggers. Conditioning on surface forms like
"how many" or "extract all" is what produced the false-positive rate that made the
prose-prompt routers lose. Cardinality is counted, never inferred from phrasing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any

from .llm import LLMClient, Usage


class Availability(str, Enum):
    COMPUTABLE = "computable"
    DERIVED = "derived"


FEATURE_AVAILABILITY: dict[str, Availability] = {
    "n_units": Availability.COMPUTABLE,
    "has_oracle": Availability.COMPUTABLE,
    "irreversible": Availability.COMPUTABLE,
    "shared_writes": Availability.COMPUTABLE,
    "budget_tokens": Availability.COMPUTABLE,
    "coupling": Availability.DERIVED,
    "horizon_unknown": Availability.DERIVED,
}

COMPUTABLE_FEATURES = tuple(
    name for name, a in FEATURE_AVAILABILITY.items() if a is Availability.COMPUTABLE
)
DERIVED_FEATURES = tuple(
    name for name, a in FEATURE_AVAILABILITY.items() if a is Availability.DERIVED
)


@dataclass(frozen=True)
class Features:
    """The phi vector.

    A DERIVED field set to None means "not established". Consumers must treat None as
    absence of knowledge, never as a zero.
    """

    # -- computable --------------------------------------------------------
    n_units: int
    has_oracle: bool
    irreversible: bool
    shared_writes: bool
    budget_tokens: int

    # -- derived -----------------------------------------------------------
    coupling: float | None = None
    horizon_unknown: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def computable_only(self) -> "Features":
        """Projection onto the deterministic subspace (mode D2)."""
        return Features(
            n_units=self.n_units,
            has_oracle=self.has_oracle,
            irreversible=self.irreversible,
            shared_writes=self.shared_writes,
            budget_tokens=self.budget_tokens,
            coupling=None,
            horizon_unknown=None,
        )

    def missing(self) -> tuple[str, ...]:
        return tuple(
            name for name in DERIVED_FEATURES if getattr(self, name) is None
        )

    def region(self) -> str:
        """Discrete feature region, used as the key for learned statistics.

        Learning per exact feature vector would never accumulate enough episodes to
        estimate anything. Binning trades resolution for sample size, and it also
        keeps the learned policy small enough to read by eye.
        """
        if self.n_units <= 1:
            card = "single"
        elif self.n_units <= 8:
            card = "few"
        elif self.n_units <= 64:
            card = "many"
        else:
            card = "bulk"

        oracle = "oracle" if self.has_oracle else "no_oracle"

        if self.coupling is None:
            coup = "unknown"
        elif self.coupling < 0.33:
            coup = "loose"
        elif self.coupling < 0.66:
            coup = "mixed"
        else:
            coup = "tight"

        return f"{card}/{oracle}/{coup}"


COUPLING_PROMPT = """You estimate two structural properties of a task. Answer with JSON only.

Task:
{task}

Number of independent input units already counted: {n_units}

Return exactly:
{{"coupling": <float 0..1>, "horizon_unknown": <true|false>}}

coupling = degree to which the sub-results depend on each other.
  0.0 = every unit can be processed alone and results merely concatenated
  1.0 = each step needs the previous step's output (chained / multi-hop)
horizon_unknown = true if the number of steps required cannot be known in advance.

No prose. No markdown fences. JSON only."""


class FeatureExtractor:
    """Builds phi from a task record.

    The COMPUTABLE part reads declared task structure. It does not attempt to parse
    intent out of the prompt text, by design.
    """

    def __init__(self, client: LLMClient | None = None) -> None:
        # None is legitimate and means "computable features only". It is not a
        # degraded mode; it is the deterministic mode.
        self._client = client

    def extract(self, task: dict[str, Any], allow_derived: bool) -> tuple[Features, Usage]:
        usage = Usage()

        units = task.get("units") or []
        base = Features(
            n_units=len(units) if units else 1,
            has_oracle=bool(task.get("oracle")),
            irreversible=bool(task.get("irreversible", False)),
            shared_writes=bool(task.get("shared_writes", False)),
            budget_tokens=int(task["budget_tokens"]),
        )

        if not allow_derived or self._client is None:
            return base, usage

        derived, derived_usage = self._derive(task, base.n_units)
        usage.merge(derived_usage)
        if derived is None:
            # Estimation failed. Leaving the fields as None is the honest outcome:
            # it will cap confidence downstream and push the router to abstain.
            return base, usage

        return (
            Features(
                n_units=base.n_units,
                has_oracle=base.has_oracle,
                irreversible=base.irreversible,
                shared_writes=base.shared_writes,
                budget_tokens=base.budget_tokens,
                coupling=derived["coupling"],
                horizon_unknown=derived["horizon_unknown"],
            ),
            usage,
        )

    def _derive(
        self, task: dict[str, Any], n_units: int
    ) -> tuple[dict[str, Any] | None, Usage]:
        prompt = COUPLING_PROMPT.format(task=task["question"], n_units=n_units)
        completion = self._client.complete(
            messages=[{"role": "user", "content": prompt}], max_tokens=200
        )
        try:
            parsed = json.loads(completion.text.strip())
            coupling = float(parsed["coupling"])
            if not 0.0 <= coupling <= 1.0:
                return None, completion.usage
            return (
                {
                    "coupling": coupling,
                    "horizon_unknown": bool(parsed["horizon_unknown"]),
                },
                completion.usage,
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None, completion.usage
