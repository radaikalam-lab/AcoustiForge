# AcoustiForge Phase 5-7A: Experience Retrieval & Analytics

**IMPLEMENTATION — PHASE 5-7A**

**Governing Architectural Invariants:**
> *AI proposes. AcoustiForge validates and executes.*
> 
> *Runtime teaches the AI layer; runtime does not rewrite the acoustic Core.*
> 
> *The Experience Store is the historical evidence layer.*
> 
> *Historical experience is advisory evidence, never an authoritative source of DSP parameters.*
> 
> *Temporal and solar context are contextual variables, not measurements of mood.*
> 
> *Behavioral engagement evidence must not be silently interpreted as satisfaction or psychological state.*
> 
> *Phase 5-7A does not perform semantic acoustic similarity, AI inference, prompt generation, preference learning, model training, or embedding-based retrieval.*

---

## 1. Purpose & Scope

Phase 5-7A implements the production retrieval and descriptive analytics layer over AcoustiForge's local-first JSONL `ExperienceStore` (Schema `1.1.0`).

This phase provides deterministic, inspectable query capabilities and transparent descriptive statistics over accumulated historical experience without introducing AI/LLM dependencies, dense vector embeddings, or opaque statistical learners.

```
                  ExperienceStore (Authoritative History)
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
     ExperienceRetriever         ExperienceAnalytics
   (Structured Query Engine)    (Descriptive Summaries)
              │                           │
              ▼                           ▼
      Filtered Records          Statistical Summaries
   (Advisory History Data)     (Transparent Aggregations)
```

---

## 2. ExperienceRetriever Contract & Query Interface

The retrieval layer is implemented in `acoustiforge.experience.retrieval.ExperienceRetriever` and consumes structured query specifications defined in `ExperienceQuery`.

### Supported Multi-Criteria Filters

| Category | Filter Attribute | Semantics |
|---|---|---|
| **Identity & Evidence** | `outcome`, `evidence_type`, `schema_version` | Exact categorical matching. |
| **Acoustic Intent & Spec** | `crossover_family`, `crossover_order`, `target_preset`, `spatial_profile` | Exact string/enum match. |
| **Frequency Bounds** | `target_frequency_range_hz`, `selected_crossover_range_hz` | Closed interval $[f_{\min}, f_{\max}]$. |
| **Spatial Configurations** | `min_spatial_positions` | Lower bound on measurement position count. |
| **Optimization Metrics** | `converged_only`, `max_loss_db`, `optimizer_name` | Convergence flag and upper loss threshold. |
| **Execution Context** | `backend_type`, `platform`, `sample_rate`, `channels`, `hardware_target` | Execution platform criteria. |
| **Engagement & Feedback** | `min_engagement_rating`, `min_user_rating`, `feedback_status`, `session_completed_only`, `session_abandoned_only`, `min_listening_duration_s`, `max_reverted_changes` | Threshold and completion status filters. |
| **Temporal & Diurnal** | `day_phase`, `start_time_iso`, `end_time_iso` | Solar phase and ISO timestamp window. |
| **Pagination** | `limit` | Maximum records returned. |

---

## 3. Deterministic Ranking Semantics

`ExperienceRetriever.deterministic_rank()` sorts matching records strictly according to a deterministic hierarchical policy:

1. **Outcome Quality Tier:** `SUCCESS` (0) $\to$ `PARTIAL` (1) $\to$ `UNKNOWN` (2) $\to$ `REJECTED` (3) $\to$ `FAILED` (4).
2. **Explicit Human Rating:** Highest user/engagement rating first (unrated records placed after rated records).
3. **Acoustic Proximity:** If `target_crossover_hz` is specified, ranked by $|f_{\text{selected}} - f_{\text{target}}|$ ascending.
4. **Optimization Final Loss:** Lowest `final_loss_db` ascending.
5. **Stable Immutable Tie-Breaker:** Lexicographical order of `experience_id`.

No random seeds, hash randomization, wall-clock ordering, or opaque weighting coefficients are used.

---

## 4. Evidence Segregation & Non-Inference Boundaries

1. **Evidence Type Separation:**
   - `SOFTWARE_OFFLINE`, `PHYSICAL_HARDWARE`, and `HYBRID_SIMULATION` records are strictly separated.
   - If a query specifies `evidence_type=PHYSICAL_HARDWARE`, synthetic offline records are never returned.
2. **Engagement vs Mood:**
   - Raw behavioral metrics (`listening_duration_s`, `replay_count`) are treated as descriptive observations, never converted into emotional labels (e.g. listening duration $\neq$ satisfaction).
   - `derived_engagement_score` is explicitly segregated and never promoted to raw observed evidence.
3. **Temporal vs Psychological Context:**
   - Diurnal solar context (`day_phase`) is strictly an astronomical/temporal index, not a psychological indicator.

---

## 5. ExperienceAnalytics Contract & Statistical Discipline

`ExperienceAnalytics` calculates transparent, descriptive aggregations across collections of `ExperienceRecord`s without machine learning or predictive models.

### Analytical Summaries

- **Optimization (`OptimizationAnalyticsSummary`):** Total count, converged count, convergence ratio, mean initial loss (dB), mean final loss (dB), mean loss reduction (dB), min/max final loss, mean optimizer iterations.
- **Engagement (`EngagementAnalyticsSummary`):** Mean and total listening duration (s), mean session duration (s), mean interaction count, mean replay count, completed/abandoned session counts, completion ratio, rated session count, mean explicit engagement rating.
- **Runtime (`RuntimeAnalyticsSummary`):** Mean block time ($\mu\text{s}$), total blocks/samples processed, total xruns, clipping event count, mean realtime margin (derived).
- **Groupings:** `group_by_crossover_family()`, `group_by_day_phase()`, `group_by_evidence_type()`, `group_by_platform()`.

### Statistical Discipline Rules
- Missing optional metrics return `None` rather than being converted to `0.0`.
- Empty record sequences return a clean summary with count 0 and `None` for all numeric averages.
- Small sample statistics (e.g., $N=2$) are reported purely descriptively and are not claimed as population baselines.

---

## 6. Computational Complexity

- **Storage Scan:** $O(N)$ linear stream over the append-only JSONL backing store.
- **Filtering & Ranking:** $O(M \log M)$ where $M \le N$ is the number of matching records.
- **Analytics Aggregation:** $O(M)$ single-pass aggregation.
- **Memory Footprint:** Zero permanent in-memory index or background daemon overhead; lightweight and embedded-safe.

---

## 7. Deferred Capabilities

The following capabilities are strictly deferred to future tracks:
- **Prompt Context Generation (`ExperiencePromptContext`):** Deferred to AI integration phases.
- **AI / LLM Integration & RAG:** Local LLM query augmentation deferred.
- **Semantic Acoustic Distance & Latent Embeddings:** Dense vector search rejected.
- **Preference Learning / Predictive Classifiers:** Supervised learning deferred until substantial physical human usage data accumulates.
- **Physical ALSA Validation (Phase 5-4C):** Physical Raspberry Pi / USB DAC playback validation remains on its dedicated validation gate.
