# Analysis V3 Source Separation Feasibility Bakeoff

## Executive Decision

**Recommendation: keep source separation in RESEARCH. Demucs/HTDemucs is operationally runnable on the current CPU/ARM development environment, while the BS-RoFormer path evaluated here is blocked on Python 3.9 and has no verified compatible pretrained checkpoint wired. This PR does not establish separation quality or downstream MIR value, so it does not justify production adoption or a first-class source-separation architecture yet.**

## Product Question

Should source separation become a first-class evidence layer for mixed music in listencloser, and which OSS path is practical enough to justify a deeper quality/downstream-value evaluation?

This PR answers only the first-stage feasibility question. It does **not** answer whether separated stems improve chord, beat, melody, instrumentation, arrangement, or Breakdown quality.

## Evaluation Environment

- **Platform**: macOS-15.3.1-arm64-arm-64bit (Apple Silicon)
- **Arch**: arm64
- **Python**: 3.9.6
- **Device**: CPU (no GPU)
- **PyTorch**: 2.8.0
- **measurement commit**: `d0ebc88d44a7b1712e66b7dacb848b4371a11afb`
- **Branch**: `eval/analysis-v3-separation-bakeoff`

## Candidate Matrix

| Candidate | Model ID | Code License | Weight License | Stems | Python Compatibility | Decision |
|---|---|---|---|---|---|---|
| bs_roformer | lucidrains/BS-RoFormer | MIT | **unverified for a concrete pretrained checkpoint** | intended 4 | evaluated package path requires Python 3.10+; no verified compatible checkpoint wired | REVISIT |
| demucs | facebookresearch/demucs / HTDemucs | MIT | MIT | vocals, drums, bass, other | works on Python 3.9 | RESEARCH |

## Datasets and Licensing

| Dataset | Source | License | Clips | Role in this PR |
|---|---|---|---|---|
| GuitarSet | https://github.com/marl/GuitarSet | MIT | 2 | real-audio extraction smoke test |
| BabySlakh | https://zenodo.org/records/4603870 | CC BY 4.0 | 2 | real multi-instrument extraction smoke test |

These clips are **not** a scored source-separation benchmark in this PR.

## Methodology

Evidence classes:
- **LOCAL MEASUREMENT**: install/load success, CPU latency, runtime feasibility, ability to emit the expected stem set
- **QUALITATIVE PRODUCT PROBE**: whether real music can be passed through the candidate and returned as usable stem arrays
- **NOT MEASURED HERE**: objective separation quality and downstream MIR improvement

No SDR/SIR/SAR, perceptual-error score, chord-improvement score, beat-improvement score, or melody-improvement score is reported because no valid reference-scored evaluation was run.

## BS-RoFormer — REVISIT

The evaluated BS-RoFormer package path (1.0.5/1.0.6) fails under the repo's Python 3.9 environment because package code uses Python 3.10+ union/type syntax and `beartype` evaluates it at import time.

A second validity issue was identified during review: instantiating the architecture class without loading an exact pretrained checkpoint would evaluate random/untrained weights. The adapter now **fails closed** instead. No BS-RoFormer quality result exists in this PR.

The exact future checkpoint and its weight license must be recorded together; weight rights are not inferred from the architecture repository.

Decision: **REVISIT**.

## Demucs / HTDemucs — RESEARCH

### Operational evaluation — LOCAL MEASUREMENT

| Metric | Value |
|---|---|
| Install success | Yes |
| Load time | 1.07s |
| CPU latency 10s | 3.48s |
| CPU latency 30s | 11.23s |
| ARM feasibility | Confirmed on Apple Silicon |
| Output stem set | vocals, drums, bass, other |
| License | MIT code / MIT weights as recorded by this evaluation |

The synthetic determinism probe reported a mismatch. That result is not interpreted as model-quality evidence and should be investigated separately before any production integration.

### Real-audio extraction smoke test — QUALITATIVE PRODUCT PROBE

| Clip | Result |
|---|---|
| guitarset_bn1_comp | four expected stems emitted |
| guitarset_rock2_comp | four expected stems emitted |
| babyslakh_01 | four expected stems emitted |
| babyslakh_02 | four expected stems emitted |

This proves only that the adapter can run on representative real files and produce the expected output shape. It does **not** prove that the stems are accurate or useful to downstream analysis.

Decision: **RESEARCH**.

## Objective Separation Quality

**Not evaluated in this PR.**

The repository contains metric helpers for separation experiments, but the current committed result artifacts do not contain a lawful reference-scored SDR/SIR/SAR evaluation. Those helpers therefore must not be interpreted as completed evidence.

A follow-up evaluation should use isolated reference sources from a lawful dataset and a modern, appropriate metric implementation. Mean SDR alone should not determine product value; perceptual error patterns should also be inspected.

## Downstream MIR Value

**Not evaluated in this PR.**

The downstream metric module currently contains scaffolding/placeholders. In particular, chord, beat, and melody improvement functions return no measurement. They are not evidence of downstream benefit.

The follow-up gate should compare the same analysis task on:

1. original mixture
2. relevant separated stem(s)
3. reference/ground-truth source where available

High-value tests include:
- beat/downbeat tracking on mixture vs drums stem
- bass/melody evidence on mixture vs bass/vocal or other relevant stem
- chord/harmony analysis on mixture vs harmonic/accompaniment stem
- instrumentation/layer-entry evidence for Breakdown

## Architecture Recommendation

**Do not productionize a source-separation evidence layer from this PR.**

What this PR establishes:
1. HTDemucs is a viable implementation candidate for deeper evaluation on the current CPU/ARM environment.
2. The evaluated BS-RoFormer package path is currently blocked by Python compatibility and lacks a verified compatible pretrained checkpoint in this harness; it should be revisited in a compatible isolated evaluation environment rather than dismissed on quality grounds.
3. The central #334 question — whether separation materially improves downstream understanding — remains open.

Source separation should become a first-class evidence layer only after a candidate demonstrates both:
- acceptable separation/perceptual quality, and
- measurable downstream or interaction value that justifies runtime/storage complexity.

## Proposed StemEvidence Contract

```typescript
type StemEvidence = {
  sourceArtifactVersionId: string
  engine: string
  engineVersion?: string
  stems: {
    vocals?: { artifactRef: string }
    drums?: { artifactRef: string }
    bass?: { artifactRef: string }
    other?: { artifactRef: string }
  }
  provenance: {
    parameters?: Record<string, unknown>
    checkpoint?: string
    checkpointChecksum?: string
  }
}
```

Notes:
- Stem audio is an artifact/reference, not an embedding vector; `artifactRef` is intentionally used instead of `vectorRef`.
- Do not attach unsupported per-stem confidence values unless the selected engine actually produces a calibrated confidence.
- #336 owns the final persistence/Evidence Graph contract.

## Remaining Uncertainty / Unfinished #334 Work

- objective source-separation quality on lawful isolated-source references
- perceptual error analysis beyond aggregate SDR-like metrics
- downstream MIR value for beat/downbeat, harmony, melody/bass, and instrumentation
- product value for isolate/loop/A-B/Breakdown workflows
- whole-track CPU/RAM/storage cost and production scheduling implications
- exact Demucs checkpoint checksum/version provenance
- BS-RoFormer evaluation in a compatible isolated Python environment with an exact pretrained checkpoint and verified checkpoint license

## Merge Interpretation

This PR is mergeable only as a **first-stage feasibility harness/report**, not as completion of #334 and not as evidence to switch production routing.

Use `Part of #334`, not `Closes #334`.

## Reproduction Instructions

```bash
export MUSIC_EVAL_CACHE_DIR=/path/to/backend/evaluation/.cache
python3 -m backend.evaluation.analysis_v3.separation.run --candidate all
python3 -m backend.evaluation.analysis_v3.separation.run --candidate demucs
```

Results are written under `backend/evaluation/analysis_v3/separation/results/`.
