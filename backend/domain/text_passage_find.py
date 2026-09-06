"""Bounded natural-language passage retrieval within one exact Work.

This is an experimental relation, not a factual detector. A candidate means only
that its CLaMP3 representation is close to the supplied text under the declared
model/runtime. Results are ephemeral and exact-source scoped; no generic vector
index or embedding authority is introduced here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.models import Artifact, ArtifactKind, Version
from domain.work_bundle_repository import WorkBundleSnapshot

TextPassageFindStatus = Literal["supported", "unavailable", "withheld", "failed"]
_ALLOWED_SOURCE_KINDS = {
    ArtifactKind.audio_original,
    ArtifactKind.audio_enhanced,
    ArtifactKind.audio_rendered,
}


class TextPassageFindQuery(BaseModel):
    """One text query over one exact source Version."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1, max_length=500)
    max_matches: int = Field(default=3, ge=1, le=5)


class TextPassageCandidate(BaseModel):
    """One exact source-time candidate proposed by the retrieval method."""

    model_config = ConfigDict(frozen=True)

    rank: int = Field(ge=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    similarity: float = Field(ge=-1, le=1)


class TextPassageFindObservation(BaseModel):
    """Method-qualified text-to-passage proposals for one source Version."""

    model_config = ConfigDict(frozen=True)

    source_version_id: UUID
    query_text: str
    method: Literal["clamp3_text_audio_cosine"] = "clamp3_text_audio_cosine"
    embedding_dim: int = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    runtime_seconds: float | None = Field(default=None, ge=0)
    candidates: list[TextPassageCandidate]
    provenance: dict[str, Any]


class TextPassageFindResult(BaseModel):
    """Truthful availability/result state for experimental text passage Find."""

    model_config = ConfigDict(frozen=True)

    status: TextPassageFindStatus
    observation: TextPassageFindObservation | None = None
    reasons: list[str] = Field(default_factory=list)


def _source_artifact(
    snapshot: WorkBundleSnapshot,
    source_version: Version,
) -> tuple[Artifact | None, list[str]]:
    artifact = next(
        (item for item in snapshot.artifacts if item.id == source_version.artifact_id),
        None,
    )
    if artifact is None or source_version.id not in {
        version.id for version in snapshot.versions_by_artifact.get(source_version.artifact_id, [])
    }:
        return None, ["source Version is not part of the authorized Work snapshot"]
    if artifact.kind not in _ALLOWED_SOURCE_KINDS:
        return None, ["text passage Find requires an audio source Version"]
    return artifact, []


def find_text_passages(
    snapshot: WorkBundleSnapshot,
    *,
    source_version: Version,
    query: TextPassageFindQuery,
    load_source: Callable[[Version], bytes],
    retrieve: Callable[..., Any],
) -> TextPassageFindResult:
    """Load one exact authorized source and run one bounded retrieval request."""

    _, source_reasons = _source_artifact(snapshot, source_version)
    if source_reasons:
        return TextPassageFindResult(status="failed", reasons=source_reasons)

    normalized_text = query.text.strip()
    if not normalized_text:
        return TextPassageFindResult(status="withheld", reasons=["text query is empty"])

    try:
        source_bytes = load_source(source_version)
    except Exception:
        return TextPassageFindResult(
            status="failed",
            reasons=["source audio could not be loaded"],
        )
    if not source_bytes:
        return TextPassageFindResult(status="failed", reasons=["source audio is empty"])

    try:
        retrieval = retrieve(
            source_bytes,
            normalized_text,
            max_matches=query.max_matches,
        )
    except RuntimeError as exc:
        message = str(exc)
        if "not fully pinned" in message or "not found" in message:
            return TextPassageFindResult(
                status="unavailable",
                reasons=["CLaMP3 internal runtime is not provisioned"],
            )
        return TextPassageFindResult(
            status="failed",
            reasons=["CLaMP3 passage retrieval failed"],
        )
    except (TypeError, ValueError):
        return TextPassageFindResult(
            status="withheld",
            reasons=["text passage query is not valid for the retrieval method"],
        )

    candidates = [
        TextPassageCandidate(
            rank=index,
            start_seconds=float(candidate.start_seconds),
            end_seconds=float(candidate.end_seconds),
            similarity=float(candidate.similarity),
        )
        for index, candidate in enumerate(retrieval.candidates, start=1)
    ]
    observation = TextPassageFindObservation(
        source_version_id=source_version.id,
        query_text=normalized_text,
        embedding_dim=int(retrieval.embedding_dim),
        duration_seconds=float(retrieval.duration_seconds),
        runtime_seconds=retrieval.runtime_seconds,
        candidates=candidates,
        provenance=dict(retrieval.provenance),
    )
    return TextPassageFindResult(status="supported", observation=observation)


__all__ = [
    "TextPassageCandidate",
    "TextPassageFindObservation",
    "TextPassageFindQuery",
    "TextPassageFindResult",
    "TextPassageFindStatus",
    "find_text_passages",
]
