# hello-ai · Music AI Studio

Turn audio into MIDI and **playable sheet music**. Upload or record audio, get a transcription (basic-pitch on an Oracle VM), and a synthesized score you can play back in the browser. Files persist to Supabase, and music analysis (key, tempo, chords, cadences) is shown after transcription.

## Live Demo

[hello-ai.vercel.app](https://hello-ai.vercel.app)

## Features

- **Library** — Upload, record, play, and delete audio in Supabase Storage
- **Transform** — Audio → MIDI (basic-pitch) → sheet music (OpenSheetMusicDisplay) with playback
- **Visualize** — Piano roll, spectrogram, chroma heatmap, tonnetz, sheet music views
- **Analyze** — Key, tempo, chords, Roman numerals, cadences, modulations, voice leading
- **Chat** — AI assistant with music tools (Vercel AI SDK + OpenRouter)

## Architecture

```
Browser → Vercel (/api/music/*) → Oracle VM
                                   FastAPI :8000
                                     ├─ basic-pitch transcription
                                     ├─ FluidSynth MIDI→WAV
                                     ├─ ffmpeg enhance
                                     ├─ music21 analysis
                                     └─ Supabase (SERVICE_ROLE)
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
  music_features.py     basic-pitch transcription, FluidSynth
  analyze.py            music theory analysis (key, chords, cadences)
supabase/               Database + storage migrations
tests/                  Playwright E2E + visual comparison
docs/                   Documentation
```

## Testing

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

