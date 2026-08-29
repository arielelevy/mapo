# Feasibility Before Selection: When Orchestration Topology Actually Matters for LLM Agents

**Draft 0.1 — 2026-08-23**
**Author**: Ariel Edgardo Levy
**Status**: working draft. Theory is complete and machine-checked; measurements are
preliminary at n=1 per cell. Every empirical claim below carries its sample size.
Target: arXiv cs.LG (primary), cs.AI (cross-list).

---

## Abstract

Per-task selection of an agent's reasoning paradigm has a large, measured prize: oracle
selection beats the best fixed paradigm by 17.1pp, and the best published router recovers
about a quarter of that gap while zero-shot self-routing recovers negative value. We argue
the bottleneck is not selector capacity but decision framing, and we develop three results
in front of the learning problem rather than inside it.

First, **feasibility is arithmetic**. Whether a topology can run a task is computable from
declared quantities — unit count, unit length, budget — with no model call and no
statistics. On a corpus scaled from 16k to 1.27M tokens this prunes three of seven
candidate topologies before any token is spent, and it separates two failure modes that
are routinely conflated: map-reduce is bounded by *cardinality*, not by total size.

Second, **selection pays only under a precise condition**. We give the Selection Value
Theorem — `Σⱼ π_j·α_j·G_j > Σⱼ ν_j·β_j·L_j`, an exact decomposition **by destination** over a
catalogue of `k` arms — and its corollaries: a router obliged to always choose controls
neither how often it errs nor how much each error costs, and optimal coverage is below one
whenever any loss would be routed. The impossibility threshold is parameterised by **loss
selectivity** `ρ`, the ratio of realised to distributional loss: a router that errs often
but cheaply can exceed the classical bound and still capture value. We
further show that where a cheap failure detector exists, escalation dominates prediction —
a router that misroutes pays a quality loss, a cascade pays a cost loss — which partitions
the problem by verifiability rather than by task type.

Third, and empirically, **tool surface governs the variance that topology choice is
credited with**. Across four feature cells, paradigms that do not use tools span a 1.2×
cost range; paradigms that do span 50×. Adding one signal — that the retriever has
returned nothing new for three consecutive searches — cut the cost of the most
elaborate topology by 3.05× against a replicate spread of 1.62× on the same measure.

We contribute the theory, a machine-checked measurement layer, a corpus generator with
exact ground truth at four scales, and a preliminary failure analysis of seven topologies.
We do not yet contribute a validated selector.

**Keywords**: LLM agents, orchestration, selective prediction, learning to defer,
retrieval-augmented generation, tool design, agent evaluation

---

# 1. Introduction

## 1.1 A measured prize that nobody captures

An LLM agent's *paradigm* — the control structure wrapped around the model, such as a
single call, a reasoning loop, a decomposition, or a verify-replan graph — is normally
chosen once at design time and frozen in code. Recent work measures what that costs.
Across six paradigms, four frontier models and ten benchmarks (~18,000 runs), oracle
per-task selection beats the best fixed paradigm by **17.1pp** on average, with individual
swings as large as +44pp and −15pp depending on the pairing [Select-then-Solve,
arXiv:2604.06753].

The same work shows the prize is not being collected. A trained embedding router recovers
roughly a quarter of the gap. Zero-shot self-routing — asking the model to pick its own
paradigm — recovers *negative* value: two models fall below their own single-paradigm
baselines, one to 27.5%.

So: the prize is large, the best published attempt captures a minority of it, and the naive
attempt is worse than not trying. That pattern invites the conclusion that better selectors
are needed. We argue it invites a different one.

## 1.2 Three claims that precede the learning problem

**Feasibility is arithmetic, and it is free.** Before asking which topology is *best*, one
can ask which can *run*. That question is answerable from quantities the task already
declares. A learned policy that spends episodes discovering that map-reduce loses on
500-unit tasks is learning arithmetic the hard way; the cap was computable before the first
token.

**Selection pays only under a precise condition.** A router that must always choose has no
degree of freedom over its false-positive rate and therefore pays for every misroute. We
formalise when selection beats a fixed fallback and show that the optimal operating point
generally involves abstaining on most requests — which is not a weaker router but a
different objective.

**Much of what is attributed to topology is attributable to tools.** In our measurements
the paradigms that use retrieval tools span a fifty-fold cost range while those that do not
span 1.2×. A benchmark that does not report the quality of its tool surface is not
comparing topologies; it is comparing one retriever wrapped seven ways.

## 1.3 What this draft does and does not establish

Established: the theory (§5), machine-checked against synthetic distributions with known
answers; a feasibility layer (§4) validated across four corpus scales; a corpus generator
whose ground truth is re-derived independently from the documents (§6).

Preliminary: every empirical number in §7 and §8 is n=1 per cell on one corpus with one
model. Replicate variance on the most elaborate topology was measured at up to 3.93× in
cost, so magnitudes are indicative. The *mechanisms* are more robust than the magnitudes,
because they rest on tool-usage traces rather than on effect sizes.

Not established: a validated selector, any result on public benchmarks, and any claim about
a regime other than exact-answer extraction over document collections.

**Structurally untested, which is stronger than "not established" and was found by
measurement.** §5.2 partitions the problem on `v`, the availability of a cheap runtime
detector, and sends `v = 1` to a cascade and `v = 0` to a router. **Every corpus in this
record sits on the `v = 1` side.** Not by choice: grading without a judge means grading by
exact match, exact match needs a gold answer, and the same field was read as the runtime
detector — so 25 of 26 tasks per corpus declared `v = 1`. The cascade rule fires at a higher
priority than the selection rule, so on two independent held-out corpora **the selection
rule never fired at all**, and both routing verdicts are measurements of the cascade.

The general form is a caution about a whole class of experiment, not about this one:

> A benchmark that establishes correctness by exact match against a reference **holds a
> cheap detector on every task by construction**, and therefore cannot exercise the
> `v = 0` branch of its own partition. Being gradeable implies being verifiable.

Whether selection pays where verification is genuinely impossible is, on this record,
**open** — and it needs a corpus whose detector availability is declared per task rather
than inherited from the answer key.

---

# 2. Related work

## 2.1 Automatic workflow search

AFlow reformulates workflow optimisation as search over code-represented workflows with
MCTS over operators [arXiv:2410.10762]; ADAS and GPTSwarm search related spaces. These
produce **one** workflow per benchmark, offline. Our concern is per-request selection among
a fixed set, and — before that — which members of the set can run at all.

## 2.2 Inference-time paradigm selection

Select-then-Solve trains a lightweight embedding router to pick a paradigm per task
[arXiv:2604.06753]. FlowBank builds a portfolio offline and selects per query
[arXiv:2606.11290]. TRACE-Router routes at the granularity of a task trace rather than a
request [arXiv:2607.22465]. Uno-Orchestra learns a joint decomposition-and-dispatch policy
[arXiv:2605.05007].

All of these operate at **coverage one**: every task receives a paradigm. §5.1 argues that
this is the binding constraint rather than model capacity, and none of them reports a
risk-coverage curve. Two details of Select-then-Solve, verified against the full paper
rather than its abstract (2026-08-26): its oracle is an *uncorrected empirical maximum* per
task, and its own limitations note that the benchmark sample is fixed with no re-sampling
across seeds — which is precisely the upward bias our noise-floor protocol (§6.1) is built
to discount. And the deferral machinery exists next door without having crossed over:
ReDAct defers individual decisions to a larger model on a calibrated uncertainty threshold
[arXiv:2604.07036]; uncertainty-decomposition routing unifies abstention and routing with
distribution-free guarantees, for classifiers [arXiv:2605.07805]; and compositional
meta-routing trains an interpretable router over textual features and names a learned
confidence gate with fallback to static routing as unevaluated future work
[arXiv:2608.00106]. Nobody applies abstention to paradigm selection (searched 2026-08-26);
the window is visibly closing.

## 2.3 Cost models for workflows

GLOW predicts agentic workflow performance from graph and language features
[arXiv:2512.15751]; Cost-Aware Optimization for Agentic Query Execution draws the analogy
to classical query optimisation explicitly [arXiv:2606.03152]. We take the analogy as
settled and do not claim it. Our addition is upstream: a hard feasibility filter that a
cost model does not replace, because an infeasible plan has no cost.

## 2.4 Symbolic governance over probabilistic inference

The Structured Cognitive Loop introduces Soft Symbolic Control, a governance mechanism
over probabilistic inference [arXiv:2511.17673]. This is the closest related work to §6.2,
and read in full (2026-08-26) its governance splits in two: *Regulation*, a persistent
natural-language metaprompt whose enforcement the paper itself notes depends on how well
the LLM interprets instructions, and *Control*, a deterministic runtime applying fixed hard
rules to the turn's execution history — duplicate calls, error counts, cycle depth — not to
propositional content. Control does carry a per-action risk classification (cache a safe
read, block a repeated critical call, freeze for human authorisation), but that is a static
class on individual actions inside one fixed loop. It operates as a **single global mode**:
it does not graduate assurance per request, derive the required level from beliefs about
the request, restrict the admissible plan space by level, or calibrate model-stated
confidence. Those four are what we add — over a belief base the symbolic layer decides on,
rather than a metaprompt the model is asked to obey.

Nearby in the belief layer itself: Nous caps belief reliability by channel provenance
[arXiv:2606.22030], MemIR types memory by provenance to prevent source collapse
[arXiv:2605.25869], Eywa promotes facts only after validators pass against immutable
evidence [arXiv:2605.30771], and HEP makes hypothesis evolution auditable — though all
validated evidence moves belief equally, with no provenance hierarchy gating promotion
[arXiv:2607.09195]. The garden-of-forking-paths problem — agents that propose and score
hypotheses on the same data — is diagnosed empirically in [arXiv:2607.01507] without a
mechanism; §6.3's propose/score partition is one.

MINERVA/HADD is the closest antecedent of the belief layer itself, and read in full
(2026-08-26) it supplies **mechanism, not vocabulary** [Zenodo 10.5281/zenodo.20003407].
The HADD invariants already contain: the LLM confined to a typed sensor that never makes
control-flow decisions; a deterministic cognition layer that is a pure function of the
belief base — "same state → same action", which is the guarantee form §6.2 adopts; an
epistemic admission gate on beliefs at the perception boundary (the EVR gate, specified in
a companion paper [Zenodo 10.5281/zenodo.19791686]); an append-only belief history an
auditor can replay; per-belief numeric confidence with adaptive calibration (EMRE); and
the Kautz Type-2 framing. Its scope is general — goal generation, plan selection and
execution control are all deterministic over beliefs about concrete state — within a
pre-verified plan library and a fixed topology.

What HADD does not have is what §6.2 adds: provenance as a **typed hierarchy with
admissibility semantics** rather than a traceability field; the rule that elicited
assertions are inadmissible for irreversible actions (HADD's nearest device is mandatory
human confirmation, a consent mechanism, not an epistemic one); assurance **graduated per
request** — HADD's guarantee is uniform, its only adaptive dial a per-tenant escalation
threshold; the admissible **pattern space bounded by level** — HADD bounds its plan
library globally; and **measured** calibration (EMRE learns confidence but never measures
it — no ECE, no reliability diagrams). Paradigm selection, abstention and deferral are
outside HADD's scope entirely.

**Delegation contracts and attested identity.** The nearest neighbour on the routing side
is the *provenance paradox* in multi-agent routing [arXiv:2603.18043], and it is close
enough that the overlap has to be stated rather than left for a reviewer. Its result is
that routing on **self-reported** quality selects the worst delegates and performs worse
than random (0.55 against 0.68), and its remedy is deterministic governance: delegation
contracts that bound authority through explicit objectives, budgets and failure policies,
plus a **claimed-versus-attested** identity model so routing consumes verified metrics
instead of claims. It is empirical, with simulated delegates and real models, and the
attested arm reaches near-optimal routing.

Two things follow, and one of them narrows what we may claim.

*It corroborates the sensor discipline from an adversarial direction.* Our reason for
refusing the model's self-assessment as an admissible input is epistemic — an assertion
about its own sufficiency has no provenance above `ELICITED`. Theirs is adversarial — a
delegate has an incentive to inflate. The two arrive at the same prohibition, and
`claimed`/`attested` is close to `ELICITED`/`OBSERVED` restricted to one proposition.

*It occupies "provenance + routing + contracts" as a phrase, so the conjunction must be
stated by what it excludes.* Their provenance is a property of a **delegate's quality
claim**; ours is an ordering over **evidence types**, and the ordering is what a rule
reads. They report no lattice, no floor on irreversible actions, and no risk-coverage
curve — they measure routing accuracy. What remains ours is the conjunction of: a
provenance **lattice over evidence**, a **floor that gates irreversible actions** on it,
abstention priced as a **measured risk-coverage curve**, and the same calculus applied
across feasibility, control and content. Any single term of that has prior art.

## 2.5 Selective prediction and learning to defer

Our theory is an application of an established framework. Chow's rule gives optimal
rejection; Mozannar and Sontag give a consistent surrogate for deferral to an expert
[PMLR v119]; Verma and Nalisnick add calibrated one-vs-all deferral [arXiv:2202.03673];
Mohri and colleagues give principled multi-expert formulations. We contribute the
application to paradigm selection and the specific corollaries in §5.1, not the framework.

## 2.6 Agents that learn without weight updates

Experiential memory approaches — ExpeL, experiential reflective learning, MemSkill, R²-Mem
— accumulate insights, rules or memory entries. Sleep-time compute shifts inference to idle
time and reports ~1/5 the tokens at inference [Letta]; SCM and related work add
biologically-inspired consolidation [arXiv:2604.20943, arXiv:2605.26099]. All consolidate
*content*. §6.3 consolidates the *control policy*, and the claim survives a dated search
(2026-08-26) only as a conjunction, so we state it as one: the policy is learned from the
agent's own episodes, consolidated offline, into a versioned deterministic artifact
executed outside the LLM, over structural task features. Each conjunct has a strong
neighbour. Trace2Policy distills control from *expert* traces into rule bases that are
injected back *as prompt text* [arXiv:2606.10457]; declarative policy compilation gives
orchestration policies exactly the artifact form we want — deterministic, auditable,
versioned — but *human-authored* rather than learned [arXiv:2603.27299]; compositional
meta-routing learns an interpretable router offline, over textual rather than structural
features [arXiv:2608.00106]. None learns its own control policy into such an artifact.

## 2.7 Evaluation and judges

We deliberately use no LLM judge. A large-scale study across 21 models and 541,000
judgments reports reliability without validity, and that raw agreement overstates
discriminative ability [arXiv:2606.19544]. RAGAS-style metrics exhibit position, verbosity
and self-enhancement bias, and the recommended mitigation is repeated runs with spread
inspection. Since our effect sizes are single-digit percentage points and judge variance is
of the same order — and since verbosity bias would systematically favour the expensive
paradigms whose value is in question — a judge would introduce a bias aligned with the
hypothesis. §6.1 explains the alternative.

On failure attribution, MemFail isolates memory-system failures into summarisation,
storage, retrieval and reasoning modes, and can attribute an error to one of them only
because the intermediate operations are recorded [arXiv:2605.26667] — convergent with
§8.4's requirement, though their attribution itself runs on an LLM judge where ours runs
on deterministic tool traces. Their headline is also ours in miniature: scaling retrieved
memories or model strength yields little and sometimes degrades, task-dependently.

## 2.8 Positioning

| | coverage | deterministic decision | auditable | feasibility filter | abstention |
|---|---|---|---|---|---|
| AFlow / ADAS / GPTSwarm | offline, single workflow | no | no | no | n/a |
| Select-then-Solve | 1.0 | no | no | no | no |
| FlowBank | 1.0 | no | no | no | no |
| TRACE-Router | 1.0 | no | no | no | no |
| SCL | global mode | yes | yes | no | no |
| **This work** | **selective** | **yes** | **yes** | **yes** | **yes** |

---

# 3. Preliminaries

A **task** `t` supplies a question, a set of *units* (documents), a declared token budget,
and flags for irreversibility and shared-state writes. A **paradigm** `p ∈ P` is a control
structure that may call tools and must emit an answer. **Quality** `q(t,p) ∈ [0,1]` is set
F1 against an exact oracle. **Cost** `c(t,p)` is total tokens over every call the paradigm
makes.

The **best fixed paradigm** is `p⋆ = argmax_p E_t[u(t,p)]`. The **oracle** is
`E_t[max_p u(t,p)]`, and the **oracle gap** is their difference. Utility is
quality net of a cost preference:

```
u(t,p) = q(t,p) − λ · (c(t,p) / min_{p'} c(t,p') − 1)
```

Normalising by the cheapest paradigm on that task makes λ interpretable — the quality one
will trade for one extra multiple of the minimum cost — and λ=0 recovers pure quality
exactly. **No single λ is chosen**: raw quality and raw cost are stored unmodified and the
trade-off is applied at analysis time, so results are reported as a function of λ rather
than under an assumption about it.

The seven paradigms are Direct, CoT, ReAct, Map-Reduce, Plan-Execute, Reflection, and a DAG
with verify-replan over a shared blackboard. Five mirror the Select-then-Solve grid so
numbers can be checked against theirs; Map-Reduce is added because it should win on high
cardinality, and the DAG because a comparison that omits the most elaborate available
topology is stacked in favour of the simple ones.

---

# 4. Feasibility is arithmetic

## 4.1 The check

Whether `p` can run `t` depends on quantities `t` already declares. With `n` units, content
`C` tokens, budget `B`, and an allowance `A = 0.6·B` that leaves room for the conversation:

| paradigm | binding constraint | infeasible when |
|---|---|---|
| Direct, CoT | one prompt holding every unit | `C > A` |
| Map-Reduce | one call per unit, then a reduce over all partials | `n > 80` or `n·f > A` |
| DAG | sub-questions × iterations × replans | projected calls > 200 |
| ReAct, Reflection | own iteration cap; reads selectively | never |

where `f` is the projected size of one finding. No model call, no statistics, no learning.

## 4.2 It separates two failure modes that are routinely conflated

Applied to **168 tasks across five corpora** from the same generator, each task carrying
its own declared budget:

| corpus | tokens/unit | units/task | max content | Direct, CoT | Map-Reduce |
|---|---|---|---|---|---|
| gold_v2 | 232 | 60 | 16k | 39/39 | 39/39 |
| gold_v3 | 2,147 | 60 | 152k | 12/39 | 39/39 |
| gold_wide | 264 | 500 | 135k | 20/32 | **18/32** |
| gold_deep | 7,161 | 60 | **483k** | 2/26 | **26/26** |
| gold_xl | 2,499 | 500 | 1,272k | 8/32 | 18/32 |

Feasible tasks over total. The four remaining paradigms are feasible in **168/168**.

Aggregated over paradigms, the admissible plan space contracts monotonically with scale —
**273/273 cells on gold_v2, 186/224 on gold_wide, 134/182 on gold_deep, 162/224 on
gold_xl**: from 100% admissible down to 72%, entirely by arithmetic and before any token is
spent. A selector operating without this layer would have to learn that quarter of the
space is unreachable, one failed episode at a time.

**The decisive pair is gold_wide against gold_deep.** gold_deep carries 3.6× more content,
and Map-Reduce moves from 18/32 feasible to **26/26** while Direct and CoT collapse to
2/26. Total size does not predict Map-Reduce's feasibility; **cardinality does**. At 483k
tokens over 60 units it runs, because it never holds them together. At 135k over 500 units
it does not: 501 calls, and a reduce concatenating 500 findings. Treating its limit as a
context limit leads to discarding it exactly where it works.

The same accumulation bound applies to the DAG's blackboard, which renders every finding
into every sub-agent prompt.

**How hard the read-everything constraint bites is easy to underestimate.** In gold_deep a
*single-unit* task is infeasible for Direct, because one document is 8,075 tokens against
an allowance of 4,800. The constraint is not "the corpus is large" but "the smallest
addressable piece already does not fit", and no amount of selective reading changes that
for a paradigm whose only move is to read.

**A second reading worth stating plainly.** The four selective paradigms are feasible in
every one of the 168 tasks. That is a real property — they cap their own iterations and
read on demand — but it also bounds what this layer can do. Feasibility constrains only
paradigms that either hold material in context or fan out per unit; **it offers no
protection against a selective paradigm spending its way through a 1.27M-token corpus**.
That protection has to come from a budget, not from arithmetic over the corpus, and §7.2
shows why it is needed: the selective paradigms are exactly the ones whose cost varies
fifty-fold.

## 4.3 Why this belongs in front of the learning problem

Feasibility is deterministic, free, and upstream of everything else. It prunes the plan
space before any selection, learned or otherwise. **The corollary for production is that
knowing the length and declining is not a degradation** — it is the difference between a
bounded system and a runaway.

\1

**Measured, and the distinction is not academic.** On four gold_deep cells, Direct was
pruned on three and ran on one, where it scored 1.000. Recorded as wrong answers those
three would make Direct's mean 0.250 — the worst paradigm in the table. Recorded as
infeasible, the statement is the accurate one: *best where it can run, unavailable where it
cannot.* The same layer that protects the study from a false conclusion is the layer a
production system needs to decline instead of failing.

---

# 5. Theory

**Neighbouring work read on 2026-08-28, and what it takes from the claim.** Four papers
were outstanding. Three of them occupy, individually, mechanisms this paper had been
treating as its own.

| work | what it occupies |
|---|---|
| **EnvProbe** — *Ask the World Before Acting: Budgeted Environment Probing for World-Model Calibration* (arXiv 2606.31422) | a **budgeted probing operator whose only purpose is to repair a structured belief table**. That is our probe, mechanism for mechanism |
| **Kintsugi** — *Learning Policies by Repairing Executable Knowledge Bases* (arXiv 2605.09487) | **verifier-gated edits to a typed executable artefact**, with failures diagnosed and localised into candidate edits. That is our consolidation plus its promotion guard |
| **ProvenanceGuard** — *Safeguarding LLM Agents from Misalignment through Provenance Analysis* (arXiv 2607.01236) | misalignment as **whether a proposed tool call is supported by traceable evidence in context**. That is our provenance floor on actions |

And the area is populated enough to have been surveyed: *From Agent Traces to Trust: A
Survey of Evidence Tracing and Execution Provenance in LLM Agents* (arXiv 2606.04990).

**So the honest position is narrower than we had it.** Budgeted probing into a typed belief
state, verifier-gated policy edits, and provenance floors on actions are each established.
None of the three is ours to claim, and saying so costs less than being told.

What remains is a **conjunction**, stated by what it excludes: a decision layer that (a)
chooses **which control-flow topology to run**, per request, from a catalog of them — none
of the three routes among *paradigms*; (b) can **abstain**, with the risk–coverage curve
reported rather than the utility of what it chose to answer; and (c) prunes by **arithmetic
on the declared budget before any inference**. Remove any one and the remainder is covered
by the work above.

**And one of the four supports us, from a place we cannot reach.** *Trace2Policy: From
Expert Behavior Traces to Self-Evolving Decision Agents* (arXiv 2606.10457) reports a
22-day production deployment over 3,349 resolved cases and finds that **across five model
scales, the variance attributable to rule version exceeds that attributable to model
choice**. Independent, at production scale, and the closest thing to external corroboration
this line of work has: the structure decides more than the model does.

---

## 5.1 The Selection Value Theorem

Let `p⋆` be the fallback and `p_1 … p_k` the specialists. Let `Δ_j(t) = u(t,p_j) − u(t,p⋆)`.
For each arm, partition the task space **in three** — the third part is not a technicality,
and §5.1.1 shows what collapsing it costs:

```
S₊ʲ = { Δ_j > 0 }   strict gain    π_j = Pr[S₊ʲ]
S₀ʲ = { Δ_j = 0 }   tie            τ_j = Pr[S₀ʲ]
S₋ʲ = { Δ_j < 0 }   strict loss    ν_j = Pr[S₋ʲ]
```

and let, **conditioned on what was actually routed**,

```
α_j = Pr[r → p_j | S₊ʲ]      G_j = E[  Δ_j | r → p_j , S₊ʲ ]
β_j = Pr[r → p_j | S₋ʲ]      L_j = E[ −Δ_j | r → p_j , S₋ʲ ]
```

**Theorem 1.** For every `k ≥ 1`,

```
V(r) − V(p⋆)  =  Σⱼ ( π_j · α_j · G_j  −  ν_j · β_j · L_j )
```

*exactly*, with no independence assumption. Hence selection beats the best fixed paradigm iff
`Σⱼ π_j α_j G_j > Σⱼ ν_j β_j L_j`.

*Proof.* `V(r) − V(p⋆) = E[Δ_{r(t)}(t)·1{r(t) ≠ p⋆}]`. Decomposing by destination gives
`Σⱼ Pr[r→p_j]·E[Δ_j | r→p_j]`, and splitting each conditional expectation by the sign of
`Δ_j`: the `S₊ʲ` part carries weight `π_j α_j` with mean `G_j`, the `S₋ʲ` part carries
`ν_j β_j` with mean `−L_j`, and **`S₀ʲ` contributes exactly zero** because `Δ_j = 0` there. ∎

Two choices make this exact rather than approximate. Conditioning `G` and `L` on the
*routed* subsets removes any independence assumption between where gain lives and where the
router chooses to go. Decomposing **by destination** rather than by a single "specialist"
makes it hold for a catalogue: with `k` arms, misrouting has a *destination*, and sending a
task to a slightly worse arm is not the same event as sending it to the worst of twelve.

**Corollary 1 (precision over coverage).** When `p⋆` is near-optimal over wide regions, `G`
is small and `L` large, so the condition demands `β → 0` even at the cost of `α`. Recall is
not the objective.

### 5.1.1 Ties are not misroutes

`S` is defined by a *strict* inequality, so ties fall outside it. An earlier statement of
this theorem defined `β` over the complement of `S₊`, which charged a router for routing on
a tie — an act that costs exactly nothing. Constructed: a router that routes only where it
gains or ties, and never where it loses, records **β = 0.714 with zero harm done**.

The product `β·L` was still correct, because `L` absorbed the zero. But `β` alone stopped
being the misroute *rate*, and Corollary 2 uses `β` and `L` separately. Defining `β` over
`S₋` restores the reading a reader expects, and leaves Theorem 1 untouched: ties contribute
zero to both sides.

This is not a corner case in any catalogue where several paradigms solve the same task. In
ours, one arm is the cheapest at a tie in 46 of 96 cells.

### 5.1.2 The impossibility threshold, and the loss it must be measured against

Define, per arm,

```
L̄_j = E[ −Δ_j | S₋ʲ ]     the task distribution's mean loss   (independent of the router)
ρ_j = L_j / L̄_j           the router's LOSS SELECTIVITY       (ρ_j := 1 when β_j = 0)
```

**Corollary 2.** The router loses to always-fallback iff
`Σⱼ π_j α_j G_j < Σⱼ ν_j β_j ρ_j L̄_j`, and for a single arm

```
β_max(ρ) = π · α · G / ( ν · ρ · L̄ )
```

| `ρ` | the router | the threshold |
|---|---|---|
| **ρ = 1** | **blind to loss magnitude** — its mistakes are distributionally representative | the classical statement, and there it is exact |
| ρ < 1 | avoids the expensive mistakes | **relaxes** |
| ρ > 1 | anti-calibrated: fails where it hurts most | **tightens** |

**Why the parameter is necessary, and not a refinement.** Stated with the distributional
loss alone, the threshold is not an impossibility. Three tasks suffice: a gain of `+0.10` at
probability `0.10` routed; a loss of `−0.001` at `0.45` routed; a loss of `−1.00` at `0.45`
*not* routed. Then `β = 0.500` exceeds `β_max = 0.0222` by 23×, and the router still captures
`+0.00955`. A router that errs *often but cheaply* is exactly what a well-built selective
router produces.

Nor can the realised loss simply be substituted: a perfect router realises no loss, so the
threshold would report infinity and appear to impose no constraint at all — the objection
that motivated the distributional form in the first place. **Both objections are correct.**
They dissolve together once the realised loss enters as a *factor of the loss* rather than
as the *denominator of a threshold*: when `β = 0` the whole term vanishes before `ρ` is
consulted.

**Corollary 2b.** A router obliged to choose controls neither `β` nor `ρ`. A selective one
controls both — and `ρ` is the cheaper lever: lowering `β` requires being right more often;
lowering `ρ` only requires declining where the bet is expensive. This gives Corollary 1 a
mechanism rather than only an inequality, and `ρ` is recoverable from any record that
reports potential and realised loss.

### 5.1.3 Optimal coverage

Let `V(c)` be captured value at coverage `c`, admitted by lowering a confidence threshold.
Then `dV/dc = E[Δ | task marginal at c]`, and therefore:

**(a)** `V` is unimodal **iff** `c ↦ E[Δ | marginal at c]` is non-increasing — that is, iff
the confidence signal orders tasks by *expected gain*. **Calibration alone does not give
this.** Calibration constrains the probability of gaining; the value depends on its
magnitude. Constructed, with `Pr[correct | κ] = κ` exactly in every group: three groups with
`E[Δ]` of `+0.008`, `−0.170`, `+0.593` at confidences `0.90`, `0.60`, `0.30` produce a
captured-value curve that goes **up, down, and up again**, with its optimum at **full
coverage**.

**(b)** Without any assumption: the optimal coverage is `< 1` whenever some task with
`Δ_{r(t)}(t) < 0` would be routed at full coverage. This is what the argument requires, and
it follows in one line — removing a negative term increases the sum.

**Corollary 3.** We claim (b). Claiming unimodality claims more than the design needs, and
concedes a counterexample.

### 5.1.4 The oracle-gap identity, and its scope

With a single specialist, the oracle gap equals `π·G`, which lets a published router's
implied `β` be recovered from its headline numbers. **With `k` arms it does not factor**: the
gap is `E[maxⱼ Δ_j⁺]`, which is not `π_j·G_j` for any fixed pair. The 17.1pp reported for a
published suite may be read as `π·G` only where that work reports a *pair*; over a grid, the
implied-`β` reading is unavailable.

### 5.1.5 What Theorem 1 is, and what it is not

It is an *identity*: an exact algebraic decomposition, true by construction. It cannot be
falsified by any measurement, and nothing in this paper should be read as having confirmed
it. What is empirical is only whether its terms satisfy the inequality on a given
distribution — a question about a router, not about the theorem.

Theorem 1 and the three corollaries are verified in `tests/test_science.py` against
distributions whose terms are known by construction. The identity was additionally checked
over 4,000 random distributions with `k` from 1 to 4 — 3,269 of them containing ties —
with maximum discrepancy `1.67 × 10⁻¹⁶`. Corollaries 2 and 3 are stated in their corrected
form above; the counterexamples that forced the correction are reproduced there.

**And the distinction matters here because the terms were never separated.** Across both
held-out corpora the router's decision margin was **0 on every task**, so the risk–coverage
curve collapses to a single point at the origin: **AURC 0.000** against a ceiling of
**+0.400**. A router that never abstains has no `α` and no `β` distinct from
always-fallback, so the identity holds vacuously — with both terms measured on a coverage
the router did not choose.

> **The work a reader might credit to §5.1 is done by §5.2.** The selection theorem supplies
> the accounting; every falsifiable claim this record actually settled is about cascade
> dominance and detector sensitivity. Presenting them in this order is a presentation
> choice, not a claim of priority — and the honest reading is that the selection branch of
> the partition below has still not been exercised.

**One observation ties the three corrections together.** `π`, `α` and `β` answer *whether*
the router is right; `G`, `L` and `ρ` answer *how much it costs when it is not*. Each place
the earlier statement failed — the threshold, the ties, the unimodality — is a place where
those two axes were treated as one.

## 5.2 Cascade dominance, and its measured correction

A **router** that errs pays `L`, a quality loss: a worse answer is delivered and nothing
recovers it. A **cascade** that errs pays `cost(p_1)`, a cost loss: the cheap attempt is
wasted and the good answer still arrives after escalation.

With detector sensitivity `s`, and writing the router's regret for a single arm — the
two-arm case of Theorem 1, which is the comparison a cascade replaces:

```
regret(router)  = ν·β·ρ·L̄
regret(cascade) = E[ladder cost] + (1−s)·L
```

**A correction we owe to measurement.** An earlier statement of this result gave the cost
term as `cost(p_1)`. That is false. When no rung satisfies the detector the cascade runs the
*whole ladder*: in our synthetic study it captured 100% of the gap at **4.4×** the cost of
the best fixed paradigm. The bound is the expected ladder cost, and the pattern requires a
budget cap.

**Detector sensitivity is the critical variable, and a weak detector is catastrophic rather
than merely suboptimal.** At `s = 0.6` the captured fraction measured **−5.98**: a missed
failure leaves the cascade halted on a cheap rung with a bad answer. This is the structural
analogue of Corollary 2 — as a router with high `β` loses, a cascade with low `s` loses, and
loses harder.

**Corollary (the verifiability partition).**

```
v = 1  (a cheap oracle exists)  ->  cascade; no router needed
v = 0  (no oracle)              ->  route, under the discipline of Theorem 1
```

Prediction is only necessary where verification is impossible. If this holds, much of the
routing literature is solving the wrong problem in the verifiable regime.

**And the partition has a sharp methodological consequence we paid to learn.** The `v = 0`
branch is the one that needs a router, and it is precisely the branch an exact-match
benchmark cannot contain: gold is what makes grading judge-free, and gold is a detector. In
this record the conflation was literal — one field served as both — and the result is that
two pre-registered routing predictions, on two independent held-out corpora, were answered
by the cascade rule while the selection rule was never evaluated. The numbers are real; what
they measure is the `v = 1` branch.

Separating the two is not a tuning change. It requires a corpus that **declares detector
availability per task** on grounds independent of the answer key — for us, whether verifying
is cheaper than solving — and it moves the cascade from firing on 22 of 26 tasks to firing
on 2.

---

# 6. Design

## 6.1 Measurement without a judge

Every task carries a set-valued oracle, so quality is set F1 after normalisation. §2.7 gives
the reason: the effect is single-digit percentage points and judge variance is of the same
order, so a judge would not merely add noise but a bias — verbosity bias favours the long
answers that the expensive paradigms produce, which is precisely the comparison under test.

An empty oracle is a legitimate and important question — *list every X* where no X exists —
and it tests whether a paradigm invents items. It is graded by requiring an explicit
statement of emptiness; silence scores zero, because a paradigm that returned nothing
because it crashed must not score as one that looked and reported finding nothing.

## 6.2 Beliefs, provenance, and per-request assurance

Full determinism is unavailable for an LLM, and pursuing it by excluding the model from the
decision discards information the model has. The inversion is HADD's (§2.4): the model is a
**sensor** that emits typed propositions, a deterministic symbolic layer decides over the
belief base, and the guarantee takes the only shape it can have:

> not *"the same prompt yields the same answer"* — false, always
> but *"the same belief base yields the same decision"* — HADD's decision stability,
> with the base recorded

What this section adds is the **epistemology of the belief itself**. In HADD, provenance is
a traceability field; here it carries the decision weight as a typed hierarchy: `COMPUTED`
(a pure function, credence 1.0) > `OBSERVED` (measured by executing a probe) > `ELICITED`
(the model asserted it, subject to calibration) > `ASSUMED`. A rule may demand a minimum
provenance, so an irreversible action can be restricted to computed and observed evidence:
*a model's opinion that an action is safe is not admissible evidence for taking it.*

Assurance is then a property **of the request**, not of the system. A global mode makes all
traffic pay for the strictest request. Four levels graduate the provenance floor, whether θ
may learn online, whether the run is replayable from cache, and **which patterns are
admissible** — the certified level excludes topologies whose control flow is unbounded, not
because they are worse (they are often better) but because their failure modes are not
enumerable. The floor is derived from beliefs about the request: a caller may ask for more
and never for less. The derivation itself learns, offline: a request category whose
elicited assertions are repeatedly refused by the gate is a category whose floor rises —
rejection statistics are evidence about the request class, and consuming them closes the
loop without ever adjusting anything inside a request.

Three properties make that safe to run, and each is enforced rather than intended.

**The event is typed, not parsed.** A refusal carries why it happened as a value — the
provenance held against the provenance the rule demanded — so the statistic counts the
event. Counting it by matching substrings of the explanation would measure the phrasing,
and the phrasing is prose that gets reworded. Only refusals for insufficient PROVENANCE
count: a belief refused for low credence, or for holding the wrong value, is the system
working, and says nothing about the evidence regime of the class.

**The guard is replication, not utility.** The record is split by task; one half proposes
the regions whose floor should rise, and the floor is installed only if the other half —
requests the proposal never saw — says the same thing independently. Utility would be the
wrong criterion here and rejecting it is not a concession: raising a floor makes the
system demand measured evidence where it would have acted on an assertion, which costs
tokens and can only lower measured utility in the short run. A governance floor scored by the utility it produces is a governance floor
that never rises.

**The raise is bounded and monotone.** It stops at accountable and never reaches
certified, because certified also restricts which patterns may run and a statistic about
evidence quality is not evidence about certifiability — a floor that learns must not be
able to disqualify a topology. And it never falls on its own: the absence of refusals
after a floor rises is what the floor was installed to produce, so reading that absence as
grounds to lower it again would be an oscillation built into the design.

The learned floors ride on the signed policy bundle, so nothing can raise a request's
level except through the same promotion path θ takes. Verified: a region whose refusals
replicate across the split has its floor installed; a region that qualifies on the
proposing half alone does not.

Credence and effect size must not be conflated. A learned margin is a *certain* belief about
a *large* effect — credence 1.0, value 0.9 — and encoding the magnitude as credence reports
a computed fact as an uncertain one, destroying the distinction the layer exists for.

## 6.3 Consolidation of the control policy

Learning is offline and copy-on-write. Episodes are replayed in order of *surprise* rather
than chronology, removing the recency bias the online update has by construction; statistics
are downscaled and unused entries pruned; and an abstraction stage searches for feature
partitions that separate paradigms better than the current binning.

Two disciplines make this safe. A candidate policy is installed only if it does not regress
on held-out episodes. And the record is split three ways *by task* — one part proposes
partitions, one scores them, one is touched only by the promotion guard — because searching
many partitions against one holdout is how detecting a truth becomes confabulating one. A
discovered partition enters with zero episodes, below the confidence floor, and cannot drive
a decision until it has earned evidence: **a dream is a hypothesis, not a fact.**

Verified: given a record where utility is independent of every attribute, no partition
survives validation.

## 6.4 The tool surface is part of the topology

Choosing *which* retrieval modality, at *what* granularity, in *what* sequence, with how
much *batching* is the agent's own business — it is the topology. A harness offering one
blunt search and one read has pre-decided all four and then measures what remains.

Four tools at three granularities, with lexical and dense exposed separately alongside the
fused entry point:

| tool | returns | measured size, 3 units |
|---|---|---|
| `search` | summaries | 312 chars |
| `keyword_search` | highlights `<< >>` | 937 |
| `semantic_search` | full text | 3,502 |
| `read` | full text, batched | 3,501 |

**11× between summarising and reading**, and that difference is invisible when every search
returns a fixed-size excerpt. Fusing lexical and dense into a single hybrid tool was a
specific mistake: hybrid is the right default, but exposing only the fused view means the
agent can never request exact matching for an identifier — and the answers in two of our
cells *are* identifiers.

Retrieval quality is a recorded variable with five arms: hybrid (BM25 + dense, RRF fusion),
lexical, semantic, two degraded simulations at stated recall and precision, and an oracle.
The simulations are deterministic functions of `(task, query, unit)`, so retrieval quality is
a controlled dial rather than another noise source. Vectors are cached by content hash, so
after a first pass fusion is local arithmetic.

**A finding against the received view**: on the coupled cell, dense alone measured recall
0.75, hybrid 0.50, lexical 0.25. RRF averages ranks, so a badly performing component drags a
good one down. "Hybrid is always better" does not hold when one component is far below the
other.

---

# 7. Preliminary measurements

> **All numbers in §7 and §8 are n=1 per cell**, on one synthetic corpus, with one model
> (`gpt-5-chat`), under hybrid retrieval. Replicate variance on the DAG topology was
> measured at up to 3.93× in cost. Magnitudes are indicative; mechanisms rest on
> tool-usage traces and are more robust.

## 7.1 The aggregate over four feature cells

| paradigm | mean quality | total tokens | cost range | hallucinated units |
|---|---|---|---|---|
| **Direct** | **0.938** | **46,101** | 1.2× | 0 |
| CoT | 0.938 | 46,272 | 1.2× | 0 |
| ReAct | 0.688 | 116,524 | **27.6×** | 0 |
| Reflection | 0.688 | 126,254 | 6.9× | 0 |
| Map-Reduce | 0.438 | 62,321 | 1.2× | 0 |
| DAG | 0.438 | **439,319** | 24.5× | 0 |
| Plan-Execute | 0.250 | 123,175 | 2.0× | **78** |

The simplest paradigm wins on quality and is simultaneously cheapest; the most elaborate
returns less than half the quality for 9.5× the cost.

**This is governed by a validity threat we state rather than bury**: on this corpus every
task fits in one prompt, and in that regime reading everything is optimal and the ordering is
close to tautological. §4 exists to escape it, and §9 records that the escape is built but
not yet measured.

## 7.2 Tool quality governs the variance that topology is credited with

| group | cost range |
|---|---|
| do not use tools (Direct, CoT, Map-Reduce) | **1.2×** |
| use tools (ReAct, Reflection, Plan-Execute, DAG) | **50×** |

Tool quality does not shift the mean; it governs the variance — and asymmetrically. The
readers are expensive and stable; the searchers are cheap-or-ruinous, and which face the coin
shows is decided by retrieval. A paradigm costing between 2,877 and 251,374 tokens depending
on whether search worked is not something one can budget for.

**Implication**: a benchmark that does not report the quality of its tool surface is not
measuring topologies. It is measuring its retriever wrapped seven ways.

## 7.3 An A/B on three accounting signals, and what a replicate did to it

Same corpus, same retriever, same four cells; the only difference is the tool surface,
recorded as a variable per row.

The three paradigms that use no tools were **identical to the token** across arms. That
control is what makes the rest attributable; without it any difference could be run noise.

A third arm added four working-memory tools (`note`, `notes`, `plan`, `advance`) and
produced a result we did not plan for. **The model never called them**: across 28 rows,
one note, one compaction and zero plans. On a corpus where everything fits in one prompt
there is no context pressure, so a working-memory tool has no work to do — exposing a
capability is not the same as providing one. That arm is therefore a null result on the
tools, and something more useful: an accidental **replicate** of the accounting surface.

As a replicate it says what the aggregate hides. **Reproducibility is per-task, not
global.** On three of the four cells, 10 of 10 quality values are identical across the
pair. On the fourth — the three-hop chain — 2 of 4 flipped, and both flipped by the full
unit. The instability is not spread thinly across the study; it is concentrated in the
hardest task, where the outcome is bimodal. Cost was reproducible nowhere: mean spread
2.05×, maximum 5.43× at *identical* quality.

That converts the A/B from a list of effects into a list of effects with an attribution
test. An effect that moves only the coin-flip cell is not attributable; one that moves a
reproducible cell is.

| paradigm | Δ reported | cells moved | attributable | verdict |
|---|---|---|---|---|
| DAG | +0.500 | c3 (unstable), c5 (stable) | **+0.250** | half survives |
| Reflection | +0.250 | c3 (unstable) only | **0.000** | **withdrawn** |
| ReAct | +0.000 | none | 0.000 | null, confirmed |
| Plan-Execute | −0.139 | c2, c5 (both stable) | **−0.139** | survives |

**We withdraw the Reflection result.** It came entirely from the cell that flips on its
own, and at n=1 it is indistinguishable from noise.

**The DAG's cost result survives, and it is the strongest thing here.** Total cost fell
**3.05×** against a replicate spread of 1.62× on the same measure, and it fell exactly
where the mechanism predicts: the two runaway cells, 251k → 51k and 143k → 10k, both
carrying stall warnings. The other two cells did not fall at all. So telling an iterative
loop that its retriever has stopped producing is worth a 3× cost reduction with the
mechanism visible in the trace — while the quality gain that accompanied it is half what
we first reported.

**Plan-Execute's degradation survives, and on reproducible cells**: +0.444 on one and a
full −1.000 on another. Our own analysis had called coverage accounting "the
highest-leverage addition" for this paradigm. It made it worse. Knowing the answer is
incomplete is useless when the architecture cannot complete it: the sub-agents have
finished by the time synthesis learns units are missing. **A diagnostic without the
capacity to act is worse than none** — and this is the one A/B effect that both moved
stable cells and contradicted our prediction.

**A second-order effect we did not predict.** `read_all` reduced the cost of a full read by
7.6× and raised ReAct's net cost by 27%: it cheapened the *act*, and therefore the
*decision*, of reading everything.

**One cell did not run.** Two rows recorded zero tokens and an empty answer — not a wrong
answer but an absent one. They are excluded from every figure above rather than scored as
zero, since a paradigm that never executed must not be pooled with one that answered
badly. Both belong to the cells marked *sin-correr* in the artefacts.

## 7.4 The two-regime study, with replicates

> Second study, run 2026-08-26 with predictions P1–P5 registered beforehand (harness
> README). Matched task sets on `gold_v2` (in-window, ~18k tokens) and `gold_deep`
> (out-of-window, ~483k), `repeat = 3`, per-cell stability tracked. 126 + 158 valid
> rows. Two heavy out-of-window cells (`react`/`reflection`/`dag` on c2-w48 and c5-w48)
> carry fewer trials than the rest; their means below are marked † and should be read
> with that smaller `n`.

The feasibility sweep, first, because it costs nothing: at 135k tokens the arithmetic
prunes read-everything on 12 of 32 tasks; at 483k on **24 of 26**; at 1.27M on 24 of 32 —
and at that scale the pruning reaches `map_reduce` on 18–20 tasks, whose projected spend
exceeds the declared budget (P1, confirmed). In-window, nothing is pruned. The regime
claim is arithmetic, not measurement.

**In-window (per-cell mean utility / mean tokens; flips = cells whose utility changed
across replicates):**

| paradigm | C2 | C3 | C4 | C5 | flips | cost median (spread) |
|---|---|---|---|---|---|---|
| `direct` | 0.75 / 13k | **1.00** / 11k | 1.00 / 13k | **1.00** / 11k | **0/6** | **10.5k (1×)** |
| `react` | 0.75 / 25k | 0.67 / 63k | 1.00 / **3k** | 1.00 / 61k | 3/6 | 23.8k (**70×**) |
| `map_reduce` | 0.75 / 16k | **0.00** / 14k | 1.00 / 16k | **0.00** / 16k | 0/6 | 15.1k (1×) |
| `plan_execute` | **0.00** / 27k | **0.00** / 11k | **0.00** / 32k | 0.33 / 29k | 1/6 | 19.0k (12×) |
| `reflection` | 0.83 / 31k | 0.44 / 40k | 1.00 / 8k | 0.67 / 113k | 3/6 | 21.2k (27×) |
| `dag_strategy` | 0.75 / 27k | 0.33 / 77k | 1.00 / 6k | 0.67 / 66k | 3/6 | 33.1k (**82×**) |

**Out-of-window (same convention; `direct` infeasible except on the small tasks):**

| paradigm | C2 | C3 | C4 | C5 | flips | cost median (spread) |
|---|---|---|---|---|---|---|
| `direct` | INFEASIBLE | INFEASIBLE | INFEASIBLE | 1.00 / 23k* | 0/8 | 22.9k (1×) |
| `react` | 0.97† / 61k | **1.00** / 14k | 1.00 / 18k | 1.00† / 40k | **0/7** | **14.6k** (40×) |
| `map_reduce` | 0.95 / 107k | **0.00** / 276k | 1.00 / 29k | **0.00** / 23k | 1/8 | 28.7k (15×) |
| `plan_execute` | 0.62 / 88k | 0.33 / 18k | 0.33 / 80k | 0.33 / 94k | **4/8** | 34.4k (52×) |
| `reflection` | 1.00† / 106k | 1.00 / 50k | 1.00 / 17k | 1.00† / 89k | 0/7 | 30.0k (47×) |
| `dag_strategy` | 1.00† / 50k | **0.67** / 86k | 1.00 / 14k | 1.00† / 26k | 1/7 | 21.0k (59×) |

\* only on tasks whose own evidence fits: pruning is per task, not per corpus.

Three findings the first study could not see:

**The ranking inverts with the regime, per prediction and beyond it.** In-window, the
readers dominate on quality, cost and stability at once. Out-of-window they do not exist,
and the paradigms the first study ranked last — `react`, `reflection`, `dag` — hold the
top of the table. `plan_execute` is the exception in both regimes: no winning region,
and out-of-window it is the least stable thing measured (4 of 8 cells flipped).

**`map_reduce`'s coupled-cell zero is structural, and now measured at two scales** (P3,
confirmed): 0.00 in-window and 0.00 out-of-window, deterministically — its failures do
not even flip. §8.3 carries the cost half of this.

**Stability lives where retrieval does not decide.** In-window, the tool-using paradigms
flipped 3 of 6 cells each while the readers flipped none. Out-of-window, `react` flipped
none of 7 — with no read-everything competitor, its search actually has a job it can
finish — and the instability migrated to `plan_execute`. Variance is not a property of a
paradigm; it is a property of *who is being asked to decide when to stop*.

## 7.5 The elaborate topology against the general fallback

The question this study exists to answer in place of the withdrawn field report: does the
most elaborate topology beat the general fallback? The measured answer is that the
question is regime-shaped — and that where it matters most, the differentiator is not the
topology.

In-window, `dag_strategy` is the worst purchase measured: the widest cost spread (82×,
3.1k to 251k on identical task sets), a 0.33 on the coupled cells that `direct` solves
for 11k, and 3 of 6 cells flipping between replicates. Out-of-window it transforms:
perfect utility on C2, C4 and C5 at costs that rival or beat `react`'s†.

Except on the deep coupled chain, where it produced the single worst row of the study:
**395,960 tokens over 35 iterations for a zero**, on a task `react` solves at 10–14k with
utility 1.0 across all three replicates. This run used the **basic** surface — no
accounting signals — and the trace shows the §8.2 mechanism at scale: the verifier keeps
finding the answer incomplete, the replan keeps widening, and nothing in the environment
says *stop*. §7.3 measured that the signals cut exactly this loop by 3.05×. Together the
two results say something sharper than "DAG loses": **the elaborate topology is viable
out-of-window only under externally imposed accounting — the intelligence of the loop is
not what was missing.**

## 7.6 Two paradigms enter by registered prediction — one survives

Against the two failure roots §8 identifies that no existing paradigm attacks cheaply, we
added two paradigms with predictions registered before running (P6–P7, harness README)
and screened them on the out-of-window discriminating tasks.

**`rewoo`** — every tool call planned in one pass with explicit dataflow placeholders,
executed without the model in the loop, one solving call; two LLM calls total, no history
resend [ReWOO, arXiv:2305.18323]. Both registered predictions held, the first
beyond its stated bound: quality identical to `react` on independent coverage (0.88 on
C2, 1.00 on C4) at **3–8% of react's cost** on the same cells (prediction said ≤50%), and
utility 0.00 on the coupled and unknown-horizon cells — a plan that cannot observe cannot
discover the hop that depends on a prior result. Its utilities were identical across
replicates in all four tasks. A textbook Theorem-1 specialist: large G inside a sharply
bounded region, total failure outside it.

**`gist_reader`** — a deterministic per-unit gist table in one prompt, then targeted
batched full reads. **Its headline prediction was falsified**: u ≥ 0.75 was predicted on
three cells and reached on one (C5: 1.00 at 8k where `react` pays 20–103k); on bulk
coverage and exact aggregation the 312-character gists do not carry the datum (0.29 on
C2, 0.00 on C4) — precisely the summary-failure mechanism the secondary prediction named.
Its cardinality bound also behaved as registered: the gist table goes infeasible by
arithmetic on 400-unit tasks, recorded free. The paradigm stays measured and
unpromoted. We report it at the same length as the success on purpose: the registered
prediction discipline is only worth having if a falsification costs a paragraph rather
than a retraction.

---

# 8. Failure mechanisms

These rest on traces rather than magnitudes, and they are what we would defend.

## 8.1 Decomposition destroys sequential dependency

Both decomposing topologies fail both coupled cells, and both **with the evidence read**.
The DAG spent 251,374 tokens on the three-hop chain, read 4 of 4 chain units, and scored
zero. A chain is sequential by definition — hop 2 cannot be formulated before hop 1 is
answered — so splitting it into parallel sub-questions leaves the blackboard holding the
right units without the structure that orders them. This is a property of decomposing, not
a coincidence of two implementations.

## 8.2 Iterative loops amplify retrieval failure rather than absorbing it

On the two-hop cell the DAG issued 31 keyword searches, read **zero** relevant units, and
spent 142,694 tokens. After the third search the retriever had already demonstrated it would
not find the target; the verify-replan loop read that as *search again*.

This inverts a design intuition. Verification loops are added *for* robustness; here the loop
is the amplification mechanism. Without it the failure would have cost 10k tokens rather than
143k.

## 8.3 One failure no tool can fix

Map-Reduce fails both coupled cells and reads zero relevant units in all four, because by
construction it views each unit in isolation. A chain and a cross-unit comparison are
unresolvable that way however many times they are examined.

The fix is not a better tool but a refusal: coupling is a declared property of the task,
so the feasibility layer can exclude the paradigm before any token is spent — which is
cheaper than any amount of learning that it loses.

**And the price of that failure scales with the corpus while the failure does not.** The
same paradigm, on the same cell, at two unit sizes:

| corpus | units | calls | relevant units read | cost | quality |
|---|---|---|---|---|---|
| gold_v2 | 48 | 49 | **0** | 13,931 | 0.000 |
| gold_deep | 48 | 49 | **0** | **276,355** | 0.000 |

Identical cardinality, identical call count, identical zero — and **19.8× the cost**. Thirty
times more text per unit bought exactly thirty times more of nothing, because the obstacle
was never the amount of evidence. This is the sharpest argument we have for deciding before
running rather than after: a paradigm whose limitation is structural does not fail more
loudly at scale, only more expensively, and an approach that learns from outcomes pays that
bill every episode until it has learned what arithmetic could have told it for free.

## 8.4 Attribution requires the trace

The tool-usage trace separates *never saw the evidence* from *saw it and reasoned wrongly*.
Without it a zero is a mystery; with it, it is a diagnosis. "The searching topology lost" is
uninterpretable when the searcher never reached a relevant unit — that is a statement about
the tool surface, and only a failure with the evidence in hand is evidence about the control
structure.

---

# 9. Limitations and threats to validity

**The in-window regime is near-tautological, and §7.4 is the escape — partially walked.**
The corpus behind §7.1–7.3 is 16k tokens at its widest, so read-everything is both correct
and cheapest there. The out-of-window regime is now measured at 483k with `repeat = 3`
(§7.4–7.5), and the regime claim across 135k/483k/1.27M rests on the zero-cost feasibility
sweep. Still open: no full run at 1.27M (only its feasibility arithmetic), and two heavy
out-of-window cells still short of full replication (marked † in §7.4).

**And one item left that list by being answered, in the direction that costs us.** The
held-out world with a fresh seed — generated and independently verified — has now run its
registered transfer test, P8. **Two of its five predictions do not transfer**, so by its own
registered decision rule the per-cell verdicts below are **corpus-local**: claims about
seed-7 worlds, each carrying a per-world caveat. The refutation does not rest on the cells
nobody solved — on the two cells where another arm reaches a perfect score, the general
fallback returns 0.667 and 0.000.

**Replicates exist now, and the noise is per-cell.** The first study's accidental
replicate (§7.3) and the second study's `repeat = 3` agree: reproducibility is per-task —
readers flip nothing, tool-users flip the cells where retrieval decides, and cost was
reproducible nowhere (mean spread 2.05×, maximum 5.43× at identical quality in the first
study; the same concentration pattern in the second). Quality deltas are therefore
reported with their per-cell flip counts, never as bare means. The formal per-cell noise
floor and the net oracle gap (`Study.noise_floor`, decisions against the net gap) are
computed at the final analysis over the completed grid — pending the re-run cells.

**One model, and it cannot be pinned.** `gpt-5-chat` rejects an explicit temperature, so
sampling is at the model default. A reasoning deployment that accepts temperature 0 is
available as an escape but changes what is measured.

**Synthetic corpus.** Ground truth is exact and independently re-derived, and structural
parameters are dials rather than hopes — but the distribution of real tasks over those dials
is unknown. Public benchmarks are required for external validity and are not yet used.

**Latency is not comparable.** The DAG runs sequentially here where it would run concurrent
waves; and once workers contend, per-row wall-clock stops measuring latency. Quality and
token counts remain exact.

**Novelty claims are verified as conjunctions, not as parts.** The two anchor works were
read in full on 2026-08-26: every number cited from Select-then-Solve checks out against
its body, and the concession to SCL stands. The remaining claims — control-policy
consolidation (§6.3), provenance-gated proposition discovery, abstention in paradigm
routing — survive dated searches only as conjunctions whose individual conjuncts each have
a published neighbour (§2.2, §2.4, §2.6). A field moving this fast can close any of them
in months; the searches are dated so a reader can re-run them.

**Reproducibility caveat.** A seed alone does not pin a corpus. When the generation algorithm
changed, the same seed produced a different world; manifests now stamp a generator version and
results across versions must not be pooled.

---

# 10. Conclusion

The prize in paradigm selection is real and measured, and the literature is pursuing it with
selectors that must always choose. We argue that three things belong in front of that
problem. Feasibility is arithmetic and prunes the space for free, separating a cardinality
bound from a context bound that are routinely conflated. Selection pays only under a
condition we can state and check, and the condition implies abstaining most of the time.
And the variance that topology choice is credited with is largely governed by the tool
surface: fifty-fold among tool-using paradigms against 1.2× among those that read.

Our strongest measured result is not about topologies at all. Telling an iterative
topology that its retriever had stopped producing cut its cost 3.05× against a replicate
spread of 1.62×, with the fall localised in exactly the two runaway cells the mechanism
predicts. An unplanned replicate also forced us to withdraw one reported effect and halve
another, which is the discipline working rather than failing. The three largest cost failures we found were not fixed by
better topologies or better models but by accounting signals that did not exist.

What we do not have is a validated selector, a noise floor, or any measurement in the regime
where reading everything is impossible. The harness for all three is built and the protocol
is registered in advance, including the decision rule for the outcome in which no selector
beats the fallback — which would be a result, and is stated as publishable before the data
is in.

---

# Appendix A — Artefacts

| artefact | contents |
|---|---|
| `PATTERNS.md` | pattern catalogue: 10 structural patterns, 4 control patterns, 15 anti-patterns, with applicability stated over the feature vector |
| `ANALYSIS.md` | the failure analysis of §8 in full, per paradigm and per cell |
| `GATE.md` | eight binary publication criteria and their current verdict |
| `PLAN.md` | revision history of the thesis, including two superseded framings and why |
| `D:\Apps\MAPO\lab` | the harness: 7 paradigms, 5 retrieval arms, 3 tool surfaces, 4 assurance levels, corpus generator with independent verifier, 63 machine-checked assertions |

Seven of the fifteen anti-patterns in the catalogue are errors made and measured in the
course of this work, including two that contradicted our own published predictions.
