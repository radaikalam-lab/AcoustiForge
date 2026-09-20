# AcoustiForge — Post-Freeze Architectural Integration & Scientific Productization (P0)

**Document ID:** `DOC-INTEGRATION-P0-01`  
**Governing Authority:** AcoustiForge Scientific Architecture Framework & Semantic Amendment (`DOC-EPISTEMIC-AMEND-01`)  
**Status:** Approved Architectural Discovery & Integration Specification  
**Scope:** Post-Freeze Scientific Productization Boundary (E0.5–E10 Unmodified)

---

## 1. Purpose

With the formal freezing of the AcoustiForge Epistemic Subsystem (Phases E0.5–E10), this document establishes how the frozen epistemic layers are integrated into future end-to-end scientific workflows, AI agent interfaces, measurement pipelines, and production compiler handoffs without compromising the fundamental safety law:

$$\boxed{
\text{Epistemic Novelty} \neq \text{Production Authority}
}$$

This phase is **P0 — Post-Freeze Architectural Integration**. It treats E0.5–E10 as a stable, frozen dependency and defines the external interface contracts surrounding it.

---

## 2. Frozen Architecture Reference

The governing frozen epistemic architecture comprises the following immutable layers:

* **Semantic Freeze & Vocabulary (E0.5, E1):** `vocabulary.py` — Typed enums for Zones (`ZONE_H`, `ZONE_M`, `ZONE_P`, `ZONE_U`), Epistemic Classes, Lifecycle States, Evidence Taxonomy, and Evidence Relations.
* **Assumption Registry (E2):** `assumptions.py` — Explicit, bounded, immutable assumption descriptors without truth/confidence scores.
* **Model Registry (E3):** `models.py` — Explanatory model definitions with falsification criteria.
* **Unknowns & Residuals (E4):** `unknowns.py`, `residuals.py` — Formal representation of systematic anomalies and candidate diagnostic assessments (`RESIDUAL != MODEL_ERROR`).
* **Epistemic Challenges (E5):** `challenges.py` — Scoped questioning of models and assumptions under declared test conditions.
* **Model Competition (E6):** `competition.py` — Dimension-separated comparative profiles (AIC/BIC, empirical fit, robustness) without singular winners.
* **Falsification & Review (E7):** `falsification.py` — Explicit state machine: $\text{VALIDATED\_MODEL} \to \text{FALSIFICATION\_EVIDENCE\_DETECTED} \to \text{UNDER\_REVIEW} \to \{\text{DOMAIN\_LIMITED}, \text{CHALLENGED}, \text{FALSIFIED}\}$.
* **Objective Challenge (E8):** `objectives.py` — Separation of optimization objectives, proxy losses, and physical laws.
* **Representation Challenge (E9):** `representation.py` — Representation schemas and gaps ($\text{NOT\_REPRESENTABLE} \neq \text{PHYSICALLY\_IMPOSSIBLE}$).
* **Theory Transitions & Red-Team (E10):** `transitions.py` — Auditable scientific lineage records and full 26-point invariant validation.

---

## 3. Repository Archaeology

A systematic inspection of the AcoustiForge codebase identified the following state of existing subsystem interfaces:

| Subsystem Component | Module Location | Status | Architectural Role |
| :--- | :--- | :--- | :--- |
| **Measurement Parsers** | `src/acoustiforge/io/` | **EXISTS** | Deterministic parsing of `.frd`, `.csv`, `.txt`, `.cal`, and `.wav` files into numerical arrays. |
| **Domain Measurements** | `src/acoustiforge/domain/measurements.py` | **EXISTS** | Immutable `FrequencyResponseData` contiguous array containers. |
| **Domain Profiles & Specs** | `src/acoustiforge/domain/` | **EXISTS** | `DriverProfile`, `EnclosureProfile`, `CrossoverSpecification`, `OptimizationSpecification`. |
| **DSP Core & Graph** | `src/acoustiforge/graph/`, `nodes/` | **EXISTS** | Authoritative typed compute graph and biquad/gain/delay DSP primitives. |
| **Acoustic Mathematics** | `src/acoustiforge/acoustic_math/` | **EXISTS** | SLSQP/DE optimizer, target curve generator, gating, metrics, and protection. |
| **Execution Plane** | `src/acoustiforge/execution/` | **EXISTS** | ALSA hardware backend, Linux SBC hooks, and offline deterministic runner. |
| **Design Intent Firewall** | `src/acoustiforge/intent/` | **EXISTS** | `DesignIntentAdapter` compiling untrusted user/AI intent into Core specs. |
| **Experience Store** | `src/acoustiforge/experience/` | **EXISTS** | Local-first, append-only JSONL telemetry store. |
| **Epistemic Subsystem** | `src/acoustiforge/epistemic/` | **EXISTS (FROZEN)** | Complete E0.5–E10 scientific reasoning layer. |
| **Observation Envelope** | External Interface | **MISSING** | Structured wrapper linking raw sweep arrays to environmental metadata and acquisition provenance. |
| **Scientific Experiment Contract** | External Interface | **MISSING** | Structured protocol for parameter manipulation, predicted vs actual sweeps, and residual capture. |
| **Production Authorization Gate** | External Interface | **MISSING** | Formal audit interface for human sign-off promoting `PRODUCTION_CANDIDATE` to `PRODUCTION_AUTHORITY`. |
| **Epistemic Local Store** | External Interface | **MISSING** | Append-only JSONL persistence for epistemic tournament histories and registry snapshots. |

---

## 4. Existing Integration Points

1. **Measurement Import to Numerical Domain:** `MeasurementParser.parse_file()` produces `MeasurementImportResult` containing `FrequencyResponseData`.
2. **Untrusted Intent Validation Firewall:** `DesignIntentAdapter.compile()` validates untrusted intent objects and compiles them into Core `OptimizationSpecification` without leaking AI authority.
3. **Local-First JSONL Store:** `ExperienceStore` provides an append-only, validated, non-executable storage engine on local disk.
4. **Epistemic Registry Queries:** All E1–E10 registries provide deterministic query methods (`get()`, `list_all()`, `find_by_*()`) and JSON round-trip serialization.

---

## 5. Missing Integration Points

1. **Observation Acquisition Envelope:** A value object encapsulating `FrequencyResponseData` alongside sensor calibration IDs, ambient temperature, humidity, microphone distance, SPL calibration offset, and operator identity.
2. **Experiment Protocol Contract:** An external workflow contract grouping manipulated variables (e.g. input drive voltage, chamber angle), controlled parameters, candidate model predictions, acquired observations, and resulting residuals.
3. **AI Proposal Gateway:** A standardized proposal receiver converting LLM outputs into strictly unprivileged candidate objects (`EpistemicChallenge`, `RepresentationGap`, `ObjectiveChallenge`) marked with `AI_GENERATED_HYPOTHESIS`.
4. **Human Production Authority Gate:** An explicit sign-off mechanism generating an immutable `ProductionAuthorizationRecord` required before Core builders accept an epistemic candidate model.
5. **Local-First Epistemic Store:** An append-only persistence layer archiving tournament results, challenge manifests, and theory transition records.

---

## 6. Measurement → Epistemic Boundary

Acoustic measurements enter the scientific pipeline through a strict 4-stage data transformation:

```text
Physical Transducer Sweep
        ↓
Measurement File (.frd, .cal, .wav)
        ↓  [src/acoustiforge/io/parser.py]
FrequencyResponseData (Raw Numerical Vectors)
        ↓  [Observation Envelope Interface]
Observation Record (Acoustic Data + Acquisition Metadata)
        ↓  [src/acoustiforge/epistemic/representation.py]
Epistemic Representation (Mapped to Modeled Variables)
        ↓  [src/acoustiforge/epistemic/vocabulary.py]
EpistemicEvidenceLink (Typed Evidence linking Observation to Theory)
```

### Key Principles
* **Raw vs Derived:** Raw sample arrays remain immutable. Smoothing, windowing, and phase unwrapping are recorded as explicit transform steps in metadata.
* **Uncertainty as Evidence Dimension:** Measurement SNR, repeatability variance, and ambient noise floor are preserved as distinct evidence metrics; they are **never collapsed into a single scalar confidence score**.
* **Reproducibility:** Re-deriving an observation from raw sweep recordings produces bit-identical frequency response vectors.

---

## 7. Experiment Boundary

Future scientific experimentation in AcoustiForge will be structured around an external **Experiment Protocol**:

```text
Experiment Protocol
 ├── Target Model Under Test (Model ID)
 ├── Competing Candidate Models (Tuple of Model IDs)
 ├── Representation Formalism (Representation ID)
 ├── Controlled Variables (Temperature, Chamber Geometry, Microphone Position)
 ├── Manipulated Variables (Drive Voltage, Frequency Band, Input Power)
 ├── Model Predictions (Expected SPL/Impedance curves)
 ├── Acquired Observations (Observation IDs)
 ├── Residual Analysis (Residual ID & ResidualAssessment)
 ├── Generated Evidence (FalsificationEvidence / EvidenceLinks)
 └── Outcome Summary (Audit findings without automated truth claims)
```

* **Non-Authority:** An experiment executes models and records evidence. It cannot alter production DSP parameters or promote models.

---

## 8. Evidence Acquisition Boundary

The pipeline maintains a strict distinction between **empirical data** and **evidence interpretation**:

$$\boxed{
\text{Data} \neq \text{Evidence Interpretation}
}$$

1. **Evidence Categorization:** Every evidence artifact is classified under `EpistemicEvidenceType` (`PHYSICAL_MEASUREMENT`, `SIMULATION`, `MATHEMATICAL_PROOF`, `ENGINEERING_TEST`, `AI_GENERATED_HYPOTHESIS`).
2. **Relational Linking:** Evidence is linked to targets using `EpistemicEvidenceLink` with explicit relations (`SUPPORTS`, `CONTRADICTS`, `CHALLENGES`, `LOCALIZES`, `DISCRIMINATES`, `DOES_NOT_TEST`).
3. **AI Quarantine:** Hypotheses formulated by AI/LLM systems are permanently tagged as `AI_GENERATED_HYPOTHESIS` and cannot masquerade as `PHYSICAL_MEASUREMENT` or `EXPERIMENTAL_RESULT`.

---

## 9. AI Integration Boundary

Future AI systems interact with AcoustiForge through an isolated **Proposal Gateway**:

```text
                  ┌──────────────────────────────┐
                  │          AI / LLM            │
                  └──────────────┬───────────────┘
                                 │ Generates Proposals
                                 ▼
                  ┌──────────────────────────────┐
                  │    PROPOSAL GATEWAY / API    │
                  └──────────────┬───────────────┘
                                 │ Validates Schema & Tags Source
                                 ▼
                  ┌──────────────────────────────┐
                  │    FROZEN EPISTEMIC LAYER    │
                  │           E0.5–E10           │
                  └──────────────┬───────────────┘
                                 │ Advisory Candidates Only
                                 ▼
                  ┌──────────────────────────────┐
                  │   HUMAN AUDIT & EXPERIMENT   │
                  └──────────────┬───────────────┘
                                 │ Explicit Sign-Off
                                 ▼
                  ════════════════════════════════
                     EXPLICIT AUTHORITY GATE
                  ════════════════════════════════
                                 │ Authoritative Specs
                                 ▼
                  ┌──────────────────────────────┐
                  │   DETERMINISTIC CORE (PROD)  │
                  └──────────────────────────────┘
```

### Allowed AI Proposals
* New `EpistemicAssumption` descriptors.
* Candidate `EpistemicModel` definitions with falsification criteria.
* Formal `EpistemicChallenge` manifests against existing models.
* Proposed `RepresentationGap` and `ObjectiveChallenge` records.
* Candidate explanation hypotheses for unexplained `ModelResidual` instances.

### Prohibited AI Actions
* Direct mutation of production compute graphs or DSP filter nodes.
* Automatic promotion of candidate models to `PRODUCTION_AUTHORITY`.
* Direct modification of production optimization loss functions.
* Overriding hardware protection limits or ALSA execution buffers.

---

## 10. Human Scientist Interface

AcoustiForge must provide human researchers with transparent, non-scalar audit views answering four fundamental questions:

1. **Lineage:** *"Why is this candidate model under consideration?"* (Inspected via `TheoryTransitionRecord` and `ModelComparison`).
2. **Falsification Risk:** *"What evidence would refute this model?"* (Inspected via `FalsificationCriterion` and `FalsificationEvidence`).
3. **Representation Limits:** *"What physical effects are intentionally or unintentionally omitted?"* (Inspected via `RepresentationDefinition.omitted_variables` and `RepresentationGap`).
4. **Authority Separation:** *"Why is this model not in production?"* (Inspected via lack of `ProductionAuthorizationRecord`).

---

## 11. Production Handoff Boundary

When a candidate model and design configuration successfully pass scientific evaluation, promotion to production requires an explicit **Production Authorization Gate**:

```text
Candidate Model (Zone M) + Compiled Specs
        ↓
Audited Theory Transition (E10)
        ↓
Production Candidate State (PRODUCTION_CANDIDATE)
        ↓
Human Engineering Review & Physical Bench Validation
        ↓
ProductionAuthorizationRecord (Signed by Authorized Engineer)
        ↓
Production Validation Firewall (Range, Stability & Realizability Checks)
        ↓
Core Compute Graph Compilation (Authoritative Biquad/Gain/Delay Nodes)
```

The Production Core accepts specifications only when accompanied by a valid, verified `ProductionAuthorizationRecord`.

---

## 12. Provenance Continuity

Complete end-to-end traceability is preserved from raw acoustic transducer measurement to compiled DSP binaries:

```text
Measurement (File Hash, Instrument Serial, Calibration ID)
    ↓
Observation (Envelope ID, Ambient Conditions)
    ↓
Representation (Schema ID, Mapped Degrees of Freedom)
    ↓
Residual (Observed vs Model Discrepancy)
    ↓
Challenge (Scoped Questioning Manifest)
    ↓
Candidate Model (Mechanisms Represented vs Omitted)
    ↓
Comparison (AIC/BIC Tradeoff Profile)
    ↓
Falsification Evidence (Threshold Violation Record)
    ↓
Model Review (Explicit Transition to DOMAIN_LIMITED / FALSIFIED)
    ↓
Theory Transition (Lineage Audit Record)
    ↓
Production Candidate (Advisory Proposal)
    ↓
Production Authorization (Cryptographic/Audited Human Sign-off)
    ↓
Production DSP Pipeline (Deterministic Compute Graph)
```

No link in this chain may be bypassed or erased.

---

## 13. Auditability Requirement

All optimizer trajectories and parameter exploration logs must be permanently reconstructable:
* **Candidate History:** Initial parameter seeds, intermediate steps, termination conditions.
* **Loss Breakdown:** Individual multi-objective error dimensions (SPL error, phase deviation, impedance peak).
* **Constraint Checks:** Explicit recording of driver excursion, amplifier thermal dissipation, and filter Q limits.

---

## 14. Offline & Local-First Requirements

AcoustiForge is strictly **local-first and offline-capable**:
1. **Zero Cloud Mandates:** The scientific reasoning and DSP synthesis pipelines function completely disconnected from external networks.
2. **Local Persistence:** All registries, tournament results, and experience records are stored on local non-volatile storage using open, human-readable formats (JSON, JSONL).
3. **Reproducibility:** Experiments and model tournaments re-executed on identical local input files produce bit-exact deterministic results across different hosts.

---

## 15. Interface Map

```text
External Measurement Sources (Microphone Array, Soundcard, Klippel, Clio)
        │
        ▼
[Observation Ingestion Interface]
        │
        ▼
[Representation Mapping Boundary (E9)]
        │
        ▼
[Frozen Epistemic Subsystem (E0.5–E10)]
  ├── Assumptions (E2)
  ├── Models & Falsification (E3, E7)
  ├── Unknowns & Residuals (E4)
  ├── Challenges & Competition (E5, E6)
  ├── Objectives (E8)
  └── Theory Transitions (E10)
        │
        ├── [AI Proposal Gateway] (Hypothesis & Challenge Generation)
        ├── [Human Scientist Console] (Audit & Inspection Views)
        └── [Experiment Runner] (Controlled Empirical Verification)
        │
        ▼
[Production Candidate Envelope (PRODUCTION_CANDIDATE)]
        │
        ▼
════════════════════════════════════════════════════════════════════════
              EXPLICIT PRODUCTION AUTHORITY GATE (HUMAN SIGN-OFF)
════════════════════════════════════════════════════════════════════════
        │
        ▼
[Production Validation Firewall (DesignIntentAdapter / Spec Validators)]
        │
        ▼
[Deterministic Production Core (ComputeGraph, DSP Nodes, ALSA Hardware)]
```

---

## 16. Freeze Compatibility Analysis

Every proposed P0 integration interface was audited against the frozen E0.5–E10 semantics:

| Freeze Question | Audit Finding | Compatibility |
| :--- | :--- | :--- |
| Does P0 require changing E0.5–E10 vocabulary? | **NO.** Reuses existing enums and types unchanged. | **COMPATIBLE** |
| Does P0 alter status lifecycle state machines? | **NO.** Preserves `VALIDATED_MODEL` to `FALSIFIED` workflow. | **COMPATIBLE** |
| Does P0 introduce a hidden model winner or truth score? | **NO.** Preserves dimension separation and multi-objective profiles. | **COMPATIBLE** |
| Does P0 allow AI proposals to silently gain Core authority? | **NO.** AI proposals are strictly quarantined in Epistemic Layer. | **COMPATIBLE** |
| Does P0 modify deterministic production Core packages? | **NO.** Core packages remain 100% untouched. | **COMPATIBLE** |

---

## 17. Future Work (Post-P0 Roadmap)

1. **Phase P1 — Scientific Observation & Experiment Envelope:** Implement the external `ObservationEnvelope` and `ExperimentSession` value objects.
2. **Phase P2 — Epistemic JSONL Store:** Implement the local-first append-only persistence layer for Epistemic registries based on the `ExperienceStore` architecture.
3. **Phase P3 — AI Proposal Gateway:** Implement the deterministic parsing and validation firewall for AI-generated challenge manifests and model hypotheses.
4. **Phase P4 — Production Authorization Interface:** Implement the formal sign-off and promotion protocol for transitioning `PRODUCTION_CANDIDATE` models into production `ComputeGraph` configurations.

---

## 18. Explicit Non-Goals

* **NO E11 Implementation:** No new epistemic abstractions or phases will be created.
* **NO Autonomous Truth Engine:** The system will never declare a single universal "true" acoustic theory.
* **NO Automated Core Deployment:** No machine learning algorithm or tournament winner will automatically deploy code to production DSP pipelines without human sign-off.
* **NO Production Core Modifications:** Core DSP mathematics, compute graphs, and hardware backends remain unchanged.
