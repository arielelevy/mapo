# mapo

A deterministic decision layer for LLM agents — the decision layer, the bench that
measures it, and the paper that validates it.

- **[`lab/`](lab/README.md)** — the DECISION layer and the measurement bench:
  arithmetic feasibility → beliefs with provenance → per-request assurance dial
  (A0–A3, with a floor that **learns from typed rejection statistics**) → selective
  routing with abstention → an executed probe that turns opinion into observation →
  EXPLAIN artifact, reproducible by belief-base digest. Corpora, registered
  predictions (**P1–P15, with verdicts**) and the REC direction live here.
- **[`whitepaper/`](whitepaper/README.md)** — the paper (`paper-en.md` canonical,
  `paper-es.md` mirrored). `GATE.md` rules what may be claimed. Nothing enters the
  paper without an implementation that runs it in `lab/`.
  [`whitepaper/artefactos/`](whitepaper/artefactos/README.md) versions the visual
  documents (self-contained HTML, opens in any browser) alongside their published,
  always-current artifact URLs.
- **[`legacy/`](legacy/README.md)** — an earlier execution layer, FROZEN. Not the
  product and not evolved: kept as the reference for the parts a real deployment
  needs and the bench has never had to model — search over a real index, permission
  scoping, citations verified against that index, streaming to a client. It was
  reviewed and repaired on 2026-08-27 (see its README) so that what it is worth
  reading for is worth reading.

## Where the record stands (2026-08-27)

**P15 — the product claim, refuted, and the mechanism is the finding.** On a world θ
had never seen (seed 47, 390 cells, zero infra errors), per-request routing lost to
the best fixed paradigm by −0.087, beyond the noise floor — while reproducing every
decision 26/26 from its recorded belief base. Verified mechanism: the region
vocabulary has **no horizon axis**, so the tasks that punish a fixed choice were
indistinguishable from the ones that reward it, and θ routed against its own recorded
verdict (P6b) because no label ever told it it was in that case. Honest headline:
**selection without sensing loses to a strong fixed default.** Sensitivity check:
repairing the learning validity (episode aggregation, clean holdout) leaves the number
identical — the refutation is not an artifact.

**The direction that follows: REC (Counterfactual Epistemic Repair).** A recorded
decision plus a deterministic trace can say which minimal belief, at which evidence
strength, would have changed the plan — and what bounded observation could resolve it.
Implemented so far: the counterfactual solver (pure replay, hypotheses never touch the
factual record), acquisition clauses that are drafts until certified, and the
certification loop — three non-overlapping worlds, a **single-use final world**
enforced by a ledger, and fail-closed installation onto the signed policy bundle.
Design: `lab/PATRON_REC.es.md`. Live status: `whitepaper/artefactos/`.

## Order of work

The product is built from what the bench proves, not the other way round. `lab/`
keeps measuring patterns and validating them; the product engine starts when that
record is mature enough to build from. Until then nothing is ported. The physical
architecture, when it starts, is already decided and reversible:
`lab/ARQUITECTURA.es.md`.

Three things that must stay distinct, because two of them are one directory today:

| | |
|---|---|
| **The product** | the decision layer (feasibility, beliefs, assurance, routing, probe, EXPLAIN) and the paradigms that survive measurement |
| **The bench** | corpus, runner, grading, metrics, registered predictions, tests — it MEASURES the product and is not part of it |
| **`legacy/`** | frozen reference for retrieval, scoping, citations and streaming |

The rule that keeps the first two apart once they are split: the bench imports the
product; the product never knows the bench exists.
