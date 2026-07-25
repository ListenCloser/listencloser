"""MIDI harmonic analysis pipeline.

All analysis runs on symbolic data (MIDI). Audio files are *never*
analysed directly — the transcribe endpoint converts audio → MIDI first,
then this module analyses the MIDI.

Pipeline:
    MIDI  →  music21      (key, chords, Roman numerals, cadences, modulations, voice leading)
          →  pretty_midi  (tempo, time-sig)
          →  windowed PC analysis (modulation detection)
"""

import logging
import os
import tempfile
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


# ── Constants ───────────────────────────────────────────────────────────────

_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

_QUALITY_MAP = {
    "major": "M", "minor": "m", "diminished": "dim", "augmented": "aug",
    "dominant seventh": "7", "major seventh": "maj7", "minor seventh": "min7",
    "half-diminished": "m7b5", "diminished seventh": "dim7",
    "suspended fourth": "sus4", "major sixth": "6", "minor sixth": "m6",
    "dominant ninth": "9",
}

_KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

_MODULATION_WINDOW_COUNT = 8
_MIN_NOTES_PER_WINDOW = 4
_MIN_CHORD_FRAME_SUM = 0.1
_MIN_CHORD_DURATION = 0.3
_MIDI_FRAME_WINDOW = 0.25

_CHORD_INTERVALS: dict[str, list[int]] = {
    "M": [0, 4, 7], "m": [0, 3, 7], "dim": [0, 3, 6], "aug": [0, 4, 8],
    "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "min7": [0, 3, 7, 10],
    "m7b5": [0, 3, 6, 10], "sus4": [0, 5, 7], "6": [0, 4, 7, 9],
    "m6": [0, 3, 7, 9], "9": [0, 4, 7, 10, 2],
}

_ALLOWED_ROOT_TRANSITIONS: set[tuple[int, int]] = set()
for _i in range(12):
    for _interval in [0, 7, 5, 1, 11, 3, 4, 9, 8, 6]:
        _ALLOWED_ROOT_TRANSITIONS.add((_i, (_i + _interval) % 12))


_MINOR_QUALITIES = {"m", "dim", "m7", "m7b5", "m6"}


def _build_chord_templates() -> dict[str, np.ndarray]:
    templates: dict[str, np.ndarray] = {}
    for root in range(12):
        for quality, intervals in _CHORD_INTERVALS.items():
            mask = np.zeros(12, dtype=np.float64)
            for iv in intervals:
                mask[(root + iv) % 12] = 1.0
            mask[root % 12] = 1.5
            third = (root + (3 if quality in _MINOR_QUALITIES else 4)) % 12
            mask[third] = 1.3
            templates[f"{_NOTES[root]}:{quality}"] = mask
    return templates


_CHORD_TEMPLATES = _build_chord_templates()


# ── Key estimation ──────────────────────────────────────────────────────────


def _key_from_pc_vector(pc: np.ndarray) -> KeyResult:
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


# ── music21 analysis ────────────────────────────────────────────────────────


def _m21_key(score, key_obj) -> KeyResult:
    try:
        corr = key_obj.correlationCoefficient
        return KeyResult(
            tonic=key_obj.tonic.name if key_obj.tonic else "C",
            mode=key_obj.mode or "major",
            confidence=round(corr if corr is not None else 0.85, 3),
        )
    except Exception:
        return KeyResult(tonic="C", mode="major", confidence=0.0)


def _m21_roman_numerals(score, detected_key) -> list[RomanNumeralResult]:
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
                    results.append(RomanNumeralResult(
                        figure=rn.figure, root=root_name, quality=quality,
                        start=round(start, 3), end=round(start + dur, 3),
                    ))
                except Exception:
                    continue
            if len(results) > 500:
                break
        if len(results) > 500:
            break
    return results


def _m21_cadences(score, detected_key) -> list[CadenceResult]:
    try:
        from music21 import roman
    except ImportError:
        return []
    cadences: list[CadenceResult] = []
    patterns = [
        ("authentic", ["V", "I"]), ("plagal", ["IV", "I"]),
        ("half", ["I", "V"]), ("deceptive", ["V", "vi"]),
        ("authentic", ["V7", "I"]), ("authentic", ["V", "i"]),
        ("half", ["i", "V"]), ("deceptive", ["V", "VI"]),
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
                cadences.append(CadenceResult(
                    type=cad_type, chords=pair,
                    position=round(chord_seq[i][0], 3),
                ))
                break
    return cadences


def _m21_voice_leading(score) -> VoiceLeadingResult | None:
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
        ("parallel", p), ("contrary", c), ("oblique", o), ("similar", s),
        key=lambda x: x[1],
    )
    return VoiceLeadingResult(
        parallel=p, contrary=c, oblique=o, similar=s,
        motion_summary=f"{dominant[0]} motion dominates ({dominant[1] * 100:.0f}%)",
    )


def _m21_phrases(score) -> list[PhraseResult]:
    phrases: list[PhraseResult] = []
    for part in score.parts:
        for slur in part.getElementsByClass("Slur"):
            try:
                start_note = slur.getFirst()
                end_note = slur.getLast()
                if start_note and end_note:
                    start = float(start_note.getOffsetInHierarchy(score))
                    end = float(end_note.getOffsetInHierarchy(score))
                    if hasattr(end_note, "quarterLength"):
                        end += float(end_note.quarterLength)
                    if end > start:
                        phrases.append(PhraseResult(
                            start=round(start, 3), end=round(end, 3),
                            kind="slur",
                        ))
            except Exception:
                continue
    if not phrases:
        for part in score.parts:
            measures = part.getElementsByClass("Measure")
            if len(measures) >= 4:
                for i in range(0, len(measures), 4):
                    group = measures[i:i + 4]
                    if len(group) >= 2:
                        start = float(group[0].getOffsetInHierarchy(score))
                        last = group[-1]
                        end = float(last.getOffsetInHierarchy(score))
                        if hasattr(last, "quarterLength"):
                            end += float(last.quarterLength)
                        if end > start:
                            phrases.append(PhraseResult(
                                start=round(start, 3), end=round(end, 3),
                                kind="measure_group",
                            ))
                break
    return phrases


# ── Chord detection from MIDI frames ────────────────────────────────────────


def _midi_frames(midi_path: str) -> tuple[np.ndarray, list[tuple[float, np.ndarray]]]:
    pm = pretty_midi.PrettyMIDI(midi_path)
    pc_hist = np.zeros(12, dtype=np.float64)
    windows: dict[int, np.ndarray] = {}
    for instr in pm.instruments:
        if instr.is_drum:
            continue
        for note in instr.notes:
            pclass = note.pitch % 12
            dur = max(note.end - note.start, 0.0)
            pc_hist[pclass] += dur
            wid = int(note.start / _MIDI_FRAME_WINDOW)
            if wid not in windows:
                windows[wid] = np.zeros(12, dtype=np.float64)
            windows[wid][pclass] += dur
    sorted_w = sorted(windows.items())
    frames = [(w * _MIDI_FRAME_WINDOW, v) for w, v in sorted_w if v.sum() > 0]
    return pc_hist, frames


def _chords_from_frames(frames: list[tuple[float, np.ndarray]]) -> list[ChordResult]:
    if not frames:
        return []
    chords: list[ChordResult] = []
    current_label, current_start, current_root, current_quality = "", 0.0, "", ""
    templates = list(_CHORD_TEMPLATES.items())
    for t, vec in frames:
        if vec.sum() < _MIN_CHORD_FRAME_SUM:
            if current_label:
                chords.append(ChordResult(root=current_root, quality=current_quality,
                                          start=round(current_start, 3), end=round(t, 3)))
                current_label = ""
            continue
        frame = vec / vec.max() if vec.max() > 0 else vec
        best_score, best_label = -1.0, "C:M"
        for label, tmpl in templates:
            score = float(np.dot(frame, tmpl))
            if score > best_score:
                best_score, best_label = score, label
        root, quality = best_label.split(":")
        if best_label != current_label:
            if current_label and t - current_start > _MIN_CHORD_DURATION:
                chords.append(ChordResult(root=current_root, quality=current_quality,
                                          start=round(current_start, 3), end=round(t, 3)))
            current_label = best_label
            current_start = t
            current_root = root
            current_quality = quality
    if current_label:
        chords.append(ChordResult(root=current_root, quality=current_quality,
                                  start=round(current_start, 3), end=round(frames[-1][0], 3)))
    return chords


def _smooth_chords(chords: list[ChordResult]) -> list[ChordResult]:
    if len(chords) <= 1:
        return chords
    filtered = [chords[0]]
    for ch in chords[1:]:
        prev_idx = _NOTES.index(filtered[-1]["root"]) if filtered[-1]["root"] in _NOTES else -1
        curr_idx = _NOTES.index(ch["root"]) if ch["root"] in _NOTES else -1
        if prev_idx >= 0 and curr_idx >= 0 and (prev_idx, curr_idx) in _ALLOWED_ROOT_TRANSITIONS:
            filtered.append(ch)
        else:
            filtered[-1]["end"] = ch["end"]
    merged = [filtered[0]]
    for ch in filtered[1:]:
        if ch["root"] == merged[-1]["root"] and ch["quality"] == merged[-1]["quality"]:
            merged[-1]["end"] = ch["end"]
        else:
            merged.append(ch)
    result = [ch for ch in merged if ch["end"] - ch["start"] >= _MIN_CHORD_DURATION]
    return result if result else merged[:1]


# ── Modulation detection ────────────────────────────────────────────────────


def _detect_modulations(score) -> list[ModulationResult]:
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
    window_sec = max_offset / max(_MODULATION_WINDOW_COUNT, 1)
    key_history: list[tuple[float, str]] = []
    for w in range(_MODULATION_WINDOW_COUNT):
        t_start = w * window_sec
        t_end = (w + 1) * window_sec
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
    for i in range(1, len(key_history)):
        if key_history[i - 1][1] != key_history[i][1]:
            modulations.append(ModulationResult(
                from_key=key_history[i - 1][1], to_key=key_history[i][1],
                position=round(key_history[i][0], 3),
            ))
    return modulations


# ── Main entry point ────────────────────────────────────────────────────────


def analyze_midi(midi_path: str) -> AnalysisResult:
    t0 = _time.perf_counter()
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
        "chords": [], "roman_numerals": [], "cadences": [],
        "modulations": [], "voice_leading": None, "phrases": [],
    }

    try:
        _, tempos = pm.get_tempo_changes()
        if len(tempos) > 0:
            result["tempo"] = TempoResult(bpm=round(float(np.median(tempos)), 1), confidence=0.9)
    except Exception:
        pass

    try:
        _, ts_nums, ts_denoms = pm.get_time_signatures()
        if len(ts_nums) > 0:
            result["time_signature"] = TimeSigResult(
                numerator=int(ts_nums[0]), denominator=int(ts_denoms[0]), confidence=0.9
            )
    except Exception:
        pass

    if score is not None:
        detected_key = score.analyze("key")
        result["key"] = _m21_key(score, detected_key)
        result["roman_numerals"] = _m21_roman_numerals(score, detected_key)
        result["cadences"] = _m21_cadences(score, detected_key)
        result["voice_leading"] = _m21_voice_leading(score)
        result["phrases"] = _m21_phrases(score)
        result["modulations"] = _detect_modulations(score)

    _, frames = _midi_frames(midi_path)
    result["chords"] = _smooth_chords(_chords_from_frames(frames))

    total_ms = round((_time.perf_counter() - t0) * 1000)
    logger.info("analyze_total", extra={"step": "total", "step_ms": total_ms})
    return result


def analyze_from_notes(notes: list[dict]) -> AnalysisResult:
    import contextlib
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0, is_drum=False, name="Piano")
    for n in notes:
        inst.notes.append(
            pretty_midi.Note(
                velocity=n.get("velocity", 100),
                pitch=n["pitch"],
                start=n["start"],
                end=n["end"],
            )
        )
    pm.instruments.append(inst)
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        midi_path = f.name
        pm.write(midi_path)
    try:
        return analyze_midi(midi_path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(midi_path)
