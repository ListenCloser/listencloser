from uuid import uuid4

from domain.api import _inspector_exposed
from domain.models import Insight


def _insight(kind: str) -> Insight:
    return Insight(
        version_id=uuid4(),
        kind=kind,
        claim="test",
    )


def test_persisted_pydantic_insight_can_be_filtered_for_inspector():
    # Regression: the API previously called `.get()` on this Pydantic model,
    # causing every version with real saved insights to return HTTP 500.
    assert _inspector_exposed(_insight("key")) is True


def test_withheld_capability_stays_hidden():
    assert _inspector_exposed(_insight("cadence")) is False


def test_stale_unknown_capability_is_hidden_instead_of_crashing():
    assert _inspector_exposed(_insight("legacy_unknown_kind")) is False
