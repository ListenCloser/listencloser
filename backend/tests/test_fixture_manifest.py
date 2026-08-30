"""Validate the fixture manifest used by the listencloser-autonomous-handoff test-suite.

The manifest lists every fixture (audio clips, MIDI files, MusicXML
scores, paired comparison fixtures, and deliberately invalid files) with
metadata needed for automated tests.  This module checks structural
integrity: valid schema version, non-empty fixture list, unique ids,
and allowed type enums.
"""

import json
from pathlib import Path

import pytest

MANIFEST_CANDIDATES = [
    Path.home() / "Downloads/listencloser-autonomous-handoff/09_FIXTURES/manifest.json",
    Path(__file__).resolve().parents[2] / "fixtures" / "manifest.json",
]

_VALID_TYPES = {"audio", "midi", "musicxml", "pair", "invalid"}


def _find_manifest() -> Path | None:
    for candidate in MANIFEST_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _skip_without_manifest() -> None:
    pytest.skip(
        "external handoff fixture manifest not present "
        f"(looked in {', '.join(str(c) for c in MANIFEST_CANDIDATES)})"
    )


def test_fixture_manifest_valid():
    manifest_path = _find_manifest()
    if manifest_path is None:
        _skip_without_manifest()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["version"] == "1.0"
    assert len(manifest["fixtures"]) >= 10
    for f in manifest["fixtures"]:
        assert "id" in f
        assert "type" in f
        assert "uses" in f


def test_all_fixture_ids_unique():
    manifest_path = _find_manifest()
    if manifest_path is None:
        _skip_without_manifest()

    manifest = json.loads(manifest_path.read_text())
    ids = [f["id"] for f in manifest["fixtures"]]
    assert len(ids) == len(set(ids))


def test_all_fixtures_have_valid_types():
    manifest_path = _find_manifest()
    if manifest_path is None:
        _skip_without_manifest()

    manifest = json.loads(manifest_path.read_text())
    for f in manifest["fixtures"]:
        assert f["type"] in _VALID_TYPES


def test_manifest_has_required_sections():
    manifest_path = _find_manifest()
    if manifest_path is None:
        _skip_without_manifest()

    manifest = json.loads(manifest_path.read_text())
    for key in ("version", "fixtures"):
        assert key in manifest, f"manifest missing top-level key '{key}'"
