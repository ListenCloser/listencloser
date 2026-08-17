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
    harmony_provenance: NotRequired[dict]
    melody_provenance: NotRequired[dict]
    pulse_provenance: NotRequired[dict | None]


# ── Harmony helpers (re-exported from the harmony engine) ───────────────────
# Legacy import surface: tests and callers import these from ``analyze``.
# The implementations now live in engines.harmony.music21_engine.

# ── Rhythm analysis (ISSUE-010) ────────────────────────────────────────────


def _midi_rhythm(midi_path: str, pulse: dict | None = None) -> RhythmResult | None:
    """Analyze rhythm using pretty_midi.

    Reports note density and average duration (honest, well-defined stats).
    Syncopation is computed ONLY against a real beat/downbeat grid supplied by
    the audio beat tracker via ``pulse``. A raw performance MIDI has no
    trustworthy metrical hierarchy, and pretty_midi injects a default 4/4 that
    is an assumption, not evidence — so without ``pulse``, syncopation is
    reported as unavailable rather than fabricated.
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
        downbeats = pulse.get("downbeats") if pulse else None

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

        syncopation_ratio: float | None = None
        syncopation_available = False
        if downbeats and beats and all_onsets:
            syncopation_available = True
            syncopation_ratio = _syncopation_ratio(all_onsets, beats, downbeats)

        return RhythmResult(
            beat_count=beat_count,
            avg_note_duration=round(avg_duration, 3),
            syncopation_ratio=syncopation_ratio,
            rhythmic_density=round(total_notes / duration, 2),
            syncopation_available=syncopation_available,
        )
    except Exception:
        return None


def _syncopation_ratio(onsets: list[float], beats: list[float], downbeats: list[float]) -> float:
    """Fraction of note onsets that land off the detected beat grid.

    A note onset is "on the grid" when it falls within a tolerance window of a
    detected beat (a quarter of the median inter-beat interval). Onsets that
    land further from the beat — the off-beat fraction — are the syncopation
    signal. This is a defensible, well-defined statistic computed only from
    real beat/downbeat evidence; it is not a musical-judgment claim.
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


# ── Main entry point ────────────────────────────────────────────────────────


def analyze_midi(midi_path: str, pulse: dict | None = None) -> AnalysisResult:
    """
    Full symbolic analysis of a MIDI file.

    Architecture: Symbolic harmony and melody analyses are routed through the
    configured engines (see engines.registry). Tempo/time-signature metadata
    and rhythm stats are read directly from the MIDI with pretty_midi. Engine
    provenance is attached so persistence can record how each fact was
    produced.

    ``pulse`` (optional) is audio-derived beat/downbeat evidence produced by the
    beat engine (see music_features.estimate_beats_with_engine). When supplied
    it overrides MIDI-metadata tempo/meter (which for a transcription is only a
    placeholder) with measured evidence:
      ``{"bpm": float, "beats": [float], "downbeats": [float] | None,
          "provenance": {...}}``
    Downbeat-dependent facts (meter, syncopation) are only produced when real
    downbeats exist; they are never fabricated from a beat-only model.

    Intentional behavior change vs. the pre-engine implementation (2026,
    engine-seam refactor): a harmony-engine failure no longer aborts the whole
    analysis. This module swallows it, keeps harmony in its conservative
    no-evidence state, and still produces rhythm/melody. Covered by
    TestIntentionalBehaviorChange.
    """
    t0 = _time.perf_counter()

    with open(midi_path, "rb") as f:
        midi_bytes = f.read()

    pm = pretty_midi.PrettyMIDI(midi_path)

    pulse = pulse or {}
    pulse_bpm = float(pulse.get("bpm") or 0.0)
    pulse_downbeats = pulse.get("downbeats") if pulse else None

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

    # Tempo: audio-derived BPM is measured evidence; MIDI metadata is used as a
    # fallback when no pulse evidence exists.
    if pulse_bpm > 0:
        result["tempo"] = TempoResult(
            bpm=round(pulse_bpm, 1),
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

    # Time signature: only from a real downbeat grid. Without downbeat evidence
    # a default 4/4 is never surfaced as a detected fact.
    if pulse_downbeats:
        derived = _meter_from_downbeats(pulse_downbeats, pulse.get("beats"))
        if derived:
            result["time_signature"] = TimeSigResult(
                numerator=derived[0],
                denominator=derived[1],
                confidence=None,
                source="audio_beat_tracking",
            )
    else:
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

    # Harmony (music21 via the harmony engine). On any failure the result stays
    # in its conservative "no reliable evidence" state rather than fabricating
    # a key/chords.
    try:
        harmony = get_harmony_engine().analyze(
            midi_bytes,
            tempo_bpm=result["tempo"]["bpm"] if result["tempo"] else None,
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


def _meter_from_downbeats(
    downbeats: list[float], beats: list[float] | None
) -> tuple[int, int] | None:
    """Infer a simple meter (numerator, denominator) from a real downbeat grid.

    Beats-per-bar is the modal number of detected beats between consecutive
    downbeats. The denominator is fixed at 4 (the beat grid's nominal
    quarter-note pulse); when the grid is too sparse or inconsistent to support
    a clean meter, None is returned rather than guessing.
    """
    if not downbeats or len(downbeats) < 2:
        return None
    beats_sorted = sorted(float(b) for b in beats or [])
    downbeats_sorted = sorted(float(d) for d in downbeats)
    if not beats_sorted:
        return None

    beat_interval = float(np.median(np.diff(beats_sorted))) if len(beats_sorted) > 1 else 0.0
    if beat_interval <= 0:
        return None

    beats_per_bar: list[int] = []
    for i in range(1, len(downbeats_sorted)):
        gap = downbeats_sorted[i] - downbeats_sorted[i - 1]
        if gap <= 0:
            continue
        count = round(gap / beat_interval)
        if 1 <= count <= 16:
            beats_per_bar.append(count)
    if not beats_per_bar:
        return None

    modal = max(set(beats_per_bar), key=beats_per_bar.count)
    consistent = beats_per_bar.count(modal) >= max(1, len(beats_per_bar) * 0.6)
    if not consistent or modal in (0, 1):
        return None
    return (modal, 4)
