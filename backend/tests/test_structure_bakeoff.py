"""Regression tests for the candidate-neutral Structure V1 bakeoff."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation.analysis_v3.structure.adapters.base import (
    StructureAdapter,
    StructureMetadata,
    StructureResult,
)
from evaluation.analysis_v3.structure.adapters.external_json import ExternalJsonStructureAdapter
from evaluation.analysis_v3.structure.adapters.songformer import SongFormerStructureAdapter
from evaluation.analysis_v3.structure.datasets.songformbench import (
    build_songformbench_index_manifest,
    build_songformbench_manifest,
    parse_msa_annotation,
)
from evaluation.analysis_v3.structure.run import run_structure_evaluation


def _sections(*boundaries: float) -> list[dict[str, float]]:
    return [
        {"start": start, "end": end} for start, end in zip(boundaries, boundaries[1:], strict=False)
    ]


def _manifest(
    tmp_path: Path,
    *,
    dataset: str = "IndependentSet",
    split: str = "test",
    audio_exists: bool = True,
    audio_provenance: str | None = None,
) -> Path:
    audio = tmp_path / "clip.wav"
    if audio_exists:
        audio.write_bytes(b"evaluation fixture")
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "name": "structure-test",
                "clips": [
                    {
                        "id": "clip-1",
                        "audio": str(audio),
                        "category": "full_mix",
                        "dataset": dataset,
                        "split": split,
                        "source_id": "fixture-1",
                        "license": "test-only",
                        "audio_provenance": audio_provenance,
                        "reference": {"sections": _sections(0.0, 5.0, 10.0)},
                    }
                ],
            }
        )
    )
    return path


class FakeStructureAdapter(StructureAdapter):
    name = "fake"
    engine = "fake"

    def __init__(self, metadata: StructureMetadata | None = None) -> None:
        super().__init__("cpu")
        self._metadata = metadata or StructureMetadata(candidate="fake", engine="fake")
        self.analyze_calls = 0

    def load(self) -> None:
        self._loaded = True

    def analyze(self, audio_path: str) -> StructureResult:
        self.analyze_calls += 1
        return StructureResult(segments=_sections(0.0, 5.0, 10.0))

    def metadata(self) -> StructureMetadata:
        return self._metadata


def test_runner_uses_shared_metrics_and_preserves_audio_provenance(tmp_path: Path):
    adapter = FakeStructureAdapter()
    result = run_structure_evaluation(
        "fake",
        str(_manifest(tmp_path, audio_provenance="mel_reconstruction")),
        adapter=adapter,
    )

    assert result["status"] == "completed"
    assert result["aggregate"]["clips_scored"] == 1
    assert result["aggregate"]["macro_boundary_f1_05"] == pytest.approx(1.0)
    assert result["aggregate"]["macro_interior_boundary_f1_05"] == pytest.approx(1.0)
    assert result["rows"][0]["evaluation_validity"] == "no_declared_overlap"
    assert result["rows"][0]["audio_provenance"] == "mel_reconstruction"
    assert result["process_peak_rss_mb"] > 0
    assert adapter.analyze_calls == 1


def test_training_overlap_is_withheld_before_inference(tmp_path: Path):
    adapter = FakeStructureAdapter(
        StructureMetadata(
            candidate="overlap",
            engine="fake",
            training_datasets=("HarmonixSet",),
        )
    )
    result = run_structure_evaluation(
        "fake",
        str(_manifest(tmp_path, dataset="SongFormBench-HarmonixSet")),
        adapter=adapter,
    )

    row = result["rows"][0]
    assert row["status"] == "withheld_training_overlap"
    assert row["evaluation_validity"] == "not_independent"
    assert result["aggregate"]["clips_withheld_training_overlap"] == 1
    assert adapter.analyze_calls == 0


def test_songformbench_bhx_is_treated_as_harmonix_overlap(tmp_path: Path):
    adapter = FakeStructureAdapter(
        StructureMetadata(
            candidate="overlap",
            engine="fake",
            training_datasets=("HarmonixSet",),
        )
    )
    result = run_structure_evaluation(
        "fake",
        str(_manifest(tmp_path, dataset="SongFormBench-BHX")),
        adapter=adapter,
    )

    row = result["rows"][0]
    assert row["status"] == "withheld_training_overlap"
    assert row["evaluation_validity"] == "not_independent"
    assert adapter.analyze_calls == 0


def test_training_overlap_override_is_scored_but_labeled(tmp_path: Path):
    adapter = FakeStructureAdapter(
        StructureMetadata(
            candidate="overlap",
            engine="fake",
            training_datasets=("HarmonixSet",),
        )
    )
    result = run_structure_evaluation(
        "fake",
        str(_manifest(tmp_path, dataset="SongFormBench-HarmonixSet")),
        allow_training_overlap=True,
        adapter=adapter,
    )

    assert result["rows"][0]["status"] == "scored"
    assert result["rows"][0]["evaluation_validity"] == "in_sample_override"
    assert adapter.analyze_calls == 1


def test_explicit_held_out_partition_is_distinguished_from_unknown_overlap(tmp_path: Path):
    adapter = FakeStructureAdapter(
        StructureMetadata(
            candidate="split-aware",
            engine="fake",
            training_datasets=("HarmonixSet",),
            held_out_datasets=("HarmonixSet",),
            held_out_partition="test",
            split_source="published split",
        )
    )
    result = run_structure_evaluation(
        "fake",
        str(_manifest(tmp_path, dataset="HarmonixSet", split="test")),
        adapter=adapter,
    )

    assert result["rows"][0]["status"] == "scored"
    assert result["rows"][0]["evaluation_validity"] == "independent_held_out"


def test_songformer_default_metadata_fails_closed_on_released_training_families(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("STRUCTURE_SONGFORMER_TRAINING_DATASETS", raising=False)
    metadata = SongFormerStructureAdapter().metadata()

    assert set(metadata.training_datasets) == {
        "HarmonixSet",
        "SongFormDB-HX",
        "SongFormDB-Ext",
        "SongFormDB-Hook",
        "SongFormDB-Gem",
    }
    assert metadata.checkpoint_license is None


def test_missing_audio_is_reported_without_inference(tmp_path: Path):
    adapter = FakeStructureAdapter()
    result = run_structure_evaluation(
        "fake",
        str(_manifest(tmp_path, audio_exists=False)),
        adapter=adapter,
    )

    assert result["rows"][0]["status"] == "blocked_missing_audio"
    assert adapter.analyze_calls == 0


def test_external_json_adapter_is_shell_free_and_parses_segments(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("STRUCTURE_EXTERNAL_COMMAND", "candidate --input {audio}")
    monkeypatch.setenv("STRUCTURE_EXTERNAL_NAME", "songformer")

    def fake_run(argv, **kwargs):
        assert argv == ["candidate", "--input", "fixture.wav"]
        assert kwargs == {"check": False, "capture_output": True, "text": True}
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"segments": _sections(0.0, 5.0, 10.0)}),
            stderr="",
        )

    monkeypatch.setattr(
        "evaluation.analysis_v3.structure.adapters.external_json.subprocess.run",
        fake_run,
    )
    adapter = ExternalJsonStructureAdapter()
    adapter.load()
    result = adapter.analyze("fixture.wav")

    assert result.ok
    assert result.segments == [
        {"start": 0.0, "end": 5.0, "label": ""},
        {"start": 5.0, "end": 10.0, "label": ""},
    ]
    assert adapter.metadata().candidate == "songformer"


def test_external_json_adapter_requires_command(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("STRUCTURE_EXTERNAL_COMMAND", raising=False)
    with pytest.raises(RuntimeError, match="STRUCTURE_EXTERNAL_COMMAND"):
        ExternalJsonStructureAdapter().load()


def test_parse_songformbench_annotation_and_require_end_marker(tmp_path: Path):
    good = tmp_path / "good.txt"
    good.write_text("0.0 intro\n5.0 verse\n10.0 end\n")
    assert parse_msa_annotation(good) == [
        {"start": 0.0, "end": 5.0, "label": "intro"},
        {"start": 5.0, "end": 10.0, "label": "verse"},
    ]

    bad = tmp_path / "bad.txt"
    bad.write_text("0.0 intro\n5.0 verse\n")
    with pytest.raises(ValueError, match="end"):
        parse_msa_annotation(bad)


def test_manifest_builder_never_invents_missing_audio(tmp_path: Path):
    annotations = tmp_path / "annotations"
    audio = tmp_path / "audio"
    annotations.mkdir()
    audio.mkdir()
    (annotations / "present.txt").write_text("0.0 intro\n5.0 end\n")
    (annotations / "missing.txt").write_text("0.0 intro\n5.0 end\n")
    (audio / "present.wav").write_bytes(b"fixture")
    output = tmp_path / "manifest.json"

    summary = build_songformbench_manifest(
        annotations,
        audio,
        output,
        audio_provenance="mel_reconstruction",
    )
    manifest = json.loads(output.read_text())

    assert summary["annotation_count"] == 2
    assert summary["materialized_clip_count"] == 1
    assert summary["missing_audio_count"] == 1
    assert manifest["clips"][0]["source_id"] == "present"
    assert manifest["clips"][0]["audio_provenance"] == "mel_reconstruction"


def test_canonical_index_filters_source_subset_and_reports_missing_mel_path(tmp_path: Path):
    root = tmp_path / "dataset"
    (root / "audio").mkdir(parents=True)
    (root / "mels").mkdir()
    (root / "audio" / "BC_fixture.wav").write_bytes(b"fixture")
    index = root / "SongFormBench.jsonl"
    entries = [
        {
            "id": "BC_fixture",
            "subset": "CN",
            "audio_path": "audio/BC_fixture.wav",
            "mel_path": "mels/BC_fixture.npy",
            "label_path": "labels/BC_fixture.txt",
            "labels": [
                {"start": 0.0, "label": "intro"},
                {"start": 5.0, "label": "verse"},
                {"start": 10.0, "label": "end"},
            ],
        },
        {
            "id": "BHX_fixture",
            "subset": "HarmonixSet",
            "audio_path": "audio/BHX_fixture.wav",
            "mel_path": "mels/BHX_fixture.npy",
            "label_path": "labels/BHX_fixture.txt",
            "labels": [
                {"start": 0.0, "label": "intro"},
                {"start": 5.0, "label": "end"},
            ],
        },
    ]
    index.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")

    summary = build_songformbench_index_manifest(
        index,
        root,
        tmp_path / "cn.json",
        audio_provenance="mel_reconstruction",
        subsets=("CN",),
    )
    manifest = json.loads((tmp_path / "cn.json").read_text())
    assert summary["materialized_clip_count"] == 1
    assert manifest["clips"][0]["source_id"] == "BC_fixture"
    assert manifest["clips"][0]["dataset"] == "SongFormBench-CN"
    assert manifest["clips"][0]["audio_provenance"] == "mel_reconstruction"

    missing = build_songformbench_index_manifest(
        index,
        root,
        tmp_path / "harmonix.json",
        subsets=("HarmonixSet",),
    )
    assert missing["materialized_clip_count"] == 0
    assert missing["missing_audio"][0]["source_id"] == "BHX_fixture"
    assert missing["missing_audio"][0]["mel_path"].endswith("mels/BHX_fixture.npy")
