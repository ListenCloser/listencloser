# End-to-End User Flows — Complete Reference

This document maps every user-facing operation in the Music AI Studio,
the expected behavior, and how to verify it.

---

## Flow 1: Library — Upload & Manage

### 1.1 Upload Audio
**Steps:** Library tab → Click drop zone or "Upload file" → Select audio file
**Expected:**
- Loading skeleton appears briefly
- Track appears in list with "✓ Audio" badge
- Status shows "Saved ✓ filename.wav"
- Track card shows "Transcribe" as primary button

**Edge cases:**
- Empty file → error message
- Non-audio file → backend rejects, error shown
- Duplicate filename → timestamp prefix prevents collision

### 1.2 Record Audio
**Steps:** Library tab → Click "● Record" → Speak/play → Click "■ Stop"
**Expected:**
- Recording indicator (red dot + timer) appears
- On stop: file uploads automatically
- Track appears in list
- Status shows recording duration

### 1.3 Play Audio
**Steps:** Library tab → Click "▶" on a track
**Expected:**
- Audio player appears with play/pause
- Progress bar shows position
- Visualizer waveform displays
- Click progress bar to seek

### 1.4 Delete Track
**Steps:** Library tab → Click "✕" on a track
**Expected:**
- Track removed from list
- Status shows "Deleted filename"
- If track was selected in Visualize/Analyze, selection clears
- Associated transcription JSON also deleted

### 1.5 Drag & Drop Upload
**Steps:** Library tab → Drag audio file onto drop zone
**Expected:**
- Drop zone highlights on drag-over
- File uploads on drop
- Same as 1.1 behavior

---

## Flow 2: Transform — Transcription Pipeline

### 2.1 Transcribe Uploaded Audio
**Steps:** Transform tab → Click "Upload file" → Select audio
**Expected:**
1. "Cleaning audio…" (enhancement step)
2. "Transcribing…" (basic-pitch ML)
3. "Synthesizing audio…" (FluidSynth)
4. Results appear: piano roll, note count, playback controls
5. Auto-saves to library if signed in
6. Track card in Library updates with "✓ Transcribed" badge

### 2.2 Transcribe Recorded Audio
**Steps:** Transform tab → Click "● Record" → Record → Click "■ Stop"
**Expected:**
- Same as 2.1 but from microphone input
- Recording indicator shown during capture

### 2.3 Transcribe from Library
**Steps:** Transform tab → Click "From library" → Select track
**Expected:**
- If track has notes: loads instantly (no re-transcription)
- If track has no notes: transcribes from library storage
- Results appear with piano roll

### 2.4 MIDI → Sheet Music
**Steps:** Transform tab → Switch to "MIDI → Sheet Music" mode → Upload MIDI or select from library
**Expected:**
1. "Converting to sheet music…" (music21 conversion)
2. Sheet music renders via OpenSheetMusicDisplay
3. "Export MusicXML" button appears
4. MusicXML saved to library

### 2.5 Download MIDI
**Steps:** Transform tab → After transcription → Click "Download MIDI"
**Expected:**
- .mid file downloads with correct filename

### 2.6 Playback Synthesized Audio
**Steps:** Transform tab → After transcription → Click "▶" on playback section
**Expected:**
- Synthesized WAV plays
- Progress bar shows position
- Visualizer waveform displays
- Can pause/resume

### 2.7 Clear Results
**Steps:** Transform tab → After transcription → Click "✕ Clear"
**Expected:**
- Returns to source picker (upload/record/library)
- All results cleared

---

## Flow 3: Visualize — Multiple Views

### 3.1 Piano Roll
**Steps:** Visualize tab → Select track → "Piano roll" mode
**Expected:**
- SVG piano roll with colored notes
- Velocity-based opacity (louder = brighter)
- Playhead follows playback
- Auto-scrolls to keep playhead visible
- Note labels on left axis
- Beat grid with measure markers

### 3.2 Spectrogram
**Steps:** Visualize tab → Select track → "Spectrogram" mode
**Expected:**
- WaveSurfer.js spectrogram display
- Frequency analysis of audio
- Waveform overlay

### 3.3 Chroma Heatmap
**Steps:** Visualize tab → Select track → "Chroma" mode
**Expected:**
- Bar chart of pitch class distribution
- 12 bars (C through B)
- Normalized to total duration

### 3.4 Tonnetz
**Steps:** Visualize tab → Select track → "Tonnetz" mode
**Expected:**
- Hexagonal grid showing harmonic relationships
- Notes placed by pitch class
- Edges show intervals (fifths, thirds)

### 3.5 Sheet Music View
**Steps:** Visualize tab → Select track → "Sheet Music" mode
**Expected:**
- MusicXML renders via OpenSheetMusicDisplay
- White background for readability
- Auto-converts MIDI to MusicXML if not cached

### 3.6 Playback Source Selection
**Steps:** Visualize tab → Select "Original", "MIDI", or "Sheet Music"
**Expected:**
- "Viewing: Original Audio / MIDI / Sheet Music" label shown
- Active source highlighted, others ghost style
- Playback switches to selected source
- MIDI/Sheet Music sources synthesize on demand (cached after first play)

### 3.7 Track Selection Persistence
**Steps:** Select track in Visualize → Switch to Transform → Switch back
**Expected:**
- Same track still selected
- Same visualization mode preserved
- Page refresh preserves selection

---

## Flow 4: Analyze — Music Theory

### 4.1 Analyze from Library
**Steps:** Library tab → Click "Analyze" on a transcribed track
**Expected:**
- Navigates to Analyze tab
- Analysis runs (key, tempo, chords, etc.)
- Results appear with:
  - Summary insights (human-readable)
  - Key/Tempo/Time signature cards with confidence bars
  - Visual chord timeline
  - Roman numeral analysis with cadence highlights
  - Cadence descriptions
  - Key change markers
  - Voice leading stats
  - Diatonic chords
  - Note statistics

### 4.2 Analyze from Transform
**Steps:** Transform tab → After transcription → Click "Analyze"
**Expected:**
- Navigates to Analyze tab
- Same analysis results as 4.1

### 4.3 Re-Analyze
**Steps:** Analyze tab → Click "← Analyze another track"
**Expected:**
- Returns to track picker
- Can select a different track

### 4.4 Analysis Results Detail
**After analysis completes, verify:**
- **Summary**: Plain language insights ("Likely in G Major", "3 key changes detected")
- **Key card**: Tonic + mode + confidence bar
- **Tempo card**: BPM + confidence bar
- **Time card**: Time signature + confidence bar
- **Chord timeline**: Horizontal bar with colored segments (major=accent, minor=accent-2)
- **Modulation markers**: Red vertical lines at key change positions
- **Roman numerals**: Chips with cadence color highlights
- **Cadences**: Colored dots with descriptions ("authentic", "plagal", etc.)
- **Key changes**: List with timestamps
- **Voice leading**: 4 motion types with percentages
- **Diatonic chords**: Colored chips (major/minor/dim)
- **Note stats**: Pitch range, count, density

---

## Flow 5: Chat — AI Assistant

### 5.1 Ask a Question
**Steps:** Chat tab → Type question → Click "Send"
**Expected:**
- User message appears (right-aligned, accent color)
- "Thinking…" indicator while waiting
- Assistant response streams in (left-aligned, panel color)
- Auto-scrolls to bottom

### 5.2 Transcribe via Chat
**Steps:** Chat tab → Attach audio file → Type "Transcribe this audio" → Send
**Expected:**
- Tool call card shows "🎵 Transcribing audio…"
- Result card appears with:
  - "✓ Transcribed N notes"
  - Embedded PianoRoll visualization
  - "▶ Play MIDI" button (synthesizes on demand)
  - "Open in Transform" navigation button
  - "Visualize" navigation button
- If signed in, results also saved to library

### 5.3 Analyze via Chat
**Steps:** Chat tab → Ask "What key is this in?"
**Expected:**
- Tool call card shows "🎼 Analyzing music theory…"
- Result card appears with:
  - Key, Tempo, Time signature, Note count
  - "View Full Analysis" navigation button

### 5.4 Enhance via Chat
**Steps:** Chat tab → Attach audio → "Clean up this recording"
**Expected:**
- Tool call card shows "🔊 Enhancing audio…"
- Result: "✓ Audio enhanced — noise removed, volume normalized"

### 5.5 Convert via Chat
**Steps:** Chat tab → "Convert this MIDI to sheet music"
**Expected:**
- Tool call card shows "🔄 Converting format…"
- Result: "✓ musicxml"

### 5.6 Navigation from Chat
**Steps:** Chat tab → Click "Open in Transform" or "Visualize"
**Expected:**
- Navigates to the specified tab
- Track pre-selected if available

---

## Flow 6: Navigation & State

### 6.1 Tab Switching
**Steps:** Click between Library, Transform, Visualize, Analyze, Chat
**Expected:**
- URL updates: `/?tab=library`, `/?tab=transcribe`, etc.
- Selected track persists across switches
- Analysis results persist
- No data re-fetching on switch (except Analyze tab)

### 6.2 Deep Linking
**Steps:** Navigate to `/?tab=viz&track=library/uid/file.wav`
**Expected:**
- Opens Visualize tab with that track pre-selected
- Visualization loads immediately

### 6.3 Page Refresh
**Steps:** Refresh while on Visualize tab with track selected
**Expected:**
- Tab preserved (from sessionStorage)
- Track selection preserved
- Visualization mode preserved
- Analysis results preserved

### 6.4 Sign In/Out
**Steps:** Click "Sign in" → Google OAuth → Complete
**Expected:**
- Redirects through /auth/callback → /auth/confirm
- Session established
- Library loads with user's tracks
- "Sign out" button appears

**Steps:** Click "Sign out"
**Expected:**
- Token cache cleared
- Session ended
- Page reloads
- Library shows empty state

---

## Flow 7: Error Handling

### 7.1 Network Error During Transcription
**Steps:** Disconnect network → Try to transcribe
**Expected:**
- Error message shown: "⚠️ transcription failed"
- "Try again" button available
- No partial state saved

### 7.2 Invalid Audio File
**Steps:** Upload a .txt file renamed to .wav
**Expected:**
- Backend rejects with error
- Error message shown
- User can try again

### 7.3 Storage Quota Exceeded
**Steps:** Upload many large files until quota hit
**Expected:**
- Error message from Supabase
- User notified of storage issue

### 7.4 Auth Token Expired
**Steps:** Wait for token expiry (1 hour) → Try to upload
**Expected:**
- 401 response
- Token cache invalidated
- Next request fetches fresh token
- User may need to re-sign-in

---

## Flow 8: Loading States

### 8.1 Library Loading
**Steps:** Navigate to Library tab
**Expected:**
- 3 skeleton track cards shown while loading
- No "No tracks" message during load
- Skeletons replaced by actual tracks

### 8.2 Transcription Progress
**Steps:** Start transcription
**Expected:**
- Step indicator shows: Clean → Transcribe → Synthesize
- Active step pulses with accent color
- Completed steps show checkmark
- Status text updates at each step

### 8.3 Analysis Loading
**Steps:** Start analysis
**Expected:**
- "Analyzing…" status with pulse animation
- Progress bar at 50%
- Results replace loading state

### 8.4 Chat Loading
**Steps:** Send message in chat
**Expected:**
- "Thinking…" indicator
- Response streams in character by character
- Tool calls show spinner with label

---

## Verification Checklist

For each flow, verify:
- [ ] No console errors
- [ ] No network errors (check DevTools)
- [ ] Loading states shown during async operations
- [ ] Error states shown on failure
- [ ] State persists across tab switches
- [ ] State persists across page refresh
- [ ] Responsive on mobile viewport
- [ ] Keyboard accessible (tab navigation, enter to submit)
- [ ] Screen reader announces status changes
