# mapo

A deterministic decision layer for LLM agents — the engine that runs it, the lab
that measures it, and the paper that validates it.

- **[`engine/`](engine/README.md)** — the EXECUTION layer (LangGraph): strategies
  (dag, react, map_reduce, plan_execute), shared blackboard, RRF semantic search,
  tools. Its prose LLM strategy classifier is the piece the study shows fragile —
  and the piece the decision layer replaces.
- **[`lab/`](lab/README.md)** — the DECISION layer and the measurement
  bench: arithmetic feasibility → beliefs with provenance → per-request assurance
  dial (A0–A3) → selective routing with abstention → accounting circuit breakers →
  EXPLAIN artifact. Corpora, registered predictions (P1–P14) and verdicts live here.
- **[`whitepaper/`](whitepaper/README.md)** — the paper (`paper-en.md` canonical,
  `paper-es.md` mirrored). `GATE.md` rules what may be claimed. Nothing enters the
  paper without an implementation that runs it in `lab/`.
