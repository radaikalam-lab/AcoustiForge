# AcoustiForge — Phase 0 Discovery Prompt

## Authority

The governing requirements are defined by:

    prompts/MASTER_PROMPT.md

Read MASTER_PROMPT.md completely before performing discovery.

This task is DISCOVERY ONLY.

No implementation authorization has been granted.

---

# 1. Absolute Restrictions

During this task DO NOT:

- implement Phase 0
- create Python source files
- create test files
- create DSP implementations
- install dependencies
- add CMSIS-DSP
- add CMSIS-Stream
- add vendor SDKs
- add MCU HALs
- add RTOS dependencies
- add Bluetooth stacks
- add audio hardware support
- modify MASTER_PROMPT.md
- silently modify normative requirements

If an architectural conflict is discovered:

    STOP
    REPORT THE CONFLICT
    PROPOSE OPTIONS

Do not silently resolve it.

---

# 2. Repository Discovery

Inspect the complete repository.

Inspect:

- .git/
- .kilo/
- .project/
- contracts/
- data/
- docs/
- prompts/
- scripts/

Also inspect all files currently present in those directories.

Determine:

- repository state
- branch
- remote
- existing commits
- untracked files
- ignored files
- existing documentation
- existing contracts
- existing scripts
- existing project configuration

---

# 3. Existing Architecture

Identify whether any architecture has already been defined.

Report:

- architectural documents
- design decisions
- conventions
- naming conventions
- existing schemas
- existing testing conventions
- existing agent instructions

Do not assume directories are empty.

---

# 4. PCM Contract Analysis

Evaluate the Phase 0 PCM requirements in MASTER_PROMPT.md.

Analyze:

- sample
- channel
- frame
- block
- stream
- serialized representation

Evaluate whether the requirements sufficiently define:

- sample rate
- channel count
- channel ordering
- sample format
- bit depth
- numerical range
- frame semantics
- block semantics
- interleaving
- memory layout
- mutability
- ownership
- lifetime
- continuity
- validation
- error behavior

Identify every ambiguity.

Do not resolve an ambiguity silently.

---

# 5. Canonical PCM Proposal

Produce a proposed concrete Phase 0 representation.

Address:

- dtype
- dimensionality
- shape
- planar/interleaved representation
- channel ordering
- supported channel counts
- sample-rate policy
- block-size policy
- contiguous-memory requirements
- finite-value requirements
- numerical range
- clipping behavior
- metadata
- timestamp behavior
- ownership
- mutation behavior

For every proposed decision explain:

    Decision
    Rationale
    Future implication

---

# 6. Validation Matrix

Produce a table containing at least:

- invalid sample rate
- invalid channel count
- invalid sample format
- invalid block size
- malformed buffer
- incorrect dtype
- incorrect dimensions
- channel/buffer mismatch
- non-contiguous buffer
- NaN
- Inf
- invalid metadata
- invalid continuity

For each:

- condition
- expected result
- error class
- mandatory/deferred
- rationale

---

# 7. Pass-Through Contract

Propose the minimal pass-through processing contract.

Address:

- input
- output
- configuration
- state
- reset
- latency
- allocation
- mutation
- metadata
- determinism

Do not implement it.

---

# 8. Reference Engine

Define the boundary between:

    PCM contract
        ->
    processing node
        ->
    reference engine

Identify what belongs in each layer.

Do not implement the engine.

---

# 9. Future Upstream Boundary

Evaluate:

CMSIS-DSP:
https://github.com/ARM-software/CMSIS-DSP

CMSIS-Stream:
https://github.com/ARM-software/CMSIS-Stream

Do not install or import either dependency.

Determine:

- what AcoustiForge owns
- what CMSIS-DSP should provide
- what CMSIS-Stream should provide
- where integration should occur
- what must remain independent

---

# 10. Hardware Boundary

Confirm that Phase 0 remains independent of:

- TG113
- PAM8403
- Bluetooth
- ADC
- DAC
- I2S
- STM32
- RISC-V
- RTOS
- speakers
- acoustic hardware

Identify any accidental hardware assumptions.

---

# 11. Repository Proposal

Propose the minimum repository additions required for Phase 0.

For every proposed file provide:

    Path
    Purpose
    Owner/layer
    Normative/informative status
    Why required

Also identify files/directories that must NOT yet be created.

---

# 12. Dependency Analysis

Classify potential dependencies:

    REQUIRED
    OPTIONAL
    DEFERRED
    PROHIBITED

Do not install anything.

---

# 13. Test Strategy

Define the Phase 0 test categories:

- contract tests
- validation tests
- pass-through tests
- numerical tests
- determinism tests
- metadata tests
- negative tests
- dependency isolation
- scope isolation

Do not implement tests.

---

# 14. Acceptance Gate

Translate MASTER_PROMPT.md Section 6F into an executable
acceptance matrix.

Every criterion must have:

    ID
    Requirement
    Verification method
    Expected result

---

# 15. Open Questions

Identify unresolved questions.

For each:

    Question
    Why it matters
    Options
    Recommendation
    Phase

Do not make unapproved architectural changes.

---

# 16. Discovery Report

Produce:

    docs/phases/PHASE_0_DISCOVERY_REPORT.md

ONLY if explicitly authorized to create the report.

Otherwise return the complete report in the agent response.

The report MUST end with:

    PHASE 0 IMPLEMENTATION AUTHORIZATION:
    NOT REQUESTED

    PHASE 0 DISCOVERY:
    PASS / FAIL