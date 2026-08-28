# Analysis V3 Source Separation Bakeoff

## Executive Decision

**Recommendation: Demucs (HTDemucs) is the only operationally feasible candidate on current CPU infrastructure. BS-RoFormer requires Python 3.10+ which is incompatible with the current environment.**

## Product Question

Should source separation become a first-class evidence layer for mixed music in hello-ai? Which OSS path is practical?

## Evaluation Environment

- **Platform**: macOS-15.3.1-arm64-arm-64bit (Apple Silicon)
- **Arch**: arm64
- **Python**: 3.9.6
- **Device**: CPU (no GPU)
- **PyTorch**: 2.8.0
- **hello-ai commit**: `78b6a39` (eval/analysis-v3-pulse-bakeoff)
- **Branch**: `eval/analysis-v3-separation-bakeoff`

## Candidate Matrix

| Candidate | Model ID | Code License | Weight License | Stems | Python Req | Status |
|---|---|---|---|---|---|---|
| bs_roformer | lucidrains/BS-RoFormer | MIT | CC-BY-NC-SA-4.0 | 4 | >=3.10 | REVISIT |
| demucs | facebookresearch/demucs | MIT | MIT | 4 | >=3.8 | RESEARCH |

## Datasets and Licensing

| Dataset | Source | License | Clips | Notes |
|---|---|---|---|---|
| GuitarSet | https://github.com/marl/GuitarSet | MIT | 2 | Guitar recordings |
| BabySlakh | https://zenodo.org/records/4603870 | CC BY 4.0 | 2 | Multi-instrument |

## Methodology

Evidence classes:
- **LOCAL MEASUREMENT**: CPU latency, load time, separation feasibility
- **QUALITATIVE PRODUCT PROBE**: Stem extraction on real music

## BS-RoFormer (REVISIT)

**Blocker**: BS-RoFormer 1.0.5/1.0.6 requires Python 3.10+ due to PEP 604 type hints (`tuple[int, int] | None`). The `beartype` decorator enforces this at import time.

**Decision**: REVISIT — blocked by Python version requirement.

## Demucs (RESEARCH)

### Operational Evaluation (LOCAL MEASUREMENT)

| Metric | Value |
|---|---|
| Install success | Yes |
| Load time | 1.07s |
| CPU latency 10s | 3.48s |
| CPU latency 30s | 11.23s |
| Determinism | False* |
| ARM feasibility | Confirmed |

*determinism check failed on synthetic audio

### Separation Evaluation (LOCAL MEASUREMENT)

| Clip | Stems Extracted | Notes |
|---|---|---|
| guitarset_bn1_comp | vocals, drums, bass, other | Guitar-only clip |
| guitarset_rock2_comp | vocals, drums, bass, other | Guitar-only clip |
| babyslakh_01 | vocals, drums, bass, other | Multi-instrument |
| babyslakh_02 | vocals, drums, bass, other | Multi-instrument |

### Licensing Findings

| Candidate | Code License | Weight License | Commercial Use |
|---|---|---|---|
| demucs | MIT | MIT | ✓ |

### Decision: RESEARCH

Demucs is operationally feasible on CPU (3.48s for 10s audio). MIT license permits commercial use. However:
- CPU latency may be too slow for real-time use
- Determinism needs investigation
- Downstream MIR value not yet evaluated
- No reference separation metrics computed

## Architecture Recommendation

**Demucs is a viable candidate for source separation. Further evaluation needed to determine downstream MIR value.**

Next steps:
1. Compute reference separation metrics (SDR/SIR/SAR) on lawful test material
2. Evaluate downstream MIR value (chord/beat/melody on separated stems)
3. Assess CPU feasibility for production use
4. Consider BS-RoFormer when Python 3.10+ is available

## Proposed StemEvidence Contract

```typescript
type StemEvidence = {
  sourceArtifactVersionId: string
  engine: string
  engineVersion?: string
  stems: {
    vocals?: { vectorRef: string; confidence?: number }
    drums?: { vectorRef: string; confidence?: number }
    bass?: { vectorRef: string; confidence?: number }
    other?: { vectorRef: string; confidence?: number }
  }
  provenance: {
    parameters?: Record<string, unknown>
    checkpoint?: string
    checkpointChecksum?: string
  }
}
```

## Remaining Uncertainty

- No reference separation metrics (SDR/SIR/SAR)
- No downstream MIR evaluation
- CPU latency may be too slow for production
- BS-RoFormer blocked by Python version
- Limited evaluation corpus

## What Should Happen Next

1. Compute reference separation metrics on lawful test material
2. Evaluate downstream MIR value (chord/beat/melody on stems)
3. Assess CPU feasibility for production use
4. Consider BS-RoFormer when Python 3.10+ is available

## Reproduction Instructions

```bash
# Set cache directory
export MUSIC_EVAL_CACHE_DIR=/path/to/backend/evaluation/.cache

# Run all candidates
python3 -m backend.evaluation.analysis_v3.separation.run --candidate all

# Run specific candidate
python3 -m backend.evaluation.analysis_v3.separation.run --candidate demucs

# Results saved to backend/evaluation/analysis_v3/separation/results/{candidate}.json
```
