"""Persisted contract for the experimental production/spatial lens.

The report carries literal window measurements and method-qualified adjacent-window
relations only. It intentionally does not translate those measurements into semantic
production adjectives, arrangement claims, or cross-recording scores.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

REPORT_SCHEMA_VERSION = 1
METHOD_ID = "pyloudnorm_librosa_mid_side_v1"
ProductionSpatialRelationKind = Literal[
    "loudness_change",
    "mid_side_change",
    "spectral_change",
    "transient_change",
]


class ProductionSpatialMethod(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Literal["pyloudnorm_librosa_mid_side_v1"] = METHOD_ID
    label: str = "BS.1770 loudness + mid/side + librosa window comparison"
    pyloudnorm_version: str
    librosa_version: str
    parameters: dict[str, float | int | str]


class ProductionSpatialWindow(BaseModel):
    model_config = ConfigDict(frozen=True)

    start_seconds: float
    end_seconds: float
    loudness_lufs: float | None
    side_energy_fraction: float | None
    spectral_centroid_hz: float
    onset_strength_mean: float


class ProductionSpatialRelation(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: ProductionSpatialRelationKind
    label: str
    method: str
    unit: str
    delta: float
    start_seconds: float
    end_seconds: float
    from_start_seconds: float
    from_end_seconds: float
    to_start_seconds: float
    to_end_seconds: float


class ProductionSpatialReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = REPORT_SCHEMA_VERSION
    report_type: Literal["production_spatial"] = "production_spatial"
    experimental: Literal[True] = True
    source_version_id: UUID
    duration_seconds: float
    channel_count: int
    method: ProductionSpatialMethod
    windows: list[ProductionSpatialWindow]
    relations: list[ProductionSpatialRelation]
    interpretation: str = (
        "Each relation compares adjacent fixed windows under the named measurement method. "
        "Values are literal measurements, not semantic production labels or importance scores."
    )
    limitations: list[str] = Field(
        default_factory=lambda: [
            (
                "Relations are local adjacent-window comparisons and do not identify "
                "sections or causes."
            ),
            (
                "Loudness is BS.1770 integrated loudness measured independently inside "
                "each fixed window."
            ),
            "Mid/side evidence is emitted only for exactly two-channel source audio.",
            "Spectral centroid and onset strength are method-specific librosa measurements.",
        ]
    )
