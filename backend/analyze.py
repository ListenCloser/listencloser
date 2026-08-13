"""
MIDI harmonic analysis pipeline.

WHY this module exists:
    The frontend needs structured music analysis data (key, tempo, chords,
    cadences, modulations, voice leading) to display in the Analysis tab.
    This module runs on the backend because music21 and pretty_midi are
    heavy Python libraries that can't run in the browser.

WHAT we build vs what we delegate:
    Symbolic harmony (key, chords, roman numerals, cadences, voice leading,
    modulations, phrases) is produced by the harmony engine seam
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
    _detect_modulations,
    _key_from_pc_vector,
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
    key: KeyResult | None
    tempo: TempoResult | None
    time_signature: TimeSigResult | None
    chords: list[ChordResult]
    roman_numerals: list[RomanNumeralResult]
    cadences: list[CadenceResult]
    modulations: list[ModulationResult]
    voice_leading: VoiceLeadingResult | None
    phrases: list[PhraseResult]
    rhythm: RhythmResult | None
    melody: MelodyResult | None
    harmony_provenance: NotRequired[dict]
    melody_provenance: NotRequired[dict]


# ── Harmony helpers (re-exported from the harmony engine) ───────────────────
# Legacy import surface: tests and callers import these from ``analyze``.
# The implementations now live in engines.harmony.music21_engine.

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


# ── Main entry point ────────────────────────────────────────────────────────


def analyze_midi(midi_path: str) -> AnalysisResult:
    """
    Full symbolic analysis of a MIDI file.

    Architecture: Symbolic harmony and melody analyses are routed through the
    configured engines (see engines.registry). Tempo/time-signature metadata
    and rhythm stats are read directly from the MIDI with pretty_midi. Engine
    provenance is attached so persistence can record how each fact was
    produced.

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

    result: AnalysisResult = {
        "key": None,
        "tempo": None,
        "time_signature": None,
        "chords": [],
        "roman_numerals": [],
        "cadences": [],
        "modulations": [],
        "voice_leading": None,
        "phrases": [],
        "rhythm": None,
        "melody": None,
        "harmony_provenance": {},
        "melody_provenance": None,
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
        ts_changes = pm.time_signature_changes
        if ts_changes:
            ts = ts_changes[0]
            result["time_signature"] = TimeSigResult(
                numerator=int(ts.numerator), denominator=int(ts.denominator), confidence=0.9
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
        result["roman_numerals"] = harmony.roman_numerals
        result["cadences"] = harmony.cadences
        result["modulations"] = harmony.modulations
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
    result["rhythm"] = _midi_rhythm(midi_path)

    total_ms = round((_time.perf_counter() - t0) * 1000)
    logger.info("analyze_total", extra={"step": "total", "step_ms": total_ms})
    return result
