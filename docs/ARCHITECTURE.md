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