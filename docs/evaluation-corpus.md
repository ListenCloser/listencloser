# Transcription evaluation corpus

This corpus is the gate for changes to AMT models, cleanup thresholds, beat
tracking, and notation profiles. Do not promote a new default from one
impressive clip.

## Layout

Keep source audio and reference MIDI out of git unless the files are explicitly
licensed for redistribution. Each local/secure corpus directory contains:

```text
manifest.json
audio/<clip>.wav
reference/<clip>.mid
predictions/<experiment>/<clip>.mid
```

`manifest.json` uses:

```json
{
  "name": "listencloser-v1",
  "entries": [{
    "id": "solo-piano-01",
    "reference_midi": "reference/solo-piano-01.mid",
    "predicted_midi": "predictions/basic-pitch-clean-v1/solo-piano-01.mid",
    "onset_tolerance_s": 0.05
  }]
}
```

Run it on the configured backend environment:

```bash
PYTHONPATH=backend python -m transcription_eval /secure/corpus/manifest.json
```

## Minimum v1 corpus

- 10 short solo-piano clips, varied tempo/dynamics
- 5 melody-plus-accompaniment clips
- 5 non-piano / dense clips, explicitly marked as exploratory

Record expected instrument, tempo, meter, and a human score-readability rating.
Compare each candidate to the existing Basic Pitch + cleanup baseline on F1,
extra-note rate, missing-note rate, onset error, duration error, and review
rating. A notation profile may only become default if it improves readability
without an unacceptable regression in note metrics.
