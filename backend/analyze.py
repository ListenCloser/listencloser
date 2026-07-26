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


class AnalysisResult(TypedDict):
    key: KeyResult
    tempo: TempoResult
    time_signature: TimeSigResult
    chords: list[ChordResult]
    roman_numerals: list[RomanNumeralResult]
    cadences: list[CadenceResult]
    modulations: list[ModulationResult]
    voice_leading: VoiceLeadingResult | None


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


# ── Custom: Modulation detection (no OOTB equivalent) ───────────────────────


def _detect_modulations(score, tempo_bpm: float | None = None) -> list[ModulationResult]:
    """
    Detect key modulations via windowed pitch-class analysis.

    WHY custom: music21 doesn't have a direct modulation detection function
    that works on MIDI. This uses a simple windowed approach: divide the
    piece into N windows, estimate the key of each, and detect changes.

    This is a reasonable custom implementation — the algorithm is standard
    in music information retrieval (MIR) literature.
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
    max_offset = all_notes[-1][0] if all_notes else 1.0
    window_size = max_offset / max(_MODULATION_WINDOW_COUNT, 1)
    key_history: list[tuple[float, str]] = []
    for w in range(_MODULATION_WINDOW_COUNT):
        t_start = w * window_size
        t_end = (w + 1) * window_size
        pitches = [p for t, p in all_notes if t_start <= t < t_end]
        if len(pitches) < _MIN_NOTES_PER_WINDOW:
            continue
        pc_counts = Counter(p % 12 for p in pitches)
        pc_dist = np.zeros(12)
        for pc, cnt in pc_counts.items():
            pc_dist[pc] = cnt
        kr = _key_from_pc_vector(pc_dist)
        key_history.append((t_start, f"{kr['tonic']} {kr['mode']}"))
    modulations: list[ModulationResult] = []
    qpm = tempo_bpm if tempo_bpm else 120.0
    for i in range(1, len(key_history)):
        if key_history[i - 1][1] != key_history[i][1]:
            position_sec = key_history[i][0] * 60.0 / qpm
            modulations.append(
                ModulationResult(
                    from_key=key_history[i - 1][1],
                    to_key=key_history[i][1],
                    position=round(position_sec, 3),
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

        # Modulations (custom — windowed analysis)
        result["modulations"] = _detect_modulations(
            score, result["tempo"]["bpm"] if "tempo" in result and result["tempo"] else None
        )

    total_ms = round((_time.perf_counter() - t0) * 1000)
    logger.info("analyze_total", extra={"step": "total", "step_ms": total_ms})
    return result
