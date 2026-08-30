from datetime import UTC, timedelta

from domain.models import utc_now


def test_utc_now_returns_explicit_utc_timestamp():
    now = utc_now()

    assert now.tzinfo is UTC
    assert now.utcoffset() == timedelta(0)
