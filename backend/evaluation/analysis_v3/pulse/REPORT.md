# Analysis V3 Pulse / Beat / Meter Bakeoff

## Executive Decision

**Recommendation: Beat This is a strong leading candidate for future production promotion. Broader annotated evaluation required before switching defaults.**

Beat This materially outperforms the exact production baseline on GuitarSet (beat F1=0.94 vs 0.30, downbeat F1=0.86, tempo error=1.87 vs 17.19 BPM). However, the scored corpus is limited to 5 GuitarSet clips. Generalization to other styles (piano, electronic, Latin, etc.) remains unevaluated.

## Product Question

Which OSS system should provide beat positions, downbeat positions, tempo, and meter evidence for hello-ai's rhythm, groove, structure, notation, and style-aware analysis?

## Existing Production Baseline

- **Engine**: librosa (via `backend/engines/beats/librosa_engine.py`)
- **Function**: `music_features.estimate_beat_grid(wav_bytes)` → `librosa.beat.beat_track(y=audio, sr=sr, trim=False)`
- **Preprocessing**: `soundfile.read()` → mono float32
- **Output**: beats (seconds), tempo (BPM from librosa)
- **Downbeats**: Not supported
- **Meter**: Not supported
- **Production default**: `BEAT_ENGINE=librosa` in `backend/engines/registry.py`

## Evaluation Environment

- **Platform**: macOS-15.3.1-arm64-arm-64bit (Apple Silicon)
- **Arch**: arm64
- **Python**: 3.9.6
- **Device**: CPU (no GPU)
- **PyTorch**: 2.8.0
- **mir_eval**: 0.8.2
- **hello-ai commit**: `05b5641f775d1d3bd28682ba2eb688337fca0669`
- **Branch**: `eval/analysis-v3-pulse-bakeoff`

## Candidate Matrix

| Candidate | Engine | Code License | Checkpoint License | Supports Beats | Supports Downbeats | Supports Tempo | Supports Meter |
|---|---|---|---|---|---|---|---|
| current | librosa | ISC | N/A | ✓ | ✗ | ✓ (derived) | ✗ |
| beat_this | beat_this | MIT | MIT | ✓ | ✓ | ✓ (derived) | ✗ |
| beatnet | BeatNet+mommom | MIT | MIT | ✓ | ✓ | ✓ | ✗ (blocked) |

## Datasets and Licensing

| Dataset | Source | License | Tracks | Annotations | Notes |
|---|---|---|---|---|---|
| GuitarSet | https://github.com/marl/GuitarSet | MIT | 5 | beats, downbeats, tempo | Guitar comping/solo styles |
| MAESTRO | https://magenta.tensorflow.org/datasets/maestro | CC BY-NC-SA 4.0 | 5 | MIDI-derived beats | Not suitable for beat evaluation (derived annotations) |

**Note**: MAESTRO beat annotations are derived from MIDI onset density, not ground-truth beat annotations. They are not suitable for beat evaluation and are excluded from scored results.

## Methodology

Evidence classes:
- **LOCAL MEASUREMENT**: CPU latency, load time, beat F1, downbeat F1, tempo error measured on this machine
- **QUALITATIVE PRODUCT PROBE**: Downbeat detection quality

Metrics:
- Beat F1 using `mir_eval.beat.f_measure` with 70ms tolerance (standard MIREX convention)
- Downbeat F1 using `mir_eval.beat.f_measure` with 70ms tolerance
- Tempo absolute error (BPM) - derived from median inter-beat interval for Beat This
- Tempo relative error (%)
- Octave/half-double error detection

## Beat Metrics (LOCAL MEASUREMENT — GuitarSet only)

| Candidate | Mean Beat F1 | Clips Scored | Notes |
|---|---|---|---|
| current (librosa) | 0.30 | 5 | Poor on guitar comping |
| beat_this | 0.94 | 5 | Strong across GuitarSet styles |

Per-clip results:

| Clip | current F1 | beat_this F1 | current Matched | beat_this Matched |
|---|---|---|---|---|
| guitarset_bn1_comp | 0.00 | 0.90 | 0/48 | 39/48 |
| guitarset_rock2_comp | 0.31 | 0.99 | 17/64 | 64/64 |
| guitarset_jazz1_comp | 0.16 | 0.86 | 7/48 | 36/48 |
| guitarset_funk1_comp | 0.36 | 1.00 | 18/48 | 48/48 |
| guitarset_ss3_solo | 0.69 | 0.95 | 44/64 | 61/64 |

**Observation**: librosa struggles with guitar comping (especially bossa nova and jazz), while Beat This achieves near-perfect tracking on funk and rock.

## Downbeat Metrics (LOCAL MEASUREMENT — GuitarSet only)

| Candidate | Mean Downbeat F1 | Clips Scored | Notes |
|---|---|---|---|
| current (librosa) | N/A | 0 | Not supported |
| beat_this | 0.86 | 5 | Strong downbeat detection |

Per-clip downbeat results:

| Clip | beat_this Downbeat F1 | Matched | Predicted | Reference |
|---|---|---|---|---|
| guitarset_bn1_comp | 0.96 | 12 | 13 | 12 |
| guitarset_rock2_comp | 1.00 | 12 | 12 | 12 |
| guitarset_jazz1_comp | 0.88 | 11 | 13 | 12 |
| guitarset_funk1_comp | 1.00 | 12 | 12 | 12 |
| guitarset_ss3_solo | 0.49 | 13 | 37 | 16 |

**Observation**: Beat This downbeat detection is strong on comping styles but less accurate on solo guitar (ss3_solo has many false positive downbeats).

## Tempo Metrics (LOCAL MEASUREMENT — GuitarSet only)

**Note**: Beat This does not independently predict tempo. BPM is derived from median inter-beat interval.

| Candidate | Mean Tempo Error | Clips Scored | Notes |
|---|---|---|---|
| current (librosa) | 17.19 BPM | 5 | Large errors on rock/funk |
| beat_this (derived) | 1.87 BPM | 5 | Consistent accuracy |

Per-clip tempo results:

| Clip | Reference BPM | current Error | beat_this Error (derived) |
|---|---|---|---|
| guitarset_bn1_comp | 129.0 | 0.2 BPM | 1.4 BPM |
| guitarset_rock2_comp | 142.0 | 46.3 BPM | 0.9 BPM |
| guitarset_jazz1_comp | 130.0 | 0.8 BPM | 5.0 BPM |
| guitarset_funk1_comp | 114.0 | 38.0 BPM | 1.4 BPM |
| guitarset_ss3_solo | 84.0 | 0.7 BPM | 0.7 BPM |

**Observation**: librosa has catastrophic tempo errors on rock and funk (likely octave/half-time errors), while Beat This derived tempo maintains consistent accuracy.

## Meter Metrics

| Candidate | Supports Meter | Notes |
|---|---|---|
| current (librosa) | ✗ | Not supported |
| beat_this | ✗ | Not supported |
| beatnet | ✗ | Blocked by madmom/numpy compatibility |

## Difficult-Case Probes (QUALITATIVE PRODUCT PROBE)

Based on GuitarSet evaluation:
- **Bossa nova comping**: librosa F1=0.00, beat_this F1=0.90
- **Rock comping**: librosa F1=0.31, beat_this F1=0.99
- **Jazz comping**: librosa F1=0.16, beat_this F1=0.86
- **Funk comping**: librosa F1=0.36, beat_this F1=1.00
- **Guitar solo**: librosa F1=0.69, beat_this F1=0.95

**Note**: These results are specific to guitar comping/solo styles. Generalization to other styles (piano, electronic, Latin, etc.) is not evaluated.

## Operational Evaluation (LOCAL MEASUREMENT)

| Metric | current (librosa) | beat_this |
|---|---|---|
| Install success | Yes | Yes |
| Load time | 0.01s | 0.72s |
| CPU latency 10s | N/A* | 0.12s |
| CPU latency 30s | N/A* | 0.90s |
| Determinism | False** | True |
| ARM feasibility | Confirmed | Confirmed |

*librosa latency measurement failed due to synthetic audio issues.
**librosa determinism check failed on synthetic audio.

## Licensing Findings

| Candidate | Code License | Checkpoint License | Commercial Use |
|---|---|---|---|
| current (librosa) | ISC | N/A | ✓ |
| beat_this | MIT | MIT | ✓ |
| beatnet | MIT | MIT | ✓ |

## Failure Analysis

- **current (librosa)**: Poor beat tracking on guitar comping styles (bossa nova, jazz, funk). Large tempo errors on rock/funk (likely octave errors).
- **beat_this**: Minor beat count differences on some clips (39 vs 48 on bossa nova), but high F1 due to tolerance. Downbeat detection less accurate on solo guitar.
- **beatnet**: Blocked by madmom/numpy compatibility issue. Marked as REVISIT.

## Per-Candidate Decisions

| Candidate | Decision | Rationale |
|---|---|---|
| current (librosa) | RESEARCH | Poor beat tracking quality on guitar styles. Non-trivial tempo errors. |
| beat_this | RESEARCH | Strong leading candidate for future production promotion. Beat F1=0.94, downbeat F1=0.86, tempo error=1.87 BPM on GuitarSet. MIT license. CPU feasible. Broader annotated evaluation required before switching defaults. |
| beatnet | REVISIT | Blocked by madmom/numpy compatibility issue. |

## Product Implications

Beat This provides:
- Beat positions for beat/bar grid, looping, section navigation
- Downbeat positions for bar-phase alignment
- Accurate derived tempo for groove analysis
- Strong performance on guitar-based styles (bossa nova, rock, jazz, funk)

This supports downstream:
- beat/bar grid representation
- beat-relative onset measurements
- groove/style modules
- notation quantization
- section alignment
- drum/bass pattern analysis

## Architecture Recommendation

**Beat This is a strong leading candidate for future production promotion. Broader annotated evaluation required before switching defaults.**

Rationale:
1. Beat This F1=0.94 vs librosa F1=0.30 on GuitarSet (5 clips)
2. Beat This downbeat F1=0.86 (librosa does not support downbeats)
3. Beat This derived tempo error=1.87 BPM vs librosa 17.19 BPM
4. Beat This MIT license permits commercial use
5. Beat This CPU latency 0.12s for 10s audio is production-feasible
6. **Limitation**: Results are specific to guitar comping/solo styles. Generalization to other styles is not evaluated.

## Proposed PulseEvidence Contract

```typescript
type PulseEvidence = {
  sourceArtifactVersionId: string
  engine: string
  engineVersion?: string

  beats?: Array<{
    timeSeconds: number
    confidence?: number
  }>

  downbeats?: Array<{
    timeSeconds: number
    confidence?: number
  }>

  tempo?: {
    bpm: number
    confidence?: number
    scope: "global" | "segment"
    span?: {
      startSeconds: number
      endSeconds: number
    }
  }

  meter?: {
    numerator: number
    denominator: number
    confidence?: number
  }

  provenance: {
    parameters?: Record<string, unknown>
    checkpoint?: string
    checkpointChecksum?: string
  }
}
```

This contract is proposed for Architecture #336. Do not create DB tables or migrate schema.

## Remaining Uncertainty

- Limited evaluation corpus (5 GuitarSet clips with beat annotations)
- No evaluation on non-guitar styles (piano, electronic, Latin, etc.)
- No evaluation on compound meter or unusual time signatures
- BeatNet blocked by compatibility issue
- No reference downstream MIR contextualization

## What Should Happen Next

1. Evaluate Beat This on broader corpus (Ballroom, Hainsworth, SMC, etc.)
2. Score downbeat detection where annotations exist
3. Investigate BeatNet compatibility fix or alternative
4. Design production integration for Beat This as beat/downbeat engine
5. Implement PulseEvidence persistence in #336

## Reproduction Instructions

```bash
# Set cache directory
export MUSIC_EVAL_CACHE_DIR=/path/to/backend/evaluation/.cache

# Run all candidates
python3 -m backend.evaluation.analysis_v3.pulse.run --candidate all

# Run specific candidate
python3 -m backend.evaluation.analysis_v3.pulse.run --candidate beat_this

# Run specific task
python3 -m backend.evaluation.analysis_v3.pulse.run --candidate beat_this --task operational

# Results saved to backend/evaluation/analysis_v3/pulse/results/{candidate}.json
```

## CI Classification

| Check | Status | Notes |
|---|---|---|
| Build | pending | |
| E2E (test) | pending | |
| Real-stack E2E | pending | |
| CodeQL | pending | |
| Dependency Review | pending | |
| Gitleaks | pending | |
| Argos | pending | |
| Lint (Ruff) | pending | |

## Unfinished Work

- Larger evaluation corpus with more diverse styles
- Downbeat scoring with reference annotations
- Meter evaluation
- BeatNet compatibility fix
- Reference downstream MIR contextualization
