"""Focused product-contract tests for the experimental Structure Map."""

from uuid import uuid4

import numpy as np
import pytest

from structure_map import build_structure_map


def _tone(seconds: float, frequency: float, *, sample_rate: int = 22_050) -> np.ndarray:
    time = np.arange(round(seconds * sample_rate), dtype=float) / sample_rate
    return (
        0.5 * np.sin(2.0 * np.pi * frequency * time)
        + 0.2 * np.sin(2.0 * np.pi * frequency * 2.0 * time)
    ).astype(np.float32)


def test_structure_map_keeps_exact_source_and_method_specific_repeat_hint() -> None:
    source_version_id = uuid4()
    a = _tone(9.0, 220.0)
    b = _tone(9.0, 660.0)
    audio = np.concatenate([a, b, a])

    report = build_structure_map(
        audio,
        source_version_id=source_version_id,
        novelty_seconds=3.0,
        min_span_seconds=5.0,
    )

    assert report.source_version_id == source_version_id
    assert report.experimental is True
    assert report.method.id == "librosa_recurrence_novelty_v1"
    assert [span.label for span in report.candidate_spans] == ["A", "B", "A?"]
    assert report.candidate_spans[2].recurrence_of == "A"
    assert report.candidate_spans[2].similarity == pytest.approx(1.0, abs=1e-3)
    assert report.candidate_spans[0].start_seconds == 0.0
    assert report.candidate_spans[-1].end_seconds == pytest.approx(27.0, abs=1e-3)
    assert report.candidate_spans[0].end_seconds == pytest.approx(9.0, abs=0.25)
    assert report.candidate_spans[1].end_seconds == pytest.approx(18.0, abs=0.25)
    assert "not verse/chorus/song-form claims" in report.interpretation


def test_structure_map_rejects_non_mono_or_empty_audio() -> None:
    source_version_id = uuid4()

    with pytest.raises(ValueError, match="non-empty mono audio"):
        build_structure_map(np.array([], dtype=np.float32), source_version_id=source_version_id)

    with pytest.raises(ValueError, match="non-empty mono audio"):
        build_structure_map(
            np.zeros((2, 4096), dtype=np.float32), source_version_id=source_version_id
        )
