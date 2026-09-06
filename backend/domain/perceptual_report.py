"""Lightweight persisted contract for measured perceptual evidence.

This module is intentionally safe to import from the FastAPI/query process.  It
owns only the serialized report schema, provenance fields, and stable constants;
worker-side DSP extraction remains in :mod:`perceptual_evidence`.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CANONICAL_SAMPLE_RATE = 22_050
DEFAULT_N_FFT = 2_048
DEFAULT_HOP_LENGTH = 512
PREPROCESSING_VERSION = "perceptual_mono_22050_pcm16_v1"
REPORT_SCHEMA_VERSION = 1

FeatureName = Literal[
    "rms",
    "spectral_centroid",
    "relative_band_energy",
    "onset_strength",
]


class MeasuredFeatureSeries(BaseModel):
    """A literal time-localized descriptor before source-lineage enrichment."""

    model_config = ConfigDict(frozen=True)

    feature: FeatureName
    frame_times_seconds: list[float]
    values: list[float] | list[list[float]]
    unit: str | None
    normalization: str
    channel_mode: Literal["mono"] = "mono"
    parameters: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class PerceptualProvenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    engine: Literal["librosa"] = "librosa"
    engine_version: str
    preprocessing_version: str = PREPROCESSING_VERSION
    parameters: dict[str, Any] = Field(default_factory=dict)


class PerceptualSeriesEvidence(MeasuredFeatureSeries):
    """Production evidence series with exact source lineage and applicability."""

    sample_rate: Literal[22050] = CANONICAL_SAMPLE_RATE
    source_version_id: UUID
    provenance: PerceptualProvenance
    validated_scope: Literal["within_work_same_preprocessing"] = "within_work_same_preprocessing"
    limitations: list[str] = Field(default_factory=list)


class PerceptualEvidenceReport(BaseModel):
    """Serializable evidence payload persisted as an immutable analysis report."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = REPORT_SCHEMA_VERSION
    report_type: Literal["perceptual_series"] = "perceptual_series"
    source_version_id: UUID
    sample_rate: Literal[22050] = CANONICAL_SAMPLE_RATE
    channel_mode: Literal["mono"] = "mono"
    preprocessing_version: str = PREPROCESSING_VERSION
    duration_seconds: float
    series: dict[str, PerceptualSeriesEvidence]
    withheld_semantics: list[str] = Field(
        default_factory=lambda: [
            "bright/dark/warm/full/thin",
            "energetic/intense/exciting",
            "drop/buildup/section labels",
            "instrument/source identity",
            "calibrated loudness from RMS",
            "cross-song ranking or population norms",
        ]
    )
