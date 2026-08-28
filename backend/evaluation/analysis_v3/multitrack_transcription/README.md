# Analysis V3 — Generic multi-instrument transcription

Evaluation-only work for GitHub issue #337.

This benchmark asks whether hello-ai needs an optional multi-track symbolic evidence path beyond the existing Basic Pitch / Transkun routing. It does **not** change production routing, `capabilities.json`, persistence, frontend behavior, or deployment dependencies.

## Decision after the measured subset

**Keep Basic Pitch as the production baseline for now. Keep MR-MT3 at `RESEARCH` as a leading optional multi-instrument evidence path.**

On five deterministic 30-second excerpts from the Slakh2100-redux test split, canonical MR-MT3 quality is measured from its decoded `NoteSequence` **before** `mt3-infer` MIDI serialization:

| metric | hello-ai Basic Pitch | MR-MT3 decoder evidence |
| --- | ---: | ---: |
| flat onset F1 | 0.3871 | **0.7898** |
| flat onset+offset F1 | 0.1397 | **0.2415** |
| GM-family onset F1 | N/A | **0.7550** |
| exact-program onset F1 | N/A | **0.4999** |
| exact-program onset+offset F1 | N/A | 0.1211 |
| GM-family detection F1 | N/A | **0.9113** |
| exact-program detection F1 | N/A | 0.3875 |

Basic Pitch does not provide program/drum attribution, so arbitrary default MIDI program values are not treated as evidence.

MR-MT3 wins flat onset recovery on all five measured excerpts once scored at the decoder boundary. This is a strong quality signal, but **not an ADOPT decision**: the subset is tiny, exact program-attributed note-with-offset quality remains weak, and the current stock process-per-track CPU wrapper costs roughly 26–155 seconds per 30-second excerpt.

The machine-readable result is `results/slakh_redux_subset_results.json`.

## Fixed evaluation shape

- **Dataset:** Slakh2100-redux, test split, CC BY 4.0.
- **Measured subset:** `Track01876`, `Track01877`, `Track01878`, `Track01880`, `Track01881`; first 30 seconds.
- **Ground truth:** active per-source `MIDI/SXX.mid` marked `midi_saved: true`, not `all_src.mid`.
- **Acquisition:** selective mirror pinned to `bb320faf307f5d24aeced0e60f9445ff0abce205`; upstream identity remains Zenodo 4599666. Cropped mix/reference files are SHA-256 recorded.
- **Production baseline:** repository `BasicPitchEngine`, measurement SHA `7057c1c247fb2770fee5f5e418479cbf69bd4619`.
- **Research candidate:** `mt3-infer 0.2.0` at `2d20ee5bb6ca727968bd23c6100fd2a35154166b`, MR-MT3 checkpoint SHA-256 `b8a3807ed265059abd25ad7f68142c06c35e8f6144dcaa45bd55946a3745398f`.
- **Required CI:** metadata/metrics/unit tests only; no model or dataset download.

## Metrics

Canonical note matching uses `mir_eval 0.8.2` maximum bipartite matching:

- 50 ms onset tolerance
- 50-cent pitch tolerance
- offset tolerance `max(50 ms, 20% of reference-note duration)`
- drums use reserved label `128`

The scorer reports flat onset/note F1, GM-family and exact-program onset F1, exact-program note F1, active-instrument detection, and per-program/per-family breakdowns. No weighted composite is used.

## Critical `mt3-infer` serializer finding

Pinned `mt3-infer` correctly decodes MR-MT3 program tokens into `Note.program` and `is_drum`, but its stock MIDI serializer writes all pitched notes to channel 0 with no `program_change` messages.

That is worse than a label-loss bug. When simultaneous/overlapping notes with the same pitch originate from different decoded programs, collapsing them onto one channel destroys note identity for MIDI parsers. The stock serialized output therefore under-reports **flat note quality as well as program-aware quality**.

Three controlled measurements establish the boundary:

1. **Stock CLI diagnostic:** serializer-corrupted macro onset F1 `0.3366`, note F1 `0.0905`.
2. **Program-channel serializer patch diagnostic:** preserves decoded program channels but still serializes through MIDI; macro onset F1 `0.3366`, note F1 `0.0977`.
3. **Decoder-sidecar calibration (canonical):** captures every decoded note immediately after `decode_and_combine_predictions`, before the stock serializer; macro onset F1 `0.7898`, note F1 `0.2415`.

Decoder-sidecar provenance:

- workflow run `33218294887`
- head `edfc29a01334db61ceaf6d7dfcde0080cbfd185b`
- artifact SHA-256 `484581f59d444cfbbc1333da128f8ecb663aa4d0bc0d819a64b72ce8d0818dc8`
- upstream adapter SHA-256 before instrumentation `5b376389c1f1794862b2704237cd01e20b1c2c32f474a429cf52afd20b2122ef`
- instrumentation writes a JSON sidecar only; stock MIDI serialization is unchanged

The locked hello-ai environment converts those sidecars into one MIDI stream per decoded program solely so the frozen scorer can consume them. Independent validation found every decoded note survives one-to-one on all five tracks, with at most ~1.1 ms serialization quantization—well below the 50 ms evaluation tolerance.

Therefore **decoder-level evidence, not stock `mt3-infer` MIDI, is the canonical MR-MT3 measurement**. Any future product adapter must preserve decoded note identity directly rather than consume the current stock MIDI serializer.

## Per-excerpt flat onset F1

| track | Basic Pitch | MR-MT3 decoder |
| --- | ---: | ---: |
| Track01876 | 0.2988 | **0.6804** |
| Track01877 | 0.6883 | **0.9582** |
| Track01878 | 0.2701 | **0.7603** |
| Track01880 | 0.2363 | **0.6700** |
| Track01881 | 0.4419 | **0.8801** |

The quality signal is consistent across this small subset, unlike the serializer-corrupted diagnostic.

## Instrument-aware result

| track | GM-family onset F1 | exact-program onset F1 | exact-program note F1 | family detection F1 |
| --- | ---: | ---: | ---: | ---: |
| Track01876 | 0.6068 | 0.3741 | 0.1473 | 1.0000 |
| Track01877 | 0.9582 | 0.8517 | 0.2890 | 0.8000 |
| Track01878 | 0.7397 | 0.3288 | 0.0411 | 0.8333 |
| Track01880 | 0.6042 | 0.4996 | 0.0489 | 0.9231 |
| Track01881 | 0.8663 | 0.4452 | 0.0794 | 1.0000 |

MR-MT3 provides meaningful broad-family and program-attributed onset evidence. Exact program-attributed **duration** evidence is much weaker, so this is not yet a trustworthy instrument-aware notation path.

## Reproducibility

Build a deterministic manifest from an unpacked Slakh2100-redux tree:

```bash
python -m backend.evaluation.analysis_v3.multitrack_transcription.run manifest \
  --dataset-root /data/slakh2100_flac_redux \
  --split test --limit 10 --hash-files \
  --output /tmp/slakh-multitrack.json
```

Run the exact production Basic Pitch engine:

```bash
python -m backend.evaluation.analysis_v3.multitrack_transcription.run basic-pitch \
  --manifest /tmp/slakh-multitrack.json \
  --dataset-root /data/slakh2100_flac_redux \
  --output-dir /tmp/basic-pitch-run \
  --hello-ai-sha "$(git rev-parse HEAD)"
```

Score any candidate satisfying `schemas/model_run_template.json`:

```bash
python -m backend.evaluation.analysis_v3.multitrack_transcription.run score \
  --manifest /tmp/slakh-multitrack.json \
  --dataset-root /data/slakh2100_flac_redux \
  --model-run /tmp/candidate/model_run.json \
  --output /tmp/candidate-score.json
```

Every scored run records candidate/checkpoint provenance, separate code/weight licenses, environment metadata, prediction paths, and manifest SHA-256. The scorer fails closed on provenance/manifest mismatches, duplicate or unknown IDs, and missing files.

## Operational findings

Basic Pitch's first excerpt includes model cold-start; the remaining four measured about 1.5–1.8 seconds each on the GitHub CPU runner.

The stock MR-MT3 CLI launches and loads a model process for every excerpt. Measured wall time was roughly 26–155 seconds with ~817–863 MB RSS. This is a wrapper/process cost, not a warm persistent-model latency measurement.

A production candidate would require a lossless decoder-level adapter, persistent/warm inference, broader data, and downstream product-task validation.

## Promotion gate

MR-MT3 remains `RESEARCH` despite the strong small-subset quality result. Promotion requires:

- materially broader per-source AMT evaluation;
- warm/batched runtime measurement on realistic deployment hardware;
- a lossless decoder-level evidence adapter;
- downstream evidence that program-aware notes improve arrangement, bass/melody, harmony, comparison, or representation workflows;
- no regression in failure behavior outside Slakh-style synthetic mixtures.

Symbolic transcription remains an optional evidence family, not the universal analysis substrate.
