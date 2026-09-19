# AcoustiForge — Phase 1A.1 DSP Node Contract Reconciliation & Freeze Preparation

**Project:** AcoustiForge  
**Architecture:** ACE — Acoustic Compute Engine  
**Phase:** 1A.1 — DSP Node Contract Reconciliation & Freeze Preparation  
**Status:** CONTRACT RECONCILIATION RECORD (FROZEN — NO IMPLEMENTATION)  

---

## 1. Purpose

This document performs the normative **Architectural Contract Reconciliation** for the **Phase 1A DSP Node Contract** in AcoustiForge. 

It corrects, refines, and formalizes the findings of the Phase 1A Discovery Report (`docs/phases/PHASE_1A_DSP_NODE_CONTRACT_DISCOVERY.md`) before freezing Phase 1A and proceeding to Phase 1B. 

This phase is **strictly architectural reconciliation and freeze preparation**. No DSP algorithms, filters, EQs, compressors, crossovers, or hardware/runtime bindings are implemented.

---

## 2. Governing Authorities

The authority hierarchy governing this reconciliation is:

1. `prompts/MASTER_PROMPT.md` (Highest normative authority)
2. `docs/contracts/PCM_CONTRACT.md` (Canonical PCM representation & validation)
3. `docs/contracts/RUNTIME_ARCHITECTURE_AMENDMENT_0_1.md` (Runtime neutrality & storage decoupling)
4. `docs/ARCHITECTURE.md` (System topology and subsystem boundaries)
5. `docs/phases/PHASE_0_ACCEPTANCE_REPORT.md` (Phase 0 verification baseline)
6. `docs/phases/PHASE_1A_DSP_NODE_CONTRACT_DISCOVERY.md` (Phase 1A discovery record)
7. This reconciliation document

---

## 3. Baseline Verification

The AcoustiForge baseline was verified prior to reconciliation:
- **Phase 0 State:** COMPLETED, VERIFIED, and FROZEN.
- **Phase 0.1 State:** COMPLETED and ADOPTED.
- **Regression Suite:** 58 tests passed in 0.35s (0 failures, 0 errors, 0 warnings).
- **Repository Hygiene:** Clean working tree, zero untracked code files, zero unapproved dependencies.
- **Scope Discipline:** Zero DSP code or hardware firmware present in `src/`.

---

## 4. Findings from Phase 1A Discovery

The Phase 1A discovery established essential concepts for DSP nodes (parameter/state separation, lifecycle states, channel isolation) but introduced several over-specifications and conceptual ambiguities that require formal reconciliation:
1. *Numerical Conformance:* Over-specified universal bit-exactness across all runtime targets.
2. *Topology:* Prematurely declared Direct Form II Transposed as a universal ACE-wide invariant.
3. *Subnormals / Denormals:* Imposed an arbitrary $10^{-15}$ Flush-to-Zero threshold into the universal semantic contract.
4. *Latency Semantics:* Conflated minimum-phase group delay with algorithmic frame displacement.
5. *Parameter Atomicity:* Lacked formal failure and rollback transaction semantics for parameter updates.
6. *Memory Allocation:* Used language implying dynamic heap allocation on the node configuration path.
7. *Channel Coupling:* Did not accommodate cross-channel coupled nodes (e.g. matrix mixers, Mid/Side processors).
8. *MicroPython:* Ambiguity regarding whether MicroPython was required to process real-time audio samples.

---

## 5. Reconciliation Decisions (DEC-01 through DEC-10)

### DEC-01 — Numerical Conformance Taxonomy
Universal bit-for-bit identity across disparate runtime targets (e.g., host x86 64-bit FPU vs. Cortex-M4 single-precision FPU vs. fixed-point DSP) is mathematically impossible and architecturally inappropriate.

ACE adopts a three-tier conformance taxonomy:

```
┌────────────────────────────────────────────────────────────────────────┐
│ ACE Numerical Conformance Taxonomy                                     │
├────────────────────────────────────────────────────────────────────────┤
│ A. BIT_EXACT                                                           │
│    Bitwise identical output (IEEE 754 float32 bit parity).             │
│    Applied strictly where exact equality is achievable and required    │
│    (e.g., PassThroughNode, Gain=1.0, Mute, Channel Routing).           │
├────────────────────────────────────────────────────────────────────────┤
│ B. NUMERICALLY_EQUIVALENT                                              │
│    Realizes the declared mathematical operation within an explicitly   │
│    defined numerical tolerance (e.g., epsilon bounds on float math).   │
├────────────────────────────────────────────────────────────────────────┤
│ C. MEASUREMENT_EQUIVALENT                                              │
│    The realization satisfies the engineering measurement criteria      │
│    explicitly declared by the applicable node contract (e.g. magnitude │
│    response, phase response, impulse response, THD, stability).        │
└────────────────────────────────────────────────────────────────────────┘
```

### DEC-02 — Biquad Topology Neutrality
- **Decision:** Direct Form II Transposed (DF-II-T) is **NOT** a universal ACE-wide architectural mandate.
- **Specification:** The Phase 1B Biquad reference implementation *may* use DF-II-T as its initial canonical numerical realization in Python. The ACE node contract itself remains topology-neutral.
- **Distinction:**
  - *Mathematical DSP Operation:* Second-order linear difference equation transfer function $H(z)$.
  - *Numerical Realization:* Floating-point evaluation order (DF-I, DF-II, DF-II-T).
  - *Runtime Implementation:* Target-specific assembly or kernel (e.g., CMSIS-DSP `arm_biquad_cascade_df1_f32`).

### DEC-03 — Denormal / Subnormal Handling Policy
- **Decision:** ACE does **not** mandate a universal semantic denormal policy or fixed flush threshold ($10^{-15}$).
- **Specification:** Runtimes MAY enable hardware FPU Flush-to-Zero (FTZ) / Denormals-Are-Zero (DAZ) or software flushing. Any such optimization is evaluated against the node's declared numerical conformance class (`NUMERICALLY_EQUIVALENT` or `MEASUREMENT_EQUIVALENT`). Reference mathematical definitions do not change.

### DEC-04 — Algorithmic Latency Semantics
- **Definition:**  
  $$\text{latency\_frames} = \text{intentional discrete temporal displacement (in integer frames) between input stream position and output stream position.}$$
- **Disambiguation:**
  - *Algorithmic Latency:* Structural delay introduced by the algorithm itself (e.g., Causal Biquad with no explicit delay $= 0$ frames; Linear-Phase FIR $= \frac{N-1}{2}$ frames; DelayNode $= N$ frames). Group delay / phase shift is continuous phase behavior, NOT discrete frame latency.
  - *Buffering / Block Latency:* Latency introduced by block scheduling (managed by the execution engine, Phase 2).
  - *Hardware / IO Latency:* Converter, DMA, and driver buffering delay (managed by hardware abstraction, Phase 4).
  - ACE node contracts describe strictly **Algorithmic Latency**.

### DEC-05 — Parameter Update Atomicity & Transaction Semantics
- **Invariant:** A parameter update MUST be validated and prepared before becoming active.
- **Transaction Flow:**
  ```
  Current Configuration ──> Candidate Configuration ──> Validate Parameters
                                                              │
                                       ┌──────────────────────┴──────────────────────┐
                                       ▼                                             ▼
                               [Validation Fails]                           [Validation Passes]
                                       │                                             │
                               Discard Candidate                             Prepare Derived Values / Coeffs
                               Current Unchanged                                     │
                               No State Mutation                                     ▼
                                                                             Atomic Activation
  ```
- **Guarantees:** A failed parameter update MUST NOT leave the node in a partially modified state (active parameters, coefficients, state buffers, and channel configurations remain intact). Parameter updates are control-plane operations.

### DEC-06 — Parameter / State Relationship & Reset Semantics
- **Separation:** Parameters (configuration) and State (runtime history) are orthogonal:
  - Changing parameters MUST NOT implicitly reset runtime state unless explicitly declared by a specific node's contract.
  - `reset()` clears runtime state history to initial zero/silence, preserves active configuration/parameters, preserves channel topology, and does NOT allocate or free memory.

### DEC-07 — Runtime-Specific State Storage
- **Decision:** The semantic contract replaces "allocates state buffers" with:  
  *"Node configuration establishes sufficient state storage for the configured node topology and channel configuration."*
- **Storage Allocation by Runtime:**
  - *Python Reference:* Heap allocation of NumPy state tensors during `configure()`.
  - *Native C / C++:* Static struct allocation or stack/bss buffers.
  - *Embedded MCU:* Fixed memory pool or statically provisioned state arrays.
  - *DMA / Zero-Copy:* Externally provisioned ring-buffer state.
- **Allocation Profiles:**
  - *ACE Semantic Contract:* A node's semantic definition MUST NOT require dynamic allocation during processing.
  - *Real-Time Execution Profile:* Implementations claiming deterministic real-time execution MUST perform no dynamic heap allocation on the audio processing hot path (`process()`).
  - *Reference / Offline Execution:* Allocation behavior is runtime-specific, provided semantic behavior and declared conformance are preserved.

### DEC-08 — Logical Channel State Isolation & Coupling Model
- **Independent Nodes (`channel_processing = INDEPENDENT`):** Each channel's processing state is logically independent. Processing channel $c$ MUST NOT read, modify, or alias state of channel $k \neq c$. Logical state isolation is normative, while physical state memory layout is runtime-specific (implementations are not restricted to literal `state[C][N]` arrays; SIMD, packed, or interleaved physical structures are permitted provided logical isolation is preserved).
- **Coupled Nodes (`channel_processing = COUPLED`):** Cross-channel processing (matrix mixers, Mid/Side, stereo wideners, crossfeed, beamformers) MUST explicitly declare their cross-channel coupling topology in their node contract.

### DEC-09 — Node Shape Contract
A formal node shape contract characterizes the structural transformation performed by any node:
$$\{ C_{\text{in}} \to C_{\text{out}},\, F_{\text{in}} \to F_{\text{out}},\, \text{SR}_{\text{in}} \to \text{SR}_{\text{out}},\, \text{latency},\, \text{statefulness},\, \text{coupling} \}$$
- *Standard In-Place DSP (Biquad, Gain):* $C \to C, F \to F, \text{SR} \to \text{SR}$, Latency $= 0$, Independent.
- *Delay Node:* $C \to C, F \to F, \text{SR} \to \text{SR}$, Latency $= N$, Independent.
- *Resampling Node (Phase 2):* $C \to C, F_{\text{in}} \to F_{\text{out}}, \text{SR}_{\text{in}} \to \text{SR}_{\text{out}}$, Latency $= L$.
- *Channel Matrix Mixer (Phase 2):* $C_{\text{in}} \to C_{\text{out}}, F \to F, \text{SR} \to \text{SR}$, Coupled.

### DEC-10 — Role of MicroPython
- **Decision:** MicroPython is an optional high-level environment for control, configuration, telemetry, and graph orchestration.
- **Boundary:** MicroPython is **NOT** the real-time sample processing runtime. Real-time sample transformation executes in native C/C++ / CMSIS-DSP kernels. MicroPython configures nodes, loads acoustic profiles, and binds native execution pipelines.

---

## 6. Revised DSP Node Semantic Model

An ACE DSP node is conceptually defined by:

```
┌────────────────────────────────────────────────────────────────────────┐
│ DSP Node Semantic Model                                                │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Identity:       Unique name, version, semantic category             │
│ 2. Configuration:  Parameter schema, valid ranges, validation rules    │
│ 3. Shape:          (Cin -> Cout, Fin -> Fout, SRin -> SRout, Latency)  │
│ 4. Coupling:       INDEPENDENT vs. COUPLED channel processing          │
│ 5. State:          Stateful declaration, state lifetime, reset rules   │
│ 6. Numerical:      Conformance class (BIT_EXACT, NUMERICALLY_EQUIV,    │
│                    MEASUREMENT_EQUIV), stability invariants            │
│ 7. Lifecycle:      configure(), process(), reset(), set_parameters()   │
│ 8. Invariants:     Semantic definition requires no dynamic allocation; │
│                    real-time profiles prohibit hot-path heap alloc     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Revised Lifecycle Model

```
        ┌──────────────────┐
        │   UNCONFIGURED   │
        └────────┬─────────┘
                 │ configure(sample_rate, channels)
                 ▼
        ┌──────────────────┐ ◄───────────────────────────────┐
        │    CONFIGURED    │                                 │
        └────────┬─────────┘                                 │
                 │ process(block)                            │ reset()
                 ▼                                           │
        ┌──────────────────┐                                 │
   ┌──► │      ACTIVE      │ ────────────────────────────────┘
   │    └────────┬─────────┘
   │             │ set_parameters() [Atomic update]
   └─────────────┘ [State & Active status preserved]
```

- **UNCONFIGURED:** Node instantiated with default parameters; no channel/rate binding; cannot process audio.
- **CONFIGURED:** Sample rate and channels bound; state storage established and zero-initialized; ready for processing.
- **ACTIVE:** Actively processing audio streams; state history maintained across sequential blocks.
- **Parameter Update:** Executed atomically during CONFIGURED or ACTIVE state without regressing to UNCONFIGURED and without implicitly resetting state.

---

## 8. Parameter / State Separation

| Dimension | Node Configuration / Parameters ($\Theta$) | Node Runtime State ($S$) |
|---|---|---|
| **Nature** | Transfer function definition ($f_0, Q, \text{Gain}, b_i, a_i$) | Past sample history ($w[n-1], w[n-2]$) |
| **Mutability** | Static during block execution; updated out-of-band | Mutated frame-by-frame during `process()` |
| **Channel Scope** | Shared or per-channel parameter sets | Logically isolated per channel (for independent nodes) |
| **Persistence** | Parameters remain active across `reset()` operations unless explicitly changed by a valid parameter update | Cleared to $0.0$ on `reset()` |
| **Hot-Path Behavior**| Read-only access on the audio hot path | Read-write in-place updates on hot path |

---

## 9. Numerical Conformance Taxonomy

```
┌────────────────────────────────────────────────────────────────────────┐
│ Conformance Level       │ Definition / Scope                           │
├─────────────────────────┼──────────────────────────────────────────────┤
│ BIT_EXACT               │ Exact bitwise equality (error = 0.0)         │
├─────────────────────────┼──────────────────────────────────────────────┤
│ NUMERICALLY_EQUIVALENT  │ Realizes declared mathematical operation     │
│                         │ within explicitly defined numerical tolerance│
├─────────────────────────┼──────────────────────────────────────────────┤
│ MEASUREMENT_EQUIVALENT  │ The realization satisfies the engineering    │
│                         │ measurement criteria explicitly declared by  │
│                         │ the applicable node contract                 │
└────────────────────────────────────────────────────────────────────────┘
```

> [!NOTE]
> Concrete numerical tolerances are deferred to the relevant node contract, beginning with Phase 1B Biquad mathematical validation.

---

## 10. Latency Semantics

- **Algorithmic Latency ($L_{\text{algo}}$):** Explicitly declared by the node contract. For a causal biquad with no explicit sample/frame delay, $L_{\text{algo}} = 0$.
- **Pipeline Latency:** The sum of algorithmic latencies across all active nodes in an execution pipeline:  
  $$L_{\text{total}} = \sum_{i=1}^{M} L_{\text{algo}, i}$$
- **Separation:** Engine buffering latency and hardware DMA latency are decoupled from the node's declared algorithmic latency. Group delay and phase shift represent continuous phase behavior, NOT discrete algorithmic frame latency.

---

## 11. Channel Coupling Model

- **`channel_processing = INDEPENDENT`:**
  - Logical state independence is normative: $S_{\text{total}} = \{S^{(0)}, S^{(1)}, \dots, S^{(C-1)}\}$.
  - $y^{(c)}[n] = f(x^{(c)}[n], S^{(c)}, \Theta)$.
  - 100% logical state isolation is enforced. Physical state memory layout (planar, packed, interleaved, SIMD register sets) is runtime-specific.
- **`channel_processing = COUPLED`:**
  - $\mathbf{y}[n] = f(\mathbf{x}[n], \mathbf{S}, \Theta)$ where $\mathbf{x}[n]$ is a multi-channel vector.
  - State coupling rules MUST be explicitly specified in the node contract.

---

## 12. Node Shape Contract

```
NodeShape:
  inputs:
    channels: C_in (e.g. 1, 2, or Any)
    sample_rate: SR_in
  outputs:
    channels: C_out
    sample_rate: SR_out
  frames:
    relationship: "1:1" | "variable"
  latency_frames: int >= 0
  statefulness: "stateless" | "stateful"
  coupling: "independent" | "coupled"
```

---

## 13. Runtime Neutrality

AcoustiForge maintains strict separation between architectural contracts and runtime implementations:
- **ACE Contract:** Normative, language-agnostic specification.
- **Python / NumPy:** Reference realization for validation and golden-model generation.
- **Native C / C++:** Production implementation for embedded systems.
- **ARM CMSIS-DSP:** Optional target-specific acceleration backend (non-normative).
- **RISC-V DSP:** Optional target-specific acceleration backend (non-normative).
- **MicroPython:** Optional orchestration and configuration layer.

---

## 14. MicroPython Role

MicroPython functions as an embedded control plane:
- Graph topology construction and pipeline linking.
- Parameter adjustment, preset loading, and acoustic profile selection.
- Telemetry gathering, thermal monitoring, and system control.
- Real-time sample processing is delegated to native C/C++ / CMSIS-DSP compute blocks.

---

## 15. Future Numerical Representation Boundary

While Phase 0 and Phase 1 use single-precision `float32`, future embedded implementations may investigate fixed-point arithmetic (`Q31`, `Q15`):
- Fixed-point realization requires explicit contracts for headroom scaling, saturation, rounding, and overflow behavior.
- Fixed-point processing is **NOT** part of Phase 1; it remains a future runtime investigation area.

---

## 16. Phase 1B Implications

Phase 1B will establish the **Biquad Filter Contract & Mathematical Foundation**:
- Standard Second-Order IIR Biquad transfer functions.
- Canonical Audio EQ Cookbook filter types (LowPass, HighPass, BandPass, Notch, Peaking, LowShelf, HighShelf).
- Normalized angular frequency $\omega_0 = 2\pi \frac{f_0}{f_s}$, bandwidth, $Q$, and gain formulation.
- Coefficient sign conventions ($b_0, b_1, b_2, a_1, a_2$).
- Direct Form II Transposed reference realization equations.
- Mathematical stability invariants ($|z_p| < 1.0$).
- Golden test vectors for numerical and measurement equivalence.

---

## 17. Items Explicitly Deferred

The following items are intentionally deferred:
- ❌ Implementation of `BiquadNode`, `GainNode`, or filter coefficient calculators (Deferred to Phase 1B/1C).
- ❌ Fixed-point arithmetic (`Q31`/`Q15`) and saturation logic (Deferred to embedded runtime phases).
- ❌ Denormal Flush-to-Zero hardware threshold selection (Deferred to runtime realization).
- ❌ CMSIS-DSP wrapper code and native C extensions (Deferred to Phase 1/Phase 2 C runtime).
- ❌ MicroPython C-module bindings (Deferred to Phase 4).
- ❌ Dynamic runtime sample-rate converters and crossover networks (Deferred to Phase 2).

---

## 18. Acceptance Checklist

- [x] Phase 0 remains completely unchanged.
- [x] Phase 0 regression tests pass (58/58 passed, 0 failures, 0 errors, 0 warnings).
- [x] No DSP implementation code was introduced.
- [x] Parameter/state separation is mathematically explicit.
- [x] Parameter update failure and rollback semantics are explicit.
- [x] Runtime state reset semantics are explicit (preserves parameters, clears state).
- [x] Channel isolation and coupling models are explicit.
- [x] Node shape semantics ($C, F, \text{SR}$, latency) are defined.
- [x] Algorithmic latency is explicitly defined and separated from buffer/hardware latency.
- [x] Universal bit-exactness is not imposed across disparate runtime targets.
- [x] Numerical equivalence and measurement equivalence are formalized.
- [x] DF-II-T is established as a reference choice for Phase 1B, not a universal ACE invariant.
- [x] Denormal/subnormal handling is deferred as a runtime-specific policy.
- [x] Runtime state storage is separated from semantic contracts (zero hot-path dynamic allocation for real-time profiles).
- [x] MicroPython is designated as control/configuration, not mandatory real-time DSP runtime.
- [x] Future fixed-point representations remain possible.
- [x] CMSIS-DSP remains optional and non-normative.
- [x] Zero physical hardware dependencies introduced.
- [x] Semantic definitions require no dynamic allocation during processing.
- [x] Phase 1B scope is clearly bounded.
- [x] Zero Phase 1B implementation code created.

---

## 19. Final Decision & Status

### Decision
$$\mathbf{PHASE\ 1A\ DSP\ NODE\ CONTRACT:\ FROZEN}$$

### Phase 0 Regression Results
- **Total Tests:** 58
- **Passed:** 58
- **Failed:** 0
- **Errors:** 0
- **Warnings:** 0

### Files Created
- `docs/phases/PHASE_1A_DSP_NODE_CONTRACT_DISCOVERY.md`
- `docs/phases/PHASE_1A_1_DSP_NODE_CONTRACT_RECONCILIATION.md`

### Files Modified
- *None*

### Files Not Modified
- `prompts/MASTER_PROMPT.md`
- `docs/contracts/PCM_CONTRACT.md`
- `docs/contracts/RUNTIME_ARCHITECTURE_AMENDMENT_0_1.md`
- `src/acoustiforge/*` (All Phase 0 implementation files intact)
- `tests/*` (All Phase 0 test files intact)
- `docs/phases/PHASE_0_ACCEPTANCE_REPORT.md`

### Phase 1B Boundary
Phase 1B is **Biquad Filter Contract & Mathematical Foundation**. Phase 1B will establish the mathematical formulas, coefficient conventions, stability constraints, and golden test vectors for biquad filters without creating production DSP node implementations.

---

PHASE 1A DSP NODE CONTRACT: FROZEN  
PHASE 1A.1-F FINAL CORRECTION: COMPLETE  
PHASE 1A IMPLEMENTATION AUTHORIZATION: NOT REQUESTED
