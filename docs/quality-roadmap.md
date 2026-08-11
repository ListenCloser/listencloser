# Product quality boundary and next backend slice

## What the app supports today

The reliable vertical slice is private import of a short audio file, durable
server processing, source versus synthesized-transcription playback, a
performance-MIDI piano roll, an explicitly labelled notation draft, and a
small set of derived observations. The workspace intentionally presents these
views together around one transport.

It does **not** yet support a public/open-source catalogue import, microphone
capture, editable score correction, genre-independent high-confidence
harmonic analysis, natural-language tutoring, or generative composition.
Those must not be implied by product copy.

## Why transcription quality is the primary limitation

Basic Pitch is an instrument-agnostic polyphonic AMT model and is best with a
single dominant instrument. Its output is useful as a performance hypothesis,
not publishable MIDI or notation. A global grid snap on that output is not a
quality fix: without trustworthy beat/downbeat alignment it can make timing
and rhythm less correct.

The next pipeline must persist two related artifacts:

1. `performance_midi`: conservative denoise only; retain expressive timing and
   record every rejected/merged note in provenance.
2. `notation_midi`: an opt-in score-oriented reduction, aligned to detected
   beats/downbeats, snapped to an explicit rhythmic grid, voice-separated, and
   reviewed before it replaces any displayed score.

## Implementation plan

### 1. Build an evaluation corpus before changing defaults

Collect 20–40 licensed or self-recorded clips spanning solo piano, melody with
accompaniment, and non-piano material. Store expected onset/pitch/note-count
annotations and a human score-readability rating. Gate changes on per-clip
precision/recall, onset tolerance, excessive-note rate, and score readability.

### 2. Conservative performance cleanup

Keep the existing short-note and duplicate-note cleanup, then add a separate
audited filter stage: pitch-range policy, low-velocity/very-short-note policy,
same-pitch merge policy, and chord-onset clustering. Each removed event needs
a reason and thresholds must be saved on the output version. Never silently
quantize the performance artifact.

### 3. Beat-aligned notation reduction

Use an audio beat/downbeat tracker to establish a real time grid. `beat_this`
is a strong OSS candidate for beat/downbeat inference; `all-in-one` additionally
provides tempo, beats, downbeats, and functional sections. Map notes to that
grid, select the simplest duration allowed by an explicit grid profile, then
use `music21` for notation/voice handling. Expose the profile to the user
(`strict`, `balanced`, `preserve performance`) rather than pretending one
automatic answer is correct.

### 4. Rich, evidence-backed analysis

Run audio-structure analysis in parallel with MIDI analysis:

- audio: tempo, beats, downbeats, sections and labels;
- MIDI: pitch/range/contour, interval and motif statistics, rhythmic density
  and syncopation, chord candidates, Roman numerals and cadence candidates;
- cross-check claims against the performance and notation timelines;
- persist all claims with time/beat/measure spans, confidence and provenance.

The UI should render a timeline with beat grid, chord regions, section labels,
and clickable annotations that seek the shared transport. It should link only
stable educational concepts (for example, a cadence or Roman-numeral explainer)
and never turn a low-confidence classifier result into a lesson stated as fact.

## OSS components being integrated

- [Basic Pitch](https://github.com/spotify/basic-pitch) remains the lightweight
  baseline for general polyphonic transcription.
- [All-In-One Music Structure Analyzer](https://github.com/mir-aidj/all-in-one)
  is the selected audio-structure engine. It produces tempo, beats, downbeats
  and labelled functional segments from audio; its optional worker adapter
  persists those results as timeline evidence. See
  [ALLIN1_DEPLOYMENT.md](ALLIN1_DEPLOYMENT.md) for the free Oracle worker
  install boundary.
- [music21](https://github.com/cuthbertLab/music21) remains the symbolic theory
  and notation layer, but it is not itself an audio transcription-quality model.

The deployment must still use a compatible CPU runtime on the Oracle free VM;
the core import/transcription path intentionally remains independent from that
optional runtime.
