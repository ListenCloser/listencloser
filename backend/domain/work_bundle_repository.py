"""Bulk read model for opening a saved Work.

The general repositories deliberately authorize each aggregate independently.
That is correct for arbitrary reads, but the Work bundle endpoint already has a
single owned Work as its authorization root. Repeating the same ownership walk
for every Artifact Version and Workflow Job creates an N+1 cold-open path.

This repository performs one ownership check at the Work boundary, then loads
only descendants whose foreign keys were discovered from that authorized Work.
The number of database round trips is therefore bounded independently of the
number of artifacts, versions, or workflows in the Work.
"""

from dataclasses import dataclass
from uuid import UUID

from supabase import Client

from domain.models import Artifact, Job, Version, Work, Workflow
from domain.repositories import JobRepo, WorkRepo


@dataclass(frozen=True)
class WorkBundleSnapshot:
    """Authorized persistence snapshot needed by ``GET /works/{work_id}``."""

    work: Work
    artifacts: list[Artifact]
    versions_by_artifact: dict[UUID, list[Version]]
    jobs: list[Job]


class WorkBundleRepository:
    """Load one Work graph with a bounded query count.

    Query shape for a non-empty Work:
      1. Work row
      2. owning Project verification (inside ``WorkRepo.get``)
      3. Artifacts for Work
      4. Versions for all Artifacts
      5. Workflows targeting those Versions
      6. Jobs for all matching Workflows

    Empty descendant sets stop early, so they use fewer queries. Child reads do
    not repeat ownership checks because all queried IDs are reached through the
    already-authorized Work/project boundary.
    """

    def __init__(self, client: Client):
        self.client = client

    def load(self, work_id: UUID, owner_id: str) -> WorkBundleSnapshot | None:
        work = WorkRepo(self.client).get(work_id, owner_id)
        if not work:
            return None

        artifact_result = (
            self.client.table("artifacts")
            .select("*")
            .eq("work_id", str(work.id))
            .order("created_at", desc=True)
            .execute()
        )
        artifacts = [Artifact.model_validate(row) for row in (artifact_result.data or [])]
        versions_by_artifact: dict[UUID, list[Version]] = {
            artifact.id: [] for artifact in artifacts
        }
        if not artifacts:
            return WorkBundleSnapshot(
                work=work,
                artifacts=artifacts,
                versions_by_artifact=versions_by_artifact,
                jobs=[],
            )

        artifact_ids = [str(artifact.id) for artifact in artifacts]
        version_result = (
            self.client.table("artifact_versions")
            .select("*")
            .in_("artifact_id", artifact_ids)
            .order("created_at", desc=True)
            .execute()
        )
        versions = [Version.model_validate(row) for row in (version_result.data or [])]
        for version in versions:
            versions_by_artifact.setdefault(version.artifact_id, []).append(version)

        version_ids = [str(version.id) for version in versions]
        if not version_ids:
            return WorkBundleSnapshot(
                work=work,
                artifacts=artifacts,
                versions_by_artifact=versions_by_artifact,
                jobs=[],
            )

        workflow_result = (
            self.client.table("workflows")
            .select("*")
            .eq("project_id", str(work.project_id))
            .in_("target_version_id", version_ids)
            .order("created_at", desc=True)
            .execute()
        )
        workflows = [Workflow.model_validate(row) for row in (workflow_result.data or [])]
        if not workflows:
            return WorkBundleSnapshot(
                work=work,
                artifacts=artifacts,
                versions_by_artifact=versions_by_artifact,
                jobs=[],
            )

        workflow_ids = [str(workflow.id) for workflow in workflows]
        job_result = (
            self.client.table("jobs")
            .select("*")
            .in_("workflow_id", workflow_ids)
            .order("created_at", desc=True)
            .execute()
        )
        job_repo = JobRepo(self.client)
        # Job rows use the persistence projection (stage/capability columns),
        # so reuse the repository's canonical row decoder rather than creating
        # a second interpretation of that storage contract.
        jobs = [job_repo._row_to_job(row) for row in (job_result.data or [])]
        jobs.sort(key=lambda job: job.created_at, reverse=True)

        return WorkBundleSnapshot(
            work=work,
            artifacts=artifacts,
            versions_by_artifact=versions_by_artifact,
            jobs=jobs,
        )
