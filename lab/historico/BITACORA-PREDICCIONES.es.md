# Bitácora de predicciones y veredictos — lab

> **Qué es esto.** El registro completo de predicciones falsables, con fecha, **anotadas
> antes de correr**, y sus veredictos. Estuvo hasta el 2026-08-29 adentro de `README.md`,
> donde ocupaba 1.400 de sus 1.687 líneas y hacía que el README no se pudiera leer.
>
> **No está acá por obsoleto.** Es lo contrario: es la evidencia de que las predicciones se
> escribieron ANTES de ver el número, que es lo único que separa una predicción de una
> explicación. Se mudó porque un README describe el estado actual y esto es una cronología.
>
> **Sigue siendo canónico.** El paper cita de acá. Nada se edita retroactivamente: un
> veredicto que refutó una predicción se queda escrito con la predicción al lado.
>
> El estado vigente —qué se sostiene hoy— está en `../README.md`. Lo que falta, en
> `../PENDIENTES.es.md`.

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

### Registered predictions — P27, the model as an arm (2026-08-28, before running)

Two questions, and they are not the same one:

| | | |
|---|---|---|
| **substitution** | `luna` costs the **same per token** as `nano` | if it is better, there is no routing decision to make — swap the cheap one and stop |
| **routing** | `terra` costs **9.8×** | if it wins, it wins where the task is hard, and *that* is what region-based routing has to learn to detect |

Run on the **8 tasks of 32 that discriminate** — those where nano's best arm scores `u < 1`.
A task nano already solves distinguishes nothing; all three would score 1.0. Arms: `rewoo`
(cheapest at 2,642 tok/cell *and* highest utility on these tasks at 0.242) and `react` (the
fallback). `dag_strategy` is excluded: 102,766 tok/cell to answer a question about the
**model**, with the paradigm held constant.

| | prediction | falsified if |
|---|---|---|
| **P27a** | `luna` beats `nano` by **less than the per-cell noise floor**. Same price class, same family lineage — the generation bump alone should not move a corpus this small | it wins clearly, which makes it a **free substitution** and retires the routing question for the cheap tier |
| **P27b** | `terra` beats `nano` on the **`piso` tasks** (u=0 for every nano arm) more than on the **`margen`** ones. Capacity should show up where nothing worked, not where something half-worked | the gain is flat across both, which would mean it is not capacity but variance |
| **P27c** | **net of price, `terra` loses.** At 9.8× it needs to recover ~0.54 utility per cell to pay for itself at λ=0.03, and the recoverable ceiling on these tasks is smaller than that | it wins net, which would be the strongest result available and would justify the expensive tier outright |
| **P27d** | `terra` emits **reasoning tokens on every cell** and `nano` emits **zero**, so the token comparison and the money comparison **disagree in direction at some λ** | they agree everywhere, which would mean reasoning output is negligible and the "same price per token" comparison was fair after all |

**P27d is the one that matters for the accounting**, not for the models. Reasoning tokens
bill as output and the model decides how many to spend. If they move the verdict, then every
cross-model cost comparison in this repo has to be in money on the cell meter — never in raw
tokens.

**And the decoding differs on purpose.** `nano` ran at `temperature=0` and replays that way;
the `5.6` family are reasoning models and forcing 0 can be rejected, so it is omitted — and
the **omission goes into the fingerprint**, so the two are never pooled. That is `load_rows`
refusing to average across decodings, working as designed.

---

### Registered predictions — P28, the dynamic supervisor (2026-08-29, before running)

`supervisor` is the third member of the sub-agent family and the one the catalogue was
missing. `dag_strategy` fixes its plan before executing; `handoff` fixes its scopes in
code; here **the calls are not decided in advance** — the supervisor reads what came back
and only then dispatches the next one, or stops. Each sub-agent gets a **window over the
material** (`SUB_SCOPE_UNITS = 8`, carved by a search over its own sub-question), not the
whole scope: context isolation is not an optimisation of this pattern, it is its
definition.

| id | prediction | what would falsify it |
|---|---|---|
| **P28a** | it beats `react` on the **coupled** cells (C3) by **≥0.05** utility: a chain whose second hop lives in a unit the first search never surfaced is exactly what a second dispatch is for | it does not, which means dispatching again buys nothing that one agent with more turns would not also get, and the pattern is `react` with a coordination tax |
| **P28b** | it does **not** beat `react` on C1 — one fact, one unit — and costs **more** there: with nothing to decompose, the coordination call is pure overhead | it wins on C1 too, which would mean the gain is not decomposition but something else, and the mechanism claim is wrong |
| **P28c** | its **reread** rate is **lower** than `dag_strategy`'s: scoped sub-agents cannot re-read what is not in their window, whereas dag's branches all range over the full scope | its reread is equal or higher, which would mean the window does not bind and the scoping is decorative |
| **P28d** | **reproducibility**: same task, same seed, same decode ⇒ identical dispatch sequence, 26/26 | any divergence, which would put every number above inside the noise of the supervisor's own choices |

**P28a is the one that matters.** The whole reason to pay a coordination call is that
seeing the first result changes what you ask next. If that is worth nothing on the cells
built for multi-hop, dispatching dynamically is a more expensive way to do what a fixed
plan already does — and the family collapses back to its two known members.

**P28c is the one that could embarrass the design.** It is the only prediction here that
the scoping mechanism makes directly, and it is measurable without any oracle.

---

### Registered predictions — P26, HyDE as a fused branch (2026-08-28, before running)

`hybrid_hyde` asks the model for a **hypothetical answer** — what the passage answering the
question would look like, in the corpus register — and ranks densely with *that* instead of
with the question. The bridge it crosses: the question says "settlement account for Valerio"
and the document says "AC-7741, holder Valerio Simoni, role custodian". A question vector
and a document vector sit far apart; a hypothetical-answer vector sits close, because it has
the document's shape.

**It is an arm, not a tool** (`H-1`). A tool is called by the model, which puts control flow
on the sensor's side. As a retrieval arm the run configuration decides, so it is
deterministic in who chooses, registrable, and comparable against the arm without it.

**It is fused, not substituted.** A hypothetical answer can be well-imagined and false — the
model invents an account that does not exist — and then its vector points at documents that
are similar and wrong. RRF makes that error **beat** the base ranking rather than replace
it, the same logic by which `hybrid` fuses lexical and dense instead of picking one.

| | prediction | falsified if |
|---|---|---|
| **P26a** | recall of answer-bearing units rises **≥5pp** over `hybrid` on the cells where the question's wording and the document's differ (C2, C4) | it does not, which retires HyDE for this corpus |
| **P26b** | on C1 — one fact, one unit, wording already close — the gain is **≤1pp**: there is no gap to bridge | it gains there too, which would mean the effect is not the semantic bridge but something else, and the mechanism claim is wrong |
| **P26c** | **net of its own cost**, at λ>0, `hybrid_hyde` does **not** beat `hybrid` for the cheap arms: one generation per distinct query is a fixed tax that a 2,435-token `rewoo` cell cannot amortise | it wins net for `rewoo` too, which would make HyDE unconditionally worth it — a stronger result than predicted |
| **P26d** | the ranking of paradigms is **unchanged** by the retrieval arm: retrieval quality shifts everyone's level, not their order | the order changes, which would mean "the best paradigm" was partly an artefact of retrieval quality — and would retire every cross-arm comparison made so far |

**P26d is the one that matters, and it is the honest baseline `AR-4` asked for.** Every
paradigm comparison in this harness ran under one retrieval arm. If the order is
arm-dependent, the comparisons are conditional on a constant nobody varied. Predicting *no
change* is predicting that the existing results survive — and it is the prediction that
would hurt most to lose.

**Charged, not free** (`H-3`). Before today the row billed `result.usage`, which is what the
paradigm remembered to add up. That equals the cell meter only while **all** spending goes
through the paradigm's own calls — true until a retrieval arm started calling the model.
`hybrid_hyde` generates one hypothetical per distinct query and that spend is invisible in
`result.usage` **by construction**: the paradigm never saw it. Billing it wrong would not
make HyDE look slightly better — it would compare a **free** retrieval against a **paid**
one and call the difference "better". The row now bills the cell meter and records
`retrieval_tokens` separately.

> And a check that was already failing quietly: the **error** path already used the meter.
> So a cell that crashed was billed correctly and a cell that worked was billed short.

---

### Registered predictions — P25, absence and presupposition (2026-08-28, before running)

Two obligations the harness never had, each with a cell, a verifier, and a typed contract.
The factor `demand_obligations` is off by default: asking for the declarations changes the
prompt every arm reads, so its rows are not comparable with the rows measured so far.

**B2 — absence.** The worst harm/attention ratio in the family. An absence asserted from a
sample produces an answer that **looks normal**: "no memo covers X" reads just as confident
after 3 units as after 40. A presence error collapses on its own — the reader looks for the
fact and it is not there — and an absence error leaves no trace, because there is nothing to
look for. The rule is the asymmetry: **presence needs one witness, absence needs the whole
domain**.

**D1 — presupposition.** "On what date did X transfer the account?" takes for granted that
a transfer happened. If none did, **every** answer to the question as asked is false,
*including* "no date is recorded": declining the datum ratifies the premise as surely as
supplying one.

| | prediction | falsified if |
|---|---|---|
| **P25a** | with the contract OFF, arms assert absence having read **<50%** of the scope on the majority of B2 tasks | they read the domain anyway, which would mean the caution was already there and the contract buys nothing |
| **P25b** | with the contract ON, `absence.emitted` falls — **fewer answers are issued**, and that is the contract working, not a regression | emission does not fall, which would mean the declaration is being made without changing behaviour |
| **P25c** | on D1 with the contract OFF, the majority of arms **answer the question** — supply a date or decline the date — rather than reject the premise | they reject it unprompted, which would retire the contract |
| **P25d** | `direct` is **not** better at either than the search-driven arms; the failure is one of obligation, not of context | it is better, which would mean the obligation is really a retrieval problem |

**And a limit stated before the run, not after.** B2's absent roles come from `ABSENT_ROLES`
— legitimate names from the same vocabulary that the generator never assigns. The first
version looked for a role from `ROLES` that nobody in scope held, which works at width 12
and **disappears at width 40**: with enough people all five get instantiated. That would
have confined the absence cell to the small regime — the one the product does not target,
and the one where the failure matters least. Asserting an absence over 12 units is less
reckless than over 400.

---

### Registered predictions — P24, terse tool descriptions as a FACTOR (2026-08-28, before running)

Tool descriptions are **1,167 of the 2,135 characters** of the spec payload — 55%. Cutting
them looks like free savings and is not: the description is the ONLY thing the model reads
to decide WHICH tool to call, so shortening it can change the choice. It enters crossed,
`{terse, verbose} × {paradigms}`, never folded into a paradigm.

The terse form keeps what **discriminates** — what each tool returns, and when one beats
another — and drops the prose that instructs on good usage. That prose is prompt
scaffolding, and this harness already measured that prompt scaffolding buys nothing.

| | prediction | falsified if |
|---|---|---|
| **P24a** | the spec payload shrinks **≥30%** | it shrinks less; measured before running: **38.4%** |
| **P24b** | total prompt tokens fall **<4%** | they fall more, which would mean the spec was a bigger share than the 6.7% measured |
| **P24c** | utility does **not** drop more than the per-cell noise floor | it does — and then saving tokens by choosing worse is not saving |
| **P24d** | the **distribution of tool choices** shifts measurably (`keyword_search` vs `semantic_search`) | it does not, which would mean the discriminating text was never what decided |

**And a decision about the run itself, made before spending.** At 2.57% of the prompt,
P24b's saving sits **below the per-cell noise floor of almost every cell measured**. A
dedicated run would pay to measure something it cannot separate from its own noise. So the
factor is implemented to **ride along** with a run commissioned for something else — never
to commission one. What that N *can* resolve is P24c and P24d, the risk side, and that is
the number the factor exists for.

---

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

### C8, the currency cell — registered 2026-08-28, before any run

**Why it did not exist, and why it costs nothing.** The corpus has carried amendments since
C5 was written, each with its precedence declared in fixed form — *"this filing supersedes
any earlier domicile on record for that account"*. Measured before building anything
(`_analyze_supersession.py`): **zero questions mention domicile, zero golds are an amended
value.** The material was there and served only as a distractor — costing tokens, dirtying
retrieval, measuring nothing.

C8 reuses the amendment C5 already plants, so the corpus grew by **32 tasks and zero
documents**.

**Same material, opposite demand — which is the point.**

| cell | question | what it tests |
|---|---|---|
| C5 | *"name the individual with contradictory city information"* | **detecting** the conflict |
| **C8** | *"what is the domicile currently on file for account X?"* | **resolving** it by precedence |

**And it separates two failures no other cell can.** Both values live in the material, so a
wrong answer says which failure happened:

- **another city entirely** → it never found the filing: a *retrieval* failure
- **the original domicile** → it found both and chose the superseded one: a **currency**
  failure, made *with impeccable provenance*, because the old memo does say what it says

Set F1 punishes the two identically and cannot tell them apart. The second is the one this
product exists to prevent.

**Registered predictions, written before a single row exists.**

- **P18a (mechanism).** A paradigm that reads every unit resolves the supersession; one
  that stops at the first match returns the superseded value. Falsified if the two classes
  are indistinguishable on C8.
- **P18b.** On C8, the *superseded value* is the single most common wrong answer — not a
  scatter of unrelated cities. Falsified if wrong answers do not concentrate there.
- **P18c.** C8 utility is **not** predicted by C5 utility on the same (idx, width):
  detecting a conflict and resolving it are different capabilities. Falsified if the two
  correlate above 0.7.

Ground truth is re-derived independently by `corpus/verify.py::_c8`, which also refuses a
task whose superseded value is absent from the material — without it, a wrong answer would
only mean "not found", which the other cells already measure.

### P23 registered (2026-08-28, before `handoff` has run) — the handoff, authorised by code

**What it is.** Agents with independent scopes and a transfer the **code** authorises. The
three frameworks surveyed — Microsoft Agent Framework, OpenAI Agents SDK, Google ADK — all
do the same thing: the handoff **is a tool the model calls**, `transfer_to_<agent>()`. That
is control flow decided by the model, which is what this product's invariant forbids.

Here the agent **proposes** —a typed proposition, `ELICITED`, because it is its reading—
and a deterministic rule authorises: the string it says it cannot resolve must appear
**verbatim** in a scope that has not run yet. That second half is `COMPUTED` over the
material, and it is what makes the transfer reproducible.

**And a lesson from `P20` is built in.** Refusing a call does not take the decision away
from the model — it re-issues with different words 69% of the time. So the agent has **no
transfer tool that could be refused**. The action does not exist.

**Why it qualifies as a pattern and not as prompting**, by the four questions in
`PATRON_O_FACTOR.es.md`: calls bounded by the number of scopes and fixed by code; the
**code** chooses whether to transfer; the shared state is a **contract** written by code
from a typed proposal; and a step can re-scope. That is a different control graph, not a
different prompt.

**Registered predictions.**

- **P23a (it must beat the arm it replaces).** On the coupled cells — `C3`, `C5` — `handoff`
  reaches strictly higher utility than a fixed fan-out with no transfer. Falsified if it
  does not: independent scopes without a working transfer are just a partition, and a
  partition already lost those cells.
- **P23b (the transfer has to fire, and rarely).** The rule authorises on **at least one and
  at most half** of the coupled cells. Falsified at zero — the pattern degenerates into two
  isolated agents — and falsified above half, which would mean the literal-bridge rule is
  authorising on noise rather than on a real reference.
- **P23c (determinism, and this is the differentiating claim).** Across replicates of the
  same cell, the set of authorised transfers is **identical**. Falsified by a single cell
  where two replicates transfer differently: that would mean the transfer inherited the
  model's variance, which is exactly what `transfer_to_agent()` does and what this pattern
  exists not to do.
- **P23d (it is not free).** Cost per cell exceeds a fixed fan-out's. Falsified if it does
  not — that would mean the second agent is not actually running, and `P23a` would be
  measuring something else.

**`P23c` is the one worth running even if the others fail.** Utility is a property of this
corpus; reproducibility of the transfer is a property of the mechanism, and it is the only
one of the four that no prompt-based handoff can match.

**Not yet run.** `map_reduce` was moved to standby by the author on the same day, so the
fixed-fan-out comparison uses its existing record rather than new spend.

### P8 verdict (2026-08-28) — the transfer test, registered 2026-08-26 and never scored

**Why this sat unevaluated.** The five predictions were registered before running, the
world was generated and verified, the run happened — and the verdict was never computed.
The paper still said *"not yet run"*. It surfaced while sweeping for "declared, not
measured", which this repo's own rule calls debt.

`gold_holdout` is seed 23; every prior per-cell verdict came from seed-7 worlds. Screening
design as registered: 4 discriminating tasks × 4 arms × repeat 2 = 32 rows.

| # | verdict | |
|---|---|---|
| **P8a** `react` u ≥ 0.9 on every feasible cell | **DOES NOT TRANSFER** | below 0.9 on **4 of 4** cells, min **0.000** |
| **P8b** `map_reduce` u = 0 on the coupled cell | **NOT EVALUABLE** | `map_reduce` did not run in this corpus |
| **P8c** `rewoo` wins C2/C4, fails coupled/unknown-horizon | **transfers** | 0.75 against 0.000 |
| **P8d** `gist_reader` u ≥ 0.75 on C2/C4/C5 at ≤ react's cost | **DOES NOT TRANSFER** | u **0.118**, and costs *more* than react |
| **P8e** `dag_strategy` stays at risk on the deep coupled cell | **transfers** | 0.000 on both replicates |

**Not evaluable is not refuted.** `P8b` has no cells to be evaluated on, so it did not
fail — it could not be asked. Counting it would demote CONCLUSIONS on an absence of data.

**The registered decision rule fires: two fail, so CONCLUSIONS is corpus-local**, and every
per-cell rule now carries a per-world caveat.

**And the obvious objection is answered by the data, not by argument.** If nothing worked in
this world, `P8a` would fail for a reason that is about the world and not about `react`. It
is not so:

| task | best arm | `react` |
|---|---|---:|
| `c2-000-w48` | `rewoo` **1.000** | 0.667 |
| `c4-000-w48` | `dag_strategy` **1.000** | **0.000** |
| `c3-001-h2` | nothing reaches anything | 0.000 |
| `c5-000-w48` | nothing reaches anything | 0.000 |

> On the two cells where the world is demonstrably solvable, another arm reaches a perfect
> score and `react` — the "general fallback" — gets 0.667 and **0.000**. The refutation does
> not rest on the two cells nobody solved.

**What this costs the paper.** The `react`-as-general-fallback claim was derived from seed-7
worlds and does not survive one unseen world. It is not that `react` is bad: it is that
"general" was a property of the worlds it was measured on.

**Honest limits.** 32 rows and 4 tasks is a screening design, registered as such. It is
enough to *refute* a universal claim — one counterexample suffices — and not enough to
establish a replacement.

### P22 registered (2026-08-28, before REC has run) — the six REC hypotheses

`PATRON_REC.es.md` §11 stated six hypotheses in prose. Prose is not a preregistration: *"the
improvement does not beat cost and the noise floor"* has no number in it, and a claim with no
number is one that gets read after the fact in whichever direction the data went. Each is
restated below with the exact figure that refutes it.

**Two disciplines apply to all six**, and both come from results this record already paid
for:

- **The baseline is P17's router, not P15's.** A frozen P15 router is one whose selection
  rule *never fires* — pre-empted three times over — so a win against it would mean "REC
  beats a router that was never allowed to select", which is a much smaller result and one
  that reads badly. This is why REC runs **after** P17 and not in parallel.
- **Every difference is decided on a paired-bootstrap interval, not a point.** 1,000
  resamples, 95%, fixed seed. Comparing two point estimates is not a guard: on a small
  holdout a candidate that wins by 0.001 wins by noise half the time, and once promoted it
  becomes the incumbent the next cycle has to beat — the error is inherited.

| # | Prediction | Refuted when |
|---|---|---|
| **P22a** | REC captures **net positive** utility against P17's router | the lower bound of the paired difference does not clear **0** at λ = 0.02 |
| **P22b** | REC beats the best feasible fixed paradigm on a **fresh final world** | the lower bound does not clear the per-cell noise floor of that world |
| **P22c** | The gain **concentrates** on evidence-sensitive decisions | tasks REC did not trigger on gain as much as the triggered ones, or more |
| **P22d** | The verified probe has **high precision** | more than **1 in 10** accepted references do not correspond to a relation present in the material |
| **P22e** | The controller **removes** unnecessary probes | it probes on at least as many tasks as the fixed-probe arm while the counterfactuals produce the same plan |
| **P22f** | The explanation is **reproducible** | any sealed replay fails to reproduce decision and digest on any task |

**P22b is the one that can kill the pattern**, and it is deliberately the hardest: a gain
that exists only on the world REC was tuned against is not a gain. The final world is
**single-use** — a held-out set consulted twice is validation with marketing.

**P22f is the cheapest and should run first.** It costs nothing —sealed replay— and if it
fails, none of the other five means anything: a result that cannot be reproduced is not a
result.

**Cost.** Seven arms over a final world, not yet generated. Not estimated, not launched.

### P21 registered (2026-08-28, before a single row exists) — `read_all` as a factor

**What was true and nobody decided.** `read_all` lives in the accounting tool specs, so on
`basic` — the variant **every measured study used** — it does not exist. The model could
never ask for the whole material even where it fit comfortably inside its own budget. That
is not a decision someone made while measuring; it is a consequence of which list the tool
ended up in.

**And there is already a guard, which is what makes offering it safe.** `_read_all` returns
full text only if the material fits its share of the declared budget; over that it returns
**summaries of every unit** plus the reason, and never truncates silently — a silent cut is
the worst outcome, because the agent believes it saw everything and answers from a prefix.

Availability and the guard are **different questions** and now live in different places: a
declared predicate says whether the tool exists for a variant, arithmetic says whether the
call fits. `test_science.py` §31 holds both, and holds the invariant the old comment only
warned about: **what is offered is exactly what dispatches**, in every variant.

It ships as a factor, off by default, and offers `read_all` **without** dragging in the rest
of the accounting tools — so what gets measured is `read_all` and not the bundle.

**Registered predictions.**

- **P21a (it gets used where it fits).** On tasks whose material fits the budget share,
  `read_all` is called at least once in the **majority** of rows. Falsified if the models
  mostly ignore it — which would put this next to the working-memory tools, offered and
  unused, and make the whole factor moot.
- **P21b (it helps exactly where coverage is demanded).** Utility rises on `exhaustive`
  cells and does **not** rise on `sufficient` ones. Falsified if it rises on both — that
  would mean it is buying something other than coverage.
- **P21c (and it must not be free).** Cost per cell rises. Falsified if it does not, which
  would mean the tool is not actually pulling the material and P21a is measuring a call
  that returns summaries.
- **P21d (the guard is what carries it).** On tasks over the allowance, utility does **not**
  drop relative to the same cells without the factor. Falsified if it drops: that would mean
  the summaries path misleads more than not offering the tool at all, and the honest move is
  to refuse rather than summarise.

**Not yet run.**

### P20 registered (2026-08-28, before a single row exists) — the stopping rule as a factor

**The prize is measured.** Between replicates of the *same* cell reaching the *same*
utility, **33% of tokens are avoidable** — 49% on `dag_strategy`, and **0%** on
`map_reduce`, whose fan-out is fixed by code rather than by the model. That is not a
proposal; it is what the record already contains.

**The signal is measured too.** On 72 tied pairs, the peak run of barren searches is
**1.17 in the cheap replicate against 2.28 in the expensive one**. It is countable and
deterministic — the kind of environment signal this project prefers over prompt scaffolding.

**What changes.** Today a stall produces a NOTE to the model: *"the last 3 searches
surfaced nothing new, consider reading instead."* That is persuasion, and the product
invariant says the LLM is a sensor and never handles control flow. The rule replaces the
note with a **typed refusal**: past the threshold, search is unavailable; reading and
answering are untouched.

It ships as a **factor**, off by default, crossed `{on, off} × {paradigms}` — per
`PATRON_O_FACTOR.es.md`, a change that applies to every arm equally is not a pattern. Rows
go to their own file: a factor that changes what a paradigm *can do* is a different
experiment, not more samples of the same one.

**Registered predictions.**

- **P20a (the prize is real).** With the rule on, mean cost per cell drops by **at least
  10%** against the same cells with it off. Falsified if the drop is under 10% — that would
  mean the avoidable third is not reachable by this rule, whatever else is true.
- **P20b (it must not cost utility).** Mean utility per cell does **not** drop by more than
  the per-cell noise floor. Falsified if it does — a rule that saves tokens by answering
  worse is not a saving, and this is the prediction that can kill the factor.
- **P20c (it bites where the autonomy is).** The cost reduction is larger on the arms whose
  loop the model controls than on `map_reduce`, whose fan-out is fixed by code. Falsified if
  `map_reduce` drops as much — that would mean the rule is cutting something other than the
  stall it targets.
- **P20d (the refusal is used, not dodged).** After a refusal, the next tool call is a read
  or an answer in the **majority** of cases. Falsified if the models mostly re-issue a
  search with different wording: that would make this a rule that renames the waste instead
  of removing it.

**Cost.** One re-run of the affected cells with the factor on. Not yet estimated, not yet
launched.

### P19 registered (2026-08-28, before a single row exists) — C9, the declared roster

**Why this cell had to exist.** `C-COMPLETE` was implemented on 2026-08-28 because a
measurement justified it: across 1,214 rows from five corpora, on cells that *demand* full
coverage, reading more does **not** improve utility (corr `+0.018`, median `-0.055`, versus
`+0.259` where coverage is not demanded; `p = 0.028` controlling within task). Exhaustiveness
is not bought with a bigger reading budget — it has to be verified.

**And then the contract had nowhere to run.** Crossing the corpus's own two declared tables,
the intersection is **empty**:

| cells | cheap detector | coverage |
|---|---|---|
| C1, C7 | **yes** | sufficient |
| C2, C4, C5, C8 | **no** | **demanded** |

Once seen it is arithmetic, not coincidence: if the code could enumerate the answer's domain
more cheaply than solving the task, the task would not be exhaustive — it would be a lookup.
And the domain that *is* cheap (`view.unit_ids`) is exactly the one measured not to predict
correctness.

**C9 breaks it by putting the domain in the question.** "For each of the following
individuals, report the settlement account on file: A, B, C, D, E." The domain is the five
named people — `COMPUTED`, enumerable, and verifying completeness costs nothing. It reuses
existing memos: **zero new documents**.

Three properties `corpus/verify.py::_c9` enforces, each blocking a different way the domain
stops being a domain: every name appears *literally* in the prompt; every name has a memo
*in scope* (otherwise the cell measures absence, a different axis); and the re-derived oracle
has the same cardinality as the domain (otherwise set F1 cannot separate missing from extra).

**Registered predictions.**

- **P19a (the point of the cell).** On C9 the dominant error is an **incomplete** answer —
  a strict subset of the oracle — not a wrong account. Falsified if wrong-but-complete
  answers outnumber incomplete ones.
- **P19b (what 8.6 predicts here).** Utility on C9 does **not** rise with `fraction_read`,
  same as the other exhaustive cells. Falsified if the within-task correlation exceeds
  `+0.20`.
- **P19c (the contract earns its cost).** `C-COMPLETE` applied to C9 refuses exactly the
  incomplete answers and emits every complete one — no false refusals. Falsified if it
  refuses any answer whose item set equals the oracle.
- **P19d (the width-4 control).** At `width=4` the declared domain and the units in scope
  **coincide**, so `from_question` and `from_scope` are the same set. If C9 behaves the same
  at w=4 and w=48, the distinction between the two domains buys nothing here and the cell is
  only measuring width.

**Not yet run.** Cost is not estimated and the cell is not in any launched study.

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

### P10a's falsification survives a serious objection (2026-08-28, `_audit_graph_index.py`, zero tokens)

**The objection, and it was a good one.** `graph_traverse` was falsified at u=0.000 on both
coupled cells after a ~280k-token index. But that index is not built with NER: it asks the
model, unit by unit, to *"list the entities and directed relations"*, and accepts whatever
comes back **without verifying anything** — not that the entity appears in the text, not
that the relation exists. Set beside the probe, which requires a reference to appear
LITERALLY and records the span offset, the asymmetry is stark: this paradigm was measured
with an input of exactly the class the product's own invariant refuses to admit as evidence.

If the graph were wrong, u=0.000 would say nothing about traversal.

**Checked, and the objection does not survive.**

| | |
|---|---|
| entities appearing **literally** in the unit that declares them | **177/177 and 175/175 — 100%** |
| `c3-000-h1` chain `memo-000 → memo-001` | **connected in the index** |
| `c3-001-h2` chain `memo-008 → memo-010 → memo-011` | **connected, every hop** |

The extractor was not hallucinating and **the traversal had exactly the edges it needed**.
It walked them and still returned "Not found" at u=0.000 on both cells. P10a measured the
thesis, not its dependency, and the falsification stands — **stronger than before, because
the obvious way to dismiss it has now been closed with evidence rather than left open.**

**And the 100% is not reassurance — it is the finding.** Checked against `gold_deep`: the
corpus contains **zero** abbreviated forms (`J. Pérez`), **zero** anaphora (`the holder`,
`said account`), and every entity appears in one canonical, fully spelled surface form.
There is nothing to deduplicate, nothing to cluster, no coreference to resolve. A
prompt-based extractor scores 100% because **the hard part of entity extraction is absent
by construction.**

So P10a is sound *for the regime it ran in*, and that regime is one where
`graph_traverse`'s hardest dependency is free. **The same structural shape as the detector
conflation**, arriving from a different direction:

> A generator that makes a dependency trivial cannot falsify a pattern whose reason to
> exist is that the dependency is hard.

`graph_traverse` therefore moves to **standby, not retirement** (author's decision,
2026-08-28). Reviving it requires a corpus with real entity resolution work — surface
variants, abbreviations, anaphora, cross-document coreference — and an index built with the
probe's discipline: accept an entity only where it appears literally, record the span. Until
such a corpus exists, the honest statement is *"falsified where entity resolution is free"*,
not *"falsified"*.

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

## P29 — el board y el guard son UN mecanismo (registradas 2026-08-29, ANTES de correr)

**Corrida**: `bench/runs/_run_board.py --modelo luna` · `{cola, sin} × {guard, sin}` ·
`react` + `dag_strategy` · las 21 tareas de `w16` · `repeat 3`. Estimado contra el corpus:
~25M tokens los cuatro brazos, **sin** contar las llamadas de extracción del guard, que
son la parte que no se puede proyectar desde el material.

**De dónde sale**: la capa congelada —la única que corrió contra un índice real— tenía el
guard y el board como **dos piezas de un mismo mecanismo**: el guard acota la ventana por
crecimiento y **produce** un hallazgo enfocado en la pregunta; el board lo conserva y con
eso **dirige** lo que sigue. El banco tenía las dos mitades rotas por separado — el board
sólo llegaba por la plantilla de `dag` y por una tool que el modelo llamó **1 vez en 125**,
y el guard no existía: las dos compactaciones del banco **degradan** y ninguna **produce**.

| # | predicción | qué la refuta |
|---|---|---|
| **P29a** | **`ambos` > `cola`** y **`ambos` > `guard`** en utilidad neta. Si son un mecanismo, cada mitad sola vale menos que las dos | que una mitad sola iguale o supere al cruce: serían dos mecanismos independientes y la tesis de «una máquina» cae |
| **P29b** | **`guard` baja el costo** contra `base` en `react`, **neto de las llamadas de extracción**. Es la prueba dura: la extracción se paga, así que el ahorro tiene que superar lo que cuesta | que el neto sea ≥ 0. Sería un mecanismo que cobra por no ahorrar, y se retira |
| **P29c** | **`cola` sube la utilidad en `react` más que en `dag_strategy`**. `dag` ya coordina con su board estructural; `react` es el agente solo, que es donde la cola no existía | que el efecto sea igual o mayor en `dag`: la cola estaría comprando coordinación de grupo y no dirección de investigación |
| **P29d** | el guard **dispara** en `w16`: `guard_evictions > 0` en la mayoría de las celdas de `react` | cero expulsiones. Sería un factor inerte y `w16` el estrato equivocado — el umbral de 20k caracteres es del régimen anterior y habría que declararlo de nuevo |
| **P29e** | `guard_evicted_nothing` **> 0 en alguna celda**: parte del material recuperado no aporta a la pregunta. Eso es información sobre la **recuperación**, no sobre el modelo | que sea 0 en todas: la recuperación no traería nada irrelevante en `w16`, que contradiría el recall medido |

**Lo que NO se predice, y se dice para no leerlo después como si se hubiera acertado**: la
magnitud. `repeat 3` sobre 21 tareas da un piso de ruido por celda que hay que calcular
sobre el registro terminado, y las decisiones van contra la **brecha neta**, no contra las
medias crudas.

**Y una amenaza declarada antes**: los brazos con guard hacen **una llamada más al modelo
por expulsión**, así que su conteo de llamadas no es comparable con `base` sin ajustar. El
costo en tokens sí lo es, y es el eje que decide.

## P30 — máxima cobertura, mínimas llamadas (registradas 2026-08-29, ANTES de correr)

**Corrida**: `bench/runs/_run_cobertura.py --modelo luna` · `react` · las 21 tareas de
`w16` · `repeat 3` · dos brazos: `readall` (la tool sola sobre `basic`) y `accounting`
(`read_all` **más** `coverage`). El `base` no se corre: lo produce la corrida del board
sobre las mismas tareas, y correrlo de nuevo sería appendear al mismo `.jsonl` desde dos
procesos.

**El número que la motiva, medido sobre 704 celdas ya pagadas:**

| | celdas | tokens | `u` |
|---|---:|---:|---:|
| ≤ 2 llamadas al modelo | 234 | **9.779** | 0,509 |
| ≥ 8 llamadas | 65 | **136.432** | 0,631 |

**14× más tokens por +0,122 de utilidad.** La causa es estructural y no del modelo: la
conversación se reenvía entera en cada vuelta, así que el costo de `N` llamadas crece como
`N²` mientras la cobertura crece como `N`. Y ningún brazo pasa hoy de **1,6 unidades por
llamada** — `read_all` las lee todas en una, y **no está ofrecido en `basic`**, que es la
variante de todos los estudios medidos.

| # | predicción | qué la refuta |
|---|---|---|
| **P30a** | `readall` baja el costo de `react` **≥ 3×** contra `base` en `w16`, con `u` dentro del ruido de la celda. No predigo 10×: el 14× del registro compara poblaciones distintas de tareas, no el mismo brazo con y sin la tool | menos de 3×, o `u` que cae más allá del ruido. Sería un ahorro que se paga con calidad |
| **P30b** | `unidades por llamada` sube de **1,41 a más de 5** en `readall` | que se quede debajo de 2: el modelo tendría `read_all` y no lo usaría, y el resultado sería sobre **adopción**, no sobre el mecanismo — el mismo nulo que dio el board como tool |
| **P30c** | `accounting` **supera a `readall`**: sin `coverage` el modelo no sabe que le conviene pedir todo | que empaten o que `accounting` pierda. Entonces la tool que informa cobertura no cambia la decisión, y el paquete de contabilidad se evalúa distinto |
| **P30d** | la traza por llamada muestra que la **ventana crece de forma superlineal** en `base` y **plana** en `readall` | que crezca parecido en los dos: la premisa `N²` sería falsa y el ahorro vendría de otro lado que hay que nombrar |

**Lo que NO se predice**: que esto generalice fuera de `react`. `dag_strategy` y
`reflection` entran después si el cruce dice algo — un solo brazo hace la corrida barata y
el mecanismo, si existe, tiene que verse ahí primero.

**Amenaza declarada antes**: `accounting` cambia **dos cosas** a la vez —trae `read_all`
y `coverage`— así que su efecto no es atribuible a `coverage` sola. `readall` es el brazo
que aísla, y por eso van los dos.

### Veredicto de P30 (2026-08-29, corrida terminada)

**63 celdas-trial pareadas**, `react` sobre las 21 tareas de `w16`, `repeat 3`. Gasto:
**5,5M tokens**, por debajo del techo de 8,6M que se había estimado.

| | tok/celda | llamadas | unidades | `u` |
|---|---:|---:|---:|---:|
| `base` | 137.211 | 4,3 | 10,0 | 0,540 |
| `readall` | **87.495** | 4,0 | 8,5 | 0,540 |

**1,57× más barato en TOKENS con la utilidad exactamente igual** — `+0,000`, no «dentro
del ruido». **En plata es 1,36×**, y la diferencia importa: el proveedor sirve el **51%**
de la entrada del brazo base desde su propio caché, a **una décima parte del precio**.
Los tokens deciden si una tarea entra en la ventana y dónde se cruza el acantilado de
contexto largo; los dólares son lo que paga un despliegue. **Un resultado de costo sin
su unidad no es reportable**, y acá los dos difieren un 15%.

| # | predicción | veredicto |
|---|---|---|
| **P30a** | costo ≥3× más barato, `u` dentro del ruido | **a medias.** Dio 1,57×, por debajo de lo predicho. Pero `u` no se movió una milésima, que era la otra mitad |
| **P30b** | unidades por llamada de 1,41 a **más de 5** | **REFUTADA, y en la dirección contraria.** Bajó: 2,33 → 2,13. `read_all` se llamó en **3 de 63 celdas** |
| **P30c** | `accounting` supera a `readall` | **sin correr.** El brazo se dejó afuera por precio; `readall` es el que aísla |
| **P30d** | la ventana crece superlinealmente | **CONFIRMADA, y es lo más fuerte que salió** |

#### La causa, y no es la que la predicción suponía

`read_all` casi no se usó, así que el ahorro **no viene de leer todo en una llamada**. Viene
de otro lado, y el registro lo señala solo:

| | `base` | `readall` | |
|---|---:|---:|---:|
| `reread_chars` | 2.836.465 | **322.094** | **8,8× menos** |
| `served_chars` | 22.586.496 | 16.949.268 | |
| **fracción releída** | **12,6%** | **1,9%** | |

La mezcla de herramientas casi no cambió —399 llamadas contra 365— pero **el releído se
derrumbó**. Con `read_all` ofrecido el agente **lee menos unidades y se repite muchísimo
menos, con la misma calidad**: el material que releía era desperdicio.

> **El efecto está en la OFERTA, no en el uso.** Es la misma forma que dio el board como
> herramienta —1 de 125 llamadas— pero acá con signo positivo: ofrecer una salida barata
> cambió la estrategia sin que la salida se tomara.

#### Y la traza por llamada dio el número que la fila nunca pudo dar

Primera corrida con `MAPO_TRACE=1`. **273 llamadas trazadas**, y el crecimiento de la
ventana por vuelta:

| turno | llamadas | ventana (chars) | prompt (tokens) | contra el turno 0 |
|---:|---:|---:|---:|---:|
| 0 | 63 | 354 | 607 | 1,0× |
| 1 | 63 | 50.617 | 9.914 | **16,3×** |
| 2 | 61 | 180.477 | 33.548 | **55,3×** |
| 4 | 22 | 216.458 | 40.131 | 66,1× |
| 8 | 1 | 364.334 | 67.233 | **110,8×** |

> **El 99% del gasto de entrada es re-envío de la conversación.** El primer turno consume
> 38.238 tokens de 5.503.757 — el 1%. Todo lo demás es material que ya se había pagado,
> viajando otra vez.

Eso es el `N²` medido directo por primera vez, y no derivado de comparar poblaciones. La
fila decía `calls=4,3` y `cost_tokens=137.211` y **no cuál llamada costó qué**; la traza lo
dice, y con eso el mecanismo deja de ser una inferencia.

#### Qué queda

Correr `accounting` cerraría `P30c` —si `coverage` cambia la decisión de pedir todo— y
`dag_strategy`/`reflection` dirían si esto generaliza fuera de `react`. Ninguno es urgente:
lo que el mecanismo tenía para decir, ya lo dijo.

---

## P29 — ¿el consenso entre paradigmas es convergencia de trayectorias, o el mismo modelo repitiéndose?

**Registrada 2026-08-30, ANTES de correr.**

**El hallazgo que la motiva** (`bench/analysis/_consenso.py`, sobre `luna`): la probabilidad de
que una respuesta sea correcta dado que `k` brazos coinciden con ella —igualdad exacta de la
cadena normalizada— sube `0,42 · 0,39 · 0,60 · 0,81` y llega a **`1,000` en `k >= 4`**, con
**180 de 180 celdas**. Sobrevive los dos controles que lo podían matar: no marca «tarea fácil»
—en las mismas 27 tareas, los brazos fuera del consenso sacan `0,100` contra `1,000`— y no es
un artefacto de comparar cadenas cortas —aguanta en las cuatro cardinalidades, incluida
enumerativa—.

**LO QUE NO PUEDE DISTINGUIR, y por eso existe esta predicción.** Los ocho brazos comparten
modelo, corpus y recuperador. Hay dos mecanismos compatibles con el número:

  · **convergencia de trayectorias** — estructuras de control distintas llegan al mismo lugar
    cuando ese lugar es el correcto, y se dispersan cuando no. Si es esto, el efecto es una
    propiedad de los paradigmas y debería reproducirse con otro modelo debajo
  · **el mismo modelo repitiéndose** — ocho envoltorios alrededor del mismo sensor producen
    la misma salida por la misma razón, y el acuerdo no es evidencia de nada. Si es esto, el
    efecto es del modelo y cambiar de modelo lo borra

**LA CORRIDA.** `terra` (`gpt-5.6-terra`, la otra familia) sobre **24 tareas × 8 brazos × 1
réplica** = 192 celdas, ~13,6M tokens, **~USD 27**. Una réplica y no tres porque el análisis de
consenso usa sólo `trial 0`: el consenso se forma entre RESPUESTAS, y promediar réplicas
produce un número, no una cadena comparable. Las 24 tareas se eligieron **estratificadas por
cardinalidad** con semilla 23 —las cuatro representadas, 10 de las 11 celdas del corpus— y
están fijas en `bench/runs/_tareas_control_terra.txt`.

**LA PREDICCIÓN, con los tres desenlaces escritos de antemano:**

| `P(correcta \| k>=4)` en `terra` | veredicto |
|---|---|
| **>= 0,90** | CONVERGENCIA. El consenso es una propiedad de los paradigmas y el detector se puede usar |
| **<= 0,65** (tasa base ~0,53) | EL MISMO MODELO. El acuerdo no es evidencia y §7.13 se retira del paper |
| entre 0,65 y 0,90 | NO DISTINGUE. Haría falta un tercer modelo, y el hallazgo queda como «de este corpus con este modelo» |

**Y una guarda contra mi propio sesgo:** el umbral `k >= 4` se eligió mirando los datos de
`luna`, así que sobre `terra` hay que reportar **la curva entera** y no sólo ese punto. Si el
umbral se mueve —digamos que en `terra` el salto está en 3 o en 5— eso ya es información:
diría que el umbral es del modelo y no de la estructura.

**Cobertura esperada:** en `luna`, 27 de 64 tareas (42%) alcanzan `k >= 4`. Sobre 24 tareas
eso proyecta ~10 tareas y ~60-70 celdas en el umbral. Si salen muchas menos, el resultado no
concluye por falta de `n` y hay que decirlo en vez de leer el promedio.

### P29 — VEREDICTO: **CONVERGENCIA** (2026-08-30)

**Corrido**: `terra` sobre 23 de las 24 tareas del control (una no produjo panel), 209 celdas
factibles, réplica 0, cero `infra_error`.

**Y se lee restringido a los 8 brazos del panel de `luna`, no a los 12 que corrieron.** Es un
defecto de diseño que aparecio al mirar el resultado: `k` acuerdos no significan lo mismo sobre
planteles de distinto tamaño. `k=4` sobre 8 brazos son 4 de 7 otros (57%); sobre 12 son 4 de 11
(36%). Comparar el umbral crudo entre corridas con planteles distintos habria dado un veredicto
falso — pareceria que el umbral «se corrio». Los 8 estan adentro de los 12, asi que la corrida
sirve igual y solo hay que filtrar al analizar.

| `terra`, 8 brazos | celdas | `P(correcta)` | cobertura |
|---|---:|---:|---:|
| `k >= 4` | 99 | **1,000** | 14 de 23 tareas |
| `k >= 3` | 115 | **1,000** | 18 de 23 tareas |

**El criterio registrado era `P(correcta | k>=4) >= 0,90` para declarar CONVERGENCIA. Dio
`1,000`.** El consenso entre paradigmas se reproduce sobre otra familia de modelo, asi que no
es el mismo modelo repitiendose: es lo que la prediccion llamo **convergencia de trayectorias**.

**El control dentro de la tarea tambien se reproduce**, y es la parte que descarta que el
consenso solo marque «tarea facil»: en las tareas donde existe consenso a `k>=3`, los brazos que
quedan AFUERA sacan `0,272` (n=29) contra `1,000` de los que estan adentro.

**Y el umbral se movio hacia abajo, no hacia arriba: 4 en `luna`, 3 en `terra`.** La guarda que
deje escrita anticipaba justo esto —«si el umbral se mueve, eso ya es informacion»—. Lo que
dice es que **el umbral exacto es del modelo y el fenomeno no**: sobre un modelo mejor hacen
falta menos acuerdos para la misma precision, lo cual es coherente con que la senal sea
convergencia y no coincidencia.

**La cobertura tambien sube**: 18 de 23 tareas (78%) en `terra` a `k>=3`, contra 27 de 64 (42%)
en `luna` a `k>=4`. El detector es mas util sobre el modelo mejor, no menos.

**Lo que sigue sin estar probado.** Dos familias no son la poblacion de los modelos, y los dos
comparten corpus y recuperador. Lo que se descarto es la explicacion mas barata —«es el mismo
modelo»—; no se probo que valga para cualquier modelo ni para cualquier corpus.

## P31 a P36 — las seis apuestas del paper (registradas 2026-09-03, ANTES de correr)

El paper v3.2 pone en §9.1 una apuesta por contribución, con criterio numérico y con lo que se
retira si falla. Se registran acá para que el veredicto se lea contra lo escrito hoy y no contra
lo que convenga después. Ninguna corrió.

### P31 — el brazo de ausencia (contribución 2: la interfaz aprendible)

Construir el brazo que junta `COBERTURA_GARANTIZADA` y `ABSTIENE_SIN_PRUEBA`: recorrido
exhaustivo con estado acotado, y abstención explícita cuando ninguna unidad sostiene la
respuesta. Correrlo sobre las celdas de ausencia del rectángulo (y presuposición falsa como
control), 3 réplicas, `gpt-5.6-luna`, mismas condiciones que la campaña.

| resultado | veredicto |
|---|---|
| `u` en ausencia >= mejor brazo del plantel en ausencia + piso p95 calibrado (8 brazos), Y leave-one-arm-out con nueve brazos con `p` exacto <= 0,05 | LAS CAPACIDADES PREDICEN. La tabla de exigencias diseñó un brazo que no existía y el brazo cumplió |
| `u` en ausencia >= mejor fijo en ausencia pero el LOAO no cruza 0,05 | la tabla predice este caso; la transferencia general sigue sugestiva, y hacen falta más brazos |
| `u` en ausencia < mejor fijo en ausencia | la tabla está MAL DECLARADA. Se anota qué capacidad faltó o cuál estaba mal, y se retira del resumen «predice un brazo que nunca corrió» |

Costo estimado: ~7 tareas de ausencia + ~7 de presuposición, 3 réplicas, un brazo: ~42 celdas,
del orden de 1M tokens.

### P32 — la corrección de `pointer_chase` transfiere (contribución 1: la condición estructural)

Generar seis tareas de cadena acoplada con semilla nueva (dos por largo: 1, 2 y 3 saltos). Correr
`pointer_chase` corregido (las cuatro correcciones de §6.1.4) y `dag_strategy` como referencia,
3 réplicas, sobre `terra`, y `luna` al lado.

| `pointer_chase` sobre las 18 celdas de `terra` | veredicto |
|---|---|
| `u >= 0,75` y `pass^3 >= 0,60` | EL MECANISMO TRANSFIERE. §6.1.4 deja de ser ajuste en muestra |
| `u` entre 0,50 y 0,75 | transfiere en parte; se reporta la clase de falla dominante y se busca la quinta corrección |
| `u <= 0,50` | FUE AJUSTE EN MUESTRA sobre tres tareas. §6.1.4 y la contribución 1 se reescriben con ese rótulo |

Guarda: las celdas se generan ANTES de tocar una línea de `pointer_chase`, y la corrida es una sola.
Costo: ~36 celdas `terra` + 36 `luna`, ~3M tokens.

### P33 — el ciclo sobre el modelo de la campaña (contribución 3: la frontera)

Repetir `P15`, `P16` y `P17` sobre `gpt-5.6-luna`, mismos mundos (semillas 47, 61, 73), mismo
vocabulario de cada etapa.

| resultado | veredicto |
|---|---|
| el signo de `P15` se conserva (neto contra el mejor fijo <= −piso por celda), la continuidad separa el horizonte >= 5 de 6, decisión reproducida 26/26 en los tres | EL MECANISMO ERA DEL VOCABULARIO. La costura de modelo se cierra |
| `P15` sobre `luna` da neto positivo > piso | lo que faltaba no era el eje sino el modelo. §6.5 se reescribe y la contribución 3 pierde su primer episodio |
| reproducibilidad < 26/26 en algún mundo | hay una ramificación delegada en la política que el registro no vio; se busca y se tipa antes de seguir |

Costo: ~40M tokens (lo que costaron sobre `nano`, ×1 en filas).

### P34 — la consolidación aprende el desempate por costo (contribución 4: el premio)

Darle a la consolidación el objetivo de costo sobre la clave `COMPUTED` que incluye
`cardinalidad × término`, leave-one-task-out sobre el rectángulo 64 × 8. Hoy la clave computada
sola da 31% de ahorro a −0,104, y la señal suelta 58% a +0,000.

| resultado | veredicto |
|---|---|
| ahorro >= 50% con `Δu` cuyo IC95 incluye cero | LA POLÍTICA APRENDE LO QUE LA SEÑAL MUESTRA. La contribución 4 pasa de «señal» a «política» |
| ahorro entre 40% y 50%, o IC95 que excluye cero por poco | aprende en parte; se reporta qué regiones pierden |
| ahorro < 40% o `Δu` significativamente negativo | LA BRECHA ES DEL ALGORITMO. Se diagnostica dónde: partición, piso de episodios (hoy ocho) u homeostasis, y se anota como deuda del sistema |

Costo: cero tokens (replay sobre el registro).

### P35 — la ontología se recupera desde el request (contribución 2)

Un clasificador con el modelo de la campaña, una llamada por tarea, recupera el eje principal de
la ontología desde el texto del request, contra la etiqueta de diseño, sobre las 64 tareas del
rectángulo.

| precisión contra la etiqueta de diseño | veredicto |
|---|---|
| >= 0,85 | LA INTERFAZ SIRVE AFUERA DEL BANCO, con la salvedad de que el eje recuperado es `ELICITED` y sólo informa el costo, nunca el piso (Prop. 5) |
| entre 0,70 y 0,85 | sirve para el desempate por costo y no para excluir brazos; se dice así |
| < 0,70 | la ontología queda como etiqueta de diseño y la clave se limita a cardinalidad y cobertura, que el caller declara |

Costo: 64 llamadas.

### P36 — el sistema propone el eje (contribución 3)

Darle a la etapa de abstracción de la consolidación el registro de `P15` con sus features crudos
(sin el eje de continuidad) y medir si propone sola una partición equivalente.

| resultado | veredicto |
|---|---|
| propone una función del material que separa el horizonte desconocido 6 de 6 sin falsos positivos | EL LAZO SE CIERRA SIN PERSONAS en los pasos 3 y 4. La reparación del vocabulario pasa de método a plasticidad |
| propone una partición que separa parcialmente (4 o 5 de 6) | plasticidad parcial; se reporta qué le faltó ver |
| no propone nada que separe | la reparación del vocabulario queda como método de desarrollo, que es lo que el paper afirma hoy |

Costo: cero tokens.

Orden: P34 y P36 primero (gratis). Después P32 y P31. Después P35. P33 último, por costo.

### Veredicto P34 (2026-09-03, `bench/analysis/_p34_costo.py`, cero tokens): **PARCIAL**, y destapó un eje que falta

Leave-one-task-out sobre el rectángulo 64 × 8 con la θ REAL (`Plasticity.candidate`, piso de 8
episodios, `hierarchical=True`), objetivo de costo, contra la constante que no aprende (0,817 ·
120.976 tok/tarea).

| clave de θ | utilidad | Δu vs constante | IC95 | tok/tarea | ahorro | tareas gobernadas |
|---|---:|---:|---|---:|---:|---:|
| región completa (con el eje ELICITED) | 0,789 | −0,027 | [−0,078, +0,021] | 58.489 | 52% | 24 |
| región COMPUTADA, 4 ejes, jerárquica | 0,770 | −0,047 | [−0,115, +0,022] | 78.621 | 35% | 64 |
| card. de UNIDADES × literal(región) | 0,848 | +0,031 | [−0,005, +0,078] | 92.076 | 24% | 64 |
| **card. de RESPUESTA × término(regex)** | **0,875** | **+0,058** | [−0,014, +0,132] | 71.070 | **41%** | 50 |
| card. de RESPUESTA × literal(región) | 0,875 | +0,058 | [−0,016, +0,136] | 71.070 | 41% | 50 |

**Primera corrida, sólo con las claves de la región: FRACASO** (35% a −0,047). Y midiendo
apareció por qué la señal del 58% no era alcanzable desde la región: **el eje `card` de la región
es cardinalidad de UNIDADES (`single/few/many`), y la señal de `_predictores.py` usa la
cardinalidad de la RESPUESTA que el caller declara (`boolean/singular/enumerative/aggregate`)**.
Son ejes distintos, los dos `COMPUTED`, y el vocabulario de región no tiene el segundo. Se agregó
al script la clave que la apuesta nombra (la señal de §6.4.1 como clave de θ) y se volvió a
correr; las dos corridas quedan reportadas.

**Con la clave correcta: 41% con Δu +0,058, IC95 que cruza cero → PARCIAL** contra el criterio
registrado (>= 50%). La utilidad queda POR ENCIMA de la constante, casi significativa.

**Dónde vive la brecha con el 58%**: 14 de las 64 tareas caen a la constante (react, ~121k
tokens) porque su clave no tiene 8 episodios en ningún nivel. Sobre las 50 gobernadas el costo
medio es ~57k, que sería ~53% de ahorro. **El piso de episodios es el mecanismo**, que es el
segundo de los tres que la apuesta nombraba (partición, piso, homeostasis).

**Qué cambia**: el paper §6.4.1 reporta el número; el vocabulario de región tiene un eje
candidato, `answer_cardinality` (declarado por el caller, `COMPUTED`), y cambiarlo es decisión
del autor (`CP-8` ya anotaba la tensión con la sonda). **No se toca el piso de 8 mirando este
resultado**: bajarlo ahora sería ajustar contra el dato que lo sugirió.

### Veredicto P36 (2026-09-03, `bench/analysis/_p36_abstraccion.py`, cero tokens): **FRACASO**, con una pista

Registro de `P15` (`gold_transfer`, 336 filas aprendibles, 5 brazos, 26 tareas; el material es
el mismo que corrió P15: el cambio K-6 fue del tokenizador, no del generador). Quince
estadísticas crudas de `(pregunta, material)` sin sensor tipado. `discover_partitions` tal como
corre en `sleep_cycle`.

**Partición canónica** (orden de `task_id`, 50/25): 8 candidatas, 3 sobreviven (`n_units`,
`total_chars`, `unit_len_cv`), **ninguna aísla el horizonte**; la más cercana, `unit_len_cv`,
da 6/6 con 10 falsos positivos. **200 particiones al azar**: ninguna sobreviviente aísla 6/6 con
0 fp salvo `raw_units_touching_question > 0,99` (la fracción de unidades que contienen algún
término de la pregunta), que lo hace en **8 de 200** y sobrevive en 49.

**Veredicto contra lo registrado: FRACASO.** La reparación del vocabulario queda como método de
desarrollo, que es lo que el paper afirma.

**La pista, dicha entera**: existe una estadística genérica del material que aísla las seis
tareas de horizonte sin falsos positivos, y la etapa la encuentra en el 4% de las particiones y
no la retiene. El límite está en la selección (winner-flip + retención sobre 26 tareas), no en
el espacio de features. Es una hipótesis para el diseño de la etapa, no un resultado.

**Y un recuento que corrige al paper**: `measure_continuation`, el sensor humano, sobre
`gold_transfer` da **6/6 con 2 falsos positivos**, las dos tareas `-pos` de C7 (acción
irreversible). La bitácora original (P15) decía «zero false positives on C1/C2/C4», que es
cierto; el paper había generalizado a «sobre las demás celdas», que no lo es. Corregido en
§6.5.2 del largo y §5.4 del corto. El criterio de P36 (0 fp) era más exigente que lo que el
sensor humano cumple.
