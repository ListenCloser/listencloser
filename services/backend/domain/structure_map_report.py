"""Persisted contract for the experimental Structure Map.

The report is intentionally method-specific. Candidate spans are inspectable
navigation evidence, not canonical verse/chorus/form annotations.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

REPORT_SCHEMA_VERSION = 1
METHOD_ID = "librosa_recurrence_novelty_v1"


class StructureMapMethod(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Literal["librosa_recurrence_novelty_v1"] = METHOD_ID
    label: str = "librosa recurrence + checkerboard novelty"
    librosa_version: str
    scipy_version: str
    parameters: dict[str, float | int | str]


class StructureCandidateSpan(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    start_seconds: float
    end_seconds: float
    recurrence_of: str | None = None
    similarity: float | None = None


class StructureMapReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = REPORT_SCHEMA_VERSION
    report_type: Literal["structure_map"] = "structure_map"
    experimental: Literal[True] = True
    source_version_id: UUID
    duration_seconds: float
    method: StructureMapMethod
    candidate_spans: list[StructureCandidateSpan]
    interpretation: str = (
        "Candidate boundaries come from self-similarity novelty; letter labels group "
        "method-similar spans and are not verse/chorus/song-form claims."
    )
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Boundary placement is approximate and method-dependent.",
            "Repeated letters indicate descriptor similarity, not motif or section identity.",
            (
                "Short, continuously changing, or weakly repetitive recordings "
                "may yield few useful spans."
            ),
        ]
    )
