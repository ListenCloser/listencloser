import os
import threading
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from supabase import Client, create_client

from domain.models import (
    Alignment,
    AlignmentKind,
    Artifact,
    ArtifactKind,
    Cadence,
    Capability,
    ChordEntity,
    Entity,
    EntityKind,
    Insight,
    Job,
    JobLifecycle,
    JobStage,
    NoteEntity,
    Project,
    Span,
    TimelineUnit,
    Version,
    Work,
    Workflow,
    WorkflowKind,
)

__all__ = [
    "get_supabase",
    "ProjectRepo",
    "WorkRepo",
    "ArtifactRepo",
    "VersionRepo",
    "EntityRepo",
    "InsightRepo",
    "AlignmentRepo",
    "WorkflowRepo",
    "JobRepo",
]

_sb_client: Optional[Client] = None
_sb_lock = threading.Lock()


def get_supabase() -> Optional[Client]:
    global _sb_client
    if _sb_client is not None:
        return _sb_client
    with _sb_lock:
        if _sb_client is not None:
            return _sb_client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            return None
        _sb_client = create_client(url, key)
        return _sb_client


def _parse_dt(value) -> Optional[datetime]:
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


def _first(data: list[dict]):
    if not data:
        raise ValueError("no rows returned")
    return data[0]


class _Repo:
    def __init__(self, client: Client, table: str):
        self.client = client
        self.table = table


# =============================================================================
# ProjectRepo
# =============================================================================


class ProjectRepo(_Repo):
    def __init__(self, client: Client, table: str = "projects"):
        super().__init__(client, table)

    def create(self, project: Project) -> Project:
        data = project.model_dump(mode="json")
        result = self.client.table(self.table).insert(data).execute()
        return Project.model_validate(_first(result.data))

    def get(self, project_id: UUID, owner_id: str) -> Optional[Project]:
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("id", str(project_id))
            .eq("owner_id", owner_id)
            .execute()
        )
        if not result.data:
            return None
        return Project.model_validate(result.data[0])

    def list_by_owner(self, owner_id: str) -> list[Project]:
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("owner_id", owner_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [Project.model_validate(r) for r in result.data]

    def update(self, project: Project, owner_id: str) -> Project:
        self._verify_owner(str(project.id), owner_id)
        data = project.model_dump(mode="json")
        result = (
            self.client.table(self.table)
            .update(data)
            .eq("id", str(project.id))
            .execute()
        )
        return Project.model_validate(_first(result.data))

    def delete(self, project_id: UUID, owner_id: str) -> None:
        self._verify_owner(str(project_id), owner_id)
        self.client.table(self.table).delete().eq("id", str(project_id)).execute()

    def _verify_owner(self, project_id: str, owner_id: str) -> None:
        result = (
            self.client.table(self.table)
            .select("id")
            .eq("id", project_id)
            .eq("owner_id", owner_id)
            .execute()
        )
        if not result.data:
            raise PermissionError("project not found or not owned by caller")


# =============================================================================
# WorkRepo
# =============================================================================


class WorkRepo(_Repo):
    def __init__(self, client: Client, table: str = "works"):
        super().__init__(client, table)

    def create(self, work: Work, owner_id: str) -> Work:
        self._verify_project(work.project_id, owner_id)
        data = work.model_dump(mode="json")
        result = self.client.table(self.table).insert(data).execute()
        return Work.model_validate(_first(result.data))

    def get(self, work_id: UUID, owner_id: str) -> Optional[Work]:
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("id", str(work_id))
            .execute()
        )
        if not result.data:
            return None
        self._verify_project(UUID(result.data[0]["project_id"]), owner_id)
        return Work.model_validate(result.data[0])

    def list_by_project(self, project_id: UUID, owner_id: str) -> list[Work]:
        self._verify_project(project_id, owner_id)
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("project_id", str(project_id))
            .order("created_at", desc=True)
            .execute()
        )
        return [Work.model_validate(r) for r in result.data]

    def update(self, work: Work, owner_id: str) -> Work:
        self._verify_project(work.project_id, owner_id)
        data = work.model_dump(mode="json")
        result = (
            self.client.table(self.table)
            .update(data)
            .eq("id", str(work.id))
            .execute()
        )
        return Work.model_validate(_first(result.data))

    def delete(self, work_id: UUID, owner_id: str) -> None:
        self._verify_work_owner(work_id, owner_id)
        self.client.table(self.table).delete().eq("id", str(work_id)).execute()

    def _verify_project(self, project_id: UUID, owner_id: str) -> None:
        result = (
            self.client.table("projects")
            .select("id")
            .eq("id", str(project_id))
            .eq("owner_id", owner_id)
            .execute()
        )
        if not result.data:
            raise PermissionError("project not found or not owned by caller")

    def _verify_work_owner(self, work_id: UUID, owner_id: str) -> None:
        w = (
            self.client.table(self.table)
            .select("project_id")
            .eq("id", str(work_id))
            .execute()
        )
        if not w.data:
            raise ValueError("work not found")
        self._verify_project(UUID(w.data[0]["project_id"]), owner_id)


# =============================================================================
# ArtifactRepo
# =============================================================================


class ArtifactRepo(_Repo):
    def __init__(self, client: Client, table: str = "artifacts"):
        super().__init__(client, table)

    def create(self, artifact: Artifact, owner_id: str) -> Artifact:
        self._verify_work_owner(artifact.work_id, owner_id)
        data = artifact.model_dump(mode="json")
        result = self.client.table(self.table).insert(data).execute()
        return Artifact.model_validate(_first(result.data))

    def get(self, artifact_id: UUID, owner_id: str) -> Optional[Artifact]:
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("id", str(artifact_id))
            .execute()
        )
        if not result.data:
            return None
        self._verify_work_owner(UUID(result.data[0]["work_id"]), owner_id)
        return Artifact.model_validate(result.data[0])

    def list_by_work(self, work_id: UUID, owner_id: str) -> list[Artifact]:
        self._verify_work_owner(work_id, owner_id)
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("work_id", str(work_id))
            .order("created_at", desc=True)
            .execute()
        )
        return [Artifact.model_validate(r) for r in result.data]

    def delete(self, artifact_id: UUID, owner_id: str) -> None:
        self._verify_artifact_owner(artifact_id, owner_id)
        self.client.table(self.table).delete().eq("id", str(artifact_id)).execute()

    def _verify_work_owner(self, work_id: UUID, owner_id: str) -> None:
        w = (
            self.client.table("works")
            .select("project_id")
            .eq("id", str(work_id))
            .execute()
        )
        if not w.data:
            raise ValueError("work not found")
        proj = (
            self.client.table("projects")
            .select("id")
            .eq("id", w.data[0]["project_id"])
            .eq("owner_id", owner_id)
            .execute()
        )
        if not proj.data:
            raise PermissionError("work does not belong to caller's project")

    def _verify_artifact_owner(self, artifact_id: UUID, owner_id: str) -> None:
        a = (
            self.client.table(self.table)
            .select("work_id")
            .eq("id", str(artifact_id))
            .execute()
        )
        if not a.data:
            raise ValueError("artifact not found")
        self._verify_work_owner(UUID(a.data[0]["work_id"]), owner_id)


# =============================================================================
# VersionRepo
# =============================================================================


class VersionRepo(_Repo):
    def __init__(self, client: Client, table: str = "artifact_versions"):
        super().__init__(client, table)

    def create(self, version: Version, owner_id: str) -> Version:
        self._verify_artifact_owner(version.artifact_id, owner_id)
        data = version.model_dump(mode="json")
        result = self.client.table(self.table).insert(data).execute()
        return Version.model_validate(_first(result.data))

    def get(self, version_id: UUID, owner_id: str) -> Optional[Version]:
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("id", str(version_id))
            .execute()
        )
        if not result.data:
            return None
        self._verify_artifact_owner(UUID(result.data[0]["artifact_id"]), owner_id)
        return Version.model_validate(result.data[0])

    def list_by_artifact(self, artifact_id: UUID, owner_id: str) -> list[Version]:
        self._verify_artifact_owner(artifact_id, owner_id)
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("artifact_id", str(artifact_id))
            .order("created_at", desc=True)
            .execute()
        )
        return [Version.model_validate(r) for r in result.data]

    def get_latest(self, artifact_id: UUID, owner_id: str) -> Optional[Version]:
        self._verify_artifact_owner(artifact_id, owner_id)
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("artifact_id", str(artifact_id))
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return Version.model_validate(result.data[0])

    def _verify_artifact_owner(self, artifact_id: UUID, owner_id: str) -> None:
        a = (
            self.client.table("artifacts")
            .select("work_id")
            .eq("id", str(artifact_id))
            .execute()
        )
        if not a.data:
            raise ValueError("artifact not found")
        w = (
            self.client.table("works")
            .select("project_id")
            .eq("id", a.data[0]["work_id"])
            .execute()
        )
        if not w.data:
            raise ValueError("work not found")
        proj = (
            self.client.table("projects")
            .select("id")
            .eq("id", w.data[0]["project_id"])
            .eq("owner_id", owner_id)
            .execute()
        )
        if not proj.data:
            raise PermissionError("artifact does not belong to caller's project")


# =============================================================================
# EntityRepo
# =============================================================================


class EntityRepo(_Repo):
    def __init__(self, client: Client, table: str = "entities"):
        super().__init__(client, table)

    def create(self, entity: Entity, owner_id: str) -> Entity:
        self._verify_version_owner(entity.version_id, owner_id)
        row = self._entity_to_row(entity)
        result = self.client.table(self.table).insert(row).execute()
        return self._row_to_entity(_first(result.data))

    def get(self, entity_id: UUID, owner_id: str) -> Optional[Entity]:
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("id", str(entity_id))
            .execute()
        )
        if not result.data:
            return None
        self._verify_version_owner(UUID(result.data[0]["version_id"]), owner_id)
        return self._row_to_entity(result.data[0])

    def list_by_version(self, version_id: UUID, owner_id: str) -> list[Entity]:
        self._verify_version_owner(version_id, owner_id)
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("version_id", str(version_id))
            .execute()
        )
        return [self._row_to_entity(r) for r in result.data]

    def delete(self, entity_id: UUID, owner_id: str) -> None:
        e = (
            self.client.table(self.table)
            .select("version_id")
            .eq("id", str(entity_id))
            .execute()
        )
        if not e.data:
            raise ValueError("entity not found")
        self._verify_version_owner(UUID(e.data[0]["version_id"]), owner_id)
        self.client.table(self.table).delete().eq("id", str(entity_id)).execute()

    def _verify_version_owner(self, version_id: UUID, owner_id: str) -> None:
        v = (
            self.client.table("artifact_versions")
            .select("artifact_id")
            .eq("id", str(version_id))
            .execute()
        )
        if not v.data:
            raise ValueError("version not found")
        a = (
            self.client.table("artifacts")
            .select("work_id")
            .eq("id", v.data[0]["artifact_id"])
            .execute()
        )
        if not a.data:
            raise ValueError("artifact not found")
        w = (
            self.client.table("works")
            .select("project_id")
            .eq("id", a.data[0]["work_id"])
            .execute()
        )
        if not w.data:
            raise ValueError("work not found")
        proj = (
            self.client.table("projects")
            .select("id")
            .eq("id", w.data[0]["project_id"])
            .eq("owner_id", owner_id)
            .execute()
        )
        if not proj.data:
            raise PermissionError("version does not belong to caller's project")

    def _entity_to_row(self, entity: Entity) -> dict:
        row: dict = {
            "id": str(entity.id),
            "version_id": str(entity.version_id),
            "kind": entity.kind.value,
            "label": entity.label,
            "start_seconds": entity.span.start_seconds,
            "end_seconds": entity.span.end_seconds,
            "start_beat": entity.span.start_beat,
            "end_beat": entity.span.end_beat,
            "start_measure": entity.span.start_measure,
            "end_measure": entity.span.end_measure,
        }
        if entity.note:
            row["note_pitch"] = entity.note.pitch
            row["note_start_seconds"] = entity.note.start_seconds
            row["note_end_seconds"] = entity.note.end_seconds
            row["note_velocity"] = entity.note.velocity
            row["note_voice"] = entity.note.voice
        if entity.chord:
            row["chord_root"] = entity.chord.root
            row["chord_quality"] = entity.chord.quality
            row["chord_bass"] = entity.chord.bass
            row["chord_start_seconds"] = entity.chord.start_seconds
            row["chord_end_seconds"] = entity.chord.end_seconds
        if entity.cadence:
            row["cadence_kind"] = entity.cadence.kind
            row["cadence_chords"] = entity.cadence.chords
            row["cadence_position_seconds"] = entity.cadence.position_seconds
        return row

    def _row_to_entity(self, row: dict) -> Entity:
        span = Span(
            start_seconds=row.get("start_seconds"),
            end_seconds=row.get("end_seconds"),
            start_beat=row.get("start_beat"),
            end_beat=row.get("end_beat"),
            start_measure=row.get("start_measure"),
            end_measure=row.get("end_measure"),
        )

        note = None
        if row.get("note_pitch") is not None:
            note = NoteEntity(
                pitch=row["note_pitch"],
                start_seconds=row["note_start_seconds"],
                end_seconds=row["note_end_seconds"],
                velocity=row.get("note_velocity", 64),
                voice=row.get("note_voice", 0),
            )

        chord = None
        if row.get("chord_root") is not None:
            chord = ChordEntity(
                root=row["chord_root"],
                quality=row["chord_quality"],
                bass=row.get("chord_bass"),
                start_seconds=row["chord_start_seconds"],
                end_seconds=row["chord_end_seconds"],
            )

        cadence = None
        if row.get("cadence_kind") is not None:
            cadence = Cadence(
                kind=row["cadence_kind"],
                chords=row.get("cadence_chords", []),
                position_seconds=row["cadence_position_seconds"],
            )

        return Entity(
            id=UUID(row["id"]),
            version_id=UUID(row["version_id"]),
            kind=EntityKind(row["kind"]),
            span=span,
            note=note,
            chord=chord,
            cadence=cadence,
            label=row.get("label", ""),
        )


# =============================================================================
# InsightRepo
# =============================================================================


class InsightRepo(_Repo):
    def __init__(self, client: Client, table: str = "insights"):
        super().__init__(client, table)

    def create(self, insight: Insight, owner_id: str) -> Insight:
        self._verify_version_owner(insight.version_id, owner_id)
        row = insight.model_dump(mode="json")
        row["span"] = insight.span.model_dump(mode="json")
        result = self.client.table(self.table).insert(row).execute()
        return Insight.model_validate(_first(result.data))

    def get(self, insight_id: UUID, owner_id: str) -> Optional[Insight]:
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("id", str(insight_id))
            .execute()
        )
        if not result.data:
            return None
        self._verify_version_owner(UUID(result.data[0]["version_id"]), owner_id)
        return Insight.model_validate(result.data[0])

    def list_by_version(self, version_id: UUID, owner_id: str) -> list[Insight]:
        self._verify_version_owner(version_id, owner_id)
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("version_id", str(version_id))
            .execute()
        )
        return [Insight.model_validate(r) for r in result.data]

    def delete(self, insight_id: UUID, owner_id: str) -> None:
        i = (
            self.client.table(self.table)
            .select("version_id")
            .eq("id", str(insight_id))
            .execute()
        )
        if not i.data:
            raise ValueError("insight not found")
        self._verify_version_owner(UUID(i.data[0]["version_id"]), owner_id)
        self.client.table(self.table).delete().eq("id", str(insight_id)).execute()

    def _verify_version_owner(self, version_id: UUID, owner_id: str) -> None:
        v = (
            self.client.table("artifact_versions")
            .select("artifact_id")
            .eq("id", str(version_id))
            .execute()
        )
        if not v.data:
            raise ValueError("version not found")
        a = (
            self.client.table("artifacts")
            .select("work_id")
            .eq("id", v.data[0]["artifact_id"])
            .execute()
        )
        if not a.data:
            raise ValueError("artifact not found")
        w = (
            self.client.table("works")
            .select("project_id")
            .eq("id", a.data[0]["work_id"])
            .execute()
        )
        if not w.data:
            raise ValueError("work not found")
        proj = (
            self.client.table("projects")
            .select("id")
            .eq("id", w.data[0]["project_id"])
            .eq("owner_id", owner_id)
            .execute()
        )
        if not proj.data:
            raise PermissionError("version does not belong to caller's project")


# =============================================================================
# AlignmentRepo
# =============================================================================


class AlignmentRepo(_Repo):
    def __init__(self, client: Client, table: str = "alignments"):
        super().__init__(client, table)

    def create(self, alignment: Alignment, owner_id: str) -> Alignment:
        self._verify_version_owner(alignment.version_id, owner_id)
        data = alignment.model_dump(mode="json")
        result = self.client.table(self.table).insert(data).execute()
        return Alignment.model_validate(_first(result.data))

    def get(self, alignment_id: UUID, owner_id: str) -> Optional[Alignment]:
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("id", str(alignment_id))
            .execute()
        )
        if not result.data:
            return None
        self._verify_version_owner(UUID(result.data[0]["version_id"]), owner_id)
        return Alignment.model_validate(result.data[0])

    def list_by_version(self, version_id: UUID, owner_id: str) -> list[Alignment]:
        self._verify_version_owner(version_id, owner_id)
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("version_id", str(version_id))
            .execute()
        )
        return [Alignment.model_validate(r) for r in result.data]

    def delete(self, alignment_id: UUID, owner_id: str) -> None:
        al = (
            self.client.table(self.table)
            .select("version_id")
            .eq("id", str(alignment_id))
            .execute()
        )
        if not al.data:
            raise ValueError("alignment not found")
        self._verify_version_owner(UUID(al.data[0]["version_id"]), owner_id)
        self.client.table(self.table).delete().eq("id", str(alignment_id)).execute()

    def _verify_version_owner(self, version_id: UUID, owner_id: str) -> None:
        v = (
            self.client.table("artifact_versions")
            .select("artifact_id")
            .eq("id", str(version_id))
            .execute()
        )
        if not v.data:
            raise ValueError("version not found")
        a = (
            self.client.table("artifacts")
            .select("work_id")
            .eq("id", v.data[0]["artifact_id"])
            .execute()
        )
        if not a.data:
            raise ValueError("artifact not found")
        w = (
            self.client.table("works")
            .select("project_id")
            .eq("id", a.data[0]["work_id"])
            .execute()
        )
        if not w.data:
            raise ValueError("work not found")
        proj = (
            self.client.table("projects")
            .select("id")
            .eq("id", w.data[0]["project_id"])
            .eq("owner_id", owner_id)
            .execute()
        )
        if not proj.data:
            raise PermissionError("version does not belong to caller's project")


# =============================================================================
# WorkflowRepo
# =============================================================================


class WorkflowRepo(_Repo):
    def __init__(self, client: Client, table: str = "workflows"):
        super().__init__(client, table)

    def create(self, workflow: Workflow, owner_id: str) -> Workflow:
        self._verify_project_owner(workflow.project_id, owner_id)
        data = workflow.model_dump(mode="json")
        result = self.client.table(self.table).insert(data).execute()
        return Workflow.model_validate(_first(result.data))

    def get(self, workflow_id: UUID, owner_id: str) -> Optional[Workflow]:
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("id", str(workflow_id))
            .execute()
        )
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
        wf = (
            self.client.table(self.table)
            .select("project_id")
            .eq("id", str(workflow_id))
            .execute()
        )
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


# =============================================================================
# JobRepo
# =============================================================================


class JobRepo(_Repo):
    def __init__(self, client: Client, table: str = "jobs"):
        super().__init__(client, table)

    def create(self, job: Job, owner_id: str) -> Job:
        self._verify_workflow_owner(job.workflow_id, owner_id)
        row = self._job_to_row(job)
        result = self.client.table(self.table).insert(row).execute()
        return self._row_to_job(_first(result.data))

    def get(self, job_id: UUID, owner_id: str) -> Optional[Job]:
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("id", str(job_id))
            .execute()
        )
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

    def update_stage(self, job_id: UUID, stage: JobStage, *, owner_id: str, **kwargs) -> Job:
        j = (
            self.client.table(self.table)
            .select("workflow_id")
            .eq("id", str(job_id))
            .execute()
        )
        if not j.data:
            raise ValueError("job not found")
        self._verify_workflow_owner(UUID(j.data[0]["workflow_id"]), owner_id)

        patch: dict = {"stage": stage.value}
        patch.update(kwargs)
        result = (
            self.client.table(self.table)
            .update(patch)
            .eq("id", str(job_id))
            .execute()
        )
        return self._row_to_job(_first(result.data))

    def claim(self, job_id: UUID, worker_id: str) -> Optional[Job]:
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
                    "lease_expires_at": datetime.now(timezone.utc).isoformat(),
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
            "provenance": job.provenance,
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
