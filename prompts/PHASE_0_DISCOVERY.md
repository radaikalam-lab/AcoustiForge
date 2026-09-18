# AcoustiForge — Phase 0 Fresh Discovery Prompt

## 1. Role

You are performing ARCHITECTURAL DISCOVERY for the AcoustiForge project.

Project:
    AcoustiForge

Conceptual compute layer:
    ACE — Acoustic Compute Engine

Current phase:
    Phase 0 — Canonical PCM Contract and Pass-Through

This is a DISCOVERY task only.

You MUST NOT implement Phase 0.

You MUST NOT create source code, tests, dependencies, or implementation
artifacts during this task.

---

# 2. Governing Document

Before doing anything else, read:

    prompts/MASTER_PROMPT.md

The Master Prompt is normative for Phase 0.

Treat it as the governing specification.

Do NOT modify MASTER_PROMPT.md.

Do NOT reinterpret or weaken its acceptance criteria.

If the repository contains information that conflicts with the Master
Prompt, identify the conflict explicitly in the discovery report.

---

# 3. Repository State

The repository has intentionally been reconstructed as a clean
AcoustiForge repository after removal of inherited project material.

The current repository MUST be treated as authoritative.

Do NOT assume that files, structures, contracts, rules, workflows,
dependencies, or architectural decisions from another project exist.

In particular, do NOT introduce assumptions from:

- CellForge
- biological knowledge graphs
- E. coli data models
- ERP systems
- unrelated prior projects
- vendor-specific audio frameworks
- CMSIS implementation details
- MCU-specific buffer models
- Bluetooth chip implementations

External technologies may be discussed only when relevant to defining
an explicit future integration boundary.

---

# 4. Discovery-Only Rule

This task MUST NOT perform implementation.

The agent MUST NOT:

- create src/
- create tests/
- create Python packages
- create PCM classes
- create processing nodes
- create YAML contracts
- create schemas
- install packages
- modify pyproject.toml
- modify MASTER_PROMPT.md
- add CMSIS dependencies
- add hardware dependencies
- create DSP implementations
- create test fixtures
- create CI workflows
- create Docker infrastructure

The agent MAY create or modify ONLY the discovery report if a report
file is explicitly required by the repository workflow.

Prefer producing the report as output unless the repository already
defines a specific discovery-report location.

---

# 5. Repository Inspection

Inspect the repository completely enough to establish the current
baseline.

At minimum inspect:

1. Repository tree
2. Git status
3. Git branch
4. Git remote
5. Recent Git history
6. Tracked files
7. Existing documentation
8. Existing prompts
9. Existing contracts directory
10. Existing data directory
11. Existing scripts
12. README if present
13. Architecture documentation if present
14. Python/project configuration if present
15. Any existing test infrastructure if present

Do not assume that an empty directory is evidence of a missing
architecture.

Distinguish:

- existing artifact
- missing artifact
- intentionally deferred artifact
- open architectural question

---

# 6. Repository Cleanliness

Verify that the repository is genuinely AcoustiForge-specific.

Look specifically for:

- inherited project files
- stale governance files
- foreign project names
- unrelated contract schemas
- unrelated project-state files
- unrelated test infrastructure
- obsolete automation
- vendor-specific assumptions

Do NOT perform a generic keyword scan and treat arbitrary words as
contamination.

Identify actual artifacts and explain why they are foreign if any are
found.

If no contamination exists, explicitly state:

    Repository contamination: NOT DETECTED

---

# 7. Understand AcoustiForge

Establish the architecture from the current repository and governing
prompt.

Document the current understanding of:

    Source
       ↓
    Transport / Decoder
       ↓
    PCM Contract
       ↓
    ACE Processing Pipeline
       ↓
    PCM Output
       ↓
    DAC / Digital Audio Interface
       ↓
    Amplification
       ↓
    Acoustic Transducer

Do not expand this architecture merely because additional components
could be useful.

Clearly distinguish:

### AcoustiForge-owned concerns

from

### External/upstream concerns

and

### Future hardware integration concerns

---

# 8. Phase 0 Objective

Define precisely what Phase 0 establishes.

Phase 0 is intended to establish the canonical internal PCM
representation and a minimal pass-through processing path.

Analyze the required boundary between:

    serialized audio
          ↓
    canonical PCM
          ↓
    processing
          ↓
    canonical PCM output

The architecture MUST distinguish:

- sample
- channel
- frame
- block
- stream
- serialized representation

Explain each term as it applies to AcoustiForge.

Pay particular attention to the distinction between:

    frame

and

    block

and between:

    stream

and

    serialized audio representation.

---

# 9. PCM Contract Discovery

Investigate and propose a candidate canonical PCM model.

The proposal MUST explicitly address:

## Sample

- numerical representation
- precision
- numerical range
- finite/non-finite values
- clipping/headroom semantics

## Channels

- supported channel counts
- channel ordering
- mono semantics
- stereo semantics
- extensibility to future channel layouts

## Sample Rate

- representation
- validity constraints
- whether Phase 0 should constrain supported rates
- distinction between contract validity and implementation support

## Frames

- exact definition
- ordering
- relationship to channels

## Blocks

- exact definition
- frame count
- scheduling semantics
- whether block size is fixed or variable

## Streams

- ordering
- continuity
- relationship between blocks
- discontinuity semantics

## Memory Representation

Evaluate alternatives such as:

- interleaved
- planar

Do not select one merely because an external DSP library prefers it.

The selection MUST be justified by AcoustiForge requirements.

Address:

- array dimensions
- shape
- dtype
- memory layout
- contiguity
- byte order where relevant
- ownership
- lifetime
- mutability
- aliasing

## Serialization

Clearly distinguish internal computational PCM from serialized
representations such as WAV.

Do not assume that serialized representation and computational
representation are identical.

---

# 10. Numerical Contract

Define the numerical requirements that Phase 0 can actually justify.

Distinguish:

1. Bit-exact requirements
2. Numerically equivalent requirements
3. Measurement-tolerance requirements

Determine what is appropriate for:

- pass-through
- metadata
- serialization conversion
- future DSP processing

Do NOT invent numerical tolerances.

If a tolerance cannot yet be justified, identify it as deferred.

The Python reference implementation may later become the behavioral
reference, but discovery must distinguish this from a requirement that
future embedded implementations be bit-identical.

---

# 11. Pass-Through Node

Define the Phase 0 pass-through processing contract.

Determine:

- input contract
- output contract
- latency
- sample preservation
- frame ordering
- block ordering
- metadata behavior
- statefulness
- reset semantics
- mutation behavior
- error behavior
- determinism requirements

Pass-through MUST NOT perform:

- gain
- clipping
- resampling
- channel mixing
- filtering
- EQ
- dynamics
- crossover
- bass enhancement
- speaker protection
- content analysis

---

# 12. Processing Node Abstraction

Propose the minimum abstraction required for a Phase 0 processing node.

The abstraction should be sufficient for:

    PassThrough

without prematurely designing:

- EQ
- FIR
- IIR
- crossover
- compressor
- limiter
- speaker protection
- adaptive DSP
- ML processing

Explain which parts are required now and which should be deferred.

Avoid framework-heavy abstractions.

The Phase 0 design should remain minimal and understandable.

---

# 13. Reference Engine Boundary

Define the conceptual boundary between:

    PCM Contract
        ↓
    Processing Node
        ↓
    Reference Processing Engine

Determine:

- what the engine owns
- what nodes own
- what the PCM contract owns
- how blocks move through the engine
- how metadata moves through the engine
- how errors propagate
- how determinism is established

Do not implement the engine.

---

# 14. CMSIS-DSP Boundary

CMSIS-DSP is an upstream reference for future optimized DSP kernels.

Determine:

- what functionality AcoustiForge may eventually consume from CMSIS-DSP
- what AcoustiForge must own independently
- where an adapter boundary would belong
- whether CMSIS-DSP is relevant to Phase 0

Phase 0 MUST remain independent of CMSIS-DSP.

Do not design the core PCM contract merely to imitate CMSIS-DSP.

---

# 15. CMSIS-Stream Boundary

CMSIS-Stream is an upstream reference for future streaming/dataflow
execution.

Determine:

- what functionality it may eventually provide
- how it differs from the AcoustiForge processing graph
- where an adapter boundary might exist
- whether it is relevant to Phase 0

Phase 0 MUST remain independent of CMSIS-Stream.

Do not make CMSIS-Stream assumptions part of the Phase 0 contract.

---

# 16. Hardware Boundary

Phase 0 is hardware-independent.

Explicitly evaluate and document the boundary involving future
hardware such as:

- Bluetooth audio modules
- TG113-class modules
- ADC
- DAC
- I2S
- digital amplifiers
- Class-D amplifiers
- MCUs
- RISC-V systems
- speaker drivers
- acoustic enclosures

Do NOT design hardware integration during Phase 0.

If a future hardware path is mentioned, describe only the interface
boundary.

Never assume the exact TG113 internal SoC, codec path, I2S availability,
or electrical interface without empirical evidence.

---

# 17. Dependency Analysis

Determine the minimum dependencies required for Phase 0.

Classify each candidate dependency as:

    REQUIRED
    OPTIONAL
    DEFERRED
    PROHIBITED

Consider:

- Python
- NumPy
- pytest
- Pydantic
- SciPy
- CMSIS-DSP
- CMSIS-Stream
- vendor SDKs
- MCU HALs
- RTOS
- audio hardware libraries

Do not add dependencies merely because they are familiar.

Every REQUIRED dependency must have a Phase 0 justification.

---

# 18. Repository Structure

Evaluate the minimum repository structure needed for Phase 0.

The Master Prompt specifies:

    contracts/
    docs/
        contracts/
        phases/
    prompts/
    scripts/
    src/
    tests/

and expected project files such as:

    README.md
    LICENSE
    .gitignore
    pyproject.toml

Determine:

1. Which are required immediately
2. Which must be created only after implementation authorization
3. Which are optional
4. Which are deferred
5. Which architectural rationale supports each decision

Do not create them during discovery.

---

# 19. Validation Matrix

Define the Phase 0 validation matrix.

At minimum evaluate:

- invalid sample rate
- invalid channel count
- invalid sample format
- invalid block size
- malformed buffer
- channel/buffer-size mismatch
- invalid memory layout where relevant
- non-contiguous input where relevant
- non-finite samples
- invalid frame semantics
- invalid stream/block continuity where applicable

For each test define:

    ID
    condition
    expected result
    rationale
    contract section

Do not implement the tests.

---

# 20. Pass-Through Test Matrix

Define tests covering:

### Data

- sample preservation
- frame preservation
- channel preservation
- block ordering
- stream ordering

### Metadata

- sample rate
- channel configuration
- frame position if applicable
- continuity state if applicable

### Numerical behavior

- exact preservation where required
- absence of unintended transformation

### Determinism

Repeated identical input/configuration must produce identical
results.

### Boundaries

Consider:

- mono
- stereo
- short blocks
- large blocks
- multiple blocks
- silence
- impulses
- negative values
- values near numerical boundaries
- valid headroom values if permitted

Do not invent requirements not justified by the contract.

---

# 21. Acceptance Gate

Construct a Phase 0 acceptance matrix directly from MASTER_PROMPT.md.

For every acceptance criterion provide:

    Criterion
    Verification method
    Planned test/document
    Status

The final report MUST NOT claim that implementation tests pass,
because implementation has not yet been performed.

Use statuses such as:

    VERIFIED BY DISCOVERY
    PROPOSED
    DEFERRED
    OPEN

Do not use:

    PASS

for an implementation criterion that has not actually been executed.

---

# 22. Required Deliverables Analysis

Determine the implementation artifacts that will eventually be required:

1. PCM contract documentation
2. PCM validation implementation
3. Canonical PCM representation
4. Pass-through processing node
5. Reference processing path
6. Contract tests
7. Numerical tests
8. Determinism tests
9. Phase 0 acceptance report

For each, identify:

- proposed location
- purpose
- dependencies
- relationship to the contract
- whether it belongs to Phase 0 implementation

Do not create them.

---

# 23. Explicit Non-Goals

Identify what Phase 0 MUST NOT implement.

At minimum:

- EQ
- FIR
- IIR
- crossover
- compressor
- limiter
- bass enhancement
- speaker protection
- acoustic modelling
- calibration algorithms
- adaptive processing
- machine learning
- Bluetooth stack
- vendor hardware integration
- MCU runtime
- CMSIS integration

If another non-goal is discovered, document it.

---

# 24. Architectural Questions

Identify unresolved questions.

For each question provide:

    Question
    Why it matters
    Options
    Current evidence
    Recommended decision timing

Do not force a decision simply to eliminate an open question.

Separate:

    Phase 0 decisions

from:

    Future-phase decisions.

---

# 25. Implementation Authorization Boundary

The discovery report MUST end with an explicit implementation boundary.

Use:

    PHASE 0 DISCOVERY STATUS:
    COMPLETE

and:

    PHASE 0 IMPLEMENTATION AUTHORIZATION:
    NOT REQUESTED

Discovery MUST NOT authorize implementation implicitly.

Implementation requires a separate explicit authorization step.

---

# 26. Required Discovery Report Structure

Produce the discovery report using exactly this high-level structure:

# AcoustiForge Phase 0 Fresh Discovery Report

## 1. Executive Summary

## 2. Repository Baseline

## 3. Repository Contamination Assessment

## 4. Current AcoustiForge Architecture

## 5. Phase 0 Objective

## 6. PCM Contract Analysis

## 7. Candidate Canonical PCM Model

## 8. Numerical Contract

## 9. Pass-Through Contract

## 10. Processing Node Abstraction

## 11. Reference Engine Boundary

## 12. CMSIS-DSP Boundary

## 13. CMSIS-Stream Boundary

## 14. Hardware Boundary

## 15. Dependency Analysis

## 16. Repository Structure

## 17. Validation Matrix

## 18. Pass-Through Test Matrix

## 19. Phase 0 Acceptance Matrix

## 20. Required Implementation Artifacts

## 21. Explicit Non-Goals

## 22. Open Architectural Questions

## 23. Proposed Implementation Sequence

## 24. Discovery Conclusions

## 25. Implementation Authorization Status

---

# 27. Critical Discipline

This discovery is intended to establish a clean architectural
foundation.

Do not optimize prematurely.

Do not introduce abstractions merely because they may be useful later.

Do not copy patterns from CellForge.

Do not copy patterns from ERP projects.

Do not make CMSIS the architectural authority.

Do not make Python implementation details the architectural authority.

Do not make future hardware the architectural authority.

The authority hierarchy is:

    1. MASTER_PROMPT.md
    2. Current AcoustiForge repository evidence
    3. Explicitly justified architectural reasoning
    4. Future integration considerations

Future requirements may be identified, but MUST NOT silently become
Phase 0 requirements.

---

# 28. Final Required Statement

End the report with exactly:

    PHASE 0 DISCOVERY STATUS: COMPLETE
    PHASE 0 IMPLEMENTATION AUTHORIZATION: NOT REQUESTED

No source code or implementation files should have been created or
modified by this discovery task.