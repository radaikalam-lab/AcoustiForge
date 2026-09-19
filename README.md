# AcoustiForge

**AcoustiForge** is a hardware-independent computational audio platform.

The core computational layer is the **Acoustic Compute Engine (ACE)**, responsible for transforming PCM audio streams according to explicit acoustic profiles, system models, and processing constraints.

## Architecture

```
Source -> Transport/Decoder -> [PCM Contract] -> ACE Pipeline -> [PCM Output] -> DAC -> Amplification -> Transducer
```

### Phase 0: Canonical PCM Contract and Pass-Through

Phase 0 establishes:
- The canonical in-memory `float32` planar PCM contract (`PCMBlock`, `AudioMetadata`).
- Deterministic negative validation and typed exception hierarchy.
- The `BaseProcessingNode` interface.
- The bit-exact, zero-latency `PassThroughNode`.
- The sequential `ReferencePipeline` execution path.
- Complete contract, numerical, determinism, and dependency isolation test suites.

## Quickstart

### Installation (Development)

```bash
pip install -e .[dev]
```

### Running Tests

```bash
pytest -v
```

## Governance

All phases are normatively governed by `prompts/MASTER_PROMPT.md`.
