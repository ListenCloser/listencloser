# Analysis V3 Source Separation Bakeoff

## Executive Decision

**Current recommendation: RESEARCH.**

Stage 1 established that HTDemucs can run on CPU/ARM and emit the expected four stems. Stage 2 now has a rigorous evaluation path for objective reference quality, downstream beat value, downstream bass-transcription value, checkpoint provenance, and whole-track operational cost. **No new Stage 2 corpus result is claimed yet.** Until the real reference runs are committed, this work does not justify production adoption or a first-class StemEvidence architecture.

BS-RoFormer remains **REVISIT** until an exact compatible pretrained checkpoint, weight license, and runnable environment are verified. Do not compare an untrained architecture against HTDemucs.

## Product Question

Should source separation become a first-class evidence layer for mixed music in hello-ai, and which OSS path is practical enough to justify the added runtime, storage, and product complexity?

The primary decision gate is not source-separation quality in isolation. It is whether the same hello-ai analysis tasks become materially better when given relevant stems.

## Stage 1 Evidence — Completed

### Environment

- **Platform**: macOS-15.3.1-arm64-arm-64bit (Apple Silicon)
- **Arch**: arm64
- **Python**: 3.9.6
- **Device**: CPU
- **PyTorch**: 2.8.0
- **measurement commit**: `d0ebc88d44a7b1712e66b7dacb848b4371a11afb`
- **measurement branch**: `eval/analysis-v3-separation-bakeoff`

### Candidate matrix

| Candidate | Model | Code license | Weight license | Stage 1 result | Decision |
|---|---|---|---|---|---|
| demucs | HTDemucs | MIT | MIT as recorded by the evaluation | runnable; vocals/drums/bass/other emitted | RESEARCH |
| bs_roformer | architecture path only | MIT | exact checkpoint unverified | evaluated package path blocked; no valid trained checkpoint benchmarked | REVISIT |

### HTDemucs operational evidence

| Metric | Stage 1 value |
|---|---:|
| Load time | 1.07 s |
| CPU latency, 10 s input | 3.48 s |
| CPU latency, 30 s input | 11.23 s |
| ARM feasibility | confirmed |
| Stem set | vocals / drums / bass / other |

The Stage 1 synthetic determinism probe reported a mismatch. Stage 2 therefore uses `shifts=0` rather than the package's random time-shift ensembling for scientific per-piece comparisons.

### Stage 1 extraction smoke data

- GuitarSet: MIT, two solo-guitar clips
- BabySlakh: CC BY 4.0, two multi-instrument mixtures

Those were extraction smoke probes only. They were not reference-scored separation-quality or downstream-value evidence.

## Stage 2 Evaluation Contract — Implemented, Results Pending

Current PR: #426.

### A. Exact HTDemucs provenance

The Stage 2 adapter pins the official `htdemucs` model identity:

- model signature: `955717e8`
- artifact: `955717e8-8726e21a.th`
- expected SHA-256 prefix from the upstream artifact: `8726e21a`
- inference shifts: `0`

At model load the harness:

1. resolves the expected Torch Hub checkpoint path;
2. refuses the run if the exact official artifact is absent;
3. hashes the checkpoint;
4. refuses the run if the SHA-256 prefix does not match;
5. records the full SHA-256, package version, checkpoint size, device, and runtime environment.

This closes the Stage 1 provenance gap for the HTDemucs candidate.

### B. Objective reference quality

A manifest may provide isolated `reference_stems`. For each available stem the runner records:

1. SI-SDR of the **original mixture** against the isolated target reference;
2. SI-SDR of the **separated stem** against that same reference;
3. the improvement in dB.

The primary number is therefore gain-over-mixture, per piece and per stem. This avoids treating an isolated stem score as sufficient product evidence.

The older BSS Eval SDR/SIR/SAR helpers remain compatibility utilities and are not the Stage 2 headline contract.

### C. Downstream beat/groove value

For clips with `reference_beats`, the runner evaluates the exact same production path twice:

1. `music_features.estimate_beat_grid(original_mixture)`
2. `music_features.estimate_beat_grid(separated_drums)`

Both are scored with the canonical #335 metric:

`mir_eval.beat.f_measure(..., f_measure_threshold=0.07)`

The result stores mixture F1, drum-stem F1, delta, and aggregate improved/degraded/unchanged counts.

#### Corpus validity correction

GuitarSet is useful for the independent pulse benchmark but is **not** a valid headline mixture-vs-drums source-separation experiment because the recordings are solo guitar. Stage 2 therefore does not treat GuitarSet drum-stem results as evidence for source-separation value.

The BabySlakh preparation helper records the exact beat grid from each track's `all_src.mid` synthesis MIDI when available. This provides a controlled mixed-track comparison with real drum sources. It is explicitly labeled `symbolic_synthesis_reference`; it is not presented as a replacement for a human-annotated beat benchmark on real recordings.

### D. Downstream bass-transcription value

When the prepared manifest includes `reference_midis.bass`, the optional `--with-bass-amt` probe evaluates:

1. production `BasicPitchEngine` on the original mixture;
2. the same production engine on the separated bass stem.

Both predictions are scored with the repository's existing Analysis V3 `match_notes` contract. The reference is the aligned BabySlakh per-source bass MIDI. Program labels are ignored because the production Basic Pitch path is instrument-agnostic.

This tests an actual product task instead of introducing a bespoke easier bass detector.

### E. Reproducible BabySlakh preparation

The Stage 2 helper groups isolated BabySlakh sources into the four HTDemucs target families:

- vocals
- drums
- bass
- other

It writes derived reference submixes under the dataset root, leaves source files untouched, preserves aligned per-source MIDI paths, records source counts, and adds the `all_src.mid` synthesis beat grid when present.

Dataset provenance recorded by the manifest:

- dataset: BabySlakh
- source: https://zenodo.org/records/4603870
- license: CC BY 4.0

### F. Operational evidence

The operational runner now records:

- 10-second latency distribution
- 30-second latency distribution
- one 3-minute whole-track latency run
- real-time factor
- process max RSS
- CUDA peak allocated memory where applicable
- load time
- determinism
- exact checkpoint provenance

The 3-minute probe intentionally has no second 3-minute warm-up run.

### G. Failure semantics

Evaluation failures are now scoped to the task that failed. A beat or bass-AMT error no longer erases otherwise-valid separation/objective evidence for the track.

Result rows preserve:

- missing input audio
- separator failures
- missing reference stems/MIDI
- objective-metric failures
- downstream-task failures

Result filenames include candidate, task, and manifest name so independent corpus runs do not silently overwrite one another.

## Current Evidence Boundary

The Stage 2 code makes the following claims **measurable**, but does not yet claim positive results:

- SI-SDR gain from HTDemucs stems
- beat-F1 gain from the drum stem
- bass-note-F1 gain from the bass stem
- 3-minute CPU/RAM feasibility under the pinned Stage 2 protocol
- perceptual usefulness
- production suitability

No ADOPT decision is allowed from harness implementation alone.

## Product / Perceptual Probe Still Required

For a small rights-safe style-diverse sample, record whether each separated stem is useful for:

- isolate + listen
- A/B original mixture vs stem
- repeated section looping
- hearing layer entry/exit
- understanding bass/rhythm interaction
- evidence-linked Breakdown explanations

Record leakage, pumping, transient smearing, missing fundamentals, vocal artifacts, and other failure modes. Do not collapse this into a single subjective quality score.

## Decision Rubric

### ADOPT

Only if all are true:

- reference quality is consistently useful rather than merely non-catastrophic;
- at least one high-value downstream task improves materially across pieces/styles;
- regressions/failures are bounded and visible;
- licensing is production-compatible;
- whole-track cost fits a credible optional worker/deferred-processing strategy;
- product interactions benefit enough to justify new artifacts and complexity.

### RESEARCH

Use when the signal is promising but corpus breadth, quality, or operational evidence is still insufficient.

### REVISIT

Use for a candidate blocked by environment/checkpoint/license constraints before a valid quality comparison exists.

### REJECT

Use when a valid candidate fails to improve downstream/product value enough to justify its cost, or when licensing/operations are fundamentally unsuitable.

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

- stem audio is an artifact/reference, not an embedding vector;
- do not invent per-stem confidence unless an engine supplies calibrated confidence;
- #336 owns the final persistence/Evidence Graph contract;
- this contract remains a proposal until #334 earns an ADOPT decision.

## Next Result-Bearing Work

1. Prepare a deterministic BabySlakh Stage 2 manifest.
2. Run pinned HTDemucs across that manifest.
3. Commit per-piece SI-SDR gain, beat-F1 delta, optional bass-note-F1 delta, failures, and provenance.
4. Record the 3-minute operational result and perceptual/product notes.
5. Inspect distributions, not just means.
6. If the signal is promising, add a rights-safe human-annotated mixed-audio beat corpus.
7. Only then decide whether validating a modern RoFormer checkpoint is worth the extra evaluation cost.
8. Return an updated `ADOPT / RESEARCH / REJECT / REVISIT` decision to #334.

## Reproduction

Prepare BabySlakh references:

```bash
export BABYSLAKH_ROOT=/path/to/babyslakh_16k
uv run --project backend --with pyyaml python -m \
  backend.evaluation.analysis_v3.separation.datasets.babyslakh \
  "$BABYSLAKH_ROOT" \
  backend/evaluation/analysis_v3/separation/manifests/babyslakh_4stem.json \
  --limit 20
```

Run objective + downstream evaluation:

```bash
python -m backend.evaluation.analysis_v3.separation.run \
  --candidate demucs \
  --task separation \
  --manifest backend/evaluation/analysis_v3/separation/manifests/babyslakh_4stem.json \
  --with-bass-amt
```

Run operational probe:

```bash
python -m backend.evaluation.analysis_v3.separation.run \
  --candidate demucs \
  --task operational
```

Use `Part of #334`, not `Closes #334`, until the measured decision is complete.
