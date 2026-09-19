# AcoustiForge Normative Contract: Acoustic Response Analysis & Quantitative Metrics
## Contract Identifier: `CONTRACT-ACOUSTIC-METRICS-01`
## Version: `1.0.0`

---

## 1. Purpose & Architectural Role

This contract defines the offline, pure mathematical analysis and quantitative metric extraction over immutable acoustic frequency response measurements (`FrequencyResponseData`).

The acoustic metrics pipeline:
$$\text{FrequencyResponseData} \; [M(f)] \; (+ \text{AcousticTargetCurve} \; [T(f)]) \xrightarrow{\text{calculate\_response\_metrics()}} \text{AcousticMetricsResult}$$

### Architectural Boundaries:
- **Layer Placement:** Resides strictly in the acoustic mathematics plane (`src/acoustiforge/acoustic_math/metrics.py`).
- **Mathematical Purity:** Functions are pure, stateless, and deterministic.
- **Data Immutability:** Input `FrequencyResponseData` and `AcousticTargetCurve` instances are never mutated.
- **Compute Isolation:** Metrics analysis runs exclusively in the offline control plane and MUST NOT be referenced in the realtime audio execution path (`ComputeGraph.process()`).
- **Domain Separation:** Metrics evaluate properties of the *numerical measurement dataset*; they do NOT claim physical acoustic directivity, 3D soundfield, or transducer non-linearity validation.

---

## 2. Mathematical Formulations & Definitions

### 2.1 Passband Sensitivity ($S_{\text{passband}}$)
Passband sensitivity represents the true energetic mean sound pressure level (SPL) within a declared frequency span $[f_{\text{min}}, f_{\text{max}}]$.

$$\overline{I} = \frac{1}{\log_{10}(f_{\text{max}}) - \log_{10}(f_{\text{min}})} \int_{\log_{10} f_{\text{min}}}^{\log_{10} f_{\text{max}}} 10^{M(f)/10} \, d(\log_{10} f)$$
$$S_{\text{passband}} = 10 \log_{10}\left( \overline{I} \right) \quad [\text{dB SPL}]$$

#### Numerical Evaluation:
1. Frequency bounds $[f_{\text{min}}, f_{\text{max}}]$ default to $[200.0, 2000.0]\text{ Hz}$ (or user-specified passband).
2. Integration is performed via the trapezoidal rule over discrete coordinate points in $\log_{10}(f)$ space.
3. If $f_{\text{min}}$ or $f_{\text{max}}$ falls between measurement bins, exact log-linear interpolation of magnitude $M(f)$ is performed at the boundary coordinates before integration.

---

### 2.2 Bandwidth Cutoff Frequencies ($F_3, F_6, F_{10}$)
Cutoff frequencies determine the effective operating bandwidth relative to the reference passband sensitivity $S_{\text{passband}}$.

$$\text{Thresholds:} \quad M_{\Delta} = S_{\text{passband}} - \Delta \quad \text{for } \Delta \in \{3.0, 6.0, 10.0\} \text{ dB}$$

#### Low-Frequency Cutoff ($F_{3,\text{low}}, F_{6,\text{low}}, F_{10,\text{low}}$):
- **Search Range:** $f \le f_{\text{min}}$ (searching downwards from the passband lower bound).
- **Outermost Policy (Normative):** Defined as the highest frequency below $f_{\text{min}}$ where the response falls permanently below $M_{\Delta}$ (i.e. the outermost boundary crossing into the low-frequency attenuation rolloff).
- **Interpolation:** Exact log-linear interpolation between the two straddling measurement points $(f_1, M_1)$ and $(f_2, M_2)$:
  $$\log_{10}(F_{\text{cutoff}}) = \log_{10}(f_1) + \frac{M_{\Delta} - M_1}{M_2 - M_1} \left( \log_{10}(f_2) - \log_{10}(f_1) \right)$$
- **No-Crossing:** If the response never drops below $M_{\Delta}$ within the measured data range, $F_{\text{cutoff}}$ is `None`.

#### High-Frequency Cutoff ($F_{3,\text{high}}, F_{6,\text{high}}, F_{10,\text{high}}$):
- **Search Range:** $f \ge f_{\text{max}}$ (searching upwards from the passband upper bound).
- **Outermost Policy (Normative):** Defined as the lowest frequency above $f_{\text{max}}$ where the response falls permanently below $M_{\Delta}$.
- **Interpolation:** Log-linear interpolation as defined above.
- **No-Crossing:** Returns `None` if the upper threshold is never crossed.

---

### 2.3 Target Tracking Error
When an `AcousticTargetCurve` is provided, tracking error metrics quantify the deviation of measured SPL $M(f)$ from target SPL $T(f)$ across their shared frequency overlap $[f_{\text{start}}, f_{\text{end}}] = [\max(f_{\text{raw,min}}, f_{\text{target,min}}), \min(f_{\text{raw,max}}, f_{\text{target,max}})]$.

1. **Error Profile:** $E(f_i) = M(f_i) - T(f_i)$ evaluated at all measurement points $f_i \in [f_{\text{start}}, f_{\text{end}}]$. Target $T(f_i)$ is evaluated via `evaluate_target_curve(curve, f_i)`.
2. **RMS Error ($E_{\text{rms}}$):**
   $$E_{\text{rms}} = \sqrt{ \frac{1}{K} \sum_{i=1}^K \left( M(f_i) - T(f_i) \right)^2 } \quad [\text{dB}]$$
3. **Peak Positive Error ($E_{\text{peak+}}$):**
   $$E_{\text{peak+}} = \max_{i} \left( M(f_i) - T(f_i) \right) \quad [\text{dB}]$$
4. **Peak Negative Error ($E_{\text{peak-}}$):**
   $$E_{\text{peak-}} = \min_{i} \left( M(f_i) - T(f_i) \right) \quad [\text{dB}]$$

If no `AcousticTargetCurve` is supplied, target error fields return `None`.

---

### 2.4 Spectral Tilt
Spectral tilt represents the broad spectral slope of the transducer response in dB per octave across a declared frequency band.

$$\text{tilt} = \frac{\sum_{i=1}^N \left( \log_2(f_i) - \overline{\log_2 f} \right) \left( M(f_i) - \overline{M} \right)}{\sum_{i=1}^N \left( \log_2(f_i) - \overline{\log_2 f} \right)^2} \quad [\text{dB/octave}]$$

- Computed via unweighted Ordinary Least Squares (OLS) linear regression of $M(f)$ against $\log_2(f)$.
- Evaluated on raw discrete measurement points unless explicitly smoothed data is passed.

---

### 2.5 Passband Ripple
Passband ripple measures the peak-to-peak SPL excursion within the passband $[f_{\text{min}}, f_{\text{max}}]$:

$$\text{Ripple} = \max_{f \in [f_{\text{min}}, f_{\text{max}}]} M(f) - \min_{f \in [f_{\text{min}}, f_{\text{max}}]} M(f) \quad [\text{dB}]$$

---

### 2.6 Fractional-Octave Smoothing
Fractional-octave smoothing produces a continuous, variance-reduced representation of frequency response using a standard log-Gaussian windowing kernel.

#### Kernel Specification:
For an octave fraction parameter $N \in \{3, 6, 12, 24\}$ (representing $1/N$-octave smoothing):
1. **Octave Standard Deviation:**
   $$\sigma = \frac{1}{N \cdot 2\sqrt{2\ln 2}} \approx \frac{1}{2.35482 \cdot N} \quad [\text{octaves}]$$
2. **Point Weighting:** For each evaluation center frequency $f_i$, the weight for candidate measurement point $f_j$ is:
   $$w_{ij} = \exp\left( -\frac{(\log_2(f_j) - \log_2(f_i))^2}{2\sigma^2} \right)$$
3. **Normalized Output:**
   $$M_{\text{smooth}}(f_i) = \frac{\sum_{j} w_{ij} M(f_j)}{\sum_{j} w_{ij}} \quad [\text{dB}]$$
4. **Truncation Window:** Computation is truncated to points within $|\log_2(f_j) - \log_2(f_i)| \le 3\sigma$ (weights $< 0.011$ are zeroed).
5. **Boundary Normalization:** Division by $\sum w_{ij}$ guarantees exact energy preservation and eliminates artificial edge drop-off at measurement extremes.

---

## 3. Data Types & API Specification

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
import numpy as np

class SmoothingMode(str, Enum):
    NONE = "none"
    OCTAVE_1_3 = "1/3"
    OCTAVE_1_6 = "1/6"
    OCTAVE_1_12 = "1/12"
    OCTAVE_1_24 = "1/24"

@dataclass(frozen=True, slots=True)
class AcousticMetricsResult:
    """Immutable mathematical analysis result container for acoustic metrics."""
    passband_sensitivity_db: float
    f3_low_hz: Optional[float]
    f3_high_hz: Optional[float]
    f6_low_hz: Optional[float]
    f6_high_hz: Optional[float]
    f10_low_hz: Optional[float]
    f10_high_hz: Optional[float]
    rms_target_error_db: Optional[float]
    peak_positive_error_db: Optional[float]
    peak_negative_error_db: Optional[float]
    spectral_tilt_db_per_oct: float
    passband_ripple_db: float
    passband_range_hz: Tuple[float, float]

def calculate_response_metrics(
    measurement: FrequencyResponseData,
    target_curve: Optional[AcousticTargetCurve] = None,
    passband_hz: Optional[Tuple[float, float]] = None,
    smoothing: SmoothingMode = SmoothingMode.NONE,
) -> AcousticMetricsResult:
    """Calculate deterministic quantitative acoustic metrics over a frequency response measurement.

    Args:
        measurement: Immutable FrequencyResponseData instance.
        target_curve: Optional AcousticTargetCurve instance for error tracking.
        passband_hz: Optional (f_min, f_max) tuple defining the reference passband.
            Defaults to (200.0, 2000.0) Hz, clamped to measurement bounds.
        smoothing: Fractional-octave smoothing mode to apply prior to metric evaluation.

    Returns:
        Immutable AcousticMetricsResult dataclass.

    Raises:
        InvalidParameterError: If measurement is invalid, frequency bounds are inverted,
            or fewer than 2 points exist in the analysis span.
    """

def smooth_frequency_response(
    measurement: FrequencyResponseData,
    mode: SmoothingMode,
) -> FrequencyResponseData:
    """Apply log-Gaussian fractional-octave smoothing to FrequencyResponseData.

    Args:
        measurement: Immutable FrequencyResponseData instance.
        mode: Fractional-octave smoothing fraction (NONE, 1/3, 1/6, 1/12, 1/24).

    Returns:
        New immutable FrequencyResponseData with smoothed magnitude (phase unmodified).
    """
```

---

## 4. Invariants & Verification Tolerances

1. **Determinism:** Repeated evaluation on identical inputs yields bit-exact outputs.
2. **Analytical Linearity:** For an idealized flat response at $M(f) = K\text{ dB}$, $S_{\text{passband}} = K \pm 10^{-12}\text{ dB}$, $\text{tilt} = 0.0 \pm 10^{-12}\text{ dB/oct}$, $\text{ripple} = 0.0 \pm 10^{-12}\text{ dB}$.
3. **Butterworth Low-Pass Cutoff Invariant:** For an idealized Butterworth low-pass filter of order $N$ with cutoff $f_c$, $F_{3,\text{high}} = f_c \pm 10^{-4}\text{ Hz}$, $F_{6,\text{high}} = f_c \cdot 10^{6 / (20N)} \pm 10^{-4}\text{ Hz}$, and asymptote slope $\to -6.0206 N\text{ dB/octave} \pm 10^{-3}\text{ dB/octave}$.
4. **Input Immutability:** Input arrays remain strictly read-only and unmutated.
5. **Dependency Isolation:** Pure Python standard library + NumPy array operations. Zero SciPy/Pandas dependencies.
