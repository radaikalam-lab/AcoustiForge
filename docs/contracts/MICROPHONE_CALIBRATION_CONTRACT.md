# AcoustiForge Normative Contract: Microphone Calibration
## Contract Identifier: `CONTRACT-MICROPHONE-CALIBRATION-01`

---

## 1. Purpose & Architectural Role

This contract defines the offline, pure mathematical application of microphone calibration curves to raw acoustic frequency response measurements.

The calibration pipeline:
$$\text{Raw Measurement} \; [M_{\text{raw}}(f)] + \text{Microphone Calibration} \; [M_{\text{cal}}(f)] \xrightarrow{\text{apply\_calibration()}} \text{Calibrated Measurement} \; [M_{\text{corrected}}(f)]$$

The calibration operation:
- Resides purely in the acoustic mathematics / calibration plane (`src/acoustiforge/acoustic_math/calibration.py`).
- Is a stateless, deterministic function returning a new immutable `FrequencyResponseData` instance.
- MUST NOT mutate the input `FrequencyResponseData` instances.
- MUST NOT be referenced by the realtime compute plane (`ComputeGraph`, `nodes`).

---

## 2. Mathematical Definition

### 2.1 Magnitude Correction
A microphone calibration file records the frequency response sensitivity deviation of the measurement microphone relative to ideal flat response.

For each measurement frequency $f_i \in \mathbf{f}_{\text{raw}}$:
$$M_{\text{corrected}}(f_i) = M_{\text{raw}}(f_i) - M_{\text{cal}}(f_i) \quad [\text{dB}]$$

*Magnitude-only calibration is the primary, normative case for Phase 4A.*

### 2.2 Phase Correction Semantics
1. **Compatible Transfer Function Phase Only:**
   Phase correction is applied only when the calibration data is explicitly declared to represent a compatible transfer-function phase response ($\phi_{\text{cal}}$):
   $$\phi_{\text{corrected}}(f_i) = \phi_{\text{raw}}(f_i) - \phi_{\text{cal}}(f_i) \quad [\text{radians}]$$
2. **Magnitude-Only Calibration:**
   If the calibration data has no phase ($\phi_{\text{cal}} \text{ is None}$), the raw measurement's phase $\phi_{\text{raw}}(f_i)$ is preserved unmodified.
3. **No Phase Invention:**
   The calibration operation MUST NOT:
   - infer phase when absent;
   - unwrap phase;
   - derive minimum phase;
   - perform time-of-flight phase compensation.

---

## 3. Frequency Alignment & Interpolation Policy

Raw measurement frequency grids $\mathbf{f}_{\text{raw}}$ rarely match calibration file grids $\mathbf{f}_{\text{cal}}$ point-for-point.

### 3.1 Interpolation Domain
- **Domain:** $\log_{10}(\text{frequency\_hz})$.
- **Method:** Piecewise linear interpolation in log-frequency space, identical to `CONTRACT-TARGET-CURVE-01`.

### 3.2 Out-of-Bounds Policy
When raw measurement frequencies extend below $f_{\text{cal, min}}$ or above $f_{\text{cal, max}}$:

1. **Policy `CLAMP` (Default):**
   - For $f < f_{\text{cal, min}}$, calibration magnitude is clamped to $M_{\text{cal}}(f_{\text{cal, min}})$.
   - For $f > f_{\text{cal, max}}$, calibration magnitude is clamped to $M_{\text{cal}}(f_{\text{cal, max}})$.
2. **Policy `ZERO_PAD`:**
   - Outside the calibration range, calibration offset is assumed to be $0.0\text{ dB}$ ($M_{\text{corrected}} = M_{\text{raw}}$).
3. **Policy `STRICT`:**
   - If any $f \in \mathbf{f}_{\text{raw}}$ lies outside $[f_{\text{cal, min}}, f_{\text{cal, max}}]$, raises `CalibrationOutOfRangeError`.

The default policy is **`CLAMP`**, ensuring robust execution over standard audio bandwidth while allowing explicit strict enforcement when required.

---

## 4. Domain Data Representation Analysis

### Domain Object Decision: Pure Reuse of `FrequencyResponseData`
- **Evaluation:** A microphone calibration file consists of discrete frequency points, magnitude offsets in dB, and optional phase offsets in degrees/radians. This structure is identical to `FrequencyResponseData`.
- **Verdict:** Reuse `FrequencyResponseData` directly for calibration curves.
- **Benefits:**
  - Zero modifications to frozen Phase 3B domain models.
  - Full interoperability with Phase 3B validation and immutability invariants.
  - Zero unnecessary wrapper classes or abstraction layers.

---

## 5. Function Signature Contract

```python
class CalibrationBoundaryPolicy(str, Enum):
    CLAMP = "clamp"
    ZERO_PAD = "zero_pad"
    STRICT = "strict"

def apply_microphone_calibration(
    raw_measurement: FrequencyResponseData,
    calibration_data: FrequencyResponseData,
    boundary_policy: CalibrationBoundaryPolicy = CalibrationBoundaryPolicy.CLAMP,
) -> FrequencyResponseData:
    """Apply microphone calibration correction to a raw frequency response measurement.

    Args:
        raw_measurement: Immutable raw measured FrequencyResponseData.
        calibration_data: Immutable microphone calibration FrequencyResponseData.
        boundary_policy: Policy for handling frequencies outside calibration curve range.

    Returns:
        New immutable FrequencyResponseData with corrected magnitude and phase.

    Raises:
        InvalidParameterError: If inputs are not FrequencyResponseData instances.
        CalibrationOutOfRangeError: If boundary_policy is STRICT and measurement exceeds calibration bounds.
    """
```

---

## 6. Verification & Conformance Invariants

1. **Exact Matching:** If $\mathbf{f}_{\text{raw}} == \mathbf{f}_{\text{cal}}$, $M_{\text{corrected}} == M_{\text{raw}} - M_{\text{cal}}$ within float64 machine epsilon ($10^{-15}$).
2. **Immutability:** `raw_measurement` and `calibration_data` arrays must remain bit-exact and unmodified.
3. **Determinism:** Repeated calls produce identical numerical outputs.
