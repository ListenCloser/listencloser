"""Deterministic server-side validation of model-produced references/actions.

Pydantic shape validation is not enough: a structurally valid reference can
still point at invented entities. This layer drops anything that cannot be
grounded in the supplied context:

- insight reference → the id must exist in the supplied `visibleInsights`.
- notes reference   → every id must come from the supplied selection's
                      `noteIds` (no selection note ids → the reference is
                      dropped, since the model could not have seen any).
- time reference    → finite numbers, `start >= 0`, `end >= start`, and a
                      defensible domain (matching the selection's timeline when
                      one is supplied; no invented cross-domain mappings).
- measure reference → finite integer range with `end >= start`.
- seek/loop action  → finite, non-negative, ordered, defensible domain.
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


def _defensible_domain(context: AskContext) -> str | None:
    """The timeline the user is grounded in, when the context can tell.

    The selection's `timeRange.domain` is the active source's timeline at
    selection time. When no selection exists there is no defensible signal, so
    cross-domain checks are skipped rather than guessed.
    """
    if context.selection is not None and context.selection.timeRange is not None:
        return context.selection.timeRange.domain
    return None


def _time_range_defensible(
    start: float, end: float | None, domain: str, context: AskContext
) -> bool:
    if not _is_finite(start) or start < 0:
        return False
    if end is not None and (not _is_finite(end) or end < start):
        return False
    active_domain = _defensible_domain(context)
    return not (active_domain is not None and domain != active_domain)


def _valid_reference(ref: AskReference, context: AskContext) -> bool:
    if ref.type == "time":
        if ref.domain not in _DOMAINS:
            return False
        return _time_range_defensible(ref.start, ref.end, ref.domain, context)
    if ref.type == "measure":
        if not isinstance(ref.start, int) or ref.start < 1:
            return False
        return not (ref.end is not None and (not isinstance(ref.end, int) or ref.end < ref.start))
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
        return _time_range_defensible(action.seconds, None, action.domain, context)
    if action.type == "loop":
        if action.domain not in _DOMAINS:
            return False
        return _time_range_defensible(action.start, action.end, action.domain, context)
    if action.type == "show_representation":
        return action.representationId in _CANONICAL_REPRESENTATIONS
    return False


def sanitize_response(response: AskResponse, context: AskContext) -> AskResponse:
    """Drop ungrounded references/actions and return the safe answer."""
    references = [
        ref for ref in response.references if _valid_reference(ref, context)
    ]
    actions = [
        action
        for action in (response.suggestedActions or [])
        if _valid_action(action, context)
    ]
    return AskResponse(
        answer=response.answer,
        references=references,
        suggestedActions=actions or None,
    )