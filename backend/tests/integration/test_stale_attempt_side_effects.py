from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from domain.capabilities import _create_output_version
from domain.job_worker import JobWorker
from domain.models import ArtifactKind


@pytest.mark.real_stack
def test_stale_attempt_can_currently_persist_output_after_genuine_takeover(sb) -> None:
    """Characterize #539 through the real JobWorker + output persistence path.

    This intentionally asserts the *current unsafe behavior* as a before-state
    contract. The production fencing PR for #539 should invert the final output
    assertion: once worker B owns the attempt, worker A must no longer be able
    to make a new product-visible Version authoritative.
    """

    owner_id = str(uuid4())
    project_id = str(uuid4())
    work_id = str(uuid4())
    workflow_id = str(uuid4())
    job_id = str(uuid4())

    sb.table("projects").insert(
        {"id": project_id, "owner_id": owner_id, "name": "stale-attempt characterization"}
    ).execute()
    try:
        sb.table("works").insert(
            {"id": work_id, "project_id": project_id, "title": "takeover fixture"}
        ).execute()
        sb.table("workflows").insert(
            {"id": workflow_id, "project_id": project_id, "kind": "understand"}
        ).execute()
        sb.table("jobs").insert(
            {
                "id": job_id,
                "workflow_id": workflow_id,
                "capability_name": "characterize_stale_attempt",
                "capability_version": "1.0",
            }
        ).execute()

        worker_a = JobWorker(lease_duration_sec=30.0)
        worker_b = JobWorker(lease_duration_sec=30.0)
        worker_a._client = sb
        worker_b._client = sb

        assert worker_a._worker_id != worker_b._worker_id
        assert worker_a._claim_job(job_id) is True
        assert worker_a._mark_running(job_id) is True

        running_row = sb.table("jobs").select("*").eq("id", job_id).execute().data[0]
        stale_job = worker_a._row_to_job(running_row)

        # Model a genuine loss of lease ownership: A stops renewing, B recovers
        # the expired row, then claims and starts the same logical Job.
        expired_at = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        sb.table("jobs").update({"lease_expires_at": expired_at}).eq("id", job_id).execute()
        assert worker_b._recover_orphans() == 1
        assert worker_b._claim_job(job_id) is True
        assert worker_b._mark_running(job_id) is True

        after_takeover = sb.table("jobs").select("*").eq("id", job_id).execute().data[0]
        assert after_takeover["worker_id"] == worker_b._worker_id
        assert after_takeover["stage"] == "running"

        # Job-row completion is already fenced by worker_id + stage, but the
        # normal production Artifact/Version helper receives only (job, client)
        # and performs no ownership check. A stale execution can therefore
        # publish a new product-visible Version after B owns the Job.
        stale_version_id = _create_output_version(
            sb,
            UUID(work_id),
            ArtifactKind.analysis_report,
            f"jobs/{job_id}/stale-attempt/characterization.json",
            b"{}",
            None,
            stale_job,
            owner_id,
            mime_type="application/json",
            label="stale attempt characterization",
            metadata={"characterization": "issue-539"},
        )
        worker_a._mark_succeeded(job_id, [str(stale_version_id)])

        final_job = sb.table("jobs").select("*").eq("id", job_id).execute().data[0]
        assert final_job["worker_id"] == worker_b._worker_id
        assert final_job["stage"] == "running"
        assert final_job["output_version_ids"] == []

        stale_rows = (
            sb.table("artifact_versions")
            .select("id,produced_by_job_id,storage_key")
            .eq("id", str(stale_version_id))
            .execute()
            .data
        )
        assert len(stale_rows) == 1
        assert stale_rows[0]["produced_by_job_id"] == job_id
        assert stale_rows[0]["storage_key"].endswith("characterization.json")
    finally:
        sb.table("projects").delete().eq("id", project_id).execute()
