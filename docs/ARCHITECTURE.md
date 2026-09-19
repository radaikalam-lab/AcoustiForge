# AcoustiForge Architecture

## Purpose

AcoustiForge is a hardware-independent computational audio platform.

## ACE

ACE = Acoustic Compute Engine.

Its responsibility is to transform PCM audio according to explicit
processing, acoustic and hardware constraints.

## Signal Path

Source
  |
  v
Transport / Decoder
  |
  v
PCM Contract
  |
  v
ACE Pipeline
  |
  +-- Content Analysis
  +-- Acoustic Profile
  +-- DSP
  +-- Protection
  |
  v
PCM / Digital Audio
  |
  v
DAC or Digital Amplifier
  |
  v
Power Amplifier
  |
  v
Acoustic Transducer

## Architectural Boundary

AcoustiForge owns:

- PCM contracts
- processing graph
- DSP node contracts
- acoustic profiles
- calibration
- system modelling
- measurement
- hardware abstraction

AcoustiForge does not initially own:

- Bluetooth radio
- proprietary codecs
- amplifier silicon
- speaker driver manufacturing
- enclosure manufacturing

## Upstream Foundations

CMSIS-DSP:
DSP computational primitives.

CMSIS-Stream:
streaming/dataflow execution model.

AcoustiForge:
architecture and acoustic intelligence above these foundations.

## Runtime Architecture & Neutrality

AcoustiForge is strictly runtime-neutral. The architecture distinguishes:

1. **ACE Semantic Contracts:** Platform- and language-independent mathematical and audio invariants.
2. **Reference Runtime:** Python 3.12+ / NumPy for high-level simulation, golden-model verification, and test generation.
3. **Embedded / Native Runtime:** Native C/C++ implementations for ARM Cortex-M (CMSIS-DSP), RISC-V, and bare-metal MCU platforms.
4. **Scripting Runtime:** Optional MicroPython integration for dynamic graph configuration on embedded targets.

PCM semantic definitions are decoupled from physical storage representation (raw pointers, circular DMA buffers, static memory pools). See `docs/contracts/RUNTIME_ARCHITECTURE_AMENDMENT_0_1.md`.