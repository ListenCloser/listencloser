"""Melody feature provider using music21/jSymbolic.

Provides canonical melody features using established OSS implementations
instead of custom heuristics.

Uses music21.features.jSymbolic for:
- StepwiseMotionFeature: fraction of intervals that are seconds
- DirectionOfMotionFeature: fraction of rising intervals
- AverageMelodicIntervalFeature: average interval in semitones
- MostCommonMelodicIntervalFeature: most frequent interval
- MelodicIntervalHistogramFeature: interval distribution
- RepeatedNotesFeature: fraction of repeated notes
- ChromaticMotionFeature: fraction of semitone intervals
- NoteDensityFeature: notes per second
- AverageNoteDurationFeature: average duration in seconds

Uses music21.interval for:
- Pitch name conversion
- Interval name conversion

Trivial projections (kept as custom):
- Highest/lowest melody note (max/min over trusted notes)
- Range in semitones (high - low)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from music21 import features, interval, note, stream

logger = logging.getLogger(__name__)


@dataclass
class MelodyNoteInput:
    """Input note for feature extraction."""

    pitch: int  # MIDI pitch
    start_seconds: float
    end_seconds: float
    velocity: int = 80


@dataclass
class MelodyFeatures:
    """Canonical melody features from music21/jSymbolic."""

    # Trivial projections (custom, acceptable)
    highest_pitch: int
    lowest_pitch: int
    range_semitones: int
    highest_pitch_name: str
    lowest_pitch_name: str

    # jSymbolic features
    stepwise_motion: float  # Fraction of intervals that are seconds
    direction_of_motion: float  # Fraction of rising intervals
    average_melodic_interval: float  # Average interval in semitones
    most_common_melodic_interval: int  # Most frequent interval in semitones
    repeated_notes: float  # Fraction of repeated notes
    chromatic_motion: float  # Fraction of semitone intervals
    note_density: float  # Notes per second
    average_note_duration: float  # Average duration in seconds

    # Interval histogram (first 13 bins: 0-12 semitones)
    interval_histogram: list[float]

    # Metadata
    note_count: int
    unique_pitch_classes: int


def _pitch_name(midi_pitch: int) -> str:
    """Convert MIDI pitch to note name using music21."""
    n = note.Note()
    n.pitch.midi = midi_pitch
    return n.nameWithOctave


def _interval_name(semitones: int) -> str:
    """Convert interval in semitones to musical name using music21."""
    if semitones == 0:
        return "unison"
    i = interval.Interval(semitones)
    return i.niceName


def extract_melody_features(notes: list[MelodyNoteInput]) -> MelodyFeatures | None:
    """Extract canonical melody features using music21/jSymbolic.

    Args:
        notes: Melody notes sorted by start time.

    Returns:
        MelodyFeatures or None if too few notes.
    """
    if len(notes) < 3:
        return None

    # Convert to music21 stream
    melody_stream = stream.Stream()
    for n in notes:
        m21_note = note.Note()
        m21_note.pitch.midi = n.pitch
        m21_note.quarterLength = (n.end_seconds - n.start_seconds) * 4  # Convert to quarter lengths
        melody_stream.append(m21_note)

    # Trivial projections
    pitches = [n.pitch for n in notes]
    highest = max(pitches)
    lowest = min(pitches)

    # jSymbolic features
    try:
        stepwise = features.jSymbolic.StepwiseMotionFeature(melody_stream).extract().vector[0]
    except Exception:
        stepwise = 0.0

    try:
        direction = features.jSymbolic.DirectionOfMotionFeature(melody_stream).extract().vector[0]
    except Exception:
        direction = 0.5

    try:
        avg_interval = (
            features.jSymbolic.AverageMelodicIntervalFeature(melody_stream).extract().vector[0]
        )
    except Exception:
        avg_interval = 0.0

    try:
        most_common = int(
            features.jSymbolic.MostCommonMelodicIntervalFeature(melody_stream).extract().vector[0]
        )
    except Exception:
        most_common = 0

    try:
        repeated = features.jSymbolic.RepeatedNotesFeature(melody_stream).extract().vector[0]
    except Exception:
        repeated = 0.0

    try:
        chromatic = features.jSymbolic.ChromaticMotionFeature(melody_stream).extract().vector[0]
    except Exception:
        chromatic = 0.0

    try:
        density = features.jSymbolic.NoteDensityFeature(melody_stream).extract().vector[0]
    except Exception:
        density = 0.0

    try:
        avg_duration = (
            features.jSymbolic.AverageNoteDurationFeature(melody_stream).extract().vector[0]
        )
    except Exception:
        avg_duration = 0.0

    # Interval histogram
    try:
        histogram = (
            features.jSymbolic.MelodicIntervalHistogramFeature(melody_stream)
            .extract()
            .vector.tolist()
        )
        # Pad or truncate to 13 bins (0-12 semitones)
        if len(histogram) < 13:
            histogram.extend([0.0] * (13 - len(histogram)))
        else:
            histogram = histogram[:13]
    except Exception:
        histogram = [0.0] * 13

    return MelodyFeatures(
        highest_pitch=highest,
        lowest_pitch=lowest,
        range_semitones=highest - lowest,
        highest_pitch_name=_pitch_name(highest),
        lowest_pitch_name=_pitch_name(lowest),
        stepwise_motion=round(float(stepwise), 3),
        direction_of_motion=round(float(direction), 3),
        average_melodic_interval=round(float(avg_interval), 2),
        most_common_melodic_interval=most_common,
        repeated_notes=round(float(repeated), 3),
        chromatic_motion=round(float(chromatic), 3),
        note_density=round(float(density), 2),
        average_note_duration=round(float(avg_duration), 3),
        interval_histogram=[round(float(x), 3) for x in histogram],
        note_count=len(notes),
        unique_pitch_classes=len({p % 12 for p in pitches}),
    )
