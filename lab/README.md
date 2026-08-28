# lab

> 🇬🇧 English · [🇪🇸 Español — documentación del entregable](README.es.md)

Harness for measuring **when selecting an orchestration paradigm actually pays** — and
when a system is better off not selecting at all.

Companion to the paper in `..\whitepaper\` (`paper-en.md`) and its pattern
catalogue (`PATTERNS.md`).

---

## The question

Published work measures a **17.1pp oracle gap** between per-task paradigm selection and
the best fixed paradigm (Select-then-Solve, arXiv 2604.06753 — 6 paradigms, 4 frontier
models, 10 benchmarks, ~18k runs). Their router recovers only **26%** of it, and
zero-shot LLM self-routing recovers *negative* value: Qwen3-30B drops to 27.5%, below
its own baseline.

So: the prize is large, nobody is capturing it, and naive selection is worse than none.
This harness measures why, and tests two claims.

**Claim 1 — Selection Value Theorem.** Selection beats the best fixed paradigm iff

```
pi * alpha * G  >  (1 - pi) * beta * L
```

so a router obliged to always choose has no control over `beta` and pays every false
positive. A **selective** router that defers to a safe fallback outside its
high-confidence region does. Optimal coverage is generally well below 1.

**Claim 2 — Cascade Dominance.** Where a cheap failure detector exists, don't predict at
all: try cheap, verify, escalate. A router that misroutes pays a *quality* loss; a
cascade pays a *cost* loss. Hence the partition:

```
v = 1 (oracle exists)  ->  CASCADE, no router needed
v = 0 (no oracle)      ->  route, with the deferral discipline of Claim 1
```

If Claim 2 holds, most of the routing literature is solving the wrong problem in the
verifiable regime.

---

## Design constraints

**No agent framework.** Direct HTTP to Azure OpenAI. Frameworks inject prompts, retries
and parsing; each would be a confound, and their hidden retries destroy replayability,
which is the property under study.

**No LLM judge.** Every task has a set-valued oracle; grading is set F1 after
normalisation. The effect is a few percentage points, and judge noise on that order is
indistinguishable from the effect.

**No defaults in configuration.** Missing env var raises at import. A silent fallback to
something plausible is how a study ends up measuring a configuration nobody chose.

**Every paradigm shares everything but control structure.** Same tools, same model, same
decoding, same answer contract.

---

## The deliverable: a deterministic decision layer for LLM agents

> 🇪🇸 Esta sección en español: [README.es.md](README.es.md)

This section documents the **solution as shipped** — what the system does at runtime and
what it guarantees. It says nothing about how the claims were verified or what the
experiments cost; that lives in the sections below and in the paper.

### What it is

A decision layer that sits **in front of** an LLM agent's orchestration. For every
incoming request it decides four things, deterministically and on the record:

1. **Which orchestration paradigms can run at all** (feasibility),
2. **what assurance the request requires** (the per-request dial),
3. **whether to select a specialised paradigm or defer to the general fallback**
   (selective routing with abstention),
4. **and it leaves an artifact that lets an auditor replay the decision** (EXPLAIN).

The LLM never manages control flow. It participates as a **sensor**: it emits typed
propositions about the task, with a credence and a provenance, and a deterministic
symbolic layer decides over that belief base.

### The flow of one request

```
request
  │
  ├─ 1. FEATURES         φ(request): structural, cheap to extract
  │      features.py       cardinality n, coupling, oracle availability, horizon,
  │                        reversibility, write contention, budget
  │
  ├─ 2. FEASIBILITY      pure arithmetic over what the task declares — no LLM call
  │      feasibility.py    "needs 386k tokens in one prompt against a 24k allowance"
  │                        → paradigm recorded as infeasible, at zero cost
  │
  ├─ 3. BELIEFS          the LLM as sensor: typed propositions with credence
  │      beliefs.py        + provenance:  COMPUTED > OBSERVED > ELICITED > ASSUMED
  │      rules.py          deterministic rules decide over the base; a rule may demand
  │                        a minimum provenance (an irreversible action does not accept
  │                        the model's opinion as evidence)
  │
  ├─ 4. ASSURANCE        the per-request dial A0–A3 (table below)
  │      assurance.py      floor derived from beliefs about the request itself;
  │                        the caller can ask for more, never for less
  │
  ├─ 5. SELECTIVE ROUTE  Π(φ, θ) with abstention: emit a specialised paradigm only
  │      router.py         inside the high-confidence region (κ > τ); otherwise defer
  │      policy.py         to the general fallback. θ is a versioned, signed, readable
  │                        decision list — not weights. Same φ and θ ⟹ same plan.
  │
  ├─ 6. EXECUTION        the chosen paradigm runs against the tool surface, which
  │      paradigms/        carries deterministic accounting signals (stagnation,
  │                        coverage, ID accounting) acting as circuit breakers —
  │                        the loop cannot re-plan forever on intuition
  │
  └─ 7. EXPLAIN          the recorded artifact: φ, beliefs with provenance, assurance
         router.py         level, verdicts, chosen plan, outcome. An auditor inspects
                           what was asserted and replays the rules — never the model.
```

### Assurance is a property of the request, not of the system

Full determinism is not available for an LLM, so claiming it would be false. Chasing it
by keeping the model out of the decision is worse: it discards information the model
genuinely has and still promises a guarantee that cannot exist. The guarantee that CAN
be given changes shape:

```
NOT   "the same prompt yields the same answer"          (false, always)
BUT   "the same belief base yields the same decision"   (true, and auditable)
```

The default sits at the flexible end; strictness is a priced escalation. A level
constrains the admissible pattern space; plasticity permutes freely inside it.

| Level | Provenance floor | theta learns online | Sealed | Patterns |
|---|---|---|---|---|
| `A0_EXPLORATORY` | `ASSUMED` | **yes** | no | full algebra |
| `A1_STANDARD` | `ELICITED` | no | no | catalogue |
| `A2_ACCOUNTABLE` | `ELICITED`* | no | no | catalogue, depth <= 3 |
| `A3_CERTIFIED` | `OBSERVED` | no | **yes** | certified subset |

\* rises to `OBSERVED` automatically while calibration is unearned.

A caller requesting `A0` on an irreversible task gets `A3` anyway, and the plan space
drops from 7 patterns to 4 — `dag_strategy`, `plan_execute` and `reflection` are
excluded, not because they are worse (they are often better) but because their control
flow is unbounded and their failure modes are not enumerable. That is why `A3` is an
escalation and not a default.

### How it learns without becoming unauditable

Learning is **offline and copy-on-write**, never inside a request. Episodes consolidate
into a *candidate* policy θ' — still a readable decision list over φ, updated with
interpretable Hebbian statistics (`policy.py`). Promotion is guarded: θ' replaces θ only
if it does not regress on held-out episodes, and the record is split three ways by task
(one part proposes, one scores, one is touched only by the promotion guard), so a
discovered rule can never be scored by the data that proposed it. A promoted θ gets a
version; two versions diff like code. Rollback is trivial because old policies are
immutable artifacts.

### What it guarantees, and what it does not

| Guaranteed | Not guaranteed |
|---|---|
| Same belief base ⟹ same decision, replayable from the EXPLAIN record | Same prompt ⟹ same answer (impossible with an LLM, and never claimed) |
| An infeasible plan is never attempted, and its exclusion is recorded with the reason | That the selected paradigm succeeds — selection bounds regret, not outcomes |
| Irreversible actions gated on computed/observed evidence only | Anything about tasks outside exact-answer extraction over documents |
| Learning cannot silently regress the policy (promotion guard) | That θ is optimal — only that it is inspectable, versioned and non-regressing |

---

## Layout

```
app/
  config.py      env validation, frozen settings, decode fingerprint
  llm.py         direct Azure OpenAI, content-addressed cache (enables D3)
  features.py    the phi vector; COMPUTABLE vs DERIVED split
  beliefs.py     Belief/Provenance/BeliefBase, deterministic Governance over rules,
                 and Calibration (reliability diagram + ECE) for elicited credence
  rules.py       the standard rule set AS DATA, plus the sensors that populate a base
  assurance.py   the per-request assurance dial and what each level admits
  paradigms/     direct, react, map_reduce, plan_execute, reflection
  paradigms/dag.py  DAG with verify-replan over a shared blackboard: plan ->
                 topological waves -> verify on 4 dimensions -> replan (<=3, ready
                 0.8, diminishing 0.05) -> synthesise. The most elaborate topology
                 available, included so the comparison is not stacked for the simple
                 ones. Sequential, so its LATENCY is not comparable.
  grading.py     set F1, deterministic
  policy.py      theta: versioned, signed, readable. Hebbian plasticity.
                 Promotion with regression guard.
  router.py      partition -> probe -> deferral, plus the EXPLAIN artifact
  metrics.py     pi/alpha/beta/G/L, beta_max, oracle gap, risk-coverage, cascade
  runner.py      cross product executor and report
  main.py        FastAPI surface (thin; the science runs from scripts)
corpus/
  generate.py    stratified synthetic corpus, exact ground truth
  verify.py      independent oracle re-derivation — a required gate
  gold_v1/       generated corpus
tests/
  test_science.py  validates the measurement layer against known answers
```

---

## Running it

```powershell
cd "D:\Apps\lab"
py -m pip install -e .        # pines reales en pyproject.toml
copy .env.example .env    # then fill AZURE_OPENAI_API_KEY

# 1. Validate the measurement layer. No API key needed. Must pass first.
py tests\test_science.py

# 2. Build and verify the corpus. E0 scale: --per-cell 15 gives ~180 tasks.
py corpus\generate.py --seed 7 --people 48 --per-cell 15 --widths 4,16,48 --out corpus\gold_v1
py corpus\verify.py --corpus corpus\gold_v1

# 3. Smoke test the cross product on a couple of tasks before committing spend.
py -c "from app.config import Settings; from app.runner import Runner; r=Runner(Settings.from_env(),'gold_v1'); r.run_cross_product(limit=2)"

# 4. Full run, then the report.
py -c "from app.config import Settings; from app.runner import Runner; r=Runner(Settings.from_env(),'gold_v1'); r.run_cross_product()"
py -c "from app.config import Settings; from app.runner import Runner; from app.policy import DeterminismMode; r=Runner(Settings.from_env(),'gold_v1'); print(r.save_report(r.report(DeterminismMode.D1_FROZEN)))"
```

> **Pending migration.** `runner.py`, `main.py` and `router.py` still take the older
> `DeterminismMode` (D0-D3, a system-wide mode). `beliefs.py`, `rules.py` and
> `assurance.py` implement the per-request model described above. Both work; they have
> not been merged yet. The report command therefore still names `DeterminismMode`.
> Migrating means: `router.decide` consumes a `BeliefBase` and an `AssuranceProfile`
> instead of `Features` and a mode, and `Runner.report` takes an `Assurance` level.

The API server is available but optional — `uvicorn app.main:app --port 8000`. It is not
started automatically, and an experiment reproducible only through an HTTP server is not
reproducible.

Runs resume: results append to `results/<corpus>_rows.jsonl` and completed
`(task, paradigm)` pairs are skipped. The LLM cache makes a second pass free and
identical.

---

## What E0 has to answer

| Outcome | Meaning |
|---|---|
| Some coverage `c* < 1` captures **> 26%** of the oracle gap | Claim 1 holds. The paper exists. |
| Capture is maximal at `c* ≈ 1` | Claim 1 survives as theory, empirical contribution weakens |
| Cascade beats every fixed paradigm and every router on `v = 1` tasks | Claim 2 holds. This is the headline. |
| `dag_strategy` loses to `react` overall | The most elaborate topology does not beat the general fallback |
| Cascade cost ratio is prohibitive | Claim 2 needs the budget cap; report the ratio honestly |
| Nothing beats always-`react` at any coverage | Publish the negative result with Theorem 1 as its explanation. Still a paper. |

Register predictions before running. `tests/test_science.py` already encodes the ones
that are checkable without spend.

### Registered predictions — out-of-window regime study (2026-08-26, before running)

Design: matched task sets on `gold_v2` (in-window) and `gold_deep` (~483k tokens,
out-of-window), 7 paradigms, `repeat = 3`, per-cell noise floor. Plus a zero-cost
feasibility sweep (pure arithmetic, no LLM calls) over every task × paradigm of
`gold_wide` (~135k), `gold_deep` (~483k) and `gold_xl` (~1,272k).

| # | Prediction | If it fails |
|---|---|---|
| P1 | Feasibility pruning: on the three large corpora, every task whose required evidence exceeds the allowance leaves `direct` infeasible by arithmetic, recorded at zero cost; on `gold_xl` the pruning also reaches full-coverage cells for paradigms whose projection exceeds the budget | The feasibility check is wrong or the corpora do not leave the window — the regime claim collapses |
| P2 | Ranking invariance among feasible paradigms: on matched tasks (same cardinality, ~30× content, `gold_v2` ↔ `gold_deep`) the per-cell utility ordering among *feasible* paradigms is preserved; what changes is the feasible set, not the order inside it | The claim "mechanisms are invariant to content scale" is rewritten — magnitudes AND orderings become corpus-local |
| P3 | `map_reduce` stays at u≈0 on coupled (C3) cells at every scale — the failure is structural, not capacity | §8 attributes to structure what is actually scale; the ontological argument is withdrawn |
| P4 | `dag_strategy` does not beat `react` on net utility out-of-window, and its cost stays ≥2× `react` on C5 cells | §8.7 is reported inverted: the elaborate topology pays off exactly where the window ends |
| P5 | Replicate variance concentrates where it did before: C3 cells are the unstable ones; C2/C4 reproduce identical quality in most cells | The per-cell noise floor is not stable across corpora and every quality delta must carry its own per-cell floor |

### Registered predictions — modern paradigms screening (2026-08-26, before running)

Two paradigms added against the measured failure roots: `rewoo` (all tool calls planned
in one pass, executed without the LLM, one solve call — attacks the O(history) cost root)
and `gist_reader` (one prompt over a deterministic gist table + targeted batched full
reads — attacks the evidence>window root). Screening design, token-minimal: `gold_deep`
only, 4 discriminating tasks (c2-000-w48, c3-001-h2, c4-000-w48, c5-000-w48),
`repeat=2`, `workers=1`. The `repeat ≥ 3` standard applies only if they survive
screening and enter the paper.

| # | Prediction | If it fails |
|---|---|---|
| P6a | `rewoo` matches `react` quality (±0.05) on C2/C4 at ≤50% of react's cost on the same cells — no history resend is the mechanism | The cost lottery of iterative reading is not attributable to history resend |
| P6b | `rewoo` fails coupled/unknown-horizon cells (u ≤ 0.33 on c3-001-h2 and c5-000-w48): a plan without observation cannot discover the hop that depends on a prior result | Adaptivity is NOT necessary for coupling — §8.1's mechanism needs rewriting |
| P7a | `gist_reader` reaches u ≥ 0.75 on C2/C4/C5 out-of-window at median cost ≤ `react` | The gist table does not carry enough signal to target reads — the ladder needs full summaries, not gists |
| P7b | Its failure mode is the exact datum absent from a gist (MemFail's summary failure): wrong unit selection on C3, or a missed exact value on C4 | — (mechanism check, not a pass/fail gate) |
| P7c | Its gist table goes infeasible by arithmetic at high cardinality (w400 cells of gold_wide/gold_xl) — recorded free, before any spend | The feasibility arithmetic for the table is mis-specified |

### Registered prediction — held-out world transfer (2026-08-26, before running)

`gold_holdout`: a NEW world, seed 23 (every prior result used seed-7 worlds), same
regime as gold_deep (hard, 8k-token units, 26 tasks), ground truth independently
re-derived 26/26. Purpose: the per-cell verdicts in CONCLUSIONS were derived from seed-7
data — if they do not transfer to an unseen world, they are world-specific (overfit
conclusions), not structural. Screening design: 5 informative paradigms (react,
dag_strategy, map_reduce, rewoo, gist_reader) × 4 discriminating tasks × repeat=2,
workers=1.

| # | Prediction (transfer of per-cell verdicts) | If it fails |
|---|---|---|
| P8a | `react` u ≥ 0.9 on every feasible cell | The "general fallback" verdict was world-specific |
| P8b | `map_reduce` u = 0 on the coupled cell — the failure is structural, worlds cannot rescue it | The ontological argument of §8 is wrong |
| P8c | `rewoo` transfers P6a/P6b (wins C2/C4 cheap; fails coupled/unknown-horizon) | Its region was an artifact of seed-7 phrasing |
| P8d | `gist_reader` transfers P7a (u ≥ 0.75 on C2/C4/C5 at ≤ react's cost) | ídem |
| P8e | `dag_strategy` (basic surface) stays at risk on the deep coupled cell: at least one replicate with u=0 or cost ≥ 3× its own median | The C3 runaway was a seed-7 accident, and the accounting-signals argument loses its showcase |

**Decision rule**: if two or more of P8a–P8e fail to transfer, CONCLUSIONS is demoted to
corpus-local and every per-cell rule must carry a per-world caveat.

### Registered prediction — managed board (2026-08-26, before running)

The cognitive arm measured that voluntary self-management does not happen (1 note, 1
compaction, 0 plans in 28 rows). The `managed` surface variant moves the bookkeeping to
the environment: after every consumed batch, full-text tool results from earlier turns
are demoted deterministically to id+gist stubs (re-readable on demand). Same tools as
basic; the only difference under test is what the harness does to the history.
Screening: react + dag_strategy × managed on the 4 discriminating gold_deep tasks,
repeat=2, workers=1.

| # | Prediction | If it fails |
|---|---|---|
| P9a | `react`×managed preserves quality (Δu within the cell's replicate spread) while cutting cost on the heavy cells (C3-h2, C5-w48) by ≥2× vs `react`×basic on the same cells | The O(history) mechanism is NOT the main component of react's cost lottery |
| P9b | `dag_strategy`×managed shows no C3 runaway ≥ 100k tokens (basic showed 396k) | The runaway is driven by the verifier's re-planning, not by history growth — the accounting signals remain the only fix |
| P9c | Quality does NOT degrade from demotion: no cell where managed loses while basic wins across both replicates | The gists destroy evidence the model still needed — demotion must be lazier |

### Registered predictions — three verified candidates (2026-08-26, before running)

`graph_traverse` (HippoRAG/GraphReader/StepChain), `extract_compute` (LOTUS/CodeAct/DFA),
`streaming_scan` (Chain-of-Agents). Screening is deliberately minimal: each candidate
runs only in its predicted niche plus one failure check; corpus-paying candidates run at
`repeat=1` (stability is measured later, only for survivors). The graph index is
amortised and disk-memoised; its cost lands in the first paying row, honestly.

| # | Prediction | If it fails |
|---|---|---|
| P10a | `graph_traverse` solves the coupled cells (c3-000-h1, c3-001-h2) with u ≥ 0.9 at per-question cost ≤ 1/3 of react's on the same cells (index excluded, reported separately) | Chains are not reducible to entity adjacency in this corpus — the traversal thesis fails here |
| P10b | It underperforms react on c5-000-w48 (contradiction-finding is not relational adjacency) | Its region is wider than predicted — good news, re-screen C2/C4 |
| P11a | `extract_compute` reaches u ≥ 0.9 on c2-000-w48 and c4-000-w48 with the count computed EXACTLY (zero arithmetic error in the emitted number) | Structured extraction misses records the prose map caught — the schema step is the weak link |
| P11b | It fails the coupled cell (c3-001-h2): rows extracted in isolation cannot join A→B | Extraction schemas CAN express joins — map_reduce's failure root needs restating |
| P12a | `streaming_scan` reaches u ≥ 0.75 on c5-000-w48 at cost ≈ content×1 with cost spread ≤ 1.5× (no lottery) | The carry loses candidates across chunks — the registry needs append-only discipline |
| P12b | Its failure mode on c2-000-w48 is partial recall (carry drops items), not invention | — (mechanism check) |

### Registered predictions — `pointer_chase` (2026-08-27, before running)

Designed against this harness's own falsifications (author-directed, drafted by the
assistant, 2026-08-26 session): the coupled niche is open — `graph_traverse` was
falsified on its thesis cells (P10a: u=0.0 on both, "Not found" after a ~280k-token
index), decomposition (plan/dag) and the react tool-loop carry measured failure
roots, and the scan-everything candidates are budget-infeasible by arithmetic (the
author ruled that infeasibility IS the screening result — P11/P12 stand unevaluated
under the production budget). Mechanism: anchor by retrieval, then a CODE-driven
loop where the LLM is a sensor over ONE unit per call, emitting `{fact, next}`;
code validates pointers, counts stalls and hallucinated pointers, and stops at the
arithmetic hop cap (`min(6, budget // mean_unit)` — against the budget, not the
conversation allowance: the chase holds no conversation). No history resend, no corpus
index, no model-assessed budget (BAGEN 2606.00198; DocTrace 2606.10921). Screening:
gold_deep, niche c3-000-h1 / c3-001-h2 at repeat=2 + anti-niche c2-000-w48 /
c5-000-w48 at repeat=1; estimated ~210k tokens (`gpt-5-chat`).

| # | Prediction | If it fails |
|---|---|---|
| P14a | `pointer_chase` solves the coupled cells (c3-000-h1, c3-001-h2) on gold_deep with u ≥ 0.9 at per-cell cost ≤ 1/3 of react's median on the same cells, with replicate cost spread ≤ 1.5× (the loop is code — no lottery) | The chain is not a text-visible pointer sequence: the sensor cannot see the next link even with the full unit in front of it, and coupling needs model-carried search after all |
| P14b | On the anti-niche (c2 coverage, c5 contradiction) it stops within its hop cap (cost ≤ cap × mean unit, no runaway) and fails honestly — DEAD_END/stall or a wrong answer with `hallucinated_units` = 0 — not by invention | The stall accounting is mis-specified: the chase wanders instead of stopping |
| P14c | (nano, after the chat verdict) Being structure-carried, its c3 verdict transfers to nano (Δu ≤ 0.25) where react collapsed — coupling becomes routable to a nano-tier model | Reading pointers requires model-carried judgment: P13a's structure argument does not extend to coupling |

### Registered prediction — second model, structure vs judgment (2026-08-26, before the grid)

Model switched to `gpt-5.4-nano` (author decision): temperature=0 + seed measured
near-token-deterministic, own quota, nano-tier price. Smoke already measured: `direct`
perfect (u=1.00, replicate-identical) and `react` collapsed (u=0.00 × 4, quits after 3
iterations having read relevant units — correct tool use, insufficient search
persistence). The grid tests whether that split is systematic:

| # | Prediction | If it fails |
|---|---|---|
| P13a | Paradigms where STRUCTURE carries control — `rewoo`, `extract_compute`, `streaming_scan`, `map_reduce` in its region, `direct` where feasible — hold their per-cell verdicts on nano (Δu ≤ 0.25 vs the chat-model grid) | Structure does NOT rescue the cheap model — the engine cannot downgrade models in structured regions |
| P13b | Paradigms where the MODEL carries control — `react`, `reflection`, `dag_strategy` — degrade materially on nano (Δu ≥ 0.25 on at least half their feasible cells) | Cheap models CAN drive open loops — the persistence failure was task-local, and the cost story changes entirely |
| P13c | Nano's determinism holds across the grid: replicate pairs identical in utility on ≥ 90% of cells | t=0 + seed does not pin this model either, and the noise-floor machinery stays mandatory |

### Registered prediction — THE PRODUCT CLAIM, on a world it has never seen (2026-08-27, before the run)

Every prediction above is about a PARADIGM. This one is about the ENGINE, and it is the
criterion the project is built to satisfy: *give MAPO a new gold corpus it has never
seen, and have it execute better than any fixed paradigm in the harness.*

Corpus `gold_transfer`, **seed 47** — a world neither θ nor any earlier prediction has
touched (seeds used so far: 7 and 23). Same shape as `gold_deep` so the regime is the one
where routing can matter at all: 48 people, 72 units, ~515k tokens of content, 26 tasks
across C1/C2/C3/C4/C5/C7, `--hard`. Verified independently of the generator: 26/26, and
the near-miss guard passes.

θ is fitted on the EXISTING record only. Nothing from `gold_transfer` enters θ before the
comparison; the run produces the rows, and the router is scored on rows it did not train on.

**Estimated before spending** (median cost per cell from the deep-regime runs, × repeat 3,
over the cells feasibility leaves standing): **9.0M tokens, 336 cells**. The arithmetic
already prunes `map_reduce` on 18 of 26 tasks at zero cost — that pruning is not a
prediction, it is the feasibility layer having run before any token was spent.

| # | Prediction | If it fails |
|---|---|---|
| P15a | **Net positive oracle gap against the best fixed paradigm, including always-`react`**, on the held-out corpus: the utility the router's selective routing achieves exceeds the best single fixed choice by more than the per-cell noise floor | The product claim is false as stated. Per-request selection does not beat a good default on a world it has not seen, and what the harness measured was a catalogue, not an engine |
| P15b | The gap is **concentrated where a fixed choice is structurally wrong** — the coupled (C3) and unknown-horizon (C5) cells — and is within the noise floor on C1/C2, where everything feasible works | The gain, if any, is diffuse: it comes from averaging rather than from deciding, and the mechanism story in §8 does not explain it |
| P15c | Abstention is **not free but is not harmful**: on the tasks where θ's margin is below τ the router defers to the fallback, and on those tasks the fallback lands within the noise floor of the best fixed paradigm | Abstention is costing utility — deferring is worse than committing, and the selective-prediction framing (§2.5) does not transfer to paradigm choice |
| P15d | The routing decision is **reproducible**: re-deciding from the recorded belief base yields the identical paradigm on 100% of tasks, and the EXPLAIN artifact suffices to re-derive it without re-running the model | Decision stability is not a property of this system, and every claim about auditability in §6.2 goes with it |

**Addendum, recorded BEFORE the run and after re-reading the nano record.** On the deep
regime the nano grid measured **u=0.000 across the whole of C3** — every paradigm, every
cell. `gold_transfer` has the same shape as `gold_deep`, so its two C3 tasks are likely to
come back all-zero, and a cell where the ORACLE is zero offers no gap for anything to
capture. If that happens, P15b is evaluated on C5 alone and the C3 half is reported as
**vacuous, not as confirmed** — the distinction matters, and it is written down here rather
than decided once the numbers are in. C3 in nano remains an open region, not a result.

### Registered prediction — P16, the clean replication (2026-08-27, before the run)

P15 refuted the product claim and said why. Both causes are fixed and their effect was
measured for free on the old corpus; this run tests them where it counts — a world θ has
never seen.

`gold_p16`, **seed 61** (used so far: 7, 23, 47). Verified 26/26 by the generator-
independent verifier, and the continuation axis separates it exactly as it separates the
other three (C5 6/6, zero false positives on C1/C2/C4). θ is fitted on the FULL prior
record — deep + holdout + v2 + transfer — under 4-segment regions
(`REGION_VOCABULARY = regions/2-continuation`). Nothing from `gold_p16` enters θ.

**The verdict code is frozen before the run.** `_analyze_p16.py` is committed in the same
commit as this prediction and before a single row of `gold_p16` exists. Registering a
prediction in prose still leaves room to pick the valuation after seeing the numbers;
freezing the code that judges does not. Whatever it prints is the verdict.

**Estimated before spending**: 12,344,856 tokens over 336 feasible cells (P15 actual:
14.07M). `repeat = 3`, per-cell noise floor, `workers = 1`.

The valuation, decided now: the **real action** is scored — a cascade climbs rung by rung
until the oracle accepts, a gate runs the fallback and does not execute the plan — and
**the full climbed cost is charged**, at λ = 0.05 primary. That last part is what P15's
exploratory decomposition could not close, and it is the one that could take the
advantage away.

| # | Prediction | If it fails |
|---|---|---|
| P16a | On the **routing cohort** (non-gated tasks), action-aware net utility at λ=0.05 beats BOTH the best fixed paradigm and always-`react`, by more than the per-cell noise floor | Per-request selection does not pay once climbing is charged. The axis and the action-aware valuation were necessary and still not sufficient, and the routing surface is reported as a measured negative — twice, on two worlds, which is a stronger negative than most routing papers publish as a positive |
| P16b | The **gate price** is reported separately and is a deficit: on irreversible tasks the gate runs the fallback by design. Preregistered as a COST, not as a routing failure | If the gated cohort shows a gain, the gate is not costing what the design says it costs and the governance claim needs restating |
| P16c | The advantage survives to λ ≥ 0.05 and the **crossover λ is published** whatever it is — the point where charging for cost erases the gain | A crossover below 0.05 means the gain is an artifact of not charging for tokens, and the honest claim becomes "selection buys quality only when cost is free" |
| P16d | Reproducibility holds under the new vocabulary: re-deciding from the recorded belief base yields the identical paradigm AND digest on 26/26 | The 4th region segment broke decision stability — and §6.2's auditability claim goes with it |

**What a negative buys.** P15 already established that selection without sensing loses.
If P16 also fails, the finding is not "the router does not work": it is that on this
corpus family, at this model tier, **per-request paradigm selection does not recover its
cost even with the missing axis supplied and the real action scored** — with the
mechanism isolated at each step. That is a publishable negative result about a technique
the literature reports positively, and it is what the bench was built to be able to say.

### P15 verdict (2026-08-27, same day, run complete: 390/390 cells, 0 infra, 14.07M tokens vs 9.58M estimated)

| # | Verdict | The number |
|---|---|---|
| P15a | **REFUTED** — net gap **−0.087** vs the best fixed (`dag_strategy`, 0.615 vs router 0.527), beyond the noise floor (0.057). Against always-`react` the router is +0.035, **within** the floor: vacuous, not a win | captured fraction of the oracle gap: −0.833 |
| P15b | **REFUTED** — the gain concentrated where predicted for C2 (+0.121) but the LOSS concentrated exactly where the gain was predicted: C5 (−0.278). C3 came back oracle-zero and is reported **vacuous**, as the pre-registered addendum required | per-cell deltas in `results/nano/p15_verdict.json` |
| P15c | **INSUFFICIENT n** — one abstention in 26 tasks (it landed badly: 0.000 vs 0.333); one observation is not a verdict in either direction | — |
| P15d | **CONFIRMED** — re-deciding from the recorded belief base reproduced paradigm AND belief digest on 26/26 tasks | the auditability claim of §6.2 stands |

**Mechanism, verified against the record — this is the finding, not a consolation:**

1. **The region vocabulary cannot see the axis that kills.** C5's defining feature — the
   number of hops is not knowable in advance — has NO axis in φ's binning
   (cardinality × oracle × coupling). Verified: C5 tasks land in `few/oracle/loose` and
   `many/oracle/loose`, the SAME regions as C2 and C4. θ therefore routed its C2/C4
   winner (`rewoo`) into all six C5 tasks — against its own registered verdict P6b
   ("rewoo fails unknown-horizon"), which it could not apply because the region label
   never told it it was in that case. The router lost precisely where its sensing was
   blind, and the machinery built to un-blind it (the probe, horizon estimation) exists
   and was not in this decision path.
2. **The best fixed paradigm flipped across worlds.** On the prior record `dag_strategy`
   never beat `react` net out-of-window (P4); on seed 47 it is the best fixed (0.615).
   θ can only route toward what its record says wins, so a world where yesterday's
   dominated paradigm is today's best is a world where learned selection starts from
   behind. This is a transfer statement about learned routing as such, not about this
   implementation.
3. Where the record DID carry the signal, selection worked: C2 delta +0.121 — `rewoo`
   over the fixed best, consistent with P6a for the third corpus in a row.

**Sensitivity (exploratory, post-registration, 2026-08-27 same day).** After the
learning-validity repair (episodes aggregated per (task, paradigm) cell — 275
pseudoreplicated trials became 140 cell episodes — and the candidate no longer fitted on
the final block), the verdict is **unchanged: −0.0874**. The refutation is not an
artifact of pseudoreplication; the missing-axis mechanism dominates.

**The Hebbian weight is selection-redundant (exploratory, free, 2026-08-27).** Selecting
by learned Hebbian weight, by mean utility, or by win rate produces IDENTICAL choices on
`gold_transfer` (router value 0.5263 all three): the weight is driven by the same episodes,
so its argmax coincides. The plasticity that GOVERNS is elsewhere — θ's reinforce/decay and
the §6.2 assurance ratchet; the weight column is record, not policy, and the operational
story should stop implying otherwise (handoff Fase 0, item 5).

**The third pre-emption is fixed, and selection fires (2026-08-27).** The two-step cycle
now lives once, in `app/decide.py`, and both callers take both steps — `serve.answer` and
the bench (`Runner.decide_for`, opt-in via `resolve_probes`, off by default so it can
never change what a registered prediction meant). Copying it into the bench would have
fixed the symptom and started the disease: two implementations of one decision, free to
drift, which is exactly the failure removed from the frozen execution layer this morning.

Verified without a network: on a bulk task with no runtime oracle, one plan says
`probe_then_decide` and `Decision.unresolved` is true — the paradigm on it is a
placeholder for AFTER probing, and calling it a decision was the measurement gap. Run the
probe, and the replan comes back **`specialise`**. That is the first time the selection
rule has fired anywhere in this investigation, and it closes the diagnosis: the three
pre-emptions were real, distinct, and only the third was ours to fix.

Two properties the tests pin, because both are ways the cycle could quietly lie: a probe
whose reading does not verify leaves the need UNRESOLVED (probing is not the same as
having measured), and it is **still charged** — evidence that did not arrive also cost.

**The full chain of pre-emption, measured (2026-08-27).** Separating the runtime
detector from the grading gold — the fix `CIERRE` §3.8.2 asks for — was measured for free
by passing the decision a task whose `oracle` is empty wherever **verifying is not cheaper
than solving**: a single fact can be checked by looking (C1), a trigger is present or not
(C7), but verifying that a list is COMPLETE (C2/C4), that a chain ended right (C3), or
when to stop (C5) *is* doing the task. Result on the held-out corpus:

| configuration | cascade | probe | defer | gate | **specialise** |
|---|---:|---:|---:|---:|---:|
| as P16 runs it | 21 | 0 | 1 | 4 | **0** |
| + hierarchical + backoff | 21 | 0 | 1 | 4 | **0** |
| + honest runtime detector | 2 | **14** | 6 | 4 | **0** |

Removing the oracle does not hand the decision to selection — it hands it to
`probe_before_deciding_on_bulk` at priority 80, which also outranks specialise at 70. And
`probe_then_decide` is by construction a TWO-step action: probe, *then* decide. **The
bench takes a single `plan()` call and never takes the second step**, so on those 14 tasks
it measures a placeholder rather than a decision. That two-step cycle exists — it is what
`serve.answer()` does, and what `/decide` does — but only on the product path, never in
`report()`.

So selection is pre-empted three times over, and each is a different kind of problem:
**by the oracle** (a corpus-design artifact: gradeability implies a detector), **by the
probe** (correct behaviour: do not specialise on unmeasured coupling), and **by the bench
never resolving the probe** (a measurement gap: the harness evaluates one step of a
two-step rule). Only the first is an artifact; the second is the layer working; the third
is the one to fix, and it costs a model call per task — which is precisely the governance
cost the thesis says should be priced rather than assumed away.

### P16 verdict (2026-08-27, run complete: 390 rows / 130 cells, 0 infra, 13.95M tokens)

The verdict script was committed BEFORE the run, so nothing about the valuation was
chosen after seeing numbers.

| prediction | verdict | number |
|---|---|---|
| **P16a** net oracle gap on the routing cohort, lambda=0.05 | **REFUTED** | -1.2888 vs best fixed (`rewoo`), noise floor 0.0339 |
| **P16b** price of the gate (irreversible cohort) | as designed | -1.0956, a deliberate deficit: the gate runs the fallback |
| **P16c** lambda sweep | **the decisive one** | see below |
| **P16d** reproducibility | **CONFIRMED** | identical paradigm + digest on 26/26 |

**P16c is the result of the whole programme, and it says exactly what was pre-registered
it would say if it went this way.**

| lambda | net vs best fixed | net vs always-`react` |
|---:|---:|---:|
| **0.00** | **+0.1211** | +0.1765 |
| 0.02 | -0.4043 | +0.0001 |
| 0.05 | -1.2888 | -0.2646 |
| 0.10 | -2.7631 | -0.7058 |
| 0.40 | -11.6089 | -3.3527 |

**With cost not charged at all, routing captures +0.121. Charging any realistic price
erases it — by lambda=0.02 the advantage is already inside the noise.** The honest
sentence, written before the numbers existed: *"la seleccion compra calidad solo cuando
los tokens son gratis"*. That is now measured, not feared.

**And the mechanism is the one already diagnosed, confirmed a third time.** Of the 22
routing-cohort tasks, **20 fire the cascade**, 1 defers, 1 asks for a probe. So P16 --
like P15 -- measured the CASCADE, not selection. That was written here before the run:
*"P16 is running under `regions/2`, so it will measure that same regime."* It did.

Per cell: C1 +0.9324 and C4 +0.2002 positive; C2 -0.2704, C5 -2.0838, and **C3 -3.7804**
-- the oracle-zero region, where every paradigm scores 0.000 and the lambda penalty turns
an expensive route into a deep loss. Routing into a dead region pays the whole price and
buys nothing, which is the clearest single argument for abstention this record contains.

**What this settles and what it does not.** It settles that **the routing claim, as
posed, fails on two independent held-out corpora** (seed 47 and seed 61). That is a
robust negative result and it is publishable as one. It does **not** settle whether
selection pays, because on neither corpus could the selection rule fire: gradeability
implied a detector, the cascade pre-empted at priority 90, and the bench took one step of
a two-step rule. **P17 is the first corpus where the question can even be asked.**

### P17 verdict (2026-08-28, run complete: 390 rows / 130 cells, 0 infra, 12.69M tokens)

First corpus where the selection rule could fire at all. Verdict script committed before
the run; the two prerequisite bugs it had were fixed before any row existed, and that is
recorded in the commit rather than hidden.

| prediction | verdict | number |
|---|---|---|
| **P17a** cascade fires on ≤ 6 of 26 | **CONFIRMED** | **2 of 26** |
| **P17b** selection decides on ≥ 7 of the 14 probed | **REFUTED** | **0 of 14** |
| **P17c** net gap positive, outside the noise floor | **REFUTED** | −1.0425 against a floor of 0.0786 |
| **P17d** reproducibility | **CONFIRMED** | 26/26 |

**P17b failed in the most informative way available, and it moves the diagnosis.** The
probe RAN on all 14 tasks and cost 83,539 tokens. It resolved **none of them**: all 14
stayed `unresolved`, so the honest action was deferral.

That is no longer pre-emption. The cascade does not crowd selection out any more (2 of 26);
the probe rule fires as designed (14 of 26). **Selection still cannot decide because the
evidence the probe returns does not clear the provenance floor it must clear.** Three
pre-emptions were diagnosed and fixed; this is a fourth, and it is the only one left.

**And the λ sweep makes the shape unmistakable.**

| λ | net vs best fixed | net vs always-`react` |
|---:|---:|---:|
| 0.00 | −0.1464 | **+0.0000** |
| 0.02 | −0.4693 | −0.3821 |
| 0.05 | −1.0425 | −0.9553 |
| 0.40 | −7.7294 | −7.6422 |

**Exactly zero against always-`react` at λ=0** — because 20 of the 22 routing-cohort tasks
end at the fallback (14 deferred unresolved, 6 deferred for want of confidence). On those
tasks the router IS `react`, so it cannot differ from it. Everything below λ=0 is the price
of having asked.

Per cell: C1 +0.9333 alone is positive; C2 −0.4413, C3 −1.0005, C4 −0.8236, C5 −0.7753.
Gate price on the irreversible cohort: −1.0158, deliberate as before.

**What this establishes, stated narrowly.** Removing the detector conflation was necessary
and it worked — the cascade stopped pre-empting. It was not sufficient: with the path
cleared, routing degenerates to the fallback on 20 of 22 tasks. **The binding constraint
is the probe, and it is now the only thing between the record and an answer about
selection.**

### The same bar, applied to the incumbents (2026-08-28, `_audit_catalog.py`, zero tokens)

A new candidate needs a registered prediction, a falsification criterion and a run before
it enters. The paradigms already in the row were never asked for any of that: they entered
by history. Exactly one arm has ever been retired on evidence, and the bar it had to clear
is the one the rest should clear too.

**Criterion:** a paradigm is dominated if it is never uniquely best and, when tied, never
the cheapest. Such an arm cannot be the right answer to any question — whatever it solves,
another solves as well or better for the same price or less.

Over 96 tasks across six corpora:

| paradigm | competed | uniquely best | cheapest when tied | verdict |
|---|---:|---:|---:|---|
| `rewoo` | 96 | 10 | 46 | earns its place |
| `gist_reader` | 96 | 9 | 9 | earns its place |
| `dag_strategy` | 96 | 8 | 0 | earns its place |
| `react` | 96 | 2 | 3 | earns its place (and is the fallback) |
| `map_reduce` | 33 | 1 | 2 | earns its place, **barely** — 180 of 270 rows infeasible |
| `reflection` | 14 | 1 | 0 | earns its place, thinly |
| **`plan_execute`** | 14 | **0** | **0** | **DOMINATED** |
| `graph_traverse` | 3 | 0 | 2 | price only — already falsified (P10a) |
| `extract_compute`, `streaming_scan` | 0 | — | — | infeasible on every row, as recorded |

**`plan_execute` is dominated.** The honest caveat: the one arm retired before it was
dominated on *every measured cell*, and this rests on 14 competed cells — thinner evidence
for the same verdict. What would overturn it is a single cell where
`plan_execute` is uniquely best, or ties cheapest.

**And it answers a design question with data rather than taste**: `map_reduce` is *not*
dominated. It wins one cell outright. So replacing it with a sub-agent/handoff pattern
would trade a measured cell of coverage for an unmeasured arm — the two should be run
against each other, not swapped.

### The ordering was not caution, it was necessary — and here is the proof (2026-08-27)

B2 (the honest-detector prerequisite) was deliberately held until P16's frozen verdict
had been computed and recorded. After applying it, the analyzer was re-run against the
same rows purely to check whether that discipline had bought anything:

| | frozen verdict (before B2) | same rows, after B2 |
|---|---:|---:|
| routing utility | −0.8464 | **−1.2506** |
| net vs best fixed | **−1.2888** | −1.6931 |
| actions | cascade 20 · probe 1 · defer 1 | **cascade 22** |
| C2 per cell | −0.2704 | **−1.7525** |

`gold_p16` was generated before `--honest-detectors` existed, so it declares a detector
on all 26 tasks while two C2 tasks carry an EMPTY gold list. Under the old rule those two
read as "no detector"; under the new one they read as "detector". Both flip into the
cascade, and the pre-registered number moves by 0.40.

So the verdict that stands is the one in `p16_verdict.json` — computed under the rule
that was in force when the prediction was registered. The re-run was reverted. Had the
order been the other way round, **a pre-registered result would have been read through a
rule that changed underneath it**, and nothing in the output would have said so.

### The Hebbian weight cannot be a better selector, and that is a proof, not a measurement (2026-08-27, `_analyze_hebbian.py`, zero tokens)

`policy.py` updates `w ← (1−DECAY)·w + LEARNING_RATE·δ` with δ = +0.5 if the paradigm was
best on that task and −0.3 otherwise. That is an exponential moving average of `was_best`
— **a recency-weighted win rate.** And `theta_assertions` already ranks by the win rate,
unweighted.

**At the fixed point, for a constant win rate p:**

```
w* = η·(0.5p − 0.3(1−p)) / DECAY = 0.1(0.8p − 0.3)/0.05 = 1.6p − 0.6
```

Strictly increasing in p over the unclipped range. **A monotone transform of the same
statistic cannot change an argmax.** So the recorded "all three selectors pick identically"
(0.5263 for weight, mean utility and win rate) is not an empirical coincidence and not a
mistuned hyperparameter — it is *forced*. The only place the two can differ is the
**transient**, which requires the estimated quantity to be moving.

**And it IS moving.** Best paradigm per region, across corpora: **4 of 5 comparable
regions change winner (80%)**. `many/oracle/loose/flat` runs `dag_strategy` →
`dag_strategy` → `dag_strategy` → `rewoo`; `many/oracle/tight/flat` starts at `direct` and
becomes `dag_strategy`. P15's verified mechanism said the same thing from another angle:
`dag_strategy`, dominated by `react` out-of-window in the prior record (P4), became the
best fixed on seed 47.

**But the current parameterisation cannot track it, and the reasons are specific:**

- below p ≈ 0.375 the weight pins to the floor 0.01, so **every weak arm becomes
  indistinguishable from every other weak arm** — the moment an arm is demoted it loses
  its ordering information entirely;
- climbing off the floor costs ~5 consecutive wins to reach a mid-range value, so the
  tracker **lags exactly when it should lead**;
- 140 episodes over ~22 (region, paradigm) keys is ~6 updates per key against an EWMA
  horizon of ~1/DECAY = 20. **The estimator never leaves its prior.**

Fitting both estimators on the same episodes in the same order and selecting on
`gold_transfer`: **identical, +0.0000.** Not for want of drift — for want of an estimator
that can see it.

**The only job the mathematics leaves it: a non-stationarity DETECTOR.** Where the weight
and the win rate disagree about the best arm, the region is in transient — and the right
action is not to route differently but to **lower confidence and abstain**, which is
machinery the product already has. Today that fires on exactly 1 region, and that region
does flip. **n=1 is an anecdote, not evidence**, and it is recorded as one.

**Two directions worth more than the repair (author's, 2026-08-27), and why.**

1. **Hebbian over tool-call ORDER, not over paradigms.** This restores what makes Hebbian
   learning distinctive and what the current use throws away: **association between pairs**.
   A (tool_i → tool_j) transition weight is not a marginal statistic of one arm, so the
   monotonicity proof above simply does not apply to it. It also aims at the right target:
   a paradigm mechanically *is* a policy over tool-call sequences, and paradigm choice
   predicts evidence recall at 60% out-of-sample — so the call order is the channel the
   dominant lever acts through. Learning it attacks that 60% instead of picking among five
   pre-baked orderings. **Blocked on instrumentation**: `tools.py:375` keeps
   `calls[name] += 1`, a count dict with no sequence. The order is not logged, so the idea
   is not yet testable — which makes logging it the cheap first step.

2. **Learned associations as beliefs — yes, with one constraint that must not be waived.**
   The lattice is `ASSUMED < ELICITED < OBSERVED < COMPUTED`, and irreversible actions
   require `COMPUTED`/`OBSERVED` precisely to keep statistics and opinion out of them. A
   learned association is arithmetic over a ledger, so it *looks* COMPUTED — and if it
   entered at that rank, a statistical regularity could gate an irreversible action, which
   destroys the reason the floor exists. A learned association is not an observation about
   THIS request; it is a prior over requests like it. So it needs a rank strictly below
   OBSERVED, and the lattice has no slot for it today. Naming that gap is worth more than
   papering over it.

### Evidence recall dwarfs the paradigm gap (2026-08-27, `_analyze_retention.py`, zero tokens)

The pending "context retention" item asked whether a paradigm's advantage survives
controlling for how much evidence it actually got. Retention proper — how much of what
was retrieved survives to the answering call — is **not instrumented**, and is not
claimed here. What the paid rows already carry is the first link in that chain: evidence
**recall**, the fraction of the units that actually bear the answer that the paradigm
read. `relevant_units` is declared per task; `relevant_units_read` is logged per row.

**The headline needs no conditioning at all — it is two means over the same cells:**

| corpus | full-recall cells | mean utility, full recall | partial recall | gap | largest paradigm advantage | ratio |
|---|---:|---:|---:|---:|---:|---:|
| `gold_transfer` | 29/90 | 0.869 | 0.336 | **+0.533** | 0.126 | **4.2×** |
| `gold_deep` | 19/55 | 0.763 | 0.261 | +0.502 | 0.357 | 1.4× |
| `gold_v2` | 9/48 | 0.607 | 0.218 | +0.388 | 0.391 | 1.0× |
| `gold_holdout` | 3/16 | 0.565 | 0.194 | +0.371 | 0.234 | 1.6× |

On `gold_transfer` — the production regime, out-of-window, five structured paradigms, and
the corpus P15 ran on — **the difference between reading all the evidence and not reading
it is 4.2× the largest difference between paradigms.** The older corpora sit near 1×, and
that is not a contradiction: they include `direct`, whose advantage IS a recall advantage
(everything fits in the window, so it reads everything by construction). The ratio
collapsing exactly where a paradigm's edge is known to be retrieval is the story, not an
exception to it.

**The obvious objection, answered before anyone raises it.** If the full-recall cells
were all C1, the gap would be task difficulty wearing recall's clothes. Stratifying by
cell decides it, and the gap **survives inside every stratum that has both groups** —
so it cannot be the stratum:

| cell | n full | u full | n partial | u partial | gap |
|---|---:|---:|---:|---:|---:|
| C1 single | 4 | 1.000 | 6 | 0.667 | +0.333 |
| C2 bulk | 7 | 0.839 | 14 | 0.656 | +0.183 |
| C3 chain | 0 | — | 8 | 0.000 | no full-recall cell exists |
| C4 aggregate | 9 | 0.815 | 8 | 0.417 | +0.398 |
| C5 horizon | 5 | 0.800 | 21 | 0.079 | **+0.721** |
| C7 irreversible | 4 | 1.000 | 4 | 0.583 | +0.417 |

And it comes back stronger than it went in. The gap is **largest on C5 (+0.721)** — the
exact cell where P15's routing lost the most (−0.278). On the cell that decided the
refutation, reading the evidence is worth more than anywhere else in the corpus, and the
routing decision was being made without knowing whether the evidence would be read.
C3 has no full-recall cell at all and scores 0.000 across the board, which is the same
oracle-zero region already on the record — stated rather than averaged away.

**The suggestive part, reported as an indication and not a verdict.** Restricting to
cells that read ALL the relevant evidence, `dag_strategy` — the best fixed paradigm, the
one P15's routing lost to — goes from **+0.083 to −0.040**. Its advantage changes sign.
Read plainly: it was not better at solving, it was better at finding.

**Why that second reading is weaker than the first, stated rather than buried.** Recall
is not a pre-treatment covariate; it is a CONSEQUENCE of the paradigm. Conditioning on a
post-treatment variable does not yield an unbiased direct effect and can open collider
bias — a clumsy paradigm's full-recall cells are the easy tasks, while a good one's
include hard ones. So the magnitude comparison stands on its own (two means, same cells),
and the sign flip is a lead to chase, not a result to cite.

**Then the question that decides whether any of this is actionable: WHO determines
recall?** Three candidates with opposite consequences. If the TASK does, it belongs to
the world and there is nothing to decide. If the REGION does, the decision layer already
sees it and can route on it. If the PARADIGM does, then choosing a paradigm IS choosing
how much evidence gets read.

| what | share of recall variance | groups |
|---|---:|---:|
| region — what the decision SEES | **5.2%** | 5 |
| paradigm — what the decision CHOOSES | **62.2%** | 5 |
| region × paradigm | 82.7% | 22 |
| task — what the world contributes | 10.5% | 21 |

**The paradigm determines recall six times more than the task does.** So routing is not
arbitrating at the margin of the dominant variable — it is the **main lever on it**. That
rescues the routing program rather than undermining it, and it reframes what routing is
FOR: not "pick the structure that reasons better" but **"pick the structure that will
actually read the evidence."**

**And the 5.2% is the problem.** Inside every region recall runs the full range, 0.00 to
1.00. The router holds the main lever on the main variable and pulls it nearly blind,
because φ's region barely predicts where it matters. That is the same shape as P15's
verified mechanism — a decision made without an axis for the thing that decides the
outcome — arriving from a completely independent direction.

*Read with care*: these are marginal shares over unbalanced groups; they do not sum to
anything and region and paradigm are not orthogonal. The 22-group number is inflated —
at ~4 points per group part of that 82.7% is fit, not structure. The two that carry the
argument are 5 groups each, and it is their CONTRAST that says something.

**What it changes.** The probe exists to turn an unseen variable into an observed one,
and today it senses **coupling**. The measurement says the variable worth sensing is
whether the evidence will be found. That is a product direction with a number behind it,
and it is not implemented — so it is registered as debt, not written into the paper.
It is also a caution for P17: a selection rule that finally fires is choosing on a
belief unrelated to the largest source of variance in the outcome.

### P17 registered (2026-08-27, before any number exists)

The three pieces P17 needed are built. Two are code and are done; the third is the
corpus, and it now exists.

**The corpus: `gold_p17`, seed 73, `--honest-detectors`.** 26 tasks, verified
independently from the documents (`corpus/verify.py`: PASS on all six cells). Gold is
present on all 26 — grading is untouched, and must be: a corpus the bench cannot grade
measures nothing. What changed is what the DECISION is told. `has_oracle` stopped being
a synonym for "the bench holds an answer key" and became the claim it was always named
for: **a cheap runtime detector exists here.** That is true only where verifying is
cheaper than solving:

| cell | detector | why |
|---|---|---|
| C1 single verifiable | yes | one fact: look at it and you know |
| C7 irreversible | yes | a trigger is present or it is not |
| C2 bulk independent | **no** | "list every X": verifying completeness IS the task |
| C3 coupled chain | **no** | checking the endpoint means walking the chain |
| C4 aggregate | **no** | verifying the count requires the count |
| C5 unknown horizon | **no** | knowing when to stop is the question |

Result: **6 of 26 tasks carry a detector, 20 do not.** Under the old regime it was 25 of
26 on every corpus in the record. The table is a claim about the world, not a knob: a
deployment that can cheaply check a list is a deployment with an index nobody has, and
declaring one anyway puts the cascade in front of every decision and calls the result a
routing measurement. A cell with no declared detector raises rather than defaulting to
`True` — the default was the whole bug.

**The prerequisite is TWO sites, not one — and finding that out is why it was
simulated before it was paid for.** The obvious one is `features.py:214`, which builds
the region segment. The load-bearing one is `rules.py:248`, which builds the belief
`oracle_available` — and the belief is what the cascade rule actually reads. A first
simulation overrode only the region and reported *no change whatsoever*, which was the
correct answer to the wrong question: relabelling a region does not change what a rule
believes. Both derive from `bool(task["oracle"])`, so both change together.

Neither is applied yet. Applying them mid-run would change what P16's frozen analyzer
computes on 2 of its 26 tasks (the empty-oracle C2 tasks, where the corpus declares a
detector and the gold list is empty), and re-reading a pre-registered verdict through a
rule that changed underneath it dissolves the only thing pre-registration buys. They
land the moment P16's verdict is recorded, and P17 runs after.

**P17a: CONFIRMED offline, zero tokens (`_analyze_p17_mechanism.py`).** The question
"which rule decides" is fixed by priority and features, not by the model, so it is
answerable before spending anything — and worth answering first: a corpus that does not
change which rule fires cannot measure what P17 says it measures.

| regime | cascade | gate→fallback | probe→decide | defer→fallback |
|---|---:|---:|---:|---:|
| `gold_p17` as P16 runs it | **22** | 4 | 0 | 0 |
| `gold_p17` honest | **2** | 4 | **14** | 6 |
| `gold_p16` (either) | 20 | 4 | 1 | 1 |

Cascade falls from 22 to 2, well inside the ≤ 6 predicted — tighter than predicted,
because C7's four irreversible tasks are taken at priority 100 by the gate before the
cascade at 90 ever looks. So C1's two tasks are the entire cascade, which is exactly the
claim the detector table makes: those are the two cells where verifying is cheaper than
solving.

That also sharpens P17b into a real gamble rather than a formality. **14 tasks now wait
on the probe** and are the only place selection can come from; the 6 that defer are
already decided (θ has no confidence there, which is abstention working). So P17b needs
at least 7 of those 14 to come back `specialise` after the probe resolves. It can fail,
and the way it fails is informative: margin 0 for want of episodes is the
distribution-shift story below, while margin 0 with episodes present is a statement
about the signal itself.

**Predictions, registered 2026-08-27 before the run.**

- **P17a (mechanism, computable offline). CONFIRMED — 2 of 26, table above.** On
  `gold_p17` with the prerequisite applied, the cascade rule fires on at most 6 of 26
  tasks — only the declared-detector cells — against 22 of 26 on the same corpus under
  P16's regime. Falsified if it fires on more than 6.
- **P17b (the claim).** With the probe resolved and its cost charged, the selection rule
  `specialise_when_theta_is_confident` DECIDES on at least 7 of the 20 no-detector tasks.
  Today it decides on 0 of 26, and has for the entire investigation. Falsified below 7.
- **P17c (the product claim).** The net oracle gap of the routed ACTION against the best
  fixed paradigm is positive and outside the per-cell noise floor. This is the registered
  criterion P15a failed; P17 is its first honest re-test, because P15a was scored in a
  regime where the rule under test could not fire.
- **P17d (reproducibility).** Replicate utility identical on 26/26 tasks, as P15d and
  P16d were.

**A risk that belongs in the record, not in a footnote.** θ is fitted on corpora whose
regions were computed under the old rule, so the `oracle`/`no_oracle` segment of a
region means something different in the training record than it will at decision time
on `gold_p17`. That is a genuine distribution shift and it cuts against P17b: θ may have
no statistics at all in the regions the honest corpus lands in, which is abstention, not
selection. If P17b fails that way — margin 0 for want of episodes rather than for want
of a signal — the honest reading is that the corpora must be REBUILT under the honest
rule before selection can be measured at all, and that is a cost to state now rather
than discover afterwards.

**The bench cannot measure selection, and the reason is structural (measured,
2026-08-27).** Chasing why θ never specialises produced a second, independent cause, and
this one is not a tuning problem:

| rule | priority | fires when |
|---|---:|---|
| `irreversible_requires_gate` | 100 | the task declares an irreversible action |
| `verifiability_partition` (cascade) | **90** | **a cheap oracle exists** |
| `probe_before_deciding_on_bulk` | 80 | many units, coupling unmeasured |
| `specialise_when_theta_is_confident` | **70** | θ has a margin above τ |

And every corpus in the bench carries an oracle on ~96% of its tasks — `gold_transfer`
25/26, `gold_deep` 25/26, `gold_v2` 38/39, `gold_p16` 24/26 — because a task without gold
cannot be graded by exact match, which is what makes the bench judge-free in the first
place.

So on 96% of every corpus, the cascade rule fires at priority 90 and
`specialise_when_theta_is_confident` is **never even evaluated**. The mechanism under
study cannot run on the bench that was built to study it. **The property that makes a
task measurable — a cheap oracle — is the same property that makes escalation the right
call, and it pre-empts selection by design.**

This is the same conflation the handoff flagged from the other end (`CIERRE` §3.8.2:
evaluation gold and the runtime cheap verifier are one field, `oracle`), and here is its
measured consequence: they must be separated not for tidiness but because their conflation
makes selection untestable.

It reframes everything above rather than replacing it. P15 did not measure "learned
routing loses to a fixed default"; it measured the cascade and the gate, with selection
switched off by rule priority on 25 of 26 tasks. E2's identical results have the same
explanation: neither router was routing. The three findings — margin zero, region
fragmentation, oracle pre-emption — are three views of one fact.

**Fixed and measured, opt-in (the router is NOT touched for P16, which is mid-run):**
hierarchical accumulation (`Plasticity.candidate(hierarchical=True)`, each episode also
indexed into its ancestor regions) plus region backoff
(`Router(region_backoff=True)`, a thin region defers to its parent and **returns which
level answered**, because an assertion from a coarser bin is a weaker claim). Effect on
the held-out record: **tasks with margin > 0 goes from 0/26 to 16/26** (levels: 6 answered
at 4 segments, 12 at 3, 5 at 2, 1 at 1, 2 at none). Utility is unchanged at −0.0112 —
because of the priority pre-emption above, which no amount of confidence can get past.

What P17 needs, and it is now specific: **a cohort of tasks with gold for grading but no
runtime oracle**, so the cascade cannot fire and selection has to carry the decision.
Until that exists, no run on this corpus family can confirm or refute the selection claim,
and the honest record says so instead of reporting a number that measures something else.

**Statistics (free, `_analyze_statistics.py`, paired bootstrap over TASKS, 10k
resamples, fixed seed) — and it corrects a reading.**

| Contrast | mean | CI95 | p |
|---|---:|---|---:|
| P15 valuation vs best fixed | −0.0874 | [−0.2284, +0.0367] | 0.190 |
| P15 valuation vs always-`react` | +0.0353 | [−0.1327, +0.2020] | 0.665 |
| action-aware vs best fixed | −0.0112 | [−0.1214, +0.0905] | 0.891 |
| action-aware vs always-`react` | **+0.1116** | **[+0.0014, +0.2382]** | 0.045 |

**Correction to how P15a is stated.** The pre-registered criterion used the per-cell
noise floor and the verdict against it stands: −0.087 is beyond ±0.057, so P15a fails its
own registered test. But the *sampling* interval over 26 tasks includes zero (p=0.19).
Those are two different uncertainties — measurement noise and sampling noise — and the
record carried only the first. Both are now reported: **P15a is refuted against its
registered criterion and is not established in either direction by a 26-task interval.**
Under Benjamini-Hochberg (q=0.05, m=4 contrasts that have p-values) **no contrast
survives**, the +0.045 one included. Threshold judgments (feasibility arithmetic, 26/26
reproducibility) are excluded from the correction on purpose: they are not tests, and
folding them in would invent precision.

**θ never specialises on this record — and the continuation axis is why (measured).**
AURC came out exactly 0.00000, which is degenerate, and the cause is not the curve: θ's
margin is 0.0 on all 26 tasks. `MIN_EPISODES_FOR_CONFIDENCE = 8`, and:

| region vocabulary | regions | max episodes in a region-paradigm cell | tasks with margin > 0 |
|---|---:|---:|---:|
| `regions/1` (3 segments) | 3 | 10 | 12 / 26 |
| `regions/2-continuation` (4 segments) | 5 | 7 | **0 / 26** |

Adding the discriminating axis **fragmented the region space below the confidence
threshold**: θ went from specialising on 12 of 26 tasks to never specialising at all.
This is the bias–variance trade in its plainest form — a more expressive vocabulary costs
statistical power, and at this record size the cost exceeds the benefit.

Two consequences, recorded BEFORE P16's numbers exist:
1. It explains E2 mechanically. Two routers that disagree on 26/26 tasks give identical
   utility because **neither was specialising**: the decision came from the gate, the
   cascade and the default in both cases. "Learned routing loses to a fixed default" was
   never what P15 measured — what it measured is a policy with no confident region
   falling through to its governance rules.
2. **P16 is running under `regions/2`, so it will measure that same regime.** Its frozen
   verdict stays frozen — the router is NOT being touched mid-run — and the limitation is
   written here before the numbers land. The fix belongs to a P17: hierarchical backoff,
   where a 4-segment region with too little evidence falls back to its 3-segment parent
   instead of asserting nothing. That keeps the axis where it has support and keeps the
   power where it does not.

**E2 — θ against a trivial learned arm on the same φ (exploratory, free,
`_run_e2_learned.py`).** The reviewer's cheapest attack, answered: a ridge regression
(72 parameters, closed form, no seed) trained on the same 140 cell episodes and seeing
exactly what θ sees. Scored the way P15 scored, **the trivial arm routes BETTER than the
whole deterministic machinery**: −0.047 vs −0.087. But wrapped in the same action
machinery both land on **exactly −0.0112 — while agreeing on 0 of 26 tasks.**

The mechanism, verified: **21/26 tasks fire the cascade**, and a cascade with an oracle
climbs the whole ladder, so the rung it STARTS from cannot change quality — 9 of those
21 exhaust the ladder with no hit, and the rest find the same winner from either start.
Two routers that disagree on every single task produce identical utility because, where
the cascade fires, **the choice is not what produces the value; the action structure is.**

Two consequences, and neither is comfortable:
1. The routing claim, on this corpus family, is largely a claim about the CASCADE, not
   about selection. §5.2's cascade dominance result is doing the work that §5.1's
   selection theorem was credited with.
2. The only surface where selection can still pay is **cost** — start at the right rung,
   stop earlier. Measured: climbing from cheapest costs 2.24M tokens on those tasks
   versus 2.49M for always-`dag_strategy`, so the cascade is already ~10% cheaper than
   the best fixed. That makes P16's λ sweep the decisive measurement of the whole
   programme, not a robustness check.

**Decomposition of the −0.087 (exploratory, post-registration, same corpus —
`_analyze_p15_decomposition.py` re-derives all of it).** Three mechanisms, in order:
(1) the **continuation axis** — literal key recurrence across distinct units, a pure
function of the material, COMPUTED — separates C5 perfectly in all three corpora (6/6,
zero false positives on C1/C2/C4) and is now the 4th region segment
(`REGION_VOCABULARY = regions/2-continuation`); alone it moves nothing (−0.0874
unchanged): necessary, not sufficient. (2) The regime confound (mixing in-window gold_v2
into training) is NOT the cause: out-of-window-only training gives the same number.
(3) What moves it is **scoring the real action** (handoff finding 3.9.1): C5 carries an
oracle, so the cascade rule fires, and `plan.paradigm` scores only the FIRST rung of a
ladder the product would climb. Action-aware scoring: net **−0.0112, inside the noise
floor**, with C5 at parity and C2/C4 positive. The residual is ENTIRELY C7 (−0.333):
irreversible tasks where the gate runs the fallback by design — the remaining deficit is
the priced cost of governance, not a routing error. Caveat P16 must close: this scoring
does not yet charge the cost of climbing (the full ladder measured 4.4× in the cascade
study) nor detector sensitivity < 1.0 (catastrophic in that same study); P16
preregisters action-aware valuation WITH cost.

**What this changes.** The product claim as registered — per-request selection beats the
best fixed paradigm on an unseen world — is false for θ over these features on this
world, and the honest headline is the mechanism: **selection without sensing loses to a
strong fixed default**. The result survives as the measured price of deciding blind on
one axis; the follow-up (exploratory, NOT registered: it is the same corpus) is to rerun
the decision pass with the probe supplying coupling/horizon and measure how much of the
−0.087 that recovers.

**Refutation is the point.** P15a failing is publishable and cheap to state: it would mean
the honest result is a measured catalogue of when each paradigm wins, plus a negative
result on selection — which is more than the literature currently offers for held-out
routing, and it would be known before anything was built on top of it.

**Registration note**: P8/P9 were registered under `gpt-5-chat`; the model switch is a
later decision, recorded here. The chat grid freezes as the first-model study (its †
cells stand documented); nano results live in `results/nano/` and are never pooled with
chat rows.

---

## Findings so far

Two corrections that came out of measurement rather than reasoning, both recorded
because they are the reason the harness exists:

1. **The first generated corpus had silently wrong answers.** Amendment units were named
   `memo-NNN-alt`, which matched the `memo-` prefix scan, so every task built after the
   first C5 task had its unit list shifted and its oracle quietly became incorrect.
   Nothing crashed. Hence `corpus/verify.py`, which re-derives every oracle by parsing
   the documents with no access to the generator's state.

2. **The Cascade Dominance claim was overstated.** It said the cost bound was
   `cost(p_1)`. Measured: when no rung satisfies the oracle the cascade runs the whole
   ladder — 100% of the gap captured at **4.4x** the cost. And with detector sensitivity
   0.6 the captured fraction goes to **-5.98**, so a weak detector is catastrophic rather
   than merely suboptimal. The pattern now requires a budget cap.

3. **Candidate screening verdicts (2026-08-27, `gpt-5-chat`, gold_deep).**
   **P10a falsified**: `graph_traverse` scored u=0.0 on both coupled cells — "Not
   found" after paying a ~280k-token entity index and reading 4/48 units. Chains in
   this corpus are not entity adjacency; P10b is moot. **P11/P12 unevaluated by
   decision**: the feasibility gate rejected `extract_compute` (~580k projected vs a
   60k declared budget) and `streaming_scan` before the first token, and the author
   ruled that under the production budget the infeasibility IS the screening result.
   **P14a falsified, P14b confirmed**: `pointer_chase` never touched a relevant unit —
   the single retrieval seed is the weak link (it anchored on memo-023 where the chain
   was memo-000→001, and on memo-045 where it was 008→010→011), so the text-visible-
   pointer thesis went untested. The brakes all held: stopped at the hop cap, zero
   hallucinated pointers, and replicates identical in path and within 0.1% in cost —
   **a code-driven loop removes the cost lottery**, a mechanism result that survives
   the pattern's death. The reframing find: `react` solves those cells at u=1.0 for
   ~10-14.5k tokens, cheaper than the chase — on `gpt-5-chat` deep coupling already
   has a cheap solution. The genuinely open region is **C3-deep on nano**, where the
   entire grid scored u=0.000.

4. **Structure vs judgment held on the second model (P13a-c, 2026-08-27,
   `_analyze_p13.py`, 98 shared cells).** P13a: 12/15 structure cells hold (Δu ≤
   0.25); all 3 breaks are `direct` on judgment-heavy cells (h3, C5) — having the
   whole evidence in-window is not structure enough when synthesis needs judgment
   (direct-nano holds h1/h2 and breaks at h3). P13b: react degrades on 10/14 feasible
   cells, reflection 8/13, dag_strategy 7/13 — with the directional surprise that
   nano IMPROVES on C2 decomposition cells (plan_execute 0→0.56-0.76): the small
   model self-destructs less when decomposing. P13c: replicate utility identical on
   73/81 cells (90.1%) — above the bar, but the per-cell noise floor stays mandatory.
   Routing consequence: coverage (C2/C4) is routable to nano via structured paradigms
   at nano price; model downgrade on deep C3/C5 is prohibited by evidence. Caveat
   recorded in `notes/`: the graph_traverse disk index is keyed by corpus only, so
   the nano rows reused the chat-built graph — irrelevant here (falsified on both),
   but any surviving index-bearing candidate must key its memo by model fingerprint.
