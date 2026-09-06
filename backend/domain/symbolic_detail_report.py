"""Persisted contract for the experimental symbolic-detail analysis.

The report contains source-MIDI note-event measurements plus explicitly
method-qualified summaries. It is not a canonical melody, texture, or
voice-leading interpretation and is never written into the normal Insight
truth stream.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

REPORT_SCHEMA_VERSION = 1
METHOD_ID = "partitura_performance_midi_v1"


class SymbolicDetailMethod(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Literal["partitura_performance_midi_v1"] = METHOD_ID
    label: str = "Partitura performance-MIDI event measurements"
    partitura_version: str
    music21_version: str
    parameters: dict[str, float | int | str | bool]


class RegisterDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    low_midi: int
    high_midi: int
    low_name: str
    high_name: str
    median_midi: float
    span_semitones: int


class ContourDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    basis: Literal["onset_pitch_centroid"] = "onset_pitch_centroid"
    onset_count: int
    first_centroid_midi: float
    last_centroid_midi: float
    net_change_semitones: float
    slope_semitones_per_quarter: float


class IntervalMotionDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    basis: Literal["within_midi_stream_onset_centroid"] = "within_midi_stream_onset_centroid"
    interval_count: int
    mean_absolute_semitones: float
    median_absolute_semitones: float
    repeat_fraction: float
    step_fraction: float
    leap_fraction: float
    ascending_fraction: float
    descending_fraction: float


class DensityWindow(BaseModel):
    model_config = ConfigDict(frozen=True)

    start_quarter: float
    end_quarter: float
    onset_count: int
    note_count: int


class DensityDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    note_count: int
    duration_quarters: float
    notes_per_quarter: float
    window_quarters: float
    windows: list[DensityWindow]


class TextureDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    midi_stream_count: int
    peak_simultaneous_notes: int
    mean_simultaneous_notes: float
    polyphonic_time_fraction: float


class VoiceMotionDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    basis: Literal["midi_stream_shared_onsets"] = "midi_stream_shared_onsets"
    status: Literal["supported", "unavailable"]
    analyzable_transition_count: int = 0
    similar_direction_fraction: float | None = None
    contrary_direction_fraction: float | None = None
    oblique_like_fraction: float | None = None
    reason: str | None = None


class SymbolicDetailReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = REPORT_SCHEMA_VERSION
    report_type: Literal["symbolic_detail"] = "symbolic_detail"
    experimental: Literal[True] = True
    source_version_id: UUID
    source_artifact_kind: Literal["midi_performance", "midi_corrected"]
    method: SymbolicDetailMethod
    register: RegisterDetail
    contour: ContourDetail
    interval_motion: IntervalMotionDetail
    density: DensityDetail
    texture: TextureDetail
    voice_motion: VoiceMotionDetail
    interpretation: str = (
        "Literal source-MIDI note measurements plus method-specific summaries. "
        "Contour uses onset pitch centroids; motion groups notes by MIDI track/channel "
        "stream and is not canonical melody, counterpoint, or voice-leading truth."
    )
    # Limitations describe method boundaries, not correctness-confidence scores.
    limitations: list[str] = Field(
        default_factory=lambda: [
            "MIDI track/channel streams are recording structure, not inferred musical voices.",
            "Onset pitch centroid is a polyphonic contour proxy, not a detected melody line.",
            "Step/leap fractions summarize adjacent stream onset centroids, not motifs.",
            (
                "Density and texture are symbolic note-event measurements, not audio "
                "loudness or timbre."
            ),
        ],
    )
