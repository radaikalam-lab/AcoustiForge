# AcoustiForge Phase 5-4C — Physical Closed-Loop Validation Discovery

> **Document Type:** Architectural Discovery & Experimental Protocol  
> **Status:** DISCOVERY ONLY — NOT AN IMPLEMENTATION CONTRACT  
> **Repository:** `E:\AcoustiForge`  
> **Core Baseline:** 100% Frozen (Phases 1 through 5-7A)  
> **Verified Regression Baseline:** 505 Passed, 2 Skipped, 0 Failed, 0 Errors, 0 Warnings (`pytest -q -W error`)  
> **Date:** September 2026  

---

## 1. Executive Summary & Objective

Phase 5-4 implemented and validated the `AlsaExecutionBackend` in native Linux software userspace via `ctypes` bindings to `libasound.
so.2`. The upstream acoustic modeling, optimization, graph compilation, and experience telemetry subsystems are completely verified across 505 automated tests.

The purpose of **Phase 5-4C Discovery** is to define the **smallest technically correct and experimentally rigorous path** from the current software repository to a verified **physical closed-loop acoustic experiment**:

```text
[AcoustiForge Core]
        │
  (ComputeGraph)
        │
  [ALSA Playback] ──> [Physical DAC] ──> [Amplifier / Speaker]
                                                 │
                                           (Physical Room)
                                                 │
  [AcoustiForge Ingestion] <── [ALSA Capture] <── [Calibrated Mic]
```

### Core Discovery Findings:
1. **Existing Foundation is Strong:** AcoustiForge already possesses complete time-domain impulse ingestion (`impulse_parser.py`), reflection gating (`gating.py`), microphone calibration subtraction (`calibration.py`), acoustic metrics calculation (`metrics.py`), and ALSA playback streaming with xrun recovery (`alsa.py`).
2. **Key Missing Software Elements:**
   - A **deterministic logarithmic sine sweep generator and deconvolution engine** (stimulus creation & impulse response extraction).
   - An **ALSA audio capture adapter** (`snd_pcm_readi` binding) to record PCM from physical USB microphones.
3. **Crucial Architectural Realization:** The first closed-loop validation **must NOT use full-duplex real-time streaming**. USB DACs and USB measurement microphones run on separate, asynchronous crystal clocks. Real-world acoustic measurement must operate via **sequential sweep excitation, capture, and deconvolution**, which is clock-drift immune and robust.

---

## 2. Existing Capability Inventory vs. Physical Boundary Gap Map

| Component | Existing in Repository | Missing in Repository | Can Reuse | Validation Needed |
| :--- | :--- | :--- | :--- | :--- |
| **ALSA Playback** | `AlsaExecutionBackend` with `snd_pcm_writei`, xrun recovery, planar-to-interleaved conversion. | None in software logic. | `src/acoustiforge/execution/alsa.py` | Verify continuous streaming on physical Linux hardware. |
| **USB DAC Output** | `LinuxStreamConfig` specifying ALSA device string (e.g., `hw:0,0` or `default`). | Physical hardware test rig. | `alsa.py` device handle lifecycle. | Electrical verification of analog output signal. |
| **Signal Generation** | Test impulse synthesis helpers in `tests/test_impulse_parser.py`. | Production deterministic log-sine sweep generator and deconvolution filter. | Math formulas in NumPy. | Spectral flatness and time-frequency linearity verification. |
| **ALSA Capture** | `SND_PCM_STREAM_CAPTURE` constant defined in `alsa.py`. | `snd_pcm_readi` prototype in `AlsaCtypesBinding`, capture device handle, and recording loop. | `AlsaPCMAdapter.interleaved_float32_to_planar_pcm_block`. | Buffer underrun/overrun handling on real USB mic input. |
| **USB Microphone** | None (Hardware external). | None (Hardware external). | Standard ALSA USB audio driver (`snd-usb-audio`). | Confirm OS device enumeration and sample rate support. |
| **WAV Recording / Buffering** | `_parse_wav_bytes` in `impulse_parser.py`. | In-memory PCM buffer accumulator or WAV file writer helper. | `PCMBlock` canonical contracts. | Verify sample rate and bit-depth fidelity. |
| **Microphone Calibration** | `apply_microphone_calibration` with magnitude and phase subtraction. | None. | `src/acoustiforge/acoustic_math/calibration.py` | Verify with real `.cal` text calibration files. |
| **Impulse Extraction** | `ImpulseResponseData` domain model and parser. | Log-sweep deconvolution function ($IR = \mathcal{F}^{-1}\{\mathcal{F}(y) \cdot \mathcal{F}(x_{\text{inv}})\slidesPerGroup$). | Existing domain models in `domain/measurements.py`. | Verify impulse peak alignment and time-zero synchronization. |
| **Reflection Gating** | `apply_reflection_gate`, `transform_impulse_to_frequency_response`, windowing. | None. | `src/acoustiforge/acoustic_math/gating.py` | Verify window placement on real room impulse response. |
| **FRD Generation** | `FrequencyResponseData` generation and quality diagnostics. | None. | `gating.py` & `diagnostics.py` | Verify SNR and reflection comb notch detection on live room data. |
| **Optimization** | Single-point and Track C spatial coordinate descent optimizer. | None. | `src/acoustiforge/acoustic_math/optimization.py` | Validate convergence against real physical FRD input. |
| **ComputeGraph** | Multi-way graph builder, Biquad, Gain, Delay, Sum DAG nodes. | None. | `src/acoustiforge/graph/` & `builders/` | Confirm real-time graph evaluation latency. |
| **Real-Time DSP Playback** | `AlsaExecutionBackend` streaming through `ComputeGraph`. | None. | `alsa.py` pipeline. | Verify audible and electrical output changes when filters are active. |
| **Re-Measurement Loop** | Multi-step pipeline tests (`test_phase_4c_end_to_end.py`). | Automated test script coordinating excitation $\to$ capture $\to$ compare. | All above modules. | Physical repeatability and metric variance evaluation. |

---

## 3. Hardware-Neutral Requirements

To ensure architectural purity and avoid premature coupling to specific commercial brands, AcoustiForge defines **functional hardware category requirements** rather than mandatory part numbers:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       MINIMUM HARDWARE CATEGORY MODEL                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. LINUX HOST / SBC                                                        │
│     - POSIX Linux kernel (>= 5.10) with standard ALSA userspace (`libasound`)│
│     - Minimum 1 GHz ARM Cortex-A53 / x86-64 CPU (>= 2 cores recommended)    │
│     - Minimum 512 MB RAM                                                    │
│                                                                             │
│  2. ALSA-COMPATIBLE OUTPUT DEVICE (DAC)                                     │
│     - Standard USB Audio Class (UAC1/UAC2) DAC or I²S Audio Codec / Hat     │
│     - Native support for 48,000 Hz (or 44,100 Hz), 16-bit or 24-bit PCM     │
│     - Direct hardware access via ALSA (`hw:X,Y` or `plughw:X,Y`)            │
│     - Monotonic, jitter-stable sample clock                                 │
│                                                                             │
│  3. ALSA-COMPATIBLE CAPTURE DEVICE (MICROPHONE)                             │
│     - Calibrated USB measurement microphone (or XLR mic with USB interface)  │
│     - Factory or laboratory calibration file (`.cal` or `.txt` format)      │
│     - Known nominal sensitivity and flat acoustic baseline                  │
│                                                                             │
│  4. ACOUSTIC TRANSDUCER & AMPLIFIER                                         │
│     - Powered active studio monitor or passive speaker with power amplifier  │
│     - Stable linear electrical response within passband (50 Hz - 15 kHz)    │
│     - Electrically isolated and safe gain staging                           │
│                                                                             │
│  5. PHYSICAL TEST ENVIRONMENT                                               │
│     - Enclosed room with stable ambient noise floor (< 45 dBA recommended)  │
│     - Fixed microphone stand and fixed loudspeaker boundary placement       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Critical Architectural Choice: Sequential Capture vs. Full-Duplex

A critical question for physical validation is whether AcoustiForge requires **synchronous full-duplex streaming** (simultaneous playback and capture in the same real-time audio thread) or **sequential asynchronous capture**.

```text
  OPTION A: SEQUENTIAL CAPTURE (RECOMMENDED)
  ┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
  │ 1. Generate Sweep File  │ ---> │ 2. Play Sweep via ALSA  │ ---> │ 3. Record Room via ALSA │
  │    (Deterministic WAV)  │      │    (Playback Stream)    │      │    (Capture Stream)     │
  └─────────────────────────┘      └─────────────────────────┘      └────────────┬────────────┘
                                                                                 │
                                                                                 v
  ┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
  │ 6. Output Calibrated FRD│ <--- │ 5. Window & FFT Gating  │ <--- │ 4. Deconvolve to Time   │
  │    (FrequencyResponse)  │      │    (Reflection Gate)    │      │    Domain Impulse (IR)  │
  └─────────────────────────┘      └─────────────────────────┘      └─────────────────────────┘

  OPTION B: SYNCHRONOUS FULL-DUPLEX (REJECTED FOR PHASE 5-4C)
  ┌───────────────────────────────────────────────────────────────────────────────────────────┐
  │ Audio Thread Loop:                                                                        │
  │   [Read Input Block from USB Mic] <==== CLOCK DRIFT / ASYNC JITTER ====> [Write to USB DAC]│
  │   - Requires common hardware word-clock sync between separate USB devices                 │
  │   - High risk of buffer starvation, deadlock, and phase modulation artifacts              │
  └───────────────────────────────────────────────────────────────────────────────────────────┘
```

### Analysis & Recommendation:
- In real-world acoustic test equipment (e.g., REW, Dirac Live, Audio Precision), acoustic transfer functions are measured using **sequential logarithmic sine sweeps**.
- USB DACs and USB measurement microphones have **independent quartz crystal oscillators**. In a full-duplex loop without word-clock synchronization, the two clocks drift by several parts-per-million, causing progressive buffer skew and destructive sample slips.
- **Decision:** **Option A (Sequential Capture with Farina Log-Sweep Deconvolution)** is mathematically superior, clock-drift immune, resilient to operating system buffer jitter, and 100% sufficient for closed-loop validation.

---

## 5. Signal Generation & Excitation Architecture

AcoustiForge currently lacks a production excitation signal generator. For Phase 5-4C, the following minimal, deterministic signal generator must be specified:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                     LOGARITHMIC SINE SWEEP GENERATOR                        │
└─────────────────────────────────────────────────────────────────────────────┘

  Parameters:
  • f_start   : 20.0 Hz (or custom start frequency)
  • f_end     : 20,000.0 Hz (Nyquist-bounded)
  • duration  : 5.0 seconds (sufficient for high SNR in domestic rooms)
  • sample_rate: 48,000 Hz
  • amplitude : -6.0 dBFS (0.5 peak, prevents DAC inter-sample clipping)

  Mathematical Formulation:
  x(t) = A * sin( (2 * pi * f_start * T / ln(f_end / f_start)) * (exp(t / T * ln(f_end / f_start)) - 1) )

  Inverse Filter Formulation (Farina Method):
  x_inv(t) = x(T - t) * exp(-t / T * ln(f_end / f_start))
  (Time-reversed sweep weighted by -6 dB/octave attenuation to equalize pink spectrum)
```

### Key Requirements:
1. **Zero Phase Distortion:** Pure mathematical evaluation in double-precision NumPy float64 before conversion to float32 `PCMBlock`.
2. **Deterministic WAV Export:** Ability to save reference sweep as a 24-bit or 16-bit WAV file for offline testing and standalone playback.
3. **Analytical Invertibility:** Deconvolution of synthetic $x(t) \ast x_{\text{inv}}(t)$ must yield a perfect Dirac delta function with time-domain sidelobes $< -90\text{ dBFS}$.

---

## 6. Capture Architecture & ALSA Binding

The existing `AlsaExecutionBackend` in `src/acoustiforge/execution/alsa.py` was built primarily for playback. To support physical measurement capture without mutating frozen core abstractions:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ALSA CAPTURE ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────────────┘

  1. DYNAMIC CTYPES PROTOTYPE ADDITION:
     - `snd_pcm_readi(snd_pcm_t *pcm, void *buffer, snd_pcm_uframes_t size) -> c_long`
     - Added cleanly to `AlsaCtypesBinding._setup_prototypes()`.

  2. CAPTURE HANDLE:
     - `NativeAlsaCaptureHandle` wrapping `snd_pcm_open(&ptr, name, SND_PCM_STREAM_CAPTURE, 0)`.
     - `readi(frames) -> np.ndarray` interleaved buffer.

  3. CAPTURE CONTROLLER / ADAPTER:
     - `AlsaCaptureRecorder`: Opens capture device, records $N$ seconds of audio, detects overruns
       (`-EPIPE`), and converts interleaved float32/int16 buffer into canonical `PCMBlock`.

  4. DECOUPLING FROM CORE:
     - Capture lives in `src/acoustiforge/execution/` or a specialized validation harness.
     - Core `ComputeGraph` remains an audio processor; it does not know or care how the audio was recorded.
```

---

## 7. Measurement Integrity & Repeatability Controls

To guarantee that AcoustiForge distinguishes between **genuine physical acoustic correction** and **measurement noise or experimental artifacts**, the validation protocol must enforce five strict controls:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       MEASUREMENT INTEGRITY CONTROLS                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. ACOUSTIC LATENCY & TIME-ZERO ALIGNMENT                                  │
│     - Direct sound flight time from speaker to mic introduces 2-10 ms delay. │
│     - Peak-detection on deconvolved impulse aligns $t=0$ accurately.        │
│                                                                             │
│  2. REPEATABILITY & VARIANCE BASELINE (GATE C)                              │
│     - Measure 3 consecutive identical sweeps without changing DSP settings. │
│     - Across $100\text{ Hz} - 10\text{ kHz}$, the baseline standard         │
│       deviation $\sigma_{\text{baseline}}(f)$ must satisfy:                 │
│                 $\sigma_{\text{baseline}} < 0.3\text{ dB}$                  │
│     - If $\sigma > 0.5\text{ dB}$, background noise is excessive; ABORT.    │
│                                                                             │
│  3. REFLECTION GATING WINDOW DISCIPLINE                                     │
│     - Gating window length ($T_{\text{gate}}$) must be chosen based on the  │
│       first floor/ceiling reflection (typically $4 - 6\text{ ms}$).         │
│     - Below $f_{\text{valid}} = 1 / T_{\text{gate}}$ (e.g., $200\text{ Hz}$),│
│       data is marked with `LOW_FREQUENCY_RESOLUTION_LIMIT` diagnostic flag.  │
│                                                                             │
│  4. SIGNAL-TO-NOISE RATIO (SNR) VERIFICATION                                │
│     - Evaluated via `evaluate_measurement_quality()`.                       │
│     - Peak impulse SNR must exceed $\ge 30\text{ dB}$ above pre-impulse     │
│       noise floor.                                                          │
│                                                                             │
│  5. GAIN STAGING & CLIP AVOIDANCE                                           │
│     - Calibrate sweep output level so microphone ADC peak does not exceed   │
│       $-6.0\text{ dBFS}$ (prevents transducer non-linearities and ADC clip).│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Proposed Staged Physical Validation Protocol

Physical validation must proceed in five discrete, verifiable gates. Each gate must pass completely before advancing to the next:

```text
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    GATE A    │     │    GATE B    │     │    GATE C    │     │    GATE D    │     │    GATE E    │
│  Electrical  │ ──> │   Acoustic   │ ──> │ Repeatable   │ ──> │   Bounded    │ ──> │ Re-Measure & │
│     PCM      │     │  Raw Sweep   │     │   Baseline   │     │   DSP Run    │     │ Causal Delta │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

### Gate Breakdown:

1. **Gate A — Electrical / ALSA Playback:**
   - Stream test audio from `AlsaExecutionBackend` to a physical USB DAC connected to a line-level load or monitor.
   - Verify: Clear audio output, clean startup/shutdown, no OS kernel panic, zero buffer underruns during a 5-minute test.
2. **Gate B — Raw Acoustic Measurement & Ingestion:**
   - Position microphone at listening location ($1.0 - 1.5\text{ m}$ on-axis).
   - Play log-sine sweep, record via ALSA capture, deconvolve to impulse response, apply reflection gate and mic calibration.
   - Verify: Gated `FrequencyResponseData` generated automatically with `MeasurementDiagnosticReport.is_valid == True`.
3. **Gate C — Measurement Repeatability Baseline:**
   - Perform 3 consecutive measurements without moving the microphone or altering system volume.
   - Verify: Across $100\text{ Hz} - 10\text{ kHz}$, inter-run standard deviation $\sigma < 0.3\text{ dB}$.
4. **Gate D — Bounded Deterministic Correction:**
   - Run AcoustiForge optimization with a target curve (or apply an intentional single-biquad test filter, e.g., $-4.0\text{ dB}$ notch at $1\text{ kHz}, Q=2.0$).
   - Compile `ComputeGraph` and instantiate `AlsaExecutionBackend` with active DSP.
5. **Gate E — Re-Measurement & Causal Delta Verification:**
   - Re-measure room transfer function through the active `ComputeGraph`.
   - Calculate response delta: $\Delta(f) = M_{\text{post}}(f) - M_{\text{pre}}(f)$.
   - Verify: Measured acoustic change $\Delta(f)$ matches the synthesized filter transfer function $H_{\text{DSP}}(f)$ within $\pm 1.0\text{ dB}$ across the valid band.

---

## 9. Critical Review of Proposed Acceptance Criteria

The commercialization assessment proposed several performance targets. Here they are factually evaluated:

| Criterion | Commercialization Target | Classification | Technical Assessment & Realistic Measurement Method |
| :--- | :--- | :--- | :--- |
| **Playback Duration** | 60 continuous minutes | **GOOD EXPERIMENTAL TARGET** | 5–10 minutes is sufficient for initial Gate A/D validation. 60 minutes is valuable for final long-term soak testing. |
| **Xrun Frequency** | $< 3$ underruns / hour | **GOOD EXPERIMENTAL TARGET** | Highly dependent on Linux kernel preemption (`PREEMPT_RT` vs standard). Measured via `AlsaExecutionBackend.recovered_xruns`. |
| **Compute Latency** | $< 1.0\text{ ms}$ / block (256 samples) | **JUSTIFIED NOW** | Standard real-time constraint. At 48 kHz, 256 samples = 5.33 ms. 1.0 ms leaves $>80\%$ CPU headroom for OS tasks. |
| **Inter-Channel Phase Drift** | Zero physical phase drift | **NEEDS MEASUREMENT DEFINITION** | Requires dual-channel loopback ADC to measure microsecond-level clock jitter. For initial stereo speaker validation, ALSA interleaved frame locking guarantees sample-exact synchronization. |
| **Acoustic Error Reduction** | $\ge 3.0\text{ dB}$ RMS reduction vs target | **PREMATURE / NEEDS DEFINITION** | In real rooms, sharp non-minimum-phase room reflections and modal nulls cannot be inverted with minimum-phase PEQ without extreme ringing. **The initial criterion must be causal tracking of predicted filter delta ($\pm 1.0\text{ dB}$), not an arbitrary universal 3 dB reduction.** |
| **Narrow-Band EQ Boost Limit** | $\le +6.0\text{ dB}$ maximum boost | **JUSTIFIED NOW** | Essential acoustic safety invariant. High-Q boosts stress amplifiers, overheat voice coils, and produce severe audible ringing. |

---

## 10. Output Safety & Protection Requirements

Before connecting AcoustiForge to physical amplifiers and transducers, the following four safety protections must be in place:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          OUTPUT SAFETY FRAMEWORK                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. HARD DIGITAL CEILING (CLIP PROTECTION)                                  │
│     - All output buffers must pass through a strict mathematical clamp:     │
│       $y[n] = \text{clip}(x[n], -1.0, 1.0)$.                                │
│     - Output gain normalization ensures $G_{\text{total}} + \text{PeakBoost}│
│       \le 0.0\text{ dBFS}$.                                                 │
│                                                                             │
│  2. INFRASONIC HIGH-PASS PROTECTION                                         │
│     - Infrasonic Butterworth HPF ($20 - 30\text{ Hz}$, 2nd or 4th order)     │
│       protects woofers from excessive subsonic excursion and DC offsets.    │
│     - Generated via `design_infrasonic_protection_filter()`.                │
│                                                                             │
│  3. MAXIMUM PEQ BOOST CLAMP                                                 │
│     - Optimizer constraint enforcement: No single peaking filter may have   │
│       $\text{gain\_db} > +6.0\text{ dB}$, and cumulative boost across        │
│       adjacent bands must not exceed $+6.0\text{ dB}$.                      │
│                                                                             │
│  4. STARTUP & SHUTDOWN TRANSIENT SUPPRESSION                                │
│     - ALSA streams must be initialized with zeroed buffers.                 │
│     - Fade-in ramp (50 ms cosine window) on stream start avoids pop/click.  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Recommended Next Implementation Unit

Based on repository evidence, the smallest, cleanest next unit of work is:

### **Recommended Choice: Unit B + C — Sweep Generation & ALSA Capture Validation Unit**

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│              RECOMMENDED NEXT UNIT: MEASUREMENT HARNESS CORE                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. `src/acoustiforge/acoustic_math/sweep.py`:                              │
│     - Deterministic Log-Sine Sweep Generator                                │
│     - Analytical Inverse Filter & Farina Deconvolution Engine               │
│     - Unit tests verifying bit-exact impulse recovery (< -90 dBFS residual) │
│                                                                             │
│  2. `src/acoustiforge/execution/alsa.py` Extension:                         │
│     - Add `snd_pcm_readi` binding to `AlsaCtypesBinding`                    │
│     - Add `NativeAlsaCaptureHandle` & `MockAlsaCaptureHandle`               │
│     - Unit tests verifying mock and dynamic capture buffer conversion       │
│                                                                             │
│  3. `tests/test_physical_loop_harness.py`:                                  │
│     - End-to-end integration test validating: Sweep -> Mock ALSA Loopback   │
│       -> Deconvolve -> Gate -> Calibration -> Valid FRD                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Rationale:
- Attempting full physical execution immediately (Option E) without verified sweep generation and capture drivers will fail because the software cannot yet create the excitation or record the microphone.
- Building only playback validation (Option A) leaves the measurement loop unaddressed.
- Implementing **Unit B + C** provides the missing mathematical and capture building blocks in pure Python/ctypes with 100% test coverage before touching real physical hardware.

---

## 12. Explicit Non-Goals for Phase 5-4C

To maintain strict architectural boundaries and avoid scope creep, the following are explicitly declared out of scope for Phase 5-4C:

1. **No Real-Time Full-Duplex Synchronization:** No attempt to lock asynchronous USB DAC and USB microphone clocks in a shared audio thread.
2. **No Graphical User Interface:** No desktop, web, or mobile UI development.
3. **No Cloud Telemetry or Services:** All testing, file I/O, and analytics remain strictly local.
4. **No AI Inference, LLM Integration, or Prompt Contexts:** Pure deterministic acoustic signal processing only.
5. **No Proprietary DSP Hardware (SHARC/FPGA/DSP Chips):** Execution targets standard host CPU via ALSA.
6. **No Room Simulation / Ray Tracing:** Physical reality in the actual room is the ground truth.
7. **No Reopening of Frozen Core Packages:** Zero mutations to `domain/`, `graph/`, `contracts/`, `builders/`, or `extensions/`.

---

## 13. Summary Conclusion

Phase 5-4C Discovery confirms that AcoustiForge is technically ready for physical validation. The missing gap is not a complete rewrite or a large laboratory build, but **a simple, deterministic sweep generator and an ALSA capture binding**.

Once these two small components are in place, the 5-stage validation protocol (Gate A $\to$ Gate E) can be executed on real hardware to provide the first undeniable proof of physical acoustic correction.

---

## 14. Post-Discovery Implementation Status (Phase 5-4C Unit B+C)

> **Status:** COMPLETED IN SOFTWARE (23 Tests Added, 528 Passed, 2 Skipped, 0 Warnings)

Following this discovery document:
1. **Unit B (Deterministic Sweep Generation & Farina Deconvolution):** Implemented in `src/acoustiforge/acoustic_math/sweep.py` (`generate_log_sweep`, `generate_inverse_sweep`, `deconvolve_sweep`, `sweep_to_pcm_block`, WAV export).
2. **Unit C (ALSA Audio Capture Subsystem):** Implemented in `src/acoustiforge/execution/alsa.py` (`snd_pcm_readi` prototype, `AlsaCaptureConfig`, `AlsaAudioCapture` engine supporting float32/int16 and overrun recovery).
3. **Physical-Loop Software Simulation Harness:** Implemented in `tests/test_physical_loop_harness.py` simulating full sequential measurement flow.
4. **Physical Hardware Status:** **PHYSICAL HARDWARE HAS NOT BEEN VALIDATED.** Physical validation remains pending the execution of Gates A–E on real Linux hardware.
5. **Next Step:** **Gate A — Electrical / ALSA Playback Hardware Validation** on physical Linux/ALSA device.

