"""Bounded natural-language passage retrieval within one exact Work.

This is an experimental relation, not a factual detector. A candidate means only
that one directly-related performance-MIDI passage is close to the supplied text
under the declared CLaMP3 C2 method. Results are ephemeral and exact-source
scoped; no generic vector index or embedding authority is introduced here.
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
    performance_version_id: UUID
    query_text: str
    method: Literal["clamp3_c2_text_performance_cosine"] = "clamp3_c2_text_performance_cosine"
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


def _artifact_for_version(
    snapshot: WorkBundleSnapshot,
    version: Version,
) -> Artifact | None:
    artifact = next(
        (item for item in snapshot.artifacts if item.id == version.artifact_id),
        None,
    )
    if artifact is None:
        return None
    authorized_ids = {
        item.id for item in snapshot.versions_by_artifact.get(version.artifact_id, [])
    }
    return artifact if version.id in authorized_ids else None


def _validate_source(
    snapshot: WorkBundleSnapshot,
    source_version: Version,
) -> list[str]:
    artifact = _artifact_for_version(snapshot, source_version)
    if artifact is None:
        return ["source Version is not part of the authorized Work snapshot"]
    if artifact.kind not in _ALLOWED_SOURCE_KINDS:
        return ["text passage Find requires an audio source Version"]
    return []


def _validate_performance(
    snapshot: WorkBundleSnapshot,
    *,
    source_version: Version,
    performance_version: Version,
) -> tuple[TextPassageFindStatus | None, list[str]]:
    artifact = _artifact_for_version(snapshot, performance_version)
    if artifact is None:
        return "failed", ["performance Version is not part of the authorized Work snapshot"]
    if artifact.kind != ArtifactKind.midi_performance:
        return "withheld", ["CLaMP3 C2 Find requires an exact performance-MIDI Version"]
    if performance_version.parent_version_id != source_version.id:
        return "withheld", [
            "performance MIDI is not directly parented to the exact source audio Version"
        ]
    return None, []


def find_text_passages(
    snapshot: WorkBundleSnapshot,
    *,
    source_version: Version,
    performance_version: Version,
    query: TextPassageFindQuery,
    load_performance: Callable[[Version], bytes],
    retrieve: Callable[..., Any],
) -> TextPassageFindResult:
    """Run bounded C2 retrieval over one exact source/performance Version pair."""

    source_reasons = _validate_source(snapshot, source_version)
    if source_reasons:
        return TextPassageFindResult(status="failed", reasons=source_reasons)

    performance_status, performance_reasons = _validate_performance(
        snapshot,
        source_version=source_version,
        performance_version=performance_version,
    )
    if performance_status is not None:
        return TextPassageFindResult(
            status=performance_status,
            reasons=performance_reasons,
        )

    normalized_text = query.text.strip()
    if not normalized_text:
        return TextPassageFindResult(status="withheld", reasons=["text query is empty"])

    try:
        performance_bytes = load_performance(performance_version)
    except Exception:
        return TextPassageFindResult(
            status="failed",
            reasons=["performance MIDI could not be loaded"],
        )
    if not performance_bytes:
        return TextPassageFindResult(
            status="failed",
            reasons=["performance MIDI is empty"],
        )

    try:
        retrieval = retrieve(
            performance_bytes,
            normalized_text,
            max_matches=query.max_matches,
        )
    except RuntimeError as exc:
        message = str(exc)
        if "not fully pinned" in message or "not found" in message:
            return TextPassageFindResult(
                status="unavailable",
                reasons=["CLaMP3 C2 runtime is not provisioned"],
            )
        return TextPassageFindResult(
            status="failed",
            reasons=["CLaMP3 C2 passage retrieval failed"],
        )
    except (TypeError, ValueError):
        return TextPassageFindResult(
            status="withheld",
            reasons=["text passage query is not valid for the CLaMP3 C2 method"],
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
        performance_version_id=performance_version.id,
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
