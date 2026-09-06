"""Focused product-contract tests for the experimental Production / Space lens."""

from uuid import uuid4

import numpy as np
import pytest

from production_spatial import build_production_spatial_report


def _tone(seconds: float, amplitude: float, *, sample_rate: int = 48_000) -> np.ndarray:
    time = np.arange(round(seconds * sample_rate), dtype=np.float64) / sample_rate
    return (amplitude * np.sin(2.0 * np.pi * 440.0 * time)).astype(np.float32)


def test_production_spatial_emits_literal_method_qualified_stereo_relations() -> None:
    source_version_id = uuid4()
    quiet = _tone(3.0, 0.05)
    loud = _tone(3.0, 0.4)
    stereo_quiet = np.column_stack([quiet, quiet])
    stereo_loud_side = np.column_stack([loud, -loud])

    report = build_production_spatial_report(
        np.concatenate([stereo_quiet, stereo_loud_side], axis=0),
        sample_rate=48_000,
        source_version_id=source_version_id,
    )

    assert report.source_version_id == source_version_id
    assert report.experimental is True
    assert report.method.id == "pyloudnorm_librosa_mid_side_v1"
    assert report.channel_count == 2
    assert report.windows[0].start_seconds == 0.0
    assert report.windows[1].end_seconds == pytest.approx(6.0)
    relations = {relation.kind: relation for relation in report.relations}
    assert relations["loudness_change"].delta > 10.0
    assert relations["mid_side_change"].delta == pytest.approx(100.0, abs=0.1)
    assert relations["loudness_change"].start_seconds == 0.0
    assert relations["loudness_change"].end_seconds == pytest.approx(6.0)
    assert "pyloudnorm" in relations["loudness_change"].method
    assert "semantic production labels" in report.interpretation


def test_production_spatial_omits_mid_side_relation_for_mono() -> None:
    source_version_id = uuid4()
    first = _tone(3.0, 0.05)
    second = _tone(3.0, 0.2)
    mono = np.concatenate([first, second])[:, np.newaxis]

    report = build_production_spatial_report(
        mono,
        sample_rate=48_000,
        source_version_id=source_version_id,
    )

    assert all(window.side_energy_fraction is None for window in report.windows)
    assert "mid_side_change" not in {relation.kind for relation in report.relations}


def test_production_spatial_rejects_too_short_audio() -> None:
    with pytest.raises(ValueError, match="too short"):
        build_production_spatial_report(
            np.zeros((48_000 * 3, 2), dtype=np.float32),
            sample_rate=48_000,
            source_version_id=uuid4(),
        )
