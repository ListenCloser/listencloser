from uuid import UUID

from supabase import Client

from domain.models import Project, Work
from domain.repositories._base import _first, _Repo


class ProjectRepo(_Repo):
    def __init__(self, client: Client, table: str = "projects"):
        super().__init__(client, table)

    def create(self, project: Project) -> Project:
        data = project.model_dump(mode="json")
        result = self.client.table(self.table).insert(data).execute()
        return Project.model_validate(_first(result.data))

    def get(self, project_id: UUID, owner_id: str) -> Project | None:
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
        result = self.client.table(self.table).update(data).eq("id", str(project.id)).execute()
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


class WorkRepo(_Repo):
    def __init__(self, client: Client, table: str = "works"):
        super().__init__(client, table)

    def create(self, work: Work, owner_id: str) -> Work:
        self._verify_project(work.project_id, owner_id)
        data = work.model_dump(mode="json")
        result = self.client.table(self.table).insert(data).execute()
        return Work.model_validate(_first(result.data))

    def get(self, work_id: UUID, owner_id: str) -> Work | None:
        result = self.client.table(self.table).select("*").eq("id", str(work_id)).execute()
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
        self._verify_work_owner(work.id, owner_id)
        self._verify_project(work.project_id, owner_id)
        data = work.model_dump(mode="json")
        result = self.client.table(self.table).update(data).eq("id", str(work.id)).execute()
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
        w = self.client.table(self.table).select("project_id").eq("id", str(work_id)).execute()
        if not w.data:
            raise ValueError("work not found")
        self._verify_project(UUID(w.data[0]["project_id"]), owner_id)
