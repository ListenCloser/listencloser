# Analysis V3: Source Separation Downstream-Value Bakeoff

Evaluation harness for #334.

The merged stage-1 work proved only that HTDemucs can run and emit four stems. This continuation is designed to answer the actual product question: **does separation make hello-ai's downstream music understanding better enough to justify a first-class optional StemEvidence layer?**

No production routing, schema, UI, worker topology, or capability default changes are made here.

## Current evaluation layers

### 1. Objective reference quality

When a manifest provides isolated `reference_stems`, the runner measures SI-SDR for:

- original mixture → target reference stem
- separated stem → target reference stem
- improvement in dB

Results are stored per piece/per stem and aggregated by stem. This is deliberately a **gain-over-mixture** measurement rather than a context-free stem-only headline number.

The older `mir_eval.separation` SDR/SIR/SAR helpers remain for compatibility but are not treated as the primary stage-2 quality contract.

### 2. Downstream beat/groove value

When `reference_beats` are present, the runner compares the exact production beat estimator on:

1. original mixture
2. separated drums

Metric contract:

- production estimator: `music_features.estimate_beat_grid`
- canonical metric: `mir_eval.beat.f_measure`
- threshold: `0.07`

The output records mixture F1, drum-stem F1, and delta.

For BabySlakh, the manifest builder derives `reference_beats` from the track's `all_src.mid` synthesis tempo/beat grid. That is useful controlled evidence for the causal question "does the drum stem help this detector on the same mixed track?", but it is **symbolic/synthetic reference evidence**, not a substitute for a human-annotated beat benchmark on real recordings.

Do not use solo GuitarSet recordings as the headline mixture-vs-drums separation test: they have useful beat annotations but do not contain the mixed drum source that this experiment is intended to isolate.

### 3. Downstream bass-transcription value

When `reference_midis.bass` are present and `--with-bass-amt` is enabled, the runner compares the repository's production `BasicPitchEngine` on:

1. original mixture
2. separated bass stem

Both predictions are scored with the existing Analysis V3 transcription contract (`multitrack_transcription.metrics.match_notes`, flat onset-note F1). Program labels are intentionally ignored because production Basic Pitch is instrument-agnostic.

This directly tests whether source separation helps bass pitch/rhythm evidence; it does not substitute a bespoke easier pitch detector.

## Candidate provenance

The HTDemucs stage-2 adapter is pinned to the official `htdemucs` mapping:

- model signature: `955717e8`
- official artifact filename: `955717e8-8726e21a.th`
- expected SHA-256 prefix encoded by the upstream artifact name: `8726e21a`
- inference shifts: `0` for deterministic per-piece comparisons

At load time the harness hashes the downloaded checkpoint and refuses to benchmark it if the official filename/checksum prefix does not match. The full SHA-256, package version, checkpoint size, device, and runtime environment are written to result provenance.

## BabySlakh reference preparation

BabySlakh provides isolated source audio and the aligned per-source MIDI used to synthesize those sources. The dataset is CC BY 4.0 and is suitable for this research/evaluation use.

The helper groups BabySlakh sources into HTDemucs-compatible `vocals / drums / bass / other` reference submixes, preserves aligned source MIDI lists for downstream AMT, and records the `all_src.mid` beat grid when available.

```bash
export BABYSLAKH_ROOT=/path/to/babyslakh_16k

uv run --project backend --with pyyaml python -m \
  backend.evaluation.analysis_v3.separation.datasets.babyslakh \
  "$BABYSLAKH_ROOT" \
  backend/evaluation/analysis_v3/separation/manifests/babyslakh_4stem.json \
  --limit 20
```

Derived reference submixes are written under `$BABYSLAKH_ROOT/.hello_ai_reference_4stems/`; source dataset files are not modified.

## Running the bakeoff

Operational probe, including 10 s / 30 s / 3 min latency, process RSS, optional CUDA peak allocation, checkpoint provenance, and determinism:

```bash
python -m backend.evaluation.analysis_v3.separation.run \
  --candidate demucs \
  --task operational
```

Objective BabySlakh reference scoring, mixture-vs-drums beat scoring, and bass AMT:

```bash
python -m backend.evaluation.analysis_v3.separation.run \
  --candidate demucs \
  --task separation \
  --manifest backend/evaluation/analysis_v3/separation/manifests/babyslakh_4stem.json \
  --with-bass-amt
```

The beat path requires `mir_eval==0.8.2` in the benchmark environment, matching #335.

## Candidate status

| Candidate | Model | Code | Weights | Current status |
|---|---|---|---|---|
| demucs | HTDemucs `955717e8` | MIT | MIT | RESEARCH; stage-2 scoring path now exists, real run still required |
| bs_roformer | exact checkpoint not yet validly wired | MIT architecture repo | checkpoint-specific | REVISIT |

Do not evaluate a random/untrained RoFormer architecture.

## Evidence boundary

Implemented does not mean measured. Until real lawful corpus runs are committed, this branch does **not** claim:

- positive SI-SDR improvement;
- positive beat or bass-AMT deltas;
- perceptual quality;
- real-recording beat improvement from human annotations;
- harmony/melody/arrangement benefit;
- production suitability.

The next result-bearing step is to prepare the BabySlakh manifest, run pinned HTDemucs across the reference corpus, commit per-piece objective/downstream results, and record failure/perceptual notes. If those results are promising, add a rights-safe human-annotated mixed-audio beat corpus and then decide whether a second modern RoFormer candidate is worth the extra evaluation cost.
