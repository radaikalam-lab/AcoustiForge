# AcoustiForge Phase 5-3 — Linux/SBC Execution Hook Implementation Report

> **Document Status:** NORMATIVE ARCHITECTURAL IMPLEMENTATION  
> **Phase:** 5-3 Implementation & Verification  
> **Subsystem:** Platform Audio Execution Boundary (Track I-B / I-C)  
> **Core Status:** 100% Frozen (Zero Core Mutation)  
> **Track C Status:** 100% Frozen (Zero Track C Mutation)  
> **Verified Baseline:** 448 Passed $\to$ **461 Passed** (13 New Tests, 0 Failed, 0 Warnings)  
> **Date:** September 2026

---

## 1. Executive Summary

Phase 5-3 establishes the platform-neutral **Linux / Single-Board Computer (SBC) Execution Hook Interface** for AcoustiForge. This module resides entirely in the new external execution package (`src/acoustiforge/execution/`) and consumes the frozen Phase 4 Core `ComputeGraph` and `PCMBlock` contracts with **zero Core mutation**.

```
+-------------------------------------------------------------------------------+
|                       AcoustiForge Core (100% FROZEN)                         |
|                                                                               |
|             OptimizationResult  --->  ComputeGraph (FROZEN DAG)              |
|                                       │                                       |
|                                       v                                       |
|                      ComputeGraph.process(PCMBlock)                           |
+---------------------------------------+---------------------------------------+
                                        │
                                        │ (Canonical PCMBlock Streams)
                                        v
+-------------------------------------------------------------------------------+
|                  Phase 5-3: Audio Execution Hook Boundary                     |
|                                                                               |
|   ┌───────────────────────────┐           ┌───────────────────────────────┐   |
|   │ AudioExecutionController  │ <-------> │     AudioExecutionBackend     │   |
|   │ (Context & Stream Engine) │           │      (Abstract Interface)     │   |
|   └───────────────────────────┘           └───────────────┬───────────────┘   |
+-----------------------------------------------------------│-------------------+
                                                            │
                            ┌───────────────────────────────┴───────────────┐
                            │                                               │
                            v                                               v
            ┌───────────────────────────────┐               ┌───────────────────────────────┐
            │    OfflineExecutionBackend    │               │     LinuxExecutionBackend     │
            │   (Deterministic Reference)   │               │   (SBC / Linux Hook Adapter)  │
            └───────────────────────────────┘               └───────────────────────────────┘
```

---

## 2. Implementation vs. Discovery vs. Deferred Scope

| Capability Area | Status | Description / Scope |
| :--- | :--- | :--- |
| **Execution Interface & Lifecycle** | **IMPLEMENTED** | `AudioExecutionBackend`, `AudioExecutionController`, `ExecutionState`, `StreamConfig` |
| **Offline Reference Backend** | **IMPLEMENTED** | `OfflineExecutionBackend` for deterministic, zero-dependency `PCMBlock` graph execution |
| **Linux / SBC Adapter Interface** | **IMPLEMENTED** | `LinuxExecutionBackend`, `LinuxStreamConfig` defining hardware parameters and ALSA/buffer hooks |
| **Linux ALSA Hardware Driver** | **DEFERRED (5-4)** | Direct C/ALSA API bindings, `snd_pcm_mmap`, kernel buffer scheduling |
| **PipeWire / JACK Drivers** | **DEFERRED** | Native PipeWire audio sinks, JACK pro-audio daemon connections |
| **Windows WASAPI Backend** | **DEFERRED (I-A)** | Windows exclusive/shared MMDevice integration |
| **Mobile Backends (Android / iOS)** | **DEFERRED (I-D/E)** | AAudio / Oboe / Core Audio implementations |
| **Embedded C99 Kernel** | **DEFERRED (I-F)** | Bare-metal standalone micro-engine |

---

## 3. Module Structure & Contracts

### 3.1 Package Hierarchy
```text
src/acoustiforge/execution/
├── __init__.py
├── interface.py
├── offline.py
└── linux.py

tests/
└── test_execution_interface.py
```

### 3.2 Key Value Objects & Classes

1. **`ExecutionState` (Enum):**
   - `UNINITIALIZED`: Instantiated, no graph or stream configuration bound.
   - `CONFIGURED`: Bound to frozen `ComputeGraph` and valid `StreamConfig`.
   - `RUNNING`: Active and accepting `process()` calls.
   - `STOPPED`: Paused, retaining DSP internal filter and delay states.
   - `CLOSED`: Fully terminated, internal references cleared.

2. **`StreamConfig` (`@dataclass(frozen=True, slots=True)`):**
   - `sample_rate: int`: Discrete sample frequency in Hz (validated $> 0$).
   - `channels: int`: Active channels count (validated $> 0$).
   - `block_size: int = 512`: Quantum frames per execution block ($> 0$).
   - `sample_format: str = "float32"`: Canonical floating-point representation.
   - `stream_name: str = "AcoustiForgeStream"`: Non-empty diagnostic label.
   - Property `metadata -> AudioMetadata`: Seamless interoperability with Core `PCMBlock`.

3. **`LinuxStreamConfig(StreamConfig)` (`@dataclass(frozen=True, slots=True)`):**
   - `alsa_device: str = "default"`: ALSA device string (e.g. `'hw:0,0'`, `'plughw:CARD=DAC,DEV=0'`).
   - `periods_per_buffer: int = 4`: Hardware ring buffer period subdivision ($\ge 2$).
   - `is_headless_appliance: bool = False`: Flag indicating standalone SBC appliance daemon mode.
   - Property `total_buffer_frames -> int`: Total hardware ring buffer capacity (`block_size * periods_per_buffer`).

4. **`AudioExecutionBackend` (Abstract Base Class):**
   - Defines strict lifecycle methods: `initialize()`, `start()`, `process()`, `stop()`, `close()`.
   - Enforces state machine transitions and rejects out-of-order execution calls.

5. **`OfflineExecutionBackend(AudioExecutionBackend)`:**
   - Concrete in-memory backend executing `PCMBlock` streams against frozen `ComputeGraph`.
   - Validates that the graph is in `GraphLifecycle.FROZEN` state.
   - Verifies incoming `PCMBlock` sample rates and channel counts against configuration.
   - Preserves stateful DSP filter memory across sequential blocks.

6. **`LinuxExecutionBackend(AudioExecutionBackend)`:**
   - Platform-neutral adapter contract for Linux desktop and Raspberry Pi / ARM SBCs.
   - Manages ALSA device strings, period calculations, and xrun accounting without native binary dependencies.

7. **`AudioExecutionController`:**
   - Higher-level execution manager supporting Python context management (`with controller:`), stream generators (`process_stream(iterable)`), and safe batching.

---

## 4. Raspberry Pi & Linux SBC Relationship

> **Raspberry Pi is a direct consumer of the Linux execution architecture, not a specialized or separate Core engine.**

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ AcoustiForge Core: ComputeGraph (Frozen DSP Engine)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ Execution Hook: LinuxExecutionBackend / OfflineExecutionBackend             │
├─────────────────────────────────────────────────────────────────────────────┤
│ Platform Target: Raspberry Pi 4/5, Orange Pi, Rockchip, x86 Linux Mini-PC   │
├─────────────────────────────────────────────────────────────────────────────┤
│ Hardware Interface: I²S DAC Hat (PCM5122, TAS5825M), USB Audio Class 2.0   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. DSP Continuity & Invariant Verification

1. **Bit-Exact DSP Parity:**
   - Executing a `PCMBlock` through `AudioExecutionController(OfflineExecutionBackend())` yields output bit-exact identical to direct `ComputeGraph.process(block)`.
2. **Statefulness Across Sequential Blocks:**
   - Sequential processing across multiple blocks preserves time-domain filter memory (Direct-Form II transposed states in biquads, ring buffer history in delay nodes).
3. **Multi-Channel & Multi-Way Routing:**
   - Multi-way active crossover graphs (with multiple declared outputs: `woofer.output`, `tweeter.output`) process multi-port blocks with complete channel and frame preservation.
4. **100-Run Determinism:**
   - 100 consecutive executions under identical input and configuration yield 100% bit-exact outputs.

---

## 6. Failure Isolation & Validation Matrix

| Test Scenario | Trigger | Expected Exception | Result |
| :--- | :--- | :--- | :--- |
| Start uninitialized backend | `backend.start()` before `initialize()` | `ExecutionStateError` | **PASS** |
| Process when not running | `backend.process()` in `CONFIGURED`/`STOPPED` | `ExecutionStateError` | **PASS** |
| Re-initialize when running | `backend.initialize()` in `RUNNING` | `ExecutionStateError` | **PASS** |
| Operations on closed backend | `start()`/`stop()`/`process()` in `CLOSED` | `ExecutionStateError` | **PASS** |
| Bind unfrozen graph | `ComputeGraph.lifecycle != FROZEN` | `InvalidGraphError` | **PASS** |
| Mismatched block sample rate | `block.sample_rate != config.sample_rate` | `MalformedBufferError` | **PASS** |
| Mismatched block channels | `block.channels != config.channels` | `MalformedBufferError` | **PASS** |
| Invalid sample rate | `sample_rate <= 0` | `InvalidSampleRateError` | **PASS** |
| Invalid channels / block size | `channels <= 0` or `block_size <= 0` | `ExecutionConfigError` | **PASS** |
| Invalid ALSA periods | `periods_per_buffer < 2` | `ExecutionConfigError` | **PASS** |

---

## 7. Rollback & Removal Strategy

The entire execution subsystem is completely isolated:
```text
src/acoustiforge/execution/
tests/test_execution_interface.py
docs/architecture/PHASE_5_3_LINUX_SBC_EXECUTION_HOOK_IMPLEMENTATION.md
```
Deleting these files restores the repository to the Phase 5-1 baseline instantly, with zero modifications required in Core or Track C.

---

## 8. Dependency & Core Mutation Audit

- **Core Files Modified:** **0 (NO)**
- **Core Contracts Modified:** **0 (NO)**
- **Track C Modified:** **0 (NO)**
- **External Dependencies Added:** **0 (NO)**
- **Platform Audio Drivers Implemented:** **0 (NO)** (Interfaces & deterministic offline backend only)

---

## 9. Test Results

```text
============================= test session starts =============================
Platform: Windows (Python 3.13.14, pytest-9.1.1)
Total test items: 461 passed
Regressions: 0 failed, 0 errors, 0 warnings under `pytest -q -W error`
```
