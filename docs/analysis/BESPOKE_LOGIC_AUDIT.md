# Bespoke Logic Audit — Custom Heuristics in Analysis Pipeline

> **Scope**: Every substantial analysis heuristic owned by this repository. For each: why it exists, what it compensates for, whether OSS solves it, genre specificity, evaluation backing, and deletability.

---

## 1. Cadence Detection — `_m21_cadences()`

**Location**: `backend/engines/harmony/music21_engine.py:157-224`
**Classification**: CUSTOM_HEURISTIC
**Provenance**: `engine="custom-rule", method="roman_numeral_pattern"`

### What it does
Scans adjacent Roman numeral pairs for hardcoded patterns:
```python
patterns = [
    ("authentic", ["V", "I"]), ("plagal", ["IV", "I"]),
    ("half", ["I", "V"]), ("deceptive", ["V", "vi"]),
    ("authentic", ["V7", "I"]), ("authentic", ["V", "i"]),
    ("half", ["i", "V"]), ("deceptive", ["V", "VI"]),
]
```
Adds heuristic `evidence_score`:
- Base: 0.5
- +0.2 if arrival near measure boundary (≤0.5 qn from measure start)
- +0.1 if arrival duration ≥1.0 qn
- Capped at 0.8

### Why it exists
Music21 provides Roman numerals but no cadence detection. The product needs "cadence" insights for the Analysis UI.

### What it compensates for
- No OSS cadence detector in music21
- No audio-informed cadence detection (would need beat/downbeat + harmonic analysis)

### Is there OSS that solves this?
- **music21**: No built-in cadence detection
- **chordia**: Chord recognition only
- **madmom**: No cadence module
- **Essentia**: No cadence module
- **Research**: Cadence detection typically requires supervised ML on annotated corpora (e.g., Bach chorales). No mature OSS Python package exists.

### Genre/instrument specific?
Assumes functional tonal harmony (V-I, IV-I patterns). Fails for:
- Modal music (no V-I)
- Jazz (extended harmonies, different cadence types)
- Pop/rock (plagal cadences common, but also non-functional)
- Electronic/percussive (no harmonic cadences)

### Backed by evaluation?
**No.** No test coverage. No precision/recall on annotated cadence corpus.

### Can it be deleted?
**Yes, but** would leave `cadence_candidate` insights empty. Better: replace with evaluated OSS or keep as explicit gap-filler with stronger documentation.

### Recommendation
**KEEP_TEMPORARILY_AS_EXPLICIT_GAP_FILLER** with:
- Clear "candidate" labeling (already done)
- Documented false positive rate
- Evaluation against Bach chorale corpus when resources allow

---

## 2. Modulation Detection — `_detect_modulations()`

**Location**: `backend/engines/harmony/music21_engine.py:304-377`
**Classification**: CUSTOM_HEURISTIC
**Provenance**: `engine="custom-rule", method="windowed_krumhansl-schmuckler"`

### What it does
1. Extracts all notes from score → pitch-class distributions in overlapping windows
2. Window size = total_duration / 8, step = window/2
3. Per window: KS key estimation (custom numpy implementation)
4. Run-length encodes key history
5. Emits transitions where new key runs ≥2 windows:
   - 2 windows → "possible_tonicization"
   - ≥3 windows → "possible_modulation"

### Why it exists
Music21 has no modulation detection. Product needs "modulation" insights.

### What it compensates for
- No OSS modulation detector
- No audio-informed key tracking

### Is there OSS that solves this?
- **music21**: No
- **librosa**: No modulation module
- **madmom**: No
- **Essentia**: `KeyExtractor` is single-global, not tracking
- **Research**: Modulation detection is an active MIR task. Some recent DL approaches (e.g., CNNs on chroma) but no mature OSS Python package.

### Genre/instrument specific?
Assumes:
- Tonal music with clear key regions
- Sufficient note density per window (≥4 notes)
- Tempo from MIDI metadata (often wrong for transcribed MIDI)

Fails for:
- Atonal/modern classical
- Electronic (no clear pitch-class distributions)
- Short pieces (<8 windows = window too large)

### Backed by evaluation?
**No.** Real piano test produces **false modulations at 0.37s, 0.74s, 1.11s** — implausibly early in a piece, with musically nonsensical key changes (E minor → F major at 0.37s).

### Can it be deleted?
**Yes.** Current output is actively misleading. The "possible_" prefix is insufficient warning.

### Recommendation
**DELETE** — Replace with:
- Explicit "modulation detection unavailable" state
- Or evaluated OSS when available (see OSS_SURVEY.md)

---

## 3. Melody Extraction — `_midi_melody()` (Skyline Heuristic)

**Location**: `backend/engines/melody/skyline_engine.py:54-117`
**Classification**: CUSTOM_HEURISTIC
**Provenance**: `engine="skyline", heuristic="greedy_continuity_skyline"`

### What it does
Greedy continuity-aware skyline:
1. Group notes by 30ms onset windows
2. Score each candidate: `0.5×duration + 0.4×(1-leap/12) + 0.1×height`
3. Pick best; track margin vs runner-up
4. Aggregate stats on resulting line

### Why it exists
No symbolic melody extraction in music21. Transcribed MIDI is polyphonic; need a "melody" for Analysis UI.

### What it compensates for
- Basic Pitch outputs all notes (melody + accompaniment) in one track
- No source separation → no isolated melody track

### Is there OSS that solves this?
- **music21**: No melody extraction
- **madmom**: `melodia` (audio-based melody extraction) — but requires audio, not MIDI
- **Essentia**: `Melodia` / `PredominantPitchMelodia` — audio-based
- **sklearn/other**: No symbolic melody extraction package
- **Research**: "Skyline" is a known heuristic (highest note). Continuity-aware variants exist in literature but no standard OSS implementation.

### Genre/instrument specific?
- **Piano**: Works moderately (melody often highest voice)
- **Guitar/ensemble**: Fails (melody not always highest)
- **Electronic**: Fails (no clear melodic line, percussive)
- **Vocal+accompaniment**: Would need source separation first

### Backed by evaluation?
**No.** Real piano test: returns `None` (melody extraction failed).

### Can it be deleted?
**Yes, but** would leave `melody` insight empty. The heuristic is documented as such.

### Recommendation
**KEEP_TEMPORARILY_AS_EXPLICIT_GAP_FILLER** with:
- Clear "heuristic" provenance (already done)
- Documented failure modes
- Route to audio-based melody extraction (Essentia Melodia) when audio available

---

## 4. Phrase Detection — `_m21_phrases()`

**Location**: `backend/engines/harmony/music21_engine.py:293-301`
**Classification**: UNIMPLEMENTED
**Provenance**: `engine="custom-rule", method="unimplemented", returns_empty=true`

### What it does
```python
def _m21_phrases(score) -> list[dict[str, Any]]:
    """Phrase boundary detection is NOT implemented.
    ...
    Return empty to avoid fake phrase claims."""
    return []
```

### Why it exists
Placeholder for API contract (`HarmonyResult.phrases: list`).

### Recommendation
**KEEP** — Honest unimplemented is better than fake. Document as explicit gap.

---

## 5. Voice Leading — `_m21_voice_leading()`

**Location**: `backend/engines/harmony/music21_engine.py:227-281`
**Classification**: OSS_DIRECT (conditional)
**Provenance**: `engine="music21"` (when ≥2 parts)

### What it does
Uses music21's `voiceLeading.iterateAllVoiceLeadingQuartets()` between part pairs. Requires ≥2 parts with ≥4 notes each.

### Current Behavior
**Almost never triggers** because:
- Transcribed MIDI = single flattened part (Basic Pitch)
- music21 parser doesn't split into independent voices
- Even with multi-instrument MIDI, parts may not be "independent melodic lines"

### Recommendation
**KEEP** — Correctly returns `None` when evidence insufficient. No bespoke logic to audit.

---

## 6. Rhythm Analysis — `_midi_rhythm()`

**Location**: `backend/analyze.py:165-204`
**Classification**: CUSTOM_HEURISTIC (but honest statistics)

### What it does
Computes from performance MIDI:
- `beat_count` = duration × median_tempo / 60
- `avg_note_duration` = mean(note durations)
- `rhythmic_density` = total_notes / duration
- `syncopation_ratio` = `None` (explicitly not computed)

### Why it exists
Basic rhythmic characterization without audio beat grid.

### Honest Limitation
Docstring: "Syncopation is NOT computed here: a raw performance MIDI has no trustworthy metrical hierarchy... pretty_midi injects a default 4/4 that is an assumption, not evidence."

### Recommendation
**KEEP** — Honest, well-defined statistics. No fabrication.

---

## 7. Key Estimation (Audio Path) — `_extract_librosa()` KS Implementation

**Location**: `backend/domain/capabilities.py:301-361`
**Classification**: OSS_WRAPPED (custom KS on top of librosa chroma)

### What it does
Custom Krumhansl-Schmuckler correlation on librosa chroma_cqt:
```python
chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr)
chroma_mean = np.mean(chroma, axis=1)
# Normalize, correlate with KS profiles
```

### Why it exists
Essentia (preferred) often unavailable on ARM worker. Librosa has no built-in key estimation.

### Is there OSS that solves this?
- **Essentia**: `KeyExtractor` — preferred but not installed
- **librosa**: No key estimation (removed in 0.10+)
- **madmom**: `CNNKeyRecognitionProcessor` — requires model download, GPU
- **Essentia.js/other**: Not Python

### Recommendation
**REPLACE_WITH_OSS** — When Essentia available, use it. Otherwise, consider `madmom` key recognition or accept `None`.

---

## 8. Tempo/Time Signature Suppression — `_transcription_defaults_pulse()`

**Location**: `backend/domain/capabilities.py:681-691`
**Classification**: CUSTOM_HEURISTIC (filtering logic)

### What it does
Checks version metadata for `tempo_is_placeholder` or `meter_is_placeholder` flags (set by transcription engines). If true, suppresses tempo/time_signature insights.

### Why it exists
Basic Pitch outputs 120 BPM / 4/4 as defaults. These are not evidence.

### Recommendation
**KEEP** — Correct filtering behavior. Not analysis logic per se.

---

## 9. Chord Quality Mapping — `_QUALITY_MAP` + `_quality_map()`

**Location**: `backend/engines/harmony/music21_engine.py:26-40` and `backend/evaluation/engines/harmony.py:360-370`
**Classification**: CUSTOM_HEURISTIC (string mapping)

### What it does
Maps music21 quality strings to standard symbols:
```python
_QUALITY_MAP = {
    "major": "M", "minor": "m", "diminished": "dim", ...
}
```

### Why it exists
music21 uses verbose quality names; product wants standard chord symbols.

### Recommendation
**KEEP** — Simple normalization, not analysis logic.

---

## 10. Transcription Cleanup — `_clean_midi()`

**Location**: `backend/music_features.py:456-508`
**Classification**: CUSTOM_HEURISTIC (conservative filtering)

### What it does
Removes from transcribed MIDI:
- Notes < 75ms duration
- Notes outside piano range (21-108)
- Low velocity (<18) + short duration (<160ms)
- Merges same-pitch overlaps

### Why it exists
Basic Pitch produces noise (false positives). Cleanup improves downstream analysis.

### Is there OSS that solves this?
- **Basic Pitch**: Has own thresholds (onset/frame) but no post-hoc cleanup
- **General**: Post-processing is domain-specific

### Recommendation
**KEEP** — Conservative, well-documented, reports every decision. Not analysis per se.

---

## Summary: Bespoke Logic Verdicts

| Component | Verdict | Reason |
|-----------|---------|--------|
| Cadence Detection | **KEEP_TEMPORARILY_AS_EXPLICIT_GAP_FILLER** | No OSS alternative; labeled "candidate"; needs evaluation |
| Modulation Detection | **DELETE** | High false positives; misleading output |
| Melody Extraction (Skyline) | **KEEP_TEMPORARILY_AS_EXPLICIT_GAP_FILLER** | No symbolic OSS alternative; documented heuristic; fails on real test |
| Phrase Detection | **KEEP** (unimplemented) | Honest empty better than fake |
| Voice Leading | **KEEP** | Correctly returns None when insufficient evidence |
| Rhythm Analysis | **KEEP** | Honest statistics, no fabrication |
| Audio Key (librosa KS) | **REPLACE_WITH_OSS** | Essentia preferred; custom KS unvalidated |
| Pulse Suppression | **KEEP** | Correct metadata filtering |
| Chord Quality Map | **KEEP** | Simple normalization |
| Transcription Cleanup | **KEEP** | Conservative preprocessing |

### Top 3 Deletion Candidates
1. **Modulation Detection** — Actively misleading
2. **Audio Key (librosa KS path)** — Unvalidated, replace with Essentia
3. **Cadence Detection** — Weak, but keep as labeled candidate until OSS exists

### Top 3 Replacement Candidates
1. **Modulation Detection** → Evaluated OSS (when available) or explicit unavailable
2. **Audio Key** → Essentia (primary) / madmom (fallback)
3. **Melody Extraction** → Audio-based (Essentia Melodia) when audio available