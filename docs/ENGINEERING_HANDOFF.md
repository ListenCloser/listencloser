# hello-ai — Engineering Handoff

> Comprehensive technical reference for the hello-ai Music AI Studio.
> Last updated: July 2026.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Frontend Architecture](#2-frontend-architecture)
3. [Backend Architecture](#3-backend-architecture)
4. [Data Model](#4-data-model)
5. [Auth Flow](#5-auth-flow)
6. [Audio Processing Pipeline](#6-audio-processing-pipeline)
7. [AI Chat System](#7-ai-chat-system)
8. [State Management](#8-state-management)
9. [Deployment](#9-deployment)
10. [Testing](#10-testing)
11. [Debugging Guide](#11-debugging-guide)
12. [Known Gotchas & Quirks](#12-known-gotchas--quirks)
13. [Environment Variables](#13-environment-variables)
14. [Key File Reference](#14-key-file-reference)

---

## 1. Architecture Overview

```
Browser (Next.js 15)
  │
  ├─ lib/api.ts ──────── Attaches Supabase JWT
  ├─ lib/music-api.ts ── Type-safe API wrappers
  │
  ▼
Next.js API Routes (thin proxies)
  │
  ├─ lib/backend.ts ──── proxyToBackend() reads MUSIC_BACKEND_URL
  │
  ▼
FastAPI (Oracle VM, ARM, always-free)
  │
  ├─ backend/main.py ─── Endpoints, auth, rate limiting
  ├─ backend/music_features.py ── Basic-pitch ML, FluidSynth, ffmpeg
  ├─ backend/analyze.py ── music21 analysis
  │
  ▼
Supabase (Postgres + Storage + Auth)
  │
  ├─ library bucket ──── User audio: library/<uid>/<ts>-<name>.ext
  ├─ transcriptions bucket ── Metadata: <uid>/<name>.json
  ├─ midi bucket ─────── Generated MIDI files
  ├─ enhanced bucket ─── Cleaned audio
```

**Key principle:** The browser **never** talks to the Oracle backend directly. All requests go through Next.js API routes which proxy server-side. This keeps the VM URL and service-role key off the client.

---

## 2. Frontend Architecture

### 2.1 Layout Shell (`components/Studio.tsx`)

```
┌─────────────┬──────────────────────────┬──────────┐
│  SIDEBAR    │  MAIN CONTENT            │ CHAT     │
│  260px      │  flex: 1                 │ PANEL    │
│             │                          │ 340px    │
│ Library     │ TrackWorkspace           │ or FAB   │
│ (sidebar)   │ (when track selected)    │          │
│             │                          │          │
│             │ Empty state              │          │
│             │ (when no track)          │          │
└─────────────┴──────────────────────────┴──────────┘
```

The app is organized around **musical assets**, not features. Clicking a song in the library opens its workspace. There are no top-level tabs.

### 2.2 Component Hierarchy

```
app/layout.tsx
  └─ AuthProvider (Supabase session context)
       └─ MSWInit (mock service worker, dev/test)
            └─ app/page.tsx → HomeClient
                 └─ Studio (SharedAudioProvider wraps everything)
                      ├─ Library (sidebar)
                      ├─ TrackWorkspace (main)
                      │    ├─ PipelineStep (processing indicator)
                      │    ├─ Transport bar (play/pause/seek/source)
                      │    ├─ Overview tab
                      │    │    ├─ Analysis summary (blurb + highlights)
                      │    │    ├─ Stat cards (key, tempo, time, notes)
                      │    │    ├─ Representations grid
                      │    │    │    ├─ Spectrogram (WaveSurfer)
                      │    │    │    ├─ PianoRoll (SVG)
                      │    │    │    ├─ SheetMusic (OSMD)
                      │    │    │    ├─ ChromaHeatmap (SVG bars)
                      │    │    │    └─ Tonnetz (SVG hex grid)
                      │    │    ├─ ChordTimeline
                      │    │    └─ Roman numeral chips
                      │    └─ Analysis tab (full Analysis component)
                      └─ ChatPanel (right sidebar or FAB)
                           └─ MusicChat (useChat + tool rendering)
```

### 2.3 Component Details

#### `Studio.tsx` — Main Shell
- **State:** `selectedTrack: LibFile | null`, `chatOpen: boolean`, `refreshKey: number`
- **Callbacks:** `handleTrackSelect`, `handleTrackDeleted`, `handleTrackUpdated`, `handleTranscribed`, `handleAnalyzed`
- **Auth:** `signIn()` → Google OAuth via Supabase, `signOut()` → clears token cache + reload

#### `library/index.tsx` — Library Sidebar
- Upload: drag-drop + file picker → `uploadToLibrary(name, blob)`
- Record: `MediaRecorder` API → webm blob → upload
- Track list: `deriveTrackState()` for badges (Audio, MIDI, Score, Analysis)
- Playback: `useSharedAudio()` toggle per track
- Metadata: size, time ago, BPM, key

#### `TrackWorkspace.tsx` — Asset Workspace
- **Auto-processing pipeline:** transcribe → sheet music → analyze (runs on mount if `autoProcess=true`)
- **Transport:** `useTransport()` hook for unified playback with source switching
- **Overview tab:** grouped representations with purpose labels
- **Analysis tab:** full `<Analysis>` component

#### `ChatPanel.tsx` — AI Chat
- Quick actions change based on `selectedTrack`
- Tool results render as interactive cards (PianoRoll, audio players, analysis summaries)
- `useChat()` from `@ai-sdk/react` with SSE streaming

#### `PianoRoll.tsx` — Piano Roll
- SVG-based, 24px row height, 40px label width
- Velocity-based opacity (0.2–0.8)
- Beat grid with measure lines every 4 beats
- Playhead line with triangle marker, auto-scrolls to follow

#### `SheetMusic.tsx` — Sheet Music
- Dynamically imports `opensheetmusicdisplay`
- Renders MusicXML as SVG, max height 500px

#### `Visualizer.tsx` — Audio Waveform
- Canvas + Web Audio API (`createMediaElementSource` → `createAnalyser` → `destination`)
- Top: time-domain waveform, Bottom 32%: frequency-domain bars
- Caches AudioContext per audio element (WeakMap)

#### `Spectrogram.tsx` — WaveSurfer
- WaveSurfer.js with `SpectrogramPlugin`, FFT 512, Hann window

#### `ChromaHeatmap.tsx` — Pitch Class Distribution
- 12 SVG bars, duration-weighted via `computeChroma()`
- Black keys at 50% opacity, white keys at 85%

#### `Tonnetz.tsx` — Harmonic Network
- SVG hexagonal grid, fifths horizontal, thirds diagonal

### 2.4 Lib Layer

| Module | Purpose |
|--------|---------|
| `lib/api.ts` | Authenticated `apiFetch()` with 60s token cache |
| `lib/backend.ts` | `proxyToBackend()` — forwards to FastAPI |
| `lib/music-api.ts` | Type-safe wrappers: `transcribeAudio`, `analyzeAudio`, `synthAudio`, etc. |
| `lib/library.ts` | Supabase Storage CRUD: `uploadToLibrary`, `listLibrary`, `saveTranscription`, `deleteFromLibrary` |
| `lib/storage.ts` | Generic helpers: `uploadFile`, `listFiles`, `getPublicUrl`, `deleteFile` |
| `lib/types.ts` | `TranscribeResult`, `LibFile`, `TrackState`, `deriveTrackState()` |
| `lib/audio-context.tsx` | `SharedAudioProvider` — single `<audio>` element, one track at a time |
| `lib/browser-store.ts` | `localStorage` (transcription cache) + `sessionStorage` (UI state) |
| `lib/midi.ts` | `notesToMidiBase64()` — Type 0 MIDI, 480 TPQ, 120 BPM |
| `lib/notes.ts` | `SHARP_NOTE_NAMES`, `FLAT_NOTE_NAMES`, `pitchToName()`, `computeChroma()` |
| `lib/format.ts` | `blobToBase64()` (chunked), `formatTime()`, `audioFmtFromName()` |
| `lib/tools/index.ts` | 6 AI chat tools (list_library, upload_audio, transcribe_audio, etc.) |

### 2.5 Hooks

| Hook | Purpose |
|------|---------|
| `hooks/useStudioState.ts` | Central state: tabs, transcription, analysis, library, viz, auth (30+ returned values) |
| `hooks/useTransport.ts` | Unified transport: source switching (Original/MIDI/Synth), synchronized time, seek |

---

## 3. Backend Architecture

### 3.1 FastAPI Server (`backend/main.py`)

| Endpoint | Method | Auth | Rate Limit | Purpose |
|----------|--------|------|------------|---------|
| `/health` | GET | None | None | Health check |
| `/health/live` | GET | None | None | Liveness probe |
| `/health/ready` | GET | None | None | Readiness (checks Supabase) |
| `/music/transcribe` | POST | Optional | 10/min | Audio → MIDI + notes |
| `/music/enhance` | POST | Optional | 20/min | Denoise/declip/normalize |
| `/music/analyze` | POST | Optional | 30/min | MIDI → music theory |
| `/music/synth` | POST | Optional | 30/min | MIDI → WAV |
| `/music/convert` | POST | Optional | 30/min | MIDI ↔ MusicXML |
| `/music/library` | GET/POST | Required | 10/min | List/upload library |
| `/music/library/{path}` | DELETE | Required | 30/min | Delete library file |

**Auth:** `verify_token()` validates Supabase JWT via service-role key. `verify_token_optional()` returns `None` instead of 401 when no token (allows anonymous processing).

**Rate limiting:** slowapi with `get_remote_address`. Default 60/min.

**Upload limit:** 25 MB decoded (`MAX_UPLOAD_BYTES = 26214400`).

### 3.2 Audio Processing (`backend/music_features.py`)

| Function | Input → Output | Tech |
|----------|---------------|------|
| `transcribe_audio()` | Audio bytes → MIDI + WAV + notes | basic-pitch ML model |
| `midi_to_wav()` | MIDI bytes → WAV bytes | FluidSynth (primary) / numpy (fallback) |
| `enhance_audio()` | Audio bytes → cleaned WAV | ffmpeg: `afftdn` + `adeclip` + `loudnorm` |
| `convert_format()` | Data bytes → converted bytes | music21 (MIDI ↔ MusicXML) |
| `_clean_midi()` | MIDI bytes → cleaned MIDI | Removes <50ms notes, deduplicates, normalizes velocity |

**MIDI Synthesis Fallback:**
- Primary: FluidSynth + `FluidR3_GM.sf2` SoundFont
- Fallback: numpy additive synthesis (4 harmonics, ADSR envelope)
- Both: 16-bit PCM WAV at 22050 Hz

### 3.3 Music Analysis (`backend/analyze.py`)

Entry point: `analyze_midi(midi_path)` → `AnalysisResult` TypedDict

| Component | Library | Notes |
|-----------|---------|-------|
| Key estimation | music21 `score.analyze("key")` | tonic, mode, confidence |
| Tempo | pretty_midi | Median of all tempo changes |
| Time signature | pretty_midi | First signature found |
| Chords | music21 `Chord` objects | Root + quality mapping |
| Roman numerals | music21 `roman.romanNumeralFromChord()` | Capped at 500 |
| Cadences | Custom pattern matching | 8 patterns: authentic, plagal, half, deceptive |
| Voice leading | music21 `voiceLeading` | Capped at 2000 quartets |
| Modulations | Custom windowed pitch-class analysis | 8 windows, Krumhansl-Schmuckler profiles |
| Rhythm | pretty_midi + custom | beat_count, syncopation_ratio, rhythmic_density |

---

## 4. Data Model

### 4.1 Core Types (`lib/types.ts`)

```typescript
Note = { pitch: number; start: number; end: number; velocity: number }

TranscribeResult = {
  notes: Note[];
  num_notes: number;
  midi_base64?: string;
  analysis?: Analysis;
}

Analysis = {
  key: { tonic: string; mode: string; confidence: number };
  tempo?: { bpm: number; confidence: number };
  time_signature?: { numerator: number; denominator: number; confidence: number };
  chords?: { root: string; quality: string; start: number; end: number }[];
  roman_numerals?: { figure: string; root: string; quality: string; start: number; end: number }[];
  cadences?: { type: string; chords: string[]; position: number }[];
  modulations?: { from_key: string; to_key: string; position: number }[];
  voice_leading?: { parallel: number; contrary: number; oblique: number; similar: number; motion_summary: string };
  phrases?: { start: number; end: number; kind: string }[];
  rhythm?: { beat_count: number; avg_note_duration: number; syncopation_ratio: number; rhythmic_density: number };
}

LibFile = {
  name: string; url: string; id: string; size?: number; created_at?: string;
  notes?: Note[]; midi_base64?: string; musicxml?: string;
  synth_wav_base64?: string; analysis?: Analysis;
}

TrackState = { uploaded: boolean; transcribed: boolean; sheetMusic: boolean; analysis: boolean; hasMidi: boolean }
```

**⚠️ CRITICAL:** `Analysis` in `lib/types.ts` and `AnalysisResult` in `backend/analyze.py` must be kept in manual sync. There is no codegen or shared schema. Any change requires updating both sides.

### 4.2 Supabase Storage Structure

| Bucket | Path Pattern | Purpose |
|--------|-------------|---------|
| `library` | `library/<uid>/<timestamp>-<name>.ext` | User audio uploads |
| `transcriptions` | `<uid>/<name>.json` | Transcription metadata (notes, midi, analysis, musicxml) |
| `midi` | `midi/<filename>.mid` | Generated MIDI files |
| `enhanced` | `enhanced/<filename>.wav` | Enhanced audio |
| `audio` | `audio/<filename>.wav` | Generated audio |

### 4.3 Supabase Tables

| Table | Purpose |
|-------|---------|
| `tracks` | Stored audio generations (prompt, model, audio_path) |
| `jobs` | Training runs (status: queued/running/done/error) |
| `models` | LoRA adapters (name, adapter_path) |

### 4.4 RLS Policies

- **Library:** Owner-scoped via `storage.foldername(name)[2] = auth.uid()` (note: index 2 because `library/` prefix adds a segment)
- **Transcriptions:** Owner-scoped via `storage.foldername(name)[1] = auth.uid()`
- **Backend-written buckets** (midi, enhanced): authenticated-only INSERT (service-role bypasses RLS)
- All buckets: public READ

---

## 5. Auth Flow

### 5.1 Sign-In (Google OAuth, PKCE)

```
1. User clicks "Sign in"
   → supabase.auth.signInWithOAuth({ provider: "google", redirectTo })

2. Google redirects to /auth/callback?code=...&next=...

3. Server route extracts code + next
   → Redirects to /auth/confirm?code=...&next=...

4. Client page calls supabase.auth.exchangeCodeForSession(code)
   → Redirects to next path

5. AuthProvider detects session via onAuthStateChange
   → Studio re-renders with signedIn={true}

6. All API calls now include Authorization: Bearer <jwt>
```

### 5.2 Sign-Out

```
1. clearTokenCache() — clears in-memory JWT
2. supabase.auth.signOut() — clears server session
3. window.location.reload() — full page refresh
```

### 5.3 Token Management (`lib/api.ts`)

- Token cached for 60 seconds
- On 401: cache cleared, next call re-fetches
- On sign-out: `clearTokenCache()` must be called explicitly

### 5.4 Dev/Test Bypass

When `NODE_ENV === "development"` or `NEXT_PUBLIC_MOCK_ENABLED === "true"`:
- `BYPASS_AUTH = true` in HomeClient
- MSW service worker intercepts all API calls
- Auth is effectively bypassed

---

## 6. Audio Processing Pipeline

### 6.1 Transcribe Flow

```
Audio upload/record
  → enhanceAudio() — ffmpeg: denoise, declip, normalize
  → transcribeAudio() — basic-pitch ML model
    → Returns: { notes[], midi_base64, wav_base64 }
  → synthAudio() — FluidSynth MIDI → WAV
  → Display: PianoRoll, Visualizer
  → Auto-save to Supabase if signed in
```

### 6.2 Sheet Music Flow

```
MIDI (from transcription)
  → convertMusicFormat(midi, "midi", "musicxml")
    → music21: parse MIDI, quantize to 16th note grid, write MusicXML
  → Display: SheetMusic (OSMD renderer)
```

### 6.3 Analysis Flow

```
MIDI (from transcription)
  → analyzeAudio(midi_base64)
    → music21: key, chords, Roman numerals, cadences, modulations, voice leading
    → pretty_midi: tempo, time signature, rhythm stats
    → Custom: windowed modulation detection, cadence pattern matching
  → Display: Analysis component (summary, stats, chord timeline, etc.)
```

### 6.4 Auto-Process on Track Selection

When a track is selected in the workspace:
1. If no notes → transcribe
2. If no MusicXML → convert MIDI to sheet music
3. If no analysis → analyze
4. Save results to Supabase

Pipeline steps shown visually: Transcribe → Sheet → Analyze

---

## 7. AI Chat System

### 7.1 Architecture

```
Browser (useChat hook)
  → POST /api/chat (SSE stream)
    → streamText() with @ai-sdk/openai (OpenRouter)
      → Default model: google/gemma-4-26b-a4b-it:free
      → Tools: list_library, upload_audio, transcribe_audio, analyze_midi, enhance_audio, convert_format
      → Each tool calls FastAPI directly (not through Next.js API routes)
```

### 7.2 Available Tools

| Tool | What It Does |
|------|-------------|
| `list_library` | Lists user's tracks with metadata |
| `upload_audio` | Uploads audio to Supabase Storage |
| `transcribe_audio` | Audio → MIDI via basic-pitch |
| `analyze_midi` | MIDI → music theory analysis |
| `enhance_audio` | Denoise/declip audio |
| `convert_format` | MIDI ↔ MusicXML |

### 7.3 Tool Auth

Tools call the FastAPI backend directly (not through Next.js API routes). Auth is threaded via `setRequestAuthHeader()` — a module-level side effect. **Be careful with concurrent requests.**

### 7.4 Chat UI Patterns

- Tool results render as interactive cards (PianoRoll, audio players, analysis summaries)
- Quick actions change based on selected track context
- Messages persisted to sessionStorage (last 50)
- File attachment: audio → base64 encoded in message text

---

## 8. State Management

### 8.1 No Global Store

There is no Redux, Zustand, or Jotai. State is managed through:

| Layer | Mechanism | Location |
|-------|-----------|----------|
| Auth | React Context | `AuthProvider.tsx` |
| Audio | React Context | `SharedAudioProvider` (audio-context.tsx) |
| Studio | `useStudioState` hook | `hooks/useStudioState.ts` |
| Workspace | Local `useState` | `TrackWorkspace.tsx` |
| Library | Local `useState` | `library/index.tsx` |
| Chat | `useChat()` + local state | `MusicChat.tsx` |
| Persistence | `browser-store.ts` | localStorage + sessionStorage |

### 8.2 Cross-Component Data Flow

```
Library → Studio: onTrackSelect(file) → setSelectedTrack(file)
Studio → TrackWorkspace: passes file, autoProcess, onTrackUpdated
TrackWorkspace → API: calls transcribe/convert/analyze directly
Chat → Studio: onTranscribed/onAnalyzed callbacks
```

### 8.3 Persistence Strategy

| Storage | What | Lifetime |
|---------|------|----------|
| `localStorage` | Local transcription cache (unsigned users) | Persistent |
| `sessionStorage` | Tab state, selected track, viz mode, chat messages | Per-tab |
| Supabase Storage | Library files + transcription JSON | Permanent (cloud) |

---

## 9. Deployment

### 9.1 Production Stack

| Component | Host | URL |
|-----------|------|-----|
| Frontend | Vercel | `https://hello-ai-wheat.vercel.app` |
| Backend | Oracle VM (always-free ARM) | `MUSIC_BACKEND_URL` (server-side only) |
| Database | Supabase | Managed Postgres + Storage + Auth |
| Monitoring | Sentry | DSN in env vars |
| CI/CD | GitHub Actions | Lint, build, test, E2E, visual regression |

### 9.2 Docker (Development)

```bash
docker compose up  # Starts: frontend (3000), backend (8000), opencode
```

### 9.3 Docker (Backend VM)

```bash
cd backend && docker compose up -d  # FastAPI + FluidSynth + ffmpeg
```

### 9.4 Observability Stack (Optional)

```bash
docker compose -f docker-compose.observability.yml up -d
# Loki (3100) + Promtail + Grafana (3001)
```

---

## 10. Testing

### 10.1 Unit Tests (Vitest)

```bash
npm test              # Run all
npm run test:watch    # Watch mode
```

Config: `vitest.config.ts` — jsdom environment, react plugin, `@` alias.

Test files: `tests/lib/*.test.ts`, `tests/components/*.test.tsx`

### 10.2 E2E Tests (Playwright)

```bash
npx playwright test    # Run all
npx playwright test --ui  # UI mode
```

Config: `playwright.config.ts` — MSW mock mode, 30s timeout, 1180×1000 viewport.

Test files: `tests/e2e/*.spec.ts`

**Note:** E2E tests run with `NEXT_PUBLIC_MOCK_ENABLED=true` — all API calls are mocked by MSW.

### 10.3 Visual Regression (Argos CI)

```bash
npx playwright test tests/visual/  # Generates screenshots
```

Argos CI compares screenshots against baseline. Visual changes require manual approval.

### 10.4 CI Pipeline

```
Push → GitHub Actions
  ├─ Lint (next lint + ruff check + ruff format)
  ├─ Build (next build)
  ├─ Unit tests (vitest)
  ├─ E2E tests (playwright + MSW)
  ├─ CodeQL (JS + Python)
  ├─ Dependency Review
  ├─ Secrets Scan (Gitleaks)
  ├─ Visual Regression (Argos)
  ├─ Semgrep SAST
  └─ Vercel Preview Deployment
```

---

## 11. Debugging Guide

### 11.1 Common Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 401 on API calls | Token expired or not attached | Check `lib/api.ts` token cache; call `clearTokenCache()` |
| 502 from API routes | Backend down or unreachable | Check `MUSIC_BACKEND_URL`, verify backend health |
| Transcription returns empty notes | basic-pitch failed silently | Check backend logs for `transcribe_audio` errors |
| MIDI playback silent | FluidSynth/SoundFont missing | Check `SOUNDFONT_PATH`, backend falls back to numpy |
| Sheet music blank | MusicXML conversion failed | Check `/music/convert` endpoint, music21 parse errors |
| Analysis empty | MIDI too short or no notes | Needs ≥32 notes for modulation detection |
| Supabase 403 | RLS policy mismatch | Check `storage.foldername()` path index (library=[2], transcriptions=[1]) |
| Chat tools not working | Auth header not threaded | Check `setRequestAuthHeader()` in `lib/tools/index.ts` |
| Session lost on refresh | PKCE flow issue | Ensure `detectSessionInUrl: false` in Supabase config |

### 11.2 Debugging Tools

- **Backend health:** `GET /health/ready` — checks Supabase connectivity
- **Sentry:** Error tracking with source maps (both frontend and backend)
- **Structured logging:** Backend logs JSON with `req_id`, `level`, `msg`
- **Loki/Grafana:** `docker compose -f docker-compose.observability.yml up` for log visualization
- **MSW:** Set `NEXT_PUBLIC_MOCK_ENABLED=true` to intercept all API calls
- **Playwright:** `npx playwright test --ui` for interactive debugging

### 11.3 Backend Local Development

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Requires: Python 3.11, ffmpeg, FluidSynth, SoundFont at `SOUNDFONT_PATH`.

### 11.4 Frontend Local Development

```bash
npm install
npm run dev  # http://localhost:3000
```

Set `NEXT_PUBLIC_MOCK_ENABLED=true` to use MSW mocks (no backend needed).

---

## 12. Known Gotchas & Quirks

### Critical

1. **Analysis schema sync:** `AnalysisResult` in `backend/analyze.py` and `TranscribeResult["analysis"]` in `lib/types.ts` must be kept in manual sync. There is no codegen.

2. **RLS path index mismatch:** Library uses `storage.foldername(name)[2]` (because `library/` prefix adds a segment), transcriptions uses `[1]`. Getting this wrong breaks RLS.

3. **Auth asymmetry:** Frontend reads use Supabase client SDK (anon key + RLS). Backend writes use service-role key (bypasses RLS). Backend uploads work even though RLS says "authenticated only."

4. **Token caching:** `lib/api.ts` caches JWT for 60 seconds. On sign-out, `clearTokenCache()` must be called or stale tokens persist.

5. **PKCE flow:** `detectSessionInUrl: false` is critical for Google OAuth. The `?code=` param must NOT be auto-consumed on init.

### Behavioral

6. **MIDI analysis duality:** `analyze_midi()` calls `score.analyze("key")` twice — once for the key result, once to pass as a parameter. This is by design, not a bug.

7. **FluidSynth graceful degradation:** Backend falls back to numpy synthesis if FluidSynth or SoundFont is missing. The VM must have both for natural timbre.

8. **Upload size limit:** 25 MB applies to decoded bytes, not the base64 string.

9. **Chat tool auth threading:** `setRequestAuthHeader()` is a module-level side effect. Be careful with concurrent requests (though fine for serverless).

10. **Promtail only scrapes backend:** Frontend logs on Vercel are separate from the Loki/Grafana stack.

### Performance

11. **CPU-only backend:** Oracle always-free ARM VM. Transcription/analysis suitable for short clips (seconds to minutes). Long recordings will be slow.

12. **Single audio element:** `SharedAudioProvider` reuses one `<audio>` element. Only one track plays at a time across the entire app.

13. **MIDI timing:** When playing synthesized MIDI, a `setInterval` at 50ms tracks position. This can drift slightly from real audio time.

---

## 13. Environment Variables

### Frontend (`.env.local` / Vercel)

| Variable | Required | Purpose |
|----------|----------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Supabase anon key |
| `MUSIC_BACKEND_URL` | Yes | Backend URL (server-side only) |
| `OPENAI_API_KEY` | Yes (chat) | OpenRouter API key |
| `CHAT_MODEL` | No | Model ID (default: `google/gemma-4-26b-a4b-it:free`) |
| `NEXT_PUBLIC_SENTRY_DSN` | No | Sentry DSN |
| `NEXT_PUBLIC_MOCK_ENABLED` | No | Enable MSW mock mode |
| `NEXT_PUBLIC_SITE_URL` | No | Canonical site URL for OAuth |

### Backend (Oracle VM)

| Variable | Required | Purpose |
|----------|----------|---------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Service-role JWT |
| `SOUNDFONT_PATH` | No | FluidR3_GM.sf2 path (default: `/app/soundfonts/FluidR3_GM.sf2`) |
| `SENTRY_DSN_BACKEND` | No | Backend Sentry DSN |
| `SENTRY_ENV` | No | Environment label (default: "production") |
| `MAX_UPLOAD_BYTES` | No | Upload size cap (default: 26214400) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |

---

## 14. Key File Reference

### Core

| File | Purpose |
|------|---------|
| `components/Studio.tsx` | Main app shell (3-panel layout) |
| `components/TrackWorkspace.tsx` | Track workspace (processing + viz + analysis) |
| `components/library/index.tsx` | Library sidebar |
| `components/ChatPanel.tsx` | AI chat panel |
| `hooks/useTransport.ts` | Unified playback transport |
| `hooks/useStudioState.ts` | Central state management |
| `app/globals.css` | Complete design system |

### API Layer

| File | Purpose |
|------|---------|
| `lib/api.ts` | Authenticated fetch wrapper |
| `lib/backend.ts` | Reverse proxy to FastAPI |
| `lib/music-api.ts` | Type-safe API client |
| `lib/library.ts` | Supabase Storage CRUD |
| `lib/tools/index.ts` | AI chat tools |

### Backend

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI server (endpoints, auth, rate limiting) |
| `backend/music_features.py` | Audio processing (transcription, synthesis, enhancement) |
| `backend/analyze.py` | Music theory analysis |

### Data

| File | Purpose |
|------|---------|
| `lib/types.ts` | Domain types (TranscribeResult, LibFile, Analysis) |
| `lib/browser-store.ts` | Client-side persistence |
| `lib/audio-context.tsx` | Shared audio playback context |

### Visualization

| File | Purpose |
|------|---------|
| `components/PianoRoll.tsx` | SVG piano roll with playhead |
| `components/SheetMusic.tsx` | OSMD sheet music renderer |
| `components/Spectrogram.tsx` | WaveSurfer spectrogram |
| `components/ChromaHeatmap.tsx` | Pitch class distribution bars |
| `components/Tonnetz.tsx` | Harmonic relationship hex grid |
| `components/Visualizer.tsx` | Canvas audio waveform + frequency bars |
| `components/analyze/index.tsx` | Full analysis display |
