> **Canonical direction moved:** `MASTER_SPEC.md` is now the authoritative product north star, analysis model, representation model, roadmap, and agent contract. This file is retained as historical context and a compact summary; where it conflicts with the master spec, the master spec wins.

# Product Vision — hello-ai·music-studio

## North Star

A music analysis and composition platform for everyone — whether you have
existing music, music theory knowledge, or neither. The product should help
you understand songs you already like, learn the music theory behind them,
and compose or generate new music.

## Core Capabilities (ordered by priority)

1. **Import existing music** — upload audio files, record from microphone,
   link from external sources.

2. **Convert unstructured audio → symbolic representations** — audio to MIDI
   (via Basic Pitch), then to MusicXML sheet music. Future representations
   may include chord charts, lead sheets, piano rolls, or DAW export.

3. **Music analysis** — high-level summaries: key / tempo / time signature
   detection, harmonic analysis, chord recognition, structural breakdown
   (verse/chorus/bridge), similarity search across a library, genre
   classification, music-theory explainers.

4. **Interactive composition playground** — suggest common chord sequences,
   start from templates, interactive progression builder, real-time
   feedback on harmonic function, voice-leading suggestions.

5. **Autonomous music generation** — generate new music from scratch or
   conditioned on existing pieces (style transfer, continuation, variation).
   Under the hood this supports fine-tuning / model specialization so
   the user can adapt the model to their own taste.

## Engineering Principles

- **Open source first** — prefer MIT/Apache-2.0 libraries and models.
  All application code is MIT (see LICENSE).
- **Limit scope** — build the minimum feature that delivers value.
  Avoid premature generalization. Delete dead code.
- **Clean UI re-use** — the CSS custom properties in `app/globals.css` are the
  runtime design-token source. No parallel visual system or fake controls.
- **Clear structure** — predictable file layout: `components/<feature>/`,
  `lib/`, `backend/`, `design/`. Each file has one responsibility.
- **PR validation** — every PR must pass CI: lint, typecheck, unit tests,
  E2E journeys, visual regression (Argos). Green status required to merge.
- **Delegate to sub-agents** — use task agents for exploration,
  implementation, testing, and documentation. Each agent gets a clear
  bounded task with verifiable output.
- **Source of Truth (SOT)** — all product, architecture, workflow, and
  agent instructions live in `docs/`. Agents read these before acting.
- **Document changes** — every significant change is captured in the PR
  description and summarized in `docs/CHANGELOG.md`.

## UX Principles

- **Progressive disclosure** — a beginner can just upload audio and see a
  score; an advanced user can dive into harmonic analysis and fine-tuning.
- **Visual-first** — waveforms, scores, chord diagrams, keyboards all render
  in-browser with zero server round-trips for interaction.
- **Library as hub** — the library is the single source of truth: upload,
  record, manage, then route to transcribe / analyze / generate.
- **Durable by default** — source files, jobs, versions, entities, and insights
  are persisted. Browser rendering can be local, but transcription and analysis
  are explicit server capabilities whose availability is shown honestly.

## Architecture

```
User Audio → [Private Artifact] → [Durable Understand Job]
                                           ↓
                         MIDI / Notes / Rendered Audio
                                           ↓
                              ┌────────────┴────────────┐
                              ↓                         ↓
                       MusicXML Score            Structured Analysis
```

The Next.js workspace is deployed on Vercel. Supabase provides authentication,
Postgres, the durable job queue, and private storage. The Oracle ARM backend runs
FastAPI plus a separate worker for heavy processing. See ADR-009 for why this
three-plane deployment remains the simplest viable entirely-free topology.
