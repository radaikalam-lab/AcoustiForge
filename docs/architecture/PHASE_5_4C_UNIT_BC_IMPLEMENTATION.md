# AcoustiForge Phase 5-4C — Unit B + C Implementation Report

> **Document Type:** Implementation & Verification Report  
> **Status:** NORMATIVE ARCHITECTURAL EXTENSION  
> **Repository:** `E:\AcoustiForge`  
> **Subsystems:** Deterministic Sweep Generation, Farina Deconvolution & Linux ALSA Audio Capture  
> **Core Status:** 100% Frozen (Zero Core, Track C, Intent, or Experience Mutation)  
> **Verified Regression Baseline:** 505 Passed $\to$ **528 Passed, 2 Skipped** (23 New Tests, 0 Failed, 0 Warnings under `pytest -q -W error`)  
> **Date:** September 2026  

---

## 1. Executive Summary & Notice

Phase 5-4C implements **Unit B (Deterministic Sweep Generation & Farina Deconvolution)** and **Unit C (Linux ALSA Audio Capture Adapter)**. These two components supply the missing excitation and recording capabilities needed to construct a complete, repeatable acoustic measurement harness.

> [!IMPORTANT]
> **Physical Validation Notice:**  
> Passing this test suite validates the **software measurement harness and analytical pipeline**, **NOT** physical acoustic correctness in a real room. Physical hardware playback (DAC $\to$ Amp $\to$ Speaker) and physical microphone capture remain pending the physical hardware gates (Gates A–E).

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                 PHASE 5-4C MEASUREMENT PIPELINE ARCHITECTURE                │
└─────────────────────────────────────────────────────────────────────────────┘

  [1. LogSweepSpecification] ──> generate_log_sweep() ──> [Deterministic Sweep]
                                                                  │
                                      ┌───────────────────────────┤
                                      ▼                           ▼
                           generate_inverse_sweep()     [AlsaExecutionBackend]
                            (Farina Inverse Filter)     (Playback to Speaker)
                                      │                           │
                                      │                   (Acoustic Path)
                                      │                           │
                                      │                 [AlsaAudioCapture]
                                      │                 (Microphone Input)
                                      │                           │
                                      ▼                           ▼
                                deconvolve_sweep() <────── [Recorded PCMBlock]
                                      │
                                      ▼
                           [ImpulseResponseData]
                                      │
                                      ▼
                             apply_reflection_gate()
                                      │
                                      ▼
                        transform_impulse_to_frequency_response()
                                      │
                                      ▼
                           apply_microphone_calibration()
                                      │
                                      ▼
                            [FrequencyResponseData]
```

---

## 2. Unit B: Sweep Generator & Deconvolution Engine

Module: `src/acoustiforge/acoustic_math/sweep.py`

### 2.1 API Specification

```python
@dataclass(frozen=True, slots=True)
class LogSweepSpecification:
    f_start: float = 20.0
    f_end: float = 20000.0
    duration_seconds: float = 5.0
    sample_rate: int = 48000
    amplitude: float = 0.5  # ~-6.0 dBFS
    fade_in_seconds: float = 0.05
    fade_out_seconds: float = 0.05
    channels: int = 1

def generate_log_sweep(spec: LogSweepSpecification) -> np.ndarray: ...
def generate_inverse_sweep(spec: LogSweepSpecification) -> np.ndarray: ...
def deconvolve_sweep(
    recorded_signal: np.ndarray,
    inverse_sweep: np.ndarray,
    n_fft: Optional[int] = None,
) -> np.ndarray: ...
def sweep_to_pcm_block(sweep: np.ndarray, sample_rate: int, channels: int = 1) -> PCMBlock: ...
def export_sweep_to_wav_bytes(sweep: np.ndarray, sample_rate: int, bits_per_sample: int = 16) -> bytes: ...
def export_sweep_to_wav_file(sweep: np.ndarray, sample_rate: int, file_path: Union[str, Path], bits_per_sample: int = 16) -> Path: ...
```

### 2.2 Signal & Deconvolution Conventions

1. **Logarithmic Sweep Formula:**
   $$L = \ln(f_{\text{end}} / f_{\text{start}})$$
   $$\phi(t) = \frac{2 \pi f_{\text{start}} T}{L} \cdot \left( \exp\left( \frac{t \cdot L}{T} \right) - 1 \right)$$
   $$x(t) = A \cdot \sin(\phi(t))$$
2. **Farina Inverse Filter:**
   The inverse filter is constructed by time-reversing $x(t)$ and modulating with an amplitude envelope decaying at $-6\text{ dB/octave}$ ($\exp(-t \cdot L / T)$).
3. **Normalization:**
   The inverse filter is normalized such that linear deconvolution of a unity loopback signal produces an impulse with exact peak amplitude $1.0$ at index $N_{\text{sweep}} - 1$.
4. **Time Alignment:**
   For a system with latency $D$ samples, the impulse peak appears at $(N_{\text{sweep}} - 1) + D$.

---

## 3. Unit C: ALSA Audio Capture Subsystem

Module: `src/acoustiforge/execution/alsa.py`

### 3.1 Ctypes Binding Extension
Added `snd_pcm_readi` prototype to `AlsaCtypesBinding`:
```python
# snd_pcm_readi(snd_pcm_t *pcm, void *buffer, snd_pcm_uframes_t size) -> c_long
cls._lib.snd_pcm_readi.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
cls._lib.snd_pcm_readi.restype = ctypes.c_long
```

### 3.2 Capture Configuration & Engine

```python
@dataclass(frozen=True, slots=True)
class AlsaCaptureConfig:
    alsa_device: str = "default"
    sample_rate: int = 48000
    channels: int = 1
    block_size: int = 256
    use_int16: bool = False  # False = float32, True = int16

class AlsaAudioCapture:
    def __init__(self, config: AlsaCaptureConfig, mock_handle: Optional[IAlsaDeviceHandle] = None, auto_recover_xruns: bool = True): ...
    def start(self) -> None: ...
    def read_block(self) -> PCMBlock: ...
    def record_frames(self, total_frames: int) -> PCMBlock: ...
    def record_duration(self, duration_seconds: float) -> PCMBlock: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...
```

### 3.3 Format & Overrun Handling
- Supports both **32-bit float** and **16-bit signed integer** hardware capture.
- Planar format conversion using `AlsaPCMAdapter.interleaved_float32_to_planar_pcm_block` and `AlsaPCMAdapter.interleaved_int16_to_planar_pcm_block`.
- Automatic `-EPIPE` / `-ESTRPIPE` overrun detection with `snd_pcm_recover` resumption and read retry.

---

## 4. Test Suite & Verification Matrix

| Test Suite | Test Count | Scope |
| :--- | :--- | :--- |
| `tests/test_sweep_and_deconvolution.py` | 14 | Parameter validation, Nyquist bounds, determinism, ideal loopback, known gain/delay, FIR channel deconvolution, WAV export roundtrip (16/24/32-bit). |
| `tests/test_alsa_capture.py` | 8 | Configuration validation, float32 and int16 block reading, multi-block recording, overrun recovery, fatal error handling, lifecycle state machine. |
| `tests/test_physical_loop_harness.py` | 1 | End-to-end simulation: Sweep $\to$ Synthetic Room $\to$ ALSA Capture $\to$ Deconvolution $\to$ IR Slicing $\to$ Gating $\to$ Mic Calibration $\to$ Quality Diagnostics $\to$ Valid `FrequencyResponseData`. |
| **Total New Tests** | **23** | **100% Passing under `pytest -q -W error`** |

---

## 5. Frozen Boundary Compliance

| Package | Status | Changes Made |
| :--- | :--- | :--- |
| `src/acoustiforge/domain/` | FROZEN | 0 |
| `src/acoustiforge/graph/` | FROZEN | 0 |
| `src/acoustiforge/contracts/` | FROZEN | 0 |
| `src/acoustiforge/builders/` | FROZEN | 0 |
| `src/acoustiforge/extensions/` | FROZEN | 0 |
| `src/acoustiforge/intent/` | FROZEN | 0 |
| `src/acoustiforge/experience/` | FROZEN | 0 |
| `src/acoustiforge/acoustic_math/` | EXTENDED | New `sweep.py` module + exports in `__init__.py` |
| `src/acoustiforge/execution/` | EXTENDED | `AlsaAudioCapture` & `AlsaCaptureConfig` added in `alsa.py` |
| **Third-Party Dependencies** | **ZERO** | Pure Python stdlib + NumPy + ctypes |

---

## 6. Next Step: Hardware Validation Gate (Gate A)

With Unit B and Unit C complete in software, the remaining path is physical execution on a Linux test rig:

1. **Gate A:** Electrical / ALSA Playback (verify `AlsaExecutionBackend` on physical USB DAC).
2. **Gate B:** Raw Acoustic Measurement (play log sweep $\to$ record with USB microphone via `AlsaAudioCapture`).
3. **Gate C:** Baseline Repeatability ($\sigma < 0.3\text{ dB}$).
4. **Gate D:** Bounded DSP Correction.
5. **Gate E:** Re-Measurement & Causal Delta Verification.
