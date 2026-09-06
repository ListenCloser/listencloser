from pathlib import Path

import pytest
from fastapi import HTTPException

from domain.upload_api import _validate_musicxml_bytes

_FIXTURE = Path(__file__).parents[2] / "tests" / "fixtures" / "source-score.musicxml"


def test_known_valid_source_score_parses_with_production_validator():
    _validate_musicxml_bytes(_FIXTURE.read_bytes())


@pytest.mark.parametrize(
    "content",
    [
        b"<score-partwise>",
        b"<?xml version='1.0'?><html><body>not a score</body></html>",
    ],
)
def test_malformed_or_non_musicxml_fails_closed_with_production_validator(content):
    with pytest.raises(HTTPException) as exc:
        _validate_musicxml_bytes(content)

    assert exc.value.status_code == 422
    assert exc.value.detail == "Invalid or unsupported MusicXML"
