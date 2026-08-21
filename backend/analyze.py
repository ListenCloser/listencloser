"""
MIDI harmonic analysis pipeline.

WHY this module exists:
    The frontend needs structured music analysis data (key, tempo, chords,
    cadences, voice leading) to display in the Analysis tab.
    This module runs on the backend because music21 and pretty_midi are
    heavy Python libraries that can't run in the browser.

WHAT we build vs what we delegate:
    Symbolic harmony (key, chords, roman numerals, cadences, voice leading,
    phrases) is produced by the harmony engine seam
    (engines.harmony.music21_engine). Melody extraction is produced by the
    melody engine seam (engines.melody.skyline_engine). Tempo/time-signature
    come from pretty_midi (MIDI metadata); rhythm stats are computed here.

    This module is the pipeline facade: it routes through the configured
    engines, merges their normalized results, and exposes the same
    AnalysisResult contract the frontend, persistence, and evaluation
    consume. The legacy private helpers (_m21_*, _midi_melody, ...) are
    re-exported from their engine homes so existing callers and tests keep
    working unchanged.

Pipeline:
    MIDI → harmony engine → harmony features
         → melody engine → melody features
         → pretty_midi   → tempo / time-signature / rhythm
"""

from __future__ import annotations

import logging
import time as _time
from typing import NotRequired, TypedDict

import numpy as np
import pretty_midi

from engines.harmony.music21_engine import (  # noqa: F401  # legacy re-export
    _m21_cadences,
    _m21_chords,
    _m21_key,
    _m21_phrases,
)
from engines.melody.skyline_engine import (  # noqa: F401  # legacy re-export
    _midi_melody,
    _pick_melody_note,
)
from engines.registry import get_harmony_engine, get_melody_engine

logger = logging.getLogger("analyze")


# ── TypedDicts ──────────────────────────────────────────────────────────────


class KeyResult(TypedDict):
    tonic: str
    mode: str
    confidence: float


class TempoResult(TypedDict):
    bpm: float
    confidence: float | None
    source: str


class TimeSigResult(TypedDict):
    numerator: int
    denominator: int
    confidence: float | None
    source: str


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
    offbeat_onset_ratio: float | None
    rhythmic_density: float
    offbeat_onset_available: bool
    # Temporal features (Analysis V2)
    note_density_over_time: list[dict[str, float]]
    onset_density_over_time: list[dict[str, float]]
    rest_segments: list[dict[str, float]]


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
    key: KeyResult | None
    tempo: TempoResult | None
    time_signature: TimeSigResult | None
    chords: list[ChordResult]
    roman_numerals: list[RomanNumeralResult]
    cadences: list[CadenceResult]
    voice_leading: VoiceLeadingResult | None
    phrases: list[PhraseResult]
    rhythm: RhythmResult | None
    melody: MelodyResult | None
    harmonic_rhythm: NotRequired[list[dict[str, float]]]
    harmony_provenance: NotRequired[dict]
    melody_provenance: NotRequired[dict]
    pulse_provenance: NotRequired[dict | None]


# ── Harmony helpers (re-exported from the harmony engine) ───────────────────
# Legacy import surface: tests and callers import these from ``analyze``.
# The implementations now live in engines.harmony.music21_engine.

# ── Rhythm analysis (ISSUE-010) ────────────────────────────────────────────


def _midi_rhythm(midi_path: str, pulse: dict | None = None) -> RhythmResult | None:
    """Analyze rhythm using pretty_midi.

    Reports note density and average duration (honest, well-defined stats). The
    off-beat onset ratio is computed against a real beat grid supplied by the
    audio beat tracker via ``pulse``. A raw performance MIDI has no trustworthy
    beat grid, and pretty_midi injects a default 4/4 that is an assumption, not
    evidence — so without ``pulse`` the metric is reported as unavailable
    rather than fabricated.
    """
    try:
        pm = pretty_midi.PrettyMIDI(midi_path)
        duration = pm.get_end_time()
        if duration <= 0:
            return None

        total_notes = sum(len(inst.notes) for inst in pm.instruments if not inst.is_drum)
        if total_notes == 0:
            return None

        beats = pulse.get("beats") or [] if pulse else []

        if beats:
            beat_count = len(beats)
        else:
            tempos = pm.get_tempo_changes()[1]
            bpm = float(np.median(tempos)) if len(tempos) > 0 else 120.0
            beat_count = int(duration * bpm / 60.0)

        all_durations = []
        all_onsets = []
        for inst in pm.instruments:
            if inst.is_drum:
                continue
            for note in inst.notes:
                all_durations.append(note.end - note.start)
                all_onsets.append(note.start)
        avg_duration = float(np.mean(all_durations)) if all_durations else 0.0

        offbeat_onset_ratio: float | None = None
        if beats and all_onsets:
            offbeat_onset_ratio = _offbeat_onset_ratio(all_onsets, beats)

        # Temporal features (Analysis V2): windowed density and rest detection.
        # Prefer beat-relative aggregation when real beat evidence is available;
        # fall back to seconds-based windows otherwise.
        note_density = _compute_windowed_density(
            all_onsets, duration, window=2.0, step=0.5, beats=beats or None
        )
        onset_density = _compute_windowed_density(
            all_onsets, duration, window=1.0, step=0.25, beats=beats or None
        )
        rest_segments = _detect_rests(all_onsets, duration, min_gap=1.0)

        return RhythmResult(
            beat_count=beat_count,
            avg_note_duration=round(avg_duration, 3),
            offbeat_onset_ratio=offbeat_onset_ratio,
            rhythmic_density=round(total_notes / duration, 2),
            offbeat_onset_available=offbeat_onset_ratio is not None,
            note_density_over_time=note_density,
            onset_density_over_time=onset_density,
            rest_segments=rest_segments,
        )
    except Exception:
        return None


def _offbeat_onset_ratio(onsets: list[float], beats: list[float]) -> float:
    """Fraction of note onsets farther than ¼ of a median beat interval from the
    nearest detected beat.

    This is a distance-to-beat statistic only; it is NOT syncopation. True
    syncopation requires a metrical hierarchy (and usually accent/duration
    structure) that a beat grid alone does not establish, so this metric is
    labeled as an off-beat onset fraction, never presented as syncopation.
    """
    beats_sorted = np.asarray(sorted(beats), dtype=float)
    median_interval = float(np.median(np.diff(beats_sorted))) if len(beats_sorted) > 1 else 0.0
    if median_interval <= 0:
        return 0.0
    tolerance = median_interval / 4.0
    off_beat = 0
    for onset in onsets:
        idx = int(np.searchsorted(beats_sorted, onset))
        nearest = float("inf")
        if idx < len(beats_sorted):
            nearest = min(nearest, abs(beats_sorted[idx] - onset))
        if idx > 0:
            nearest = min(nearest, abs(beats_sorted[idx - 1] - onset))
        if nearest > tolerance:
            off_beat += 1
    return round(off_beat / len(onsets), 3) if onsets else 0.0


def _compute_windowed_density(
    onsets: list[float],
    duration: float,
    window: float = 2.0,
    step: float = 0.5,
    beats: list[float] | None = None,
) -> list[dict[str, float]]:
    """Compute event density over time using a sliding window.

    When ``beats`` is provided (real beat evidence from audio analysis),
    density is expressed as events per beat-relative unit rather than
    events per second. This produces musically meaningful comparisons
    across tempo changes. Falls back to seconds-based windows when no
    beat grid is available.

    Returns a list of {start, end, density} where density = events / unit.
    """
    if not onsets or duration <= 0:
        return []
    sorted_onsets = sorted(onsets)
    result: list[dict[str, float]] = []

    if beats and len(beats) >= 2:
        # Beat-relative: count onsets per beat window
        sorted_beats = sorted(beats)
        for i in range(len(sorted_beats)):
            beat_start = sorted_beats[i]
            beat_end = sorted_beats[min(i + int(window), len(sorted_beats) - 1)]
            if beat_end <= beat_start:
                continue
            count = sum(1 for o in sorted_onsets if beat_start <= o < beat_end)
            result.append({
                "start": round(beat_start, 2),
                "end": round(beat_end, 2),
                "density": round(count, 2),
            })
        return result

    # Seconds-based fallback
    t = 0.0
    while t < duration:
        window_end = min(t + window, duration)
        count = sum(1 for o in sorted_onsets if t <= o < window_end)
        actual_window = window_end - t
        result.append({
            "start": round(t, 2),
            "end": round(window_end, 2),
            "density": round(count / actual_window, 2) if actual_window > 0 else 0.0,
        })
        t += step
    return result


def _detect_rests(
    onsets: list[float],
    duration: float,
    min_gap: float = 1.0,
) -> list[dict[str, float]]:
    """Detect observed silence segments where no notes onset for min_gap seconds.

    A rest_segment is an OBSERVED GAP in note onsets — it does NOT imply a
    phrase boundary, musical rest notation, or intentional silence. It simply
    records that no note onset events were detected in this time window.

    Returns a list of {start, end, duration} for each rest segment.
    """
    if not onsets or duration <= 0:
        return []
    sorted_onsets = sorted(onsets)
    rests: list[dict[str, float]] = []

    # Check gap before first onset
    if sorted_onsets[0] >= min_gap:
        rests.append({
            "start": 0.0,
            "end": round(sorted_onsets[0], 2),
            "duration": round(sorted_onsets[0], 2),
        })

    # Check gaps between onsets
    for i in range(len(sorted_onsets) - 1):
        gap = sorted_onsets[i + 1] - sorted_onsets[i]
        if gap >= min_gap:
            rests.append({
                "start": round(sorted_onsets[i], 2),
                "end": round(sorted_onsets[i + 1], 2),
                "duration": round(gap, 2),
            })

    # Check gap after last onset
    if duration - sorted_onsets[-1] >= min_gap:
        rests.append({
            "start": round(sorted_onsets[-1], 2),
            "end": round(duration, 2),
            "duration": round(duration - sorted_onsets[-1], 2),
        })

    return rests


# ── Main entry point ────────────────────────────────────────────────────────


def analyze_midi(
    midi_path: str,
    pulse: dict | None = None,
    audio_bytes: bytes | None = None,
) -> AnalysisResult:
    """
    Full symbolic analysis of a MIDI file.

    Architecture: Symbolic harmony and melody analyses are routed through the
    configured engines (see engines.registry). Tempo/time-signature metadata
    and rhythm stats are read directly from the MIDI with pretty_midi. Engine
    provenance is attached so persistence can record how each fact was
    produced.

    ``pulse`` (optional) is audio-derived beat/downbeat evidence produced by the
    beat engine (see music_features.estimate_beats_with_engine). When supplied
    it overrides MIDI-metadata tempo (which for a transcription is only a
    placeholder) with measured evidence:
      ``{"bpm": float | None, "beats": [float], "downbeats": [float] | None,
          "provenance": {...}}``

    ``audio_bytes`` (optional) is WAV audio for audio-native engines (lv-chordia).
    When supplied, the harmony engine uses audio for chord recognition instead of
    MIDI-based analysis.

    Truthfulness rules for the audio path:
      - A degenerate beat estimate (bpm None / ≤ 0) produces NO tempo fact; it
        is never replaced by a default 120.
      - Time signature is never derived from beat/downbeat timestamps. A pulse
        model gives temporal pulse and bar starts, not the notated beat unit,
        so the audio path leaves time_signature None.
    The MIDI-metadata fallback (explicit tempo/meter from a real MIDI file) is
    used only when no pulse is supplied at all.
    """
    t0 = _time.perf_counter()

    with open(midi_path, "rb") as f:
        midi_bytes = f.read()

    pm = pretty_midi.PrettyMIDI(midi_path)

    has_pulse = pulse is not None
    pulse = pulse or {}
    pulse_bpm = pulse.get("bpm")

    result: AnalysisResult = {
        "key": None,
        "tempo": None,
        "time_signature": None,
        "chords": [],
        "roman_numerals": [],
        "cadences": [],
        "voice_leading": None,
        "phrases": [],
        "rhythm": None,
        "melody": None,
        "harmony_provenance": {},
        "melody_provenance": None,
        "pulse_provenance": pulse.get("provenance"),
    }

    # Tempo: audio-derived BPM is measured evidence; a degenerate estimate must
    # become no BPM evidence, never a default tempo. The MIDI-metadata fallback
    # (a real MIDI file's explicit tempo) applies only when no audio pulse is
    # supplied at all.
    if has_pulse:
        if pulse_bpm is not None and pulse_bpm > 0:
            result["tempo"] = TempoResult(
                bpm=round(float(pulse_bpm), 1),
                confidence=None,
                source="audio_beat_tracking",
            )
    else:
        try:
            _, tempos = pm.get_tempo_changes()
            if len(tempos) > 0:
                result["tempo"] = TempoResult(
                    bpm=round(float(np.median(tempos)), 1),
                    confidence=0.9,
                    source="midi_metadata",
                )
        except Exception:
            pass

    # Time signature: never inferred from beat/downbeat timestamps. A beat model
    # supplies temporal pulse and bar starts — not a notated beat unit — so the
    # audio path leaves time_signature None. Only a no-pulse analysis of a real
    # MIDI file falls back to its explicit metadata meter.
    if not has_pulse:
        try:
            ts_changes = pm.time_signature_changes
            if ts_changes:
                ts = ts_changes[0]
                result["time_signature"] = TimeSigResult(
                    numerator=int(ts.numerator),
                    denominator=int(ts.denominator),
                    confidence=0.9,
                    source="midi_metadata",
                )
        except Exception:
            pass

    # Harmony (via the configured harmony engine). On any failure the result
    # stays in its conservative "no reliable evidence" state rather than
    # fabricating a key/chords.
    try:
        harmony = get_harmony_engine().analyze(
            midi_bytes,
            tempo_bpm=result["tempo"]["bpm"] if result["tempo"] else None,
            audio_bytes=audio_bytes,
        )
        result["key"] = harmony.key
        result["chords"] = harmony.chords
        # Truthfulness invariant: no chord evidence → no Roman numerals
        if harmony.chords:
            result["roman_numerals"] = harmony.roman_numerals
        else:
            result["roman_numerals"] = []
        result["cadences"] = harmony.cadences
        result["voice_leading"] = harmony.voice_leading
        result["phrases"] = harmony.phrases
        result["harmony_provenance"] = {
            k: v.to_dict() for k, v in harmony.component_provenance.items()
        }

        # Harmonic rhythm: chord onset density over time (Analysis V2)
        if harmony.chords:
            chord_onsets = [c["start"] for c in harmony.chords if "start" in c]
            if chord_onsets:
                duration = pm.get_end_time()
                result["harmonic_rhythm"] = _compute_windowed_density(
                    chord_onsets, duration, window=4.0, step=1.0
                )
        
        # Theory interpretation: RN + function from chord timeline
        # Only when chord engine is trusted (lv-chordia)
        chord_provenance = result.get("harmony_provenance", {}).get("chords", {})
        chord_engine = chord_provenance.get("engine") if chord_provenance else None
        if chord_engine == "lv-chordia" and harmony.chords:
            try:
                from engines.registry import get_theory_engine
                theory = get_theory_engine().analyze(
                    harmony.chords,
                    global_key=(
                        result["key"].get("tonic") + " " + result["key"].get("mode", "major")
                        if result.get("key") else None
                    ),
                )
                # Convert TheoryResult to dicts for persistence
                result["roman_numerals_theory"] = [
                    {
                        "numeral": rn.numeral,
                        "degree": rn.degree,
                        "quality": rn.quality,
                        "inversion": rn.inversion,
                        "is_secondary": rn.is_secondary,
                        "secondary_target": rn.secondary_target,
                        "start": rn.start_seconds,
                        "end": rn.end_seconds,
                        "key_context": rn.key_context,
                    }
                    for rn in theory.roman_numerals
                ]
                result["harmonic_functions"] = [
                    {
                        "function": f.function,
                        "numeral": f.roman_numeral,
                        "start": f.start_seconds,
                        "end": f.end_seconds,
                        "key_context": f.key_context,
                    }
                    for f in theory.harmonic_functions
                ]
                result["cadences_theory"] = [
                    {
                        "type": c.type,
                        "chords": c.chords,
                        "start": c.start_seconds,
                        "end": c.end_seconds,
                        "key_context": c.key_context,
                        "confidence": c.confidence,
                    }
                    for c in theory.cadences
                ]
                result["theory_provenance"] = theory.provenance.to_dict()
            except Exception:
                logger.exception("theory engine failed")
    except Exception:
        logger.exception("harmony engine failed")

    # Melody (pretty_midi + skyline heuristic via the melody engine)
    try:
        melody = get_melody_engine().analyze(midi_bytes)
        result["melody"] = melody.melody
        result["melody_provenance"] = melody.provenance.to_dict()
    except Exception:
        logger.exception("melody engine failed")

    # Rhythm — operates directly on the saved performance MIDI and remains
    # useful even when symbolic parsing fails.
    result["rhythm"] = _midi_rhythm(midi_path, pulse)

    total_ms = round((_time.perf_counter() - t0) * 1000)
    logger.info("analyze_total", extra={"step": "total", "step_ms": total_ms})
    return result
