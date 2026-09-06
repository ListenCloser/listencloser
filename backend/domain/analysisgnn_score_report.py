"""Persisted contract for bounded AnalysisGNN score-analysis proposals.

This report is intentionally narrower than the upstream model. It stores only the
first admitted score-analysis tasks and keeps their literal model labels attached
to exact score coordinates and exact engine/checkpoint provenance. Nothing in this
contract promotes AnalysisGNN to current theory authority.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from engines.symbolic.analysisgnn import AnalysisGNNScoreEvidence, PRODUCT_SCORE_TASKS

REPORT_SCHEMA_VERSION = 1
REPORT_TYPE = "analysisgnn_score_analysis"
AnalysisGNNProductTask = Literal["cadence", "localkey", "romanNumeral"]


class AnalysisGNNTaskLabel(BaseModel):
    model_config = ConfigDict(frozen=True)

    task: AnalysisGNNProductTask
    value: str


class AnalysisGNNPersistedObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    onset_beat: float
    measure_number: int = Field(ge=0)
    labels: list[AnalysisGNNTaskLabel]


class AnalysisGNNPersistedMethod(BaseModel):
    model_config = ConfigDict(frozen=True)

    engine: Literal["analysisgnn"] = "analysisgnn"
    library_version: str
    model: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class AnalysisGNNScoreReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = REPORT_SCHEMA_VERSION
    report_type: Literal["analysisgnn_score_analysis"] = REPORT_TYPE
    experimental: Literal[True] = True
    work_id: UUID
    source_score_artifact_id: UUID
    source_score_version_id: UUID
    tasks: list[AnalysisGNNProductTask]
    method: AnalysisGNNPersistedMethod
    observations: list[AnalysisGNNPersistedObservation]
    interpretation: str = (
        "Each label is an AnalysisGNN prediction at the recorded score coordinate. "
        "It is an experimental model proposal, not current ListenCloser theory truth."
    )
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Only cadence, local key, and Roman-numeral tasks are admitted in this first slice.",
            "Score coordinates come from the exact analyzed MusicXML Version and are not performance-time alignment.",
            "No generic confidence is inferred from model output.",
            "Current music21/TheoryInterpreter authority is unchanged by this report.",
        ]
    )


def build_analysisgnn_score_report(
    evidence: AnalysisGNNScoreEvidence,
    *,
    work_id: UUID,
    source_score_artifact_id: UUID,
    source_score_version_id: UUID,
) -> AnalysisGNNScoreReport:
    """Convert bounded engine evidence into the immutable report contract."""

    product_tasks = set(PRODUCT_SCORE_TASKS)
    unexpected_tasks = set(evidence.tasks) - product_tasks
    if unexpected_tasks:
        unexpected = ", ".join(sorted(unexpected_tasks))
        raise ValueError(f"AnalysisGNN report received non-product tasks: {unexpected}")

    observations: list[AnalysisGNNPersistedObservation] = []
    for observation in evidence.observations:
        labels: list[AnalysisGNNTaskLabel] = []
        for task, value in observation.labels:
            if task not in product_tasks:
                raise ValueError(f"AnalysisGNN report received non-product task: {task}")
            labels.append(AnalysisGNNTaskLabel(task=task, value=value))
        if not labels:
            continue
        observations.append(
            AnalysisGNNPersistedObservation(
                onset_beat=observation.onset_beat,
                measure_number=observation.measure_number,
                labels=labels,
            )
        )

    if not observations:
        raise ValueError("AnalysisGNN report requires at least one bounded observation")

    provenance = evidence.provenance.to_dict()
    return AnalysisGNNScoreReport(
        work_id=work_id,
        source_score_artifact_id=source_score_artifact_id,
        source_score_version_id=source_score_version_id,
        tasks=list(evidence.tasks),
        method=AnalysisGNNPersistedMethod(
            engine=provenance["engine"],
            library_version=provenance["library_version"],
            model=provenance.get("model"),
            parameters=provenance.get("parameters", {}),
        ),
        observations=observations,
    )
