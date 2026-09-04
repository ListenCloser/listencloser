"""DSP-free wire contract for experimental Similar moments.

Keep these Pydantic models importable by the HTTP/OpenAPI layer without pulling
NumPy or perceptual-analysis runtime dependencies into the API process.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SIMILAR_MOMENTS_METHOD_ID = "perceptual_descriptor_shape"
SIMILAR_MOMENTS_METHOD_VERSION = "1.0"
MAX_MATCHES = 5


class SimilarMomentMatch(BaseModel):
    """One inspectable candidate under the declared descriptor-shape method."""

    model_config = ConfigDict(frozen=True)

    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    distance: float = Field(ge=0)
    component_distances: dict[str, float]


class SimilarMomentsMethod(BaseModel):
    """Stable declaration of what the experimental distance does and does not mean."""

    model_config = ConfigDict(frozen=True)

    id: Literal["perceptual_descriptor_shape"] = SIMILAR_MOMENTS_METHOD_ID
    version: Literal["1.0"] = SIMILAR_MOMENTS_METHOD_VERSION
    dimensions: list[str]
    distance: Literal["mean_length_normalized_z_euclidean"] = (
        "mean_length_normalized_z_euclidean"
    )
    candidate_window: Literal["same_evidence_frame_count_as_query"] = (
        "same_evidence_frame_count_as_query"
    )
    overlap_exclusion: Literal[
        "exclude_query_overlap_and_mutually_overlapping_returned_windows"
    ] = "exclude_query_overlap_and_mutually_overlapping_returned_windows"
    score_semantics: Literal["lower_is_closer_under_this_method_not_confidence"] = (
        "lower_is_closer_under_this_method_not_confidence"
    )
    semantic_claims: Literal["none"] = "none"
    parameters: dict[str, float | int] = Field(default_factory=dict)


class SimilarMomentsObservation(BaseModel):
    """Experimental result tied to one exact source/evidence Version pair."""

    model_config = ConfigDict(frozen=True)

    source_version_id: UUID
    evidence_report_version_id: UUID
    evidence_report_type: Literal["perceptual_series"] = "perceptual_series"
    preprocessing_version: str
    sample_rate: int
    query_start_seconds: float = Field(ge=0)
    query_end_seconds: float = Field(gt=0)
    max_matches: int = Field(ge=1, le=MAX_MATCHES)
    method: SimilarMomentsMethod
    matches: list[SimilarMomentMatch]
    no_match_reason: str | None = None


__all__ = [
    "MAX_MATCHES",
    "SIMILAR_MOMENTS_METHOD_ID",
    "SIMILAR_MOMENTS_METHOD_VERSION",
    "SimilarMomentMatch",
    "SimilarMomentsMethod",
    "SimilarMomentsObservation",
]
