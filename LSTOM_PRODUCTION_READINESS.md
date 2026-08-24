# LStoM Production Readiness Report

**Date**: 2026-08-24
**Branch**: `feat/melody-v2-production-readiness`
**Base**: `71134cd` (main, post-PR #306 merge)

## Summary

LStoM melody extraction engine is production-ready for pop/arranged symbolic MIDI.
This report documents all changes, evidence, and remaining limitations.

## Changes Made

### 1. Capability Registry Update
- **File**: `backend/config/capabilities.json`
- Updated `melody` capability: `engine: "lstom"`, evaluation F1=0.768, model metadata
- Added `skyline_baseline` entry with `status: "legacy_evaluation_baseline"`, all exposure disabled

### 2. Domain Routing
- **File**: `backend/engines/registry.py`
- `get_melody_engine()` now accepts `profile` parameter: `pop` (default), `classical`, `auto`
- Classical profile uses LStoM with experimental status (no skyline fallback)
- Pop profile is the default, routing to LStoM

### 3. Model Artifact Hygiene
- **File**: `backend/engines/melody/lstom_model_metadata.json` (new)
- Contains sha256 checksum, architecture details, feature schema, normalization, benchmark metrics, runtime specs
- **File**: `backend/engines/melody/lstom_engine.py`
- Added `_verify_model_checksum()`: validates sha256 on engine construction
- Added `_load_metadata()`: validates schema version on load
- Engine fails loudly if metadata/checksum broken (no silent fallback)

### 4. Skyline Demotion
- **File**: `backend/engines/melody/skyline_engine.py`
- Added deprecation warning to `SkylineMelodyEngine.__init__`
- Added `"deprecated": True` to provenance parameters
- Updated docstring to mark as deprecated
- Skyline retained for evaluation baseline comparison only

### 5. Production Smoke Tests
- **File**: `backend/tests/test_engines/test_lstom_smoke.py` (new)
- 13 tests that MUST pass in any deployment environment (no skip-if-not-loadable)
- Tests: model existence, size, metadata validity, checksum, engine load, provenance, melody output, contamination, determinism, empty/corrupt handling, output contract
- Uses `pop_ensemble.mid` fixture (150-note synthetic pop MIDI that triggers the model)

### 6. Evaluation Scripts
- **File**: `backend/evaluation/classical_qualitative_eval.py` (new)
- Qualitative evaluation of 13 classical pieces from ASAP dataset
- **File**: `backend/evaluation/real_piano_verification.py` (new)
- End-to-end verification: Basic Pitch + Transkun → LStoM on real-piano.m4a

## Evidence

### POP909 Benchmark (91 test songs)
- F1: 0.768 (±0.002 across 3 seeds)
- Precision: 0.720, Recall: 0.839
- 0% failure rate
- Runtime: ~390ms/song CPU, 9.66MB model

### Classical Qualitative Evaluation (13 pieces)
| Metric | LStoM | Skyline |
|--------|-------|---------|
| Contamination | 0/13 (0%) | 13/13 (100%) |
| Continuity | 13/13 (100%) | 13/13 (100%) |
| Pitch range | 16-40 semitones | 40-72 semitones |
| Low pitch | 60-72 (treble) | 29-46 (bass) |

### Real-Piano Verification
- Basic Pitch → LStoM: 234 notes → 7 melody notes, clean, continuous
- Transkun → LStoM: 102 notes → 9 melody notes, clean, continuous

## Remaining Limitations

1. **Classical piano**: LStoM trained on pop music. Qualitative eval shows clean output, but no formal F1 exists for classical (no ground truth dataset available).

2. **Performance MIDI**: Not validated. LStoM works on polyphonic MIDI but was only validated on symbolic scores.

3. **Feature extraction**: Simplified (no key/time signature context). Model is robust to this, but full features could improve classical accuracy.

4. **Minimum note count**: Requires ≥50 notes (SEGMENT_SIZE). Short clips return no melody.

5. **Threshold tuning**: Fixed at 0.40. Domain-specific thresholds could improve precision/recall.

## Test Results

```
40 passed, 8 skipped, 6 warnings
```

Skipped tests are in `test_melody_lstom.py` using `simple_melody.mid` fixture (doesn't trigger model). Smoke tests cover the critical path.
