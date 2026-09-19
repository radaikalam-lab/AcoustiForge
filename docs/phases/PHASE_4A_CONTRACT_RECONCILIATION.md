# AcoustiForge — Phase 4A Contract Reconciliation & Implementation Gate
## Measurement File Ingestion, Microphone Calibration & Measurement-Driven EQ Graph Construction

---

## 1. Purpose

This document establishes the normative contracts, architectural boundaries, and verification criteria for **Phase 4A: Measurement Pipeline & Measurement-Driven EQ Integration**.

Following the completed Phase 4 Discovery (`docs/phases/PHASE_4_DISCOVERY.md`), this reconciliation pass defines exact specifications before any production implementation is authorized.

**Governing Objective:**
Create a complete, deterministic vertical slice:
$$\text{Raw Measurement File (.frd / .csv / .txt)} \longrightarrow \text{Ingestion Parser} \longrightarrow \text{Microphone Calibration} \longrightarrow \text{Parametric EQ Synthesis} \longrightarrow \text{ComputeGraph Construction} \longrightarrow \text{PCM Execution}$$
without modifying frozen domain models, compute graph contracts, or DSP node implementations.

---

## 2. Frozen Baseline

- **Phase 3B Domain Plane:** FROZEN (`src/acoustiforge/domain/`).
- **Phase 3C Acoustic Mathematics:** FROZEN (`src/acoustiforge/acoustic_math/`).
- **Phase 3D Graph Builders:** FROZEN (`src/acoustiforge/builders/`).
- **Phase 2B Typed Compute Graph:** FROZEN (`src/acoustiforge/graph/`).
- **Phase 0/1 DSP Engine & Nodes:** FROZEN (`src/acoustiforge/nodes/`, `engine/`).
- **Regression Suite:** 279 passed in 0.98s (`pytest -q -W error`).

---

## 3. Phase 4 Discovery Inputs

Phase 4 Discovery evaluated six capability candidates:
- *Candidate A (Measurement Ingestion):* Selected for Phase 4A.
- *Candidate B (Microphone Calibration):* Selected for Phase 4A.
- *Candidate C (Acoustic Response Analysis):* Retained for Phase 4B/deferred.
- *Candidate D (Multi-Way Graph Builders):* Retained for Phase 4B/deferred.
- *Candidate E (Measurement-Driven EQ Graph Integration):* Selected for Phase 4A.
- *Candidate F (Hardware / Real-Time Streaming):* Deferred.

---

## 4. Measurement Ingestion Contract

Governed by `docs/contracts/MEASUREMENT_INGESTION_CONTRACT.md` (`CONTRACT-MEASUREMENT-INGESTION-01`):

1. **Supported Formats:** Tabular ASCII `.frd`, `.csv`, `.txt` (including Room EQ Wizard text exports).
2. **Column Structure:**
   - 2-Column: `[frequency_hz, magnitude_db]` $\implies$ Magnitude-only.
   - 3-Column: `[frequency_hz, magnitude_db, phase_deg]` $\implies$ Magnitude and Phase.
3. **Invariants:**
   - Frequency: strictly positive ($f > 0$), strictly ascending ($f_{i+1} > f_i$), finite, non-empty ($N \ge 2$).
   - Magnitude: finite real numbers in dB SPL / dB.
   - Phase: optional finite real numbers in degrees (converted to radians for canonical storage).
4. **Error Taxonomy:**
   - Base: `MeasurementIngestionError`
   - Formats: `UnsupportedMeasurementFormatError`
   - Syntax: `MalformedMeasurementDataError`
   - Invariants: `InvalidMeasurementDataError`

---

## 5. Microphone Calibration Contract

Governed by `docs/contracts/MICROPHONE_CALIBRATION_CONTRACT.md` (`CONTRACT-MICROPHONE-CALIBRATION-01`):

1. **Mathematical Correction:**
   $$M_{\text{corrected}}(f_i) = M_{\text{raw}}(f_i) - M_{\text{cal}}(f_i) \quad [\text{dB}]$$
   $$\phi_{\text{corrected}}(f_i) = \phi_{\text{raw}}(f_i) - \phi_{\text{cal}}(f_i) \quad [\text{radians, if present}]$$
2. **Frequency Alignment:** Piecewise linear interpolation in $\log_{10}(f)$ domain.
3. **Boundary Policy:**
   - `CLAMP` (default): Calibration offset is clamped to edge values ($M_{\text{cal}}(f_{\min})$, $M_{\text{cal}}(f_{\max})$).
   - `ZERO_PAD`: Out-of-bounds offset is $0.0\text{ dB}$.
   - `STRICT`: Raises `CalibrationOutOfRangeError` if measurement frequencies exceed calibration band.
4. **Data Container:** Reuses `FrequencyResponseData` directly without creating redundant classes.

---

## 6. Measurement Provenance Contract

To maintain Phase 3B domain immutability without polluting `FrequencyResponseData` with file I/O metadata:
- **Parser Result Wrapper:**
  ```python
  @dataclass(frozen=True, slots=True)
  class MeasurementImportResult:
      """Immutable container holding parsed measurement data and file provenance."""
      data: FrequencyResponseData
      source_format: str
      source_path: Optional[str] = None
      header_comments: tuple[str, ...] = ()
  ```
- `FrequencyResponseData` remains a pure mathematical value type (`frequencies_hz`, `magnitude_db`, `phase_rad`).

---

## 7. Measurement-Driven EQ Integration Contract

The integration pipeline executes in three strict stages:

```
Step 1: Parse & Calibrate (Control Plane / IO)
  raw_file.frd + mic.cal -> Calibrated FrequencyResponseData

Step 2: Parametric EQ Synthesis (Phase 3C Math)
  synthesize_parametric_eq(measurement, budget, sample_rate, target_curve) -> EQSynthesisResult

Step 3: Graph Translation (Phase 3D Builder)
  CrossoverGraphBuilder.build_2way_graph(..., equalizers={"woofer": eq_woofer, "tweeter": eq_tweeter})
```

- Zero measurement parsing inside graph builders.
- Zero target interpolation inside graph builders.
- Zero filter optimization inside graph builders.

---

## 8. Graph Builder Integration Decision

**Decision: Additive Extension to `CrossoverGraphBuilder`**
- `CrossoverGraphBuilder.build_2way_graph` receives an optional `equalizers: Optional[Mapping[str, EQSynthesisResult]] = None`.
- If provided, the builder inserts a cascade of `BiquadNode` instances for the driver's EQ bands with deterministic IDs:
  `f"{driver_name}.eq.{idx}"`
- **Backwards Compatibility:** If `equalizers` is omitted or `None`, the generated topology is bit-exact identical to the Phase 3D baseline.

---

## 9. EQ Placement Decision

### Canonical Branch Signal Order
$$\text{Branch Root} \longrightarrow [\text{DelayNode}] \longrightarrow [\text{GainNode}] \longrightarrow [\text{BiquadNode: EQ Cascade}] \longrightarrow [\text{BiquadNode: Crossover}] \longrightarrow [\text{BiquadNode: Protection}] \longrightarrow \text{Output}$$

### Signal Model Rationale
1. **Delay (`DelayNode`):** Synchronizes driver acoustic center before any amplitude/spectral shaping.
2. **Gain (`GainNode`):** Applies passband sensitivity trimming, establishing reference dynamic range headroom.
3. **Parametric EQ (`BiquadNode: EQ Cascade`):** Linearizes the specific transducer's raw acoustic anomalies across its operational band.
4. **Crossover Filters (`BiquadNode: Crossover`):** Band-limits the equalized signal to the driver's allocated crossover passband.
5. **Protection Filter (`BiquadNode: Protection`):** Guards low-frequency transducers against destructive infrasonic displacement below enclosure cutoff.

---

## 10. Domain Reuse vs Extension Analysis

| Component | Architecture Action | Justification |
| :--- | :--- | :--- |
| `FrequencyResponseData` | **REUSE (Frozen)** | Perfectly captures frequency, magnitude, and phase |
| `ImpulseResponseData` | **REUSE (Frozen)** | Perfectly captures time-domain impulse measurements |
| `AcousticTargetCurve` | **REUSE (Frozen)** | Reused for target error minimization |
| `EqualizerBudget` | **REUSE (Frozen)** | Reused for band, boost, cut, and Q limits |
| `DriverProfile` | **REUSE (Frozen)** | Reused for system driver definitions |
| `MicrophoneCalibrationData` | **NOT NEEDED** | Reuses `FrequencyResponseData` directly |
| `MeasurementImportResult` | **ADDITIVE (IO plane)** | Encapsulates I/O file provenance cleanly |

**Conclusion:** Zero changes required to `src/acoustiforge/domain/`. Phase 3B remains 100% frozen.

---

## 11. Golden Data Strategy

To ensure independent, non-self-referential verification, frozen text fixtures will be placed in `tests/fixtures/`:
1. `valid_2col.frd`: Fixed standard 2-column text fixture.
2. `valid_3col.csv`: Fixed comma-delimited fixture with phase.
3. `rew_export.txt`: Fixed REW ASCII export with `#` headers.
4. `mic_calibration.cal`: Fixed microphone calibration curve with known $+1.5\text{ dB}$ peak at 10 kHz.
5. `malformed_jagged.txt`: Fixture with missing column values.
6. `invalid_frequency_order.frd`: Fixture with non-monotonic frequency values.

Expected parsed arrays and corrected values are calculated analytically and hardcoded into test assertions.

---

## 12. Contract Test Matrix

### Ingestion Suite (`tests/test_measurement_ingestion.py`)
- [ ] Parse valid 2-column FRD (frequency + magnitude).
- [ ] Parse valid 3-column CSV with headers (frequency + magnitude + phase).
- [ ] Parse REW text export with comments and metadata.
- [ ] Automatic delimiter detection (comma, tab, space, semicolon).
- [ ] Reject non-monotonic / descending frequencies.
- [ ] Reject duplicate frequencies.
- [ ] Reject non-positive frequencies ($f \le 0$).
- [ ] Reject NaN and $\pm\infty$ values.
- [ ] Reject empty or 1-row files.
- [ ] Reject malformed / jagged text rows.

### Calibration Suite (`tests/test_microphone_calibration.py`)
- [ ] Exact frequency grid subtraction ($M_{\text{raw}} - M_{\text{cal}}$).
- [ ] Log-frequency interpolation matching target curve contract.
- [ ] Out-of-bounds `CLAMP` policy.
- [ ] Out-of-bounds `STRICT` policy error raising.
- [ ] Phase correction when phase is present in calibration data.
- [ ] Phase preservation when calibration data is magnitude-only.
- [ ] Input array immutability verification.

### Measurement-Driven Graph Integration Suite (`tests/test_measurement_driven_graph.py`)
- [ ] Ingest measurement $\to$ calibrate $\to$ synthesize EQ $\to$ build 2-way graph.
- [ ] Verify deterministic node IDs: `f"{driver}.eq.{idx}"`.
- [ ] Verify graph topology and schedule ordering.
- [ ] Execute multi-block PCM audio stream through the equalized graph.
- [ ] Verify frequency response linearization across audio passband.

---

## 13. Dependency Audit

- **Standard Library:** `csv`, `io`, `pathlib`, `re`, `enum`, `dataclasses`, `typing`.
- **Numerical Processing:** `numpy`.
- **Forbidden Dependencies:** Pandas, SciPy, Librosa, SoundFile, PortAudio, sounddevice, PyTorch, TensorFlow.
- **Audit Verdict:** Dependency budget strictly preserved.

---

## 14. Architecture Plane Boundaries

- **Runtime Boundary:** Ingestion, calibration, and EQ fitting occur strictly during setup (control plane). Once built and frozen, `ComputeGraph` processes PCM at full execution speed.
- **Persistence Boundary:** Pure stateless file readers. No databases, ORMs, or SQL dependencies.
- **Entity/Action Boundary:** Pure functional composition:
  $$\text{parse(file)} \longrightarrow \text{calibrate(raw, cal)} \longrightarrow \text{synthesize(meas, target)} \longrightarrow \text{build(results)}$$
  Zero Entity/Action frameworks authorized.

---

## 15. Implementation Gate Classification

| Area | Scope Classification | Status |
| :--- | :--- | :--- |
| **Phase 3B Domain Layer** | `REUSE` | **FROZEN (0 changes)** |
| **Phase 3C Mathematics** | `REUSE` + `ADDITIVE` (Calibration Math) | **FROZEN / READY** |
| **Phase 3D Graph Builders** | `REUSE` + `ADDITIVE` (EQ cascade parameter) | **FROZEN / READY** |
| **Phase 2B ComputeGraph** | `REUSE` | **FROZEN (0 changes)** |
| **Phase 0/1 DSP Nodes** | `REUSE` | **FROZEN (0 changes)** |
| **Measurement Ingestion (`io`)** | `NEW ADDITIVE` | **CONTRACT FROZEN** |
| **Microphone Calibration** | `NEW ADDITIVE` | **CONTRACT FROZEN** |

---

## 16. Implementation Gate Verdict

```
PHASE 4A CONTRACT RECONCILIATION: COMPLETE
FROZEN CONTRACT CONFLICTS: ZERO (0)
DOMAIN CONTRACT GAP: ZERO (0)
DEPENDENCY FOOTPRINT: STDLIB + NUMPY
IMPLEMENTATION GATE: IMPLEMENTATION READY
```

*Note: Phase 4A implementation is fully specified and awaiting user authorization.*
