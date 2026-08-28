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
- per-program/per-family onset breakdowns for failure analysis

Note-event matching uses `mir_eval 0.8.2` maximum bipartite matching with a 50 ms onset tolerance and 50-cent pitch tolerance. Offset-aware metrics use the larger of 50 ms or 20% of the reference-note duration. Drums use reserved label `128`.

The flat metric lets Basic Pitch remain a meaningful note-recovery baseline; program-aware metrics expose the product value a multi-track model would need to add. No weighted composite is used.

## Reproducibility

Every scored model run records an immutable candidate revision, separate code/weight licenses, environment metadata, prediction paths, and dataset-manifest provenance. The scorer verifies the recorded manifest SHA-256 against the manifest being scored before accepting a run.

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

## Verified harness gate

Measurement/code head `7057c1c247fb2770fee5f5e418479cbf69bd4619` was rebased onto then-current `main` (`399ad131563e7741fe12019cc749f5e82e3ba451`) and verified one commit ahead / zero behind. On that exact head:

- Ruff check + format: pass (`239 files already formatted`)
- generated API contract: pass
- all 17 new multi-track evaluator/provenance tests: pass
- required Python suite: **756 passed, 13 skipped, 37 deselected**
- Build, E2E, CodeQL, Dependency Review, and Gitleaks: pass

This verifies the harness, not a new AMT model. No Slakh Basic Pitch versus MR-MT3 quality result has been measured yet.

## Promotion gate

A second AMT path is not justified merely by better aggregate note F1. It must materially improve instrument-aware evidence on mixed music, have acceptable per-piece/per-instrument failure distributions and operational cost, and have code/weight licensing compatible with the intended deployment. Any production integration is a later, separate decision.
