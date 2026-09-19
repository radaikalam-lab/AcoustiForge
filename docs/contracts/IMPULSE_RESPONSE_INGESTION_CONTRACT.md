# AcoustiForge Normative Contract: Time-Domain Impulse Response Ingestion
## Contract Identifier: `CONTRACT-IR-INGESTION-01`

---

## 1. Purpose & Architectural Boundary

This contract governs the ingestion, decoding, and validation of time-domain acoustic impulse response files (uncompressed RIFF/WAVE files and ASCII time/sample text exports) into AcoustiForge's immutable Phase 3B domain object [ImpulseResponseData](file:///E:/AcoustiForge/src/acoustiforge/domain/measurements.py#L70-L121).

The ingestion pipeline is strictly an **offline control-plane input boundary**:
$$\text{External File (.wav, .txt, .csv, .ir)} \xrightarrow{\text{Impulse Parser}} \text{ImpulseResponseData}$$

### Architectural Invariants:
1. **Offline Only:** Ingestion executes in the offline control plane (`src/acoustiforge/io/`).
2. **Zero DSP / Execution Impact:** Ingestion MUST NOT execute realtime audio processing, run `ComputeGraph`, or modify DSP node contracts.
3. **Zero Third-Party Audio Dependencies:** Parsing MUST use only the Python Standard Library (`struct`, `io`, `pathlib`, `math`, `wave`) and NumPy (`np.ndarray`). No `scipy`, `soundfile`, `librosa`, `pyaudio`, or `sounddevice`.
4. **Immutability:** Produces an immutable [ImpulseResponseData](file:///E:/AcoustiForge/src/acoustiforge/domain/measurements.py#L70-L121) instance with owned, read-only 1D float64 NumPy array buffers.

---

## 2. Supported File Formats & Encoding Specifications

### 2.1 RIFF / WAVE Binary Format (`.wav`)

The parser supports standard RIFF/WAVE uncompressed audio containers:

| Format Code | Encoding | Bit Depth | Channel Support | Decoding Policy |
| :--- | :--- | :--- | :--- | :--- |
| `0x0001` (`WAVE_FORMAT_PCM`) | Signed Integer Linear PCM | 16-bit | Mono / Multi-channel | Little-endian signed 16-bit integer divided by $32768.0$ $\to$ float64 range $[-1.0, 32767/32768]$. |
| `0x0001` (`WAVE_FORMAT_PCM`) | Signed Integer Linear PCM | 24-bit | Mono / Multi-channel | Little-endian 3-byte integer with sign extension divided by $8388608.0$ $\to$ float64 range $[-1.0, 8388607/8388608]$. |
| `0x0001` (`WAVE_FORMAT_PCM`) | Signed Integer Linear PCM | 32-bit | Mono / Multi-channel | Little-endian signed 32-bit integer divided by $2147483648.0$ $\to$ float64 range $[-1.0, 2147483647/2147483648]$. |
| `0x0003` (`WAVE_FORMAT_IEEE_FLOAT`) | IEEE 754 Floating-Point | 32-bit | Mono / Multi-channel | Little-endian 32-bit float cast directly to float64. |
| `0xFFFE` (`WAVE_FORMAT_EXTENSIBLE`) | Sub-format GUID | 16/24/32-bit | Mono / Multi-channel | Decodes PCM or IEEE Float sub-format matching GUID. |

*Multi-Channel Handling:*
- Multi-channel files accept an explicit parameter `channel_index: int = 0`.
- De-interleaves frames and extracts the specified channel.
- If `channel_index < 0` or `channel_index >= num_channels`, raises `InvalidParameterError`.

*Pure-Python Parsing Rule:*
- Standard library `wave` module natively rejects format `0x0003` (`IEEE_FLOAT`) and `0xFFFE`.
- Therefore, the implementation must utilize a pure-Python RIFF chunk scanner using `struct` and `io` to decode chunks (`RIFF`, `fmt `, `data`) deterministically.

### 2.2 ASCII Tabular Text Impulse Format (`.txt`, `.csv`, `.ir`, `.tim`)

The parser supports ASCII time-domain exports (e.g. from REW, ARTA, CLIO):

1. **Two-Column Time-Amplitude Layout:**
   - Columns: `[Time (seconds or ms), Amplitude]`
   - Time coordinates must be strictly monotonically increasing with uniform spacing $\Delta t$.
   - Sample rate derived as $f_s = \text{round}(1.0 / \Delta t)$.
2. **Single-Column Sample-Amplitude Layout:**
   - Column: `[Amplitude]`
   - Requires explicit `sample_rate: int` in parse call.
3. **Delimiter & Comment Rules:**
   - Delimiters: Comma (`,`), Semicolon (`;`), Whitespace (spaces/tabs).
   - Comments: Lines beginning with `#`, `*`, `//`, or non-numeric semicolon lines are ignored.

---

## 3. Data Invariants & Semantic Constraints

### 3.1 Sample Rate Invariants ($f_s$)
1. Must be a positive integer $f_s \in [8000, 384000]\text{ Hz}$.
2. Non-positive, zero, or non-finite sample rates raise `InvalidMeasurementDataError`.

### 3.2 Time-Domain Samples ($h[n]$)
1. **Finiteness:** Every sample $h[n]$ must be a real finite number. NaNs and infinities ($\pm \infty$) raise `InvalidMeasurementDataError`.
2. **Non-Emptiness:** Impulse response must contain at least $N \ge 16$ samples.
3. **Peak Detection:**
   - Automatically detects absolute maximum:
     $$n_{\text{peak}} = \min \{ n \mid |h[n]| = \max_{k} |h[k]| \}$$
   - In case of identical peaks, the earliest sample index is chosen.
   - User-supplied `peak_index` overrides automatic detection, validated to $0 \le \text{peak\_index} < N$.

---

## 4. Ingestion Error Taxonomy

All impulse ingestion exceptions inherit from `MeasurementIngestionError` ([exceptions.py](file:///E:/AcoustiForge/src/acoustiforge/io/exceptions.py)):

```text
AcoustiForgeError (from contracts/validation.py)
  └── MeasurementIngestionError
        ├── UnsupportedMeasurementFormatError  # Compressed WAV (MP3, ADPCM), unknown format tags
        ├── MalformedMeasurementDataError      # Corrupt RIFF headers, truncated data chunks, jagged text
        └── InvalidMeasurementDataError        # Non-positive sample rates, NaN/Inf samples, empty buffers
```

---

## 5. Verification & Acceptance Criteria

1. **Golden WAV Vectors:** Exact bit-level verification of 16-bit, 24-bit, and 32-bit float synthetic impulse files.
2. **Analytical Signal Conformance:** Dirac delta ($h[0]=1.0$) and delayed delta ($h[D]=1.0$) ingested bit-exact.
3. **Rejection Suite:** Clean rejection of compressed WAVs, corrupt headers, NaN floats, non-monotonic time columns, and out-of-range channel indices.
