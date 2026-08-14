# Real Piano Audit — Analysis Output on Canonical Fixture

> **Fixture**: `tests/fixtures/real-piano.m4a` (solo piano, ~3 min)
> **Transcription**: Basic Pitch (default profile) → 234 notes
> **Analysis**: `analyze.analyze_midi()` on transcribed MIDI
> **Date**: 2026-08-14

---

## Four-Stage Evidence Flow (Critical Distinction)

| Stage | What It Contains | 120 BPM / 4/4 Present? | Zero Chords? | False Modulations? |
|-------|------------------|------------------------|--------------|-------------------|
| **1. Raw `AnalysisResult`** (analyze.py output) | Full typed dict with all fields | ✅ Yes (bpm=120, confidence=0.9) | ✅ Yes (`chords: []`) | ✅ Yes (3 events) |
| **2. Persisted `Insight` rows** (DB) | Filtered via `_create_insight()` | ❌ Suppressed by `_transcription_defaults_pulse()` | ✅ Yes (no chord insights created) | ✅ Yes (3 modulation insights created) |
| **3. User-visible Inspector** (GET /insights) | Same as persisted Insights | ❌ Not shown | ❌ Not shown | ✅ **Shown** (3 "possible_modulation" cards) |
| **4. AskContext evidence** (deriveAskContext) | `visibleInsights` filtered to whole-work + selection | ❌ Not in evidence | ❌ Not in evidence | ✅ **In evidence** (3 modulation objects) |

**Key finding**: The 120 BPM / 4/4 placeholders are correctly suppressed at persistence (stage 2), so users don't see them in Inspector (stage 3). However, the **false modulations survive all filters** and reach both Inspector and AskContext.

---

## Raw AnalysisResult (Complete)

```json
{
  "key": {
    "tonic": "C",
    "mode": "major",
    "confidence": 0.853
  },
  "tempo": {
    "bpm": 120.0,
    "confidence": 0.9
  },
  "time_signature": {
    "numerator": 4,
    "denominator": 4,
    "confidence": 0.9
  },
  "chords": [],
  "roman_numerals": [
    { "figure": "i5", "root": "C", "quality": "m", "start": 51.641, "end": 52.577 },
    { "figure": "iii5", "root": "E", "quality": "m", "start": 55.641, "end": 57.386 },
    { "figure": "ii", "root": "D", "quality": "m", "start": 77.123, "end": 78.732 },
    { "figure": "ii4", "root": "D", "quality": "m", "start": 109.264, "end": 110.009 },
    { "figure": "ii", "root": "D", "quality": "m", "start": 117.264, "end": 117.559 }
  ],
  "cadences": [],
  "modulations": [
    { "from_key": "E minor", "to_key": "F major", "position": 0.371, "kind": "possible_tonicization", "run_length_windows": 2, "duration_seconds": 0.247, "window_size_seconds": 0.247 },
    { "from_key": "C major", "to_key": "D minor", "position": 0.741, "kind": "possible_tonicization", "run_length_windows": 2, "duration_seconds": 0.247, "window_size_seconds": 0.247 },
    { "from_key": "C major", "to_key": "D minor", "position": 1.112, "kind": "possible_modulation", "run_length_windows": 3, "duration_seconds": 0.371, "window_size_seconds": 0.247 }
  ],
  "voice_leading": null,
  "phrases": [],
  "rhythm": { "beat_count": 108, "avg_note_duration": 0.832, "syncopation_ratio": null, "rhythmic_density": 4.32, "syncopation_available": false },
  "melody": null,
  "harmony_provenance": { ... },
  "melody_provenance": { ... }
}
```

---

## Human-Readable Timeline (Persisted Insights → User Visible)

| Time / Measure | Insight Type | Claim | Confidence | Provenance | Shown in Inspector? | In AskContext? |
|----------------|--------------|-------|------------|------------|---------------------|----------------|
| Global | **Key** | "Key: C major" | 0.853 | music21 `analyze("key")` | ✅ | ✅ |
| Global | **Tempo** | — | — | — | ❌ (suppressed) | ❌ |
| Global | **Time Signature** | — | — | — | ❌ (suppressed) | ❌ |
| 51.64-52.58 qn | Roman Numeral | "i5" | None | music21 RN | ✅ | ✅ |
| 55.64-57.39 qn | Roman Numeral | "iii5" | None | music21 RN | ✅ | ✅ |
| 77.12-78.73 qn | Roman Numeral | "ii" | None | music21 RN | ✅ | ✅ |
| 109.26-110.01 qn | Roman Numeral | "ii4" | None | music21 RN | ✅ | ✅ |
| 117.26-117.56 qn | Roman Numeral | "ii" | None | music21 RN | ✅ | ✅ |
| 0.371 sec | Modulation | "E minor → F major" | None | Custom windowed KS | ✅ | ✅ |
| 0.741 sec | Modulation | "C major → D minor" | None | Custom windowed KS | ✅ | ✅ |
| 1.112 sec | Modulation | "C major → D minor" | None | Custom windowed KS | ✅ | ✅ |
| Global | Rhythm | "4.32 notes/sec · syncopation unavailable..." | None | pretty_midi stats | ✅ | ✅ |
| Global | Melody | — | — | — | ❌ (None) | ❌ |
| Global | Chords | — | — | — | ❌ (empty) | ❌ |
| Global | Cadences | — | — | — | ❌ (empty) | ❌ |
| Global | Voice Leading | — | — | — | ❌ (None) | ❌ |
| Global | Phrases | — | — | — | ❌ (empty) | ❌ |

---

## Root Cause Proof: Zero Chords

### Code Path: `_m21_chords()` in `engines/harmony/music21_engine.py:79-112`

```python
for chord in score.flatten().getElementsByClass("Chord"):
    root = chord.root()
    implied = str(chord.impliedQuality) if hasattr(chord, "impliedQuality") else ""
    quality = _QUALITY_MAP.get(implied, implied)
    if not quality or quality == "unknown":
        continue  # ← SKIPPED
```

### Mechanical Evidence from Canonical MIDI

| Metric | Value |
|--------|-------|
| Explicit `Chord` objects in score | **28** |
| `impliedQuality` on those chords | **Empty string `""`** (all 28) |
| `_QUALITY_MAP.get("", "")` → | `""` (empty) |
| `if not quality or quality == "unknown"` → | **True** (skipped) |
| **Chords emitted** | **0** |

**Root cause**: Basic Pitch produces simultaneous note pairs/triples that music21 parses as `Chord` objects, but without harmonic spelling (no `impliedQuality`). The quality mapping returns empty string, triggering the skip filter.

**Not caused by**: "single-track MIDI" per se — music21 *does* find 28 Chord objects. The failure is the quality filter on un-spelled simultaneities.

---

## Root Cause Proof: False Modulations

### Code Path: `_detect_modulations()` in `engines/harmony/music21_engine.py:304-377`

### Numerical Trace from Canonical MIDI

| Variable | Value | Source |
|----------|-------|--------|
| `tempo_bpm` passed to analyze | **120.0** | MIDI metadata (Basic Pitch default) |
| `qpm` used in detection | **120.0** | `tempo_bpm if tempo_bpm else 120.0` |
| `max_offset_qn` (last note offset) | **3.75** | `part.recurse().getElementsByClass("GeneralNote")` |
| `total_sec = max_offset_qn * 60 / qpm` | **1.875 sec** | 3.75 × 60 / 120 |
| `window_sec = total_sec / 8` | **0.234 sec** | 1.875 / 8 |
| `step_sec = window_sec / 2` | **0.117 sec** | 0.234 / 2 |
| Number of windows | **16** | 1.875 / 0.117 |

### Window-by-Window Key Estimation (KS on 4-90 notes per window)

| Window t (sec) | Notes | KS Key | Confidence |
|----------------|-------|--------|------------|
| 0.000 | 90 | C major | 0.826 |
| 0.117 | 25 | A minor | 0.696 |
| 0.234 | 26 | A minor | 0.692 |
| 0.352 | 20 | A minor | 0.495 |
| 0.469 | 15 | D minor | 0.540 |
| 0.586 | 11 | D minor | 0.597 |
| 0.703 | 22 | C major | 0.672 |
| 0.820 | 30 | F major | 0.679 |
| 0.938 | 17 | D minor | 0.775 |
| 1.055 | 10 | G minor | 0.624 |
| 1.172 | 27 | D minor | 0.884 |
| 1.289 | 24 | D minor | 0.932 |
| 1.406 | 12 | F major | 0.645 |
| 1.523 | 37 | C major | 0.652 |
| 1.641 | 30 | C major | 0.704 |

### Run-Length Encoding → False Modulations

| Run | Key | Start (sec) | Length (windows) | Emitted As |
|-----|-----|-------------|------------------|------------|
| 1 | C major | 0.000 | 1 | — |
| 2 | **A minor** | 0.117 | **3** | **possible_modulation** (C→Am @ 0.117) |
| 3 | D minor | 0.469 | 2 | possible_tonicization (Am→Dm @ 0.469) |
| 4 | C major | 0.703 | 1 | — |
| 5 | F major | 0.820 | 1 | — |
| 6 | D minor | 0.938 | 1 | — |
| 7 | G minor | 1.055 | 1 | — |
| 8 | **D minor** | 1.172 | **2** | **possible_tonicization** (Gm→Dm @ 1.172) |
| 9 | F major | 1.406 | 1 | — |
| 10 | **C major** | 1.523 | **2** | **possible_tonicization** (F→C @ 1.523) |

**Result**: 4 false modulation events in first 1.5 seconds of a ~100-second piece.

**Root cause**: The MIDI's default 120 BPM compresses the 3.75 quarter-note span into 1.875 seconds. The 8-window KS analysis runs on ~0.23s windows with only 4-90 notes each — far too small for stable key estimation. The KS estimator fluctuates wildly on tiny, noisy windows.

**Not caused by**: The modulation algorithm itself — given correct tempo and sufficient note density per window, the run-length gating is reasonable. The causal chain is: **Basic Pitch default tempo → wrong quarter-note→second conversion → microscopic windows → KS noise → false modulations**.

---

## What the System Actually Knows (Persisted Insights)

| Category | Status | Details |
|----------|--------|---------|
| **Global key** | ✅ Known | C major, correlation 0.853 (moderate evidence) |
| **Global tempo** | ❌ Suppressed | 120 BPM is Basic Pitch default; correctly filtered at persistence |
| **Global meter** | ❌ Suppressed | 4/4 is Basic Pitch default; correctly filtered at persistence |
| **Chord progression** | ❌ **MISSING** | 28 Chord objects found but all filtered by empty `impliedQuality` |
| **Harmonic function** | ❌ **MISSING** | 5 Roman numerals but all minor (i, iii, ii) — nonsensical for C major |
| **Cadences** | ❌ **MISSING** | Zero detected (pattern matcher finds no valid adjacent RN pairs) |
| **Modulations** | ❌ **WRONG** | 4 false positives in first 1.5 seconds (survive all filters) |
| **Melody** | ❌ **MISSING** | Skyline heuristic returned None |
| **Rhythm** | ⚠️ **PARTIAL** | Density/duration stats only; no metrical grid |
| **Phrases** | ❌ **MISSING** | Explicitly unimplemented |
| **Voice leading** | ❌ **MISSING** | Requires multi-part (transcription = single part) |

---

## What Reaches the User (Inspector + AskContext)

| Insight | Inspector | AskContext | Problem |
|---------|-----------|------------|---------|
| Key: C major | ✅ | ✅ | Only reliable signal |
| 5 Roman numerals | ✅ | ✅ | All minor in major key — misleading |
| 4 Modulations | ✅ | ✅ | **False positives** — actively harmful |
| Rhythm density | ✅ | ✅ | Honest but context-free |
| Tempo / Meter | ❌ | ❌ | Correctly suppressed |
| Chords / Melody / Cadences / Phrases | ❌ | ❌ | Missing |

**The user sees**: Key + 5 wrong RNs + 4 false modulations + rhythm density. That's it.

---

## What Output Is Clearly Wrong (in Persisted Insights)

1. **4 Modulation insights** — False positives from tempo-compressed KS windows. Actively misleading.
2. **5 Roman numeral insights** — All minor chords (i5, iii5, ii, ii4, ii) in a C major piece. Contradicts key insight.
3. **Zero chord insights** — 28 Chord objects existed but were filtered by empty quality mapping.

---

## What Output Is Technically Correct But Useless

| Output | Why Correct | Why Useless |
|--------|-------------|-------------|
| `rhythmic_density: 4.32 notes/sec` | Accurate count from transcribed MIDI | Transcription noise inflates; no metrical context |
| `key.confidence: 0.853` | Real music21 correlation | Correlation ≠ probability; no calibration |
| `harmony_provenance` per-component | Honest about custom vs music21 | Downstream consumers ignore it |

---

## Comparison: What Transkun Would Produce (Projected)

| Aspect | Basic Pitch (current) | Transkun (solo_piano profile) |
|--------|----------------------|-------------------------------|
| Note F1 (macro) | 0.1083 | **0.8034** |
| Note accuracy | Low (noise, false positives) | High (piano-specific) |
| Chord detection | 0 (quality filter) | Likely >0 (cleaner notes → music21 spells chords) |
| Melody extraction | None | May work (cleaner separation) |
| Modulation detection | 4 false positives | Fewer (if tempo from audio) or same (if still uses MIDI tempo) |

**Critical insight**: The analysis pipeline is only as good as its transcription input. Basic Pitch's general-purpose output produces Chord objects that music21 cannot spell, and a default tempo that breaks time-domain analysis.

---

## Conclusion

The canonical piano fixture exposes a **fundamental mismatch**:
1. **Transcription** (Basic Pitch) → noisy, single-track, default tempo/meter, un-spelled simultaneities
2. **Symbolic analysis** (music21) → expects clean, spelled chords, correct tempo
3. **Custom heuristics** (modulation, cadence, melody) → operate on garbage input → garbage output

**The analysis pipeline cannot be fixed without fixing the transcription→analysis interface** — specifically:
- Audio-derived tempo/beat must replace MIDI metadata tempo
- Chord detection needs either audio-native (chordia) or transcription that produces spelled chords (Transkun)
- Modulation detection must be deleted or receive correct tempo