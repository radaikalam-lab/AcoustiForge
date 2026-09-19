# AcoustiForge Phase 5-6: Runtime Experience & Learning Boundary

**Governing Architectural Invariants:**
> *AI proposes. AcoustiForge validates and executes.*
> 
> *Runtime teaches the AI layer; runtime does not rewrite the acoustic Core.*
> 
> *The Experience Store is the historical evidence layer. It does not directly modify model weights or the acoustic Core.*
> 
> *Temporal and solar context may provide explanatory variables for future preference learning. They are not direct measurements of human mood or psychological state.*
> 
> *AcoustiForge captures behavioral and explicitly reported engagement evidence as part of the historical Experience Store, alongside temporal and solar context. Future learning systems may determine whether these variables correlate with user preferences or engagement.*

---

## 1. Motivation

AcoustiForge generates high-fidelity DSP configurations and executes real-time PCM audio across software backends and embedded hardware (such as Linux ALSA targets). Over time, repeated deployments across varying acoustic spaces, listening configurations, temporal contexts, and user feedback generate valuable historical evidence.

The goal of Phase 5-6 is **not** to train an LLM or fine-tune neural network weights prematurely. Instead, Phase 5-6 establishes a durable, structured, validated data substrate—the **Experience Store**—that systematically captures the complete execution trajectory:

$$\text{Intent} \longrightarrow \text{Specification} \longrightarrow \text{Optimization} \longrightarrow \text{Graph} \longrightarrow \text{Execution} \longrightarrow \text{Observations} \longrightarrow \text{Temporal Context} \longrightarrow \text{Engagement Evidence} \longrightarrow \text{Feedback} \longrightarrow \text{Outcome}$$

By decoupling evidence accumulation from specific model architectures or learning algorithms, AcoustiForge builds an authoritative historical dataset that can later be consumed by local LLMs, RAG retrievers, few-shot prompt builders, preference learners, and evaluation harnesses.

---

## 2. Architectural Invariants & Trust Model

```
                 USER / AI
                     │
                     ▼
                DesignIntent
                     │
                     ▼
             Validation Firewall
                     │
                     ▼
            Deterministic Core
                     │
                     ▼
                ComputeGraph
                     │
                     ▼
                 Execution
                     │
       ┌─────────────┼──────────────┐
       ▼             ▼              ▼
    Runtime      Acoustic       User
    Metrics      Measurement    Feedback
       │             │              │
       └─────────────┼──────────────┘
                     │
          ┌──────────┴───────────┐
          ▼                      ▼
   Temporal / Solar         Engagement
      Context               Evidence
          │                      │
          └──────────┬───────────┘
                     ▼
             ExperienceRecord
                     │
                     ▼
              ExperienceStore
                     │
                     ▼
             Future Learning
                     │
                     ▼
              Better Proposal
                     │
                     └────→ Validation Firewall
```

1. **Unidirectional Feedback**: The feedback loop terminates strictly at **proposal generation**. Runtime observations never modify Core optimization algorithms, biquad synthesis math, graph compilation rules, or active DSP parameters.
2. **Zero Production Mutation**: Domain contracts, acoustic math, graph compilation, and execution backends remain 100% frozen.
3. **Fail-Closed Storage Boundary**: Experience records are treated as untrusted data at the storage boundary. They are parsed as passive JSON, validated against strict dataclass schemas, and never dynamically executed.

---

## 3. ExperienceRecord Contract

The canonical record is defined in `acoustiforge.experience.contracts.ExperienceRecord` as a frozen, immutable dataclass:

| Component | Class | Contents |
|---|---|---|
| **Identity** | `ExperienceRecord` | `experience_id`, `timestamp_iso`, `schema_version` (`1.1.0`), `runtime_version` (`0.5.6`), `evidence_type`, `outcome`. |
| **Intent Summary** | `IntentSummary` | Query string, intent ID, target preset, target crossover frequency, crossover family/order, spatial profile, tonal modifiers summary. |
| **Specification Summary** | `SpecificationSummary` | Canonical specification class name, crossover topology/order, frequency search bounds, spatial position count. |
| **Optimization Summary** | `OptimizationSummary` | Convergence status, initial loss (dB), final loss (dB), selected crossover frequency (Hz), completed iterations. |
| **Graph Summary** | `GraphSummary` | Graph name/ID, node count, sample rate, channel count, frozen lifecycle status. |
| **Execution Context** | `ExecutionContextSummary` | Backend type, platform identifier, sample rate, channels, block size, hardware target identifier. |
| **Runtime Observations** | `RuntimeObservations` | Segregated observed metrics and post-hoc derived metrics. |
| **Temporal Context** | `TemporalSolarContext` | Timezone-aware local timestamp, solar milestones, relative diurnal features, day phase. |
| **Engagement Evidence** | `EngagementMetrics` | Behavioral telemetry, explicit user ratings/notes, post-hoc derived scores, and session trajectory events (`ExperienceEvent`). |
| **Human Feedback** | `HumanFeedback` | User rating (1.0–5.0), qualitative notes, feedback status (`ACCEPTED`, `REJECTED`, `MODIFIED`, `UNRATED`). |

---

## 4. Engagement Capture & Evidence Classes

The `EngagementMetrics` contract strictly distinguishes three categories of engagement evidence:

1. **Behavioral Telemetry (Observed):**
   - `session_duration_s`, `listening_duration_s`
   - `interaction_count`, `configuration_change_count`
   - `accepted_change_count`, `rejected_change_count`, `reverted_change_count`
   - `replay_count`, `completion_ratio`
   - `session_abandoned`, `session_completed`, `return_session`
2. **Explicit User-Reported Evidence:**
   - `explicit_engagement_rating` (1.0–5.0)
   - `explicit_engagement_feedback` (qualitative textual notes)
3. **Derived Evidence (Post-Hoc Calculations):**
   - `derived_engagement_score`, `derived_notes`
   - Segregated and clearly marked; never conflated with raw physical measurements.

### Session Trajectory Events (`ExperienceEvent`)

Preserves the ordered trajectory of user actions during a session:
- `SESSION_STARTED`, `INTENT_PROPOSED`, `INTENT_ACCEPTED`, `INTENT_REJECTED`
- `CONFIGURATION_APPLIED`, `CONFIGURATION_MODIFIED`, `CONFIGURATION_REVERTED`
- `MEASUREMENT_CAPTURED`, `USER_FEEDBACK`
- `PLAYBACK_STARTED`, `PLAYBACK_STOPPED`, `REPLAY`
- `SESSION_COMPLETED`, `SESSION_ABANDONED`

---

## 5. Observed vs Derived Segregation

To prevent derived heuristics from being misconstrued as physical measurements, `RuntimeObservations` and `EngagementMetrics` maintain strict divisions:

```text
Observed (Direct Telemetry):
  blocks_processed = 100
  samples_processed = 51200
  total_execution_time_s = 0.050
  mean_block_time_us = 500.0
  xrun_count = 0
  peak_output_dbfs = -3.2
  clipping_detected = False
  listening_duration_s = 2350.0
  replay_count = 1

Derived (Post-Hoc Calculations):
  derived_realtime_margin = 21.33x   (1.0667s audio / 0.050s execution)
  derived_throughput_samples_per_sec = 1024000.0
  derived_engagement_score = 0.92
```

Derived metrics must never masquerade as physical observations.

---

## 6. Software vs Physical Acoustic Evidence

The `EvidenceType` enum explicitly segregates evidence sources:
- `SOFTWARE_OFFLINE`: Synthetic audio processing through `OfflineExecutionBackend`.
- `PHYSICAL_HARDWARE`: Live playback and physical microphone captures through `AlsaExecutionBackend` on native Linux/ALSA targets.
- `HYBRID_SIMULATION`: Multi-position simulation combining real driver measurements with synthetic spatial weighting.

Software execution evidence is never mislabeled or reported as physical hardware evidence.

---

## 7. Temporal and Solar Context

The `TemporalSolarContext` contract captures environmental and diurnal variables:
- `local_timestamp_iso` (timezone-aware) and `timezone_name`
- `sunrise_timestamp_iso` and `sunset_timestamp_iso`
- `daylight_duration_s`
- `minutes_since_sunrise` (negative before sunrise, positive after)
- `minutes_until_sunset` (positive before sunset, negative after)
- `daylight_fraction` ($[0.0, 1.0]$)
- `day_phase`: `PRE_SUNRISE`, `MORNING`, `MIDDAY`, `AFTERNOON`, `SUNSET_WINDOW`, `EVENING`, `NIGHT`
- `source`: `calculated`, `external-context`, `user-supplied`, `unavailable`

### Mood and Preference Boundary

> **Temporal and solar context may provide explanatory variables for future preference learning. They are not direct measurements of human mood or psychological state.**

AcoustiForge strictly refrains from hardcoded psychological assumptions (e.g., mapping sunset $\to$ "relaxed" or morning $\to$ "energetic"). Instead, raw diurnal variables and engagement metrics are stored alongside human feedback so that empirical correlations can be discovered statistically by future learning algorithms.

---

## 8. ExperienceStore Engine

The `ExperienceStore` provides a local, append-only, inspectable JSONL persistence layer:
- **Append-Only Integrity**: Records are written sequentially and never overwritten.
- **Validation Firewall**: Every record is validated against dataclass contracts before disk write.
- **Fail-Closed Recovery**: Malformed or corrupted lines are safely detected and skipped without executing code or halting store iteration.
- **Rich Querying**: Multi-dimensional filtering by `outcome`, `evidence_type`, `day_phase`, `min_engagement_rating`, `session_completed`, `session_abandoned`, `schema_version`, and ISO timestamp intervals.

---

## 9. ExperienceCollector Workflow

The `ExperienceCollector` provides a non-intrusive builder pattern across pipeline stages:

```python
collector = ExperienceCollector(session_id="exp-session-001")
collector.record_event(EventType.SESSION_STARTED)
collector.record_intent(intent, query="2 kHz crossover")
collector.record_specification(spec)
collector.record_optimization(opt_result)
collector.record_graph(graph)
collector.record_execution(backend, config, total_time_s, blocks_processed, samples_processed)
collector.record_temporal_context(now_dt, sunrise_dt, sunset_dt)
collector.record_engagement(
    session_duration_s=1800.0,
    listening_duration_s=1750.0,
    interaction_count=3,
    session_completed=True,
    explicit_engagement_rating=4.8,
)
collector.record_feedback(status=FeedbackStatus.ACCEPTED, rating=5.0)

record = collector.build(evidence_type=EvidenceType.SOFTWARE_OFFLINE)
store.append(record)
```

The collector reads external objects without modifying their internal state.

---

## 10. Experience Store vs LLM Memory

> **The Experience Store is the historical evidence layer. It does not directly modify model weights or the acoustic Core.**

The Experience Store is an independent historical dataset. It does not contain neural network weights, LoRA adapters, embedding indexes, or vector database bindings. Future AI consumers read from the store to propose improved `DesignIntent` configurations, which AcoustiForge then independently validates through its deterministic firewall.

---

## 11. Privacy and Local-First Telemetry Policy

All runtime experience records, user queries, acoustic measurements, and hardware telemetry remain strictly on the local filesystem by default:
- Zero automatic cloud telemetry.
- Zero remote network uploads.
- Any future dataset sharing or export is an explicit, user-initiated action.

---

## 12. Implemented vs Deferred Capabilities

### Implemented
- Immutable `ExperienceRecord` and sub-contracts (`IntentSummary`, `SpecificationSummary`, `OptimizationSummary`, `GraphSummary`, `ExecutionContextSummary`, `RuntimeObservations`, `TemporalSolarContext`, `EngagementMetrics`, `ExperienceEvent`, `HumanFeedback`).
- Segregation of Behavioral vs User-Reported vs Derived engagement evidence.
- Session trajectory event logging (`EventType`).
- Timezone-aware diurnal solar calculation and day-phase classification.
- Local append-only JSONL `ExperienceStore` with query engine and fail-closed validation.
- Non-intrusive `ExperienceCollector` builder.
- Full end-to-end integration and isolation test suite.

### Deferred
- **LLM Fine-Tuning & Model Training**: Deferred until substantial real-world experience is accumulated.
- **Vector Database / Embedding Indexing**: Deferred to future AI consumer retrieval tracks.
- **Physical Room Sensor Ingestion**: Temperature/humidity telemetry bindings deferred until hardware sensor interfaces are specified.
