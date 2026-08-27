"""The learned policy bundle (theta), its plasticity, and the determinism ladder.

Three ideas live here, and they are the contribution of the lab.

1. PLASTICITY. Statistics about how each paradigm performs in each feature region are
   updated from outcomes with the Hebbian rule of MAP:

       W <- (1 - lambda) * W + eta * delta

   That is Definition 11.2 of the v1 whitepaper, applied to (region, paradigm) pairs
   instead of (agent, agent) edges. The weights stay bounded and interpretable, which
   is precisely why this substrate was chosen over an embedding: a number in [0,1]
   attached to a named region can be read, audited, argued with and edited by hand.
   An embedding cannot.

2. SELF-OPTIMISATION WITHOUT DRIFT. Learning never happens inside a request. A run
   accumulates episodes; an offline promotion step builds a candidate bundle and
   installs it only if it does not regress against the incumbent on held-out
   episodes. This is Oracle's SQL Plan Management discipline, and it is what keeps
   "self-improving" from meaning "silently different tomorrow".

3. ASSURANCE IS NOT HERE ANY MORE. This module used to define a system-wide
   determinism ladder (D0-D3). That was the wrong shape: it made every request pay for
   the strictest one. Assurance is now a property OF THE REQUEST and lives in
   `assurance.py`; provenance and the belief substrate live in `beliefs.py`. What
   remains here is theta itself and how it learns.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Hebbian hyperparameters. Kept at the v1 whitepaper's recommended values so the
# lab and the paper cannot silently disagree: eta = 0.1 sits inside the stability
# bound of Corollary 11.1 with margin.
LEARNING_RATE = 0.1
DECAY = 0.05
WEIGHT_MIN = 0.01
WEIGHT_MAX = 1.0
PRIOR_WEIGHT = 0.5

# A region needs this many episodes before its statistics are allowed to drive a
# specialised route. Below it, confidence is capped and the router abstains.
MIN_EPISODES_FOR_CONFIDENCE = 8



@dataclass
class Stat:
    """Learned statistics for one (region, paradigm) pair."""

    weight: float = PRIOR_WEIGHT
    episodes: int = 0
    utility_sum: float = 0.0
    cost_sum: float = 0.0
    wins: int = 0

    @property
    def mean_utility(self) -> float:
        return self.utility_sum / self.episodes if self.episodes else 0.0

    @property
    def mean_cost(self) -> float:
        return self.cost_sum / self.episodes if self.episodes else 0.0

    @property
    def win_rate(self) -> float:
        return self.wins / self.episodes if self.episodes else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "weight": round(self.weight, 5),
            "episodes": self.episodes,
            "mean_utility": round(self.mean_utility, 5),
            "mean_cost": round(self.mean_cost, 2),
            "win_rate": round(self.win_rate, 5),
            "utility_sum": self.utility_sum,
            "cost_sum": self.cost_sum,
            "wins": self.wins,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Stat":
        return cls(
            weight=float(raw["weight"]),
            episodes=int(raw["episodes"]),
            utility_sum=float(raw["utility_sum"]),
            cost_sum=float(raw["cost_sum"]),
            wins=int(raw["wins"]),
        )


@dataclass
class Episode:
    """One observed execution. The unit of learning and of audit."""

    task_id: str
    region: str
    paradigm: str
    utility: float
    cost_tokens: int
    was_best: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "region": self.region,
            "paradigm": self.paradigm,
            "utility": self.utility,
            "cost_tokens": self.cost_tokens,
            "was_best": self.was_best,
        }


@dataclass
class PolicyBundle:
    """theta: an immutable, versioned, signed, human-readable policy.

    Immutability is enforced by convention plus the signature: any in-place edit
    invalidates `signature`, and `verify()` will say so.
    """

    version: int
    created_at: str
    fallback: str
    tau: float
    stats: dict[str, dict[str, Stat]] = field(default_factory=dict)
    signature: str = ""
    notes: str = ""

    # -- access ------------------------------------------------------------

    def stat(self, region: str, paradigm: str) -> Stat:
        return self.stats.get(region, {}).get(paradigm, Stat())

    def paradigms_for(self, region: str) -> dict[str, Stat]:
        return self.stats.get(region, {})

    def regions(self) -> Iterable[str]:
        return self.stats.keys()

    # -- signature ---------------------------------------------------------

    def _payload(self) -> str:
        body = {
            "version": self.version,
            "created_at": self.created_at,
            "fallback": self.fallback,
            "tau": self.tau,
            "stats": {
                region: {p: s.as_dict() for p, s in sorted(paradigms.items())}
                for region, paradigms in sorted(self.stats.items())
            },
        }
        return json.dumps(body, sort_keys=True, ensure_ascii=False)

    def sign(self) -> "PolicyBundle":
        self.signature = hashlib.sha256(self._payload().encode("utf-8")).hexdigest()
        return self

    def verify(self) -> bool:
        expected = hashlib.sha256(self._payload().encode("utf-8")).hexdigest()
        return bool(self.signature) and expected == self.signature

    # -- persistence -------------------------------------------------------

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "fallback": self.fallback,
            "tau": self.tau,
            "signature": self.signature,
            "notes": self.notes,
            "stats": {
                region: {p: s.as_dict() for p, s in sorted(paradigms.items())}
                for region, paradigms in sorted(self.stats.items())
            },
        }

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"theta_v{self.version:04d}.json"
        path.write_text(
            json.dumps(self.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    @classmethod
    def load(cls, path: Path) -> "PolicyBundle":
        raw = json.loads(path.read_text(encoding="utf-8"))
        bundle = cls(
            version=int(raw["version"]),
            created_at=raw["created_at"],
            fallback=raw["fallback"],
            tau=float(raw["tau"]),
            stats={
                region: {p: Stat.from_dict(s) for p, s in paradigms.items()}
                for region, paradigms in raw["stats"].items()
            },
            signature=raw.get("signature", ""),
            notes=raw.get("notes", ""),
        )
        if not bundle.verify():
            raise ValueError(
                f"Policy bundle at {path} fails signature verification. "
                "It was edited after signing; refusing to load it silently."
            )
        return bundle

    @classmethod
    def cold_start(cls, fallback: str, tau: float) -> "PolicyBundle":
        """Version 0: no statistics at all.

        A cold bundle routes everything to the fallback, because every region has
        zero episodes and therefore zero confidence. That is the correct behaviour
        for a system that has not learned anything yet, and it means the system is
        never worse than its fallback on day one.
        """
        return cls(
            version=0,
            created_at=datetime.now(timezone.utc).isoformat(),
            fallback=fallback,
            tau=tau,
            stats={},
            notes="cold start: no episodes, abstains everywhere",
        ).sign()

    # -- readability -------------------------------------------------------

    def explain_text(self) -> str:
        """Render theta as something a human (or an auditor) can read."""
        lines = [
            f"theta version {self.version}  signed {self.signature[:16]}",
            f"fallback = {self.fallback}   tau = {self.tau}",
            "",
        ]
        for region in sorted(self.stats):
            lines.append(f"region {region}")
            ranked = sorted(
                self.stats[region].items(),
                key=lambda kv: kv[1].mean_utility,
                reverse=True,
            )
            for paradigm, stat in ranked:
                confident = stat.episodes >= MIN_EPISODES_FOR_CONFIDENCE
                flag = "" if confident else "  (below episode floor -> abstain)"
                lines.append(
                    f"    {paradigm:<14} u={stat.mean_utility:6.3f} "
                    f"w={stat.weight:5.3f} n={stat.episodes:<4d} "
                    f"cost={stat.mean_cost:8.1f}{flag}"
                )
            lines.append("")
        return "\n".join(lines)


class Plasticity:
    """Applies the Hebbian update and builds promoted bundles."""

    @staticmethod
    def delta(episode: Episode) -> float:
        """Reinforcement signal.

        Positive when the paradigm was the best available choice for the task,
        negative otherwise. Being merely adequate is not reinforced: the quantity
        the router needs to estimate is "is this the right paradigm here", not
        "did this paradigm produce something".
        """
        return 0.5 if episode.was_best else -0.3

    @classmethod
    def apply(cls, stats: dict[str, dict[str, Stat]], episode: Episode) -> None:
        region = stats.setdefault(episode.region, {})
        stat = region.setdefault(episode.paradigm, Stat())

        updated = (1.0 - DECAY) * stat.weight + LEARNING_RATE * cls.delta(episode)
        stat.weight = max(WEIGHT_MIN, min(WEIGHT_MAX, updated))
        stat.episodes += 1
        stat.utility_sum += episode.utility
        stat.cost_sum += episode.cost_tokens
        stat.wins += 1 if episode.was_best else 0

    @classmethod
    def candidate(
        cls,
        incumbent: PolicyBundle,
        episodes: list[Episode],
        tau: float,
        notes: str = "",
    ) -> PolicyBundle:
        """Build the next bundle by replaying episodes onto a copy of the incumbent."""
        stats = {
            region: {p: Stat.from_dict(s.as_dict()) for p, s in paradigms.items()}
            for region, paradigms in incumbent.stats.items()
        }
        for episode in episodes:
            cls.apply(stats, episode)

        return PolicyBundle(
            version=incumbent.version + 1,
            created_at=datetime.now(timezone.utc).isoformat(),
            fallback=incumbent.fallback,
            tau=tau,
            stats=stats,
            notes=notes or f"promoted from v{incumbent.version} on {len(episodes)} episodes",
        ).sign()


@dataclass
class PromotionVerdict:
    accepted: bool
    incumbent_value: float
    candidate_value: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "incumbent_value": round(self.incumbent_value, 5),
            "candidate_value": round(self.candidate_value, 5),
            "delta": round(self.candidate_value - self.incumbent_value, 5),
            "reason": self.reason,
        }


def promote(
    incumbent: PolicyBundle,
    candidate: PolicyBundle,
    holdout: list[Episode],
    router_value_fn,
    min_gain: float = 0.0,
) -> PromotionVerdict:
    """Install `candidate` only if it does not regress on held-out episodes.

    `router_value_fn(bundle, holdout) -> float` is injected rather than imported so
    the promotion rule cannot quietly depend on the routing implementation. The
    guard is the reason "self-optimising" is safe to say here: a bundle that would
    make things worse never reaches production, and the verdict is recorded.
    """
    if not holdout:
        return PromotionVerdict(
            accepted=False,
            incumbent_value=0.0,
            candidate_value=0.0,
            reason="no holdout episodes: refusing to promote unverified policy",
        )

    incumbent_value = router_value_fn(incumbent, holdout)
    candidate_value = router_value_fn(candidate, holdout)

    if candidate_value >= incumbent_value + min_gain:
        return PromotionVerdict(
            accepted=True,
            incumbent_value=incumbent_value,
            candidate_value=candidate_value,
            reason=f"candidate v{candidate.version} does not regress on holdout",
        )

    return PromotionVerdict(
        accepted=False,
        incumbent_value=incumbent_value,
        candidate_value=candidate_value,
        reason=(
            f"candidate v{candidate.version} regresses by "
            f"{incumbent_value - candidate_value:.5f}; keeping v{incumbent.version}"
        ),
    )
