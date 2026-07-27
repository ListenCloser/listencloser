# Known Issues & Technical Debt

## Critical — Product Not Working Correctly

### ISSUE-001: Chat tool results not wired to Studio state
**Component:** `components/MusicChat.tsx`
**Problem:** When chat transcribes audio, the `onTranscribed` callback fires but the notes are empty because the chat tool returns notes in a different format than expected. The Transform tab shows "0 notes" even after successful transcription via chat.
**Impact:** Chat transcription flow is broken — user gets no visual feedback.
**Fix:** Ensure tool result `notes` array is properly passed through to `onTranscribed`.

### ISSUE-002: Analysis state not updating across tabs
**Component:** `components/Studio.tsx`, `components/library/index.tsx`
**Problem:** After analyzing a track in the Analyze tab, the Library tab still shows "Analyze" button instead of "View Analysis". The `deriveTrackState()` function checks the library file's data, but the library files aren't refreshed after analysis completes.
**Impact:** User sees inconsistent UI — button says "Analyze" when analysis already exists.
**Fix:** Refresh library files after analysis completes (partially done in useStudioState but not propagated to Library component).

### ISSUE-003: Sheet music not persisted as proper state
**Component:** `components/viz/index.tsx`, `lib/library.ts`
**Problem:** Sheet music (MusicXML) is converted on-demand but not reliably persisted to the library JSON. When the user navigates away and back, the sheet music is re-converted. The `musicxml` field exists on LibFile but isn't always populated after conversion.
**Impact:** Sheet music disappears on tab switch. User must re-convert every time.
**Fix:** After MusicXML conversion in viz component, call `saveTranscription` to persist. Also ensure `listLibrary` reads the `musicxml` field correctly.

### ISSUE-004: MIDI playback not using cached WAV
**Component:** `components/viz/index.tsx`
**Problem:** The viz component checks for `midiWavUrl` (local state) but not `selected.synth_wav_base64` (persisted in library). Each time the user clicks play, it re-synthesizes instead of using the cached WAV.
**Impact:** Slow playback — user waits for synthesis every time.
**Fix:** Check `selected.synth_wav_base64` before calling `synthAudio()`.

### ISSUE-005: Transcription produces noisy MIDI
**Component:** `backend/music_features.py`
**Problem:** basic-pitch returns every detected pitch event including noise (short spurious notes, wrong velocities). No post-processing to filter or clean the output.
**Impact:** Sheet music is confusing — 32nd notes, random velocities, non-standard notation.
**Fix:** Add post-processing step: remove notes shorter than 50ms, normalize velocities, quantize to grid.

### ISSUE-006: Sheet music has no quantization
**Component:** `backend/music_features.py`, `components/SheetMusic.tsx`
**Problem:** Raw MIDI events are converted to MusicXML without quantization. Result has tuplets, 32nd notes, and non-standard notation that's hard to read.
**Impact:** Sheet music is visually confusing and not useful for musicians.
**Fix:** Apply music21's `quantize()` method before MusicXML export. Use configurable quantization depth (16th vs 8th note grid).

---

## High — Analysis Quality

### ISSUE-007: Analysis timestamps inaccurate
**Component:** `backend/analyze.py`
**Problem:** Modulation timestamps show 0:00-0:01 for a 1-minute song. The modulation detection uses quarter-note positions from music21 but the conversion to seconds is wrong when tempo varies.
**Impact:** Analysis says "key changes at 0:00" which is meaningless.
**Fix:** Use actual time positions from pretty_midi instead of music21 quarter-note offsets.

### ISSUE-008: Analysis shows 0 notes / 0 density when analyzing from library
**Component:** `components/Studio.tsx`
**Problem:** When analyzing from the Library tab, `lastResult` is not set, so the Analysis component receives empty notes. The note count and density show as 0.
**Impact:** Analysis appears broken — key/tempo work but note stats are wrong.
**Fix:** Set `lastResult` when `handleAnalyzeLibrary` is called with a track that has notes.

### ISSUE-009: No structural analysis (verse/chorus/bridge)
**Component:** `backend/analyze.py`
**Problem:** Analysis only shows key, tempo, chords, cadences, modulations. No structural breakdown of the piece.
**Impact:** Analysis is shallow — user can't understand the form of the music.
**Fix:** Add MSAF (Music Structure Analysis Framework) or music21's structure detection.

### ISSUE-010: No rhythm analysis
**Component:** `backend/analyze.py`
**Problem:** No beat tracking, groove analysis, or rhythmic pattern detection.
**Impact:** Analysis misses a core dimension of music.
**Fix:** Add madmom for beat/downbeat tracking, or use pretty_midi's beat detection.

---

## Medium — Chat Functionality

### ISSUE-011: Chat history not persisted correctly across tab switches
**Component:** `components/MusicChat.tsx`
**Problem:** `setMessages()` from `useChat` hook may not correctly restore messages from sessionStorage. The persisted messages are loaded but `setMessages` might not accept them in the right format.
**Impact:** Chat history is lost when switching tabs.
**Fix:** Test `setMessages` with actual persisted data format. May need to use `useChat`'s `id` parameter for persistence.

### ISSUE-012: Chat tool results not rendering embedded widgets
**Component:** `components/MusicChat.tsx`
**Problem:** Tool results (transcribe, analyze) should render as embedded PianoRoll, audio player, etc. The rendering code exists but may not be triggered correctly due to SSE format mismatch.
**Impact:** Chat shows plain text instead of interactive widgets.
**Fix:** Verify SSE event format matches `uiMessageChunkSchema` exactly. Test with tool calls.

### ISSUE-013: Chat can't access library without sign-in
**Component:** `lib/tools/index.ts`
**Problem:** `list_library` tool returns "library empty" when not signed in because it can't access Supabase without auth headers.
**Impact:** Unauthenticated users get no useful response from chat.
**Fix:** This is expected behavior — chat needs auth to access library. Document clearly in the tool description.

---

## Medium — UI Consistency

### ISSUE-014: Button hierarchy inconsistent
**Component:** `components/library/index.tsx`, `components/transcribe/index.tsx`
**Problem:** Primary vs ghost button styling is inconsistent. "Analyze" shows as primary when it should be ghost (analysis exists), and vice versa.
**Impact:** Confusing UI — user can't tell what action will happen.
**Fix:** Use `deriveTrackState()` consistently to determine button style.

### ISSUE-015: Analyze tab "analyze another track" vs dropdown
**Component:** `components/Studio.tsx`
**Problem:** Analyze tab has both a dropdown for track selection AND a separate "Analyze another track" button. This is inconsistent with the Visualize tab which only uses a dropdown.
**Impact:** Inconsistent UX — two ways to do the same thing.
**Fix:** Remove the "Analyze another track" button, use dropdown only (like Visualize tab).

### ISSUE-016: Visualize tab loading flash
**Component:** `components/viz/index.tsx`
**Problem:** Before library files load, the viz tab briefly shows "No transcribed tracks" before switching to the actual content.
**Impact:** Jarring flash of empty state.
**Fix:** Add loading skeleton (partially done in previous PRs but may not be in main).

---

## Low — Code Quality

### ISSUE-017: transcribe/index.tsx is 780 lines
**Component:** `components/transcribe/index.tsx`
**Problem:** Single component handles upload, recording, transcription, MIDI-to-score, library selection, playback, and result display. Violates single responsibility.
**Impact:** Hard to maintain, test, and modify.
**Fix:** Split into: SourcePicker, ProcessingPipeline, ResultDisplay, LibraryPicker sub-components.

### ISSUE-018: Studio.tsx has 20+ state variables
**Component:** `components/Studio.tsx`
**Problem:** God component with all cross-tab state. 15+ useState hooks.
**Impact:** Hard to understand state flow, hard to test.
**Fix:** Extract state into custom hook or useReducer. Consider feature-based state management.

### ISSUE-019: Magic numbers in visualization components
**Component:** `components/PianoRoll.tsx`, `components/Visualizer.tsx`, `components/Spectrogram.tsx`
**Problem:** Hardcoded values like `PPQ=16`, `rowH=22`, `fftSize=2048`, `height=60`, `bars=64`.
**Impact:** Changes require hunting through component code.
**Fix:** Extract to named constants at top of file with descriptive names.

### ISSUE-020: lib/music.ts does too many things
**Component:** `lib/music.ts`
**Problem:** Types + API calls + MIDI encoding + format utils + library CRUD all in one file.
**Impact:** Hard to find things, hard to test in isolation.
**Fix:** Already split into midi.ts, format.ts, types.ts, music-api.ts, library.ts. Verify barrel exports are clean.

---

## Low — Testing Gaps

### ISSUE-021: No unit tests for chat tools
**Component:** `lib/tools/index.ts`
**Problem:** Chat tools (list_library, transcribe_audio, etc.) have no unit tests.
**Impact:** Tool behavior unverified, regressions possible.
**Fix:** Add mock-based tests for each tool.

### ISSUE-022: E2E tests don't test signed-in chat flow
**Component:** `tests/e2e/full-flow.spec.ts`
**Problem:** Chat tests only verify unauthenticated flow. No test for signed-in user uploading audio, transcribing via chat, seeing tool results.
**Impact:** Critical user flow untested.
**Fix:** Add E2E test with mocked auth that tests full chat workflow.

### ISSUE-023: No integration tests for analysis pipeline
**Component:** `backend/tests/`
**Problem:** Backend tests cover health/contract/security but not analysis quality.
**Impact:** Analysis regressions undetected.
**Fix`: Add test with sample MIDI file that verifies key, tempo, chord detection.

---

## Low — Documentation

### ISSUE-024: CHANGELOG.md has stale entries
**Component:** `docs/CHANGELOG.md`
**Problem:** References removed features (MusicGen, Chat, Piano) and removed files.
**Impact:** Misleads developers about current state.
**Fix:** Remove stale entries or mark as historical.

### ISSUE-025: README.md references incorrect auth flow
**Component:** `README.md`
**Problem:** Says "implicit OAuth flow" but code uses PKCE flow.
**Impact:** Misleads developers about auth implementation.
**Fix:** Update to "PKCE OAuth flow".

---

## Tracking

| ID | Severity | Status | Assignee |
|----|----------|--------|----------|
| ISSUE-001 | Critical | Open | — |
| ISSUE-002 | Critical | Open | — |
| ISSUE-003 | Critical | Open | — |
| ISSUE-004 | Critical | Open | — |
| ISSUE-005 | Critical | Open | — |
| ISSUE-006 | Critical | Open | — |
| ISSUE-007 | High | Open | — |
| ISSUE-008 | High | Open | — |
| ISSUE-009 | High | Open | — |
| ISSUE-010 | High | Open | — |
| ISSUE-011 | Medium | Open | — |
| ISSUE-012 | Medium | Open | — |
| ISSUE-013 | Medium | Open | — |
| ISSUE-014 | Medium | Open | — |
| ISSUE-015 | Medium | Open | — |
| ISSUE-016 | Medium | Open | — |
| ISSUE-017 | Low | Open | — |
| ISSUE-018 | Low | Open | — |
| ISSUE-019 | Low | Open | — |
| ISSUE-020 | Low | Open | — |
| ISSUE-021 | Low | Open | — |
| ISSUE-022 | Low | Open | — |
| ISSUE-023 | Low | Open | — |
| ISSUE-024 | Low | Open | — |
| ISSUE-025 | Low | Open | — |
