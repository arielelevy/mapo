"""The one place that owns persisted learning state.

Before this module the persistence was partial in a way that quietly disabled the
learning loop: theta was written only by the HTTP layer, belief bases were never written
at all despite two assurance profiles declaring `log_belief_base: True`, calibration
existed only inside a function call, and dream reports were computed and dropped.

The consequence was not a missing feature but a dead loop. With no belief log there is
no calibration; with no calibration `trust_elicited` can never become true; so A2 would
demand OBSERVED provenance for ever and the probe would fire on every request,
regardless of how well the model was actually calibrated. And the abstraction stage of
the sleep cycle would discover propositions and discard them, which is theatre.

Layout, all under the results directory:

    <corpus>_rows.jsonl          execution record (owned by Runner)
    <corpus>_report.json         metrics report (owned by Runner)
    policies/theta_vNNNN.json    theta, versioned and signed
    beliefs/<corpus>.jsonl       belief bases, append-only
    calibration/<corpus>.json    per-proposition reliability
    dreams/<corpus>_cNNN.json    one file per consolidation cycle
    propositions/<corpus>.json   propositions discovered and their evidence so far

Append-only wherever the record is evidence. A belief base that could be rewritten is
not an audit trail, and a calibration figure recomputed from a mutable log cannot be
checked by anyone.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .beliefs import Calibration, Provenance, score_calibration
from .fsio import write_atomic

# One writer at a time for the append+head pair. Two concurrent appends that read
# the same head produce two records with the same `prev` — a forked chain that
# `verify_chain` reports as tampering forever after. Process-local by design: the
# FastAPI endpoints run sync-in-threadpool within one process.
_BELIEF_LOG_LOCK = threading.Lock()


@dataclass
class DiscoveredProposition:
    """A proposition the abstraction stage proposed, and its accumulating evidence.

    It is stored precisely so it can fail to earn promotion. A proposition enters with
    zero episodes and stays inert — below the confidence floor, invisible to the router
    — until enough evidence accumulates. Persisting it is what lets that accumulation
    span cycles instead of restarting every time.
    """

    proposition: str
    attribute: str
    threshold: float
    first_seen_cycle: int
    times_proposed: int = 0
    separation_history: list[float] = field(default_factory=list)
    episodes: int = 0
    promoted: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "proposition": self.proposition,
            "attribute": self.attribute,
            "threshold": self.threshold,
            "first_seen_cycle": self.first_seen_cycle,
            "times_proposed": self.times_proposed,
            "separation_history": [round(x, 5) for x in self.separation_history],
            "mean_separation": (
                round(sum(self.separation_history) / len(self.separation_history), 5)
                if self.separation_history else None
            ),
            "episodes": self.episodes,
            "promoted": self.promoted,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "DiscoveredProposition":
        return cls(
            proposition=raw["proposition"],
            attribute=raw["attribute"],
            threshold=float(raw["threshold"]),
            first_seen_cycle=int(raw["first_seen_cycle"]),
            times_proposed=int(raw.get("times_proposed", 0)),
            separation_history=[float(x) for x in raw.get("separation_history", [])],
            episodes=int(raw.get("episodes", 0)),
            promoted=bool(raw.get("promoted", False)),
        )


class LearningStore:
    """Owns every piece of persisted learning state for one corpus."""

    def __init__(self, results_dir: Path, corpus: str) -> None:
        self._root = results_dir
        self._corpus = corpus
        for sub in ("policies", "beliefs", "calibration", "dreams", "propositions"):
            (self._root / sub).mkdir(parents=True, exist_ok=True)

    # -- paths -------------------------------------------------------------

    @property
    def policy_dir(self) -> Path:
        return self._root / "policies"

    @property
    def belief_log_path(self) -> Path:
        return self._root / "beliefs" / f"{self._corpus}.jsonl"

    @property
    def calibration_path(self) -> Path:
        return self._root / "calibration" / f"{self._corpus}.json"

    @property
    def propositions_path(self) -> Path:
        return self._root / "propositions" / f"{self._corpus}.json"

    def dream_path(self, cycle: int) -> Path:
        return self._root / "dreams" / f"{self._corpus}_c{cycle:03d}.json"

    # -- belief bases ------------------------------------------------------

    @property
    def belief_head_path(self) -> Path:
        return self._root / "beliefs" / f"{self._corpus}.head.json"

    @staticmethod
    def _link(prev_chain: str, payload: str) -> str:
        return hashlib.sha256(f"{prev_chain}|{payload}".encode("utf-8")).hexdigest()

    GENESIS = "0" * 64

    def _head(self) -> dict[str, Any]:
        if not self.belief_head_path.exists():
            return {"seq": 0, "chain": self.GENESIS}
        return json.loads(self.belief_head_path.read_text(encoding="utf-8"))

    @property
    def decision_log_path(self) -> Path:
        return self._root / f"{self._corpus}.decisions.jsonl"

    def append_decision(self, record: dict[str, Any]) -> None:
        """Dejar rastro de una decision de produccion.

        POR QUE HACE FALTA. `serve.py` decidia, ejecutaba, respondia — y no escribia
        nada. Sin esto, el EXPLAIN existe SOLO mientras dura la respuesta: un artefacto
        de explicacion que no se puede consultar despues no explica, decora.

        Append y `write_atomic` no aplican: es una linea por request y el archivo crece.
        Lo que se protege es que una linea a medio escribir no envenene la lectura, y
        eso lo da escribir la linea entera de una.
        """
        self._root.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with self.decision_log_path.open("a", encoding="utf-8") as sink:
            sink.write(line + "\n")

    def iter_decisions(self) -> "Iterator[dict[str, Any]]":
        if not self.decision_log_path.exists():
            return
        with self.decision_log_path.open(encoding="utf-8") as source:
            for line in source:
                if line.strip():
                    yield json.loads(line)

    def append_belief_base(
        self, base_dict: dict[str, Any], context: dict[str, Any] | None = None
    ) -> str:
        """Append one belief base, chained to the previous record.

        Append-only was not enough. Each record already carried its own digest, but
        nothing bound records to each other, so a whole line could be deleted from the
        log and nothing would detect it — the record was evidence of itself and of
        nothing else. Chaining each record to its predecessor makes deletion, insertion
        and reordering all detectable.

        The head is also written to a sidecar as a witness: truncating the tail of the
        log leaves the head pointing at a hash that no longer appears in it, so even
        removing the last N records is visible.
        """
        with _BELIEF_LOG_LOCK:
            head = self._head()
            record = {
                "seq": head["seq"] + 1,
                "prev": head["chain"],
                "beliefs": base_dict.get("beliefs", []),
                "digest": base_dict.get("digest"),
            }
            if context:
                record["context"] = context

            # The link covers the record without its own chain field, so the chain
            # can be recomputed from the record exactly as stored.
            payload = json.dumps(record, sort_keys=True, ensure_ascii=False)
            record["chain"] = self._link(head["chain"], payload)

            with self.belief_log_path.open("a", encoding="utf-8") as sink:
                sink.write(json.dumps(record, ensure_ascii=False) + "\n")
            write_atomic(
                self.belief_head_path,
                json.dumps({"seq": record["seq"], "chain": record["chain"]}, indent=2),
            )
            return record["chain"]

    def verify_chain(self) -> dict[str, Any]:
        """Recompute the whole chain and report the first broken link.

        Returns `intact` plus enough detail to say WHAT broke: a mismatched link means
        a record was edited, a mismatched `prev` means one was removed or reordered,
        and a head that disagrees with the recomputed tail means the log was truncated.
        """
        expected_prev = self.GENESIS
        seq = 0
        for record in self.iter_belief_log():
            seq += 1
            if record.get("prev") != expected_prev:
                return {
                    "intact": False,
                    "broken_at_seq": record.get("seq", seq),
                    "reason": "prev does not match the preceding record's chain: a "
                              "record was removed, inserted or reordered",
                }
            stored_chain = record.get("chain")
            payload_record = {k: v for k, v in record.items() if k != "chain"}
            payload = json.dumps(payload_record, sort_keys=True, ensure_ascii=False)
            if self._link(expected_prev, payload) != stored_chain:
                return {
                    "intact": False,
                    "broken_at_seq": record.get("seq", seq),
                    "reason": "recomputed link does not match: this record was edited",
                }
            expected_prev = stored_chain

        head = self._head()
        if head["chain"] != expected_prev or head["seq"] != seq:
            return {
                "intact": False,
                "broken_at_seq": seq,
                "reason": (
                    f"head witness says seq={head['seq']} chain={head['chain'][:12]} "
                    f"but the log ends at seq={seq} chain={expected_prev[:12]}: "
                    "the log was truncated"
                ),
            }

        return {"intact": True, "records": seq, "head": expected_prev}

    def belief_log(self) -> list[dict[str, Any]]:
        if not self.belief_log_path.exists():
            return []
        return [
            json.loads(line)
            for line in self.belief_log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def iter_belief_log(self) -> Iterator[dict[str, Any]]:
        """Streaming view, for a log too large to hold at once."""
        if not self.belief_log_path.exists():
            return
        with self.belief_log_path.open(encoding="utf-8") as source:
            for line in source:
                if line.strip():
                    yield json.loads(line)

    # -- calibration -------------------------------------------------------

    def rebuild_calibration(self) -> dict[str, Any]:
        """Recompute per-proposition calibration from the belief log and persist it.

        Recomputed rather than incrementally updated: the log is the source of truth,
        and an incrementally maintained figure would drift out of agreement with it
        without anything detecting the divergence.
        """
        per_prop, contradictions = score_calibration(self.iter_belief_log())

        payload = {
            "corpus": self._corpus,
            "propositions": {
                name: calibration.as_dict() for name, calibration in per_prop.items()
            },
            # Se persisten porque estaban en la otra copia y no en esta, que es como se
            # noto que habia dos. «Mal calibrado» y «equivocado» no son lo mismo.
            "contradictions": contradictions,
            # The switch a rule actually reads. False with no data is the correct
            # default: an unmeasured credence has not earned trust.
            "trust_elicited": bool(per_prop) and all(
                c.is_trustworthy() for c in per_prop.values()
            ),
        }
        write_atomic(
            self.calibration_path, json.dumps(payload, ensure_ascii=False, indent=2)
        )
        return payload

    def calibration(self) -> dict[str, Any]:
        if not self.calibration_path.exists():
            return {"propositions": {}, "trust_elicited": False}
        return json.loads(self.calibration_path.read_text(encoding="utf-8"))

    def trusts_elicited(self, proposition: str | None = None) -> bool:
        """Whether elicited credence has earned the right to drive a decision.

        Per proposition when one is named, because a model may be reliable about
        cardinality and hopeless about coupling, and a single global answer cannot say
        so. Absent data the answer is no.
        """
        data = self.calibration()
        if proposition is None:
            return bool(data.get("trust_elicited", False))
        entry = data.get("propositions", {}).get(proposition)
        return bool(entry and entry.get("trustworthy"))

    # -- discovered propositions -------------------------------------------

    def propositions(self) -> dict[str, DiscoveredProposition]:
        if not self.propositions_path.exists():
            return {}
        raw = json.loads(self.propositions_path.read_text(encoding="utf-8"))
        return {
            k: DiscoveredProposition.from_dict(v) for k, v in raw.items()
        }

    def record_discoveries(
        self, discovered: list[dict[str, Any]], cycle: int
    ) -> dict[str, Any]:
        """Merge this cycle's survivors into the persisted set.

        Re-proposal across cycles is the signal that matters. A partition found once
        may be an artefact of one split of the record; one found in three consecutive
        cycles, on different splits, is a finding. Persisting `times_proposed` is what
        makes that distinction available at all.
        """
        existing = self.propositions()
        for item in discovered:
            if not item.get("survives"):
                continue
            name = item["proposition"]
            entry = existing.get(name) or DiscoveredProposition(
                proposition=name,
                attribute=item["attribute"],
                threshold=float(item["threshold"]),
                first_seen_cycle=cycle,
            )
            entry.times_proposed += 1
            entry.separation_history.append(float(item["separation_validate"]))
            existing[name] = entry

        write_atomic(
            self.propositions_path,
            json.dumps(
                {k: v.as_dict() for k, v in sorted(existing.items())},
                ensure_ascii=False,
                indent=2,
            ),
        )
        return {
            "total_known": len(existing),
            "reproposed": [
                k for k, v in existing.items() if v.times_proposed > 1
            ],
        }

    # -- dreams ------------------------------------------------------------

    def save_dream(self, report_dict: dict[str, Any]) -> Path:
        cycle = int(report_dict.get("cycle", 0))
        path = self.dream_path(cycle)
        write_atomic(path, json.dumps(report_dict, ensure_ascii=False, indent=2))
        return path

    def next_cycle(self) -> int:
        # Max parsed index + 1, not len(glob) + 1: a deleted dream or a numbering
        # gap must never make the next cycle OVERWRITE an existing one — the record
        # is evidence, and evidence is append-only.
        indices = [
            int(m.group(1))
            for p in (self._root / "dreams").glob(f"{self._corpus}_c*.json")
            if (m := re.search(r"_c(\d+)\.json$", p.name))
        ]
        return max(indices, default=0) + 1

    # -- theta -------------------------------------------------------------

    def latest_theta_path(self) -> Path | None:
        bundles = sorted(self.policy_dir.glob("theta_v*.json"))
        return bundles[-1] if bundles else None

    def summary(self) -> dict[str, Any]:
        """What has actually been persisted. Useful for answering the question
        "is the learning loop closed" without reading the filesystem by hand."""
        theta = self.latest_theta_path()
        calibration = self.calibration()
        return {
            "corpus": self._corpus,
            "theta": theta.name if theta else None,
            "belief_bases_logged": sum(1 for _ in self.iter_belief_log()),
            "calibrated_propositions": sorted(calibration.get("propositions", {})),
            "trust_elicited": calibration.get("trust_elicited", False),
            "discovered_propositions": len(self.propositions()),
            "dream_cycles": self.next_cycle() - 1,
            "belief_chain": self.verify_chain(),
        }
