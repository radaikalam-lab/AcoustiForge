# AcoustiForge Canonical PCM Contract — Phase 0

**Status:** NORMATIVE  
**Phase:** Phase 0 — Canonical PCM Contract and Pass-Through  
**Governing Authority:** `prompts/MASTER_PROMPT.md`

---

## 1. Scope and Purpose

This document normatively defines the canonical in-memory Pulse Code Modulation (PCM) representation for the **Acoustic Compute Engine (ACE)** in AcoustiForge.

The PCM contract defines the computational boundary between source decoders/transports, digital signal processing nodes, and downstream audio interfaces.

> [!NOTE]
> **Phase 0.1 Amendment:** The PCM Semantic Contract is runtime-neutral. Python dataclasses and NumPy arrays are the reference implementation choice, decoupled from future embedded C/C++, MicroPython, or static DMA memory storage models (see `docs/contracts/RUNTIME_ARCHITECTURE_AMENDMENT_0_1.md`).

---

## 2. Terminology and Domain Definitions

```
Stream:   [ Block 0 ] ──> [ Block 1 ] ──> [ Block 2 ] ──> ...
             │
             └── Block N: Shape (C, F) in contiguous float32 memory
                    │
                    ├── Frame M: Samples across all channels at sampling instant t_M
                    │      ├── Channel 0 (Left):  Sample[0, M]  (float32 scalar)
                    │      └── Channel 1 (Right): Sample[1, M]  (float32 scalar)
```

1. **Sample:** A dimensionless single-precision floating-point scalar (`float32`) representing normalized discrete-time amplitude for one channel at one sampling instant.
2. **Channel:** An independent, isolated monophonic signal line.
3. **Frame:** An aligned temporal slice consisting of exactly one sample for every active channel at the same sampling instant. In a $C$-channel system, 1 frame comprises $C$ samples.
4. **Block:** A contiguous collection of $F$ consecutive frames ($F \ge 1$) scheduled and processed as a single atomic unit.
5. **Stream:** An ordered sequence of contiguous blocks sharing identical sample rate and channel count.
6. **Serialized Audio Representation:** An external storage or transport format (e.g. 16-bit integer interleaved PCM in a WAV container) distinct from the in-memory computational format.

---

## 3. Normative Technical Specification

### 3.1 Numerical Format
- **Data Type (`dtype`):** IEEE 754 single-precision floating-point (`float32`).
- **Nominal Amplitude Range:** $[-1.0, +1.0]$, corresponding to $0\,\text{dBFS}$.
- **Headroom Policy:** Intermediate computations may exceed $|x| > 1.0$ (floating-point headroom) without internal clipping.
- **Finite Value Invariant:** Samples MUST be finite. Values of `NaN`, `+Inf`, and `-Inf` are strictly forbidden and MUST trigger immediate deterministic rejection.

### 3.2 Tensor Layout and Dimensionality
- **Dimensionality:** Exactly 2 dimensions.
- **Shape:** `(channels, frames)`
  - Dimension 0: Channel count ($C$).
  - Dimension 1: Frame count ($F$).
- **Memory Layout:** Planar (non-interleaved), C-contiguous (`Row-major`).
  - Channel 0 buffer is at memory offset $0$.
  - Channel 1 buffer begins at memory offset $F \times \text{sizeof}(\text{float32})$.

### 3.3 Channel Configuration
- **Phase 0 Supported Counts:**
  - Mono: $C = 1$
  - Stereo: $C = 2$
- **Channel Ordering:**
  - Mono ($C = 1$): Index 0 = Mono (`M`).
  - Stereo ($C = 2$): Index 0 = Left (`L`), Index 1 = Right (`R`).
- **Scope Policy:** Channel count $C \le 0$ or non-integer is malformed. Channel count $C > 2$ is rejected by the Phase 0 validation gate.

### 3.4 Sample Rate Policy
- **Type:** Positive non-zero integer (`int > 0`).
- **Standard Supported Rates:** $44100\,\text{Hz}$, $48000\,\text{Hz}$, $88200\,\text{Hz}$, $96000\,\text{Hz}$ (any positive integer clock rate is valid).
- **Pipeline Homogeneity:** Connected processing nodes must operate at matching sample rates.

### 3.5 Block Size Policy
- **Frame Count ($F$):** Integer $F \ge 1$.
- **Dynamic Sizing:** Block size is dynamic per block call. The contract does not impose fixed or power-of-two constraints on data blocks.

---

## 4. Metadata Contract

Every `PCMBlock` carries an associated `AudioMetadata` record:

| Attribute | Type | Constraints | Description |
|---|---|---|---|
| `sample_rate` | `int` | $> 0$ | Clock frequency in Hertz. |
| `channels` | `int` | $1$ or $2$ (Phase 0) | Number of audio channels. |

---

## 5. Invariant Validation Matrix

| Rule ID | Anomaly Condition | Required Error Class | Behavior |
|---|---|---|---|
| `VAL-01` | `sample_rate <= 0` or non-integer | `InvalidSampleRateError` | Reject configuration immediately |
| `VAL-02` | `channels <= 0` or `channels > 2` | `InvalidChannelCountError` | Reject configuration immediately |
| `VAL-03` | `dtype != float32` | `InvalidSampleFormatError` | Reject buffer immediately |
| `VAL-04` | `frames < 1` (empty buffer) | `InvalidBlockSizeError` | Reject buffer immediately |
| `VAL-05` | Tensor `ndim != 2` | `MalformedBufferError` | Reject buffer immediately |
| `VAL-06` | Tensor `shape[0] != metadata.channels` | `ChannelMismatchError` | Reject buffer immediately |
| `VAL-07` | Buffer `flags.c_contiguous == False` | `NonContiguousBufferError` | Reject buffer immediately |
| `VAL-08` | Buffer contains `NaN` | `NonFiniteValueError` | Reject buffer immediately |
| `VAL-09` | Buffer contains `+Inf` or `-Inf` | `NonFiniteValueError` | Reject buffer immediately |
| `VAL-10` | Node rate/channel mismatch | `IncompatibleNodeError` | Reject pipeline link immediately |

---

## 6. Pass-Through Processing Contract

A pass-through processing node (`PassThroughNode`) represents the canonical identity transformation:

1. **Input:** Canonical `PCMBlock` of shape $(C, F)$.
2. **Output:** Canonical `PCMBlock` of shape $(C, F)$.
3. **Bit-Exact Sample Invariant:**  
   $$\forall c \in [0, C-1], \forall f \in [0, F-1]: \text{Output}[c, f] \equiv \text{Input}[c, f]$$
4. **Metadata Preservation:** Output metadata is identical to input metadata.
5. **Latency:** Exactly $0$ frames added delay.
6. **Statelessness:** No state accumulation; `reset()` is a deterministic no-op.
7. **Zero Transformation:** Gain = $0.0\,\text{dB}$, Phase shift = $0^\circ$, Delay = $0$, Resampling = None, Channel mixing = None.
