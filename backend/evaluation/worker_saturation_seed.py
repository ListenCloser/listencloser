"""Seed isolated production-shaped understand jobs for worker saturation evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4

from domain.models import (
    Artifact,
    ArtifactKind,
    Capability,
    Job,
    Project,
    Version,
    Work,
    Workflow,
    WorkflowKind,
)
from domain.repositories import (
    ArtifactRepo,
    JobRepo,
    ProjectRepo,
    VersionRepo,
    WorkflowRepo,
    WorkRepo,
    get_supabase,
)

_PROJECT_NAME = "Worker saturation benchmark"


def _benchmark_project(client) -> tuple[UUID, str]:
    result = (
        client.table("projects")
        .select("id,owner_id")
        .eq("name", _PROJECT_NAME)
        .limit(1)
        .execute()
    )
    if result.data:
        row = result.data[0]
        return UUID(row["id"]), str(row["owner_id"])

    email = f"worker-saturation-{uuid4()}@example.test"
    created = client.auth.admin.create_user(
        {
            "email": email,
            "password": f"benchmark-{uuid4()}",
            "email_confirm": True,
        }
    )
    user = created.user
    if user is None:
        raise RuntimeError("benchmark auth user was not created")
    owner_id = str(user.id)
    project = ProjectRepo(client).create(
        Project(owner_id=owner_id, name=_PROJECT_NAME, description="Ephemeral CI capacity probe")
    )
    return project.id, owner_id


def _seed_one(
    client,
    *,
    project_id: UUID,
    owner_id: str,
    content: bytes,
    fixture: Path,
    index: int,
) -> str:
    work = WorkRepo(client).create(
        Work(project_id=project_id, title=f"Worker saturation {index + 1}"),
        owner_id,
    )
    artifact = ArtifactRepo(client).create(
        Artifact(work_id=work.id, kind=ArtifactKind.audio_original, mime_type="audio/mp4"),
        owner_id,
    )
    storage_key = f"benchmarks/worker-saturation/{uuid4()}/{fixture.name}"
    client.storage.from_("artifacts").upload(
        storage_key,
        content,
        {"content-type": "audio/mp4"},
    )
    version = VersionRepo(client).create(
        Version(
            artifact_id=artifact.id,
            storage_key=storage_key,
            storage_bucket="artifacts",
            byte_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            created_by=owner_id,
            label=fixture.name,
            metadata={"benchmark": "worker_saturation"},
        ),
        owner_id,
    )
    workflow = WorkflowRepo(client).create(
        Workflow(
            project_id=project_id,
            kind=WorkflowKind.understand,
            target_version_id=version.id,
            parameters={"benchmark": "worker_saturation"},
        ),
        owner_id,
    )
    job = JobRepo(client).create(
        Job(
            workflow_id=workflow.id,
            capability=Capability(name="understand", version="1.0"),
            input_version_ids=[version.id],
            parameters={
                "fmt": fixture.suffix.lstrip(".").lower() or "wav",
                "transcription_profile": "auto",
                "score_engine": "musescore",
            },
            cache_key=None,
            created_by=owner_id,
            provenance={"benchmark": "worker_saturation"},
        ),
        owner_id,
    )
    return str(job.id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()
    if args.jobs < 1:
        raise SystemExit("--jobs must be positive")

    client = get_supabase()
    if client is None:
        raise SystemExit("Supabase service credentials are required")
    content = args.fixture.read_bytes()
    project_id, owner_id = _benchmark_project(client)
    job_ids = [
        _seed_one(
            client,
            project_id=project_id,
            owner_id=owner_id,
            content=content,
            fixture=args.fixture,
            index=index,
        )
        for index in range(args.jobs)
    ]
    print(
        json.dumps(
            {
                "project_id": str(project_id),
                "owner_id": owner_id,
                "fixture": args.fixture.name,
                "fixture_bytes": len(content),
                "job_ids": job_ids,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
