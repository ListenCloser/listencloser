# Application audit

## Decision

The product is now one persistent, audio-first music-understanding application.
The former tabbed prototype, browser-only library, direct `/music/*` endpoints,
duplicate transport/state hooks, placeholder chat tools, and tests for those
paths were removed. Maintaining both systems caused results to disappear on
refresh, let the browser orchestrate server work, and made the UI imply features
that were not backed by durable capabilities.

## What is real now

| Product promise | Implementation | Verification |
|---|---|---|
| Private audio import | authenticated multipart upload, size/type checks, owner-prefixed private object | API/RLS tests + E2E request |
| Durable processing | Postgres-backed job claimed by a separate worker | worker lease/retry tests |
| Audio to MIDI | Basic Pitch capability | adapter tests + real deployed smoke |
| Piano roll | persisted note entities | component + E2E |
| Playback comparison | signed original and rendered WAV versions | store tests + E2E source selector |
| Sheet music | persisted MusicXML derived from MIDI | adapter + E2E rendering |
| Analysis | persisted insights with evidence/confidence/provenance | analysis/domain tests + E2E |
| Reopen previous work | work bundle endpoint over immutable artifact versions | API + E2E |
| Command experience | deterministic commands over active persisted state | E2E |

## Not yet a product claim

- high-quality multi-instrument or all-genre transcription;
- editable corrections and notation round-tripping;
- comparative analysis across works or performances;
- generative melody/rhythm/harmony suggestions;
- grounded theory/history tutoring;
- imports from external music collections or microphone recording.

These remain the next capability slices. Each should produce a new immutable
version or evidence-backed insight and ship with an evaluation set before the UI
presents it as available.

## Operational release gate

A release is credible when static checks, unit/domain tests, production build,
mocked browser journeys, migrations, and a real deployed audio smoke test pass.
The last test needs deployment credentials and cannot be substituted with mocks.
