from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from supabase import Client

from domain.models import Capability, Job, JobLifecycle, JobStage, Workflow
from domain.repositories._base import _first, _Repo
from observability import capture_job_trace_provenance


def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _parse_uuid_list(value) -> list[UUID]:
    if not value:
        return []
    return [UUID(v) for v in value]


def _uuid_list(value: list[UUID]) -> list[str]:
    return [str(v) for v in value]


class WorkflowRepo(_Repo):
    def __init__(self, client: Client, table: str = "workflows"):
        super().__init__(client, table)

    def create(self, workflow: Workflow, owner_id: str) -> Workflow:
        self._verify_project_owner(workflow.project_id, owner_id)
        data = workflow.model_dump(mode="json")
        result = self.client.table(self.table).insert(data).execute()
        return Workflow.model_validate(_first(result.data))

    def get(self, workflow_id: UUID, owner_id: str) -> Workflow | None:
        result = self.client.table(self.table).select("*").eq("id", str(workflow_id)).execute()
        if not result.data:
            return None
        self._verify_project_owner(UUID(result.data[0]["project_id"]), owner_id)
        return Workflow.model_validate(result.data[0])

    def list_by_project(self, project_id: UUID, owner_id: str) -> list[Workflow]:
        self._verify_project_owner(project_id, owner_id)
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("project_id", str(project_id))
            .order("created_at", desc=True)
            .execute()
        )
        return [Workflow.model_validate(r) for r in result.data]

    def delete(self, workflow_id: UUID, owner_id: str) -> None:
        wf = self.client.table(self.table).select("project_id").eq("id", str(workflow_id)).execute()
        if not wf.data:
            raise ValueError("workflow not found")
        self._verify_project_owner(UUID(wf.data[0]["project_id"]), owner_id)
        self.client.table(self.table).delete().eq("id", str(workflow_id)).execute()

    def _verify_project_owner(self, project_id: UUID, owner_id: str) -> None:
        result = (
            self.client.table("projects")
            .select("id")
            .eq("id", str(project_id))
            .eq("owner_id", owner_id)
            .execute()
        )
        if not result.data:
            raise PermissionError("project not found or not owned by caller")


class JobRepo(_Repo):
    def __init__(self, client: Client, table: str = "jobs"):
        super().__init__(client, table)

    def create(self, job: Job, owner_id: str) -> Job:
        self._verify_workflow_owner(job.workflow_id, owner_id)
        row = self._job_to_row(job)
        result = self.client.table(self.table).insert(row).execute()
        return self._row_to_job(_first(result.data))

    def get(self, job_id: UUID, owner_id: str) -> Job | None:
        result = self.client.table(self.table).select("*").eq("id", str(job_id)).execute()
        if not result.data:
            return None
        self._verify_workflow_owner(UUID(result.data[0]["workflow_id"]), owner_id)
        return self._row_to_job(result.data[0])

    def list_by_workflow(self, workflow_id: UUID, owner_id: str) -> list[Job]:
        self._verify_workflow_owner(workflow_id, owner_id)
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("workflow_id", str(workflow_id))
            .order("created_at", desc=True)
            .execute()
        )
        return [self._row_to_job(r) for r in result.data]

    def cancel(self, job_id: UUID, owner_id: str) -> Job:
        job = self.get(job_id, owner_id)
        if not job:
            raise ValueError("job not found")
        if job.lifecycle.current == JobStage.cancelled:
            return job
        if job.lifecycle.current not in {
            JobStage.queued,
            JobStage.claimed,
            JobStage.running,
        }:
            raise RuntimeError(f"cannot cancel a {job.lifecycle.current.value} job")
        now = datetime.now(UTC).isoformat()
        result = (
            self.client.table(self.table)
            .update(
                {
                    "stage": JobStage.cancelled.value,
                    "status_message": "cancelled by user",
                    "completed_at": now,
                    "lease_expires_at": None,
                }
            )
            .eq("id", str(job_id))
            .in_(
                "stage",
                [
                    JobStage.queued.value,
                    JobStage.claimed.value,
                    JobStage.running.value,
                ],
            )
            .execute()
        )
        if not result.data:
            raise RuntimeError("job changed state before cancellation")
        return self._row_to_job(result.data[0])

    def retry(self, job_id: UUID, owner_id: str) -> Job:
        job = self.get(job_id, owner_id)
        if not job:
            raise ValueError("job not found")
        if job.lifecycle.current not in {
            JobStage.failed,
            JobStage.cancelled,
        }:
            raise RuntimeError(f"cannot retry a {job.lifecycle.current.value} job")
        retry_id = uuid5(NAMESPACE_URL, f"hello-ai:retry:{job.id}")
        existing_retry = self.get(retry_id, owner_id)
        if existing_retry:
            return existing_retry
        retry_job = Job(
            id=retry_id,
            workflow_id=job.workflow_id,
            capability=job.capability,
            input_version_ids=job.input_version_ids,
            parameters=job.parameters,
            cache_key=(f"{job.cache_key}:retry:{job.id}" if job.cache_key else None),
            provenance={
                **job.provenance,
                "retry_of_job_id": str(job.id),
            },
            created_by=job.created_by,
        )
        return self.create(retry_job, owner_id)

    def update_stage(self, job_id: UUID, stage: JobStage, *, owner_id: str, **kwargs) -> Job:
        j = self.client.table(self.table).select("workflow_id").eq("id", str(job_id)).execute()
        if not j.data:
            raise ValueError("job not found")
        self._verify_workflow_owner(UUID(j.data[0]["workflow_id"]), owner_id)
        patch: dict = {"stage": stage.value}
        patch.update(kwargs)
        result = self.client.table(self.table).update(patch).eq("id", str(job_id)).execute()
        return self._row_to_job(_first(result.data))

    def claim(self, job_id: UUID, worker_id: str) -> Job | None:
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("id", str(job_id))
            .eq("stage", JobStage.queued.value)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        updated = (
            self.client.table(self.table)
            .update(
                {
                    "stage": JobStage.claimed.value,
                    "worker_id": worker_id,
                    "lease_expires_at": datetime.now(UTC).isoformat(),
                }
            )
            .eq("id", str(job_id))
            .eq("stage", JobStage.queued.value)
            .execute()
        )
        if not updated.data:
            return None
        return self._row_to_job(updated.data[0])

    def _verify_workflow_owner(self, workflow_id: UUID, owner_id: str) -> None:
        wf = (
            self.client.table("workflows")
            .select("project_id")
            .eq("id", str(workflow_id))
            .execute()
        )
        if not wf.data:
            raise ValueError("workflow not found")
        proj = (
            self.client.table("projects")
            .select("id")
            .eq("id", wf.data[0]["project_id"])
            .eq("owner_id", owner_id)
            .execute()
        )
        if not proj.data:
            raise PermissionError("workflow does not belong to caller's project")

    def _job_to_row(self, job: Job) -> dict:
        lc = job.lifecycle
        row: dict = {
            "id": str(job.id),
            "workflow_id": str(job.workflow_id),
            "capability_name": job.capability.name,
            "capability_version": job.capability.version,
            "stage": lc.current.value,
            "progress": lc.progress,
            "status_message": lc.message,
            "retry_count": lc.retry_count,
            "max_retries": lc.max_retries,
            "lease_expires_at": lc.lease_expires_at.isoformat() if lc.lease_expires_at else None,
            "started_at": lc.started_at.isoformat() if lc.started_at else None,
            "completed_at": lc.completed_at.isoformat() if lc.completed_at else None,
            "input_version_ids": _uuid_list(job.input_version_ids),
            "output_version_ids": _uuid_list(job.output_version_ids),
            "parameters": job.parameters,
            "cache_key": job.cache_key,
            "error_message": job.error,
            "error_details": job.error_details,
            "provenance": capture_job_trace_provenance(job.provenance),
            "created_at": job.created_at.isoformat(),
            "created_by": job.created_by,
        }
        return row

    def _row_to_job(self, row: dict) -> Job:
        lifecycle = JobLifecycle(
            current=JobStage(row["stage"]),
            progress=float(row.get("progress", 0.0)),
            message=row.get("status_message", ""),
            retry_count=int(row.get("retry_count", 0)),
            max_retries=int(row.get("max_retries", 3)),
            lease_expires_at=_parse_dt(row.get("lease_expires_at")),
            started_at=_parse_dt(row.get("started_at")),
            completed_at=_parse_dt(row.get("completed_at")),
        )
        capability = Capability(
            name=row["capability_name"],
            version=row["capability_version"],
        )
        return Job(
            id=UUID(row["id"]),
            workflow_id=UUID(row["workflow_id"]),
            capability=capability,
            lifecycle=lifecycle,
            input_version_ids=_parse_uuid_list(row.get("input_version_ids")),
            output_version_ids=_parse_uuid_list(row.get("output_version_ids")),
            parameters=row.get("parameters", {}),
            cache_key=row.get("cache_key"),
            error=row.get("error_message"),
            error_details=row.get("error_details", {}),
            provenance=row.get("provenance", {}),
            created_at=_parse_dt(row["created_at"]),
            created_by=row.get("created_by"),
        )
