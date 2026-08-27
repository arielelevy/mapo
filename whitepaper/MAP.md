# MAP — Hebbian Plasticity for Decisions

> Extracted 2026-08-26 from the frozen v1 whitepaper (its Chapter 10 and Appendix B.3),
> the single piece of v1 that MAPO inherits. Recontextualised: in MAPO this is the
> statistics layer that feeds the policy θ (see `../lab/app/policy.py`), with
> Hebbian weights as the interpretable, auditable substrate of the decision list.

# Capability 10: Plasticity and Continuous Learning (MAP)

This capability represents the **main theoretical contribution** of this work: extending the functional agency framework to incorporate **structural plasticity**, enabling multi-agent systems to dynamically adapt their relationships and behaviors based on accumulated experience.

## 10.1 Motivation: From Static Architectures to Adaptive Systems

The multi-agent systems described in previous chapters present a fundamental limitation: **relationships between agents are static**. Once the initial topology is defined (which agents can invoke which others), it remains fixed throughout system operation.

**Problem**: In dynamic environments, optimal routing preferences change:
- An initially reliable agent may degrade
- New query patterns may require different agent combinations
- Repeated errors on a route should reduce its future use

**Solution**: We introduce **MAP (Multiagent Plasticity)**, a theoretical framework that extends functional agency with structural plasticity inspired by neuroscientific principles.

<p align="center">
  <img src="diagrams/10_map_evolucion_en.svg" alt="Evolution from Static to Plastic" width="700">
<br><em>Figure 45: Evolution from Static to Plastic Architectures</em>
</p>

## 10.2 MAP Theoretical Framework

The concept of structural plasticity has deep roots in computational neuroscience. Beyond the classical Hebbian principle (Hebb, 1949), recent works have formalized plasticity mechanisms in artificial networks:

- **Elastic Weight Consolidation** (Kirkpatrick et al., 2017): Protects weights important for previous tasks, mitigating catastrophic forgetting through Fisher matrix-based regularization.
- **Synaptic Intelligence** (Zenke et al., 2017): Measures synapse importance online during training, enabling selective protection of critical connections.
- **Dynamic Sparse Training** (Mocanu et al., 2018): Enables connection growth and pruning during training, maintaining constant sparsity.

MAP adapts these principles to the multi-agent context, where "synaptic weights" represent trust between agents rather than neural network parameters. This adaptation allows the system to evolve its coordination structure based on operational experience.

### 10.2.0 Differentiation from Related Work

MAP explicitly differentiates from related approaches:

| Framework | Trust Mechanism | Topology | Prompt Adapt. | Learning |
|-----------|-----------------|----------|---------------|----------|
| **DyLAN** [Liu et al., 2024] | Importance Score | Per-domain | None | Optimization |
| **GTD** [Jiang et al., 2025] | None | Generated | None | Diffusion |
| **MetaGPT** [Hong et al., 2024] | None | Fixed | Post-project | Offline |
| **DRF** | UCB Reputation | Predefined | None | Bandit |
| **AutoGen** [Wu et al., 2023] | Per-conversation | Static | None | None |
| **MAP** | **Hebbian** | **Evolved** | **Real-time** | **Continuous** |

**Key differentiators:**

- **vs. DyLAN**: DyLAN's importance scores are calculated per-domain, not accumulating collaboration history. MAP implements "fire together, wire together"—trust strengthens with repeated successful collaboration.

- **vs. GTD**: Graph diffusion generates per-task topologies; MAP *evolves* the topology through accumulated experience.

- **vs. MetaGPT**: Prompt modification occurs post-project; MAP applies patches in *real-time* during execution.

- **vs. DRF**: UCB reputation is stateless between sessions; Hebbian weights persist and accumulate.

> **Novel Contribution**: MAP is the first framework combining Hebbian trust dynamics, structural neurogenesis/pruning, and real-time prompt patching for LLM-based multi-agent systems.

### Formal Assumptions

The MAP framework assumes the following conditions, which we consider reasonable in enterprise BI scenarios:

**A1** (Outcome Observability): The reinforcement function <img src="diagrams/formulas/f_delta_o_53cf1498.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> is observable after each interaction. This requires explicit feedback mechanism (user rating) or implicit (re-query detection, abandonment).

**A2** (Local Stationarity): The query distribution <img src="diagrams/formulas/f_p_q_a34619d1.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> is locally stationary during adaptation periods. Abrupt distribution changes (e.g., organizational restructuring) require re-stabilization period with elevated learning rates.

**A3** (Agent Independence): Agent capabilities <img src="diagrams/formulas/f_a_j_1e30c03d.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> are independent of each other. One agent's specialization doesn't affect others' intrinsic capabilities (though it does affect selection via weights).

**A4** (Weight Boundedness): Trust weights <img src="diagrams/formulas/f_w_ij_in_0_1_e39cbe33.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> are bounded, avoiding divergence. This is guaranteed via softmax normalization or clipping.

Under these assumptions, we derive the theoretical guarantees presented in Section 11.3.

### 10.2.1 Extension of Functional Agency

We extend the agentic system definition (Definition 1.1) to include plasticity:

**Definition 11.1 (Plastic Agentic System)**. A plastic agentic system is a tuple:

<p align="center"><img src="diagrams/formulas/f_a_p_s_o_g_pi_m_alpha_eba89d2f.svg" alt="formula"></p>

where the first six elements are identical to Definition 1.1, and we add:
- <img src="diagrams/formulas/f_w_e_rightarrow_0_1_3800a2ed.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">: weight function over edges <img src="diagrams/formulas/f_e_3a3ea00c.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> of the agent graph
- <img src="diagrams/formulas/f_gamma_w_times_h_times_o_r_e38c7118.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">: **plasticity function** that updates weights based on history <img src="diagrams/formulas/f_h_c1d9f50f.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> and outcomes <img src="diagrams/formulas/f_o_f1862177.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">
- <img src="diagrams/formulas/f_eta_in_0_1_d2fe29bf.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">: learning rate

**Plasticity Condition (Condition 4)**. A system exhibits structural plasticity if:

<p align="center"><img src="diagrams/formulas/f_structural_plasticity_def.svg" alt="Structural Plasticity Definition"></p>

That is, weights evolve as a function of accumulated experience.

### 10.2.2 Hebbian Learning for Agents

We apply the Hebbian principle ("neurons that fire together wire together") to the multi-agent context:

**Definition 11.2 (Hebbian Update Rule)**. Given an episode where agents <img src="diagrams/formulas/f_a_i_693a3b97.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> and <img src="diagrams/formulas/f_a_j_6daefbe0.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> collaborated sequentially with outcome <img src="diagrams/formulas/f_o_d9567975.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">:

<p align="center">
  <img src="diagrams/formulas/f01_hebbian_update.svg" alt="Hebbian Rule" width="400">
</p>

where:
- <img src="diagrams/formulas/f_delta_o_53cf1498.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">: reinforcement signal derived from outcome (<img src="diagrams/formulas/f_delta_0_65b1b5bb.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> for success, <img src="diagrams/formulas/f_delta_0_e007a4b0.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> for failure)
- <img src="diagrams/formulas/f_c_ij_98b138f9.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">: contribution of edge <img src="diagrams/formulas/f_i_j_5270ae67.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> to result (default 1.0, can be estimated with attribution)
- <img src="diagrams/formulas/f_eta_ffe9f913.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">: learning rate
- <img src="diagrams/formulas/f_lambda_in_0_1_5715e471.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">: decay factor (gradual forgetting)

> [!TIP] **Intuition: Hebbian Rule**
> *"Neurons that fire together, wire together."*
>
> Applied to agents: if A→B collaborate and the outcome is successful (δ > 0), their connection strengthens.
> If they fail (δ < 0), trust decreases. This is reinforcement learning at the *connection* level, not individual agents.

**Proposition 11.1 (Hebbian Convergence)**. With decay <img src="diagrams/formulas/f_lambda_in_0_1_5715e471.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> and i.i.d. outcomes, weights converge to a stationary distribution:

<p align="center">
  <img src="diagrams/formulas/f02_stationary_weight.svg" alt="Stationary Weight" width="250">
</p>

*Proof sketch*: The update with decay is <img src="diagrams/formulas/f_w_t_1_1_lambda_w_t_bbefeeba.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">. At steady state, <img src="diagrams/formulas/f_w_1_lambda_w_eta_ma_0bdf4974.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">, hence <img src="diagrams/formulas/f_w_eta_mathbb_e_delta_c_0b0d4178.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">. ∎

> [!NOTE] **Intuition: Hebbian Convergence**
> Weights converge to a value proportional to the "average success" of collaboration (<img src="diagrams/formulas/f_mathbb_e_delta_cdot_c_5ff4d6b9.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">).
> - **Large η** → higher weights, faster adaptation
> - **Large λ** → stronger decay, lower equilibrium weights
> - If <img src="diagrams/formulas/f_mathbb_e_delta_0_59f049d7.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> (more successes than failures), weight grows; if <img src="diagrams/formulas/f_mathbb_e_delta_0_43d7a163.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">, it decreases.

### 10.2.3 Types of Plasticity

MAP defines three levels of plasticity with different granularity:

| Level | Type | Mechanism | Frequency | Impact |
|-------|------|-----------|-----------|--------|
| **L1** | Weights | Hebbian update of <img src="diagrams/formulas/f_w_ij_3c81d2fb.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> | Each episode | Low |
| **L2** | Structure | Neurogenesis (create edges) / Pruning (remove edges) | Every N episodes | Medium |
| **L3** | Prompts | Learned patches to agent instructions | Per error pattern | High |

**L1 Plasticity (Weights)**:
```python
# Hebbian update pseudo-code
for (source, target) in episode_path:
    current_weight = trust_graph.get_weight(source, target)
    delta = compute_delta(outcome)  # +0.5 success, -0.3 failure
    # W^(t+1) = (1-λ)W^(t) + η·δ
    new_weight = (1 - decay) * current_weight + learning_rate * delta
    new_weight = clip(new_weight, min=0.01, max=1.0)
    trust_graph.set_weight(source, target, new_weight)
```

**L2 Plasticity (Structure)**:
- **Neurogenesis**: Create new edge when two never-connected agents collaborate successfully
- **Pruning**: Remove edge when <img src="diagrams/formulas/f_w_ij_theta_prune_37755b91.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> for <img src="diagrams/formulas/f_n_8d9c307c.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> consecutive episodes

**L3 Plasticity (Prompts)**:
- Add learned context to agent instructions based on recurring error patterns

### 10.2.4 Trust Graph: Central Data Structure

The **Trust Graph** is the structure that stores and manages trust relationships:

<p align="center">
  <img src="diagrams/10_map_trust_graph_en.svg" alt="Trust Graph" width="700">
<br><em>Figure 46: MAP Trust Graph</em>
</p>

### 10.2.5 Structural Memory: Indexing by Intent

A fundamental aspect of MAP is that trust weights <img src="diagrams/formulas/f_w_ij_3c81d2fb.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> are **indexed by the intent type** detected in each query. This allows the system to learn collaboration patterns specific to each task category.

**Definition 11.6 (Structural Memory)**. Structural memory is a function:

<p align="center"><img src="diagrams/formulas/f_mathcal_m_s_i_times_e_rig_24266538.svg" alt="formula"></p>

where <img src="diagrams/formulas/f_i_98593f57.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">`QUERY_DAX`, `DOCUMENT`, `REPORT`, `GENERAL`<img src="diagrams/formulas/f__4641d03f.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> is the set of intents and <img src="diagrams/formulas/f_e_3a3ea00c.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> is the set of edges between agents. Each intent <img src="diagrams/formulas/f_i_in_i_6fa78e29.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> maintains its own weight matrix:

<p align="center"><img src="diagrams/formulas/f_w_i_jk_mathcal_m_s_i_91da127c.svg" alt="formula"></p>

> [!NOTE] **Intuition: Memory by Intent**
>
> Imagine a company where the same employee excels at technical tasks but is mediocre at customer service.
> Structural memory **learns this separately**:
>
> ```
> DAXAgent for QUERY_DAX:    W = 0.92  (highly reliable)
> DAXAgent for DOCUMENT:     W = 0.12  (not their strength)
> ```
>
> The router learns to direct each query type to the most suitable agent.

**Rationale**: An agent may be highly reliable for one task type but less so for another. For example, `DAXAgent` may have <img src="diagrams/formulas/f_w_query_dax_router_to_d_6b307ec5.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> but <img src="diagrams/formulas/f_w_document_router_to_dax_014562e1.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">. This specialization enables optimal context-based routing.

<p align="center">
  <img src="diagrams/10_map_structural_memory_en.svg" alt="MAP Structural Memory" width="700">
<br><em>Figure 47: MAP Structural Memory</em>
</p>

**Hebbian Update Algorithm by Intent**:

```python
def update_structural_memory(intent: str, episode_path: List[Tuple], outcome: float):
    """Updates W_ij for the specific intent."""
    delta = compute_delta(outcome)  # +δ success, -δ failure

    for (source, target) in episode_path:
        key = f"map:trust:{intent}:{source}:{target}"
        current_weight = redis.hget("map:structural_memory", key) or 0.5

        # Hebbian update: W^(t+1) = (1-λ)W^(t) + η·δ
        new_weight = (1 - DECAY) * current_weight + LEARNING_RATE * delta
        new_weight = max(0.01, min(1.0, new_weight))

        redis.hset("map:structural_memory", key, new_weight)
```

This intent-based indexing constitutes the system's **Structural Memory**—the fifth memory type (see Memory Types Table in Section 6.1). Unlike other memories that store semantic content, Structural Memory stores **learned collaboration patterns** between agents.

## 10.3 Theoretical Guarantees: Bounded Predictability

A plastic system must maintain **bounded predictability**—behavior variance must remain within controlled limits even while the system learns.

**Theorem 10.1 (Variance Bound with Plasticity)**. Let <img src="diagrams/formulas/f_a_p_599d351d.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> be a plastic system where each agent <img src="diagrams/formulas/f_a_0cc175b9.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> has a contract with maximum variance <img src="diagrams/formulas/f_sigma_2_max_a_839f74f9.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">. Then:

<p align="center">
  <img src="diagrams/formulas/f03_variance_bound.svg" alt="Variance Bound" width="400">
</p>

where <img src="diagrams/formulas/f_epsilon_gamma_26c38352.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> is the additional variance term introduced by plasticity, bounded by:

<p align="center">
  <img src="diagrams/formulas/f04_plasticity_variance.svg" alt="Plasticity Variance" width="250">
</p>

*Proof sketch*: Total variance is the weighted sum of individual variances (by conditional agent independence given state). Plasticity introduces additional variance proportional to the square of learning rate and expected magnitude of deltas. Reducing <img src="diagrams/formulas/f_eta_ffe9f913.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> reduces <img src="diagrams/formulas/f_epsilon_gamma_26c38352.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> at the cost of slower learning. ∎

> [!IMPORTANT] **Interpretation: Variance Bound**
>
> This theorem guarantees that system "unpredictability" is **bounded** by two components:
>
> | Component | Formula | Meaning |
> |-----------|---------|---------|
> | **Intrinsic variance** | <img src="diagrams/formulas/f_sum_w_a_cdot_sigma_2_a_52322d43.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> | Each agent contributes variance proportional to its weight |
> | **Learning variance** | <img src="diagrams/formulas/f_epsilon_gamma_propto_eta_2_bdd2386c.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> | Small if η is small |
>
> **Practical implication**: Using <img src="diagrams/formulas/f_eta_approx_0_1_8082997c.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> keeps the system stable (<img src="diagrams/formulas/f_epsilon_gamma_2d3a3ebb.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> low) while allowing gradual adaptation.

**Corollary 11.1 (Stability Condition)**. The system is stable if:

<p align="center">
  <img src="diagrams/formulas/f05_stability_condition.svg" alt="Stability Condition" width="250">
</p>

where <img src="diagrams/formulas/f_epsilon_max_5a52e274.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> is the maximum tolerable additional variance.

> [!WARNING] **Computing Maximum η**
>
> For a system with:
> - 10 edges (<img src="diagrams/formulas/f_e_10_4390f219.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">)
> - Reinforcement variance <img src="diagrams/formulas/f_mathbb_e_delta_2_0_25_1fadae0e.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> (δ ∈ {-0.5, +0.5})
> - Tolerance <img src="diagrams/formulas/f_epsilon_max_0_05_d4a3d567.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">
>
> Maximum learning rate is: <img src="diagrams/formulas/f_eta_max_sqrt_0_05_0_2_33010316.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">
>
> **Recommendation**: Use <img src="diagrams/formulas/f_eta_0_1_289fdd60.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> to leave a safety margin.

## 10.4 MAP Evaluation Metrics (MAP-Bench)

MAP-Bench introduces **9 metrics** organized in three dimensions, addressing a significant gap in adaptive systems evaluation: no previous benchmark jointly measures adaptation + predictability + structure.

### 10.4.1 Adaptation Metrics

**Definition 11.3 (Adaptation Rate)**. Episodes required to recover baseline performance after stress:

<p align="center">
  <img src="diagrams/formulas/f06_adaptation_rate.svg" alt="Adaptation Rate" width="450">
</p>

**Definition 11.2.1 (Plasticity Efficiency)**:

<p align="center">
  <img src="diagrams/formulas/f07_plasticity_efficiency.svg" alt="Plasticity Efficiency" width="350">
</p>

**Definition 11.2.2 (Consolidation Stability)**:

<p align="center">
  <img src="diagrams/formulas/f08_consolidation_stability.svg" alt="Consolidation Stability" width="220">
</p>

| Metric | Formula | Interpretation | Target |
|--------|---------|----------------|--------|
| **AR** (Adaptation Rate) | See Def. 11.2 | Lower = faster adaptation | AR < 20 eps |
| **PE** (Plasticity Efficiency) | See Def. 11.2.1 | Improvement per weighted mutation | PE > 0.5 |
| **CS** (Consolidation Stability) | See Def. 11.2.2 | CS→1: successful consolidation | CS > 0.7 |

*Note: Weights (1.0, 2.5, 1.5) reflect relative impact of weight, structure, and prompt mutations respectively.*

### 10.4.2 Predictability Metrics

**Definition 11.4 (Behavior Variance)**. Expected output variance within semantic clusters:

<p align="center">
  <img src="diagrams/formulas/f09_behavior_variance.svg" alt="Behavior Variance" width="400">
</p>

where <img src="diagrams/formulas/f_c_0d61f837.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> is an input clustering by semantic similarity (HDBSCAN, <img src="diagrams/formulas/f_tau_0_92_b61e7a6d.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">).

**Definition 11.4.1 (Contract Compliance)**:

<p align="center">
  <img src="diagrams/formulas/f10_contract_compliance.svg" alt="Contract Compliance" width="380">
</p>

| Metric | Formula | Interpretation | Target |
|--------|---------|----------------|--------|
| **BV** (Behavior Variance) | See Def. 11.4 | Lower = more consistent | BV < 0.1 |
| **CC** (Contract Compliance) | See Def. 11.4.1 | % meeting contracts | CC > 95% |
| **VR** (Violation Rate) | Violations / Episode | Theoretical bounds exceeded | VR < 0.01 |

### 10.4.3 Structural Metrics

**Definition 11.5 (Topology Entropy)**. Normalized entropy of weight distribution:

<p align="center">
  <img src="diagrams/formulas/f11_topology_entropy.svg" alt="Topology Entropy" width="500">
</p>

| Metric | Formula | Interpretation | Target |
|--------|---------|----------------|--------|
| **TE** (Topology Entropy) | See above | High = diverse distribution | 0.5 < TE < 0.9 |
| **PR** (Pruning Rate) | Prunes / Episode | Removal rate | Context-dep. |
| **NR** (Neurogenesis Rate) | Creations / Episode | Creation rate | Context-dep. |

## 10.5 MAP Benchmark Protocol

The evaluation protocol consists of five phases:

<p align="center">
  <img src="diagrams/10_map_benchmark_protocol_en.svg" alt="MAP Benchmark Protocol" width="700">
<br><em>Figure 48: MAP Benchmark Protocol</em>
</p>

## 10.6 Implementation in the reference deployment (Case Study)

MAP implementation in the reference deployment is **partially realized** for L1 Plasticity (weights), with L2 and L3 identified as future work.

### 10.6.1 Current State: Static Trust Weights

Currently, the reference deployment uses **statically configured** trust weights for routing:

```python
# Current configuration (static)
AGENT_TRUST_WEIGHTS = {
    ("Router", "DAXAgent"): 0.9,
    ("Router", "DocumentAgent"): 0.8,
    ("Router", "ReportAgent"): 0.7,
    ("DAXAgent", "FabricAgent"): 0.85,
}
```

### 10.6.2 Proposal: Evolution Toward MAP

The proposed evolution introduces the dynamic Trust Graph:

```python
# MAP proposal (dynamic)
class TrustGraph:
    def __init__(self, redis_client, learning_rate=0.1, decay=0.01):
        self.redis = redis_client
        self.eta = learning_rate
        self.decay = decay

    async def update_hebbian(self, path: List[str], outcome: Outcome):
        """Updates Hebbian weights based on outcome."""
        delta = +0.5 if outcome.success else -0.3

        for i in range(len(path) - 1):
            source, target = path[i], path[i+1]
            current = await self.get_weight(source, target)
            new = clip(current + self.eta * delta, 0.01, 1.0)
            new = new * (1 - self.decay)  # Apply decay
            await self.set_weight(source, target, new)
```

### 10.6.3 Integration with Microsoft Agent Framework

MAP integrates with Agent Framework through extensions:

| Original Component | MAP Extension |
|--------------------|----------------|
| `ChatCompletionAgent` | `PlasticAgent` with trust weights |
| `AgentGroupChat` | `PlasticAgentGroupChat` with feedback loop |
| `SelectionStrategy` | `TrustBasedSelectionStrategy` |

## 10.7 Future Work: Complete MAP Implementation

Complete MAP implementation constitutes an **open research direction**. Pending components include:

### 10.7.1 L2 Plasticity: Structural Mutations

**Automatic neurogenesis**: Create edges between agents that never collaborated when query patterns suggest it.

**Intelligent pruning**: Remove edges with low usage and low trust to simplify topology.

### 10.7.2 L3 Plasticity: Prompt Patching

**Context learning**: Add "learned context" to agent prompts based on recurring error patterns.

```python
# Prompt patch example
class PromptPatch:
    content: str  # "When user asks X, always verify Y"
    confidence: float  # 0.85
    ttl_hours: int  # 168 (1 week)
```

### 10.7.3 Complete Benchmark

Implementation of 5-phase benchmark protocol with:
- Controlled episode generator
- Calibrated error injection
- Automated metrics
- Visual scorecard

### 10.7.4 Hyperparameter Meta-Learning

Automatic optimization of:
- Learning rate <img src="diagrams/formulas/f_eta_ffe9f913.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">
- Decay rate <img src="diagrams/formulas/f_lambda_c6a6eb61.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">
- Pruning thresholds <img src="diagrams/formulas/f_theta_prune_4f584727.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">

### Future Work

| Aspect | Current State | Future Direction |
|--------|---------------|------------------|
| Plasticity | L1 Connections (TrustGraph) | L2 Structural (neurogenesis/pruning), L3 Prompts |
| Transfer | Same domain | Cross-domain transfer (BI → Healthcare) |
| Convergence | Empirical heuristics | Formal convergence theory |

**Open research questions**:
- What is the optimal learning rate η per domain?
- How to balance stability-plasticity without catastrophic forgetting?
- Which emergent specialization patterns are theoretically predictable?

---


---

# Appendix — Expanded Proof of Theorem 10.1

## B.3 Expanded Proof of Theorem 10.1 (MAP)

**Theorem 10.1 (Variance Bound with Plasticity)**. *Let <img src="diagrams/formulas/f_a_p_599d351d.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> be a plastic agentic system per Definition 11.1. Under assumptions A1-A4, the adaptive policy variance is bounded:*

<p align="center"><img src="diagrams/formulas/f_var_pi_p_s_g_leq_sum_a_w_33298ec9.svg" alt="formula"></p>

**Complete Proof.**

*Step 1 (Joint Policy Decomposition)*:

By assumption A3 (agent independence), the plastic system's joint policy decomposes as a weighted sum:

<p align="center"><img src="diagrams/formulas/f_pi_p_s_g_sum_j_1_n_w_e5bc5791.svg" alt="formula"></p>

where <img src="diagrams/formulas/f_w_j_2c0e2174.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> is the normalized trust weight of agent <img src="diagrams/formulas/f_j_363b122c.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">, and <img src="diagrams/formulas/f_pi_j_68df4fed.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> is the individual agent's policy.

*Step 2 (Application of Total Variance Law)*:

We partition variance conditioning on weights <img src="diagrams/formulas/f_w_61e9c06e.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">:

<p align="center"><img src="diagrams/formulas/f_var_pi_p_e_var_pi_p_w_04e73867.svg" alt="formula"></p>

The first term captures intrinsic agent variance; the second captures variance from weight adaptation.

*Step 3 (Conditional Variance Bound)*:

Since weights <img src="diagrams/formulas/f_w_61e9c06e.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> evolve slowly (by A2, local stationarity), we treat <img src="diagrams/formulas/f_w_61e9c06e.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> as locally constant:

<p align="center"><img src="diagrams/formulas/f_var_pi_p_w_var_left_sum_30b28aab.svg" alt="formula"></p>

By A3 (independence), cross-covariances are zero:

<p align="center"><img src="diagrams/formulas/f_var_pi_p_w_sum_j_w_j_2_3e9f86bf.svg" alt="formula"></p>

Each agent has maximum variance bounded by contract: <img src="diagrams/formulas/f_var_pi_j_leq_sigma_2_max_10867cd6.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">.

By A4 (weight boundedness), <img src="diagrams/formulas/f_w_j_in_0_1_f814bafd.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">, implying <img src="diagrams/formulas/f_w_j_2_leq_w_j_5a7456bb.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">:

<p align="center"><img src="diagrams/formulas/f_var_pi_p_w_leq_sum_j_w_j_1f36016e.svg" alt="formula"></p>

*Step 4 (Adaptation Variance Bound)*:

The structural adaptation term <img src="diagrams/formulas/f_gamma_ae539dfc.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> introduces additional variance. By the Hebbian update rule (Definition 11.2):

<p align="center"><img src="diagrams/formulas/f_w_ij_t_1_1_lambda_8fc67ca7.svg" alt="formula"></p>

This term's variance depends on learning rate <img src="diagrams/formulas/f_eta_ffe9f913.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">, decay <img src="diagrams/formulas/f_lambda_c6a6eb61.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">, and reinforcement variance <img src="diagrams/formulas/f_delta_o_53cf1498.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">:

<p align="center"><img src="diagrams/formulas/f_var_e_pi_p_w_leq_eta_2_c2e28271.svg" alt="formula"></p>

Note that <img src="diagrams/formulas/f_epsilon_gamma_to_0_0f3345d3.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> when <img src="diagrams/formulas/f_eta_to_0_5a4babd2.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> (slow learning regime).

*Step 5 (Term Combination)*:

Substituting results from steps 3 and 4 into step 2:

<p align="center"><img src="diagrams/formulas/f_var_pi_p_e_var_pi_p_w_04e73867.svg" alt="formula"></p>
<p align="center"><img src="diagrams/formulas/f_leq_e_left_sum_j_w_j_cdot_9091e46a.svg" alt="formula"></p>
<p align="center"><img src="diagrams/formulas/f_sum_j_mathbb_e_w_j_cdot_aa99c19a.svg" alt="formula"></p>

Renaming <img src="diagrams/formulas/f_w_a_mathbb_e_w_j_bad83f45.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> for each agent <img src="diagrams/formulas/f_a_0cc175b9.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">:

<p align="center"><img src="diagrams/formulas/f_var_pi_p_s_g_leq_sum_a_w_d3a73453.svg" alt="formula"></p>

**Corollary B.3.1 (Asymptotic Stability)**: In the limit <img src="diagrams/formulas/f_eta_to_0_5a4babd2.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">, <img src="diagrams/formulas/f_epsilon_gamma_to_0_0f3345d3.svg" alt="formula" style="vertical-align: middle; height: 1.5em;">, and variance converges to the weighted average of individual variances:

<p align="center"><img src="diagrams/formulas/f_lim_eta_to_0_var_pi_p_3691f74c.svg" alt="formula"></p>

where <img src="diagrams/formulas/f_w_a_5beabcfe.svg" alt="formula" style="vertical-align: middle; height: 1.5em;"> are stationary weights given by Proposition 11.1.

---

