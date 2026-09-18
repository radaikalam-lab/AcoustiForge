# \# AcoustiForge — Phase 0 Master Prompt

# 

# Project:

# &#x20;   AcoustiForge

# 

# Architecture:

# &#x20;   ACE — Acoustic Compute Engine

# 

# Phase:

# &#x20;   0 — Canonical PCM Contract and Pass-Through

# 

# Status:

# &#x20;   NORMATIVE

# 

# This document governs Phase 0 discovery, contract definition,

# implementation, validation, and acceptance.

# 

# \---

# 

# \# 6A. PCM Contract — Phase 0 Normative Requirements

# 

# \# 6A. PCM Contract — Phase 0 Normative Requirements

# 

# Phase 0 establishes the canonical internal PCM representation used by

# AcoustiForge.

# 

# The PCM contract is an architectural boundary, not merely a Python class.

# 

# The contract MUST distinguish:

# 

# \- sample

# \- channel

# \- frame

# \- block

# \- stream

# \- serialized audio representation

# 

# Definitions:

# 

# A sample:

# &#x20;   One numerical amplitude value for one channel at one sampling instant.

# 

# A frame:

# &#x20;   One sample for every channel at the same sampling instant.

# 

# A block:

# &#x20;   A contiguous collection of frames processed as one scheduling unit.

# 

# A stream:

# &#x20;   An ordered sequence of PCM frames.

# 

# The contract MUST explicitly define:

# 

# \- sample rate

# \- channel count

# \- channel ordering

# \- sample representation

# \- bit depth where applicable

# \- numerical range

# \- frame semantics

# \- block size

# \- interleaving

# \- in-memory representation

# \- serialized representation where applicable

# \- mutability

# \- ownership/lifetime

# \- continuity

# \- validation rules

# \- error behavior

# 

# Phase 0 MUST support a deliberately small initial format set.

# 

# The initial implementation SHOULD use:

# 

# &#x20;   float32 PCM

# 

# as the canonical computational representation unless discovery

# demonstrates a compelling reason otherwise.

# 

# Serialized formats such as WAV may use integer PCM, but conversion into

# the canonical computational representation MUST occur at the boundary.

# 

# The architecture MUST NOT assume that serialized representation and

# internal computational representation are identical.

# 

# \---

# 

# \# 6B. Numerical Contract

# 

# The host reference implementation and embedded implementation may use

# different numerical representations.

# 

# The contract MUST distinguish:

# 

# 1\. Bit-exact requirements

# 2\. Numerically equivalent requirements

# 3\. Measurement-tolerance requirements

# 

# For Phase 0:

# 

# \- pass-through of canonical float32 PCM MUST preserve sample values

# &#x20; exactly where the implementation permits it.

# \- metadata MUST remain unchanged.

# \- no clipping, gain, resampling, channel mixing or filtering may occur.

# \- any conversion performed at an external serialization boundary must

# &#x20; be explicitly tested.

# 

# Tolerance values MUST NOT be introduced without justification.

# 

# Later phases MUST define numerical tolerances for cross-implementation

# comparison.

# 

# The Python reference implementation is the behavioral reference during

# early development.

# 

# This does NOT imply that embedded floating-point or fixed-point

# implementations must be bit-identical.

# 

# \---

# 

# \# 6C. Phase 0 Dependency Boundary

# 

# Phase 0 MUST NOT require CMSIS-DSP or CMSIS-Stream.

# 

# CMSIS-DSP and CMSIS-Stream are upstream architectural references for

# subsequent phases.

# 

# Phase 0 exists to establish the AcoustiForge contracts independently

# of any embedded vendor framework.

# 

# No vendor SDK, MCU HAL, Bluetooth stack, RTOS or DSP library shall be

# required to pass the Phase 0 gate.

# 

# \---

# 

# \# 6D. Phase 0 Hardware Boundary

# 

# Phase 0 is hardware-independent.

# 

# The following are explicitly OUT OF SCOPE:

# 

# \- TG113

# \- PAM8403

# \- Bluetooth hardware

# \- DAC hardware

# \- ADC hardware

# \- I2S hardware

# \- STM32

# \- RISC-V

# \- speaker drivers

# \- acoustic enclosures

# 

# Hardware integration begins only after the computational contract has

# been established.

# 

# \---

# 

# \# 6E. Phase 0 Required Deliverables

# 

# Phase 0 MUST produce:

# 

# 1\. PCM contract documentation

# 2\. PCM validation implementation

# 3\. Canonical PCM representation

# 4\. Pass-through processing node

# 5\. Reference processing path

# 6\. Contract tests

# 7\. Numerical tests

# 8\. Determinism tests

# 9\. Phase 0 acceptance report

# 

# The implementation MUST remain minimal.

# 

# No EQ, FIR, IIR, crossover, compressor, limiter, bass enhancement,

# speaker protection or content analysis shall be implemented as part

# of Phase 0.

# 

# \---

# 

# \# 6F. Phase 0 Acceptance Gate

# 

# Phase 0 passes only if ALL conditions are satisfied.

# 

# \### Contract

# 

# \- PCM contract is documented.

# \- Frame and block semantics are unambiguous.

# \- Supported representation is explicitly defined.

# \- Channel ordering is explicitly defined.

# \- Validation rules are executable.

# 

# \### Pass-through

# 

# \- Input samples are preserved.

# \- Channel count is preserved.

# \- Sample rate is preserved.

# \- Frame ordering is preserved.

# \- Block ordering is preserved.

# \- No unintended transformation occurs.

# 

# \### Validation

# 

# Invalid configurations MUST be rejected deterministically.

# 

# At minimum, tests MUST cover:

# 

# \- invalid sample rate

# \- invalid channel count

# \- invalid sample format

# \- invalid block size

# \- malformed buffer

# \- channel/buffer-size mismatch

# \- non-contiguous or otherwise invalid input where relevant

# 

# \### Determinism

# 

# Identical input and configuration MUST produce identical output.

# 

# \### Dependency isolation

# 

# Phase 0 MUST pass without:

# 

# \- CMSIS-DSP

# \- CMSIS-Stream

# \- MCU hardware

# \- vendor SDKs

# \- RTOS

# \- audio hardware

# 

# \### Test gate

# 

# The complete Phase 0 test suite MUST pass with:

# 

# &#x20;   0 failed

# &#x20;   0 errors

# 

# Warnings MUST be treated as errors where practical.

# 

# \### Scope gate

# 

# No Phase 1 DSP functionality may be required for Phase 0 completion.

# 

# \---

# 

# \# 6G. Phase 0 Required Repository Structure

# 

# The minimum Phase 0 structure is:

# 

# &#x20;   contracts/

# &#x20;   docs/

# &#x20;       contracts/

# &#x20;       phases/

# &#x20;   prompts/

# &#x20;   scripts/

# &#x20;   src/

# &#x20;   tests/

# 

# Additional directories MAY exist if justified.

# 

# The following files are expected unless a documented architectural

# reason exists:

# 

# &#x20;   README.md

# &#x20;   LICENSE

# &#x20;   .gitignore

# &#x20;   pyproject.toml

# 

# The exact Python package name MUST be established during Phase 0

# discovery and documented before implementation.

# 

# \---

# 

# \# 6H. Phase 0 Discovery Rule

# 

# Before creating implementation files, the agent MUST perform discovery.

# 

# The discovery report MUST identify:

# 

# 1\. Current repository structure

# 2\. Existing files

# 3\. Existing contracts

# 4\. Existing tests

# 5\. Existing project configuration

# 6\. Missing Phase 0 artifacts

# 7\. Proposed PCM model

# 8\. Proposed processing-node abstraction

# 9\. Proposed reference-engine boundary

# 10\. CMSIS-DSP integration boundary

# 11\. CMSIS-Stream integration boundary

# 12\. Phase 0 acceptance tests

# 13\. Files to create

# 14\. Files explicitly not to create

# 15\. Open architectural questions

# 

# The agent MUST NOT implement Phase 0 during the discovery step.

# 

# Implementation requires explicit authorization after discovery.

