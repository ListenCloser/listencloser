# Music Quality Evaluation Framework

## Why Evaluation Exists

The production pipeline (audio → MIDI → beats → notation → analysis) evolves
over time. Without reproducible metrics, each change is judged by one manual
example. This framework provides:

- A **corpus** of known audio clips with optional reference MIDI/beats/analysis.
- **Deterministic metrics** for transcription, beat tracking, notation quality,
  and analysis accuracy.
- A **runner** that exercises the current production pipeline and emits
  machine-readable JSON + human-readable Markdown reports.
- **Before/after comparison**: future algorithm PRs must report metrics against
  the same corpus.

No production algorithm is changed by this framework. It reads the pipeline,
never mutates it.

## Corpus Schema

A corpus is a JSON manifest:

```json
{
  "name": "synthetic_piano",
  "description": "Synthetic piano fixtures for deterministic evaluation.",
  "clips": [
    {
      "id": "piano_synthetic",
      "audio": "piano-synthetic.wav",
      "category": "solo_piano",
      "reference_midi": "piano-synthetic.mid",
      "reference": {
        "bpm": 120,
        "key": "C major",
        "meter": "4/4",
        "beats": [0.0, 0.5, 1.0, 1.5],
        "downbeats": [0.0, 1.0],
        "chords": [{"root": "C", "start": 0}],
        "sections": [{"start": 0, "end": 2.0, "label": "A"}]
      }
    }
  ]
}
```

Fields:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Unique clip identifier |
| `audio` | yes | Path (relative to manifest) to audio WAV |
| `category` | yes | One of the defined categories |
| `reference_midi` | no | Path to ground-truth MIDI for note metrics |
| `reference_musicxml` | no | Path to ground-truth MusicXML |
| `reference.bpm` | no | Known tempo |
| `reference.key` | no | Known key |
| `reference.meter` | no | Known time signature |
| `reference.beats` | no | List of beat times in seconds |
| `reference.downbeats` | no | List of downbeat times in seconds |
| `reference.chords` | no | Chord labels with timing |
| `reference.sections` | no | Section boundaries with labels |

### Categories

- `solo_piano` — single piano
- `polyphonic_piano` — complex piano
- `monophonic` — single melody line
- `pitched_single_instrument` — e.g., solo violin
- `melody_accompaniment` — lead with backing
- `full_mix` — mixed ensemble
- `noisy_recording` — challenging audio

Not every clip needs every annotation. Metrics are computed only for the
fields present.

## Metric Definitions

### Transcription

| Metric | Formula | Notes |
|--------|---------|-------|
| Note precision | matched / predicted | How many predicted notes match a reference |
| Note recall | matched / reference | How many reference notes were found |
| Note F1 | 2 × P × R / (P + R) | Harmonic mean |
| Onset precision | onset_matched / predicted | Within tolerance (default 0.05s) |
| Onset recall | onset_matched / reference | |
| Onset F1 | 2 × P × R / (P + R) | |
| Excessive count | predicted - matched | Extra notes without reference match |
| Missed count | reference - matched | Reference notes not predicted |

### Beat

| Metric | Formula |
|--------|---------|
| BPM absolute error | abs(predicted - reference) |
| BPM relative error % | error / reference × 100 |
| Beat precision/recall/F1 | Timestamp matching within 0.07s |

### Notation

Structural diagnostics only (no single "readability" score):

- Total note count, measure count
- Short note count (≤ 2 divisions)
- Tie count, tuplet count, voice count
- Measure duration stats (min, max, stddev)
- MusicXML parse validity

Human ratings (stored separately):

- Readability 1–5
- Musical fidelity 1–5
- Editing effort 1–5

### Analysis

Only evaluated when ground truth is present:

- Key correctness (string match)
- BPM absolute error
- Meter correctness
- Section precision/recall/F1 (±1s window)
- Chord precision/recall/F1 (±0.5s window, root match)

## How to Add a Fixture

1. Place audio + optional reference files in `backend/tests/fixtures/music_eval/`.
2. Add an entry to `backend/tests/fixtures/music_eval/manifest.json`.
3. Do **not** commit copyrighted music. Use synthetic/self-generated material.
4. Run the evaluation to verify.

Generate the synthetic fixture:

```bash
python3 -c "from evaluation.corpus import build_piano_synthetic_fixture; build_piano_synthetic_fixture('backend/tests/fixtures/music_eval')"
```

## How to Run

```bash
cd backend
PYTHONPATH=. python3 -m evaluation.runner --manifest tests/fixtures/music_eval/manifest.json
```

With custom output directory:

```bash
PYTHONPATH=. python3 -m evaluation.runner --manifest tests/fixtures/music_eval/manifest.json --output ../evaluation/results
```

Outputs:

- `evaluation/results/latest.json` — machine-readable full results
- `evaluation/results/latest.md` — human-readable summary

## How Future Algorithm PRs Must Use It

When proposing a change to transcription, beat tracking, notation, or analysis:

1. **Run the evaluation** against the current `main` pipeline and save results.
2. **Make your changes** and re-run against the same corpus.
3. **Include the before/after comparison** in your PR description:

```markdown
| Metric | Before | After |
|--------|--------|-------|
| Note F1 | 0.85 | 0.91 |
| Beat F1 | 0.72 | 0.88 |
```

4. **If metrics regress**, explain why the trade-off is worth it (e.g.,
   better-quality notation at the cost of slightly lower note precision).

5. **Add a new fixture** if your change targets a category not yet represented.
