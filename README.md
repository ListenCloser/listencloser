# hello-ai · Music AI Studio

Turn audio into persisted MIDI notes, playable rendered audio, MusicXML sheet
music, and evidence-backed musical analysis. Processing runs asynchronously on a
durable worker; the browser displays stored results rather than fabricated demo
data.

## Live Demo

[hello-ai.vercel.app](https://hello-ai.vercel.app)

## Features

- **Import** — Private authenticated audio upload to Supabase Storage
- **Transform** — Audio → MIDI notes → rendered WAV and MusicXML
- **Visualize** — Piano roll, waveform, and sheet music from real outputs
- **Analyze** — Key, tempo, meter, chords, Roman numerals, and cadences
- **Persist** — Immutable artifact versions, lineage, provenance, and durable jobs

## Architecture

```
Browser → Vercel (/api/v1/*) → FastAPI → Supabase/Postgres queue
                                      ↘ worker → music engines → artifacts
```

The browser never talks to the Oracle backend directly. All backend calls go through `app/api/*` → `lib/backend.ts`.

## Getting Started

```bash
npm install
npm run dev
```

## Project Structure

```
app/                    Next.js app router + API routes
components/             React UI components
lib/                    Shared utilities and API clients
backend/                FastAPI on Oracle VM
  main.py               API endpoints
  worker.py             Durable queue worker entrypoint
  music_features.py     basic-pitch transcription, FluidSynth
  analyze.py            music theory analysis (key, chords, cadences)
supabase/               Database + storage migrations
tests/                  Playwright E2E + visual comparison
docs/                   Documentation
```

**Key Rule:** The browser never talks to the Oracle backend directly. All backend calls go through `app/api/*` → `lib/backend.ts` (`proxyToBackend`), keeping the VM URL/key off the client.

The canonical `/` route is a workspace with unified transport, shared selection,
and domain entities (Projects, Works, Artifacts, Versions, Entities, Insights,
Alignments). See `docs/ARCHITECTURE.md` for current runtime truth and
`docs/ROADMAP.md` for the product sequence.

## Running Tests

### Component Tests (Vitest)

```bash
npm test                  # Unit tests (Vitest)
npm run typecheck         # TypeScript
npm run lint              # ESLint
npm run build             # Production build
npx playwright test       # E2E tests
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, TypeScript |
| Styling | Tailwind CSS v4, CSS custom properties |
| Backend | FastAPI, Python 3.11 |
| Transcription | basic-pitch (TensorFlow) |
| Synthesis | FluidSynth + numpy fallback |
| Analysis | music21, pretty_midi |
| Database | Supabase (PostgreSQL + Storage) |
| Auth | Supabase Auth (PKCE flow) |
| Monitoring | Sentry |
| CI/CD | GitHub Actions, Vercel |
