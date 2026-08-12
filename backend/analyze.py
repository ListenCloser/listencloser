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

from __future__ import annotations

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
    evidence_score: float
    evidence: dict


class ModulationResult(TypedDict):
    from_key: str
    to_key: str
    position: float
    kind: str  # "possible_tonicization" or "possible_modulation"
    run_length_windows: int
    duration_seconds: float
    window_size_seconds: float


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
    syncopation_ratio: float | None
    rhythmic_density: float
    syncopation_available: bool


class MelodyResult(TypedDict):
    low_pitch: int
    high_pitch: int
    range_semitones: int
    unique_pitch_classes: int
    stepwise_ratio: float
    leap_ratio: float
    quality_score: float
    heuristic: str


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
    """Detect cadence candidates from adjacent Roman numerals.

    This is deliberately conservative: a V-I progression is only a candidate,
    not a confirmed cadence. Evidence includes metric position, chord duration,
    and whether the arrival lands near a measure boundary.
    """
    try:
        from music21 import roman
    except ImportError:
        return []
    candidates: list[CadenceResult] = []
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
    # Collect (offset, figure, duration_qn, measure_start_offset)
    chord_seq: list[tuple[float, str, float, float]] = []
    for part in score.parts:
        for measure in part.getElementsByClass("Measure"):
            m_start = float(measure.offset) if measure.offset is not None else 0.0
            for ch in measure.getElementsByClass("Chord"):
                try:
                    rn = roman.romanNumeralFromChord(ch, detected_key)
                    offset = float(ch.getOffsetInHierarchy(score))
                    dur = float(ch.quarterLength) if hasattr(ch, "quarterLength") else 0.0
                    chord_seq.append((offset, rn.figure, dur, m_start))
                except Exception:
                    continue

    for i in range(len(chord_seq) - 1):
        prev_off, prev_fig, prev_dur, prev_m = chord_seq[i]
        off, fig, dur, m_start = chord_seq[i + 1]
        pair = [prev_fig, fig]
        for cad_type, pattern in patterns:
            if pair == pattern:
                # Metric evidence: arrival near a measure boundary boosts confidence.
                near_boundary = (off - m_start) <= 0.5
                # Duration evidence: longer arrival is more phrase-ending-like.
                long_arrival = dur >= 1.0
                evidence_score = 0.5
                if near_boundary:
                    evidence_score += 0.2
                if long_arrival:
                    evidence_score += 0.1
                candidates.append(
                    CadenceResult(
                        type=cad_type,
                        chords=pair,
                        position=round(off, 3),
                        evidence_score=round(min(evidence_score, 0.8), 3),
                        evidence={
                            "metric_position": (
                                "near_measure_boundary" if near_boundary else "mid_measure"
                            ),
                            "arrival_duration_qn": round(dur, 3),
                            "method": "roman_numeral_pattern",
                        },
                    )
                )
                break
    return candidates


def _m21_voice_leading(score) -> VoiceLeadingResult | None:
    """Voice-leading analysis, only when separated voices exist.

    Transcribed MIDI is typically a single flattened part or an arbitrary
    parser split. Contrapuntal motion statistics are meaningless without
    trustworthy independent voices, so suppress when fewer than two parts
    carry independent melodic lines.
    """
    try:
        from music21 import voiceLeading
    except ImportError:
        return None
    parts = [p for p in list(score.parts) if _has_melodic_content(p)]
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


def _has_melodic_content(part) -> bool:
    """A part has melodic content if it contains enough notes to form a line."""
    try:
        notes = list(part.recurse().getElementsByClass("Note"))
        return len(notes) >= 4
    except Exception:
        return False


# ── Rhythm analysis (ISSUE-010) ────────────────────────────────────────────


def _midi_rhythm(midi_path: str) -> RhythmResult | None:
    """Analyze rhythm using pretty_midi.

    Reports note density and average duration (honest, well-defined stats).
    Syncopation is NOT computed here: a raw performance MIDI has no trustworthy
    metrical hierarchy (beat/downbeat) — pretty_midi injects a default 4/4 that
    is an assumption, not evidence. Syncopation requires the beat/downbeat grid
    from the audio beat tracker, which lives in a different pipeline stage.
    """
    try:
        pm = pretty_midi.PrettyMIDI(midi_path)
        duration = pm.get_end_time()
        if duration <= 0:
            return None

        total_notes = sum(len(inst.notes) for inst in pm.instruments if not inst.is_drum)
        if total_notes == 0:
            return None

        tempos = pm.get_tempo_changes()[1]
        bpm = float(np.median(tempos)) if len(tempos) > 0 else 120.0
        beat_count = int(duration * bpm / 60.0)

        all_durations = []
        for inst in pm.instruments:
            if inst.is_drum:
                continue
            for note in inst.notes:
                all_durations.append(note.end - note.start)
        avg_duration = float(np.mean(all_durations)) if all_durations else 0.0

        return RhythmResult(
            beat_count=beat_count,
            avg_note_duration=round(avg_duration, 3),
            syncopation_ratio=None,
            rhythmic_density=round(total_notes / duration, 2),
            syncopation_available=False,
        )
    except Exception:
        return None


def _midi_melody(midi_path: str) -> MelodyResult | None:
    """Continuity-aware skyline melody heuristic.

    Rather than always picking the highest note at each onset, prefer a
    sustained upper line that minimizes melodic leaps and favors longer,
    overlapping notes. Isolated high spikes are downweighted.

    This is a heuristic for polyphonic transcription, NOT a claim about the
    composer's intended melody.
    """
    try:
        pm = pretty_midi.PrettyMIDI(midi_path)
        notes = [note for inst in pm.instruments if not inst.is_drum for note in inst.notes]
        if len(notes) < 2:
            return None
        notes.sort(key=lambda n: (n.start, -n.pitch))

        # Group by onset windows (30 ms) to find competing notes at each time.
        line: list[pretty_midi.Note] = []
        margins: list[float] = []
        i = 0
        while i < len(notes):
            window = [notes[i]]
            j = i + 1
            while j < len(notes) and notes[j].start - notes[i].start < 0.03:
                window.append(notes[j])
                j += 1
            best, margin = _pick_melody_note(window, line[-1] if line else None)
            if best is not None:
                line.append(best)
                margins.append(margin)
            i = j

        if len(line) < 2:
            return None

        intervals = [abs(line[i + 1].pitch - line[i].pitch) for i in range(len(line) - 1)]
        nonzero = [iv for iv in intervals if iv > 0]
        low, high = min(n.pitch for n in line), max(n.pitch for n in line)

        # Quality: average score margin between chosen and runner-up candidates.
        avg_margin = float(np.mean(margins)) if margins else 0.0
        quality_score = round(max(0.0, min(1.0, avg_margin)), 3)

        return MelodyResult(
            low_pitch=low,
            high_pitch=high,
            range_semitones=high - low,
            unique_pitch_classes=len({n.pitch % 12 for n in line}),
            stepwise_ratio=round(sum(iv <= 2 for iv in nonzero) / len(nonzero), 3)
            if nonzero
            else 0.0,
            leap_ratio=round(sum(iv >= 5 for iv in nonzero) / len(nonzero), 3) if nonzero else 0.0,
            quality_score=quality_score,
            heuristic="greedy_continuity_skyline",
        )
    except Exception:
        return None


def _pick_melody_note(
    window: list[pretty_midi.Note],
    prev: pretty_midi.Note | None,
) -> tuple[pretty_midi.Note | None, float]:
    """Pick the most melodic candidate from a simultaneous onset group.

    Scores each candidate by: duration (sustained preferred), small leap from
    previous note, and pitch height. Returns (note, score_margin) where margin
    is the gap between the best and second-best candidate score.
    """
    if not window:
        return None, 0.0
    scored: list[tuple[float, pretty_midi.Note]] = []
    for note in window:
        dur = note.end - note.start
        dur_score = min(dur / 2.0, 1.0)  # cap at 2s
        if prev is not None:
            leap = abs(note.pitch - prev.pitch)
            leap_score = 1.0 - min(leap / 12.0, 1.0)
        else:
            leap_score = 0.5
        height_score = (note.pitch - 60) / 48.0
        score = dur_score * 0.5 + leap_score * 0.4 + height_score * 0.1
        scored.append((score, note))
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_note = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else best_score
    margin = best_score - second_score
    return best_note, margin


# ── Structural analysis: phrases (ISSUE-009) ────────────────────────────────


def _m21_phrases(score) -> list[PhraseResult]:
    """Phrase boundary detection is NOT implemented.

    The previous implementation returned chord spans labelled as "phrases",
    which is misleading. Real phrase-boundary analysis requires evidence
    (rests, slurs, cadence context, melodic closure) that is not available
    from raw transcription. Return empty to avoid fake phrase claims.
    """
    return []


# ── Custom: Modulation detection (no OOTB equivalent) ───────────────────────


def _detect_modulations(score, tempo_bpm: float | None = None) -> list[ModulationResult]:
    """Detect key changes using overlapping windows with sustained-evidence gating.

    A single noisy window change is NOT a modulation. Key history is run-length
    encoded so each sustained local-key region emits at most one transition.
    Brief changes are "possible_tonicization"; sustained ones "possible_modulation".
    """
    all_notes = []
    for part in score.parts:
        for note in part.recurse().getElementsByClass("GeneralNote"):
            offset = float(note.offset) if note.offset is not None else 0.0
            if hasattr(note, "pitch") and note.pitch is not None:
                all_notes.append((offset, note.pitch.midi))
    if len(all_notes) < 16:
        return []
    all_notes.sort(key=lambda x: x[0])

    qpm = tempo_bpm if tempo_bpm else 120.0
    max_offset_qn = all_notes[-1][0] if all_notes else 1.0
    total_sec = max_offset_qn * 60.0 / qpm
    if total_sec <= 0:
        return []

    # Overlapping windows: window_sec step half of window size.
    window_sec = total_sec / 8.0
    step_sec = window_sec / 2.0

    key_history: list[tuple[float, str]] = []
    t = 0.0
    while t + window_sec <= total_sec + 1e-9:
        t_start_qn = t * qpm / 60.0
        t_end_qn = (t + window_sec) * qpm / 60.0
        pitches = [p for toff, p in all_notes if t_start_qn <= toff < t_end_qn]
        if len(pitches) >= _MIN_NOTES_PER_WINDOW:
            pc_dist = np.zeros(12)
            for pc, cnt in Counter(p % 12 for p in pitches).items():
                pc_dist[pc] = cnt
            kr = _key_from_pc_vector(pc_dist)
            if kr is not None:
                key_history.append((t, f"{kr['tonic']} {kr['mode']}"))
        t += step_sec

    # Run-length encode key history into (key, start_time, run_length).
    runs: list[tuple[str, float, int]] = []
    for kt, key in key_history:
        if runs and runs[-1][0] == key:
            prev_key, prev_start, prev_len = runs[-1]
            runs[-1] = (prev_key, prev_start, prev_len + 1)
        else:
            runs.append((key, kt, 1))

    modulations: list[ModulationResult] = []
    for i in range(1, len(runs)):
        prev_key, prev_start, prev_len = runs[i - 1]
        new_key, new_start, new_len = runs[i]
        if new_len >= 3:
            kind = "possible_modulation"
        elif new_len == 2:
            kind = "possible_tonicization"
        else:
            # Single-window fluctuation: not a modulation.
            continue
        modulations.append(
            ModulationResult(
                from_key=prev_key,
                to_key=new_key,
                position=round(new_start, 3),
                kind=kind,
                run_length_windows=new_len,
                duration_seconds=round(new_len * step_sec, 3),
                window_size_seconds=round(window_sec, 3),
            )
        )
    return modulations


# ── Custom: Key estimation from pitch-class vector ──────────────────────────

_KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

_KS_MAJOR_C = _KS_MAJOR - _KS_MAJOR.mean()
_KS_MAJOR_C = _KS_MAJOR_C / np.linalg.norm(_KS_MAJOR_C)
_KS_MINOR_C = _KS_MINOR - _KS_MINOR.mean()
_KS_MINOR_C = _KS_MINOR_C / np.linalg.norm(_KS_MINOR_C)


def _key_from_pc_vector(pc: np.ndarray) -> KeyResult | None:
    """Estimate key from a 12-dim pitch-class distribution.

    Uses centered/normalized Krumhansl-Schmuckler profiles (cosine similarity)
    so the score is not biased by profile magnitude. Returns None when there is
    no pitch-class evidence, rather than fabricating a key.
    """
    if pc.sum() <= 0:
        return None
    pc_c = pc - pc.mean()
    pc_c = pc_c / (np.linalg.norm(pc_c) + 1e-10)
    candidates: list[tuple[str, str, float]] = []
    for shift in range(12):
        rolled = np.roll(pc_c, -shift)
        candidates.append((_NOTES[shift], "major", float(np.dot(rolled, _KS_MAJOR_C))))
        candidates.append((_NOTES[shift], "minor", float(np.dot(rolled, _KS_MINOR_C))))
    candidates.sort(key=lambda x: x[2], reverse=True)
    best = candidates[0]
    confidence = round(min(max(best[2], 0.0), 1.0), 3)
    return KeyResult(tonic=best[0], mode=best[1], confidence=confidence)


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
