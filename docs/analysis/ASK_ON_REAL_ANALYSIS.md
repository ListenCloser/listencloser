# Ask on Real Analysis — Simulated LLM Responses to Actual Evidence

> **Context**: The Ask endpoint (`POST /api/v1/ask`) does not yet exist in the main backend. This document simulates the Ask pipeline using the **actual insights** that would be persisted for the canonical piano fixture (Basic Pitch transcription), and classifies expected failure modes.

---

## Evidence Supplied to AskContext

From `deriveAskContext()` (ask-ui), the LLM would receive these **visible insights** (whole-work + selection):

### Whole-Work Insights (9 total)

| # | Kind | Claim | Evidence (abridged) |
|---|------|-------|---------------------|
| 1 | `key` | "Key: C major" | `{tonic: "C", mode: "major"}` conf=0.853 |
| 2 | `roman_numeral` | "i5" | `{figure: "i5", root: "C", quality: "m", start: 51.64, end: 52.58}` |
| 3 | `roman_numeral` | "iii5" | `{figure: "iii5", root: "E", quality: "m", start: 55.64, end: 57.39}` |
| 4 | `roman_numeral` | "ii" | `{figure: "ii", root: "D", quality: "m", start: 77.12, end: 78.73}` |
| 5 | `roman_numeral` | "ii4" | `{figure: "ii4", root: "D", quality: "m", start: 109.26, end: 110.01}` |
| 6 | `roman_numeral` | "ii" | `{figure: "ii", root: "D", quality: "m", start: 117.26, end: 117.56}` |
| 7 | `rhythm` | "4.32 notes/sec · syncopation unavailable (no metrical grid)" | `{rhythmic_density: 4.32, syncopation_available: false}` |
| 8 | `modulation` | "E minor → F major" | `{from_key: "E minor", to_key: "F major", position: 0.371, kind: "possible_tonicization"}` |
| 9 | `modulation` | "C major → D minor" | `{from_key: "C major", to_key: "D minor", position: 0.741, kind: "possible_tonicization"}` |
| 10 | `modulation` | "C major → D minor" | `{from_key: "C major", to_key: "D minor", position: 1.112, kind: "possible_modulation"}` |

**Missing (suppressed/empty)**: `tempo`, `time_signature`, `chord`, `melody`, `cadence_candidate`, `voice_motion_candidate`, `phrases`

---

## Simulated Ask Sessions

### Question 1: "What can you confidently tell me about this piece?"

**Expected LLM Response** (based on evidence):
> "This piece is in C major (confidence 0.85). The harmonic analysis shows five Roman numeral annotations: i5, iii5, ii, ii4, and ii — all minor chords, which is unusual for a major key. There are three possible modulation/tonicization events detected very early in the piece (within the first 1.1 seconds): E minor to F major, then C major to D minor twice. The rhythmic density is 4.32 notes per second, but no metrical grid is available so syncopation cannot be assessed. No tempo, time signature, chords, melody, cadences, or phrases were detected."

**Classification**: **A (Underlying analysis missing/incorrect)**
- Roman numerals are wrong (minor chords in major key)
- Modulations are false positives (first 1.1 seconds)
- No tempo/meter/chords/melody/cadences/phrases
- LLM correctly reflects garbage evidence → garbage answer

---

### Question 2: "What key is this in?"

**Expected LLM Response**:
> "The analysis indicates C major with a correlation coefficient of 0.853. However, the Roman numeral analysis shows only minor chords (i, iii, ii), which contradicts a C major interpretation. The modulation detection also suggests brief shifts to E minor, F major, and D minor within the first second, though these are labeled as 'possible tonicization' with low evidence."

**Classification**: **A (Underlying analysis missing/incorrect)**
- Key detection exists but contradicted by own harmonic analysis
- Modulation noise confuses the answer
- Confidence 0.853 is correlation, not probability

---

### Question 3: "Does the harmony change anywhere?"

**Expected LLM Response**:
> "The analysis shows three possible modulation events: E minor → F major at 0.37s, C major → D minor at 0.74s, and C major → D minor at 1.11s. However, all occur within the first 1.1 seconds of a ~100 second piece, which is musically implausible. The Roman numerals show only minor chords throughout (i, iii, ii variants), suggesting either the key detection is wrong or the chord analysis is unreliable. No clear harmonic progression or section changes are detectable."

**Classification**: **A (Underlying analysis missing/incorrect)**
- Modulation detector produces false positives due to tempo default
- No real harmonic change evidence

---

### Question 4: "What is notable about the melody?"

**Expected LLM Response**:
> "No melody was extracted. The melody extraction heuristic (greedy continuity skyline) returned no result, likely because the transcription contains polyphonic piano texture without a clear isolated melodic line."

**Classification**: **A (Underlying analysis missing/incorrect)**
- Melody extraction returned `None` — correctly reported as unavailable
- But user gets no melodic info at all

---

### Question 5: "What is the rhythmic character?"

**Expected LLM Response**:
> "The piece has a rhythmic density of 4.32 notes per second with an average note duration of 0.83 seconds. No metrical grid (beats/downbeats) is available from the analysis, so syncopation, groove, and time signature cannot be assessed. The analysis reports 108 beats based on MIDI metadata (120 BPM default), but this is not audio-derived evidence."

**Classification**: **A (Underlying analysis missing/incorrect)**
- Rhythm stats exist but lack metrical context
- Tempo/meter suppressed (correctly) but leaves a void

---

### Question 6: "Where does the piece change structurally?"

**Expected LLM Response**:
> "No structural segments were detected. The audio structure analysis (All-In-One) is disabled by default. The symbolic analysis found no phrases (unimplemented) and no cadences. The three modulation candidates all occur in the first second and are likely artifacts."

**Classification**: **A (Underlying analysis missing/incorrect)**
- Structure analysis disabled
- Phrases unimplemented
- Cadences empty

---

### Question 7: "What is happening in this selected passage?" (Selecting ~measure 5-10 where real music occurs)

**Context**: User selects a region with actual musical content (e.g., 30-60 seconds in).

**Available Selection Insights** (overlap with selection):
- Roman numerals at 51.64-57.39 qn (i5, iii5)
- Modulations at 0.37s, 0.74s, 1.11s (all BEFORE selection)

**Expected LLM Response**:
> "In this selection, the analysis shows two Roman numerals: i5 (C minor) at 51.6-52.6 quarter notes and iii5 (E minor) at 55.6-57.4 quarter notes. However, the global key is C major, making these minor chords unexpected. No chords, melody, cadences, or phrase boundaries are detected in this region. The early modulation candidates (0.37-1.11s) fall before this selection."

**Classification**: **A (Underlying analysis missing/incorrect)**
- RNs in selection are wrong (minor in major key)
- No chords/melody/cadences in selection
- Modulations outside selection irrelevant

---

## Failure Mode Classification Summary

| Question | Primary Failure Mode | Root Cause |
|----------|---------------------|------------|
| General overview | **A** | Most evidence missing/wrong |
| Key | **A** | Key contradicts own harmonic analysis |
| Harmony change | **A** | False modulation positives (tempo default) |
| Melody | **A** | Melody extraction failed (returns None) |
| Rhythm | **A** | No metrical grid (beat tracking not wired) |
| Structure | **A** | Structure disabled, phrases unimplemented |
| Selection detail | **A** | Selection evidence wrong (RNs), missing (chords/melody) |

**Dominant failure mode: A (Underlying analysis missing/incorrect) — 100%**

---

## Why AskContext Cannot Compensate

The AskContext derivation (`deriveAskContext` in ask-ui) **correctly filters and categorizes** insights:
- Only whole-work + selection insights passed
- Temporal spans preserved for referencing
- Provenance available (engine: music21 vs custom-rule)

But it **cannot**:
1. **Invent missing evidence** — No tempo, chords, melody, cadences, phrases
2. **Correct wrong evidence** — False modulations, contradictory RNs
3. **Calibrate confidence** — 0.853 correlation ≠ 85% probability; heuristic scores uncalibrated
4. **Provide audio-grounded truth** — All symbolic, from noisy transcription

---

## What Would Need to Change for Ask to Be Useful

| Missing Capability | Required for Ask | OSS Candidate |
|--------------------|------------------|---------------|
| Audio tempo/beat grid | "When does the beat fall?", "Loop this measure" | Beat This! / Essentia |
| Audio downbeats | "Start of measure 5", "4-bar phrases" | Beat This! / All-In-One |
| Chord progression | "What chords in the bridge?", "Is that a ii-V-I?" | chordia (audio) / music21 (symbolic, needs clean MIDI) |
| Melody extraction | "What's the melody note at 1:23?" | Essentia Melodia / crepe (audio) |
| Phrase boundaries | "Where are the phrases?" | — (research gap) |
| Cadence detection | "Does it resolve?" | — (research gap) |
| Real modulation detection | "Does it change key?" | — (research gap) |
| Structural segments | "Verse/chorus structure?" | All-In-One (audio) |

---

## Conclusion

**Ask is currently useless on this evidence** because the analysis pipeline produces:
- 1 correct but uncalibrated global key
- 5 incorrect Roman numerals
- 3 false modulation positives
- 1 honest rhythm stat (no grid)
- 0 chords, melody, cadences, phrases, tempo, meter

The Ask machinery (context derivation, reference system, action suggestions) is **architecturally sound** but **evidence-starved**. Fixing Ask requires fixing the analysis pipeline first — specifically:
1. Wire audio beat tracking → analysis
2. Replace Basic Pitch with Transkun for piano (already routed)
3. Replace custom modulation/cadence with evaluated OSS or explicit unavailable
4. Add audio-native chord detection (chordia) for non-piano
5. Implement phrase detection or mark explicitly unavailable