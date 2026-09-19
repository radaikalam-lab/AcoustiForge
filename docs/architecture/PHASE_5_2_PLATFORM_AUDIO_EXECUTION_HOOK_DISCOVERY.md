# AcoustiForge Phase 5-2 — Platform Audio Execution Hook Discovery & Architecture

> **Document Status:** NORMATIVE ARCHITECTURAL DISCOVERY  
> **Phase:** 5-2 Discovery  
> **Target Subsystem:** Platform Audio Execution Boundary (Track I)  
> **Core Status:** 100% Frozen (Zero Core Mutation)  
> **Verified Baseline:** 448 Passed / 0 Failed / 0 Errors / 0 Warnings (`pytest -q -W error`)  
> **Date:** September 2026

---

## 1. Executive Summary

AcoustiForge has achieved complete mathematical, domain, and DSP execution determinism through Phase 4D and Phase 5-1 Track C. The existing control plane and execution pipeline are defined as:

$$\text{Measurements / Target Curve} \longrightarrow \text{Domain Model} \longrightarrow \text{Complex Forward Model} \longrightarrow \text{Deterministic Optimizer} \longrightarrow \text{OptimizationResult} \longrightarrow \text{Compilation Adapter} \longrightarrow \text{ComputeGraph} \longrightarrow \text{PCM Execution}$$

The purpose of **Phase 5-2** is to define the architecture for a platform-neutral **Platform Audio Execution Hook** (formally designated **Track I**). 

This boundary enables the compiled `ComputeGraph` to process audio streams across:
1. **Windows Desktop** (WASAPI / Audio Graphs)
2. **Linux Desktop** (PipeWire / ALSA / JACK)
3. **Raspberry Pi & Linux SBCs** (ALSA direct / I²S / USB DACs / Headless Appliances)
4. **Android** (AAudio / Oboe / AudioTrack)
5. **iOS / iPadOS** (Core Audio / AVAudioEngine / AUv3)
6. **Future Embedded / Native Systems** (C99 micro-kernels)

### Core Architectural Principle
> **AcoustiForge Core computes what the audio should be. The platform execution adapter determines how that PCM is transported to and from a particular operating system, runtime, or hardware device.**
>
> **Platform-specific audio APIs must NEVER become acoustic-domain or Core dependencies.**

---

## 2. Current PCM & ComputeGraph Architecture

An inspection of the frozen Core reveals the exact execution contract:

### 2.1 Canonical Data Format (`PCMBlock`)
- **Memory Layout:** Planar, C-contiguous NumPy float32 arrays of shape `(channels, frames)`.
- **Validation Invariants:** Validated finite samples, non-negative, non-empty, matching declared channel layout (`AudioMetadata`).
- **Memory Floor:** Strict floating-point floor policies (e.g. $-240\,\text{dB}$ magnitude floor).

### 2.2 Graph Topology & Execution (`ComputeGraph`)
- **Lifecycle:** `BUILDING` $\to$ `VALIDATED` $\to$ `FROZEN`.
- **Schedule:** Static topological sort computed once at graph freeze time.
- **Node Execution:** Sequential processing along pre-computed schedule via `node.process(block)`.
- **Stateful Processing:** Nodes retain internal time-domain filter state (e.g. `BiquadNode` direct-form II transposed states, `DelayNode` ring buffer history).
- **Execution Mode:** Currently synchronous block-by-block execution (`graph.process(input_block)` or `graph.process_stream(iterator)`).

---

## 3. Proposed Platform Audio Execution Hook Boundary

The execution hook is an optional, external abstraction sitting strictly above the frozen Core:

```
+-------------------------------------------------------------------------------+
|                             AcoustiForge Core                                 |
|                                                                               |
|             OptimizationResult  --->  ComputeGraph (FROZEN DAG)              |
|                                       │                                       |
|                                       v                                       |
|                      ComputeGraph.process(PCMBlock)                           |
+---------------------------------------+---------------------------------------+
                                        │
                                        │ (Canonical PCMBlock Stream)
                                        v
+-------------------------------------------------------------------------------+
|               Track I: Platform Audio Execution Hook Interface                |
|                                                                               |
|   ┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────┐   |
|   │ AudioStreamController │   │ AudioRingBufferQueue  │   │ StateGuard    │   |
|   └───────────────────────┘   └───────────────────────┘   └───────────────┘   |
+---------------------------------------+---------------------------------------+
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           │                            │                            │
           v                            v                            v
┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│  Track I-A: Windows  │    │ Track I-B/C: Linux   │    │ Track I-D/E: Mobile  │
│                      │    │ (Desktop & RPi SBC)  │    │ (Android & iOS)      │
│  - WASAPI Exclusive  │    │  - ALSA Direct / I2S │    │  - AAudio / Oboe     │
│  - WASAPI Shared     │    │  - PipeWire / JACK   │    │  - Core Audio        │
└──────────┬───────────┘    └──────────┬───────────┘    └──────────┬───────────┘
           │                           │                           │
           └───────────────────────────┼───────────────────────────┘
                                       v
                             PCM Hardware Endpoint
                         (DAC / I2S / USB / Headphones)
```

---

## 4. Platform Matrix

| Platform | Sub-Track | Candidate Mechanism | Audio Input | Audio Output | Realtime & Buffer Considerations | Role / Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Windows** | `Track I-A` | WASAPI (Exclusive/Shared) | Loopback / Mic / File | USB DAC / Headphones | MMDevice API, pro-audio timer, low jitter | Discovery |
| **Linux Desktop** | `Track I-B` | PipeWire / ALSA / JACK | PipeWire Sink / ALSA | ALSA PCM / PipeWire | RTKit scheduling, zero-copy ringbuffers | Discovery |
| **Raspberry Pi & SBC** | `Track I-C` | ALSA Direct / I²S / USB | Line-In / Network stream | I²S DAC / USB DAC / Amp | CPU thermals, small RAM, headless daemon | Discovery |
| **Android** | `Track I-D` | AAudio / Oboe / AudioTrack | Mic / In-app PCM | USB-C DAC / Headphone jack | Android audio flinger, power management | Discovery |
| **iOS / iPadOS** | `Track I-E` | Core Audio / AVAudioEngine / AUv3 | AudioUnit input | Headphone / USB DAC | Realtime audio render thread constraints | Discovery |
| **Embedded / C99** | `Track I-F` | Native C99 execution kernel | ADC / I²S DMA | DAC / I²S DMA | Zero dynamic allocation, deterministic cycles | Future |

---

## 5. Linux & Raspberry Pi / SBC Architecture

### 5.1 First-Class Principle: Raspberry Pi is Linux
> **Raspberry Pi is a consumer of the generic Linux execution architecture, not a separate or special Core engine.**

The hardware/software hierarchy for Linux and Single-Board Computers is:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. AcoustiForge Core: ComputeGraph (Python/C99 Kernel)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. Platform Execution Adapter: Linux Audio Engine (ALSA / PipeWire / JACK)  │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. Platform OS & Runtime: Linux Kernel (Standard or RT-PREEMPT)             │
├─────────────────────────────────────────────────────────────────────────────┤
│ 4. Hardware Driver & SoC: Raspberry Pi 4/5, Orange Pi, Rockchip, x86 MiniPC │
├─────────────────────────────────────────────────────────────────────────────┤
│ 5. Physical Audio Interface: I²S Hat (PCM5122, TAS5825M), USB DAC, SPDIF   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 SBC Hardware Integration Profiles
1. **I²S Master DAC Hats:** Direct memory-mapped DMA via ALSA hardware devices (`hw:0,0`), bypassing all software mixing for absolute minimal latency and jitter.
2. **Asynchronous USB Audio Class 2.0 (UAC2):** Hardware-clocked playback with decoupled host timing.
3. **Multi-Channel Active Crossover Amplifiers:** 4-channel to 8-channel DAC routing for direct per-driver amplification.

---

## 6. Headphone Topology & Use Case

A critical distinction must be maintained between **Calibration** and **Execution**:

### 6.1 Headphone Calibration (Acoustic Domain Plane)
```text
Raw Measurement (GRAS/MiniDSP/IEC711)
               ↓
     FrequencyResponseData
               ↓
   Target Curve (Harman / Free-Field)
               ↓
   Multi-Way / EQ Optimization
               ↓
    Compiled ComputeGraph
```

### 6.2 Headphone Realtime Execution (Data Plane)
```text
System Audio / Music Player
               ↓
   Platform Audio Capture Hook
               ↓
      Float32 PCM Block
               ↓
  AcoustiForge ComputeGraph (EQ / Crossfeed / Limiter)
               ↓
       Processed PCM Block
               ↓
        DAC / Headphones
```

The execution hook operates exclusively on the Data Plane.

---

## 7. Network / Appliance Architecture (Headless SBC Mode)

The execution hook naturally enables standalone **AcoustiForge Audio Appliance Mode**:

```text
Source Device (PC / Phone / Tablet)
               │  [Wi-Fi / Ethernet]
               │  (UPnP / AirPlay / Roon RAAT / Snapcast / TCP Stream)
               v
┌─────────────────────────────────────────────────────────────────────────────┐
│ Raspberry Pi / Linux SBC Headless Audio Appliance                           │
│                                                                             │
│   Network Receiver Daemon (Outside Core)                                    │
│         │ (Decodes PCM)                                                     │
│         v                                                                   │
│   AcoustiForge Execution Hook                                               │
│         │ (Passes PCMBlock)                                                 │
│         v                                                                   │
│   AcoustiForge ComputeGraph (Active Crossover / Room EQ / Time Alignment)   │
│         │ (Multi-channel output)                                            │
│         v                                                                   │
│   ALSA I²S / Multi-Channel DAC (e.g. 4-Ch / 8-Ch HAT)                       │
└─────────────────────────────────────────────────────────────────────────────┘
               │
               v
 Multi-Channel Amplifier ---> Active Multi-Way Loudspeakers
```

**Architectural Rule:** Network protocols, transport sockets, and streaming daemons belong entirely in user-space wrapper services outside AcoustiForge Core.

---

## 8. Realtime Execution Requirements & Contract

Realtime audio rendering imposes strict constraints on thread safety and deterministic timing:

### 8.1 Realtime Audio Render Thread Rules
1. **Zero Heap Allocation:** No dynamic memory allocation (`malloc`, `new`, Python object creation) during the high-priority render callback.
2. **Zero Blocking / Synchronization:** No mutexes, condition variables, disk I/O, network socket access, or system calls in the audio thread.
3. **Lock-Free Ring Buffers:** Communication between user control planes (e.g., UI, parameter updates) and the audio render callback must use Single-Producer Single-Consumer (SPSC) lock-free ring buffers.

### 8.2 Parameter Update Semantics
- **Atomic State Swap:** When new optimizer parameters or graph states are applied, the graph swaps pointer structures or coefficient tables atomically at block boundaries.
- **Zipper Noise Prevention:** Filter coefficient updates must be smoothed or stepped at zero-crossings to eliminate audible clicks.

### 8.3 Underrun / Overrun Isolation
- Buffer underruns (xruns) must be logged and handled by emitting silence blocks rather than throwing exceptions or crashing the DSP graph.

---

## 9. Determinism Boundary

| Domain | Guarantee | Conditions & Scope |
| :--- | :--- | :--- |
| **Core Acoustic Math** | Bit-exact reproducible | Deterministic coordinate descent, golden line search, IEEE 754 float arithmetic |
| **Graph Construction** | Structurally identical | Frozen topological sort, deterministic node sequencing |
| **Offline PCM Processing** | Bit-exact reproducible | Identical input `PCMBlock` yields identical output `PCMBlock` |
| **Realtime Platform I/O** | Deterministic processing | Subject to platform OS timer jitter, DMA scheduling, and DAC hardware clocks |

---

## 10. Failure Isolation

Platform execution failures must be strictly isolated to the platform adapter layer:

```text
[Platform Audio Failure (e.g. DAC Disconnect / ALSA xrun / WASAPI Device Invalidate)]
                                    │
                                    v
            ┌───────────────────────────────────────────────┐
            │       Execution Hook Adapter Boundary         │
            │   - Catches platform device exceptions        │
            │   - Releases hardware handles cleanly         │
            │   - Flushes ring buffers to silence           │
            │   - Enters safe IDLE state                    │
            └───────────────────────┬───────────────────────┘
                                    │
                         (Core Remains Pristine)
                                    v
            ┌───────────────────────────────────────────────┐
            │              AcoustiForge Core                │
            │   - ComputeGraph state unharmed               │
            │   - Optimization results preserved            │
            │   - Ready for next playback session           │
            └───────────────────────────────────────────────┘
```

---

## 11. Track Classification: Sub-Track Proposal

To prevent monolithic cross-platform coupling, **Track I** is structured into independent, unblocked sub-tracks:

```text
Track I: Platform Audio Execution Hook
├── Track I-A: Windows WASAPI Execution Hook
├── Track I-B: Linux Desktop (PipeWire / ALSA) Hook
├── Track I-C: Raspberry Pi / Linux SBC Appliance Hook
├── Track I-D: Android (AAudio / Oboe) Hook
├── Track I-E: iOS / iPadOS (Core Audio / AUv3) Hook
└── Track I-F: Embedded / Bare-metal C99 Execution Kernel
```

### Decoupling Guarantee
- `Track I-C` (Raspberry Pi) can proceed without waiting for `Track I-A` (Windows) or `Track I-D` (Android).
- Mobile tracks do not block desktop or SBC tracks.

---

## 12. Core Mutation & Dependency Gate

### 12.1 Core Modification Required: **NO**
- The frozen Core contracts (`ComputeGraph`, `PCMBlock`, `AudioMetadata`, `OptimizationResult`, `compile_optimization_result_to_graph`) already supply all required interfaces for block-based audio execution.
- Zero modifications to `src/acoustiforge/domain/`, `acoustic_math/`, `graph/`, `contracts/`, or `builders/` are required.

### 12.2 New Dependencies Added: **NO**
- This phase introduces **zero** external libraries or dependencies.
- The repository remains 100% pure standard library + NumPy.

---

## 13. Security, Sandbox & Permission Considerations

| Platform | Sandbox / Permission Requirement | Adapter Design Recommendation |
| :--- | :--- | :--- |
| **Windows** | Exclusive mode privileges | Fallback automatically to WASAPI Shared mode if Exclusive is disallowed. |
| **Linux / RPi** | `audio` group membership, RTKit / `ulimit -r` | Run appliance daemon under dedicated `acoustiforge` system user with `rtprio 95`. |
| **Android** | `RECORD_AUDIO` (if input), background service wake-lock | Run via Android Foreground Service with continuous media notification. |
| **iOS** | Background Audio capability, Audio Unit entitlements | Integrate as an `AUv3` Audio Unit Extension or AVAudioEngine node. |

---

## 14. Open Questions & Future Investigations

1. **Native C Execution Acceleration:**
   - *Question:* Should high-sample-rate (192 kHz / 8-channel) SBC execution use a compiled C shared library for the inner biquad loop while retaining Python for graph management?
   - *Finding:* Yes, an optional C dynamic library (`.so` / `.dll`) could provide a drop-in C-accelerated `ComputeGraph.process` without modifying Core contracts.
2. **Dynamic Latency Reporting:**
   - *Question:* How should platform-reported hardware buffer latency be propagated to client software for video lip-sync alignment?
   - *Finding:* The execution hook controller should expose `total_latency_seconds = graph_algorithmic_latency + platform_buffer_latency`.

---

## 15. Recommended Next Implementation Candidate

Following the completion of Phase 5-2 discovery:
- **Recommended Candidate:** **Track I-C / I-B: Linux & Raspberry Pi Execution Hook Interface**.
- **Rationale:** 
  1. Linux audio (ALSA / PipeWire) provides open, accessible, standard POSIX APIs without proprietary SDK requirements.
  2. Raspberry Pi and Linux SBCs directly fulfill the high-value physical appliance model for active multi-way DSP crossovers and room EQ.
  3. Provides a clean foundation that naturally extends to Windows (`Track I-A`) and Mobile (`Track I-D`/`I-E`).

---

## 16. Explicit Non-Goals

During this discovery phase, the following were explicitly **OUT OF SCOPE** and remain strictly unimplemented:
- No Windows WASAPI code written.
- No ALSA / PipeWire / JACK code written.
- No Raspberry Pi system daemon created.
- No Android or iOS applications built.
- No external audio dependencies installed.
- Track C remains untouched and frozen.
- Core remains untouched and frozen.
