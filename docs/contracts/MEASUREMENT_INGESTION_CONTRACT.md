# AcoustiForge Normative Contract: Measurement File Ingestion
## Contract Identifier: `CONTRACT-MEASUREMENT-INGESTION-01`

---

## 1. Purpose & Architectural Role

This contract governs the ingestion and parsing of external acoustic frequency-response measurement text files into AcoustiForge's immutable Phase 3B domain object (`FrequencyResponseData`).

The ingestion pipeline is strictly an **offline control-plane input boundary**:
$$\text{External File (.frd, .csv, .txt)} \xrightarrow{\text{Ingestion Parser}} \text{FrequencyResponseData}$$

### Scope Constraint
- **Phase 4A Scope:** **`FrequencyResponseData` ONLY.**
- **Deferred:** Time-domain impulse response file parsing (`ImpulseResponseData`) is explicitly deferred to a future phase.

The ingestion layer:
- Resides purely in the input plane (`src/acoustiforge/io/`).
- MUST NOT be imported or referenced by `graph/`, `nodes/`, `engine/`, or `contracts/pcm.py`.
- MUST NOT execute realtime DSP or mutate existing domain instances.
- MUST NOT introduce third-party parsing dependencies (Pandas, SciPy, Librosa). Standard library (`csv`, `io`, `pathlib`, `re`) + NumPy only.

---

## 2. Supported Input File Formats

The parser supports three canonical tabular text formats:

1. **FRD Format (`.frd`):**
   - Standard ASCII loudspeaker frequency response format.
   - Whitespace-delimited (spaces or tabs).
   - 2 columns `[Freq(Hz), Mag(dB)]` or 3 columns `[Freq(Hz), Mag(dB), Phase(deg)]`.
2. **CSV Tabular Format (`.csv`):**
   - Comma-delimited (`,`) or semicolon-delimited (`;`) numerical data.
   - Optional single header row (e.g. `Frequency, Magnitude, Phase`).
3. **General ASCII Text / REW Export (`.txt`):**
   - Plain text export from Room EQ Wizard (REW), ARTA, SoundEasy, CLIO, or HolmImpulse.
   - Header lines prefixed by `#`, `*`, `;`, or `//`.

*Unsupported formats:* Binary proprietary files (.mdat, .pir, .zma, .cal-binary) are NOT supported in Phase 4A and must fail explicitly with `UnsupportedMeasurementFormatError`.

---

## 3. Input Invariants & Semantic Constraints

### 3.1 Frequency Invariants ($f$)
1. **Positivity:** Every frequency sample must be strictly positive: $f_i > 0.0\text{ Hz}$.
2. **Finiteness:** Every frequency must be a real finite floating-point number. NaNs, $+\infty$, and $-\infty$ are strictly rejected.
3. **Monotonicity:** Frequencies must be strictly monotonically ascending:
   $$f_{i+1} > f_i \quad \forall i \in [0, N-2]$$
   Decreasing frequencies or duplicate frequency points ($f_{i+1} == f_i$) are strictly rejected with `InvalidMeasurementDataError`.
4. **Non-Emptiness:** The dataset must contain at least $N \ge 2$ valid coordinate rows.

### 3.2 Magnitude Invariants ($M$)
1. **Finiteness:** Every magnitude value must be finite. NaNs, $+\infty$, and $-\infty$ are strictly rejected with `InvalidMeasurementDataError`.
2. **Unit Standard:** Magnitude values represent SPL or transfer function magnitude in decibels ($\text{dB}$).

### 3.3 Phase Semantics ($\phi$)
1. **Optional Presence:** If a 3rd column is present, it is parsed as phase in degrees ($\text{deg}$). If absent, phase is `None`.
2. **Finiteness:** If present, all phase values must be finite numbers.
3. **Conversion to Radians:** The parser converts degrees to radians ($\phi_{\text{rad}} = \phi_{\text{deg}} \times \frac{\pi}{180}$) for storage in canonical `FrequencyResponseData(phase_rad=...)`.
4. **No Implicit Phase Manipulation:** Phase values are preserved as supplied. The parser MUST NOT perform arbitrary phase unwrapping, minimum-phase derivation, or time-of-flight phase stripping.

---

## 4. Deterministic Parsing & Semicolon Precedence Rules

### 4.1 Semicolon Comment vs. Delimiter Precedence Rule
To eliminate ambiguity between semicolon-delimited CSV rows and semicolon-prefixed comments:
1. **Leading Whitespace:** Stripped prior to evaluation.
2. **Non-Ambiguous Comments:** Lines beginning with `#`, `*`, or `//` are unconditionally treated as comments.
3. **Semicolon Precedence:**
   - When inspecting a line starting with `;`:
     - If the line contains semicolon-separated tokens that parse as a valid numerical row (e.g. `100.0;85.2;0.0`), it is treated as a **valid data row** under the semicolon delimiter.
     - If the line contains non-numeric textual characters following the `;` (e.g. `; Measurement Export Date 2026`), it is treated as a **comment line** and skipped.
   - This ensures valid European-style semicolon CSV files are never corrupted by comment stripping.

### 4.2 Parsing Sequence
1. **Encoding:** Input text is decoded as UTF-8 (fallback to ASCII). Non-decodable byte sequences raise `MalformedMeasurementDataError`.
2. **Blank Lines:** Empty lines and whitespace-only lines are ignored.
3. **Delimiter Detection:** Inspects candidate lines to identify comma (`,`), semicolon (`;`), or whitespace (spaces/tabs).
4. **Header Handling:** The first non-comment line containing non-numeric alphabetic headers (e.g. `"Freq"`, `"SPL"`, `"deg"`) is skipped.
5. **Data Row Extraction:**
   - Numerical tokens are extracted per row.
   - Column counts must be consistent across all rows (all 2-column or all 3-column).
   - Jagged rows or non-numeric tokens within data blocks raise `MalformedMeasurementDataError`.
6. **Target Construction:** Assembles contiguous 1D float64 NumPy arrays and instantiates `FrequencyResponseData(frequencies_hz=..., magnitude_db=..., phase_rad=...)`.

---

## 5. Ingestion Error Taxonomy

All ingestion errors inherit from `MeasurementIngestionError`:

```
AcoustiForgeError (from contracts/validation.py)
  └── MeasurementIngestionError
        ├── UnsupportedMeasurementFormatError  # Unknown extension or binary file
        ├── MalformedMeasurementDataError      # Corrupt text, jagged columns, non-numeric rows
        └── InvalidMeasurementDataError        # Non-positive, non-ascending, NaN/Inf values
```

---

## 6. Verification & Conformance Criteria

1. **Golden Files:** Ingestion must pass bit-exact / numerically equivalent checks on frozen reference fixture files.
2. **Rejection Suite:** Must cleanly reject:
   - Empty files
   - Single-point files
   - Non-monotonic frequencies
   - Duplicate frequencies
   - NaN / Inf values
   - Missing delimiters / jagged rows
   - Binary files
