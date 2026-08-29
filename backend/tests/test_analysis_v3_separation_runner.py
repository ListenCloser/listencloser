from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np

from backend.evaluation.analysis_v3.separation import run as separation_run
from backend.evaluation.analysis_v3.separation.adapters.base import (
    SeparationMetadata,
    SeparationResult,
)
from backend.evaluation.analysis_v3.separation.metrics.runtime import RuntimeMetrics


@dataclass
class _FakeAdapter:
    device: str = "cpu"

    def load(self) -> None:
        return None

    def metadata(self) -> SeparationMetadata:
        return SeparationMetadata(
            candidate="fake",
            model_id="fake/model",
            code_license="MIT",
            weight_license="MIT",
        )

    def separate(self, audio: np.ndarray, sample_rate: int) -> SeparationResult:
        stem = np.asarray(audio, dtype=np.float32)
        return SeparationResult(
            drums=stem,
            bass=stem,
            other=stem,
            metadata={"fixture": True},
        )


def test_downstream_failure_does_not_erase_successful_separation(monkeypatch, tmp_path):
    audio_path = tmp_path / "mix.wav"
    audio_path.write_bytes(b"fixture")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "name": "runner-fixture",
                "clips": [
                    {
                        "id": "track-1",
                        "audio_path": str(audio_path),
                        "reference_beats": [0.0, 0.5, 1.0],
                    }
                ],
            }
        )
    )

    monkeypatch.setattr(separation_run, "_load_adapter", lambda candidate, device: _FakeAdapter())
    monkeypatch.setattr(
        separation_run,
        "_load_audio",
        lambda path, target_sr=44100: (np.zeros(100, dtype=np.float32), target_sr),
    )

    def fail_beat(*args, **kwargs):
        raise RuntimeError("beat detector failed")

    monkeypatch.setattr(separation_run, "compare_beat_f1_mixture_vs_stem", fail_beat)

    result = separation_run.run_separation_evaluation("fake", str(manifest_path))

    row = result["results"][0]
    assert row["status"] == "ok"
    assert "beat detector failed" in row["downstream_errors"]["beat_f1_drums"]
    assert result["summary"]["separation_succeeded_clips"] == 1
    assert result["summary"]["separation_failed_clips"] == 0
    assert result["summary"]["downstream_task_failures"] == 1


def test_missing_audio_is_counted_and_preserved_in_results(monkeypatch, tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "name": "missing-audio-fixture",
                "clips": [{"id": "missing", "audio_path": str(tmp_path / "missing.wav")}],
            }
        )
    )
    monkeypatch.setattr(separation_run, "_load_adapter", lambda candidate, device: _FakeAdapter())

    result = separation_run.run_separation_evaluation("fake", str(manifest_path))

    assert result["results"][0]["status"] == "skipped_missing_audio"
    assert result["summary"]["manifest_clips"] == 1
    assert result["summary"]["missing_audio_clips"] == 1


def test_operational_three_minute_probe_has_no_second_long_warmup(monkeypatch):
    adapter = _FakeAdapter()
    calls: list[tuple[float, int, int]] = []

    monkeypatch.setattr(separation_run, "_load_adapter", lambda candidate, device: adapter)
    monkeypatch.setattr(
        separation_run,
        "generate_synthetic_audio",
        lambda duration_seconds: np.zeros(int(duration_seconds * 10), dtype=np.float32),
    )

    def fake_measure_latency(adapter, audio, sample_rate, num_runs, warmup_runs):
        duration = len(audio) / 10.0
        calls.append((duration, num_runs, warmup_runs))
        return RuntimeMetrics(
            latency_seconds=1.0,
            latency_min=1.0,
            latency_max=1.0,
            latency_p95=1.0,
            real_time_factor=0.1,
            process_max_rss_mb=100.0,
            num_runs=num_runs,
            audio_duration_seconds=duration,
            device="cpu",
        )

    monkeypatch.setattr(separation_run, "measure_latency", fake_measure_latency)
    monkeypatch.setattr(separation_run, "check_determinism", lambda *args, **kwargs: True)

    result = separation_run.run_operational_evaluation("fake")

    assert calls == [(10.0, 2, 1), (30.0, 2, 1), (180.0, 1, 0)]
    assert result["latency_3min"]["real_time_factor"] == 0.1


def test_result_filename_includes_task_and_manifest():
    filename = separation_run._result_filename(
        "demucs",
        "separation",
        "BabySlakh 4-Stem Reference v1",
    )
    assert filename == "demucs-separation-babyslakh-4-stem-reference-v1.json"
