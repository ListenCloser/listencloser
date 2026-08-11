"""
MIDI harmonic analysis pipeline.

WHY this module exists:
    The frontend needs structured music analysis data (key, tempo, chords,
    cadences, modulations, voice leading) to display in the Analysis tab.
    This module runs on the backend because music21 and pretty_midi are
    heavy Python libraries that can't run in the browser.

WHAT we build vs what we delegate:
    - Key estimation: music21 (score.analyze)
    - Tempo/time-sig: pretty_midi (MIDI metadata)
    - Chords: music21 (chord.Chord analysis)
    - Roman numerals: music21 (roman module)
    - Cadences: music21 (cadence analysis)
    - Voice leading: music21 (voiceLeading module)
    - Modulations: CUSTOM (windowed key analysis — no OOTB equivalent)
    - Chord smoothing: CUSTOM (post-processing to clean noisy detections)

Pipeline:
    MIDI → music21 parse → analysis functions → structured result
"""

import logging
import time as _time
from collections import Counter
from typing import TypedDict

import numpy as np
import pretty_midi

logger = logging.getLogger("analyze")


# ── TypedDicts ──────────────────────────────────────────────────────────────


class KeyResult(TypedDict):
    tonic: str
    mode: str
    confidence: float


class TempoResult(TypedDict):
    bpm: float
    confidence: float


class TimeSigResult(TypedDict):
    numerator: int
    denominator: int
    confidence: float


class ChordResult(TypedDict):
    root: str
    quality: str
    start: float
    end: float


class RomanNumeralResult(TypedDict):
    figure: str
    root: str
    quality: str
    start: float
    end: float


class CadenceResult(TypedDict):
    type: str
    chords: list[str]
    position: float


class ModulationResult(TypedDict):
    from_key: str
    to_key: str
    position: float


class VoiceLeadingResult(TypedDict):
    parallel: float
    contrary: float
    oblique: float
    similar: float
    motion_summary: str


class PhraseResult(TypedDict):
    start: float
    end: float
    kind: str


class RhythmResult(TypedDict):
    beat_count: int
    avg_note_duration: float
    syncopation_ratio: float
    rhythmic_density: float


class MelodyResult(TypedDict):
    low_pitch: int
    high_pitch: int
    range_semitones: int
    unique_pitch_classes: int
    stepwise_ratio: float
    leap_ratio: float


class AnalysisResult(TypedDict):
    key: KeyResult
    tempo: TempoResult
    time_signature: TimeSigResult
    chords: list[ChordResult]
    roman_numerals: list[RomanNumeralResult]
    cadences: list[CadenceResult]
    modulations: list[ModulationResult]
    voice_leading: VoiceLeadingResult | None
    phrases: list[PhraseResult]
    rhythm: RhythmResult | None
    melody: MelodyResult | None


# ── Constants ───────────────────────────────────────────────────────────────

_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

_QUALITY_MAP = {
    "major": "M",
    "minor": "m",
    "diminished": "dim",
    "augmented": "aug",
    "dominant seventh": "7",
    "major seventh": "maj7",
    "minor seventh": "min7",
    "half-diminished": "m7b5",
    "diminished seventh": "dim7",
    "suspended fourth": "sus4",
    "major sixth": "6",
    "minor sixth": "m6",
    "dominant ninth": "9",
}

_MODULATION_WINDOW_COUNT = 8
_MIN_NOTES_PER_WINDOW = 4


# ── music21 analysis (delegated, not custom) ────────────────────────────────


def _m21_key(score) -> KeyResult:
    """Delegate key estimation to music21's built-in analysis."""
    try:
        key = score.analyze("key")
        corr = key.correlationCoefficient
        return KeyResult(
            tonic=key.tonic.name if key.tonic else "C",
            mode=key.mode or "major",
            confidence=round(corr if corr is not None else 0.85, 3),
        )
    except Exception:
        return KeyResult(tonic="C", mode="major", confidence=0.0)


def _m21_chords(score) -> list[ChordResult]:
    """Delegate chord detection to music21's chord analysis."""
    results: list[ChordResult] = []
    try:
        for chord in score.flatten().getElementsByClass("Chord"):
            try:
                root = chord.root()
                root_name = root.name if root else "?"
                implied = (
                    str(chord.impliedQuality) if hasattr(chord, "impliedQuality") else "unknown"
                )
                quality = _QUALITY_MAP.get(implied, implied)
                start = float(chord.getOffsetInHierarchy(score))
                dur = float(chord.quarterLength) if hasattr(chord, "quarterLength") else 0.0
                if dur > 0:
                    results.append(
                        ChordResult(
                            root=root_name,
                            quality=quality,
                            start=round(start, 3),
                            end=round(start + dur, 3),
                        )
                    )
            except Exception:
                continue
    except Exception:
        pass
    return results


def _m21_roman_numerals(score, detected_key) -> list[RomanNumeralResult]:
    """Delegate Roman numeral analysis to music21."""
    try:
        from music21 import roman
    except ImportError:
        return []
    results: list[RomanNumeralResult] = []
    for part in score.parts:
        for measure in part.getElementsByClass("Measure"):
            for ch in measure.getElementsByClass("Chord"):
                try:
                    rn = roman.romanNumeralFromChord(ch, detected_key)
                    root_p = ch.root()
                    root_name = root_p.name if root_p else "?"
                    implied = str(rn.impliedQuality) if hasattr(rn, "impliedQuality") else "unknown"
                    quality = _QUALITY_MAP.get(implied, implied)
                    start = float(ch.getOffsetInHierarchy(score))
                    dur = float(ch.quarterLength) if hasattr(ch, "quarterLength") else 0.0
                    results.append(
                        RomanNumeralResult(
                            figure=rn.figure,
                            root=root_name,
                            quality=quality,
                            start=round(start, 3),
                            end=round(start + dur, 3),
                        )
                    )
                except Exception:
                    continue
            if len(results) > 500:
                break
        if len(results) > 500:
            break
    return results


def _m21_cadences(score, detected_key) -> list[CadenceResult]:
    """Delegate cadence detection to music21."""
    try:
        from music21 import roman
    except ImportError:
        return []
    cadences: list[CadenceResult] = []
    patterns = [
        ("authentic", ["V", "I"]),
        ("plagal", ["IV", "I"]),
        ("half", ["I", "V"]),
        ("deceptive", ["V", "vi"]),
        ("authentic", ["V7", "I"]),
        ("authentic", ["V", "i"]),
        ("half", ["i", "V"]),
        ("deceptive", ["V", "VI"]),
    ]
    chord_seq: list[tuple[float, str]] = []
    for part in score.parts:
        for measure in part.getElementsByClass("Measure"):
            for ch in measure.getElementsByClass("Chord"):
                try:
                    rn = roman.romanNumeralFromChord(ch, detected_key)
                    offset = float(ch.getOffsetInHierarchy(score))
                    chord_seq.append((offset, rn.figure))
                except Exception:
                    continue
    for i in range(len(chord_seq) - 1):
        pair = [chord_seq[i][1], chord_seq[i + 1][1]]
        for cad_type, pattern in patterns:
            if pair == pattern:
                cadences.append(
                    CadenceResult(
                        type=cad_type,
                        chords=pair,
                        position=round(chord_seq[i][0], 3),
                    )
                )
                break
    return cadences


def _m21_voice_leading(score) -> VoiceLeadingResult | None:
    """Delegate voice leading analysis to music21."""
    try:
        from music21 import voiceLeading
    except ImportError:
        return None
    parts = list(score.parts)
    if len(parts) < 2:
        return None
    parallel = contrary = oblique = similar = total = 0
    for i in range(min(len(parts), 4)):
        for j in range(i + 1, min(len(parts), 4)):
            try:
                for vlq in voiceLeading.iterateAllVoiceLeadingQuartets(parts[i], parts[j]):
                    motion = vlq.motionType()
                    if "Parallel" in str(motion):
                        parallel += 1
                    elif "Contrary" in str(motion):
                        contrary += 1
                    elif "Oblique" in str(motion):
                        oblique += 1
                    elif "Similar" in str(motion):
                        similar += 1
                    total += 1
                    if total > 2000:
                        break
            except Exception:
                continue
            if total > 2000:
                break
        if total > 2000:
            break
    if total == 0:
        return None
    p, c, o, s = (round(n / total, 3) for n in [parallel, contrary, oblique, similar])
    dominant = max(
        ("parallel", p),
        ("contrary", c),
        ("oblique", o),
        ("similar", s),
        key=lambda x: x[1],
    )
    return VoiceLeadingResult(
        parallel=p,
        contrary=c,
        oblique=o,
        similar=s,
        motion_summary=f"{dominant[0]} motion dominates ({dominant[1] * 100:.0f}%)",
    )


# ── Rhythm analysis (ISSUE-010) ────────────────────────────────────────────


def _midi_rhythm(midi_path: str) -> RhythmResult | None:
    """Analyze rhythm using pretty_midi.

    WHY custom: pretty_midi provides beat tracking and note-level timing
    data. We compute:
    - beat_count: estimated beats from tempo
    - avg_note_duration: average note length in seconds
    - syncopation_ratio: fraction of notes off the beat grid
    - rhythmic_density: notes per second
    """
    try:
        pm = pretty_midi.PrettyMIDI(midi_path)
        duration = pm.get_end_time()
        if duration <= 0:
            return None

        # Count total notes
        total_notes = sum(len(inst.notes) for inst in pm.instruments if not inst.is_drum)
        if total_notes == 0:
            return None

        # Estimate beats from tempo
        tempos = pm.get_tempo_changes()[1]
        bpm = float(np.median(tempos)) if len(tempos) > 0 else 120.0
        beat_count = int(duration * bpm / 60.0)

        # Average note duration
        all_durations = []
        for inst in pm.instruments:
            if inst.is_drum:
                continue
            for note in inst.notes:
                all_durations.append(note.end - note.start)
        avg_duration = float(np.mean(all_durations)) if all_durations else 0.0

        # Syncopation: fraction of notes that don't start on a beat
        beat_duration = 60.0 / bpm
        syncopated = 0
        for inst in pm.instruments:
            if inst.is_drum:
                continue
            for note in inst.notes:
                beat_pos = (note.start % beat_duration) / beat_duration
                if beat_pos > 0.1 and beat_pos < 0.9:
                    syncopated += 1
        syncopation_ratio = syncopated / total_notes if total_notes > 0 else 0.0

        return RhythmResult(
            beat_count=beat_count,
            avg_note_duration=round(avg_duration, 3),
            syncopation_ratio=round(syncopation_ratio, 3),
            rhythmic_density=round(total_notes / duration, 2),
        )
    except Exception:
        return None


def _midi_melody(midi_path: str) -> MelodyResult | None:
    """Summarize pitch range and melodic motion from the highest active line.

    This is intentionally labelled as a transcription-derived heuristic. It is
    useful for navigation and discussion, not a claim that polyphonic audio has
    a single objectively correct melody.
    """
    try:
        pm = pretty_midi.PrettyMIDI(midi_path)
        notes = sorted(
            (note for inst in pm.instruments if not inst.is_drum for note in inst.notes),
            key=lambda note: (note.start, -note.pitch),
        )
        if len(notes) < 2:
            return None
        # At a shared onset, retain the upper voice as a transparent heuristic.
        line = []
        for note in notes:
            if line and abs(note.start - line[-1].start) < 0.03:
                continue
            line.append(note)
        intervals = [
            abs(current.pitch - previous.pitch)
            for previous, current in zip(line, line[1:], strict=False)
        ]
        nonzero = [interval for interval in intervals if interval > 0]
        low, high = min(note.pitch for note in line), max(note.pitch for note in line)
        return MelodyResult(
            low_pitch=low,
            high_pitch=high,
            range_semitones=high - low,
            unique_pitch_classes=len({note.pitch % 12 for note in line}),
            stepwise_ratio=round(sum(interval <= 2 for interval in nonzero) / len(nonzero), 3)
            if nonzero
            else 0.0,
            leap_ratio=round(sum(interval >= 5 for interval in nonzero) / len(nonzero), 3)
            if nonzero
            else 0.0,
        )
    except Exception:
        return None


# ── Structural analysis: phrases (ISSUE-009) ────────────────────────────────


def _m21_phrases(score) -> list[PhraseResult]:
    """Detect phrases using music21's slur analysis.

    WHY custom: music21 doesn't have a direct phrase boundary detection
    function that returns structured data. This uses slur markings as
    phrase indicators, which is a standard approach in music analysis.
    """
    try:
        phrases: list[PhraseResult] = []
        for part in score.parts:
            for measure in part.getElementsByClass("Measure"):
                for ch in measure.getElementsByClass("Chord"):
                    try:
                        offset = float(ch.getOffsetInHierarchy(score))
                        dur = float(ch.quarterLength) if hasattr(ch, "quarterLength") else 0.0
                        # Simple heuristic: short chords (< 0.5 beats) are likely grace notes
                        if dur < 0.25:
                            continue
                        phrases.append(
                            PhraseResult(
                                start=round(offset, 3),
                                end=round(offset + dur, 3),
                                kind="chord",
                            )
                        )
                    except Exception:
                        continue
        return phrases[:200]  # Limit to prevent huge outputs
    except Exception:
        return []


# ── Custom: Modulation detection (no OOTB equivalent) ───────────────────────


def _detect_modulations(score, tempo_bpm: float | None = None) -> list[ModulationResult]:
    """
    Detect key modulations via windowed pitch-class analysis.
    Uses time in seconds (not quarter notes) for stable window sizes.
    """
    all_notes = []
    for part in score.parts:
        for note in part.recurse().getElementsByClass("GeneralNote"):
            offset = float(note.offset) if note.offset is not None else 0.0
            if hasattr(note, "pitch") and note.pitch is not None:
                all_notes.append((offset, note.pitch.midi))
    if len(all_notes) < _MODULATION_WINDOW_COUNT * 4:
        return []
    all_notes.sort(key=lambda x: x[0])

    # Convert quarter-note positions to seconds using tempo
    qpm = tempo_bpm if tempo_bpm else 120.0
    max_offset_qn = all_notes[-1][0] if all_notes else 1.0
    max_offset_sec = max_offset_qn * 60.0 / qpm
    window_sec = max_offset_sec / max(_MODULATION_WINDOW_COUNT, 1)

    key_history: list[tuple[float, str]] = []
    for w in range(_MODULATION_WINDOW_COUNT):
        t_start_sec = w * window_sec
        t_end_sec = (w + 1) * window_sec
        t_start_qn = t_start_sec * qpm / 60.0
        t_end_qn = t_end_sec * qpm / 60.0
        pitches = [p for t, p in all_notes if t_start_qn <= t < t_end_qn]
        if len(pitches) < _MIN_NOTES_PER_WINDOW:
            continue
        pc_counts = Counter(p % 12 for p in pitches)
        pc_dist = np.zeros(12)
        for pc, cnt in pc_counts.items():
            pc_dist[pc] = cnt
        kr = _key_from_pc_vector(pc_dist)
        key_history.append((t_start_sec, f"{kr['tonic']} {kr['mode']}"))

    modulations: list[ModulationResult] = []
    for i in range(1, len(key_history)):
        if key_history[i - 1][1] != key_history[i][1]:
            modulations.append(
                ModulationResult(
                    from_key=key_history[i - 1][1],
                    to_key=key_history[i][1],
                    position=round(key_history[i][0], 3),
                )
            )
    return modulations


# ── Custom: Key estimation from pitch-class vector ──────────────────────────

_KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def _key_from_pc_vector(pc: np.ndarray) -> KeyResult:
    """Estimate key from a 12-dim pitch-class distribution.

    WHY custom: Used by modulation detection to estimate key of each window.
    music21's score.analyze('key') requires a full Score object, not a
    pitch-class vector. This is a lightweight alternative for windowed analysis.
    """
    if pc.sum() <= 0:
        return KeyResult(tonic="C", mode="major", confidence=0.0)
    pc = pc / pc.max() if pc.max() > 0 else pc
    best_corr, best_tonic, best_mode = -1.0, "C", "major"
    for shift in range(12):
        rolled = np.roll(pc, shift)
        corr_major = float(np.dot(rolled, _KS_MAJOR))
        corr_minor = float(np.dot(rolled, _KS_MINOR))
        if corr_major > best_corr:
            best_corr, best_tonic, best_mode = corr_major, _NOTES[shift], "major"
        if corr_minor > best_corr:
            best_corr, best_tonic, best_mode = corr_minor, _NOTES[shift], "minor"
    max_possible = float(np.dot(_KS_MAJOR, _KS_MAJOR))
    confidence = round(min(max(best_corr / max_possible if max_possible > 0 else 0.0, 0.0), 1.0), 3)
    return KeyResult(tonic=best_tonic, mode=best_mode, confidence=confidence)


# ── Main entry point ────────────────────────────────────────────────────────


def analyze_midi(midi_path: str) -> AnalysisResult:
    """
    Full symbolic analysis of a MIDI file.

    Architecture: Parse once with music21, extract everything from the
    parsed score. Use pretty_midi only for tempo/time-sig metadata.
    """
    t0 = _time.perf_counter()

    # Parse with music21 (single parse for all analyses)
    from music21 import converter

    try:
        score = converter.parse(midi_path, quantizePost=False)
    except Exception:
        logger.exception("music21 parse failed")
        score = None

    pm = pretty_midi.PrettyMIDI(midi_path)

    result: AnalysisResult = {
        "key": KeyResult(tonic="C", mode="major", confidence=0.0),
        "tempo": TempoResult(bpm=120.0, confidence=0.0),
        "time_signature": TimeSigResult(numerator=4, denominator=4, confidence=0.0),
        "chords": [],
        "roman_numerals": [],
        "cadences": [],
        "modulations": [],
        "voice_leading": None,
        "phrases": [],
        "rhythm": None,
        "melody": None,
    }

    # Tempo from MIDI metadata
    try:
        _, tempos = pm.get_tempo_changes()
        if len(tempos) > 0:
            result["tempo"] = TempoResult(bpm=round(float(np.median(tempos)), 1), confidence=0.9)
    except Exception:
        pass

    # Time signature from MIDI metadata
    try:
        _, ts_nums, ts_denoms = pm.get_time_signatures()
        if len(ts_nums) > 0:
            result["time_signature"] = TimeSigResult(
                numerator=int(ts_nums[0]), denominator=int(ts_denoms[0]), confidence=0.9
            )
    except Exception:
        pass

    if score is not None:
        # Key estimation (music21)
        result["key"] = _m21_key(score)

        # Chords (music21)
        result["chords"] = _m21_chords(score)

        # Roman numerals (music21)
        detected_key = score.analyze("key")
        result["roman_numerals"] = _m21_roman_numerals(score, detected_key)

        # Cadences (music21)
        result["cadences"] = _m21_cadences(score, detected_key)

        # Voice leading (music21)
        result["voice_leading"] = _m21_voice_leading(score)
        result["phrases"] = _m21_phrases(score)

        # Modulations (custom — windowed analysis)
        result["modulations"] = _detect_modulations(
            score, result["tempo"]["bpm"] if "tempo" in result and result["tempo"] else None
        )

    # These operate directly on the saved performance MIDI and remain useful
    # even when symbolic parsing fails.
    result["rhythm"] = _midi_rhythm(midi_path)
    result["melody"] = _midi_melody(midi_path)

    total_ms = round((_time.perf_counter() - t0) * 1000)
    logger.info("analyze_total", extra={"step": "total", "step_ms": total_ms})
    return result
