# Product Roadmap

North star: a human-guided music workspace that can ingest musical material,
transform it into useful representations, explain it, compare it, and help a
person create variations without taking authorship away from them.

## Now: trustworthy audio-to-understanding loop

The first product slice is audio upload → MIDI/note entities → playback and
MusicXML → harmonic analysis. Its acceptance criterion is simple: every result
shown in the UI must come from a persisted artifact or insight, and failures must
remain visible.

Still needed to complete this slice operationally:

- deployed worker health, queue metrics, and stuck-job alerts;
- a real-backend smoke test with a small licensed fixture;
- better source-format validation and transcription-quality diagnostics;
- score correction and export from a new immutable version.

## Next: analysis as the core product

Build a genre-neutral analysis framework while allowing specialized analyzers:

- melody, rhythm, meter, harmony, cadence, form, motif, texture, and timbre;
- confidence, evidence, time spans, provenance, and alternative interpretations;
- comparison across versions, performances, references, and a user's library;
- plain-language explanations linked to notes, measures, and audible moments;
- analyzer evaluation sets split by instrumentation and genre.

“Genre-neutral” applies to contracts and composition of capabilities, not to a
claim that one model performs equally well on every kind of music.

## Then: human-guided creation

- correct transcription and notation with version history;
- request a melody, rhythm, chord, orchestration, or structural variation;
- constrain suggestions by selected spans, harmony, range, density, or style;
- audition, compare, accept, reject, and combine suggestions;
- keep generated material attributed to a capability, model, prompt, and seed.

The existing continuation handler is prototype scaffolding and must not be
marketed as generative intelligence until it is replaced and evaluated.

## Later: sources, learning, and richer representations

- microphone and direct recording;
- import from licensed/open collections with source and rights metadata;
- spectrograms, chroma, tonal spaces, structure maps, and aligned performances;
- contextual music-theory and history lessons grounded in the active work;
- optional specialist models for polyphonic transcription, separation,
  orchestration, and audio generation.

## Product boundary

The durable backend and capability contracts are the product core. A chat/CLI
interface can expose operations sooner than a polished studio UI, but all
operations must remain reachable from the deployed Vercel app. UI breadth should
follow trustworthy capabilities rather than imply capabilities that do not work.
