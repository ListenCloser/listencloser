"""Bulk read model for opening a saved Work.

The general repositories deliberately authorize each aggregate independently.
That is correct for arbitrary reads, but the Work bundle endpoint already has a
single owned Work as its authorization root. Repeating the same ownership walk
for every Artifact Version and Workflow Job creates an N+1 cold-open path.

This repository performs one ownership check at the Work boundary, then loads
only descendants whose foreign keys were discovered from that authorized Work.
Database round trips grow by bounded ID chunks and result pages rather than by
individual descendants, so large graphs stay complete without reintroducing N+1.
"""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from supabase import Client

from domain.models import Artifact, Job, Version, Work, Workflow
from domain.repositories import JobRepo, WorkRepo

_PAGE_SIZE = 1000
_ID_CHUNK_SIZE = 100


@dataclass(frozen=True)
class WorkBundleSnapshot:
    """Authorized persistence snapshot needed by ``GET /works/{work_id}``."""

    work: Work
    artifacts: list[Artifact]
    versions_by_artifact: dict[UUID, list[Version]]
    jobs: list[Job]


def _read_all_pages(build_query: Callable[[], object]) -> list[dict]:
    """Read a filtered PostgREST result without silently accepting row caps."""

    rows: list[dict] = []
    start = 0
    while True:
        result = build_query().range(start, start + _PAGE_SIZE - 1).execute()
        page = list(result.data or [])
        rows.extend(page)
        if len(page) < _PAGE_SIZE:
            return rows
        start += _PAGE_SIZE


def _read_id_chunks(
    values: list[str],
    build_query: Callable[[list[str]], object],
) -> list[dict]:
    """Read rows for IDs without creating an unbounded PostgREST ``in`` filter."""

    rows: list[dict] = []
    for start in range(0, len(values), _ID_CHUNK_SIZE):
        chunk = values[start : start + _ID_CHUNK_SIZE]
        rows.extend(_read_all_pages(lambda chunk=chunk: build_query(chunk)))
    return rows


class WorkBundleRepository:
    """Load one Work graph with an authorization-rooted, bounded query shape.

    A typical non-empty Work below the ID-chunk and PostgREST page sizes uses:
      1. Work row
      2. owning Project verification (inside ``WorkRepo.get``)
      3. Artifacts for Work
      4. Versions for all Artifacts
      5. Workflows targeting those Versions
      6. Jobs for all matching Workflows

    Descendant reads paginate and bound ``in`` filters so neither Supabase's
    configured row cap nor request-size limits can silently truncate or reject a
    large Work. Empty descendant sets stop early. Child reads do not repeat
    ownership checks because all queried IDs are reached through the already-
    authorized Work/project boundary.
    """

    def __init__(self, client: Client):
        self.client = client

    def load(self, work_id: UUID, owner_id: str) -> WorkBundleSnapshot | None:
        work = WorkRepo(self.client).get(work_id, owner_id)
        if not work:
            return None

        artifact_rows = _read_all_pages(
            lambda: self.client.table("artifacts")
            .select("*")
            .eq("work_id", str(work.id))
            .order("created_at", desc=True)
        )
        artifacts = [Artifact.model_validate(row) for row in artifact_rows]
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
        version_rows = _read_id_chunks(
            artifact_ids,
            lambda chunk: self.client.table("artifact_versions")
            .select("*")
            .in_("artifact_id", chunk)
            .order("created_at", desc=True),
        )
        versions = [Version.model_validate(row) for row in version_rows]
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

        workflow_rows = _read_id_chunks(
            version_ids,
            lambda chunk: self.client.table("workflows")
            .select("*")
            .eq("project_id", str(work.project_id))
            .in_("target_version_id", chunk)
            .order("created_at", desc=True),
        )
        workflows = [Workflow.model_validate(row) for row in workflow_rows]
        if not workflows:
            return WorkBundleSnapshot(
                work=work,
                artifacts=artifacts,
                versions_by_artifact=versions_by_artifact,
                jobs=[],
            )

        workflow_ids = [str(workflow.id) for workflow in workflows]
        job_rows = _read_id_chunks(
            workflow_ids,
            lambda chunk: self.client.table("jobs")
            .select("*")
            .in_("workflow_id", chunk)
            .order("created_at", desc=True),
        )
        job_repo = JobRepo(self.client)
        # Job rows use the persistence projection (stage/capability columns),
        # so reuse the repository's canonical row decoder rather than creating
        # a second interpretation of that storage contract.
        jobs = [job_repo._row_to_job(row) for row in job_rows]
        jobs.sort(key=lambda job: job.created_at, reverse=True)

        return WorkBundleSnapshot(
            work=work,
            artifacts=artifacts,
            versions_by_artifact=versions_by_artifact,
            jobs=jobs,
        )
