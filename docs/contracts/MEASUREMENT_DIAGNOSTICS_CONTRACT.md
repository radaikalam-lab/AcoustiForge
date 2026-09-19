# AcoustiForge Normative Contract: Acoustic Measurement Diagnostics
## Contract Identifier: `CONTRACT-DIAGNOSTICS-01`

---

## 1. Purpose & Scope

This contract governs the automated mathematical quality diagnostics evaluated over raw/gated acoustic impulse responses ([ImpulseResponseData](file:///E:/AcoustiForge/src/acoustiforge/domain/measurements.py#L70-L121)) and frequency responses ([FrequencyResponseData](file:///E:/AcoustiForge/src/acoustiforge/domain/measurements.py#L24-L67)).

Diagnostics execute offline in `src/acoustiforge/acoustic_math/diagnostics.py` to identify:
1. Low-frequency pseudo-anechoic validity boundaries ($f_{\text{valid, min}}$).
2. Time-domain signal-to-noise ratio (SNR) and pre-onset noise contamination.
3. Room reflection comb-filtering interference notches.
4. Phase discontinuity / wrapping anomalies.

---

## 2. Diagnostic Mathematical Formulations

### 2.1 Low-Frequency Validity Boundary ($f_{\text{valid, min}}$)
- **Input:** Gate duration $T_{\text{gate}} = \frac{n_{\text{end}} - n_{\text{start}}}{f_s}$ in seconds.
- **Formulation:**
  $$f_{\text{valid, min}} = \frac{1.0}{T_{\text{gate}}} \quad [\text{Hz}]$$
- **Semantic:** Below $f_{\text{valid, min}}$, frequency bins do not contain a full cycle of oscillation; metric calculations or target fitting in this region are flagged with `DiagnosticFlag.LOW_FREQUENCY_RESOLUTION_LIMIT`.

### 2.2 Time-Domain Signal-to-Noise Ratio (SNR)
- **Input:** Raw impulse samples $h[n]$ of length $N$, peak index $n_{\text{peak}}$, and gate start index $n_{\text{start}}$.
- **Pre-Onset Noise Calculation:**
  Evaluated over pre-arrival samples $n \in [0, \max(1, n_{\text{start}} - 1)]$:
  $$\text{RMS}_{\text{noise}} = \sqrt{\frac{1}{n_{\text{start}}} \sum_{n=0}^{n_{\text{start}}-1} h[n]^2}$$
  If $n_{\text{start}} < 8$, noise floor is evaluated over the first $5\%$ of the buffer.
- **Peak Signal Amplitude:**
  $$A_{\text{peak}} = |h[n_{\text{peak}}]|$$
- **SNR in Decibels:**
  $$\text{SNR}_{\text{db}} = 20 \log_{10}\left( \frac{A_{\text{peak}}}{\max(\text{RMS}_{\text{noise}}, 10^{-12})} \right)$$
- **Threshold Policy:**
  - If $\text{SNR}_{\text{db}} < 20.0\text{ dB}$: Flag `DiagnosticFlag.POOR_SNR_WARNING`.
  - If $\text{SNR}_{\text{db}} < 6.0\text{ dB}$: Flag `DiagnosticFlag.CRITICAL_NOISE_FLOOR_ERROR` and set `is_valid = False`.

### 2.3 Reflection Comb-Filtering Notch Detection
- **Input:** Magnitude spectrum $M(f)$ in dB across frequencies $f \ge f_{\text{valid, min}}$.
- **Notch Criteria:**
  A local minimum at frequency $f_0$ is classified as a reflection notch if:
  1. **Depth:** The dip depth $\Delta M = \min(M_{\text{left\_peak}}, M_{\text{right\_peak}}) - M(f_0) \ge 6.0\text{ dB}$.
  2. **Bandwidth / Q Factor:**
     $$Q = \frac{f_0}{\Delta f_{-3\text{dB}}} \ge 10.0$$
  3. **Periodicity:**
     If $\ge 3$ consecutive detected notches exhibit approximately uniform frequency spacing:
     $$\Delta f_k = f_{k+1} - f_k, \quad \left| \frac{\Delta f_k - \overline{\Delta f}}{\overline{\Delta f}} \right| \le 0.15$$
     Then a reflection interference condition is declared with estimated path delay:
     $$\tau_{\text{refl}} = \frac{1.0}{\overline{\Delta f}} \quad [\text{seconds}]$$
     and flagged with `DiagnosticFlag.REFLECTION_CONTAMINATION_WARNING`.

---

## 3. Diagnostic Report Data Model

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

class DiagnosticFlag(str, Enum):
    CLEAN = "CLEAN"
    LOW_FREQUENCY_RESOLUTION_LIMIT = "LOW_FREQUENCY_RESOLUTION_LIMIT"
    POOR_SNR_WARNING = "POOR_SNR_WARNING"
    CRITICAL_NOISE_FLOOR_ERROR = "CRITICAL_NOISE_FLOOR_ERROR"
    REFLECTION_CONTAMINATION_WARNING = "REFLECTION_CONTAMINATION_WARNING"
    PHASE_DISCONTINUITY_WARNING = "PHASE_DISCONTINUITY_WARNING"

@dataclass(frozen=True, slots=True)
class MeasurementDiagnosticReport:
    """Immutable diagnostic report for acoustic measurements."""
    is_valid: bool
    snr_db: float
    f_valid_min_hz: float
    flags: Tuple[DiagnosticFlag, ...]
    estimated_reflection_ms: Optional[float] = None
```

---

## 4. Conformance & Verification Criteria

1. **Clean Synthetic Impulse:** Verification that idealized Dirac and delayed delta return `is_valid = True`, `flags = (DiagnosticFlag.CLEAN,)`, and `estimated_reflection_ms = None`.
2. **Injected Noise Impulse:** Synthetic impulse with $-12\text{ dB}$ SNR triggers `POOR_SNR_WARNING`.
3. **Simulated Reflection Contamination:** Direct impulse + delayed reflection at $5.0\text{ ms}$ ($\Delta f = 200\text{ Hz}$ notches) triggers `REFLECTION_CONTAMINATION_WARNING` with $\tau_{\text{refl}} \approx 5.0\text{ ms} \pm 0.2\text{ ms}$.
