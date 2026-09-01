from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from domain.models import Version
from domain.storage_locator_audit import (
    _read_all_pages,
    AuditRows,
    audit_storage_locator_rows,
)


def _version_row(
    *,
    artifact_id: UUID,
    storage_key: str,
    owner_id: str,
    created_at: datetime,
    produced_by_job_id: UUID | None = None,
) -> dict:
    return Version(
        artifact_id=artifact_id,
        storage_key=storage_key,
        storage_bucket="artifacts",
        created_by=owner_id,
        produced_by_job_id=produced_by_job_id,
        created_at=created_at,
    ).model_dump(mode="json")


def test_audit_reuses_locator_policy_and_keeps_default_report_private():
    owner_id = str(uuid4())
    project_id = uuid4()
    work_id = uuid4()
    artifact_id = uuid4()
    now = datetime.now(UTC)
    trusted_key = f"{owner_id}/{project_id}/{artifact_id}/private-source.wav"
    legacy_key = "transcriptions/private-take.mid"
    trusted = _version_row(
        artifact_id=artifact_id,
        storage_key=trusted_key,
        owner_id=owner_id,
        created_at=now,
    )
    legacy = _version_row(
        artifact_id=artifact_id,
        storage_key=legacy_key,
        owner_id=owner_id,
        created_at=now + timedelta(seconds=1),
    )
    rows = AuditRows(
        projects=[{"id": str(project_id), "owner_id": owner_id}],
        works=[{"id": str(work_id), "project_id": str(project_id)}],
        artifacts=[{"id": str(artifact_id), "work_id": str(work_id), "kind": "midi_performance"}],
        versions=[trusted, legacy],
        workflows=[],
        jobs=[],
    )

    report = audit_storage_locator_rows(rows)
    summary = report.summary()

    assert summary["trusted_versions"] == 1
    assert summary["candidate_versions"] == 1
    assert summary["latest_candidate_versions"] == 1
    assert summary["affected_works"] == 1
    assert summary["candidate_reasons"] == {"owner_path_shape": 1}
    assert summary["candidate_path_classes"] == {"transcriptions": 1}

    serialized_summary = json.dumps(summary)
    assert owner_id not in serialized_summary
    assert trusted_key not in serialized_summary
    assert legacy_key not in serialized_summary

    detail = report.selected([legacy["id"]])[0]
    serialized_detail = json.dumps(detail)
    assert detail["version_id"] == legacy["id"]
    assert detail["work_id"] == str(work_id)
    assert detail["project_id"] == str(project_id)
    assert detail["legacy_path_class"] == "transcriptions"
    assert detail["storage_key_sha256"]
    assert owner_id not in serialized_detail
    assert legacy_key not in serialized_detail


def test_worker_output_is_trusted_only_through_same_work_workflow_membership():
    owner_id = str(uuid4())
    project_id = uuid4()
    work_id = uuid4()
    input_artifact_id = uuid4()
    output_artifact_id = uuid4()
    workflow_id = uuid4()
    job_id = uuid4()
    now = datetime.now(UTC)
    input_version = _version_row(
        artifact_id=input_artifact_id,
        storage_key=f"{owner_id}/{project_id}/{input_artifact_id}/input.wav",
        owner_id=owner_id,
        created_at=now,
    )
    output_version = _version_row(
        artifact_id=output_artifact_id,
        storage_key=f"jobs/{job_id}/attempt-0/output.mid",
        owner_id=owner_id,
        created_at=now + timedelta(seconds=1),
        produced_by_job_id=job_id,
    )
    rows = AuditRows(
        projects=[{"id": str(project_id), "owner_id": owner_id}],
        works=[{"id": str(work_id), "project_id": str(project_id)}],
        artifacts=[
            {"id": str(input_artifact_id), "work_id": str(work_id), "kind": "audio_original"},
            {
                "id": str(output_artifact_id),
                "work_id": str(work_id),
                "kind": "midi_performance",
            },
        ],
        versions=[input_version, output_version],
        workflows=[
            {
                "id": str(workflow_id),
                "project_id": str(project_id),
                "target_version_id": input_version["id"],
            }
        ],
        jobs=[{"id": str(job_id), "workflow_id": str(workflow_id)}],
    )

    report = audit_storage_locator_rows(rows)
    by_id = {entry.version_id: entry for entry in report.entries}

    assert by_id[output_version["id"]].trusted is True
    assert by_id[output_version["id"]].locator_kind == "worker_output"

    rows_without_membership = AuditRows(
        projects=rows.projects,
        works=rows.works,
        artifacts=rows.artifacts,
        versions=rows.versions,
        workflows=[],
        jobs=rows.jobs,
    )
    report_without_membership = audit_storage_locator_rows(rows_without_membership)
    by_id = {entry.version_id: entry for entry in report_without_membership.entries}
    assert by_id[output_version["id"]].reason == "job_not_in_work"


def test_broken_authority_graph_is_reported_instead_of_skipped():
    owner_id = str(uuid4())
    missing_artifact_id = uuid4()
    version = _version_row(
        artifact_id=missing_artifact_id,
        storage_key="legacy/unknown.wav",
        owner_id=owner_id,
        created_at=datetime.now(UTC),
    )
    report = audit_storage_locator_rows(
        AuditRows(
            projects=[],
            works=[],
            artifacts=[],
            versions=[version],
            workflows=[],
            jobs=[],
        )
    )

    assert len(report.entries) == 1
    assert report.entries[0].trusted is False
    assert report.entries[0].reason == "missing_artifact"
    assert report.summary()["candidate_versions"] == 1


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows, ranges):
        self.rows = rows
        self.ranges = ranges
        self.start = 0
        self.end = 0

    def select(self, _columns):
        return self

    def order(self, _column):
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        self.ranges.append((start, end))
        return self

    def execute(self):
        return _Result(self.rows[self.start : self.end + 1])


class _Client:
    def __init__(self, rows):
        self.rows = rows
        self.ranges = []

    def table(self, _table):
        return _Query(self.rows, self.ranges)


def test_paginated_reader_does_not_drop_rows_after_postgrest_default_boundary():
    rows = [{"id": str(index)} for index in range(1001)]
    client = _Client(rows)

    result = _read_all_pages(client, "artifact_versions", "id")

    assert result == rows
    assert client.ranges == [(0, 999), (1000, 1999)]
