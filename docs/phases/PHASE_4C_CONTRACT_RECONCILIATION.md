# AcoustiForge Phase 4C — Contract Reconciliation Report
## Time-Domain Measurement Ingestion, Gating, Spectral Transformation & Diagnostics

---

## 1. Repository State

- **Baseline Commit:** `a4fafa3`
- **Current Verified Suite:**
  - `pytest -q -W error`
  - Result: `333 passed in 1.21s`
  - Failures: `0`
  - Errors: `0`
  - Warnings: `0`
- **Working Tree State:** Contains verified Phase 4B implementation and discovery artifacts. All frozen layers remain 100% unmodified.

---

## 2. Existing Contract Inventory

| Contract | Document | Status | Layer |
| :--- | :--- | :--- | :--- |
| **PCM Runtime** | [PCM_CONTRACT.md](file:///E:/AcoustiForge/docs/contracts/PCM_CONTRACT.md) | `NORMATIVE` (Frozen) | Phase 0 |
| **Typed ComputeGraph** | [TYPED_COMPUTE_GRAPH_CONTRACT.md](file:///E:/AcoustiForge/docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md) | `NORMATIVE` (Frozen) | Phase 2B |
| **Measurement Ingestion** | [MEASUREMENT_INGESTION_CONTRACT.md](file:///E:/AcoustiForge/docs/contracts/MEASUREMENT_INGESTION_CONTRACT.md) | `NORMATIVE` (Frozen) | Phase 4A |
| **Microphone Calibration** | [MICROPHONE_CALIBRATION_CONTRACT.md](file:///E:/AcoustiForge/docs/contracts/MICROPHONE_CALIBRATION_CONTRACT.md) | `NORMATIVE` (Frozen) | Phase 4A |
| **Acoustic Metrics** | [ACOUSTIC_METRICS_CONTRACT.md](file:///E:/AcoustiForge/docs/contracts/ACOUSTIC_METRICS_CONTRACT.md) | `NORMATIVE` (Frozen) | Phase 4B |
| **Multi-Way Graph Builder** | [MULTIWAY_GRAPH_BUILDER_CONTRACT.md](file:///E:/AcoustiForge/docs/contracts/MULTIWAY_GRAPH_BUILDER_CONTRACT.md) | `NORMATIVE` (Frozen) | Phase 4B |

---

## 3. New Contract Inventory

The following three normative contracts are created for Phase 4C:

1. **[IMPULSE_RESPONSE_INGESTION_CONTRACT.md](file:///E:/AcoustiForge/docs/contracts/IMPULSE_RESPONSE_INGESTION_CONTRACT.md) (`CONTRACT-IR-INGESTION-01`):**
   - Governs uncompressed RIFF/WAVE (16-bit integer, 24-bit integer, 32-bit float, extensible format) and ASCII tabular impulse response file ingestion into [ImpulseResponseData](file:///E:/AcoustiForge/src/acoustiforge/domain/measurements.py#L70-L121).
2. **[REFLECTION_GATING_CONTRACT.md](file:///E:/AcoustiForge/docs/contracts/REFLECTION_GATING_CONTRACT.md) (`CONTRACT-GATING-01`):**
   - Governs window functions (`RectangularWindow`, `HannWindow`, `TukeyWindow`), peak-relative reflection gating, and discrete Fourier transform ($\text{FFT} \to \text{FrequencyResponseData}$).
3. **[MEASUREMENT_DIAGNOSTICS_CONTRACT.md](file:///E:/AcoustiForge/docs/contracts/MEASUREMENT_DIAGNOSTICS_CONTRACT.md) (`CONTRACT-DIAGNOSTICS-01`):**
   - Governs measurement quality evaluation (SNR estimation, reflection comb-filtering notch detection, low-frequency validity limits).

---

## 4. Contract Conflicts & Resolution

| Candidate Area | Conflict / Ambiguity | Resolution | Status |
| :--- | :--- | :--- | :--- |
| **Python `wave` 32-bit Float Support** | Python standard library `wave.open` rejects format `0x0003` (`WAVE_FORMAT_IEEE_FLOAT`) and `0xFFFE`. | Implementation must provide a pure-Python RIFF chunk scanner using standard library `struct` and `io` to decode PCM and Float formats without external C dependencies. | **RESOLVED** |
| **Dirac Delta Analytical Magnitude** | Discovery report informally stated "$1.0\text{ dB}$" for unit Dirac delta. | Contract explicitly establishes $|H(f)| = 1.0 \implies \text{magnitude} = 0.0\text{ dB}$ and $\text{phase} = 0.0\text{ rad}$. | **RESOLVED** |
| **DC Frequency Bin ($k=0$)** | FFT bin $k=0$ produces $f_0 = 0.0\text{ Hz}$, which violates [FrequencyResponseData](file:///E:/AcoustiForge/src/acoustiforge/domain/measurements.py#L24-L67)'s strict positivity invariant ($f_i > 0.0$). | Contract explicitly specifies that the DC bin ($k=0$) is excluded from output `FrequencyResponseData` ($k \in [1, N_{\text{fft}}/2]$). | **RESOLVED** |
| **Time Reference Preservation** | Risk of silently shifting impulse buffer to sample index 0 during gating. | Gated `ImpulseResponseData` preserves the exact original buffer length $N$, sample rate $f_s$, and `peak_index` (tapering samples outside the gate window). | **RESOLVED** |
| **Comb-Filtering Definition** | Heuristic comb detection lacked formal mathematical thresholds. | Contract formalizes: minimum notch depth $\ge 6.0\text{ dB}$, notch $Q \ge 10.0$, and periodic spacing across $\ge 3$ consecutive notches within $\pm 15\%$ tolerance. | **RESOLVED** |

---

## 5. Resolved Semantics

### 5.1 Impulse-Response Time Reference
- $t_n = \frac{n}{f_s}$, where index 0 is $t = 0.0\text{ s}$.
- Peak detection is automatic: $n_{\text{peak}} = \min \{ n \mid |h[n]| = \max_k |h[k]| \}$.
- Gating does not shift time; $h_{\text{gated}}[n]$ retains the original array length and sample rate.

### 5.2 FFT Phase Convention
- $H[k] = \text{FFT}(h_{\text{gated}}[n])$ for $k \in [1, N_{\text{fft}}/2]$.
- Frequency coordinate: $f_k = k \frac{f_s}{N_{\text{fft}}}$.
- Raw Phase (default): $\phi[k] = \text{atan2}(\text{Im}, \text{Re}) \in (-\pi, \pi]$, which naturally includes the linear time-of-flight phase slope $\phi_{\text{tof}}(f) = -2\pi f \frac{n_{\text{peak}}}{f_s}$.
- Peak-Aligned Phase (optional transform flag): Multiplies complex spectrum by $e^{+j 2\pi k n_{\text{peak}} / N_{\text{fft}}}$ prior to phase extraction.

### 5.3 Magnitude Convention
- $\text{magnitude\_linear} = |H[k]|$.
- $\text{magnitude\_db} = 20 \log_{10}(\max(|H[k]|, 10^{-12}))$. Zero magnitude is floor-clamped at $-240\text{ dB}$ ($10^{-12}$) to preserve finiteness.

---

## 6. WAV Ingestion Specification

- **Supported Encodings:**
  - 16-bit signed PCM (div $32768.0$)
  - 24-bit signed PCM (3-byte struct unpack with sign extension, div $8388608.0$)
  - 32-bit signed PCM (div $2147483648.0$)
  - 32-bit IEEE float (native float64 cast)
- **Channel Selection:** Parameter `channel_index: int = 0` selects desired channel from multi-channel streams.
- **Pure-Python Architecture:** Implemented with `struct` and `io.BytesIO` without third-party audio packages.

---

## 7. ASCII Impulse Specification

- **Supported Layouts:**
  - 2-Column: `[Time (s or ms), Amplitude]` with strictly monotonic time coordinates and derived sample rate $f_s = \text{round}(1 / \Delta t)$.
  - 1-Column: `[Amplitude]` with explicit `sample_rate: int`.
- **Delimiters:** Comma (`,`), Semicolon (`;`), Whitespace.

---

## 8. Reflection Gating Specification

- **Window Types:**
  - `RectangularWindow`: $w[n] = 1.0$.
  - `HannWindow`: $w[n] = 0.5(1 - \cos(2\pi n / (M-1)))$.
  - `TukeyWindow(alpha)`: Flat top with cosine-tapered transition regions of width $L = \lfloor \alpha (M-1) / 2 \rfloor$.
- **Gate Bounds:**
  - $n_{\text{start}} = \max(0, n_{\text{peak}} - n_{\text{left}})$.
  - $n_{\text{end}} = \min(N - 1, n_{\text{peak}} + n_{\text{right}})$.
- **Output:** Immutable `GatedImpulseResult` containing gated `ImpulseResponseData`, gate bounds, window vector, and $f_{\text{min, valid}} = \frac{1.0}{T_{\text{gate}}}$.

---

## 9. Spectral FFT Transformation Specification

- $N_{\text{fft}}$ default: Next power of 2 ($N_{\text{fft}} = 2^{\lceil \log_2 N \rceil}$), zero-padded.
- Real FFT via `numpy.fft.rfft`.
- Outputs standard immutable [FrequencyResponseData](file:///E:/AcoustiForge/src/acoustiforge/domain/measurements.py#L24-L67).

---

## 10. Measurement Diagnostics Specification

- **Validity Limit:** $f_{\text{valid, min}} = \frac{1.0}{T_{\text{gate}}}\text{ Hz}$.
- **SNR Floor:** Pre-onset noise RMS vs peak amplitude $\text{SNR} = 20 \log_{10}(A_{\text{peak}} / \text{RMS}_{\text{noise}})$. Flag `POOR_SNR_WARNING` if $< 20.0\text{ dB}$.
- **Reflection Comb Detection:** Periodic notches with depth $\ge 6.0\text{ dB}$, $Q \ge 10.0$, and periodic spacing $\Delta f \pm 15\%$ estimating path delay $\tau = 1 / \Delta f$.
- **Output:** Immutable `MeasurementDiagnosticReport`.

---

## 11. Error Taxonomy

Reused under existing `MeasurementIngestionError` ([exceptions.py](file:///E:/AcoustiForge/src/acoustiforge/io/exceptions.py)):
- `UnsupportedMeasurementFormatError`: Unknown extensions, unsupported compressed WAV tags.
- `MalformedMeasurementDataError`: Corrupt headers, truncated data chunks, jagged columns.
- `InvalidMeasurementDataError`: Non-positive sample rates, NaN/Inf samples, non-monotonic time.

---

## 12. Dependency Boundary

- Standard library: `wave`, `struct`, `io`, `pathlib`, `math`, `typing`, `dataclasses`, `enum`.
- Scientific library: `numpy` (`numpy.fft`, `numpy.ndarray`).
- Forbidden: `scipy`, `soundfile`, `librosa`, `sounddevice`, `pyaudio`, `torch`, `matplotlib`, `pandas`.

---

## 13. Phase 4B Compatibility

- Phase 4B acoustic metrics ([metrics.py](file:///E:/AcoustiForge/src/acoustiforge/acoustic_math/metrics.py)), 3-way builder ([multiway_builder.py](file:///E:/AcoustiForge/src/acoustiforge/builders/multiway_builder.py)), and execution plane DAGs remain 100% frozen.
- Phase 4C outputs canonical [FrequencyResponseData](file:///E:/AcoustiForge/src/acoustiforge/domain/measurements.py#L24-L67), which flows seamlessly into Phase 4B metrics and builders without modifications.

---

## 14. Independent Golden Specification

| Golden Case | Input Signal | Independent Derivation | Tolerance |
| :--- | :--- | :--- | :--- |
| **Dirac Delta** | $h[0]=1.0, h[n>0]=0$ | $|H|=1.0 \implies 0.0\text{ dB}$, $\phi=0.0\text{ rad}$ | $\pm 10^{-12}\text{ dB}, \pm 10^{-12}\text{ rad}$ |
| **Delayed Delta** | $h[D]=1.0, h[n\ne D]=0$ | $|H|=1.0 \implies 0.0\text{ dB}$, $\phi[k] = -2\pi f_k \frac{D}{f_s}$ | $\pm 10^{-12}\text{ dB}, \pm 10^{-12}\text{ rad}$ |
| **Single-Pole Low-Pass** | $h[n] = e^{-n / \tau}$ | $H(f) = \frac{1}{1 - e^{-1/\tau} e^{-j 2\pi f / f_s}}$ | $\pm 10^{-6}\text{ dB}, \pm 10^{-6}\text{ rad}$ |
| **Floor Reflection Comb** | Dirac + delayed echo at $5\text{ ms}$ | $4\text{ ms}$ gate removes comb notches analytically | $\pm 10^{-6}\text{ dB}$ |
| **Window Mathematical Vectors** | $M=5, \alpha=0.5$ | Closed-form cosine evaluations | $\pm 10^{-12}$ |
| **WAV Bit-Exact Decoder** | Synthetic 16/24/32-bit floats | Exact IEEE/integer conversions | Bit-exact ($\pm 10^{-12}$) |

---

## 15. Contract Acceptance Matrix

| Contract | Document | Status | Conflicts | Resolved? | Implementation Ready? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Impulse Response Ingestion** | `IMPULSE_RESPONSE_INGESTION_CONTRACT.md` | `NORMATIVE` | Python `wave` float limitation | **YES** (pure-Python chunk parser) | **YES** |
| **Reflection Gating** | `REFLECTION_GATING_CONTRACT.md` | `NORMATIVE` | DC bin $k=0$ positivity | **YES** (DC excluded from FRD) | **YES** |
| **Measurement Diagnostics** | `MEASUREMENT_DIAGNOSTICS_CONTRACT.md` | `NORMATIVE` | Comb notch heuristic ambiguity | **YES** (strict Q/depth criteria) | **YES** |

---

## 16. Implementation Plan (Proposed Slices)

```text
Phase 4C.1 — Impulse Response Ingestion (WAV 16/24/32-bit & ASCII parsers in acoustiforge.io)
Phase 4C.2 — Windowing & Reflection Gating (Tukey/Hann/Rectangular in acoustiforge.acoustic_math.gating)
Phase 4C.3 — Spectral FFT Transformation (Gated IR → FrequencyResponseData)
Phase 4C.4 — Measurement Quality Diagnostics (acoustiforge.acoustic_math.diagnostics)
Phase 4C.5 — End-to-End Vertical Slice & Golden Test Suite
```

---

## 17. Remaining Unknowns

**NONE.** All file formats, numerical tolerances, phase reference conventions, window formulas, diagnostic criteria, and error taxonomy are fully specified.

---

## 18. STOP / GO Decision

```text
GO — Phase 4C contracts are sufficiently precise for implementation.
```
