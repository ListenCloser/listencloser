from uuid import UUID

from supabase import Client

from domain.models import Artifact, Version
from domain.repositories._base import _first, _Repo


class ArtifactRepo(_Repo):
    def __init__(self, client: Client, table: str = "artifacts"):
        super().__init__(client, table)

    def create(self, artifact: Artifact, owner_id: str) -> Artifact:
        self._verify_work_owner(artifact.work_id, owner_id)
        data = artifact.model_dump(mode="json")
        result = self.client.table(self.table).insert(data).execute()
        return Artifact.model_validate(_first(result.data))

    def get(self, artifact_id: UUID, owner_id: str) -> Artifact | None:
        result = self.client.table(self.table).select("*").eq("id", str(artifact_id)).execute()
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
        w = self.client.table("works").select("project_id").eq("id", str(work_id)).execute()
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
        a = self.client.table(self.table).select("work_id").eq("id", str(artifact_id)).execute()
        if not a.data:
            raise ValueError("artifact not found")
        self._verify_work_owner(UUID(a.data[0]["work_id"]), owner_id)


class VersionRepo(_Repo):
    def __init__(self, client: Client, table: str = "artifact_versions"):
        super().__init__(client, table)

    def create(self, version: Version, owner_id: str) -> Version:
        self._verify_artifact_owner(version.artifact_id, owner_id)
        data = version.model_dump(mode="json")
        result = self.client.table(self.table).insert(data).execute()
        return Version.model_validate(_first(result.data))

    def get(self, version_id: UUID, owner_id: str) -> Version | None:
        result = self.client.table(self.table).select("*").eq("id", str(version_id)).execute()
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

    def get_latest(self, artifact_id: UUID, owner_id: str) -> Version | None:
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
        a = self.client.table("artifacts").select("work_id").eq("id", str(artifact_id)).execute()
        if not a.data:
            raise ValueError("artifact not found")
        w = self.client.table("works").select("project_id").eq("id", a.data[0]["work_id"]).execute()
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
