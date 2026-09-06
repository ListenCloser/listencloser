"""Experimental symbolic-detail measurements over an exact MIDI Version.

Partitura supplies score-MIDI parsing and its explicitly inferred voice/staff
organization. music21 is used only for deterministic pitch spelling in the
register display. No harmony, melody, counterpoint, or form interpretation is
promoted by this module.
"""

from __future__ import annotations

import math
import os
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from uuid import UUID

import numpy as np
import partitura
from music21 import pitch as m21_pitch

from domain.symbolic_detail_report import (
    METHOD_ID,
    ContourDetail,
    DensityDetail,
    DensityWindow,
    IntervalMotionDetail,
    RegisterDetail,
    SymbolicDetailMethod,
    SymbolicDetailReport,
    TextureDetail,
    VoiceMotionDetail,
)

DEFAULT_DENSITY_WINDOW_QUARTERS = 4.0
MAX_DENSITY_WINDOWS = 32
_EPSILON = 1e-7


@dataclass(frozen=True)
class _NoteRow:
    onset: float
    duration: float
    pitch: int
    part: int
    voice: int

    @property
    def end(self) -> float:
        return self.onset + self.duration


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def _score_parts(score_like) -> list:
    parts = getattr(score_like, "parts", None)
    if parts is not None:
        return list(parts)
    if isinstance(score_like, list | tuple):
        flattened: list = []
        for item in score_like:
            flattened.extend(_score_parts(item))
        return flattened
    return [score_like]


def _note_rows_from_midi(midi_bytes: bytes) -> list[_NoteRow]:
    if not midi_bytes:
        raise ValueError("symbolic_detail requires non-empty MIDI bytes")

    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as handle:
        handle.write(midi_bytes)
        midi_path = handle.name
    try:
        score = partitura.load_score_midi(midi_path)
    finally:
        os.unlink(midi_path)

    rows: list[_NoteRow] = []
    for part_index, part in enumerate(_score_parts(score)):
        if not hasattr(part, "note_array"):
            continue
        note_array = part.note_array(include_staff=True)
        fields = set(note_array.dtype.names or ())
        required = {"onset_quarter", "duration_quarter", "pitch"}
        if not required.issubset(fields):
            raise ValueError("Partitura MIDI note array lacks quarter-note coordinates")
        for item in note_array:
            duration = max(0.0, float(item["duration_quarter"]))
            voice = int(item["voice"]) if "voice" in fields else 0
            rows.append(
                _NoteRow(
                    onset=max(0.0, float(item["onset_quarter"])),
                    duration=duration,
                    pitch=int(item["pitch"]),
                    part=part_index,
                    voice=voice,
                )
            )

    rows.sort(key=lambda item: (item.onset, item.part, item.voice, item.pitch, item.duration))
    if not rows:
        raise ValueError("symbolic_detail requires at least one pitched MIDI note")
    return rows


def _centroids(rows: list[_NoteRow]) -> dict[float, float]:
    pitches: dict[float, list[int]] = defaultdict(list)
    for row in rows:
        pitches[round(row.onset, 6)].append(row.pitch)
    return {onset: float(np.mean(values)) for onset, values in sorted(pitches.items())}


def _voice_centroids(rows: list[_NoteRow]) -> dict[tuple[int, int], dict[float, float]]:
    grouped: dict[tuple[int, int], list[_NoteRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.part, row.voice)].append(row)
    return {identity: _centroids(notes) for identity, notes in grouped.items()}


def _register(rows: list[_NoteRow]) -> RegisterDetail:
    pitches = np.asarray([row.pitch for row in rows], dtype=float)
    low = int(np.min(pitches))
    high = int(np.max(pitches))
    return RegisterDetail(
        low_midi=low,
        high_midi=high,
        low_name=m21_pitch.Pitch(low).nameWithOctave,
        high_name=m21_pitch.Pitch(high).nameWithOctave,
        median_midi=round(float(np.median(pitches)), 3),
        span_semitones=high - low,
    )


def _contour(rows: list[_NoteRow]) -> ContourDetail:
    centroids = _centroids(rows)
    onsets = np.asarray(list(centroids), dtype=float)
    values = np.asarray(list(centroids.values()), dtype=float)
    slope = float(np.polyfit(onsets, values, 1)[0]) if len(onsets) > 1 else 0.0
    return ContourDetail(
        onset_count=len(onsets),
        first_centroid_midi=round(float(values[0]), 3),
        last_centroid_midi=round(float(values[-1]), 3),
        net_change_semitones=round(float(values[-1] - values[0]), 3),
        slope_semitones_per_quarter=round(slope, 4),
    )


def _interval_motion(rows: list[_NoteRow]) -> IntervalMotionDetail:
    deltas: list[float] = []
    for centroids in _voice_centroids(rows).values():
        values = list(centroids.values())
        deltas.extend(float(right - left) for left, right in zip(values, values[1:], strict=False))

    if not deltas:
        return IntervalMotionDetail(
            interval_count=0,
            mean_absolute_semitones=0.0,
            median_absolute_semitones=0.0,
            repeat_fraction=0.0,
            step_fraction=0.0,
            leap_fraction=0.0,
            ascending_fraction=0.0,
            descending_fraction=0.0,
        )

    values = np.asarray(deltas, dtype=float)
    absolute = np.abs(values)
    count = len(values)
    repeat = absolute <= _EPSILON
    step = (absolute > _EPSILON) & (absolute <= 2.0 + _EPSILON)
    leap = absolute > 2.0 + _EPSILON
    return IntervalMotionDetail(
        interval_count=count,
        mean_absolute_semitones=round(float(np.mean(absolute)), 3),
        median_absolute_semitones=round(float(np.median(absolute)), 3),
        repeat_fraction=round(float(np.sum(repeat) / count), 4),
        step_fraction=round(float(np.sum(step) / count), 4),
        leap_fraction=round(float(np.sum(leap) / count), 4),
        ascending_fraction=round(float(np.sum(values > _EPSILON) / count), 4),
        descending_fraction=round(float(np.sum(values < -_EPSILON) / count), 4),
    )


def _density(rows: list[_NoteRow]) -> DensityDetail:
    duration = max(row.end for row in rows)
    if duration <= 0:
        duration = max(row.onset for row in rows) or 1.0
    minimum_window = DEFAULT_DENSITY_WINDOW_QUARTERS
    multiplier = max(1, math.ceil(duration / (minimum_window * MAX_DENSITY_WINDOWS)))
    window = minimum_window * multiplier
    window_count = max(1, math.ceil(duration / window))
    windows: list[DensityWindow] = []
    for index in range(window_count):
        start = index * window
        end = min(duration, (index + 1) * window)
        notes = [
            row
            for row in rows
            if start <= row.onset < end
            or (index == window_count - 1 and math.isclose(row.onset, end))
        ]
        onset_count = len({round(row.onset, 6) for row in notes})
        windows.append(
            DensityWindow(
                start_quarter=round(start, 3),
                end_quarter=round(end, 3),
                onset_count=onset_count,
                note_count=len(notes),
            )
        )
    return DensityDetail(
        note_count=len(rows),
        duration_quarters=round(duration, 3),
        notes_per_quarter=round(len(rows) / duration, 4),
        window_quarters=window,
        windows=windows,
    )


def _texture(rows: list[_NoteRow]) -> TextureDetail:
    duration = max(row.end for row in rows)
    changes: dict[float, int] = defaultdict(int)
    for row in rows:
        if row.duration <= 0:
            continue
        changes[round(row.onset, 6)] += 1
        changes[round(row.end, 6)] -= 1

    active = 0
    previous = 0.0
    weighted = 0.0
    polyphonic = 0.0
    peak = 0
    for point in sorted(changes):
        span = max(0.0, point - previous)
        weighted += active * span
        if active >= 2:
            polyphonic += span
        active += changes[point]
        peak = max(peak, active)
        previous = point

    identities = {(row.part, row.voice) for row in rows}
    return TextureDetail(
        inferred_voice_count=len(identities),
        peak_simultaneous_notes=peak,
        mean_simultaneous_notes=round(weighted / duration, 4) if duration > 0 else 0.0,
        polyphonic_time_fraction=round(polyphonic / duration, 4) if duration > 0 else 0.0,
    )


def _voice_motion(rows: list[_NoteRow]) -> VoiceMotionDetail:
    voices = _voice_centroids(rows)
    if len(voices) < 2:
        return VoiceMotionDetail(
            status="unavailable",
            reason="Fewer than two Partitura-inferred voices are present in this MIDI.",
        )

    all_onsets = sorted({onset for values in voices.values() for onset in values})
    similar = contrary = oblique = total = 0
    for left, right in zip(all_onsets, all_onsets[1:], strict=False):
        deltas = [
            values[right] - values[left]
            for values in voices.values()
            if left in values and right in values
        ]
        if len(deltas) < 2:
            continue
        signs = [0 if abs(delta) <= _EPSILON else (1 if delta > 0 else -1) for delta in deltas]
        moving = {sign for sign in signs if sign != 0}
        if not moving:
            continue
        total += 1
        if len(moving) > 1:
            contrary += 1
        elif 0 in signs:
            oblique += 1
        elif len(signs) >= 2:
            similar += 1

    if total == 0:
        return VoiceMotionDetail(
            status="unavailable",
            reason=(
                "Inferred voices do not share enough consecutive onset coordinates for "
                "motion comparison."
            ),
        )
    return VoiceMotionDetail(
        status="supported",
        analyzable_transition_count=total,
        similar_direction_fraction=round(similar / total, 4),
        contrary_direction_fraction=round(contrary / total, 4),
        oblique_like_fraction=round(oblique / total, 4),
    )


def build_symbolic_detail(
    midi_bytes: bytes,
    *,
    source_version_id: UUID,
    source_artifact_kind: str,
) -> SymbolicDetailReport:
    if source_artifact_kind not in {"midi_performance", "midi_corrected"}:
        raise ValueError("symbolic_detail requires a performance or corrected MIDI Version")
    rows = _note_rows_from_midi(midi_bytes)
    return SymbolicDetailReport(
        source_version_id=source_version_id,
        source_artifact_kind=source_artifact_kind,
        method=SymbolicDetailMethod(
            partitura_version=_package_version("partitura"),
            music21_version=_package_version("music21"),
            parameters={
                "coordinate_unit": "quarter_note",
                "density_window_quarters": DEFAULT_DENSITY_WINDOW_QUARTERS,
                "max_density_windows": MAX_DENSITY_WINDOWS,
                "voice_source": "partitura_load_score_midi_inference",
                "contour_basis": "onset_pitch_centroid",
            },
        ),
        register=_register(rows),
        contour=_contour(rows),
        interval_motion=_interval_motion(rows),
        density=_density(rows),
        texture=_texture(rows),
        voice_motion=_voice_motion(rows),
    )


__all__ = ["METHOD_ID", "build_symbolic_detail"]
