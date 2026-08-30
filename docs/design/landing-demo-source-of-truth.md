# Landing demo source of truth

Issue: #695. Parent UX direction: #328.

The signed-out hero may be more expressive than the authenticated workspace, but any visual that looks like musical evidence must remain truthful. The landing hero is therefore a miniature product demonstration, not decorative music-shaped geometry.

## Core invariant

One canonical recording owns time.

```text
canonical audio
   |
   +-- source-derived waveform min/max bins
   +-- canonical note events / transcription
   +-- score artifact + measured score-time alignment
   +-- supported evidence span(s)
                     |
                     v
             landing demo manifest
                     |
                     v
       one shared seconds -> x projection
```

The hero component must not store or hand-author x positions for time-bearing objects. Waveform bins are ordered samples over the declared window; notes, score measure starts, evidence spans and the playhead are represented in seconds. Rendering derives geometry from those values.

`lib/landing-demo.ts` encodes and validates this contract.

## Candidate engineering fixture

`tests/fixtures/real-piano.m4a` is the existing canonical real-stack fixture. PR #208 records that it is a checked-in AAC-LC recording supplied by the reviewer and proves that the real pipeline can produce playback, transcription, Piano Roll, Score and analysis from it.

That makes it a useful engineering fixture for exercising the demo pipeline. It does **not** by itself establish public/marketing redistribution rights. A production landing manifest must set `source.publicUseApproved=true` only after provenance/license is explicitly documented. If that approval cannot be established, replace the source with an explicitly safe recording and regenerate every derived layer.

## Manifest responsibilities

The manifest contains only source facts needed by the visual:

- source asset path, SHA-256, duration, provenance and public-use approval;
- selected source-time window;
- waveform min/max bins derived from the real audio window;
- note IDs, MIDI pitches, source start/end seconds and optional source velocity;
- MusicXML artifact path/hash plus aligned measure-start seconds;
- evidence IDs/kinds/labels/provenance and source start/end seconds.

It deliberately does **not** contain:

- note x/width values;
- evidence left/width percentages;
- playhead positions;
- random waveform heights;
- hand-drawn score fragments represented as if they came from the source;
- invented confidence, finding text or timestamps.

The validator rejects common stored temporal-geometry keys so accidental mockup data cannot quietly become production truth.

## Generation pipeline

A follow-up implementation should generate a checked-in manifest deterministically from durable artifacts, not by editing JSON until the hero looks good.

Recommended sequence:

1. hash and decode the canonical audio;
2. select a musically useful fixed time window;
3. compute deterministic min/max waveform bins over that window;
4. read canonical note events from the pipeline output and preserve their source seconds;
5. read the corresponding MusicXML and durable `measure_starts_seconds` alignment;
6. select only evidence already supported by persisted/deterministic analysis and preserve its provenance;
7. validate the manifest in engineering mode;
8. require explicit public-use approval before the production landing imports it;
9. render all time-bearing layers through the shared projection helper.

The generator should record enough source hashes/version information that a changed audio/MIDI/score artifact cannot leave a stale visual manifest looking plausible.

## Animation grammar

Motion explains derivation and alignment:

1. real waveform resolves;
2. corresponding notes appear at their actual source times;
3. notation resolves for the same passage;
4. one playhead moves through every layer using the shared time projection;
5. a real evidence span appears where its source interval resolves;
6. the object settles and remains quiet.

A reduced-motion state presents the same complete information without staged movement. Do not autoplay audio, fake model processing, loop decorative particles, or add continuous motion that competes with reading.

21st.dev references from #695 (Entropy, Background Paths, Liquid Metal) are references for restraint, path motion and material treatment only. They do not override product truth or the local design system.

## Relationship to production representations

The landing object should reuse the semantics defined by #694:

- playhead = active musical time;
- selection/evidence = explicit source-time spans;
- score projection remains honest about its precision;
- representation does not imply playback source.

It should not import production Waveform/Spectrogram renderer internals merely to look consistent. #688 separately decides whether WaveSurfer owns any generic production rendering. The landing demo is a small deterministic visualization over a checked-in manifest so renderer experiments cannot change its truth contract.

## Shipping gate

Do not replace the current structural landing illustration with a data-bearing hero until all of these are true:

- source provenance/public-use rights are explicit;
- waveform, notes, score and evidence all resolve from the same canonical source;
- hashes are recorded and validation passes with public-use approval required;
- desktop/mobile and reduced-motion states are reviewed;
- no-copy/no-logo review still reads as ListenCloser rather than generic AI/data visualization;
- auth CTA and performance remain at least as usable as the current landing.
