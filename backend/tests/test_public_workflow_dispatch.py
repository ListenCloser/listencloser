import pytest
from fastapi import HTTPException

from domain.api.workflows_jobs import _require_public_create_action


@pytest.mark.parametrize("action", ["transform", "perceptual_series", "pitch_contour"])
def test_public_create_workflow_actions_are_explicit(action: str) -> None:
    assert _require_public_create_action(action) == action


@pytest.mark.parametrize(
    "action",
    [
        "generate_continuation",
        "analyze",
        "score",
        "describe",
        "future_worker_registration",
    ],
)
def test_internal_worker_capabilities_are_not_public_actions(action: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _require_public_create_action(action)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Unsupported workflow action"
