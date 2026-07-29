# hello-ai · Music AI Studio

Turn audio into MIDI and **playable sheet music**. Upload or record audio, get a transcription (basic-pitch on an Oracle VM), and a synthesized, cursor-highlighted score you can play back in the browser (abcjs). Files persist to Supabase, and a lightweight analysis (key, tempo, time signature) is shown after transcription.

## Live Demo

[hello-ai.vercel.app](https://hello-ai.vercel.app)

## Quick Links

- **📚 Documentation** – See `/docs/` for agent workflows, architecture, and setup guides
- **⚡ Key Documentation**
  - [README.md](README.md) – Project overview & navigation
  - [ARCHITECTURE.md](docs/ARCHITECTURE.md) – System design & autonomous loops
  - [AGENTS.md](docs/AGENTS.md) – Engineering source of truth for AI agents
  - [ROADMAP.md](docs/ROADMAP.md) – Current phase & feature roadmap
  - [PRODUCT_VISION.md](docs/PRODUCT_VISION.md) – North star & priorities
- **🔧 Developer Docs**
  - [LOCAL_DEV.md](docs/LOCAL_DEV.md) – Local setup (Vercel + Oracle + Supabase)
  - [E2E.md](docs/E2E.md) – User journey tests that block merges
- **🎨 Design**
  - [design/tokens.json](design/tokens.json) – Token definitions
- **📁 Project Structure**
```
app/                    — Next.js app (Vercel)
  lib/                  — Core libraries + backend proxy
backend/               — FastAPI on Oracle VM
  main.py               — API endpoints
  music_features.py     — basic-pitch transcription, FluidSynth
  analyze.py            — audio analysis (key, tempo, chords)
docs/                   — Documentation sources of truth
  README.md             — Project overview
  ARCHITECTURE.md       — System design & workflows
  AGENTS.md             — Engineering SOT for AI agents
  ROADMAP.md            — Feature roadmap
  ... (15+ files)
supabase/              — Database + storage migrations
public/                — Worker files for MSW (dev mock)
tests/                 — Playwright E2E + visual comparison
scripts/               — CI/CD + auto-merge helpers
```

## Features

### 🎵 Core Studio

- **Library** (`/?tab=library`) — Upload, record, play, and delete audio in Supabase
- **Transcribe** (`/?tab=transcribe`) — Audio → MIDI (basic-pitch) → rendered sheet music with playback
- **Analysis** — Key / tempo / time-signature detection shown inline after a transcription

### 🌐 Live Features

| Concern | Location |
|---------|----------|
| Page shell | `components/Studio.tsx` (tabbed shell) |
| Transcribe | `components/transcribe/index.tsx`, `components/PianoRoll.tsx` |
| Library | `components/library/index.tsx`, `components/Visualizer.tsx`, `lib/storage.ts` |
| Backend proxy | `lib/backend.ts`, `app/api/**/route.ts` |
| Design SOT | `design/tokens.json`, `design/mockups/*` |
| E2E journeys | `tests/e2e/journey.spec.ts` |

## Getting Started

### Local Development

```bash
# One-time setup
npm install

# Start dev server (frontend + mocked backend)
npm run dev

# Run E2E user journeys (needs Supabase auth in another terminal)
npx playwright test tests/e2e

# Run visual regression tests
npx playwright test tests/visual
```

### Production Features

- **Auth** — Supabase implicit OAuth flow, seamless session handling
- **Error Tracking** — Sentry SDK + Sentry MCP for agent self-diagnosis
- **CI/CD** — Vercel auto-deploys `main`, blocking PR checks (E2E + lint + build)
- **Visual QA** — Argos CI diff against design mockups

## Architecture Overview

```
Browser ──▶ Vercel (/api/music/*) ──▶ Oracle VM
                         Caddy :443 (HTTPS/Let's Encrypt)
                         FastAPI :8000
                           ├─ basic-pitch transcription
                           ├─ FluidSynth MIDI→WAV
                           └─ ffmpeg enhance
                           └─ Supabase (SERVICE_ROLE)
```

**Key Rule:** The browser never talks to the Oracle backend directly. All backend calls go through `app/api/*` → `lib/backend.ts` (`proxyToBackend`), keeping the VM URL/key off the client.

The app is transitioning to a **workspace architecture** at `/workspace` with a unified transport, shared selection, and domain model entities (Projects, Works, Artifacts, Versions, Entities, Insights, Alignments). See `docs/ORCHESTRATION.md` for the architectural roadmap and `docs/adr/ADR-007.md` for the migration plan from the reference `LibFile` model.

## Running Tests

### Component Tests (Vitest)

```bash
npm test
```

### E2E User Journeys (Playwright)

```bash
# Transcribe tab runs offline (mocked backend)
npx playwright test tests/e2e/journey.spec.ts

# Library tab needs real Supabase credentials
export NEXT_PUBLIC_SUPABASE_URL=... && npx playwright test tests/e2e/journey.spec.ts
```

### Visual Regression (Argos)

```bash
npx playwright test tests/visual/preview.spec.ts
# Uploads screenshots to Argos for diff against baseline
```

## Contributing

> This project uses autonomous AI agents with defined roles (PM → Designer → Auditor → Engineer → Picky User). Read `docs/AGENTS.md` first.

### Feature Checklist

For **new features**, follow the standard workflow:

1. **Design (UI Designer)** → Add component to `components/<feature>/index.tsx`
   - Read `docs/specs/<feature>.md` (PM spec)
   - Use design tokens from `design/tokens.json`

2. **Engineering** → Implement per conventions:
   - `components/` one component per file
   - `app/api/<feature>/route.ts` if backend needed
   - Write E2E in `tests/e2e/journey.spec.ts`

3. **Testing** → Verify everything passes:
   - `npm run typecheck`
   - `npx playwright test --reporter=line`
   - `npm run build`

## Roadmap

See `docs/ROADMAP.md` for the current phase and full feature sequencing.

## Documentation

| Document | Purpose |
|----------|---------|
| `docs/PRODUCT_VISION.md` | North star + principles |
| `docs/ROADMAP.md` | Current focus + feature sequencing |
| `docs/ARCHITECTURE.md` | System design + CI workflow |
| `docs/AGENTS.md` | Engineering SOT for AI agents |
| `docs/DEVELOPMENT.md` | Docker + local setup |
| `docs/E2E.md` | Why E2E tests are blocking |
| `docs/CHANGELOG.md` | Recent changes + gotchas |

## Links

- [Main Site](https://hello-ai.vercel.app)
- [GitHub](https://github.com/agent-of-empires/hello-ai)
- [Architecture Diagram](docs/ARCHITECTURE.md#1-system-at-a-glance)
