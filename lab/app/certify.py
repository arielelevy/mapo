"""REC F4: the offline clause loop and the certificate — how a draft earns the right to run.

THE GATE THIS CLOSES. F3 can already say, for any recorded decision, which minimal belief
change would have altered the plan. What nothing could do yet is turn that diagnosis into
an ACQUISITION POLICY without opening the exact door the project exists to keep shut: a
system that installs its own repairs because they looked good on the data that suggested
them. This module is the single path from draft to promoted clause, and it is fail-closed
at every joint:

  - the loop proposes on one world, validates on a second, certifies on a THIRD that
    neither proposing nor choosing ever touched (PATRON_REC §6.7);
  - the three worlds are named by immutable manifests, and overlap is checked by task
    identity, not by trust;
  - the final world is SINGLE USE: a ledger refuses the second claim against the same
    manifest, so a failed certification cannot be retried against the same held-out data
    until new data exists (CIERRE Fase 4.5);
  - what installs is a clause WITH its certificate digest, onto the signed bundle — and
    the bundle is the only place production reads clauses from.

WHAT THE GUARD MEASURES. Benefit, against the noise floor, on tasks that exhibit the
deficit: the utility of the paradigm the repaired decision would pick, minus the utility
of what the unrepaired decision runs. The criterion is preregistered in the certificate
text itself, so the artifact records what it had to beat before it saw the numbers.

WHAT THIS DOES NOT CLAIM. The "signature" here is a SHA-256 digest: it detects
alteration, it does not authenticate an issuer (ARQUITECTURA §11 keeps calling it a
digest on purpose). And no date enters any semantic digest — data and rules do
(PATRON_REC §7).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .beliefs import BeliefBase, Provenance
from .fsio import write_atomic
from .rec import AcquisitionClause, Deficit, SCHEMA, diagnose
from .rules import BeliefPolicy, sense

# ---------------------------------------------------------------------------------
# World manifests: the data a step ran on, as an immutable identity
# ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class WorldManifest:
    """One split of one corpus, frozen: which tasks, and a digest over their content.

    The digest covers task ids AND the per-task utility table the step consumed, so a
    manifest cannot silently mean different data on two runs. Overlap between manifests
    is checked on task identity — two steps that share a task share information, and no
    argument about 'different columns' changes that.
    """

    corpus: str
    role: str  # "propose" | "validate" | "final"
    task_ids: tuple[str, ...]
    content_digest: str

    @classmethod
    def build(
        cls, corpus: str, role: str, utilities: dict[str, dict[str, float]]
    ) -> "WorldManifest":
        blob = json.dumps(
            {t: dict(sorted(utilities[t].items())) for t in sorted(utilities)},
            sort_keys=True,
            ensure_ascii=False,
        )
        return cls(
            corpus=corpus,
            role=role,
            task_ids=tuple(sorted(utilities)),
            content_digest=hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        )

    def overlaps(self, other: "WorldManifest") -> set[str]:
        return set(self.task_ids) & set(other.task_ids)

    def as_dict(self) -> dict[str, Any]:
        return {
            "corpus": self.corpus,
            "role": self.role,
            "tasks": len(self.task_ids),
            "task_ids": list(self.task_ids),
            "content_digest": self.content_digest,
        }


# ---------------------------------------------------------------------------------
# The final-world ledger: held-out data is spent, not borrowed
# ---------------------------------------------------------------------------------


class FinalLedger:
    """Refuses the second certification attempt against the same final manifest.

    A final world that can be consulted twice is a validation world with better
    branding: the first look already conditioned what gets proposed next. The ledger
    makes the spend explicit and durable — appending is the only operation, and a
    digest already present means the answer is no, whoever is asking and why.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._spent: dict[str, str] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                self._spent[record["final_digest"]] = record["claim_id"]

    def claim(self, manifest: WorldManifest, claim_id: str) -> None:
        if manifest.content_digest in self._spent:
            raise PermissionError(
                f"Final world {manifest.corpus}/{manifest.content_digest[:12]} was "
                f"already spent by claim {self._spent[manifest.content_digest]!r}. "
                "A held-out set answers once; generate a new world."
            )
        record = {"final_digest": manifest.content_digest, "claim_id": claim_id,
                  "corpus": manifest.corpus, "tasks": len(manifest.task_ids)}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._spent[manifest.content_digest] = claim_id


# ---------------------------------------------------------------------------------
# The certificate
# ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Certificate:
    """The verifiable manifest that authorises one clause (PATRON_REC §7).

    Everything a skeptic needs to re-derive the decision to promote: what was
    incumbent, what was proposed, on which frozen data each step ran, what the
    preregistered criterion demanded, and what the numbers were. The semantic digest
    covers data and rules and NEVER a date.
    """

    claim_id: str
    incumbent_digest: str
    clause_digest: str
    schema_digest: str
    model_fingerprint: str
    manifests: tuple[dict[str, Any], ...]
    criterion: str
    noise_floor: float
    propose_benefit: float
    validate_benefit: float
    final_benefit: float
    deficit_tasks: dict[str, int]
    accepted: bool
    authorizer: str

    def as_dict(self) -> dict[str, Any]:
        body = {
            "claim_id": self.claim_id,
            "incumbent_digest": self.incumbent_digest,
            "clause_digest": self.clause_digest,
            "schema_digest": self.schema_digest,
            "model_fingerprint": self.model_fingerprint,
            "manifests": list(self.manifests),
            "criterion": self.criterion,
            "noise_floor": round(self.noise_floor, 5),
            "propose_benefit": round(self.propose_benefit, 5),
            "validate_benefit": round(self.validate_benefit, 5),
            "final_benefit": round(self.final_benefit, 5),
            "deficit_tasks": dict(self.deficit_tasks),
            "accepted": self.accepted,
            "authorizer": self.authorizer,
        }
        body["certificate_digest"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return body

    @property
    def digest(self) -> str:
        return str(self.as_dict()["certificate_digest"])


def schema_digest() -> str:
    """Identity of the intervention vocabulary the diagnosis ran under."""
    blob = json.dumps(
        [
            {
                "proposition": e.proposition,
                "alternatives": [str(a) for a in e.alternatives],
                "reachable": e.reachable.value,
            }
            for e in SCHEMA
        ],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------
# The offline loop (PATRON_REC §6)
# ---------------------------------------------------------------------------------


@dataclass
class World:
    """Everything the loop may know about one corpus: recorded means, per task."""

    corpus: str
    tasks: dict[str, dict[str, Any]]  # task_id -> task payload
    regions: dict[str, str]  # task_id -> region label
    utilities: dict[str, dict[str, float]]  # task_id -> paradigm -> mean utility


def _rebuild_base(
    task: dict[str, Any],
    policy: BeliefPolicy,
    theta_best: str | None,
    theta_margin: float,
) -> BeliefBase:
    """The base the router would have sensed for this task: deterministic replay."""
    return sense(
        task, policy, theta_best=theta_best, theta_confidence=theta_margin
    )


def _benefit_on(
    world: World,
    deficits: dict[str, Deficit],
    fallback: str,
) -> tuple[float, int]:
    """Mean benefit of repairing, over the tasks of this world that show the deficit.

    Benefit per task: the recorded utility of the paradigm the REPAIRED decision picks,
    minus the recorded utility of what the unrepaired decision runs (the fallback — a
    probe placeholder never executes as itself). Recorded means only: this loop never
    runs anything, it re-reads what the bench already paid for.
    """
    gains = []
    for task_id, deficit in deficits.items():
        after = deficit.label_after.paradigm
        row = world.utilities.get(task_id, {})
        if after not in row or fallback not in row:
            continue  # unmeasured on this world: no invented numbers
        gains.append(row[after] - row[fallback])
    if not gains:
        return 0.0, 0
    return sum(gains) / len(gains), len(gains)


def _diagnose_world(
    world: World,
    policy: BeliefPolicy,
    theta_assert,
    fallback: str,
    target_proposition: str,
) -> dict[str, Deficit]:
    """The tasks of one world whose decision the target proposition would flip."""
    found: dict[str, Deficit] = {}
    for task_id, task in world.tasks.items():
        best, margin = theta_assert(world.regions[task_id], sorted(world.utilities[task_id]))
        base = _rebuild_base(task, policy, best, margin)
        diagnosis = diagnose(base.as_dict()["beliefs"], policy, fallback)
        minimal = diagnosis.minimal
        if minimal is None:
            continue
        if any(
            iv.proposition == target_proposition for iv in minimal.interventions
        ):
            found[task_id] = minimal
    return found


CRITERION = (
    "mean recorded benefit of the repaired choice over the fallback exceeds the "
    "noise floor on the VALIDATE world and on the FINAL world independently, with "
    "at least {min_tasks} deficit tasks in each; the final world is consulted once"
)


def certify_clause(
    draft: AcquisitionClause,
    incumbent_digest: str,
    worlds: tuple[World, World, World],
    policy: BeliefPolicy,
    theta_assert,
    fallback: str,
    noise_floor: float,
    ledger: FinalLedger,
    model_fingerprint: str,
    authorizer: str,
    claim_id: str,
    min_tasks: int = 2,
) -> tuple[AcquisitionClause | None, Certificate]:
    """The single path from draft to promoted clause. Everything else is a draft forever.

    Order is the loop's own: propose-world benefit is reported but DECIDES NOTHING (it
    is the data that suggested the clause); the validate world decides whether the
    final world is even consulted; the final world is spent through the ledger and its
    verdict is the verdict.
    """
    if draft.promoted:
        raise ValueError(
            "This clause already carries a certificate. Certification is not "
            "re-entrant: a new claim needs a new draft and a new final world."
        )
    propose, validate, final = worlds
    manifests = (
        WorldManifest.build(propose.corpus, "propose", propose.utilities),
        WorldManifest.build(validate.corpus, "validate", validate.utilities),
        WorldManifest.build(final.corpus, "final", final.utilities),
    )
    for i, a in enumerate(manifests):
        for b in manifests[i + 1:]:
            shared = a.overlaps(b)
            if shared:
                raise ValueError(
                    f"Worlds {a.role} and {b.role} share {len(shared)} task(s) "
                    f"(e.g. {sorted(shared)[:3]}). A split that leaks is not a split."
                )

    stages: dict[str, tuple[float, int]] = {}
    for world, manifest in zip(worlds, manifests):
        deficits = _diagnose_world(
            world, policy, theta_assert, fallback, draft.target_proposition
        )
        stages[manifest.role] = _benefit_on(world, deficits, fallback)

    validate_ok = (
        stages["validate"][1] >= min_tasks
        and stages["validate"][0] > noise_floor
    )

    final_benefit, final_n = 0.0, 0
    if validate_ok:
        # The final world is SPENT before it answers: a claim that fails still consumed
        # it, which is what makes failing here expensive enough to plan around.
        ledger.claim(manifests[2], claim_id)
        final_benefit, final_n = stages["final"]

    accepted = (
        validate_ok and final_n >= min_tasks and final_benefit > noise_floor
    )

    certificate = Certificate(
        claim_id=claim_id,
        incumbent_digest=incumbent_digest,
        clause_digest=draft.digest(),
        schema_digest=schema_digest(),
        model_fingerprint=model_fingerprint,
        manifests=tuple(m.as_dict() for m in manifests),
        criterion=CRITERION.format(min_tasks=min_tasks),
        noise_floor=noise_floor,
        propose_benefit=stages["propose"][0],
        validate_benefit=stages["validate"][0],
        final_benefit=final_benefit,
        deficit_tasks={
            "propose": stages["propose"][1],
            "validate": stages["validate"][1],
            "final": final_n,
        },
        accepted=accepted,
        authorizer=authorizer,
    )

    if not accepted:
        return None, certificate

    promoted = AcquisitionClause.from_dict(
        {**draft.as_dict(), "certificate": certificate.digest}
    )
    return promoted, certificate


# ---------------------------------------------------------------------------------
# Installation: the bundle is the only place production reads clauses from
# ---------------------------------------------------------------------------------


def install_clause(bundle, clause: AcquisitionClause, certificate: Certificate):
    """Attach a PROMOTED clause to a policy bundle and re-sign it.

    Fail-closed three ways: a draft is refused; a certificate that does not name this
    exact clause is refused; a certificate that was not accepted is refused. The clause
    enters the SIGNED payload, so an in-place edit afterwards invalidates the bundle.
    """
    if not clause.promoted:
        raise PermissionError("Refusing to install a draft: no certificate.")
    if not certificate.accepted:
        raise PermissionError("Refusing to install: the certificate records a rejection.")
    if certificate.clause_digest != clause.digest():
        raise PermissionError(
            "Refusing to install: the certificate names a different clause."
        )
    if certificate.digest != clause.certificate:
        raise PermissionError(
            "Refusing to install: the clause does not carry this certificate."
        )
    bundle.clauses.append(clause.as_dict())
    bundle.sign()
    return bundle


def save_certificate(directory: Path, certificate: Certificate) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"certificate_{certificate.claim_id}.json"
    write_atomic(path, json.dumps(certificate.as_dict(), ensure_ascii=False, indent=2))
    return path
