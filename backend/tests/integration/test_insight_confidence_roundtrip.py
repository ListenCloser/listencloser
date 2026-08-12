"""Real-database integration test for the insights.confidence contract.

Under the old `confidence double precision not null` schema this test fails
(inserting a heuristic insight with confidence = None raises a Postgres
constraint violation). After 20260814_insights_confidence_nullable.sql it
passes, proving the domain model (float | None) and the database agree.
"""

from __future__ import annotations

import uuid

import pytest

from domain.models import Artifact, ArtifactKind, Insight, Project, Version, Work
from domain.repositories import (
    ArtifactRepo,
    InsightRepo,
    ProjectRepo,
    VersionRepo,
    WorkRepo,
)

OWNER_ID = "00000000-0000-4000-8000-000000000101"

pytestmark = pytest.mark.integration


def _seed_version(sb) -> Version:
    project = ProjectRepo(sb).create(
        Project(owner_id=OWNER_ID, name=f"it-confidence-{uuid.uuid4().hex[:8]}")
    )
    work = WorkRepo(sb).create(
        Work(project_id=project.id, title="integration confidence"), OWNER_ID
    )
    artifact = ArtifactRepo(sb).create(
        Artifact(work_id=work.id, kind=ArtifactKind.audio_original), OWNER_ID
    )
    return VersionRepo(sb).create(
        Version(
            artifact_id=artifact.id,
            storage_key=f"it/{uuid.uuid4().hex}.wav",
            storage_bucket="artifacts",
        ),
        OWNER_ID,
    )


def test_insight_confidence_null_and_numeric_roundtrip(sb):
    version = _seed_version(sb)
    repo = InsightRepo(sb)

    calibrated = repo.create(
        Insight(
            version_id=version.id,
            kind="key",
            claim="Key: C major",
            confidence=0.9,
            evidence={"tonic": "C", "mode": "major"},
        ),
        OWNER_ID,
    )
    heuristic = repo.create(
        Insight(
            version_id=version.id,
            kind="melody",
            claim="Range: C4–G5",
            confidence=None,
            evidence={"low_pitch": 60, "high_pitch": 67},
        ),
        OWNER_ID,
    )

    rows = repo.list_by_version(version.id, OWNER_ID)
    by_id = {row.id: row for row in rows}

    assert by_id[calibrated.id].confidence == pytest.approx(0.9)
    assert by_id[heuristic.id].confidence is None
