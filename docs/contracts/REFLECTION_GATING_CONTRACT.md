# AcoustiForge Normative Contract: Reflection Gating & Spectral Transformation
## Contract Identifier: `CONTRACT-GATING-01`

---

## 1. Purpose & Scope

This contract governs the mathematical algorithms for pseudo-anechoic reflection gating of time-domain impulse responses and their subsequent transformation into frequency-response datasets ([FrequencyResponseData](file:///E:/AcoustiForge/src/acoustiforge/domain/measurements.py#L24-L67)).

The workflow bridges time-domain measurement into frequency-domain acoustic mathematics:
$$\text{ImpulseResponseData (Raw)} \xrightarrow{\text{Reflection Gate}} \text{Gated Impulse} \xrightarrow{\text{Discrete Fourier Transform}} \text{FrequencyResponseData}$$

---

## 2. Window Mathematical Definitions

All window functions are evaluated over discrete coordinate $n \in [0, M-1]$ of length $M \ge 1$:

### 2.1 Rectangular Window (`RectangularWindow`)
$$w_{\text{rect}}[n] = 1.0 \quad \forall n \in [0, M-1]$$

### 2.2 Hann Window (`HannWindow`)
$$w_{\text{hann}}[n] = 0.5 \left( 1 - \cos\left( \frac{2\pi n}{M - 1} \right) \right) \quad \text{for } M > 1, \quad w[0] = 1.0 \text{ if } M=1$$

### 2.3 Tukey Window (`TukeyWindow(alpha)`)
Tapered cosine window parameterized by taper fraction $\alpha \in [0.0, 1.0]$:
- $\alpha = 0.0$: Equivalent to `RectangularWindow` (no taper).
- $\alpha = 1.0$: Equivalent to `HannWindow` (full taper).
- For $0 < \alpha < 1.0$, with transition width $L = \lfloor \frac{\alpha (M - 1)}{2} \rfloor$:
  $$w[n] = \begin{cases} 
  0.5 \left( 1 - \cos\left( \frac{\pi n}{L} \right) \right) & 0 \le n < L \\
  1.0 & L \le n \le M - 1 - L \\
  0.5 \left( 1 - \cos\left( \frac{\pi (M - 1 - n)}{L} \right) \right) & M - 1 - L < n \le M - 1
  \end{cases}$$

---

## 3. Reflection Gating Algorithm & Specification

### 3.1 Gate Specification (`GateSpecification`)
An immutable specification defining:
- `left_time_ms: Optional[float] = None` (or `left_samples: Optional[int] = None`): Duration before the impulse peak to begin the left taper. Defaults to $1.0\text{ ms}$.
- `right_time_ms: Optional[float] = None` (or `right_samples: Optional[int] = None`): Duration after the impulse peak before truncating the floor/ceiling reflection.
- `left_window: WindowType = WindowType.HALF_HANN` (left taper function).
- `right_window: WindowType = WindowType.HALF_HANN` (right taper function).

### 3.2 Gate Boundary Indexing
Given total samples $N$, sample rate $f_s$, and peak index $n_{\text{peak}}$:
1. Convert durations to discrete sample spans:
   $$n_{\text{left}} = \text{round}\left( \text{left\_time\_ms} \times 10^{-3} \times f_s \right)$$
   $$n_{\text{right}} = \text{round}\left( \text{right\_time\_ms} \times 10^{-3} \times f_s \right)$$
2. Compute gate boundary indices:
   $$n_{\text{start}} = \max(0, n_{\text{peak}} - n_{\text{left}})$$
   $$n_{\text{end}} = \min(N - 1, n_{\text{peak}} + n_{\text{right}})$$
3. Construct composite gating weight vector $W[n]$ of length $N$:
   - For $n < n_{\text{start}}$: $W[n] = 0.0$.
   - For $n \in [n_{\text{start}}, n_{\text{peak}}]$: $W[n]$ follows left taper from $0.0$ to $1.0$.
   - For $n \in [n_{\text{peak}}, n_{\text{end}}]$: $W[n]$ follows right taper from $1.0$ to $0.0$.
   - For $n > n_{\text{end}}$: $W[n] = 0.0$.
4. Multiply raw samples:
   $$h_{\text{gated}}[n] = h[n] \times W[n] \quad \forall n \in [0, N-1]$$

### 3.3 Output Immutability & Time Reference Preservation
- Reflection gating returns an immutable `GatedImpulseResult` containing:
  - `gated_impulse: ImpulseResponseData`: Gated impulse array of identical length $N$ and sample rate $f_s$, preserving original time origin ($t=0$ at index $0$) and `peak_index`.
  - `gate_start_index: int`: $n_{\text{start}}$.
  - `gate_end_index: int`: $n_{\text{end}}$.
  - `gate_duration_seconds: float`: $T_{\text{gate}} = \frac{n_{\text{end}} - n_{\text{start}}}{f_s}$.
  - `f_min_valid_hz: float`: Low-frequency validity cutoff $f_{\text{min, valid}} = \frac{1.0}{T_{\text{gate}}}$.

---

## 4. Spectral Fourier Transformation & Phase Convention

### 4.1 FFT Transform Configuration
1. **$N_{\text{fft}}$ Zero-Padding Policy:**
   - Default: Next power of 2 greater than or equal to $N$:
     $$N_{\text{fft}} = 2^{\lceil \log_2 N \rceil}$$
   - Configurable: User-supplied $N_{\text{fft}} \ge N$.
2. **Real-Valued FFT:**
   $$\tilde{H}[k] = \sum_{n=0}^{N-1} h_{\text{gated}}[n] e^{-j 2\pi k n / N_{\text{fft}}}, \quad k \in [0, N_{\text{fft}}/2]$$
3. **Frequency Vector:**
   $$f_k = k \frac{f_s}{N_{\text{fft}}}$$
   To conform with [FrequencyResponseData](file:///E:/AcoustiForge/src/acoustiforge/domain/measurements.py#L24-L67)'s strict positivity invariant ($f_i > 0.0$), the DC component ($k=0$) is excluded. The output frequency grid spans $k \in [1, N_{\text{fft}}/2]$.

### 4.2 Magnitude Convention
$$\text{magnitude\_db}[k] = 20 \log_{10}\left( \max\left( |\tilde{H}[k]|, 10^{-12} \right) \right)$$
Zero magnitude is clamped at $-240\text{ dB}$ ($10^{-12}$) to prevent non-finite values.

### 4.3 Phase Convention
1. **Raw FFT Phase (Default, `phase_reference="raw"`):**
   $$\phi[k] = \text{atan2}\left( \text{Im}(\tilde{H}[k]), \text{Re}(\tilde{H}[k]) \right) \in (-\pi, \pi] \quad [\text{radians}]$$
   Includes the true physical/time-of-flight phase slope $\phi(f) = -2\pi f \frac{n_{\text{peak}}}{f_s}$.
2. **Peak-Aligned Phase (`phase_reference="peak_aligned"`):**
   Multiplies complex spectrum by $e^{+j 2\pi k n_{\text{peak}} / N_{\text{fft}}}$ to remove time-of-flight delay before extracting phase.

---

## 5. Analytical Golden Conformance

1. **Analytical Dirac Delta:**
   $$h[0] = 1.0, \quad h[n] = 0.0 \quad (\forall n > 0)$$
   $$\implies |H(f)| = 1.0, \quad \text{magnitude} = 0.0\text{ dB}, \quad \text{phase} = 0.0\text{ rad}$$
2. **Analytical Delayed Delta:**
   $$h[D] = 1.0, \quad h[n] = 0.0 \quad (\forall n \ne D)$$
   $$\implies |H(f)| = 1.0, \quad \text{magnitude} = 0.0\text{ dB}, \quad \text{phase}[k] = -2\pi f_k \frac{D}{f_s} \pmod{2\pi}$$
3. **Single-Pole Exponential Decay ($h[n] = e^{-n / \tau}$):**
   $$H(f) = \frac{1}{1 - e^{-1/\tau} e^{-j 2\pi f / f_s}}$$
   Must match analytical magnitude and phase within $\pm 10^{-6}\text{ dB}$ and $\pm 10^{-6}\text{ rad}$.
