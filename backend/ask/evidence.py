"""Server-authoritative evidence resolution for grounded Ask requests.

The browser may choose which persisted Insights are relevant to the current UI,
but it is not an authority for musical-analysis content. This module proves the
requested Work's Version set first, then resolves only requested Insight IDs
inside that set, reapplies Ask exposure policy, and recomputes selection/
whole-work categorization from canonical spans before any evidence is shown to
the LLM or output sanitizer.
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


def _uuid_column(rows: list[dict], column: str) -> list[UUID]:
    values: list[UUID] = []
    for row in rows:
        try:
            values.append(UUID(str(row[column])))
        except (KeyError, TypeError, ValueError):
            continue
    return values


def _load_allowed_version_ids(sb, work_id: UUID) -> set[UUID]:
    artifact_result = (
        sb.table("artifacts").select("id").eq("work_id", str(work_id)).execute()
    )
    artifact_ids = _uuid_column(list(artifact_result.data or []), "id")
    if not artifact_ids:
        return set()

    version_result = (
        sb.table("artifact_versions")
        .select("id")
        .in_("artifact_id", [str(item) for item in artifact_ids])
        .execute()
    )
    return set(_uuid_column(list(version_result.data or []), "id"))


def _load_authorized_insights(
    sb,
    requested_ids: list[UUID],
    allowed_version_ids: set[UUID],
) -> list[Insight]:
    if not requested_ids or not allowed_version_ids:
        return []

    result = (
        sb.table("insights")
        .select("*")
        .in_("id", [str(item) for item in requested_ids])
        .in_("version_id", [str(item) for item in allowed_version_ids])
        .execute()
    )
    persisted: list[Insight] = []
    for row in list(result.data or []):
        try:
            persisted.append(Insight.model_validate(row))
        except ValidationError:
            continue
    return persisted


def load_canonical_ask_context(sb, context: AskContext) -> AskContext:
    """Resolve requested Ask Insights only inside the authorized Work's Versions."""

    requested_ids = _requested_insight_ids(context)
    if not requested_ids:
        return context.model_copy(update={"visibleInsights": []})

    # Work ownership is established by the API before this function runs. Build
    # the authorized Version set first so a service-role query never loads an
    # arbitrary foreign Insight row merely because the client supplied its ID.
    allowed_version_ids = _load_allowed_version_ids(sb, context.workId)
    persisted = _load_authorized_insights(sb, requested_ids, allowed_version_ids)
    return canonicalize_ask_context(
        context,
        persisted_insights=persisted,
        allowed_version_ids=allowed_version_ids,
    )
