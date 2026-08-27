# mapo

A deterministic decision layer for LLM agents — the engine that runs it, the lab
that measures it, and the paper that validates it.

- **[`lab/`](lab/README.md)** — the DECISION layer and the measurement
  bench: arithmetic feasibility → beliefs with provenance → per-request assurance
  dial (A0–A3) → selective routing with abstention → accounting circuit breakers →
  EXPLAIN artifact. Corpora, registered predictions (P1–P14) and verdicts live here.
- **[`whitepaper/`](whitepaper/README.md)** — the paper (`paper-en.md` canonical,
  `paper-es.md` mirrored). `GATE.md` rules what may be claimed. Nothing enters the
  paper without an implementation that runs it in `lab/`.
- **[`legacy/`](legacy/README.md)** — an earlier execution layer, FROZEN. Not the
  product and not evolved: kept as the reference for the parts a real deployment
  needs and the bench has never had to model — search over a real index, permission
  scoping, citations verified against that index, streaming to a client. It was
  reviewed and repaired on 2026-08-27 (see its README) so that what it is worth
  reading for is worth reading.

## Order of work

The product is built from what the bench proves, not the other way round. `lab/`
keeps measuring patterns and validating them; the product engine starts when that
record is mature enough to build from. Until then nothing is ported.

Three things that must stay distinct, because two of them are one directory today:

| | |
|---|---|
| **The product** | the decision layer (feasibility, beliefs, assurance, routing, EXPLAIN) and the paradigms that survive measurement |
| **The bench** | corpus, runner, grading, metrics, registered predictions, tests — it MEASURES the product and is not part of it |
| **`legacy/`** | frozen reference for retrieval, scoping, citations and streaming |

The rule that keeps the first two apart once they are split: the bench imports the
product; the product never knows the bench exists.
