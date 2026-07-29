# hello-ai UI Component Library

All reusable UI components used across the Music AI Studio. Components consume design tokens from `design/tokens.json` (accessed as CSS variables in `app/globals.css`). No hardcoded values are allowed.

## Component Directory

```
components/                    — All React components
  Studio.tsx                  — Main page shell (tabbed shell)
  AuthProvider.tsx            — Supabase session management
  MusicChat.tsx               — AI chat with music tools
  library/                    — Library UI suite
    index.tsx                 — Library control panel (upload, list, playback)
  PianoRoll.tsx               — SVG piano roll visualization
  SheetMusic.tsx              — OpenSheetMusicDisplay renderer
  Spectrogram.tsx             — WaveSurfer.js spectrogram
  ChromaHeatmap.tsx            — Pitch class distribution chart
  Tonnetz.tsx                 — Tonnetz visualization
  Visualizer.tsx              — Canvas audio visualizer
  MSWInit.tsx                 — Mock Service Worker init
  transcribe/                 — Transcription UI (drop zone, status, results)
    index.tsx                 — Core audio → MIDI flow
  analyze/                    — Analysis display widgets
    index.tsx                 — Key/tempo/time-signature display
  viz/                        — Visualization hub
    index.tsx                 — Multi-mode viz (piano roll, spectrogram, etc.)
```

## Token Usage

All components use design tokens as CSS variables:

```tsx
<div style={{ background: "var(--panel)", borderRadius: "var(--r-md)" }}>
  <span className="chip">Labels and badges</span>
</div>
```

| Category | CSS Var | Example |
|----------|---------|---------|
| Color | `--bg`, `--panel`, `--accent`, `--danger` | `background: var(--panel);` |
| Radius | `--r-sm` … `--r-full` | `border-radius: var(--r-lg);` |
| Spacing | `--s-1` … `--s-8` | `padding: var(--s-4);` |
| Typography | `--fs-*` — `--fs-2xl` | `font-size: var(--fs-lg);` |
| Elevation | `--shadow-*` — `--ring` | `box-shadow: var(--shadow-md);` |

## Component Reference

### 1. Studio.tsx — Main Page Shell

**Location**: `components/Studio.tsx`

The master layout component. Renders Transcribe, Library, or Analysis tab based on `step`.

**Props**

```tsx
{
  initialTab?: string;      // "library", "transcribe", "analyze" (default: "transcribe")
  signedIn?: boolean;       // Auth status (default: false)
}
```

**Features**

- Tab navigation between Library, Transcribe, Analysis
- Auth gating: shows "Sign In" button when not authenticated
- Analysis flow: propagates results from Transcribe → Analysis via callbacks

---

### 2. Transcribe/index.tsx — Audio Transcription Interface

**Location**: `components/transcribe/index.tsx`

Primary audio processing interface handling upload, enhancement, transcription, and result display.

**Workflow States**

| State | UI | Description |
|-------|----|-------------|
| "idle" | Empty state with upload/recording controls | Initial user interaction |
| "enhancing" | "Cleaning audio…" status | Run ffmpeg pipeline |
| "transcribing" | "Transcribing…" status | basic-pitch to MIDI conversion |
| "populated" | Results with Piano Roll + Sheet Music | Display notes, download MIDI |
| "error" | Error message with retry button | User feedback for failures |

**Props**

```tsx
{
  compact?: boolean;         // Minimal UI for embedded contexts
  signedIn?: boolean;        // Auth status
  onTranscribed?: (result, name) => void;  // Callback when transcription completes
  onGoToAnalyze?: () => void;  // Navigate to Analysis tab
  onAnalyze?: (audioBase64, fmt, name) => void;  // Trigger analysis
}
```

---

### 3. SheetMusic.tsx — Sheet Music Renderer

**Location**: `components/SheetMusic.tsx`

Renders MusicXML sheet music via OpenSheetMusicDisplay (OSMD) with SVG output.

**Props**

```tsx
{
  musicXml: string;  // MusicXML string to render
}
```

---

### 4. PianoRoll.tsx — Interactive Piano Keyboard

**Location**: `components/PianoRoll.tsx`

Interactive piano keyboard displaying notes from transcription with user interaction for melody input.

**Props**

```tsx
{
  notes: {
    pitch: number;      // MIDI pitch number
    start: number;       // Start time in seconds
    end: number;         // End time in seconds
    velocity: number;    // Note velocity (volume)
  }[];
}
```

---

### 5. Analysis/index.tsx — Music Analysis Display

**Location**: `components/analyze/index.tsx`

Displays key/tempo/time-signature analysis results from audio processing.

**Props**

```tsx
{
  analysis?: TranscribeResult["analysis"];  // Complete analysis result
  notes: TranscribeResult["notes"];        // Raw notes data
  audioName?: string;                       // Track name
  numNotes?: number;                         // Note count
}
```

---

### 6. Library/index.tsx — Audio Library Manager

**Location**: `components/library/index.tsx`

Audio file manager with upload, playback, deletion, and MusOpen integration.

**Props**

```tsx
{
  compact?: boolean;         // Minimal UI for embedded contexts
  signedIn?: boolean;        // Auth status
  onSignIn?: () => void;     // Trigger sign-in flow
}
```

**Workflow**

1. File Upload: Drag/drop or click to select audio files
2. Storage: Files stored in Supabase Storage with metadata
3. Playback: In-browser audio player with waveform visualization
4. Transcription: Select library files to process to MIDI
5. Deletion: Remove files with confirmation

---

### 7. Visualizer.tsx — Audio Waveform Display

**Location**: `components/Visualizer.tsx`

Visual waveform display for audio playback with real-time updating.

**Props**

```tsx
{
  audioRef: React.RefObject<HTMLAudioElement>;  // Audio element reference
}
```

---

### 8. AuthProvider.tsx — Authentication

**Location**: `components/AuthProvider.tsx`

Supabase authentication using implicit OAuth flow (Google).

**Features**

- Implicit OAuth flow via Supabase (`flowType: "implicit"`)
- Session management with automatic renewal
- `AuthProvider` wraps app for auth state; `useAuth()` hook for access

---

### 9. MusicChat.tsx — AI Chat

**Location**: `components/MusicChat.tsx`

AI-powered chat interface with music tools (transcribe, analyze, enhance, convert). Uses Vercel AI SDK + OpenRouter.

**Props**

```tsx
{
  onTranscribed?: (result: TranscribeResult, name: string) => void;
  onAnalyzed?: (midiBase64?: string, name?: string) => void;
}
```
