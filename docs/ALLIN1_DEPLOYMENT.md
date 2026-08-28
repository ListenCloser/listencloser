# All-In-One audio structure — archived research deployment notes

> **Do not enable this in production.** The current capability registry marks `section`, `audio_structure`, and `structure` as `evaluation_only`, with no Inspector/annotation/Ask exposure. This file is retained only as historical research/runtime notes. Any future structure engine must pass the current Analysis V3 evaluation process and receive an explicit production decision before dependencies or flags are added to the production worker image.

The historical experiment wrote seconds-based hypotheses such as recording tempo, beat/downbeat anchors, and labelled functional sections (`intro`, `verse`, `chorus`, `bridge`, and so on). Those section labels were model hypotheses, not trusted product evidence, and the current architecture does not expose them.

## Why this remains isolated

All-In-One requires PyTorch, NATTEN, and `madmom`, in addition to model weights. It must not be added blindly to the API/worker production image or locked backend dependency set: compatible NATTEN builds are platform and PyTorch-version specific, and a failed optional research-model installation must never make imports, transcription, FastAPI, or the durable worker unavailable.

The production capability registry is authoritative. An environment variable or importable package is **not** permission to expose a capability.

## Historical disposable-runner recipe

For research reproduction only, use a disposable environment rather than mutating Oracle production:

```bash
pip install torch
pip install git+https://github.com/CPJKU/madmom
pip install allin1
```

Select a PyTorch/NATTEN pairing compatible with the test machine and explicitly record versions/checkpoints. Do not rely on unpinned latest dependencies or infer Oracle ARM compatibility from an x86 research run.

A minimal research smoke is:

```bash
python - <<'PY'
import allin1
result = allin1.analyze("/path/to/a/licensed-decoded.wav", device="cpu")
print(result.bpm, len(result.beats), len(result.downbeats), len(result.segments))
PY
```

This only proves that the research dependency can execute. It does **not** establish section-label accuracy, genre generalization, product value, licensing suitability, latency viability, or production readiness.

Before reconsidering production use, benchmark a current structure candidate on lawful labelled data, compare it against the current evaluation baseline, record licensing/runtime provenance, and update `backend/config/capabilities.json` only after the evidence supports an explicit status change.
