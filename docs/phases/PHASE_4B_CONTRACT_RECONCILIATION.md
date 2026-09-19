# AcoustiForge — Phase 4B Contract Reconciliation Report
## Acoustic Metrics & Multi-Way System Synthesis

---

## 1. Baseline

- **Frozen Repository Baseline:** Commit `a4fafa3` (*chore(acoustiforge): finalize Phase 4A measurement pipeline*).
- **Regression Suite:** `pytest -q -W error` passing with **301 passed, 0 failures, 0 errors, 0 warnings**.
- **Frozen Planes:** Phase 0 PCM contracts, Phase 1 DSP nodes, Phase 2B Typed ComputeGraph, Phase 3B Acoustic Domain, Phase 3C Acoustic Math, Phase 3D Graph Builders, and Phase 4A Measurement Pipeline.

---

## 2. Discovery Inputs

Phase 4B discovery evaluated seven candidates (A through G) and selected the optimal additive vertical slice:
1. **Candidate B — Acoustic Response Analysis & Metrics:** Pure closed-form functions for passband sensitivity, $F_3/F_6/F_{10}$ bandwidth limits, RMS target tracking error, passband ripple, spectral slope, and fractional-octave log-Gaussian smoothing over `FrequencyResponseData`.
2. **Candidate C — Multi-Way Loudspeaker System Synthesis:** Generalizing graph building to 3-Way (Woofer, Midrange, Tweeter) systems with bandpass midrange biquad cascades, independent driver delay alignment, sensitivity matching, protection filters, and additive EQ cascades.

---

## 3. Existing Contract Reuse

| Contract Identifier | Role in Phase 4B | Status |
| :--- | :--- | :--- |
| `PCM_CONTRACT.md` | Audio buffer and metadata format (`PCMBlock`, `AudioMetadata`) | **100% Frozen / Reused As-Is** |
| `TYPED_COMPUTE_GRAPH_CONTRACT.md` | Graph execution, static topological scheduling, typed ports | **100% Frozen / Reused As-Is** |
| `MEASUREMENT_INGESTION_CONTRACT.md` | Measurement file ingestion (`FrequencyResponseData`) | **100% Frozen / Reused As-Is** |
| `MICROPHONE_CALIBRATION_CONTRACT.md` | Microphone calibration preprocessing | **100% Frozen / Reused As-Is** |
| `CONTRACT-ACOUSTIC-METRICS-01` | Normative specification for quantitative acoustic metrics | **NEW (Phase 4B)** |
| `CONTRACT-MULTIWAY-BUILDER-01` | Normative specification for 3-way loudspeaker graph assembly | **NEW (Phase 4B)** |

---

## 4. Acoustic Metrics Reconciliation

### 4.1 Passband Sensitivity ($S_{\text{passband}}$)
- **Resolved Formulation:** Energy-weighted integral in $\log_{10}(f)$ space across default $[200.0, 2000.0]\text{ Hz}$ or declared passband:
  $$S_{\text{passband}} = 10 \log_{10}\left( \frac{\int_{\log_{10} f_{\text{min}}}^{\log_{10} f_{\text{max}}} 10^{M(f)/10} \, d(\log_{10} f)}{\log_{10}(f_{\text{max}}) - \log_{10}(f_{\text{min}})} \right) \quad [\text{dB SPL}]$$
- Evaluated via trapezoidal integration on the discrete measurement grid with exact log-linear boundary interpolation.

### 4.2 Cutoff Frequencies ($F_3, F_6, F_{10}$)
- **Reference SPL:** $S_{\text{passband}}$.
- **Cutoff Threshold:** $M_{\Delta} = S_{\text{passband}} - \Delta\text{ dB}$ for $\Delta \in \{3.0, 6.0, 10.0\}$.
- **Multiple Crossing Policy (Resolved):** Outermost policy is normative:
  - $F_{\text{low}}$ is the highest frequency below $f_{\text{min}}$ where the response falls permanently into the low-frequency attenuation band.
  - $F_{\text{high}}$ is the lowest frequency above $f_{\text{max}}$ where the response falls permanently into the high-frequency attenuation band.
- **Interpolation (Resolved):** Exact piecewise log-linear interpolation between straddling frequency bins.
- **No-Crossing Behavior (Resolved):** Returns `None` if the threshold is never reached.

### 4.3 Target Tracking Error
- Evaluated across shared overlap span $[f_{\text{start}}, f_{\text{end}}] = [\max(f_{\text{raw,min}}, f_{\text{target,min}}), \min(f_{\text{raw,max}}, f_{\text{target,max}})]$.
- $E_{\text{rms}} = \sqrt{ \frac{1}{K} \sum_{i=1}^K (M(f_i) - T(f_i))^2 }$. Target $T(f)$ evaluated via `evaluate_target_curve(curve, f_i)`.
- Peak positive error $E_{\text{peak+}} = \max_i(M(f_i) - T(f_i))$ and peak negative error $E_{\text{peak-}} = \min_i(M(f_i) - T(f_i))$.

### 4.4 Spectral Tilt & Ripple
- Spectral tilt: Linear regression slope of $M(f)$ vs $\log_2(f)$ in $\text{dB/octave}$.
- Passband ripple: Peak-to-peak difference $\max M(f) - \min M(f)$ in the passband.

### 4.5 Fractional-Octave Smoothing
- Log-Gaussian weighting kernel in $\log_2(f)$ domain with standard deviation $\sigma = \frac{1}{N \cdot 2\sqrt{2\ln 2}}$ octaves for $1/N$-octave smoothing.
- Normalized by sum of weights to eliminate edge drop-off artifacts. Truncated at $3\sigma$.

---

## 5. Multi-Way Builder Reconciliation

### 5.1 Backward Compatibility Strategy
- Existing `CrossoverGraphBuilder.build_2way_graph` remains 100% untouched.
- 3-Way graph synthesis is encapsulated in an additive `ThreeWayGraphBuilder` (and `SystemTopologyBuilder.build_stereo_3way_graph`).

### 5.2 Canonical Midrange Processing Order
- Standardized as:
  $$\text{input} \longrightarrow [\text{delay}] \longrightarrow [\text{gain}] \longrightarrow [\text{eq}\dots] \longrightarrow [\text{crossover.hp}\dots] \longrightarrow [\text{crossover.lp}\dots] \longrightarrow [\text{protection}\dots] \longrightarrow \text{output}$$
- **Ordering Convention:** High-pass crossover precedes low-pass crossover to reject low-frequency energy before high-frequency band-limiting.

### 5.3 Deterministic Node Naming
- Woofer: `f"{w}.delay"`, `f"{w}.gain"`, `f"{w}.eq.{i}"`, `f"{w}.crossover.{i}"`, `f"{w}.protection.{i}"`
- Midrange: `f"{m}.delay"`, `f"{m}.gain"`, `f"{m}.eq.{i}"`, `f"{m}.crossover.hp.{i}"`, `f"{m}.crossover.lp.{i}"`, `f"{m}.protection.{i}"`
- Tweeter: `f"{t}.delay"`, `f"{t}.gain"`, `f"{t}.eq.{i}"`, `f"{t}.crossover.{i}"`, `f"{t}.protection.{i}"`

---

## 6. Numerical Semantics & Tolerances

- **Float64 Internal Math:** All mathematical calculations inside `acoustic_math/` execute in 64-bit IEEE floating-point arithmetic.
- **Analytical Identities:** $\pm 10^{-12}\text{ dB}$ tolerance.
- **Interpolated Cutoffs:** $\pm 10^{-4}\text{ Hz}$ tolerance.
- **Spectral Tilt:** $\pm 10^{-6}\text{ dB/octave}$ tolerance.
- **Realtime Float32 PCM:** Audio processing across `ComputeGraph` converts to/from float32 planar buffers, preserving full dynamic range with zero buffer corruptions.

---

## 7. Golden Data Strategy

Golden test data will be generated completely independently of production implementation code:
1. **Idealized Analytical Filters:** Closed-form mathematical Butterworth curves with hand-calculated exact $F_3$, $F_6$, $F_{10}$, and $-6N\text{ dB/oct}$ asymptotic slopes.
2. **Ideal Tilted Lines & Ripple Sinusoids:** Known linear slopes ($+3.0\text{ dB/oct}$) and sinusoidal ripple vectors.
3. **Multi-Way Topologies:** Hand-derived topological execution schedules and analytical impulse response outputs.
4. **No Self-Referential Tests:** Never generate expected values by calling the code under test.

---

## 8. Dependency Boundary

- **Permitted:** Python standard library + NumPy.
- **Strictly Forbidden:** SciPy, Pandas, Librosa, soundfile, PortAudio, sounddevice, PyAudio, Torch, AI/ML libraries, GUI frameworks, database/ORM frameworks.

---

## 9. Runtime Boundary

- **Offline Control Plane:** Acoustic metric analysis, fractional-octave smoothing, and 3-way graph construction execute strictly offline.
- **Realtime Compute Plane:** `ComputeGraph.process()` performs only static, non-allocating DSP node execution. Zero acoustic analysis logic is executed inside the realtime audio loop.

---

## 10. Physical Acoustic Boundary

- Metric calculations evaluate the discrete numerical measurement data supplied.
- They do **NOT** prove real-world room acoustic behavior, microphone placement geometry, transducer non-linear distortion, thermal compression, or 3D spatial directivity.
- 3-way graph synthesis proves deterministic computational filter construction, not physical acoustic perfection.

---

## 11. Domain Model Decision

- **Verdict:** No new entity framework authorized.
- New mathematical result value object `AcousticMetricsResult` is located in `acoustiforge.acoustic_math` (or `acoustiforge.domain.metrics`).
- Domain layer remains 100% frozen; builders consume existing domain specifications.

---

## 12. Backward Compatibility Gate

- 2-way graph construction remains bit-exact and topologically identical to Phase 3D/4A.
- Existing 301 test baseline MUST continue to pass with 0 warnings.

---

## 13. Future Test Matrix

During the subsequent implementation phase, the test suite will cover:
1. **Acoustic Metrics Unit Tests:**
   - Flat response (sensitivity, 0 ripple, 0 tilt, no cutoffs).
   - Idealized low-pass Butterworth (exact $F_3, F_6, F_{10}$, asymptotic slope).
   - Idealized high-pass Butterworth.
   - Bandpass response with both lower and upper cutoffs.
   - Outermost multiple crossing resolution vs narrow notch dips.
   - No-crossing handling (`None` returns).
   - RMS, peak positive, and peak negative target error against target curve.
   - Spectral tilt calculation on tilted synthetic response.
   - Passband ripple calculation.
   - Fractional-octave smoothing modes (`1/3`, `1/6`, `1/12`, `1/24`).
   - Immutability of input measurements.
2. **Multi-Way Graph Builder Tests:**
   - 3-way graph topological structure and node IDs.
   - Midrange bandpass filter sequence (`hp` $\to$ `lp`).
   - Crossover frequency ordering validation ($f_{\text{low}} < f_{\text{high}}$).
   - Stage omission fall-through (omitting EQ, protection, gain, delay).
   - Stereo 3-way graph composition.
   - Multi-block PCM execution across 3 output channels (Woofer, Midrange, Tweeter).
3. **Regression Tests:** Full 301 baseline tests pass.

---

## 14. Checklist of Required Resolutions

| Item | Resolution | Status |
| :--- | :--- | :--- |
| `AcousticMetricsResult` ownership | Pure immutable dataclass in `acoustic_math.metrics` | **RESOLVED** |
| Passband sensitivity definition | Energy-weighted integral over $\log_{10}(f)$ in $[f_{\text{min}}, f_{\text{max}}]$ | **RESOLVED** |
| $F_3/F_6/F_{10}$ reference definition | Referenced to $S_{\text{passband}}$ | **RESOLVED** |
| Multiple crossing policy | Outermost crossing into attenuation band | **RESOLVED** |
| No-crossing behavior | Returns `None` | **RESOLVED** |
| Cutoff interpolation | Piecewise log-linear interpolation between straddling bins | **RESOLVED** |
| Target error definition | RMS error, peak positive, peak negative over shared overlap | **RESOLVED** |
| Target interpolation | `evaluate_target_curve` in $\log_{10}(f)$ space | **RESOLVED** |
| Target overlap behavior | Evaluated over common frequency intersection | **RESOLVED** |
| Spectral tilt definition | Unweighted OLS regression of $M(f)$ vs $\log_2(f)$ [dB/oct] | **RESOLVED** |
| Ripple definition | $\max M(f) - \min M(f)$ within declared passband | **RESOLVED** |
| Smoothing formulation | Log-Gaussian kernel in $\log_2(f)$ domain with $\sigma = \frac{1}{2.35482 N}$ | **RESOLVED** |
| Smoothing edge behavior | Normalization by weight sum $\sum w_{ij}$; truncated at $3\sigma$ | **RESOLVED** |
| Smoothing normalization | Exact normalized sum eliminating edge attenuation artifacts | **RESOLVED** |
| Numerical tolerances | Analytical: $\pm 10^{-12}\text{ dB}$, Cutoffs: $\pm 10^{-4}\text{ Hz}$, Tilt: $\pm 10^{-6}\text{ dB/oct}$ | **RESOLVED** |
| 3-way builder placement | `src/acoustiforge/builders/multiway_builder.py` | **RESOLVED** |
| 2-way compatibility strategy | Dedicated `ThreeWayGraphBuilder`; 2-way builder 100% frozen | **RESOLVED** |
| 3-way branch identity | `woofer`, `midrange`, `tweeter` | **RESOLVED** |
| Midrange HP $\to$ LP convention | `crossover.hp` $\to$ `crossover.lp` normative sequence | **RESOLVED** |
| Deterministic node IDs | `f"{driver}.crossover.hp.{idx}"`, `f"{driver}.eq.{idx}"`, etc. | **RESOLVED** |
| Crossover frequency invariants | $0 < f_{\text{low}} < f_{\text{high}} < f_s / 2$ | **RESOLVED** |
| Stage omission semantics | Direct port connection bypass for omitted stages | **RESOLVED** |
| Domain model minimum | No entity framework; reuse existing domain value types | **RESOLVED** |
| Golden-data strategy | Analytical closed-form filters and independent reference numbers | **RESOLVED** |
| Dependency policy | Python stdlib + NumPy only | **RESOLVED** |
| Physical-acoustic boundary | Computational data metrics; physical acoustic validity not claimed | **RESOLVED** |

---

## 15. Deferred Questions

1. **Impulse Response WAV Ingestion & Time-Domain Gating:** Deferred to Phase 4C.
2. **Automated Multi-Way Numerical Optimization:** Deferred to Phase 4D.
3. **Room Acoustic Simulation & Modal Analysis:** Strictly deferred.
4. **Real-time Hardware Audio Streaming (PortAudio/sounddevice):** Strictly deferred.

---

## 16. Scope Summary

- **In Scope for Phase 4B Implementation:**
  - `src/acoustiforge/acoustic_math/metrics.py` (Acoustic response metrics & log-Gaussian fractional smoothing).
  - `src/acoustiforge/builders/multiway_builder.py` (`ThreeWayGraphBuilder`).
  - `src/acoustiforge/builders/system_builder.py` (Stereo 3-way extension).
  - Test suites: `tests/test_acoustic_metrics.py`, `tests/test_multiway_graph_builder.py`.
- **Out of Scope:**
  - Code implementation in this task.
  - Changes to frozen layers.
  - New external dependencies.

---

## 17. Implementation Entry Gate

Phase 4B implementation may begin only when:
1. `CONTRACT-ACOUSTIC-METRICS-01` and `CONTRACT-MULTIWAY-BUILDER-01` are ratified.
2. Phase 4A baseline remains frozen at 301 passed tests with 0 warnings.
3. Independent golden test fixtures and analytical vectors are prepared.

---

## 18. Final Reconciliation Verdict

```
PHASE 4B — CONTRACTS READY FOR IMPLEMENTATION
```
