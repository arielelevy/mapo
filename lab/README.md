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
| Infrastructure failures (429s) are excluded from every statistic | — |

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
  paradigms/     direct, cot, react, map_reduce, plan_execute, reflection
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
py -m pip install -r requirements.txt
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
| P1 | Feasibility pruning: on the three large corpora, every task whose required evidence exceeds the allowance leaves `direct`/`cot` infeasible by arithmetic, recorded at zero cost; on `gold_xl` the pruning also reaches full-coverage cells for paradigms whose projection exceeds the budget | The feasibility check is wrong or the corpora do not leave the window — the regime claim collapses |
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
