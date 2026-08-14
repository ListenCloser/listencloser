# Capability Matrix — Current Analysis Implementation

> **Classification Legend:**
> - **OSS_DIRECT**: Direct call to OSS library, minimal wrapper
> - **OSS_WRAPPED**: OSS library used but with significant custom logic/adaptation
> - **CUSTOM_HEURISTIC**: Primarily custom rule-based logic (may use OSS as helper)
> - **MISSING**: No implementation exists
> - **UNIMPLEMENTED**: Explicitly returns empty/None with documentation

---

## Signal-Level Capabilities (Audio → Evidence)

| Capability | Classification | OSS Dependency | Bespoke Code | Input | Output | Temporal Resolution | Confidence Semantics | Known Weaknesses | Test Coverage | Production Usage |
|------------|----------------|----------------|--------------|-------|--------|---------------------|----------------------|------------------|---------------|------------------|
| **Beat tracking** | OSS_WRAPPED | librosa (default), beat_this (optional) | `music_features.estimate_beat_grid()` wraps librosa; registry seam | Audio (WAV bytes) | `bpm: float, beats: list[float], downbeats: list[float]\|None` | Per-beat (seconds) | None returned by engine; caller may add | librosa: no downbeats; beat_this: optional, not installed by default | `test_beat_this.py`, `test_adapters.py` | Used in `handle_score` for notation alignment; NOT in `handle_analyze` |
| **Downbeat detection** | MISSING (librosa) / OSS_DIRECT (beat_this, allin1) | beat_this, allin1 | Registry seam exists but beat_this not default | Audio | `downbeats: list[float]` | Per-downbeat (seconds) | None | Only available if beat_this/allin1 enabled via env | None | Not in default pipeline |
| **Tempo (audio)** | OSS_WRAPPED | librosa, essentia (optional) | `_extract_audio_descriptors()` tries essentia → librosa fallback | Audio | `bpm: float` | Global | Essentia: internal confidence; librosa: none | librosa tempo often 2×/0.5× actual; essentia not installed on ARM worker | Implicit in transcription tests | Used in `handle_audio_structure` (allin1); NOT in `handle_analyze` |
| **Key (audio)** | OSS_WRAPPED | essentia (preferred), librosa (fallback) | Custom Krumhansl-Schmuckler in librosa path | Audio | `tonic, mode, confidence` | Global | Essentia: key_strength; librosa: normalized correlation | Librosa KS implementation unvalidated; essentia unavailable on worker | None | Used in `handle_audio_structure` (allin1); NOT in `handle_analyze` |
| **Meter/Time Signature (audio)** | MISSING | — | — | Audio | — | — | — | No audio meter detection exists | — | — |
| **Structure/Segmentation (audio)** | OSS_DIRECT (allin1) | allin1 (optional, disabled by default) | `AllInOneEngine` wrapper | Audio | `segments: [{start,end,label}], beats, downbeats, bpm` | Per-segment (seconds) | None from engine | Disabled by default (`ALLIN1_ENABLED=false`); heavyweight (PyTorch/NATTEN) | None | `handle_audio_structure` returns early if None |
| **Instrumentation/Timbre** | MISSING | — | — | Audio | — | — | — | No instrument classification | — | — |
| **Dynamics (audio)** | OSS_WRAPPED | essentia (LoudnessEBUR128), librosa (RMS) | `_extract_audio_descriptors()` | Audio | `loudness_lufs: float` | Global | None | Only loudness, not dynamic shape | — | `handle_audio_structure` evidence only |
| **Onset Density** | OSS_DIRECT | librosa (via rhythm analysis) | Computed in `_midi_rhythm` from MIDI note count | MIDI | `rhythmic_density: notes/sec` | Global | None | From transcribed MIDI, not audio | — | `rhythm` insight |

---

## Symbolic-Level Capabilities (MIDI/Notes → Evidence)

| Capability | Classification | OSS Dependency | Bespoke Code | Input | Output | Temporal Resolution | Confidence Semantics | Known Weaknesses | Test Coverage | Production Usage |
|------------|----------------|----------------|--------------|-------|--------|---------------------|----------------------|------------------|---------------|------------------|
| **Key (symbolic)** | OSS_DIRECT | music21 `score.analyze("key")` | `_m21_key()` filters None correlation/tonic | MIDI (parsed score) | `tonic, mode, confidence=correlation` | Global | music21 correlation coefficient (0-1) | Correlation ≠ probability; fails on atonal/polytonal | `test_analysis_truthfulness.py` | `handle_analyze` → `key` insight |
| **Chords (symbolic)** | OSS_DIRECT | music21 `Chord` class | `_m21_chords()` maps quality strings, filters unknown | MIDI (parsed score) | `list[{root, quality, start_qn, end_qn}]` | Per-chord (quarter notes) | None | Only finds explicit Chord objects; no chord segmentation | `test_analysis_truthfulness.py` (filters unknown) | `handle_analyze` → `chord` insights |
| **Roman Numerals** | OSS_DIRECT | music21 `roman.romanNumeralFromChord` | `_m21_roman_numerals()` same quality mapping, 500 cap | MIDI + detected key | `list[{figure, root, quality, start_qn, end_qn}]` | Per-chord (quarter notes) | None | Requires valid key; 500-result cap; same chord detection limits | None | `handle_analyze` → `roman_numeral` insights |
| **Harmonic Function** | MISSING | — | RN provides implicit function but no explicit labeling | — | — | — | — | RN figures not parsed for function (T/S/D) | — | — |
| **Cadence Detection** | CUSTOM_HEURISTIC | music21 (for RN) | `_m21_cadences()`: adjacent RN pattern matching (V-I, IV-I, I-V, V-vi, etc.) | MIDI + detected key | `list[{type, chords, position_qn, evidence_score, evidence}]` | Per-cadence (quarter notes) | `evidence_score` 0.5-0.8 (heuristic, not calibrated) | Pattern-only; no metric/harmonic context beyond RN; false positives on non-cadential V-I | None | `handle_analyze` → `cadence_candidate` insights |
| **Modulation Detection** | CUSTOM_HEURISTIC | music21 (for notes), numpy (KS) | `_detect_modulations()`: windowed KS + run-length encoding | MIDI + tempo | `list[{from_key, to_key, position_sec, kind, run_length, duration, window_size}]` | Per-window (seconds) | None; `kind` = "possible_tonicization" (2 windows) or "possible_modulation" (≥3) | Window size = total/8; tempo from MIDI (often wrong); KS on transcribed notes = noisy; false modulations at 0.37s, 0.74s in real piano test | None | `handle_analyze` → `modulation` insights |
| **Melody Extraction** | CUSTOM_HEURISTIC | pretty_midi (note access) | `_midi_melody()`: greedy continuity skyline (30ms windows, duration/leap/height scoring) | MIDI (performance) | `{low/high_pitch, range, unique_pcs, stepwise/leap_ratio, quality_score, heuristic}` | Global (single summary) | `quality_score` = mean margin (best-2nd)/capped [0,1] — NOT calibrated | Heuristic, not ML; fails on polyphonic/accompanied melody; returns None on real piano test | None | `handle_analyze` → `melody` insight (often None) |
| **Melodic Contour** | MISSING | — | Only global stats (range, stepwise%) | — | — | — | — | No contour shape representation | — | — |
| **Phrase Boundaries** | UNIMPLEMENTED | — | `_m21_phrases()` explicitly returns `[]` | — | `[]` | — | — | Deliberately unimplemented (docstring: "misleading") | None | `phrases` always empty |
| **Rhythm (symbolic)** | CUSTOM_HEURISTIC | pretty_midi | `_midi_rhythm()`: note density, avg duration from MIDI | MIDI (performance) | `{beat_count, avg_note_duration, rhythmic_density, syncopation_ratio=None, syncopation_available=False}` | Global | None | No metrical grid → no syncopation; beat_count from MIDI tempo (often default) | None | `handle_analyze` → `rhythm` insight |
| **Rhythmic Density** | CUSTOM_HEURISTIC | pretty_midi | Part of `_midi_rhythm` | MIDI | `notes/sec` | Global | None | From transcribed MIDI (noise-sensitive) | — | `rhythm` insight evidence |
| **Groove/Feel** | MISSING | — | — | — | — | — | — | No microtiming analysis | — | — |
| **Dynamics (symbolic)** | MISSING | — | Velocity available in note entities but not analyzed | — | — | — | — | Note velocity stored but no dynamics analysis | — | — |
| **Texture** | MISSING | — | Voice leading requires ≥2 parts (rare in transcription) | — | — | — | — | Transcription typically single part | — | `voice_leading` always None |
| **Instrumentation (symbolic)** | MISSING | — | MIDI program numbers available but not analyzed | — | — | — | — | No instrument classification from MIDI | — | — |
| **Polyphony** | MISSING | — | Note overlap detectable but not summarized | — | — | — | — | Could be derived from note entities | — | — |
| **Register** | PARTIAL | pretty_midi | Melody engine returns `low_pitch`/`high_pitch` | MIDI | Global pitch range | Global | None | Only for extracted melody line | — | `melody` insight |

---

## Relational/Higher-Level Capabilities (Reasoning over Evidence)

| Capability | Classification | Current Approach | Input Evidence | Output | Status |
|------------|----------------|------------------|----------------|--------|--------|
| **Harmonic Function (T/S/D)** | MISSING | RN figures not parsed for function | Roman numerals | — | Not implemented |
| **Cadence Confirmation** | CUSTOM_HEURISTIC | Pattern + metric position + duration heuristic | RN sequence, measure boundaries | `cadence_candidate` with `evidence_score` | Implemented but weak |
| **Modulation Confirmation** | CUSTOM_HEURISTIC | Run-length gating (2=tonicization, 3+=modulation) | Windowed KS key history | `modulation` with `kind` | Implemented but high false positive |
| **Phrase Detection** | UNIMPLEMENTED | Explicitly returns empty | — | `[]` | Deliberately omitted |
| **Motif/Repetition** | MISSING | — | Note sequences | — | Not implemented |
| **Section Relationship** | MISSING | Audio structure gives segments but no symbolic relation | Audio segments | — | Audio-only, not symbolic |
| **Tension/Release** | MISSING | — | Harmony + rhythm | — | Not implemented |
| **Voice Leading Analysis** | OSS_DIRECT (when applicable) | music21 `voiceLeading` but requires ≥2 independent parts | Multi-part score | Motion ratios + summary | Almost never triggered (transcription = 1 part) |

---

## Summary Classification Counts

| Classification | Count | Capabilities |
|----------------|-------|--------------|
| **OSS_DIRECT** | 4 | Key (symbolic), Chords, Roman Numerals, Voice Leading (conditional) |
| **OSS_WRAPPED** | 5 | Beat tracking, Tempo (audio), Key (audio), Structure (audio), Dynamics (audio) |
| **CUSTOM_HEURISTIC** | 7 | Cadences, Modulations, Melody, Rhythm (symbolic), Rhythmic Density, (Groove), (Texture) |
| **MISSING** | 14 | Meter (audio), Instrumentation (audio), Harmonic Function, Melodic Contour, Groove, Dynamics (symbolic), Texture, Instrumentation (symbolic), Polyphony, Register (full), Motif, Section Relationship, Tension, Voice Leading (robust) |
| **UNIMPLEMENTED** | 1 | Phrases |

---

## Confidence Semantics Audit

| Insight Kind | Confidence Source | Is Calibrated? | Meaning |
|--------------|-------------------|----------------|---------|
| `key` | music21 correlationCoefficient | **No** | Correlation with KS profile, not P(key\|data) |
| `tempo` | Hardcoded 0.9 | **No** | MIDI metadata confidence (often transcription default) |
| `time_signature` | Hardcoded 0.9 | **No** | MIDI metadata confidence (often transcription default) |
| `chord` | `None` | **N/A** | No confidence provided |
| `roman_numeral` | `None` | **N/A** | No confidence provided |
| `cadence_candidate` | `evidence_score` 0.5-0.8 | **No** | Heuristic weight, not probability |
| `modulation` | `None` (kind indicates strength) | **No** | Run-length windows as proxy |
| `rhythm` | `None` | **N/A** | No confidence |
| `melody` | `quality_score` (margin) | **No** | Candidate separation margin |
| `voice_motion_candidate` | `None` | **N/A** | No confidence |

**Critical Finding**: Only `key` has a numerical confidence from an OSS library, and it's a correlation coefficient, not a calibrated probability. All other confidences are either hardcoded, heuristic scores, or `None`.