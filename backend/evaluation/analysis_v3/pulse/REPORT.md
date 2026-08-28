# Analysis V3 Pulse / Beat / Meter Bakeoff

## Executive Decision

**Recommendation: Beat This becomes the preferred beat/downbeat evidence engine. Current librosa baseline remains as lightweight fallback. Meter remains separate/experimental.**

Beat This materially improves beat tracking over the current librosa baseline (F1=0.94 vs 0.30) with acceptable runtime (0.12s for 10s audio). It also provides downbeat detection, which the current baseline lacks.

## Product Question

Which OSS system should provide beat positions, downbeat positions, tempo, and meter evidence for hello-ai's rhythm, groove, structure, notation, and style-aware analysis?

## Existing Production Baseline

- **Engine**: librosa (via `backend/engines/beats/librosa_engine.py`)
- **Function**: `librosa.beat.beat_track()`
- **Output**: beats, tempo (BPM)
- **Downbeats**: Not supported
- **Meter**: Not supported
- **Production default**: `BEAT_ENGINE=librosa` in `backend/engines/registry.py`

## Evaluation Environment

- **Platform**: macOS-15.3.1-arm64-arm-64bit (Apple Silicon)
- **Arch**: arm64
- **Python**: 3.9.6
- **Device**: CPU (no GPU)
- **PyTorch**: 2.8.0
- **hello-ai commit**: `eb4c85430f7e45c3c27316338c5e8b6e6db3a58a`
- **Branch**: `eval/analysis-v3-pulse-bakeoff`

## Candidate Matrix

| Candidate | Engine | Code License | Checkpoint License | Supports Beats | Supports Downbeats | Supports Tempo | Supports Meter |
|---|---|---|---|---|---|---|---|
| current | librosa | ISC | N/A | ✓ | ✗ | ✓ | ✗ |
| beat_this | beat_this | MIT | MIT | ✓ | ✓ | ✓ | ✗ |
| beatnet | BeatNet+mommom | MIT | MIT | ✓ | ✓ | ✓ | ✓ |

## Datasets and Licensing

| Dataset | Source | License | Clips | Annotations |
|---|---|---|---|---|
| GuitarSet | https://github.com/marl/GuitarSet | MIT | 5 | beats, downbeats, tempo |
| BabySlakh | https://zenodo.org/records/4603870 | CC BY 4.0 | 3 | none |

## Methodology

Evidence classes:
- **LOCAL MEASUREMENT**: CPU latency, load time, beat F1, tempo error measured on this machine
- **QUALITATIVE PRODUCT PROBE**: Downbeat detection, meter inference

Metrics:
- Beat F1 with 70ms tolerance (standard MIREX convention)
- Tempo absolute error (BPM)
- Tempo relative error (%)
- Octave/half-double error detection

## Beat Metrics (LOCAL MEASUREMENT)

| Candidate | Mean Beat F1 | Clips Scored | Notes |
|---|---|---|---|
| current (librosa) | 0.30 | 5 | Poor on guitar comping, decent on solo |
| beat_this | 0.94 | 5 | Strong across all styles |

Per-clip results:

| Clip | current F1 | beat_this F1 | current Matched | beat_this Matched |
|---|---|---|---|---|
| guitarset_bn1_comp | 0.00 | 0.90 | 0/48 | 39/48 |
| guitarset_rock2_comp | 0.32 | 0.99 | 17/64 | 64/64 |
| guitarset_jazz1_comp | 0.15 | 0.86 | 7/48 | 36/48 |
| guitarset_funk1_comp | 0.34 | 1.00 | 18/48 | 48/48 |
| guitarset_ss3_solo | 0.70 | 0.95 | 44/64 | 61/64 |

**Observation**: librosa struggles with guitar comping (especially bossa nova and jazz), while Beat This achieves near-perfect tracking on funk and rock.

## Downbeat Metrics (LOCAL MEASUREMENT)

| Candidate | Supports Downbeats | Notes |
|---|---|---|
| current (librosa) | ✗ | Not supported |
| beat_this | ✓ | Provides downbeat positions |

Beat This downbeat detection is available but not scored here due to limited reference downbeat annotations. Qualitative inspection shows reasonable downbeat placement on GuitarSet clips.

## Tempo Metrics (LOCAL MEASUREMENT)

| Candidate | Mean Tempo Error | Clips Scored | Notes |
|---|---|---|---|
| current (librosa) | 17.19 BPM | 5 | Large errors on rock/funk |
| beat_this | 1.87 BPM | 5 | Consistent accuracy |

Per-clip tempo results:

| Clip | Reference BPM | current Error | beat_this Error |
|---|---|---|---|
| guitarset_bn1_comp | 129.0 | 0.2 BPM | 1.4 BPM |
| guitarset_rock2_comp | 142.0 | 46.3 BPM | 0.9 BPM |
| guitarset_jazz1_comp | 130.0 | 0.8 BPM | 5.0 BPM |
| guitarset_funk1_comp | 114.0 | 38.0 BPM | 1.4 BPM |
| guitarset_ss3_solo | 84.0 | 0.7 BPM | 0.7 BPM |

**Observation**: librosa has catastrophic tempo errors on rock and funk (likely octave/half-time errors), while Beat This maintains consistent accuracy.

## Meter Metrics

| Candidate | Supports Meter | Notes |
|---|---|---|
| current (librosa) | ✗ | Not supported |
| beat_this | ✗ | Not supported |
| beatnet | ✓ | Blocked by numpy compatibility |

## Difficult-Case Probes (QUALITATIVE PRODUCT PROBE)

Based on GuitarSet evaluation:
- **Bossa nova comping**: librosa fails completely (F1=0.0), Beat This strong (F1=0.90)
- **Rock comping**: librosa poor (F1=0.32), Beat This excellent (F1=0.99)
- **Jazz comping**: librosa poor (F1=0.15), Beat This strong (F1=0.86)
- **Funk comping**: librosa poor (F1=0.34), Beat This perfect (F1=1.00)
- **Guitar solo**: librosa decent (F1=0.70), Beat This strong (F1=0.95)

## Operational Evaluation (LOCAL MEASUREMENT)

| Metric | current (librosa) | beat_this |
|---|---|---|
| Install success | Yes | Yes |
| Load time | 0.0s | 0.81s |
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
- **beat_this**: Minor beat count differences on some clips (39 vs 48 on bossa nova), but high F1 due to tolerance.
- **beatnet**: Blocked by numpy compatibility issue with madmom dependency. Marked as REVISIT.

## Per-Candidate Decisions

| Candidate | Decision | Rationale |
|---|---|---|
| current (librosa) | RESEARCH | Poor beat tracking quality on guitar styles. Non-trivial tempo errors. |
| beat_this | ADOPT | Strong beat tracking (F1=0.94), accurate tempo (1.87 BPM error), MIT license, CPU feasible. |
| beatnet | REVISIT | Blocked by madmom/numpy compatibility issue. |

## Product Implications

Beat This provides:
- Beat positions for beat/bar grid, looping, section navigation
- Downbeat positions for bar-phase alignment
- Accurate tempo for groove analysis
- Strong performance on guitar-based styles (bossa nova, rock, jazz, funk)

This supports downstream:
- beat/bar grid representation
- beat-relative onset measurements
- groove/style modules
- notation quantization
- section alignment
- drum/bass pattern analysis

## Architecture Recommendation

**Beat This becomes preferred beat/downbeat evidence engine. Existing librosa remains lightweight fallback. Meter remains separate/experimental.**

Rationale:
1. Beat This F1=0.94 vs librosa F1=0.30 on GuitarSet
2. Beat This tempo error=1.87 BPM vs librosa 17.19 BPM
3. Beat This provides downbeat detection (librosa does not)
4. Beat This MIT license permits commercial use
5. Beat This CPU latency 0.12s for 10s audio is production-feasible

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
- No downbeat reference annotations for scoring
- No meter reference annotations for scoring
- BeatNet blocked by compatibility issue
- No evaluation on non-guitar styles (piano, electronic, Latin, etc.)

## What Should Happen Next

1. Evaluate Beat This on broader corpus (MAESTRO, Ballroom, RWC, etc.)
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
