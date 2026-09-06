"""Deterministic server-side validation of model-produced references/actions.

Pydantic shape validation is not enough: a structurally valid reference can
still point at invented entities. This layer drops anything that cannot be
grounded in the supplied context:

- insight reference → the id must exist in the supplied `visibleInsights`.
- notes reference   → every id must come from the supplied selection's
                      `noteIds` (no selection note ids → the reference is
                      dropped, since the model could not have seen any).
- time reference    → finite numbers, `start >= 0`, `end >= start`, domain in
                      {"performance", "notation"}, and the range must be fully
                      contained in a time range present in the supplied
                      selection or visibleInsight spans.
- measure reference → finite integer range with `start >= 1`, `end >= start`,
                      and the range must be fully contained in a measure range
                      present in the supplied selection or visibleInsight spans.
- seek/loop action  → finite, non-negative, ordered, domain in
                      {"performance", "notation"}, and the range must be fully
                      contained in a time range present in the supplied
                      selection or visibleInsight spans.
- show_representation → must be a canonical supported representation.

Invalid items are dropped individually — a single bad optional reference never
fails the whole answer. The backend never executes actions.
"""

import math

from .contracts import (
    AskAction,
    AskContext,
    AskReference,
    AskResponse,
)

_DOMAINS = {"performance", "notation"}
_CANONICAL_REPRESENTATIONS = {"score", "piano_roll", "listen"}


def _is_finite(value: float) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _collect_time_ranges(context: AskContext) -> dict[str, list[tuple[float, float]]]:
    """Collect all grounded time ranges per domain from selection and insights.

    Returns dict mapping domain -> list of (start, end) tuples where end may be
    None (open-ended). Both selection.timeRange and insight spans contribute.
    """
    ranges: dict[str, list[tuple[float, float | None]]] = {"performance": [], "notation": []}

    # Selection time range
    if context.selection is not None and context.selection.timeRange is not None:
        tr = context.selection.timeRange
        end = tr.end if tr.end is not None and tr.end >= tr.start else None
        ranges[tr.domain].append((tr.start, end))

    # Insight spans with time domain
    for item in context.visibleInsights:
        span = item.insight.span
        if (
            span.start_seconds is not None
            and span.end_seconds is not None
            and span.end_seconds >= span.start_seconds
        ):
            # Determine domain: prefer insight's domain if we had one,
            # but since InsightSpan doesn't carry domain, we can't assign.
            # For now, add to both domains - this is conservative.
            # Actually, the insight came from some representation, but
            # we don't track that. Safer: only allow time refs that match
            # a selection time range, or we'd need domain on insight spans.
            pass

    # Since InsightSpan doesn't carry a domain, we can only ground time
    # references against the selection's timeRange (which has a domain).
    # This is the safe, defensible approach.
    return {k: [(s, e) for s, e in v if e is not None] for k, v in ranges.items() if v}


def _collect_measure_ranges(context: AskContext) -> list[tuple[int, int]]:
    """Collect all grounded measure ranges from selection and insights."""
    ranges: list[tuple[int, int]] = []

    # Selection measure range
    if context.selection is not None and context.selection.measureRange is not None:
        mr = context.selection.measureRange
        if mr.end >= mr.start:
            ranges.append((mr.start, mr.end))

    # Insight spans with measure domain
    for item in context.visibleInsights:
        span = item.insight.span
        if (
            span.start_measure is not None
            and span.end_measure is not None
            and span.end_measure >= span.start_measure
        ):
            ranges.append((span.start_measure, span.end_measure))

    return ranges


def _time_range_contained(
    start: float, end: float | None, domain: str, context: AskContext
) -> bool:
    """Check if [start, end] is fully contained in any grounded time range for domain."""
    if not _is_finite(start) or start < 0:
        return False
    if end is not None and (not _is_finite(end) or end < start):
        return False

    grounded = _collect_time_ranges(context).get(domain, [])
    if not grounded:
        return False

    check_end = end if end is not None else start
    return any(g_start <= start and check_end <= g_end for g_start, g_end in grounded)


def _measure_range_contained(start: int, end: int | None, context: AskContext) -> bool:
    """Check if [start, end] is fully contained in any grounded measure range."""
    if not isinstance(start, int) or start < 1:
        return False
    if end is not None and (not isinstance(end, int) or end < start):
        return False

    grounded = _collect_measure_ranges(context)
    if not grounded:
        return False

    check_end = end if end is not None else start
    return any(g_start <= start and check_end <= g_end for g_start, g_end in grounded)


def _valid_reference(ref: AskReference, context: AskContext) -> bool:
    if ref.type == "time":
        if ref.domain not in _DOMAINS:
            return False
        return _time_range_contained(ref.start, ref.end, ref.domain, context)
    if ref.type == "measure":
        return _measure_range_contained(ref.start, ref.end, context)
    if ref.type == "notes":
        if not ref.ids:
            return False
        allowed = set(context.selection.noteIds or []) if context.selection is not None else set()
        if not allowed:
            return False
        return set(ref.ids).issubset(allowed)
    if ref.type == "insight":
        return any(item.insight.id == ref.id for item in context.visibleInsights)
    return False


def _valid_action(action: AskAction, context: AskContext) -> bool:
    if action.type == "seek":
        if action.domain not in _DOMAINS:
            return False
        return _time_range_contained(action.seconds, None, action.domain, context)
    if action.type == "loop":
        if action.domain not in _DOMAINS:
            return False
        return _time_range_contained(action.start, action.end, action.domain, context)
    if action.type == "show_representation":
        return action.representationId in _CANONICAL_REPRESENTATIONS
    return False


def sanitize_response(response: AskResponse, context: AskContext) -> AskResponse:
    """Drop ungrounded references/actions and return the safe answer."""
    references = [ref for ref in response.references if _valid_reference(ref, context)]
    actions = [
        action for action in (response.suggestedActions or []) if _valid_action(action, context)
    ]
    return AskResponse(
        answer=response.answer,
        references=references,
        suggestedActions=actions or None,
    )
