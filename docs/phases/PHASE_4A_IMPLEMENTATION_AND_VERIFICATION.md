# AcoustiForge Phase 4A Implementation & Verification Report
## Measurement Pipeline & Measurement-Driven EQ Integration

---

## 1. Executive Summary

Phase 4A connects raw measurement file ingestion and microphone calibration directly to the existing frozen Phase 3C acoustic filter synthesis, Phase 3D graph builders, and Phase 2B ComputeGraph runtime.

The implementation strictly respects all frozen architectural layers:
- **Phase 3B Domain Layer:** 100% frozen (`src/acoustiforge/domain/` untouched). `FrequencyResponseData` is reused directly for both raw driver measurements and microphone calibration curves.
- **Phase 3C Acoustic Mathematics:** Untouched except for the additive addition of stateless, deterministic microphone calibration math (`src/acoustiforge/acoustic_math/calibration.py`).
- **Phase 3D Graph Builders:** Non-breaking additive extension to `CrossoverGraphBuilder.build_2way_graph` supporting optional `equalizers: Optional[Mapping[str, EQSynthesisResult]] = None`. When `equalizers=None`, the topology, node IDs, schedule, latency, and PCM output are 100% bit-exact identical to the Phase 3D baseline.
- **Compute Plane:** 100% frozen (`ComputeGraph`, `nodes/` untouched).

---

## 2. Implementation Architecture & Data Flow

$$\begin{aligned}
\text{Raw File } (.frd, .csv, .txt, .cal) &\xrightarrow{\text{parse\_measurement\_file()}} \text{MeasurementImportResult} \\
&\xrightarrow{} \text{FrequencyResponseData (Raw)} \\
&\xrightarrow[\text{apply\_microphone\_calibration()}]{\text{Microphone Calibration FRD}} \text{FrequencyResponseData (Calibrated)} \\
&\xrightarrow{\text{evaluate\_target\_curve()}} \text{Target SPL Grid} \\
&\xrightarrow{\text{synthesize\_parametric\_eq()}} \text{EQSynthesisResult (Peaking Biquads)} \\
&\xrightarrow{\text{CrossoverGraphBuilder(equalizers=...)}} \text{ComputeGraph (Frozen DAG)} \\
&\xrightarrow{\text{ComputeGraph.process()}} \text{Multi-Block PCM Audio Output}
\end{aligned}$$

---

## 3. Detailed Component Implementation

### 3.1 Measurement Ingestion Layer (`src/acoustiforge/io/`)
- **`exceptions.py`**: Strict hierarchy rooted at `AcoustiForgeError`:
  - `MeasurementIngestionError`
  - `UnsupportedMeasurementFormatError`
  - `MalformedMeasurementDataError`
  - `InvalidMeasurementDataError`
- **`result.py`**: Immutable `MeasurementImportResult` separating pure mathematical data (`FrequencyResponseData`) from file provenance metadata (`source_format`, `source_path`, `header_comments`).
- **`parser.py`**:
  - Auto-detection of separator (comma, whitespace, or semicolon).
  - **Semicolon Precedence Rule:** A line that parses as a valid numerical data row under the semicolon separator is treated as data, preventing valid semicolon-separated rows from being erroneously discarded as comments. Textual semicolon lines are preserved as comments.
  - Frequency verification: strictly positive ($> 0\text{ Hz}$), strictly monotonically ascending ($\Delta f > 0$, no duplicates or reversals), finite (rejects NaN and Inf).
  - Magnitude & phase verification: finite, validates consistent column counts across all rows.
  - Phase degree-to-radian conversion during ingestion.

### 3.2 Microphone Calibration Mathematics (`src/acoustiforge/acoustic_math/calibration.py`)
- **Magnitude Subtraction:**
  $$M_{\text{corrected}}(f) = M_{\text{raw}}(f) - M_{\text{cal}}(f) \quad [\text{dB}]$$
- **Phase Correction Semantics:**
  - Magnitude-only calibration is the normal Phase 4A case (`apply_phase_correction=False`).
  - Phase subtraction $\phi_{\text{corrected}} = \phi_{\text{raw}} - \phi_{\text{cal}}$ is applied ONLY when explicitly enabled (`apply_phase_correction=True`) AND compatible phase exists in both raw and calibration data.
  - No phase inference, no phase unwrapping, no minimum phase derivation, no time-of-flight compensation.
- **Log-Frequency Interpolation:** Piecewise linear interpolation in $\log_{10}(\text{frequency\_hz})$ domain.
- **Boundary Policies:**
  - `CLAMP` (default): clamps edge calibration values.
  - `ZERO_PAD`: assumes $0.0\text{ dB}$ offset outside calibration span.
  - `STRICT`: raises `CalibrationOutOfRangeError` if raw frequencies exceed calibration bounds.

### 3.3 Additive EQ Graph Builder Integration (`src/acoustiforge/builders/crossover_builder.py`)
- Added optional `equalizers: Optional[Mapping[str, EQSynthesisResult]] = None` to `build_2way_graph`.
- Driver branch sequential topology:
  $$\text{input} \longrightarrow [\text{delay}] \longrightarrow [\text{gain}] \longrightarrow [\text{eq.0} \dots \text{eq.K}] \longrightarrow [\text{crossover.0} \dots \text{crossover.N}] \longrightarrow [\text{protection.0} \dots] \longrightarrow \text{output}$$
- Node IDs: `f"{driver_name}.eq.{idx}"`.
- Backward Compatibility: When `equalizers=None` or omitted, zero EQ nodes are inserted, and the topology, node IDs, schedule, latency, and PCM output are bit-exact identical to the Phase 3D baseline.

---

## 4. Verification Suite & Test Results

The test suite was executed under strict pytest warning enforcement: `pytest -q -W error`.

```
============================== 301 passed in 1.21s ==============================
```

### 4.1 Parser Verification (`tests/test_measurement_ingestion.py`)
- [x] FRD 2-column whitespace format (`valid_2col.frd`)
- [x] CSV 3-column with comma delimiter and phase (`valid_3col.csv`)
- [x] CSV semicolon delimiter with normative comment/data precedence rule (`valid_semicolon.csv`)
- [x] REW plain text export with `*` comments (`rew_export.txt`)
- [x] Header comment preservation in `MeasurementImportResult`
- [x] Unsupported file extension rejection (`.bin`)
- [x] Empty file and single-point rejection (`InvalidMeasurementDataError`)
- [x] Non-monotonic frequency rejection (`invalid_frequency_order.frd`)
- [x] Duplicate frequency rejection
- [x] Zero and negative frequency rejection
- [x] NaN and Inf non-finite value rejection
- [x] Jagged and malformed row length rejection (`malformed_jagged.txt`)

### 4.2 Calibration Mathematics Verification (`tests/test_microphone_calibration.py`)
- [x] Exact frequency grid magnitude subtraction ($M_{\text{raw}} - M_{\text{cal}}$)
- [x] Compatible transfer-function phase subtraction ($\phi_{\text{raw}} - \phi_{\text{cal}}$)
- [x] Magnitude-only calibration preserving raw phase (`apply_phase_correction=False`)
- [x] Log-frequency interpolation at geometric midpoint ($5.0\text{ dB}$ offset at $\sqrt{100 \times 1000}\text{ Hz}$)
- [x] `CLAMP` boundary policy holding edge offsets
- [x] `ZERO_PAD` boundary policy applying $0.0\text{ dB}$ outside calibration span
- [x] `STRICT` boundary policy raising `CalibrationOutOfRangeError`
- [x] Input immutability (raw and calibration arrays unmodified)
- [x] Deterministic repeated execution producing identical outputs

### 4.3 Graph & Backward Compatibility Verification (`tests/test_measurement_driven_graph.py`)
- [x] `equalizers=None` backward compatibility: identical node set, identical schedule, identical latency, bit-exact PCM output vs default.
- [x] Deterministic node IDs `f"{driver}.eq.{idx}"` and correct branch placement order.
- [x] Sample rate mismatch rejection between builder and EQ synthesis result.
- [x] Full vertical slice test: Raw File $\to$ Ingestion $\to$ Calibration $\to$ Target Curve $\to$ EQ Synthesis $\to$ Graph Builder $\to$ ComputeGraph $\to$ Multi-block PCM execution.

### 4.4 Golden Data Independence
All test fixtures and assertions define expected numerical values independently of the production implementation code. No self-referential tests are present.

### 4.5 Dependency Isolation
- Allowed: Python standard library, NumPy.
- Forbidden (audited): SciPy, Pandas, Librosa, soundfile, PortAudio, sounddevice, AI/ML libraries.
- Verified by `tests/test_dependency_isolation.py`.

---

## 5. Scope & Physical Acoustic Boundary

This implementation fulfills the computational ACE pipeline from measurement files to PCM processing. In accordance with architectural boundaries:
- No claim of physical acoustic validation is made (e.g. microphone placement geometry, room acoustics, or transducer mechanical behavior).
- Time-domain impulse response parsing, hardware audio I/O, GUI, and database persistence remain explicitly deferred.
