"""Regression tests for candidate-native Structure batch execution."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from evaluation.analysis_v3.structure.adapters.allin1 import AllInOneStructureAdapter
from evaluation.analysis_v3.structure.adapters.base import (
    StructureAdapter,
    StructureMetadata,
    StructureResult,
)
from evaluation.analysis_v3.structure.run import run_structure_evaluation


def _sections(*boundaries: float) -> list[dict[str, float]]:
    return [
        {"start": start, "end": end} for start, end in zip(boundaries, boundaries[1:], strict=False)
    ]


def _manifest(tmp_path: Path, *, count: int = 2) -> Path:
    clips = []
    for index in range(count):
        audio = tmp_path / f"clip-{index}.wav"
        audio.write_bytes(b"evaluation fixture")
        clips.append(
            {
                "id": f"clip-{index}",
                "audio": str(audio),
                "category": "full_mix",
                "dataset": "IndependentSet",
                "split": "test",
                "source_id": f"fixture-{index}",
                "license": "test-only",
                "reference": {"sections": _sections(0.0, 5.0, 10.0)},
            }
        )
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"name": "batch-test", "clips": clips}))
    return path


class PerClipAdapter(StructureAdapter):
    name = "per-clip"
    engine = "fake"

    def __init__(self) -> None:
        super().__init__("cpu")
        self.calls: list[str] = []

    def load(self) -> None:
        self._loaded = True

    def analyze(self, audio_path: str) -> StructureResult:
        self.calls.append(audio_path)
        return StructureResult(segments=_sections(0.0, 5.0, 10.0))

    def metadata(self) -> StructureMetadata:
        return StructureMetadata(candidate=self.name, engine=self.engine)


class BatchAdapter(StructureAdapter):
    name = "batch"
    engine = "fake"
    supports_batch = True

    def __init__(
        self,
        *,
        result_count: int | None = None,
        batch_error: Exception | None = None,
    ) -> None:
        super().__init__("cpu")
        self.batch_calls: list[list[str]] = []
        self.result_count = result_count
        self.batch_error = batch_error

    def load(self) -> None:
        self._loaded = True

    def analyze(self, audio_path: str) -> StructureResult:
        raise AssertionError("batch-capable adapter should not use per-clip analyze")

    def analyze_many(self, audio_paths: list[str]) -> list[StructureResult]:
        self.batch_calls.append(list(audio_paths))
        if self.batch_error is not None:
            raise self.batch_error
        count = len(audio_paths) if self.result_count is None else self.result_count
        return [
            StructureResult(
                segments=_sections(0.0, 5.0, 10.0),
                metadata={"execution_mode": "native_batch"},
            )
            for _ in range(count)
        ]

    def metadata(self) -> StructureMetadata:
        return StructureMetadata(candidate=self.name, engine=self.engine)


def test_non_batch_adapter_keeps_per_clip_latency_semantics(tmp_path: Path) -> None:
    adapter = PerClipAdapter()
    result = run_structure_evaluation(
        "fake",
        str(_manifest(tmp_path)),
        adapter=adapter,
    )

    assert result["execution_mode"] == "per_clip"
    assert result["eligible_clip_count"] == 2
    assert result["candidate_batch_seconds"] >= 0.0
    assert result["effective_seconds_per_clip"] >= 0.0
    assert result["aggregate"]["clips_scored"] == 2
    assert result["aggregate"]["mean_inference_seconds"] is not None
    assert all("latency_seconds" in row for row in result["rows"])
    assert len(adapter.calls) == 2


def test_batch_adapter_runs_once_without_fabricating_per_clip_latency(tmp_path: Path) -> None:
    adapter = BatchAdapter()
    result = run_structure_evaluation(
        "fake",
        str(_manifest(tmp_path)),
        adapter=adapter,
    )

    assert result["execution_mode"] == "batch"
    assert result["eligible_clip_count"] == 2
    assert result["candidate_batch_seconds"] >= 0.0
    assert result["effective_seconds_per_clip"] == pytest.approx(
        result["candidate_batch_seconds"] / 2,
        abs=1e-4,
    )
    assert result["aggregate"]["clips_scored"] == 2
    assert result["aggregate"]["mean_inference_seconds"] is None
    assert len(adapter.batch_calls) == 1
    assert len(adapter.batch_calls[0]) == 2
    assert all("latency_seconds" not in row for row in result["rows"])
    assert all(
        row["candidate_output_metadata"]["execution_mode"] == "native_batch"
        for row in result["rows"]
    )


def test_batch_result_cardinality_mismatch_fails_closed(tmp_path: Path) -> None:
    adapter = BatchAdapter(result_count=1)
    result = run_structure_evaluation(
        "fake",
        str(_manifest(tmp_path)),
        adapter=adapter,
    )

    assert result["aggregate"]["clips_scored"] == 0
    assert result["aggregate"]["clips_candidate_error"] == 2
    assert result["candidate_batch_seconds"] is not None
    assert all(row["status"] == "candidate_error" for row in result["rows"])
    assert all("cardinality mismatch" in row["error"] for row in result["rows"])


def test_batch_exception_fails_closed_without_fabricating_runtime(tmp_path: Path) -> None:
    adapter = BatchAdapter(batch_error=RuntimeError("upstream batch failed"))
    result = run_structure_evaluation(
        "fake",
        str(_manifest(tmp_path)),
        adapter=adapter,
    )

    assert result["aggregate"]["clips_scored"] == 0
    assert result["aggregate"]["clips_candidate_error"] == 2
    assert result["candidate_batch_seconds"] is None
    assert result["effective_seconds_per_clip"] is None
    assert all(row["status"] == "candidate_error" for row in result["rows"])
    assert all("upstream batch failed" in row["error"] for row in result["rows"])


def test_allin1_uses_upstream_multi_track_api_once() -> None:
    upstream = MagicMock()
    upstream.analyze.return_value = [
        SimpleNamespace(
            segments=[
                SimpleNamespace(start=0.0, end=5.0, label="Intro"),
                SimpleNamespace(start=5.0, end=10.0, label="Verse"),
            ]
        ),
        SimpleNamespace(
            segments=[
                SimpleNamespace(start=0.0, end=4.0, label="Intro"),
                SimpleNamespace(start=4.0, end=10.0, label="Chorus"),
            ]
        ),
    ]
    adapter = AllInOneStructureAdapter(device="cpu")
    adapter._module = upstream
    adapter._loaded = True

    results = adapter.analyze_many(["first.wav", "second.wav"])

    upstream.analyze.assert_called_once_with(
        ["first.wav", "second.wav"],
        model="harmonix-all",
        device="cpu",
    )
    assert len(results) == 2
    assert all(result.ok for result in results)
    assert results[0].segments[0]["label"] == "intro"
    assert results[1].segments[1]["label"] == "chorus"
    assert all(result.metadata["execution_mode"] == "upstream_batch" for result in results)
