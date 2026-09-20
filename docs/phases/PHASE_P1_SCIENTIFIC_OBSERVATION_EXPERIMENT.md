# AcoustiForge — Phase P1 & P1.1: Scientific Observation & Experiment Envelope

**Phase:** `P1` (and `P1.1 Hardening`)  
**Governing Authority:** AcoustiForge Post-Freeze Architectural Integration (`DOC-INTEGRATION-P0-01`)  
**Status:** IMPLEMENTED, HARDENED & VERIFIED  
**Production Core Modified:** NO  
**Epistemic Freeze Reopened:** NO

---

## 1. Purpose

Phase P1 and P1.1 implement and harden the external scientific integration contracts identified during Phase P0 discovery:
1. `ObservationEnvelope`: Encapsulates acoustic measurement vectors (`FrequencyResponseData`) with acquisition metadata, sensor calibration, environmental conditions, and explicit transformation provenance.
2. `ExperimentSession`: Groups controlled environmental variables, manipulated test parameters, candidate model predictions, acquired observation IDs, and resulting residual IDs.

Both abstractions operate **strictly external to the frozen E0.5–E10 epistemic layers and outside the Production Core**.

---

## 2. Existing Interfaces Reused

* `FrequencyResponseData` ([`src/acoustiforge/domain/measurements.py`](file:///e:/AcoustiForge/src/acoustiforge/domain/measurements.py)): Reused unmodified as the raw numerical measurement payload.
* `InvalidMeasurementError`, `InvalidSpecificationError` ([`src/acoustiforge/domain/validation.py`](file:///e:/AcoustiForge/src/acoustiforge/domain/validation.py)): Reused for deterministic error handling and validation.
* `MeasurementParser` ([`src/acoustiforge/io/parser.py`](file:///e:/AcoustiForge/src/acoustiforge/io/parser.py)): Ingests raw `.frd`, `.csv`, `.cal`, and `.wav` files into `FrequencyResponseData`.

---

## 3. ObservationEnvelope Contract

Located at [`src/acoustiforge/science/observation.py`](file:///e:/AcoustiForge/src/acoustiforge/science/observation.py):

```python
@dataclass(frozen=True, slots=True)
class ObservationEnvelope:
    observation_id: str
    data: FrequencyResponseData
    source_reference: str
    source_format: str
    sensor_id: Optional[str] = None
    calibration_id: Optional[str] = None
    operator: Optional[str] = None
    microphone_distance_m: Optional[float] = None
    spl_calibration_offset_db: Optional[float] = None
    environmental_conditions: EnvironmentalConditions = field(default_factory=EnvironmentalConditions)
    uncertainty: MeasurementUncertainty = field(default_factory=MeasurementUncertainty)
    transforms: tuple[MeasurementTransform, ...] = ()
    provenance: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

### Key Semantics & Hardening
* **Ownership of Acquisition Context:** `ObservationEnvelope` exclusively owns and encapsulates the physical sweep, instrument serials, environmental metrics, and calibration state.
* **Deep Immutability & Defensive Copying:** All nested dictionary attributes (`metadata`, transform `parameters`) are recursively frozen into read-only `MappingProxyType` instances with defensive copying on ingest.
* **Raw-Data Wrapping:** Wraps `FrequencyResponseData` without modifying or replacing it; numpy arrays remain strictly read-only and alias-isolated.
* **Transform Lineage:** Records explicit `MeasurementTransform` entries (`transform_type`, `parameters`, `rationale`) so derived data is never confused with raw measurements.
* **Separated Uncertainty:** `MeasurementUncertainty` preserves SNR, repeatability variance, and calibration uncertainty separately without collapsing them into a single truth/confidence scalar.

---

## 4. ExperimentSession Contract

Located at [`src/acoustiforge/science/experiment.py`](file:///e:/AcoustiForge/src/acoustiforge/science/experiment.py):

```python
@dataclass(frozen=True, slots=True)
class ExperimentSession:
    experiment_id: str
    name: str
    description: str
    lifecycle_state: ExperimentLifecycleState = ExperimentLifecycleState.DEFINED
    target_model_ids: tuple[str, ...] = ()
    representation_id: Optional[str] = None
    controlled_variables: Mapping[str, Any] = field(default_factory=dict)
    manipulated_variables: Mapping[str, Any] = field(default_factory=dict)
    observation_ids: tuple[str, ...] = ()
    prediction_references: Mapping[str, str] = field(default_factory=dict)
    residual_references: tuple[str, ...] = ()
    provenance: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

### Key Semantics & Hardening
* **Protocol & Reference Ownership:** `ExperimentSession` references observations by stable string IDs (`observation_ids`) rather than duplicating raw acquisition metadata into the session record.
* **Deep Immutability & Defensive Copying:** `controlled_variables`, `manipulated_variables`, `prediction_references`, and `metadata` are recursively frozen into read-only `MappingProxyType` structures.
* **Controlled vs Manipulated Partitioning:** Explicit separation of fixed ambient/chamber conditions from manipulated experimental parameters (e.g. drive voltage, angle, power).
* **Prediction vs Observation Separation:** Preserves model predictions and measured responses as distinct reference keys.
* **Stable Identifiers:** References models, representations, observations, and residuals via stable string IDs rather than embedding mutable registry objects.

---

## 5. Provenance & Identity Model

* **Ownership Boundary:**
  * `ObservationEnvelope` owns acquisition context (sensor, calibration, distance, ambient environment, raw arrays).
  * `ExperimentSession` references observations and defines the experimental protocol (manipulated/controlled conditions, model predictions, residual traces).
* **Stable Identity:** `observation_id` and `experiment_id` are explicit caller-supplied or deterministic content-derived strings.
* **Zero Nondeterministic Identity:** No use of `uuid.uuid4()`, `time.time()`, or `random` for identity generation.
* **Traceable Lineage:** An experiment session links directly to source measurement files, sensor serials, calibration IDs, operator identity, and chamber conditions.

---

## 6. Serialization Model

* Both `ObservationEnvelope` and `ExperimentSession` implement deterministic `to_dict()` and `from_dict()` methods.
* All nested array vectors (`FrequencyResponseData`), environmental records, frozen mapping proxies, and transform histories round-trip through JSON with 100% fidelity.

---

## 7. Lifecycle Model

* `ExperimentLifecycleState`: `DEFINED` $\to$ `ACQUIRING` $\to$ `COMPLETED` (or `ABORTED`).
* Strictly isolated from `EpistemicStatus`; experiment lifecycle states represent operational execution phase rather than epistemic truth claims.

---

## 8. Semantic Boundaries

* $\text{DATA} \neq \text{EVIDENCE INTERPRETATION}$
* $\text{OBSERVATION} \neq \text{FALSIFICATION}$
* $\text{EXPERIMENT} \neq \text{MODEL}$
* $\text{EXPERIMENT} \neq \text{OBJECTIVE}$
* $\text{EXPERIMENT} \neq \text{PRODUCTION\_AUTHORITY}$
* $\text{CONTROLLED\_VARIABLES} \neq \text{MANIPULATED\_VARIABLES}$
* $\text{PREDICTION} \neq \text{OBSERVATION}$
* $\text{OBSERVATION\_CONTEXT} \neq \text{EXPERIMENT\_PROTOCOL}$

---

## 9. Test Verification

* Dedicated test suites:
  * `tests/science/test_observation_envelope.py` (7 tests)
  * `tests/science/test_experiment_session.py` (6 tests)
  * `tests/science/test_science_integration.py` (5 tests)
* **P1 & P1.1 Suite:** 18 passed (100% passing)
* **Full Suite:** 819 passed, 2 skipped (0 failures, 0 warnings)

---

## 10. Production Core & Freeze Isolation

* **Production Core (`src/acoustiforge/{domain,acoustic_math,graph,nodes,execution,intent}`):** UNTOUCHED (0 modifications).
* **Frozen Epistemic Subsystem (`src/acoustiforge/epistemic/`):** UNTOUCHED (0 modifications).

---

## 11. Deferred Work (P2 / P3 / P4)

* **P2 (Local JSONL Store):** Persistence for scientific observations and experiment sessions is deferred to Phase P2.
* **P3 (AI Proposal Gateway):** Automated proposal ingestion firewalls are deferred to Phase P3.
* **P4 (Production Authorization Gate):** Formal promotion sign-off contracts are deferred to Phase P4.
