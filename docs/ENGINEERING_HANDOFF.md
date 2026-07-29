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

Runs on Oracle always-free ARM VM. FastAPI + uvicorn. The browser never talks to this directly — all requests come through Next.js API routes that call `proxyToBackend()`.

#### Endpoints

| Endpoint | Method | Auth | Rate Limit | Purpose |
|----------|--------|------|------------|---------|
| `/health` | GET | None | None | Health check |
| `/health/live` | GET | None | None | Liveness probe |
| `/health/ready` | GET | None | None | Readiness (checks Supabase) |
| `/music/transcribe` | POST | Optional | 10/min | Audio → MIDI + notes + WAV |
| `/music/enhance` | POST | Optional | 20/min | Denoise/declip/normalize via ffmpeg |
| `/music/analyze` | POST | Optional | 30/min | MIDI → key, tempo, chords, cadences, etc. |
| `/music/synth` | POST | Optional | 30/min | MIDI → WAV (FluidSynth or numpy) |
| `/music/convert` | POST | Optional | 30/min | MIDI ↔ MusicXML via music21 |
| `/music/library` | GET/POST | Required | 10/min | List/upload library files |
| `/music/library/{path}` | DELETE | Required | 30/min | Delete library file (owner check) |

#### Auth System

Two auth dependencies:

- **`verify_token()`** — extracts Bearer token, validates via `sb.auth.get_user(token)` using service-role key. Returns user object or raises 401. On network/timeout errors, returns 503 (handles Supabase outages gracefully).
- **`verify_token_optional()`** — same but returns `None` instead of 401 when no token. Used on processing endpoints so anonymous users can still transcribe/analyze.

Write endpoints (library upload, delete) require auth. Processing endpoints (transcribe, analyze, synth, enhance, convert) use optional auth.

#### Supabase Client

Lazy-initialized singleton `_sb()` using `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`. Thread-safe via `threading.Lock`. The service-role key bypasses RLS, which is how backend writes work despite RLS policies saying "authenticated only."

#### Middleware

- **Observability:** assigns `x-request-id` (from header or generates hex16), logs `method/path/status/duration_ms` as structured JSON.
- **CORS:** origins from `CORS_ORIGINS` env (comma-separated), defaults to `https://hello-ai-wheat.vercel.app` + `http://localhost:3000`.
- **Rate limiting:** slowapi with `get_remote_address`. Default 60/min, per-endpoint overrides.
- **Upload limit:** 25 MB decoded (`MAX_UPLOAD_BYTES = 26214400`). Checked on base64-decoded bytes, not the string.

### 3.2 Audio Transcription Pipeline (`backend/music_features.py`)

#### `transcribe_audio(audio_bytes, fmt, onset_threshold=0.5, frame_threshold=0.3)`

This is the core pipeline that turns raw audio into MIDI + notes + WAV:

```
1. Write audio to temp file (input.wav)
   │
2. basic-pitch.inference.predict(in_path, onset_threshold, frame_threshold)
   │  Returns: (_, midi_data, note_events)
   │  - midi_data: pretty_midi.PrettyMIDI object (written to input.mid)
   │  - note_events: list of (start_s, end_s, pitch, velocity, onsets) tuples
   │
3. _clean_midi(midi_bytes)  ← post-processing
   │  a. Remove notes shorter than 50ms (spurious detections)
   │  b. Remove duplicate/overlapping notes at same pitch
   │     (sort by pitch then start, merge overlapping)
   │  c. Normalize velocities to 0-127 range
   │  Skips drums (inst.is_drum)
   │
4. Extract note list from note_events
   │  notes = [{pitch, start, end, velocity}, ...]
   │
5. midi_to_wav(midi_bytes)  ← synthesize audio
   │  (see section 3.3)
   │
6. Return: { midi, wav, notes, num_notes }
```

**basic-pitch** is Spotify's ML model for audio-to-MIDI transcription. It runs on CPU (TensorFlow). The `onset_threshold` (default 0.5) controls note onset sensitivity — lower = more notes detected. The `frame_threshold` (default 0.3) controls frame-level activation — lower = more notes but more noise.

#### `midi_to_wav(midi_bytes, sr=22050)`

Two-tier synthesis with automatic fallback:

**Primary: FluidSynth** (`_midi_to_wav_fluidsynth`)
1. Check if SoundFont exists at `SOUNDFONT_PATH` (default `/app/soundfonts/FluidR3_GM.sf2`)
2. Import `fluidsynth` (pyfluidsynth). If unavailable, return None.
3. Create `fluidsynth.Synth(samplerate=22050)`
4. Load SoundFont, select bank 0, program 0 (Acoustic Grand Piano)
5. Apply light reverb (`room=0.25, damp=0.4, width=0.6, level=0.12`) and chorus (2 voices, depth=0.04)
6. Render MIDI → WAV via `fs.midi2audio()`
7. Peak-normalize to 0.95 (FluidSynth output is typically quiet)
8. Return 16-bit PCM WAV

**Fallback: numpy additive synth** (`_midi_to_wav_numpy`)
- Self-contained polyphonic piano synth. No external dependencies beyond numpy + pretty_midi.
- For each note: compute frequency from MIDI pitch (`440 * 2^((pitch-69)/12)`)
- Generate 4 harmonics: `(1, 1.0), (2, 0.3), (3, 0.12), (4, 0.06)` — simulates piano timbre
- Apply ADSR envelope: attack=10ms, release=150ms
- Mix all notes into output buffer, clip to [-1, 1], convert to int16 PCM
- Both produce: **16-bit PCM WAV at 22050 Hz**

#### `enhance_audio(audio_bytes, fmt)`

Pre-processing step that runs before transcription (transparent to user):

```
1. Write audio to temp file
   │
2. Pre-convert non-standard formats to WAV
   │  basic-pitch only reads: wav, flac, ogg, mp3, m4a, aac
   │  ffmpeg: -y -i input -ac 1 -ar 22050 input_conv.wav
   │
3. Run cleanup pipeline:
   │  ffmpeg -af "afftdn=nr=12:nf=-30,adeclip,loudnorm=I=-16:TP=-1.5:LRA=11"
   │         -ar 22050 -ac 1 output.wav
   │
   │  afftdn: FFT denoiser (nr=12dB noise reduction, nf=-30dB noise floor)
   │  adeclip: declipper (fixes clipping distortion)
   │  loudnorm: EBU R128 loudness normalization (I=-16 LUFS, TP=-1.5 dBTP)
   │
4. Output: mono, 22050 Hz WAV
5. Falls back to raw input if ffmpeg fails (no-op safe)
```

#### `convert_format(data, source, target)`

MIDI ↔ MusicXML conversion via music21:

```
1. Write data to temp file (input.mid or input.xml)
2. score = music21.converter.parse(in_path)
3. If target == "musicxml": score.quantize(inPlace=True)
   (quantizes to 16th-note grid for cleaner notation)
4. score.write(fmt, fp=out_path)
5. Return converted bytes
```

**Gotcha:** `source == target` returns data unchanged (short-circuit).

### 3.3 Music Analysis Pipeline (`backend/analyze.py`)

#### `analyze_midi(midi_path)` → `AnalysisResult`

Single entry point. Parses MIDI once with music21, extracts everything. Uses pretty_midi only for tempo/time-signature metadata.

```
1. Parse MIDI:
   │  score = music21.converter.parse(midi_path, quantizePost=False)
   │  pm = pretty_midi.PrettyMIDI(midi_path)
   │
2. Tempo (pretty_midi):
   │  tempos = pm.get_tempo_changes()[1]
   │  result.tempo = median(tempos), confidence=0.9
   │  (median is more robust than mean for variable-tempo pieces)
   │
3. Time signature (pretty_midi):
   │  _, ts_nums, ts_denoms = pm.get_time_signatures()
   │  result.time_signature = first signature found, confidence=0.9
   │
4. Key estimation (_m21_key):
   │  key = score.analyze("key")
   │  Returns: tonic, mode, correlationCoefficient
   │
5. Chords (_m21_chords):
   │  For each Chord in score.flatten():
   │    root = chord.root().name
   │    quality = chord.impliedQuality → mapped via _QUALITY_MAP
   │    start/end = offset/duration in quarter notes
   │
6. Roman numerals (_m21_roman_numerals):
   │  For each Chord in each Measure:
   │    rn = roman.romanNumeralFromChord(chord, detected_key)
   │    Capped at 500 results
   │
7. Cadences (_m21_cadences):
   │  Build chord sequence from score
   │  Match consecutive pairs against 8 patterns:
   │    authentic: V→I, V7→I, V→i
   │    plagal: IV→I
   │    half: I→V, i→V
   │    deceptive: V→vi, V→VI
   │
8. Voice leading (_m21_voice_leading):
   │  For pairs of parts (up to 4):
   │    iterateAllVoiceLeadingQuartets → motionType()
   │    Count: parallel, contrary, oblique, similar
   │    Capped at 2000 quartets
   │
9. Rhythm (_midi_rhythm):
   │  Using pretty_midi:
   │  - beat_count: duration * bpm / 60
   │  - avg_note_duration: mean of all note lengths
   │  - syncopation_ratio: fraction of notes NOT on beat grid
   │    (beat_pos > 0.1 && beat_pos < 0.9 means off-beat)
   │  - rhythmic_density: total_notes / duration
   │
10. Modulations (_detect_modulations) ← CUSTOM:
    │  (see detailed breakdown below)
```

#### Modulation Detection — Custom Implementation

No out-of-the-box library handles this. The approach:

```
1. Collect all notes with (offset, pitch) from all parts
2. Convert quarter-note positions to seconds using tempo
3. Divide into 8 equal time windows
4. For each window:
   a. Collect pitches in that time range
   b. Compute 12-dim pitch-class distribution (Counter mod 12)
   c. Estimate key using Krumhansl-Schmuckler profiles:
      - Roll the distribution 12 times (once per tonic)
      - Correlate with _KS_MAJOR and _KS_MINOR profiles
      - Best correlation = estimated key
   d. Record: (window_start_sec, "Tonic mode")
5. Compare consecutive windows
6. Where key changes → modulation detected
```

The Krumhansl-Schmuckler profiles are empirically derived weight vectors:
```
_KS_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_KS_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
```

Each index corresponds to a pitch class (C, C#, D, ..., B). Higher values = more important in that key. The correlation between the window's pitch distribution and each profile determines the best-fit key.

**Minimum notes:** Requires ≥32 notes total (`_MODULATION_WINDOW_COUNT * 4`). Fewer notes → empty modulations list.

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

### 9.5 Open-Source Dependencies — What Does What

#### Backend (Python) — The Heavy Hitters

| Library | What It Does | Used For | Gotcha |
|---------|-------------|----------|--------|
| **basic-pitch** (Spotify) | ML model: audio → MIDI note events | Transcription | CPU-only (TensorFlow). Runs on ARM. ~2-5s for short clips. |
| **music21** | Symbolic music analysis library | Key, chords, Roman numerals, cadences, voice leading, MusicXML parse/write | HEAVY. First import takes ~2s. `score.analyze("key")` is expensive. |
| **pretty_midi** | MIDI file manipulation | Tempo/time-sig extraction, rhythm analysis, MIDI cleaning | Lightweight. Used alongside music21 (music21 handles harmony, pretty_midi handles metadata). |
| **FluidSynth** (pyfluidsynth) | MIDI → WAV synthesis via SoundFont | Natural piano timbre rendering | Requires `fluidsynth` binary + SoundFont file on disk. Falls back to numpy if missing. |
| **numpy** | Numerical computing | Additive synth fallback, pitch-class vectors, normalization | Also used by music21/pretty_midi internally. |
| **soundfile** (libsndfile) | Audio file I/O | WAV read/write for normalization | Requires `libsndfile1` system package. |
| **ffmpeg** | Audio processing | Denoise, declip, normalize, format conversion | External binary. 120s timeout. |

**Import chain:** `basic-pitch` pulls in `tensorflow` (~800MB). `music21` pulls in `matplotlib`, `numpy`, `chaos` (~200MB). Total backend image: ~2GB.

**Why two MIDI libraries?** music21 is brilliant for harmonic analysis (chords, Roman numerals, key detection) but slow for metadata extraction. pretty_midi is fast for tempo/time-sig/note-level operations but can't do harmonic analysis. They complement each other.

**Why custom modulation detection?** music21's `score.analyze("key")` works on the full Score object. For modulation detection, we need key estimation on time windows (sub-sections of the piece). There's no OOTB function for this. The Krumhansl-Schmuckler approach is a standard musicology technique — correlate pitch-class distribution against empirical profiles.

#### Frontend (TypeScript/JavaScript)

| Library | What It Does | Used For | Bundle Impact |
|---------|-------------|----------|---------------|
| **opensheetmusicdisplay** (OSMD) | MusicXML → SVG rendering | Sheet music display | ~500KB gzipped (dynamically imported) |
| **wavesurfer.js** | Audio waveform + spectrogram | Waveform visualization, spectrogram plugin | ~100KB gzipped |
| **@ai-sdk/react** | React hooks for AI chat | `useChat()` for SSE streaming | ~15KB |
| **@ai-sdk/openai** | OpenAI-compatible API client | Chat with OpenRouter | ~10KB |
| **@supabase/supabase-js** | Supabase client SDK | Auth, Storage, Realtime | ~60KB |
| **@sentry/nextjs** | Error monitoring | Sentry integration | ~30KB |
| **zod** | Schema validation | Tool input validation in chat | ~15KB |
| **tailwindcss** | CSS framework | Utility-first styling | 0KB (purged at build) |

**Dynamic imports:** OSMD and WaveSurfer are dynamically imported (`next/dynamic` or `import()`) to avoid loading ~600KB on initial page load. They only load when the user navigates to a visualization.

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
