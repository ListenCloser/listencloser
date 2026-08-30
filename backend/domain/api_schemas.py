"""Public response DTOs for the domain API.

Keep composite wire shapes explicit so FastAPI can publish an authoritative
OpenAPI contract instead of falling back to untyped JSON responses.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from domain.models import Artifact, Job, Version, Work, Workflow
from domain.relation_findings import GroundedRelationFinding


class WorkArtifactBundleResponse(BaseModel):
    artifact: Artifact
    versions: list[Version]
    latest_version: Version | None = None
    signed_url: str | None = None


class WorkBundleResponse(BaseModel):
    work: Work
    artifacts: list[WorkArtifactBundleResponse]
    jobs: list[Job]


class DeletedWorkResponse(BaseModel):
    deleted: str


class UploadArtifactResponse(BaseModel):
    artifact: Artifact
    version: Version


class WorkflowJobResponse(BaseModel):
    workflow: Workflow
    job: Job


class VersionResourceResponse(BaseModel):
    version: Version
    artifact: Artifact
    signed_url: str


class PerceptualSpanComparisonResponse(BaseModel):
    status: Literal["supported", "unavailable", "withheld", "failed"]
    evidence_report_version_id: UUID | None = None
    finding: GroundedRelationFinding | None = None
    reasons: list[str] = Field(default_factory=list)
