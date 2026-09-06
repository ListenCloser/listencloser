from __future__ import annotations

import time
from contextlib import suppress
from uuid import UUID, uuid4

import pytest

from domain.capabilities import _create_output_version
from domain.models import ArtifactKind
from domain.pgmq_job_worker import PgmqJobWorker


@pytest.mark.real_stack
def test_stale_attempt_cannot_persist_output_after_genuine_takeover(sb) -> None:
    """Prove #539 is fenced through real PGMQ redelivery + output persistence.

    Worker A is allowed to compute past its PGMQ visibility timeout. After the
    same delivery is genuinely redelivered, only Worker B's fresh execution
    token may make product-visible state durable. The persistence RPC checks
    and locks that token in the same transaction as the Artifact/Version insert,
    so there is no check/write gap.
    """

    owner_id = str(uuid4())
    project_id = str(uuid4())
    work_id = str(uuid4())
    workflow_id = str(uuid4())
    job_id = str(uuid4())
    uploaded_keys: list[str] = []

    sb.table("projects").insert(
        {"id": project_id, "owner_id": owner_id, "name": "stale-attempt fence"}
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

        worker_a = PgmqJobWorker(visibility_timeout_sec=1, heartbeat_interval_sec=0.5)
        worker_b = PgmqJobWorker(visibility_timeout_sec=1, heartbeat_interval_sec=0.5)
        worker_a._client = sb
        worker_b._client = sb

        assert worker_a._worker_id != worker_b._worker_id
        attempt_a = worker_a._receive_next_job()
        assert attempt_a is not None
        assert str(attempt_a["id"]) == job_id
        assert worker_a._mark_running(job_id) is True

        running_row = sb.table("jobs").select("*").eq("id", job_id).execute().data[0]
        stale_job = worker_a._row_to_job(running_row)
        stale_token = running_row["execution_token"]
        stale_client = worker_a._handler_client(job_id)
        assert stale_token

        # Production writes Storage before publishing its Artifact/Version. A may
        # therefore leave a private orphan object if it loses delivery visibility
        # after upload. Use the real Storage API here so the DB publication fence
        # also proves the exact bucket+key exists in storage.objects.
        stale_storage_key = f"jobs/{job_id}/stale-attempt/characterization.json"
        stale_scoped_key = stale_client.scope_storage_key(stale_storage_key)
        stale_client.storage.from_("artifacts").upload(
            stale_storage_key,
            b"{}",
            {"content-type": "application/json"},
        )
        uploaded_keys.append(stale_scoped_key)

        # Model a genuine PGMQ takeover: A stops extending visibility, the same
        # message becomes visible again, and B receives a fresh execution token.
        time.sleep(1.1)
        attempt_b = worker_b._receive_next_job()
        assert attempt_b is not None
        assert str(attempt_b["id"]) == job_id
        assert int(attempt_b["_queue_msg_id"]) == int(attempt_a["_queue_msg_id"])
        assert int(attempt_b["_queue_read_ct"]) >= 2
        assert worker_b._mark_running(job_id) is True

        after_takeover = sb.table("jobs").select("*").eq("id", job_id).execute().data[0]
        current_token = after_takeover["execution_token"]
        assert after_takeover["worker_id"] == worker_b._worker_id
        assert after_takeover["stage"] == "running"
        assert after_takeover["lease_expires_at"] is None
        assert current_token
        assert current_token != stale_token

        # A heartbeat thread may outlive its PGMQ visibility ownership. The stale
        # token must not extend or otherwise disturb B's current generation.
        worker_a._heartbeat_delivery(job_id)
        after_stale_heartbeat = sb.table("jobs").select("*").eq("id", job_id).execute().data[0]
        assert after_stale_heartbeat["worker_id"] == worker_b._worker_id
        assert after_stale_heartbeat["execution_token"] == current_token
        assert after_stale_heartbeat["stage"] == "running"

        # A stale execution may still finish inference, and its object may already
        # exist, but its normal production output helper is fenced at the durable
        # database boundary after B takes ownership.
        with pytest.raises(Exception, match="stale job execution cannot publish output"):
            _create_output_version(
                stale_client,
                UUID(work_id),
                ArtifactKind.analysis_report,
                stale_storage_key,
                b"{}",
                None,
                stale_job,
                owner_id,
                mime_type="application/json",
                label="stale attempt characterization",
                metadata={"characterization": "issue-539"},
            )

        # Job-row completion is token-fenced too: stale A cannot terminate B's
        # current attempt after its output publication has been rejected.
        worker_a._mark_succeeded(job_id, [])
        still_current = sb.table("jobs").select("*").eq("id", job_id).execute().data[0]
        assert still_current["worker_id"] == worker_b._worker_id
        assert still_current["execution_token"] == current_token
        assert still_current["stage"] == "running"
        assert still_current["output_version_ids"] == []

        stale_versions = (
            sb.table("artifact_versions")
            .select("id")
            .eq("produced_by_job_id", job_id)
            .execute()
            .data
        )
        stale_artifacts = sb.table("artifacts").select("id").eq("work_id", work_id).execute().data
        assert stale_versions == []
        assert stale_artifacts == []

        # The new owner uploads and publishes through the exact same production
        # path, then completes the Job. This keeps redelivery at-least-once rather
        # than turning takeover into a permanent failure mode.
        current_job = worker_b._row_to_job(after_takeover)
        current_client = worker_b._handler_client(job_id)
        current_storage_key = f"jobs/{job_id}/current-attempt/characterization.json"
        current_scoped_key = current_client.scope_storage_key(current_storage_key)
        current_client.storage.from_("artifacts").upload(
            current_storage_key,
            b"{}",
            {"content-type": "application/json"},
        )
        uploaded_keys.append(current_scoped_key)
        current_version_id = _create_output_version(
            current_client,
            UUID(work_id),
            ArtifactKind.analysis_report,
            current_storage_key,
            b"{}",
            None,
            current_job,
            owner_id,
            mime_type="application/json",
            label="current attempt characterization",
            metadata={"characterization": "issue-539-current"},
        )
        worker_b._mark_succeeded(job_id, [str(current_version_id)])

        final_job = sb.table("jobs").select("*").eq("id", job_id).execute().data[0]
        assert final_job["stage"] == "succeeded"
        assert final_job["execution_token"] == current_token
        assert final_job["output_version_ids"] == [str(current_version_id)]

        current_rows = (
            sb.table("artifact_versions")
            .select("id,produced_by_job_id,storage_bucket,storage_key")
            .eq("id", str(current_version_id))
            .execute()
            .data
        )
        assert len(current_rows) == 1
        assert current_rows[0]["produced_by_job_id"] == job_id
        assert current_rows[0]["storage_bucket"] == "artifacts"
        assert current_rows[0]["storage_key"] == current_scoped_key
    finally:
        if uploaded_keys:
            with suppress(Exception):
                sb.storage.from_("artifacts").remove(uploaded_keys)
        sb.table("projects").delete().eq("id", project_id).execute()
