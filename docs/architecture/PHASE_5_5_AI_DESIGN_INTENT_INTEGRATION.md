# AcoustiForge Phase 5-5: AI Design-Intent Integration

**Governing Invariant:**
> *AI proposes. AcoustiForge validates and executes.*
> 
> *AI is advisory and produces untrusted design intent. AcoustiForge validates the intent and remains the authoritative acoustic computation layer.*

---

## 1. Architectural Overview

Phase 5-5 introduces an optional, decoupled integration boundary connecting natural language or high-level AI design intent to AcoustiForge's deterministic Core optimization and execution pipeline.

The AI layer is intentionally decoupled from core acoustic computing. It is an advisory metadata producer that constructs high-level `DesignIntent` data structures. These proposals are subjected to a strict 4-stage validation firewall before any existing Core specification (`OptimizationSpecification` or Track C `MultiPositionOptimizationSpecification`) is generated.

```
                 ┌─────────────────────────────────┐
                 │     Natural Language / AI       │
                 │          (Advisory)             │
                 └────────────────┬────────────────┘
                                  │ Proposes
                                  ▼
                 ┌─────────────────────────────────┐
                 │          DesignIntent           │
                 │   (Untrusted High-Level Data)   │
                 └────────────────┬────────────────┘
                                  │
                                  ▼
                 ┌─────────────────────────────────┐
                 │       VALIDATION FIREWALL       │
                 │  - Schema & Finite Type Checks  │
                 │  - Semantic & Boundary Checks   │
                 │  - Acoustic Constraint Checks   │
                 │  - Closed-World Preset Check    │
                 └────────────────┬────────────────┘
                                  │ Compiles & Validates
                                  ▼
                 ┌─────────────────────────────────┐
                 │   Deterministic Specification   │
                 │    (Existing Core Contracts)    │
                 └────────────────┬────────────────┘
                                  │
                                  ▼
                 ┌─────────────────────────────────┐
                 │       ACOUSTIFORGE CORE         │
                 │    (Authoritative & Frozen)     │
                 │  - optimize_two_way()           │
                 │  - optimize_multi_position()    │
                 └────────────────┬────────────────┘
                                  │
                                  ▼
                 ┌─────────────────────────────────┐
                 │      OptimizationResult         │
                 └────────────────┬────────────────┘
                                  │
                                  ▼
                 ┌─────────────────────────────────┐
                 │   Deterministic ComputeGraph    │
                 └────────────────┬────────────────┘
                                  │
                                  ▼
                 ┌─────────────────────────────────┐
                 │      PCM Audio Execution        │
                 │  - OfflineExecutionBackend      │
                 │  - AlsaExecutionBackend         │
                 └─────────────────────────────────┘
```

---

## 2. Trust Boundary & Security Isolation

AcoustiForge treats all external AI output strictly as **untrusted, advisory data**:
1. **No Code Execution**: Natural language text and provider proposals are strictly parsed into immutable dataclass structures. They are never interpreted as Python code, shell commands, or dynamic expressions.
2. **No Graph Mutation or Node Injection**: AI cannot create graph nodes, inject arbitrary DSP/biquad filter coefficients, or mutate an existing `ComputeGraph`.
3. **No Direct Hardware Access**: The intent layer has no access to audio hardware handles, ALSA bindings, or execution threads.
4. **No Core Mutation**: The intent package imports existing Core domain contracts (`CrossoverSpecification`, `AcousticTargetCurve`, `OptimizationSpecification`, etc.) as an unprivileged client. Core remains 100% functional and importable without importing the intent module.
5. **Fail-Closed Validation**: If an intent contains NaN, infinities, out-of-range acoustic parameters, conflicting bounds, or unsupported target presets, the adapter raises an explicit `IntentValidationError` or `UnsupportedIntentError`.

---

## 3. DesignIntent Data Contracts

The intent data layer lives in `acoustiforge.intent.contracts` and contains small, focused, frozen dataclasses:

| Contract | Purpose | Boundary Invariants |
|---|---|---|
| `TargetCurveIntent` | High-level acoustic target goal (`flat`, `custom_anchors`). | Rejects non-existent presets (e.g. `harman_loudspeaker`, `diffuse_field`) as unsupported. |
| `TonalBalanceIntent` | Semantic adjustments (`warmth_db`, `brightness_db`, `low_shelf_db`, `high_shelf_db`, `tilt_db_per_octave`). | Strict magnitude safety envelope (±24 dB) and finite float checks. |
| `CrossoverIntent` | User crossover guidance (target frequency, search band, family, order). | Constrained to Linkwitz-Riley and Butterworth orders 2 and 4. |
| `SpatialIntent` | Spatial preference (`single_position`, `primary_seat_weighted`, `uniform_spatial_balance`). | Directly maps to Track C multi-position optimization with automatic weight normalization. |
| `ConstraintIntent` | Compute constraints (`max_iterations`, `spl_tolerance_db`, `max_delay_samples`). | Bounded strictly to existing Core optimizer tolerances. |
| `DesignIntent` | Immutable top-level container holding sub-intents and query metadata. | Complete immutability via `frozen=True`. |
| `IntentTranslationRecord` | Comprehensive audit trail of translation, validation status, accepted/rejected items, and output specification. | Purely descriptive; does not make false claims of cryptographic/content-addressed provenance. |

---

## 4. Provider Abstraction

The provider interface (`IDesignIntentProvider`) is a standard Python `typing.Protocol`. It requires zero external dependencies (no OpenAI SDK, Anthropic SDK, LangChain, or network clients).

```python
class IDesignIntentProvider(Protocol):
    def propose_intent(self, query: str, context: Optional[Mapping[str, Any]] = None) -> DesignIntent: ...
```

`MockDesignIntentProvider` implements a narrow, deterministic mock provider that parses controlled queries (e.g. `"flat target"`, `"2 kHz crossover"`, `"prioritize primary listening position"`) for local testing and CI/CD without network access.

---

## 5. Validation Firewall & Translation Adapter

The `DesignIntentAdapter.compile()` method implements the 4-stage validation firewall:
1. **Schema & Finite Type Validation**: Ensures all inputs are valid `DesignIntent` instances and all numeric values are strictly finite `float` / `int` instances.
2. **Semantic & Boundary Checks**: Confirms that frequency bounds are ordered ($f_{\min} < f_{\max}$), orders are supported, and spatial weights are strictly positive.
3. **Acoustic Constraint Validation**: Ensures crossover search bands fall within valid acoustic ranges (20 Hz – 20 kHz) and tolerances do not conflict.
4. **Canonical Specification Generation**:
   - Synthesizes `AcousticTargetCurve` with deterministic logarithmic grid interpolation and tonal shelf/tilt modifiers.
   - If spatial measurement positions are provided, compiles directly into Track C's `MultiPositionOptimizationSpecification`.
   - If single driver data is provided, compiles directly into Core `OptimizationSpecification`.
   - Produces an `IntentTranslationRecord` documenting the audit outcome.

---

## 6. Track C Spatial Optimization Integration

When `spatial_positions` are provided, the adapter translates `SpatialIntent` into `MultiPositionOptimizationSpecification` without modifying `src/acoustiforge/extensions/spatial_optimization.py`.

Spatial weighting profiles:
- `uniform_spatial_balance`: Uniform weights $\frac{1}{N}$ across all measurement positions.
- `primary_seat_weighted` / `single_position`: Prioritizes the first (primary) position (0.7) and divides remaining weight (0.3) among secondary positions.
- All weights are strictly normalized such that $\sum w_i = 1.0$.

---

## 7. Determinism Boundary & Analytical Golden Parity

AcoustiForge maintains a strict distinction between AI advisory proposals and deterministic computation:

```
Known Controlled Input
       │
       ├── AI Path: MockProvider ──→ DesignIntent ──→ Adapter ──→ Specification A
       │
       └── Direct Path: Canonical Python Factory ───────────────→ Specification B
```

The analytical golden test (`test_independent_golden_parity_between_ai_path_and_direct_path`) verifies:
1. **Contract-Level Equality**: `Specification A == Specification B` across crossover family, order, target curve points, and constraints.
2. **Execution Parity**: Running both specifications through the deterministic optimizer yields exact mathematical parity in loss, metrics, and filter states.

---

## 8. Implemented vs Deferred Capabilities

### Implemented
- Immutable, validated `DesignIntent` contracts (`TargetCurveIntent`, `TonalBalanceIntent`, `CrossoverIntent`, `SpatialIntent`, `ConstraintIntent`).
- Deterministic, zero-dependency `IDesignIntentProvider` and `MockDesignIntentProvider`.
- 4-stage Validation Firewall and `DesignIntentAdapter`.
- Track C Multi-Position Optimization translation.
- `IntentTranslationRecord` audit trail.
- Full end-to-end integration: AI Intent $\to$ Adapter $\to$ Track C Optimizer $\to$ ComputeGraph $\to$ PCM Offline Execution.
- Independent Analytical Golden Parity test suite.

### Deferred
- **Unverified Target Presets**: `harman_loudspeaker` and `diffuse_field` presets were not present in the repository and were deferred rather than inventing synthetic target curves. The firewall explicitly rejects them as `UnsupportedIntentError`.
- **Cryptographic Provenance**: `IntentTranslationRecord` records translation audit metadata but does not claim cryptographic hashing or distributed artifact identity.
- **Dynamic DSP Filter Topologies**: AI is strictly prohibited from inventing arbitrary filter chains or topologies outside the validated Core builders.
