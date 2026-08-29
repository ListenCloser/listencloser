"""Preflight regressions for heavyweight Structure evaluation candidates."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.analysis_v3.structure.adapters.base import (
    StructureAdapter,
    StructureMetadata,
    StructureResult,
)
from evaluation.analysis_v3.structure.run import run_structure_evaluation


class CountingAdapter(StructureAdapter):
    name = "counting"
    engine = "counting"

    def __init__(self, *, training_datasets: tuple[str, ...] = ()) -> None:
        super().__init__("cpu")
        self.load_calls = 0
        self.analyze_calls = 0
        self._metadata = StructureMetadata(
            candidate=self.name,
            engine=self.engine,
            training_datasets=training_datasets,
        )

    def load(self) -> None:
        self.load_calls += 1
        self._loaded = True

    def analyze(self, audio_path: str) -> StructureResult:
        self.analyze_calls += 1
        return StructureResult(
            segments=[
                {"start": 0.0, "end": 5.0},
                {"start": 5.0, "end": 10.0},
            ]
        )

    def metadata(self) -> StructureMetadata:
        return self._metadata


def _manifest(
    tmp_path: Path,
    *,
    dataset: str = "IndependentSet",
    audio_exists: bool = True,
) -> Path:
    audio_path = tmp_path / "clip.wav"
    if audio_exists:
        audio_path.write_bytes(b"fixture")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "name": "preflight-test",
                "clips": [
                    {
                        "id": "clip-1",
                        "audio": str(audio_path),
                        "category": "full_mix",
                        "dataset": dataset,
                        "reference": {
                            "sections": [
                                {"start": 0.0, "end": 5.0},
                                {"start": 5.0, "end": 10.0},
                            ]
                        },
                    }
                ],
            }
        )
    )
    return manifest_path


def test_training_overlap_is_withheld_without_loading_candidate(tmp_path: Path) -> None:
    adapter = CountingAdapter(training_datasets=("HarmonixSet",))

    result = run_structure_evaluation(
        "counting",
        str(_manifest(tmp_path, dataset="SongFormBench-BHX")),
        adapter=adapter,
    )

    assert result["status"] == "completed"
    assert result["load_seconds"] == 0.0
    assert result["rows"][0]["status"] == "withheld_training_overlap"
    assert adapter.load_calls == 0
    assert adapter.analyze_calls == 0


def test_missing_audio_is_reported_without_loading_candidate(tmp_path: Path) -> None:
    adapter = CountingAdapter()

    result = run_structure_evaluation(
        "counting",
        str(_manifest(tmp_path, audio_exists=False)),
        adapter=adapter,
    )

    assert result["status"] == "completed"
    assert result["load_seconds"] == 0.0
    assert result["rows"][0]["status"] == "blocked_missing_audio"
    assert adapter.load_calls == 0
    assert adapter.analyze_calls == 0


def test_eligible_rows_load_candidate_once_and_score(tmp_path: Path) -> None:
    adapter = CountingAdapter()

    result = run_structure_evaluation(
        "counting",
        str(_manifest(tmp_path)),
        adapter=adapter,
    )

    assert result["status"] == "completed"
    assert result["aggregate"]["clips_scored"] == 1
    assert adapter.load_calls == 1
    assert adapter.analyze_calls == 1
