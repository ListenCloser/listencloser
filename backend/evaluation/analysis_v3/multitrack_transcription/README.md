# Analysis V3 — Generic multi-instrument transcription

Evaluation-only work for GitHub issue #337.

This harness asks whether hello-ai needs an optional multi-track symbolic evidence path beyond the existing Basic Pitch / Transkun routing. It does **not** change production routing, `capabilities.json`, persistence, frontend behavior, or deployment dependencies.

## Fixed evaluation shape

- **Dataset:** Slakh2100-redux, test split, deterministic manifest.
- **Ground truth:** per-source `MIDI/SXX.mid` files, not `all_src.mid`, because the per-source MIDI is what synthesized each stem.
- **Production baseline:** the repository's existing `BasicPitchEngine`.
- **Research baselines/candidates:** Magenta MT3 if mechanically runnable, YourMT3+ as a quality/reference path, and MR-MT3 as the preferred newer practical first-run candidate.
- **Required CI:** metadata/metrics/unit tests only. No dataset or model download.

## Metrics

The scorer intentionally reports several views rather than one composite:

- onset F1, instrument-agnostic
- onset+offset note F1, instrument-agnostic
- onset F1 requiring the same GM program family
- onset F1 requiring the exact MIDI program
- onset+offset F1 requiring the exact program
- exact-program instrument detection F1
- GM-family instrument detection F1

Drums use reserved label `128`. Offset matching uses `max(50 ms, 20% of reference duration)`. The flat metric lets Basic Pitch remain a meaningful note baseline; program-aware metrics expose the product value a multi-track model would need to add.

## Commands

Create a deterministic manifest from an unpacked Slakh2100-redux tree:

```bash
python -m backend.evaluation.analysis_v3.multitrack_transcription.run manifest \
  --dataset-root /data/slakh2100_flac_redux \
  --split test --limit 10 --hash-files \
  --output /tmp/slakh-multitrack.json
```

Run the current production Basic Pitch engine on that manifest:

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
  --model-run /tmp/basic-pitch-run/model_run.json \
  --output /tmp/basic-pitch-score.json
```

## Promotion gate

A second AMT path is not justified merely by better aggregate note F1. It must materially improve instrument-aware evidence on mixed music, have acceptable failure distributions and operational cost, and have code/weight licensing compatible with the intended deployment. Any production integration is a later, separate decision.
