# AcoustiForge — Phase 4C Architectural Discovery Report
## Time-Domain Measurement Ingestion, Gating, Impulse Analysis & Diagnostics

---

## 1. Executive Summary

With Phase 4B (*Acoustic Metrics, Three-Way Graph Synthesis, and End-to-End PCM Execution*) verified and frozen at commit `a4fafa3` + Phase 4B implementation (333 passed, 0 failures, 0 errors, 0 warnings under `pytest -q -W error`), AcoustiForge has achieved a complete control-plane pipeline capable of analyzing calibrated frequency-response data and synthesizing 2-way and 3-way loudspeaker execution DAGs.

Phase 4C discovery addresses the time-domain ingestion and acoustic diagnostic boundary:
> *"What is the next computational capability in the AcoustiForge architecture that enables ingestion of raw time-domain impulse measurements, reflection gating, and quality diagnostics without introducing external audio/DSP dependencies or compromising runtime neutrality?"*

### Key Discovery Conclusions:
1. **Primary Capability — Time-Domain Impulse Response Ingestion & Reflection Gating (Candidate A):**
   - Ingest raw time-domain acoustic impulse responses from uncompressed WAV files (16-bit, 24-bit, 32-bit float) and ASCII text formats into the existing immutable `ImpulseResponseData` domain type.
   - Provide deterministic time-domain windowing/reflection gating (Tukey, Hann, Rectangular windows with sample-accurate left/right gate bounds) to isolate direct-sound arrival from room reflections (pseudo-anechoic processing).
   - Transform gated impulse data via discrete Fourier transform (FFT) into canonical `FrequencyResponseData`, fully bridging raw time-domain measurements into Phase 4A calibration, Phase 4B metrics, and 3-way graph synthesis.
2. **Secondary Capability — Measurement Quality Diagnostics (Candidate E):**
   - Provide objective diagnostic checks over measurement data: signal-to-noise ratio (SNR) estimation, reflection comb-filtering notch detection, frequency resolution validity, and phase continuity.
3. **Zero Third-Party Dependencies:**
   - Achieved strictly via Python standard library (`wave`, `struct`, `io`, `pathlib`) and `numpy.fft`.
   - Zero SciPy, zero SoundFile, zero Librosa, zero PyAudio.
4. **Strict Architectural Isolation:**
   - All Phase 4C operations execute offline in the control/intelligence plane (`acoustiforge.io` and `acoustiforge.acoustic_math`).
   - The ACE execution plane (`ComputeGraph`, DSP nodes, PCM contracts) remains 100% untouched and frozen.

---

## 2. Frozen Baseline Verification

The existing baseline is permanently frozen:
- **Phase 0:** `PCMBlock`, `AudioMetadata`, `ChannelLayout`, planar float32 buffers.
- **Phase 1:** `BiquadNode`, `GainNode`, `DelayNode`, `PassThroughNode`, `SequentialPipeline`.
- **Phase 2B:** `ComputeGraph`, typed single-producer ports, static topological scheduling, fan-out, latency tracking.
- **Phase 3B:** Domain value objects (`DriverProfile`, `EnclosureProfile`, `TransducerLimits`, `CrossoverSpecification`, `AcousticTargetCurve`, `EqualizerBudget`, `FrequencyResponseData`, `ImpulseResponseData`).
- **Phase 3C:** Acoustic mathematics (`synthesize_crossover_biquads`, `calculate_driver_alignment`, `calculate_sensitivity_gain`, `evaluate_target_curve`, `derive_protection_filter_for_driver`, `synthesize_parametric_eq`).
- **Phase 3D:** Graph builders (`CrossoverGraphBuilder`, `SystemTopologyBuilder`).
- **Phase 4A:** Measurement file parser (`parse_measurement_file`, `parse_measurement_text`), microphone calibration (`apply_microphone_calibration`), measurement-driven EQ graph integration.
- **Phase 4B:** Acoustic metrics (`AcousticMetricsResult`, `calculate_response_metrics`, `smooth_frequency_response`), 3-way DAG builder (`ThreeWayGraphBuilder`), and end-to-end multi-block PCM execution.
- **Current Test Count:** 333 passed in 1.17s, 0 failures, 0 errors, 0 warnings.

---

## 3. Current Architecture & Phase 4C Integration Point

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ CONTROL / ACOUSTIC INTELLIGENCE PLANE                                           │
│                                                                                 │
│  [WAV / Text Impulse Response] (.wav, .txt)                                      │
│          │                                                                      │
│          ▼ (NEW Phase 4C Ingestion: acoustiforge.io.impulse_parser)             │
│  [ImpulseResponseData (Raw)] (Phase 3B Domain Model - Reused)                   │
│          │                                                                      │
│          ▼ (NEW Phase 4C Gating & FFT: acoustiforge.acoustic_math.gating)       │
│  [ImpulseResponseData (Gated)]                                                  │
│          │                                                                      │
│          ▼ (Discrete Fourier Transform & Normalization)                         │
│  [FrequencyResponseData (Uncalibrated)] ──► [Quality Diagnostics (Phase 4C)]   │
│          │                                                                      │
│          ▼ (Phase 4A Calibration: apply_microphone_calibration)                 │
│  [FrequencyResponseData (Calibrated)]                                           │
│          │                                                                      │
│          ▼ (Phase 4B Acoustic Metrics: calculate_response_metrics)              │
│  [AcousticMetricsResult]                                                        │
│          │                                                                      │
│          ▼ (Phase 3C Math / Phase 4B Synthesis)                                 │
│  [ThreeWayGraphBuilder / CrossoverGraphBuilder]                                 │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │ produces frozen DAG
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ COMPUTE / REALTIME DATAFLOW PLANE (Frozen Phase 2B / Phase 0)                   │
│  ComputeGraph.process(PCMBlock) ──► Multi-Block Audio Execution                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Phase 4C Objective & Scope

### 4.1 Primary Objectives
1. **Time-Domain Ingestion:** Ingest raw impulse responses from uncompressed PCM WAV files (16-bit integer, 24-bit integer, 32-bit float) and ASCII text exports into `ImpulseResponseData`.
2. **Pseudo-Anechoic Reflection Gating:** Implement configurable time-domain windowing (Tukey, Hann, Rectangular) with sample-accurate gate start and duration relative to the direct-sound impulse peak.
3. **Spectral Transformation:** Transform gated time-domain data to `FrequencyResponseData` containing both magnitude ($20 \log_{10} |H(f)|$) and unmanipulated phase ($\angle H(f)$ in radians), complete with frequency vector scaling ($f_k = k \frac{f_s}{N_{\text{fft}}}$).
4. **Measurement Diagnostics:** Evaluate raw/gated measurements for reflection contamination (comb filtering), SNR limits, and low-frequency validity cutoffs determined by gate length ($f_{\text{valid, min}} \approx \frac{1}{T_{\text{gate}}}$).

### 4.2 Explicitly Deferred Scope
- **Hardware I/O:** No live soundcard recording, no real-time stream capture (WASAPI, ASIO, ALSA, PortAudio).
- **Multi-Way Optimizer:** Automated crossover/gain/delay parameter optimization is deferred to Phase 4D.
- **Room Acoustic Simulation:** 3D modal modeling, ray-tracing, and finite element room modeling remain deferred.
- **AI/ML Models:** Neural network regression or predictive modeling remain deferred.
- **GUI / Interactive Plotting:** Visualization packages remain deferred.

---

## 5. Contract Discovery & Requirements

### 5.1 Required Normative Contracts for Phase 4C
1. **`IMPULSE_RESPONSE_INGESTION_CONTRACT.md` (`CONTRACT-IR-INGESTION-01`):**
   - WAV decoding formats: 16-bit integer PCM, 24-bit integer PCM (using 3-byte struct unpacking), 32-bit float. Single-channel mono and multi-channel extraction.
   - Text IR format: Time-amplitude or sample-amplitude tabular ASCII data.
   - Invariants: Non-empty samples, finite sample rate ($f_s > 0$), finite real amplitudes, automatic peak detection index.
   - Error taxonomy: `UnsupportedMeasurementFormatError`, `MalformedMeasurementDataError`, `InvalidMeasurementDataError`.
2. **`REFLECTION_GATING_CONTRACT.md` (`CONTRACT-GATING-01`):**
   - Window types: `TukeyWindow`, `HannWindow`, `RectangularWindow`.
   - Gate parameters: Left gate time / samples (pre-peak taper), Right gate time / samples (post-peak reflection truncation).
   - Frequency resolution boundary: $f_{\text{min, valid}} = \frac{1}{T_{\text{gate, sec}}}$.
   - Output: `GatedImpulseResult` and direct transformation to `FrequencyResponseData`.
3. **`MEASUREMENT_DIAGNOSTICS_CONTRACT.md` (`CONTRACT-DIAGNOSTICS-01`):**
   - Diagnostic checks: Reflection comb-filtering detection ($Q > 15$ periodic notches), SNR floor evaluation, low-frequency truncation warning.
   - Output: `MeasurementDiagnosticReport` (immutable dataclass).

---

## 6. Gap Analysis Matrix

| Requirement | Existing Capability | Gap | New Abstraction Required? | Modification Required? |
| :--- | :--- | :--- | :--- | :--- |
| **WAV File Parsing** | None | Need pure Python `wave` + `struct` 16/24/32-bit decoder | Yes (`acoustiforge.io.impulse_parser`) | No |
| **ASCII IR Parsing** | `parse_measurement_text` (FRD only) | Needs time-domain 1D/2D parser into `ImpulseResponseData` | Yes (`parse_impulse_file`) | No |
| **Impulse Data Container** | `ImpulseResponseData` (Phase 3B) | **NO GAP FOUND** (Fully defined in Phase 3B) | No (Pure reuse) | No |
| **Window Functions** | None | Need closed-form Tukey, Hann, Rectangular window generators | Yes (`acoustiforge.acoustic_math.gating`) | No |
| **Reflection Gating** | None | Need sample-accurate left/right gating around peak index | Yes (`apply_reflection_gate`) | No |
| **FFT Spectral Transform** | `np.fft` available | Need gated IR $\to$ `FrequencyResponseData` conversion | Yes (`transform_impulse_to_frequency_response`) | No |
| **Microphone Calibration** | `apply_microphone_calibration` (Phase 4A) | **NO GAP FOUND** (Directly consumes transformed FRD) | No (Pure reuse) | No |
| **Acoustic Metrics** | `calculate_response_metrics` (Phase 4B) | **NO GAP FOUND** (Directly consumes transformed FRD) | No (Pure reuse) | No |
| **3-Way Graph Builder** | `ThreeWayGraphBuilder` (Phase 4B) | **NO GAP FOUND** (Directly consumes synthesis results) | No (Pure reuse) | No |
| **Quality Diagnostics** | None | Need comb-notch & low-frequency resolution checks | Yes (`evaluate_measurement_quality`) | No |

---

## 7. Phase 4B Boundary & Compatibility

- **Phase 4B Frozen Status:** Maintained 100% frozen.
- **Interface Interaction:** Phase 4C transforms time-domain impulse data into standard `FrequencyResponseData`. This object is then ingested directly by existing, frozen Phase 4A calibration and Phase 4B metrics/builders.
- **Zero Modifications:** No existing Phase 4B, 4A, 3D, 3C, 3B, 2B, or 1 code needs modification.

---

## 8. Dependency & Layering Analysis

- **Permitted Dependencies:** Python standard library (`wave`, `struct`, `io`, `pathlib`, `math`) and `numpy` (`numpy.fft`, `numpy.ndarray`).
- **Forbidden Dependencies:** `scipy`, `soundfile`, `librosa`, `sounddevice`, `pyaudio`, `torch`, `matplotlib`, `pandas`.
- **Layering:**
  ```
  src/acoustiforge/io/ (Impulse parsers)
          ↓
  src/acoustiforge/domain/ (ImpulseResponseData, FrequencyResponseData)
          ↓
  src/acoustiforge/acoustic_math/ (Gating, Windowing, FFT transformation, Diagnostics)
          ↓
  src/acoustiforge/builders/ (Unchanged)
          ↓
  src/acoustiforge/graph/ (Unchanged)
  ```

---

## 9. Verification Strategy

1. **Unit Tests:**
   - WAV header decoding across 16-bit PCM, 24-bit PCM, and 32-bit IEEE float.
   - Window mathematical formulations (Tukey $\alpha=0.5$, Hann $\alpha=1.0$, Rectangular $\alpha=0.0$).
   - Sample-accurate peak alignment and gate boundary indexing.
2. **Independent Golden Vectors:**
   - **Analytical Dirac Delta:** $h[0] = 1, h[n]=0 \implies |H(f)| = 1.0\text{ dB}$ (flat), $\angle H(f) = 0.0\text{ rad}$.
   - **Analytical Delayed Delta:** $h[D] = 1 \implies |H(f)| = 1.0$, linear phase slope $\phi(f) = -2\pi f \frac{D}{f_s}$.
   - **Analytical Exponential Decay (Single-Pole Low-Pass):** $h[n] = e^{-n / \tau} \implies H(f) = \frac{1}{1 - e^{-1/\tau} e^{-j 2\pi f / f_s}}$.
   - **Gating Isolation:** Synthetic impulse with injected simulated floor reflection at $t = 5\text{ ms}$; verify that a $4\text{ ms}$ gate removes the reflection comb-filtering ripple analytically.
3. **End-to-End Vertical Slice:**
   - Ingest raw WAV impulse response $\to$ Reflection gate $\to$ FFT spectral transformation $\to$ Microphone calibration $\to$ Phase 4B Acoustic Metrics $\to$ Three-Way Graph Synthesis $\to$ Multi-Block PCM processing.
4. **Regression Protection:**
   - Verify all 333 baseline tests pass with zero warnings (`pytest -q -W error`).

---

## 10. Proposed Implementation Slices for Phase 4C

```
Phase 4C.1 — Impulse Response File Ingestion (WAV 16/24/32-bit & ASCII parsers)
Phase 4C.2 — Windowing & Reflection Gating Mathematics (Tukey/Hann/Rectangular gates)
Phase 4C.3 — Spectral Transformation (Gated FFT → FrequencyResponseData)
Phase 4C.4 — Measurement Quality Diagnostics
Phase 4C.5 — End-to-End Time-Domain to Graph Vertical Slice & Golden Tests
```

---

## 11. Acceptance Gate Matrix for Phase 4C

| Gate | Requirement |
| :--- | :--- |
| **4C-A** | Baseline reproduced ($333\text{ passed}, 0\text{ errors}, 0\text{ warnings}$) |
| **4C-B** | WAV (16/24/32-bit) and ASCII impulse response parsers implemented |
| **4C-C** | Window functions & reflection gating algorithms implemented |
| **4C-D** | Spectral FFT transformation $\to$ `FrequencyResponseData` implemented |
| **4C-E** | Measurement quality diagnostics implemented |
| **4C-F** | Independent analytical impulse golden vectors pass |
| **4C-G** | End-to-end WAV $\to$ Gating $\to$ FRD $\to$ Metrics $\to$ 3-Way Graph $\to$ PCM verified |
| **4C-H** | Phase 4B, 4A, 3D backward compatibility verified |
| **4C-I** | Dependency audit passes (stdlib + NumPy only) |
| **4C-J** | Scope audit passes (zero hardware/real-time/ML creep) |
| **4C-K** | `pytest -q -W error` passes with zero warnings |
| **4C-L** | Implementation report `PHASE_4C_IMPLEMENTATION_AND_VERIFICATION.md` completed |

---

## 12. STOP / GO Decision

```
DECISION: GO — Phase 4C is sufficiently specified for contract reconciliation and implementation planning.
```
