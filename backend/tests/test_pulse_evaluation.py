"""Deterministic unit tests for pulse evaluation."""

from __future__ import annotations

import json
import os

import numpy as np
import pytest
from backend.evaluation.analysis_v3.pulse.metrics.beat import (
    BeatF1Result,
    compute_beat_f1,
    match_timestamps,
)
from backend.evaluation.analysis_v3.pulse.metrics.meter import (
    MeterResult,
    compute_meter_accuracy,
)
from backend.evaluation.analysis_v3.pulse.metrics.runtime import (
    generate_synthetic_audio,
)
from backend.evaluation.analysis_v3.pulse.metrics.tempo import (
    TempoResult,
    check_octave_errors,
    compute_tempo_accuracy,
    compute_tempo_error,
)


class TestMatchTimestamps:
    def test_exact_match(self):
        pred = [1.0, 2.0, 3.0]
        ref = [1.0, 2.0, 3.0]
        matched, unmatched_pred, unmatched_ref = match_timestamps(pred, ref, tolerance=0.07)
        assert matched == 3
        assert len(unmatched_pred) == 0
        assert len(unmatched_ref) == 0

    def test_no_match(self):
        pred = [1.0, 2.0, 3.0]
        ref = [10.0, 20.0, 30.0]
        matched, unmatched_pred, unmatched_ref = match_timestamps(pred, ref, tolerance=0.07)
        assert matched == 0
        assert len(unmatched_pred) == 3
        assert len(unmatched_ref) == 3

    def test_partial_match(self):
        pred = [1.0, 2.0, 3.0]
        ref = [1.0, 2.0, 10.0]
        matched, unmatched_pred, unmatched_ref = match_timestamps(pred, ref, tolerance=0.07)
        assert matched == 2
        assert len(unmatched_pred) == 1
        assert len(unmatched_ref) == 1

    def test_tolerance(self):
        pred = [1.0, 2.0, 3.0]
        ref = [1.05, 2.05, 3.05]
        matched, _, _ = match_timestamps(pred, ref, tolerance=0.1)
        assert matched == 3

    def test_tolerance_too_small(self):
        pred = [1.0, 2.0, 3.0]
        ref = [1.1, 2.1, 3.1]
        matched, _, _ = match_timestamps(pred, ref, tolerance=0.05)
        assert matched == 0


class TestComputeBeatF1:
    def test_perfect(self):
        pred = [1.0, 2.0, 3.0]
        ref = [1.0, 2.0, 3.0]
        result = compute_beat_f1(pred, ref, tolerance=0.07)
        assert result.f1 == pytest.approx(1.0)
        assert result.precision == pytest.approx(1.0)
        assert result.recall == pytest.approx(1.0)
        assert result.matched == 3

    def test_no_match(self):
        pred = [1.0, 2.0, 3.0]
        ref = [10.0, 20.0, 30.0]
        result = compute_beat_f1(pred, ref, tolerance=0.07)
        assert result.f1 == pytest.approx(0.0)
        assert result.matched == 0

    def test_empty_reference(self):
        pred = [1.0, 2.0, 3.0]
        ref: list[float] = []
        result = compute_beat_f1(pred, ref, tolerance=0.07)
        assert result.f1 == pytest.approx(0.0)
        assert result.reference == 0

    def test_empty_predicted(self):
        pred: list[float] = []
        ref = [1.0, 2.0, 3.0]
        result = compute_beat_f1(pred, ref, tolerance=0.07)
        assert result.f1 == pytest.approx(0.0)
        assert result.predicted == 0


class TestComputeTempoError:
    def test_exact_match(self):
        result = compute_tempo_error(120.0, 120.0)
        assert result.is_correct is True
        assert result.absolute_error == pytest.approx(0.0)
        assert result.relative_error_pct == pytest.approx(0.0)

    def test_within_tolerance(self):
        result = compute_tempo_error(121.0, 120.0)
        assert result.is_correct is True
        assert result.absolute_error == pytest.approx(1.0)

    def test_outside_tolerance(self):
        result = compute_tempo_error(130.0, 120.0)
        assert result.is_correct is False
        assert result.absolute_error == pytest.approx(10.0)

    def test_custom_tolerance(self):
        assert compute_tempo_error(123.6, 120.0).is_correct is True
        assert compute_tempo_error(123.6, 120.0, tolerance_pct=2.0).is_correct is False

    def test_octave_error(self):
        result = compute_tempo_error(240.0, 120.0)
        assert result.is_octave_error is True
        assert result.is_half_double_error is True

    def test_half_error(self):
        result = compute_tempo_error(60.0, 120.0)
        assert result.is_octave_error is True
        assert result.is_half_double_error is True

    def test_octave_tolerance_is_relative_to_target(self):
        assert compute_tempo_error(249.6, 120.0).is_octave_error is True
        assert compute_tempo_error(62.4, 120.0).is_octave_error is True
        assert compute_tempo_error(250.0, 120.0).is_octave_error is False
        assert compute_tempo_error(62.5, 120.0).is_octave_error is False

    def test_none_predicted(self):
        result = compute_tempo_error(None, 120.0)
        assert result.is_correct is None
        assert result.absolute_error is None

    def test_nonpositive_reference_is_unscored(self):
        result = compute_tempo_error(120.0, 0.0)
        assert result.is_correct is None
        assert result.relative_error_pct is None

    def test_negative_tolerance_rejected(self):
        with pytest.raises(ValueError, match="non-negative"):
            compute_tempo_error(120.0, 120.0, tolerance_pct=-1.0)


class TestComputeTempoAccuracy:
    def test_honors_custom_tolerance(self):
        near = compute_tempo_error(123.6, 120.0)
        doubled = compute_tempo_error(240.0, 120.0)

        default = compute_tempo_accuracy([near, doubled])
        tight = compute_tempo_accuracy([near, doubled], tolerance_pct=2.0)

        assert default["accuracy"] == pytest.approx(0.5)
        assert default["octave_aware_accuracy"] == pytest.approx(1.0)
        assert default["octave_errors"] == 1
        assert default["half_double_errors"] == 1
        assert default["mean_relative_error_pct"] == pytest.approx(51.5)
        assert tight["accuracy"] == pytest.approx(0.0)
        assert tight["octave_aware_accuracy"] == pytest.approx(0.5)

    def test_empty_or_invalid_results_are_unscored(self):
        invalid = compute_tempo_error(120.0, 0.0)
        summary = compute_tempo_accuracy([invalid])
        assert summary["accuracy"] is None
        assert summary["count"] == 0
        assert summary["mean_absolute_error"] is None


class TestCheckOctaveErrors:
    def test_double(self):
        assert check_octave_errors(240.0, 120.0) is True

    def test_half(self):
        assert check_octave_errors(60.0, 120.0) is True

    def test_normal(self):
        assert check_octave_errors(120.0, 120.0) is False

    def test_zero_reference(self):
        assert check_octave_errors(120.0, 0.0) is False


class TestComputeMeterAccuracy:
    def test_correct(self):
        result = compute_meter_accuracy(4, 4, 4, 4)
        assert result.meter_correct is True
        assert result.numerator_correct is True
        assert result.denominator_correct is True

    def test_incorrect_numerator(self):
        result = compute_meter_accuracy(3, 4, 4, 4)
        assert result.meter_correct is False
        assert result.numerator_correct is False
        assert result.denominator_correct is True

    def test_incorrect_denominator(self):
        result = compute_meter_accuracy(4, 8, 4, 4)
        assert result.meter_correct is False
        assert result.numerator_correct is True
        assert result.denominator_correct is False

    def test_none_values(self):
        result = compute_meter_accuracy(None, None, 4, 4)
        assert result.meter_correct is None
        assert result.numerator_correct is None


class TestPulseSummary:
    def test_distribution(self):
        from backend.evaluation.analysis_v3.pulse.run import _distribution

        summary = _distribution([0.1, 0.5, 0.9])
        assert summary["count"] == 3
        assert summary["mean"] == pytest.approx(0.5)
        assert summary["median"] == pytest.approx(0.5)
        assert summary["p25"] == pytest.approx(0.3)
        assert summary["p75"] == pytest.approx(0.7)

    def test_failure_and_metric_summary(self):
        from backend.evaluation.analysis_v3.pulse.run import _summarize_beat_evaluation

        tempo_results = [
            compute_tempo_error(120.0, 120.0),
            compute_tempo_error(240.0, 120.0),
        ]
        rows = [
            {"id": "ok-1", "latency_seconds": 0.2},
            {"id": "ok-2", "latency_seconds": 0.4},
            {"id": "failed", "error": "engine failed"},
        ]

        summary = _summarize_beat_evaluation(
            rows,
            beat_f1_values=[0.8, 1.0],
            downbeat_f1_values=[0.6],
            tempo_results=tempo_results,
        )

        assert summary["completed"] == 2
        assert summary["failed"] == 1
        assert summary["failure_rate"] == pytest.approx(1 / 3, abs=1e-4)
        assert summary["beat_f1"]["mean"] == pytest.approx(0.9)
        assert summary["downbeat_f1"]["count"] == 1
        assert summary["tempo"]["octave_aware_accuracy"] == pytest.approx(1.0)
        assert summary["latency_seconds"]["mean"] == pytest.approx(0.3)


class TestGenerateSyntheticAudio:
    def test_duration(self):
        audio = generate_synthetic_audio(duration_seconds=5.0, sample_rate=22050)
        assert len(audio) == 5 * 22050

    def test_dtype(self):
        audio = generate_synthetic_audio()
        assert audio.dtype == np.float32

    def test_range(self):
        audio = generate_synthetic_audio()
        assert np.max(np.abs(audio)) <= 1.0


class TestManifestParsing:
    def test_diversity_probe(self):
        manifest_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "manifests",
            "diversity_probe.json",
        )
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                manifest = json.load(f)
            assert "clips" in manifest
            assert len(manifest["clips"]) > 0
            for clip in manifest["clips"]:
                assert "id" in clip
                assert "audio_path" in clip


class TestResultSerialization:
    def test_beat_f1_result(self):
        result = BeatF1Result(
            precision=0.9,
            recall=0.8,
            f1=0.85,
            matched=10,
            predicted=11,
            reference=12,
        )
        d = result.to_dict()
        assert d["precision"] == 0.9
        assert d["f1"] == 0.85
        assert d["matched"] == 10

    def test_tempo_result(self):
        result = TempoResult(
            absolute_error=1.5,
            relative_error_pct=1.25,
            is_correct=True,
            is_octave_error=False,
            is_half_double_error=False,
            predicted_bpm=121.5,
            reference_bpm=120.0,
        )
        d = result.to_dict()
        assert d["absolute_error"] == 1.5
        assert d["is_correct"] is True

    def test_meter_result(self):
        result = MeterResult(
            numerator_correct=True,
            denominator_correct=True,
            meter_correct=True,
            predicted_numerator=4,
            predicted_denominator=4,
            reference_numerator=4,
            reference_denominator=4,
        )
        d = result.to_dict()
        assert d["meter_correct"] is True


class TestAdapterUnsupportedCapability:
    def test_unsupported_downbeats(self):
        from backend.evaluation.analysis_v3.pulse.adapters.base import PulseAdapter

        class BeatsOnlyAdapter(PulseAdapter):
            name = "test"
            engine = "test"

            def load(self):
                pass

            def analyze(self, audio, sample_rate):
                from backend.evaluation.analysis_v3.pulse.adapters.base import PulseResult

                return PulseResult(beats=[1.0, 2.0], tempo_bpm=120.0)

            def metadata(self):
                from backend.evaluation.analysis_v3.pulse.adapters.base import PulseMetadata

                return PulseMetadata(
                    candidate="test",
                    engine="test",
                    supports_beats=True,
                    supports_downbeats=False,
                )

        adapter = BeatsOnlyAdapter()
        meta = adapter.metadata()
        assert meta.supports_beats is True
        assert meta.supports_downbeats is False
