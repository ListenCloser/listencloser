# Analysis V3 — Generic multi-instrument transcription

Evaluation-only work for GitHub issue #337.

This benchmark asks whether hello-ai needs an optional multi-track symbolic evidence path beyond the existing Basic Pitch / Transkun routing. It does **not** change production routing, `capabilities.json`, persistence, frontend behavior, or deployment dependencies.

## Decision after the measured subset

**Do not replace Basic Pitch globally. Keep MR-MT3 at `RESEARCH` as a possible optional evidence path.**

On five deterministic 30-second excerpts from the Slakh2100-redux test split:

| metric | hello-ai Basic Pitch | MR-MT3 |
| --- | ---: | ---: |
| flat onset F1 | **0.3871** | 0.3366 |
| flat onset+offset F1 | **0.1397** | 0.0977* |
| GM-family onset F1 | N/A | 0.3147 |
| exact-program onset F1 | N/A | 0.2286 |
| exact-program onset+offset F1 | N/A | 0.0512 |
| GM-family detection F1 | N/A | **0.9113** |
| exact-program detection F1 | N/A | 0.3875 |

`*` The MR-MT3 offset metric uses the program-preserving serializer described below. Basic Pitch does not provide program/drum attribution, so arbitrary default MIDI program values are not treated as evidence.

The small result is heterogeneous: MR-MT3 wins flat onset recovery strongly on one excerpt (`Track01878`, 0.5411 vs 0.2701) but loses on four of five. Its high family-detection score suggests useful **coarse instrument-presence** signal, while exact program-attributed note quality is still too weak for a trustworthy instrument-aware score/piano-roll path.

This is a research decision, not production adoption. The machine-readable result is `results/slakh_redux_subset_results.json`.

## Fixed evaluation shape

- **Dataset:** Slakh2100-redux, test split.
- **Measured subset:** `Track01876`, `Track01877`, `Track01878`, `Track01880`, `Track01881`; first 30 seconds.
- **Ground truth:** active per-source `MIDI/SXX.mid` marked `midi_saved: true`, not `all_src.mid`.
- **Acquisition:** selective file mirror pinned to revision `bb320faf307f5d24aeced0e60f9445ff0abce205`; upstream dataset remains Zenodo 4599666, CC BY 4.0. Every cropped mix/reference MIDI is hashed in the result fixture.
- **Production baseline:** the repository's existing `BasicPitchEngine` at hello-ai measurement SHA `7057c1c247fb2770fee5f5e418479cbf69bd4619`.
- **Practical research candidate:** MR-MT3 through `mt3-infer 0.2.0` pinned to `2d20ee5bb6ca727968bd23c6100fd2a35154166b` and checkpoint SHA-256 `b8a3807ed265059abd25ad7f68142c06c35e8f6144dcaa45bd55946a3745398f`.
- **Required CI:** metadata/metrics/unit tests only. No dataset or model download.

## Metrics

The scorer intentionally reports complementary views rather than one composite:

- onset F1, instrument-agnostic
- onset+offset note F1, instrument-agnostic
- onset F1 requiring the same GM program family
- onset F1 requiring the exact MIDI program
- onset+offset F1 requiring the exact program
- exact-program instrument detection F1
- GM-family instrument detection F1
- per-program/per-family onset breakdowns

Note-event matching uses `mir_eval 0.8.2` maximum bipartite matching with a 50 ms onset tolerance and 50-cent pitch tolerance. Offset-aware metrics use the larger of 50 ms or 20% of reference-note duration. Drums use reserved label `128`.

The flat metric keeps Basic Pitch meaningful as a note-recovery baseline; program-aware metrics measure the incremental product value a multi-track model would need to add. No weighted composite is used.

## MR-MT3 serializer validity finding

The pinned `mt3-infer 0.2.0` MR-MT3 adapter correctly decodes program tokens into `Note.program`, but its stock final MIDI serializer discards that field: all pitched notes are written on channel 0 without `program_change` messages. Therefore stock-CLI program metrics are invalid as MR-MT3 model attribution metrics.

The research run applied a fail-closed patch **only to that final serializer**. It assigns each already-decoded pitched program a unique non-drum MIDI channel and emits its program change at time zero. Model weights, preprocessing, forward generation, codec, event decoding, event ordering, pitches, velocities, and timing math are unchanged.

Validity was checked against a preceding stock-CLI run on the exact same five excerpts:

- manifest bytes identical
- predicted note counts identical on every track
- flat onset F1 identical on every track
- the complete raw note-on/note-off event sequence is identical when channel is ignored; normalized event SHA-256 matches for all five tracks
- offset-aware F1 changes on two tracks because separate channels disambiguate overlapping same-pitch note-offs; this is an expected serialization/parser effect, not a model-prediction change

Patch provenance, workflow run IDs, artifact digests, before/after adapter hashes, and per-track equivalence hashes are committed in `results/slakh_redux_subset_results.json`.

## Reproducibility

Create a deterministic manifest from an unpacked Slakh2100-redux tree:

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

Score any candidate that writes the `schemas/model_run_template.json` contract:

```bash
python -m backend.evaluation.analysis_v3.multitrack_transcription.run score \
  --manifest /tmp/slakh-multitrack.json \
  --dataset-root /data/slakh2100_flac_redux \
  --model-run /tmp/candidate/model_run.json \
  --output /tmp/candidate-score.json
```

Every scored run records immutable candidate/checkpoint provenance, separate code/weight licenses, environment metadata, prediction paths, and the dataset-manifest SHA-256. The scorer fails closed on provenance/manifest mismatches, duplicate or unknown IDs, and missing files.

## Operational findings

Basic Pitch's first excerpt includes model cold-start; the remaining four measured about 1.5–1.8 seconds each on the GitHub CPU runner. MR-MT3's stock CLI launches a fresh process and loads the model for every excerpt; measured per-track wall time was roughly 26–155 seconds with about 817–863 MB peak RSS. That is a **wrapper execution cost**, not a warm batched-model latency claim.

A production integration would need a persistent/warm runner and a broader benchmark. This PR does not add one.

## Harness verification

The evaluator code head `7057c1c247fb2770fee5f5e418479cbf69bd4619` passed Ruff/format, generated API-contract verification, all 17 original multi-track tests, the required Python suite (`756 passed, 13 skipped, 37 deselected`), Build, E2E, Real-stack E2E, Backend Image, CodeQL, Dependency Review, and Gitleaks.

The measured-result commits add only machine-readable evidence, documentation, and deterministic result-fixture tests. Fresh CI on the final PR head remains the merge gate.

## Promotion gate

MR-MT3 stays `RESEARCH`. A second production AMT path would need broader evidence that instrument-aware note quality materially improves downstream harmony/bass/melody/arrangement workflows, plus acceptable warm runtime and deployment/licensing characteristics. Symbolic transcription remains one optional evidence family, not the universal analysis substrate.
