# All-In-One audio structure deployment

This enables the optional structure stage in the durable `understand` workflow.
It writes seconds-based evidence on the original-audio version:

- recording tempo;
- beat/downbeat anchors;
- labelled functional sections (`intro`, `verse`, `chorus`, `bridge`, and so
  on).

The symbolic MIDI analysis remains separate. A section label is an audio-model
hypothesis, not a claim about the score or an assertion that every genre has
verse/chorus form.

## Why this is a worker-only dependency

All-In-One requires PyTorch, NATTEN, and `madmom`, in addition to model
weights. It must not be added blindly to the API image or to the normal
requirements file: a compatible NATTEN build is platform and PyTorch-version
specific. A failed optional-model installation should never make imports,
transcription, or the FastAPI API unavailable.

The code ships disabled (`ALLIN1_ENABLED=false`). The structure stage becomes
active only after the worker image has been built with a compatible runtime.

## Oracle worker handoff

On a disposable copy of the worker image, install the upstream dependencies in
this order, using a PyTorch/NATTEN pairing compatible with the Oracle ARM
architecture:

```bash
pip install torch
pip install git+https://github.com/CPJKU/madmom
pip install allin1
```

Then rebuild/restart only the `worker` service with:

```env
ALLIN1_ENABLED=true
ALLIN1_MODEL=harmonix-all
ALLIN1_DEVICE=cpu
```

The upstream project documents its required NATTEN installation separately;
select its CPU-compatible backend for the no-GPU Oracle VM. Do not use a CUDA
wheel or rely on an unpinned latest pairing.

## Smoke check

Before enabling the flag in the production compose environment:

```bash
python - <<'PY'
import allin1
result = allin1.analyze("/path/to/a/decoded.wav", device="cpu")
print(result.bpm, len(result.beats), len(result.downbeats), len(result.segments))
PY
```

Run one real import after deployment. A successful work should receive an
`audio_structure` summary, `audio_tempo`, and seekable `section` insights on
the original-audio version. If the model is unavailable, the workflow remains
successful but no structural claims are persisted; this is intentional and
honest.
