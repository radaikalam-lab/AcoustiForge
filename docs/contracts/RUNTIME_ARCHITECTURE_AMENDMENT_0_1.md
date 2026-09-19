# AcoustiForge — Phase 0.1 Future Runtime Architecture Amendment

**Status:** NORMATIVE ARCHITECTURAL AMENDMENT  
**Phase:** Phase 0.1 — Future Runtime Architecture Amendment  
**Governing Authority:** `prompts/MASTER_PROMPT.md`  
**Parent Specification:** `docs/contracts/PCM_CONTRACT.md`

---

## 1. Principle of Runtime Neutrality

AcoustiForge and its core computational engine, the **Acoustic Compute Engine (ACE)**, SHALL be strictly runtime-neutral.

The architecture explicitly decouples semantic definitions from runtime implementation mechanisms:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. ACE Semantic Contracts (Language- & Platform-Independent)           │
│    - Mathematical sample definitions, channel topologies, frame/block  │
│      semantics, validation rules, and transformation invariants.       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Realized by
     ┌──────────────────────────────┼──────────────────────────────┐
     ▼                              ▼                              ▼
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│ 2. Reference Runtime    │  │ 3. Embedded / Native    │  │ 4. Optional Scripting   │
│    (Python 3.12+ /      │  │    Runtime (C/C++, MCU, │  │    Runtime (MicroPython, │
│     NumPy ndarray)      │  │    CMSIS-DSP, RISC-V)   │  │    JSON/YAML graphs)     │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
```

1. **ACE Semantic Contracts:** Authoritative specification of audio math, channel layouts, validation invariants, and processing contracts.
2. **Reference Runtime (Python 3.12+ / NumPy):** The high-level behavioral reference used for algorithm prototyping, golden-model verification, and test generation.
3. **Embedded / Native Runtime:** High-performance, memory-constrained C/C++ runtimes targeting microcontrollers, DSPs, or bare-metal execution.
4. **Optional Scripting / Control Runtime:** Optional MicroPython or declarative interfaces for graph configuration and parameter tuning on resource-constrained devices.

> [!IMPORTANT]
> The Phase 0 Python/NumPy implementation is a **Reference Runtime**, NOT the definition of the ACE runtime. The semantic behavior of ACE is defined solely by the contracts.

---

## 2. PCM Semantics vs. Storage Representation

The architecture explicitly establishes the boundary between mathematical semantics and physical storage:

### 2.1 PCM Semantic Contract (Universal & Immutable)
The semantic contract defines what the audio data **means**:
- **Sample:** Dimensionless discrete-time numerical amplitude scalar in single-precision floating-point (`float32`), with nominal range $[-1.0, +1.0]$ and unclipped headroom.
- **Channel:** An independent, isolated monophonic signal line (e.g. Mono, Stereo L/R, or future $N$-channel layouts).
- **Frame:** An aligned temporal slice containing exactly one sample per active channel at instant $t_m$.
- **Sample Rate:** Positive discrete clock rate in Hertz ($f_s > 0$).
- **Block:** An atomic collection of $F$ consecutive frames ($F \ge 1$).
- **Stream:** An ordered sequence of blocks sharing matching sample rate and channel count.
- **Finite Invariant:** Prohibition of `NaN`, `+Inf`, and `-Inf`.

### 2.2 PCM Storage Representation (Runtime-Specific)
The storage representation defines how data is **held in physical memory**:
- **Reference Runtime (Python):** `numpy.ndarray` planar 2D tensor `(channels, frames)` with C-contiguous layout.
- **Embedded / Native Runtime (C/C++):** Pointers to raw contiguous float buffers (`float32_t *channel_ptrs[C]`), static ring buffers, or flat planar memory blocks.
- **Hardware / DMA Storage:** Hardware circular FIFOs, double-buffered ping-pong DMA regions, or memory-mapped SRAM blocks.

Implementation-specific storage concerns—including memory address, stride, alignment, buffer ownership, heap vs. static allocation, buffer lifetime, and DMA cache line alignment—belong exclusively to the runtime layer and MUST NOT constrain the semantic contract.

---

## 3. Memory Mutability & Zero-Copy Processing

1. **Reference Runtime Model:** Python processing nodes avoid in-place mutation of input arrays (`block.copy()` or read-only views) to preserve side-effect-free execution and caller immutability during high-level testing.
2. **Embedded Zero-Copy Model:** Embedded native runtimes (C/C++, CMSIS-DSP, MicroPython C-modules) are legally permitted to execute in-place transformations (e.g., `process_in_place(float32_t *buf, size_t frames)`) and use pre-allocated static memory pools without violating the semantic contract.
3. **Hardware Interleaving:** Interleaved hardware transports (e.g., standard stereo I2S DMA streams) convert to/from the canonical planar representation at the hardware ingestion/emission boundary.

---

## 4. Phase Compatibility & Non-Invalidation

This amendment:
- Fully preserves and validates the Phase 0 Reference Runtime implementation.
- Guarantees 100% passing status for all existing Phase 0 test suites (58/58 passed).
- Prevents future embedded, native, DSP, or MicroPython implementations from being constrained by Python language artifacts.
