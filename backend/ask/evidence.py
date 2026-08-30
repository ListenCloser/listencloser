"""Server-authoritative evidence resolution for grounded Ask requests.

The browser may choose which persisted Insights are relevant to the current UI,
but it is not an authority for musical-analysis content. This module resolves
those requested Insight IDs back to persisted rows, proves their Versions belong
to the already-authorized Work, reapplies Ask exposure policy, and recomputes
selection/whole-work categorization from canonical spans before any evidence is
shown to the LLM or output sanitizer.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from pydantic import ValidationError

from domain.capability_policy import is_exposed
from domain.models import Insight

from .contracts import (
    AskContext,
    AskInsight,
    AskInsightSpan,
    AskSelection,
    AskVisibleInsight,
)


def _requested_insight_ids(context: AskContext) -> list[UUID]:
    """Return unique syntactically valid requested Insight IDs in client order."""

    ids: list[UUID] = []
    seen: set[UUID] = set()
    for item in context.visibleInsights:
        try:
            insight_id = UUID(item.insight.id)
        except (TypeError, ValueError):
            continue
        if insight_id in seen:
            continue
        seen.add(insight_id)
        ids.append(insight_id)
    return ids


def _category(insight: Insight, selection: AskSelection | None) -> str:
    """Mirror the frontend's deterministic temporal Insight categorization."""

    if selection is None or selection.timeRange is None:
        return "whole-work"
    if insight.span.start_seconds is None or insight.span.end_seconds is None:
        return "whole-work"

    selection_start = selection.timeRange.start
    selection_end = selection.timeRange.end
    overlaps = (
        insight.span.start_seconds < selection_end
        and insight.span.end_seconds > selection_start
    )
    return "selection" if overlaps else "unrelated"


def _to_visible_insight(insight: Insight, category: str) -> AskVisibleInsight | None:
    try:
        return AskVisibleInsight(
            insight=AskInsight(
                id=str(insight.id),
                version_id=str(insight.version_id),
                kind=insight.kind,
                claim=insight.claim,
                span=AskInsightSpan.model_validate(insight.span.model_dump()),
                entity_ids=[str(entity_id) for entity_id in insight.entity_ids],
            ),
            category=category,
        )
    except ValidationError:
        return None


def canonicalize_ask_context(
    context: AskContext,
    *,
    persisted_insights: Iterable[Insight],
    allowed_version_ids: set[UUID],
) -> AskContext:
    """Replace client-supplied Insight fields with canonical persisted evidence."""

    requested_ids = _requested_insight_ids(context)
    by_id = {
        insight.id: insight
        for insight in persisted_insights
        if insight.id in requested_ids and insight.version_id in allowed_version_ids
    }

    visible: list[AskVisibleInsight] = []
    for insight_id in requested_ids:
        insight = by_id.get(insight_id)
        if insight is None:
            continue
        try:
            if not is_exposed(insight.kind, "ask"):
                continue
        except KeyError:
            continue

        category = _category(insight, context.selection)
        if category == "unrelated":
            continue
        canonical = _to_visible_insight(insight, category)
        if canonical is not None:
            visible.append(canonical)

    return context.model_copy(update={"visibleInsights": visible})


def _load_rows(sb, table: str, ids: list[UUID]) -> list[dict]:
    if not ids:
        return []
    result = sb.table(table).select("*").in_("id", [str(item) for item in ids]).execute()
    return list(result.data or [])


def load_canonical_ask_context(sb, context: AskContext) -> AskContext:
    """Resolve requested Ask Insights and Work membership in bounded batch queries."""

    requested_ids = _requested_insight_ids(context)
    if not requested_ids:
        return context.model_copy(update={"visibleInsights": []})

    persisted: list[Insight] = []
    for row in _load_rows(sb, "insights", requested_ids):
        try:
            persisted.append(Insight.model_validate(row))
        except ValidationError:
            continue

    version_ids = list({insight.version_id for insight in persisted})
    version_rows = _load_rows(sb, "artifact_versions", version_ids)
    artifact_id_by_version: dict[UUID, UUID] = {}
    for row in version_rows:
        try:
            version_id = UUID(str(row["id"]))
            artifact_id = UUID(str(row["artifact_id"]))
        except (KeyError, TypeError, ValueError):
            continue
        artifact_id_by_version[version_id] = artifact_id

    artifact_ids = list(set(artifact_id_by_version.values()))
    artifact_rows = _load_rows(sb, "artifacts", artifact_ids)
    work_id_by_artifact: dict[UUID, UUID] = {}
    for row in artifact_rows:
        try:
            artifact_id = UUID(str(row["id"]))
            work_id = UUID(str(row["work_id"]))
        except (KeyError, TypeError, ValueError):
            continue
        work_id_by_artifact[artifact_id] = work_id

    allowed_version_ids = {
        version_id
        for version_id, artifact_id in artifact_id_by_version.items()
        if work_id_by_artifact.get(artifact_id) == context.workId
    }
    return canonicalize_ask_context(
        context,
        persisted_insights=persisted,
        allowed_version_ids=allowed_version_ids,
    )
