# AcoustiForge Phase 5-7: Experience Intelligence & Retrieval Boundary Discovery

**STATUS: DISCOVERY ONLY — NOT AN IMPLEMENTATION CONTRACT**

**Governing Architectural Invariants:**
> *AI proposes. AcoustiForge validates and executes.*
> 
> *Runtime teaches the AI layer; runtime does not rewrite the acoustic Core.*
> 
> *The Experience Store is the historical evidence layer. It does not directly modify model weights or the acoustic Core.*
> 
> *Temporal and solar context are explanatory variables, not measurements of human mood or psychological state.*
> 
> *Behavioral and explicitly reported engagement evidence are captured as historical evidence. Future learning determines whether these variables correlate with user preferences.*

---

## 1. Executive Summary & Objective

The objective of this discovery phase is to address a single foundational architectural question:

> **What is the smallest, safest, evidence-justified mechanism by which AcoustiForge can begin learning from its accumulated Experience Store without compromising the deterministic Core?**

This document evaluates how historical experience accumulated in the local, append-only JSONL `ExperienceStore` (Schema `1.1.0`) can be indexed, retrieved, and presented as contextual evidence to assist future AI `DesignIntent` proposals.

**Non-Goals:**
- No neural network training, LoRA fine-tuning, or weight modification.
- No vector database dependencies (e.g. Chroma, FAISS, Pinecone) or embedding SDKs.
- No dynamic DSP coefficient injection or runtime state mutation.

---

## 2. Current Baseline & Experience Store Capabilities Audit

### 2.1 Baseline State
- **Regression Suite:** 497 passed, 2 skipped, 0 failures, 0 errors, 0 warnings under `pytest -q -W error`.
- **Core, Track C, and Execution Mutation:** ZERO.
- **Dependencies:** 100% Python stdlib + existing project domain contracts.

### 2.2 Current Experience Schema (v1.1.0) Inspection

The canonical contract `ExperienceRecord` captures nine distinct subsystems:

| Field Group | Contract | Evidence Category | Content / Capabilities |
|---|---|---|---|
| **Identity** | `ExperienceRecord` | Identity & Audit | `experience_id`, `timestamp_iso`, `schema_version` ("1.1.0"), `runtime_version` ("0.5.6"), `evidence_type`, `outcome`. |
| **Intent Summary** | `IntentSummary` | Input Evidence | `query`, `intent_id`, `target_preset`, `crossover_frequency_target_hz`, `crossover_family`, `crossover_order`, `spatial_profile`, `tonal_summary`, `provider_name`. |
| **Specification Summary** | `SpecificationSummary` | Core Contract Mapping | `specification_type`, `crossover_family`, `crossover_order`, `search_band_hz`, `spatial_position_count`, `sample_rate`. |
| **Optimization Summary** | `OptimizationSummary` | Deterministic Math Result | `converged`, `initial_loss_db`, `final_loss_db`, `selected_crossover_hz`, `iterations_completed`, `optimizer_name`. |
| **Graph Summary** | `GraphSummary` | Topology Metadata | `graph_name`, `node_count`, `sample_rate`, `channels`, `is_frozen`. |
| **Execution Context** | `ExecutionContextSummary` | Hardware/Runtime | `backend_type`, `platform`, `sample_rate`, `channels`, `block_size`, `hardware_target`, `driver_version`. |
| **Runtime Observations** | `RuntimeObservations` | Observed vs Derived | **Observed:** `blocks_processed`, `samples_processed`, `total_execution_time_s`, `mean_block_time_us`, `xrun_count`, `peak_output_dbfs`, `clipping_detected`.<br>**Derived:** `derived_realtime_margin`, `derived_throughput_samples_per_sec`. |
| **Temporal/Solar Context** | `TemporalSolarContext` | Environmental / Diurnal | `local_timestamp_iso`, `timezone_name`, `sunrise_timestamp_iso`, `sunset_timestamp_iso`, `daylight_duration_s`, `minutes_since_sunrise`, `minutes_until_sunset`, `daylight_fraction`, `day_phase`, `source`. |
| **Engagement Metrics** | `EngagementMetrics` | Behavioral / Explicit / Trajectory | **Behavioral:** `session_duration_s`, `listening_duration_s`, `interaction_count`, `configuration_change_count`, `accepted_change_count`, `rejected_change_count`, `reverted_change_count`, `replay_count`, `completion_ratio`, `session_abandoned`, `session_completed`, `return_session`.<br>**Explicit:** `explicit_engagement_rating`, `explicit_engagement_feedback`.<br>**Derived:** `derived_engagement_score`, `derived_notes`.<br>**Trajectory:** `events` (`tuple[ExperienceEvent, ...]`). |
| **Human Feedback** | `HumanFeedback` | Explicit User Feedback | `status` (`ACCEPTED`, `REJECTED`, `MODIFIED`, `UNRATED`), `rating` (1.0–5.0), `qualitative_notes`, `comparison_outcome`. |

### 2.3 Store Querying Capabilities
The existing `ExperienceStore.query()` supports filtering on:
- `outcome` (`OutcomeClassification`)
- `evidence_type` (`EvidenceType`)
- `day_phase` (`DayPhase`)
- `schema_version`
- `min_engagement_rating`
- `session_completed`
- `session_abandoned`
- `start_time_iso` / `end_time_iso`
- `limit`

---

## 3. Evaluation of Candidate Intelligence Mechanisms

| Candidate Pattern | Description | Prerequisites | Evidence Required | Architectural Impact | Limitations & Risks |
|---|---|---|---|---|---|
| **A. Structured Historical Filtering** | Exact match and range filtering over typed metadata fields (e.g. find all Linkwitz-Riley 4th order crossovers in 2-way setups with rating $\ge 4.5$). | Existing `ExperienceStore.query()` | Modest ($N \ge 10$ records). | Minimal; consumes existing store directly without extra memory structures. | Limited to explicit categorical/range criteria; cannot compute conceptual acoustic similarity. |
| **B. Deterministic Feature Similarity** | Normalized Euclidean/cosine distance over a deterministic mathematical feature vector (crossover band, target curve slope, listening duration, rating). | Fixed numeric feature signature extraction function. | Moderate ($N \ge 50$ records). | Low; pure mathematical function without external libraries or model weights. | Requires careful weight calibration across heterogeneous dimensions (e.g. Hz vs dB vs seconds). |
| **C. Retrieval-Augmented Generation (RAG)** | Retrieve top-$k$ relevant past episodes (intent + outcome + feedback) to inject as few-shot prompt context for a local LLM proposing `DesignIntent`. | Validated retrieval layer + local LLM interface. | Moderate to High ($N \ge 100$ diverse episodes). | Moderate; strictly upstream of `DesignIntentAdapter`; validated by firewall. | Quality bounded by prompt token budgets and LLM capability; LLM must remain advisory. |
| **D. Preference Learning** | Statistical ranking/preference model (e.g. Bradley-Terry or contextual bandits) to estimate user preference over parameter combinations. | Abundant pairwise or rated interaction data. | High ($N \ge 500$ real sessions with active user feedback). | High; introduces statistical learner; must strictly remain advisory to proposal generation. | Extreme risk of confounding if engagement (listening time) is conflated with satisfaction. |
| **E. Supervised Classification** | Predictive model estimating $P(\text{accepted} \mid \text{spec}, \text{context})$. | Large, balanced, labeled dataset with positive and negative feedback. | Very High ($N \ge 1000$ labeled records). | High; requires offline training and dataset validation pipelines. | Severe label sparsity and class imbalance in early deployments; prone to spurious correlations. |
| **F. Analytics-First Intelligence** | Descriptive statistical aggregations (mean ratings per crossover range, distribution of listening durations across day phases, xrun rates). | Store aggregation utilities. | Minimal ($N \ge 5$ records). | Zero external footprint; transparent, explainable summaries for users and developers. | Does not directly generate automated proposals, but provides essential empirical baselines. |

---

## 4. Analysis: Premature Vector / Embedding Architectures

Introducing vector databases (e.g., Chroma, FAISS) and opaque dense embeddings at this stage is **strongly premature and technically unjustified**:

1. **Dependency Burden:** Embedding libraries introduce hundreds of megabytes of binary dependencies (PyTorch, ONNX, C++ extensions), violating AcoustiForge’s zero-dependency, lightweight, embedded-friendly footprint.
2. **Loss of Explainability & Determinism:** Dense embeddings project acoustic parameters (frequencies, slopes, Q factors) into non-interpretable latent spaces where mathematical guarantees (e.g., exact crossover bounds) are lost.
3. **Structured vs Unstructured Reality:** 95% of AcoustiForge's experience data is **structured numeric and categorical data** (Hz, dB, sample rates, timings, enums), for which deterministic mathematical filtering and normalized feature distances are strictly superior in speed, inspectability, and precision.
4. **Local Resource Budget:** On target embedded devices (e.g. Raspberry Pi 4/5 audio nodes), memory and CPU cycles must be reserved for real-time PCM audio execution, not background vector indexing.

---

## 5. Trust Boundary & Separation of Evidence Classes

### 5.1 Trust Boundary Invariant
```
               ExperienceStore (Authoritative History)
                         │
                         ▼
              Deterministic Retrieval / Filter
                         │
                         ▼
              Advisory Context for AI Proposal
                         │
                         ▼
                    DesignIntent
                         │
                         ▼
              VALIDATION FIREWALL (Authoritative Boundary)
                         │
                         ▼
              OptimizationSpecification (Canonical Core Contract)
                         │
                         ▼
              AcoustiForge Deterministic Core (Frozen Math)
```

**Forbidden Shortcuts:**
- No direct mapping from historical record $\to$ DSP filter coefficients.
- No dynamic injection of ComputeGraph nodes from past records.
- No bypassing of the 4-stage validation firewall.
- Historical experience is strictly advisory evidence for proposal generation.

### 5.2 Segregation of Evidence Classes
The retrieval layer must never conflate different evidence tiers:
1. **Observed Telemetry:** Raw execution timings, buffer counts, and xruns (hardware facts).
2. **Explicit User Feedback:** Direct user ratings and statements (subjective facts).
3. **Derived Metrics:** Post-hoc calculations like realtime margin and throughput (computational artifacts).
4. **AI Inference:** Hypothetical proposals or synthesized intents (untrusted advisory data).
5. **Historical Precedent:** Past session trajectories (contextual empirical data).

---

## 6. Analysis: Engagement & Temporal Context Usefulness

### 6.1 Engagement Variables
- **High-Value Retrieval Labels:** `session_completed`, `session_abandoned`, `reverted_change_count`, `explicit_engagement_rating`.
- **Confounding Risks:** `listening_duration_s` may reflect user absence (leaving audio playing while away) rather than high engagement. Therefore, listening duration must always be evaluated in conjunction with `interaction_count` and `explicit_engagement_rating`.

### 6.2 Temporal/Solar Context
- **Safe Role:** Contextual stratification (e.g. filtering for configurations accepted during `EVENING` or `MIDDAY` sessions, or comparing weekday vs weekend usage).
- **Forbidden Assumption:** Inferring emotional mood from diurnal phase (e.g. treating `SUNSET_WINDOW` as "relaxed"). Diurnal context is purely physical/astronomical explanatory context.

---

## 7. Data Sufficiency Assessment

| Evidence Type | Current Repository Volume | Valid Learning Use Cases | Invalid / Premature Use Cases |
|---|---|---|---|
| `SOFTWARE_OFFLINE` | Synthetic test episodes generated during CI/test runs. | Testing retrieval pipelines, schema validation, analytical aggregation, and deterministic feature distance logic. | Cannot be used for user preference learning, subjective engagement prediction, or physical acoustic modeling. |
| `PHYSICAL_HARDWARE` | Pending Phase 5-4C hardware validation gate. | Real-world hardware execution latency, xrun correlation, thermal stability. | Supervised preference learning (until real human listening sessions are logged). |
| `HYBRID_SIMULATION` | Spatial multi-position synthetic sweeps. | Optimizer convergence analysis, spatial weight sensitivity. | Real acoustic room mood / preference correlation. |

**Key Finding:** The repository currently has zero real human listening sessions. Implementing complex statistical preference learners or LLM fine-tuning pipelines before accumulating genuine physical user sessions is fundamentally ungrounded.

---

## 8. Architectural Recommendations for Phase 5-7

### Comparison of Next-Step Options

| Option | Description | Readiness | Recommendation |
|---|---|---|---|
| **Option 1: Structured Retrieval + Analytics Engine** | Implement a local, zero-dependency `ExperienceRetriever` and `ExperienceAnalytics` module providing multi-criteria filtering, aggregation statistics, and query formatting. | **Immediate** | **RECOMMENDED** |
| **Option 2: Deterministic Episode Similarity** | Add a mathematical normalized feature-vector distance metric over structured acoustic and engagement variables. | High | Feasible as an extension to Option 1. |
| **Option 3: Local RAG Prompt Formatter** | Format retrieved top-$k$ historical episodes into structured markdown/JSON prompts for advisory consumption by `IDesignIntentProvider`. | High | Feasible as an extension to Option 1. |
| **Option 4: Preference Learning / ML Models** | Train predictive ranking models on experience data. | Blocked | **DEFERRED** (Requires large real-world dataset). |
| **Option 5: Vector DB / Embeddings** | Introduce third-party vector store and dense neural embeddings. | Inappropriate | **REJECTED** (Violates zero-dependency and local-first invariants). |

### Recommended Scope for Phase 5-7

The recommended Phase 5-7 implementation boundary is:

1. **`ExperienceRetriever` ([`src/acoustiforge/experience/retrieval.py`](file:///e:/AcoustiForge/src/acoustiforge/experience/retrieval.py)):**
   - Multi-criteria structured querying and deterministic ranking.
   - Exact and bounded acoustic matching (crossover frequencies, target topologies).
   - Segregated filtering across evidence types (`SOFTWARE_OFFLINE` vs `PHYSICAL_HARDWARE`).
2. **`ExperienceAnalytics` ([`src/acoustiforge/experience/analytics.py`](file:///e:/AcoustiForge/src/acoustiforge/experience/analytics.py)):**
   - Descriptive statistical summaries (mean loss improvement, convergence rates, acceptance ratios by crossover family, average listening durations).
3. **`ExperiencePromptContext` ([`src/acoustiforge/experience/prompt_context.py`](file:///e:/AcoustiForge/src/acoustiforge/experience/prompt_context.py)):**
   - Serializes retrieved historical episodes into clean, passive text context that can be passed to `IDesignIntentProvider.propose_intent(query, context=...)` without LLM SDK dependencies.

---

## 9. Deferred Items

1. **Physical ALSA Validation (Phase 5-4C):** Physical Raspberry Pi / USB DAC playback and live microphone ingestion remain an independent hardware validation track.
2. **Calibrated Room / Environmental Sensors:** Ingestion of live ambient noise SPL, temperature, and humidity sensors.
3. **Model Weight Fine-Tuning / Training:** Gradient-based parameter updates and LoRA adapters remain deferred until a substantial corpus of validated physical experience records is accumulated.
4. **Vector Databases & Neural Embeddings:** Opaque latent representations remain deferred in favor of transparent, deterministic mathematical feature indexing.

---

## 10. Final Discovery Status

**DISCOVERY COMPLETE — IMPLEMENTATION NOT STARTED**
