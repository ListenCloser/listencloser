"""Focused runtime-boundary tests for the SongFormer challenger."""

from __future__ import annotations

import json
import subprocess

import pytest

import engines.structure.songformer as songformer_module
from engines.structure.songformer import SongFormerEngine


def _runtime_tree(tmp_path):
    runtime_python = tmp_path / "python"
    runtime_python.write_text("placeholder", encoding="utf-8")
    runtime_root = tmp_path / "SongFormer-repo"
    songformer_root = runtime_root / "src" / "SongFormer"
    (songformer_root / "infer").mkdir(parents=True)
    (songformer_root / "infer" / "infer.py").write_text("# placeholder", encoding="utf-8")
    (songformer_root / "ckpts" / "MusicFM").mkdir(parents=True)
    (songformer_root / "ckpts" / "SongFormer.safetensors").write_bytes(b"sf")
    (songformer_root / "ckpts" / "MusicFM" / "pretrained_msd.pt").write_bytes(b"mf")
    (songformer_root / "ckpts" / "MusicFM" / "msd_stats.json").write_text(
        "{}", encoding="utf-8"
    )
    hf_home = tmp_path / "hf-home"
    hf_home.mkdir()
    return runtime_python, runtime_root, hf_home


def test_songformer_requires_explicit_muq_revision(tmp_path):
    runtime_python, runtime_root, hf_home = _runtime_tree(tmp_path)
    engine = SongFormerEngine(
        runtime_python=str(runtime_python),
        runtime_root=str(runtime_root),
        hf_home=str(hf_home),
        muq_revision=None,
    )

    with pytest.raises(RuntimeError, match="SONGFORMER_MUQ_REVISION"):
        engine.analyze(b"RIFF-not-real-audio")


def test_songformer_runs_offline_and_parses_segments(tmp_path, monkeypatch):
    runtime_python, runtime_root, hf_home = _runtime_tree(tmp_path)
    observed = {}
    monkeypatch.setattr(songformer_module, "_verify_md5", lambda path, expected: None)

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["cwd"] = kwargs["cwd"]
        observed["env"] = kwargs["env"]
        output_dir = command[command.index("--output_path") + 1]
        with open(f"{output_dir}/source.json", "w", encoding="utf-8") as handle:
            json.dump(
                [
                    {"start": 0.0, "end": 12.5, "label": "intro"},
                    {"start": 12.5, "end": 42.0, "label": "verse"},
                ],
                handle,
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    engine = SongFormerEngine(
        runtime_python=str(runtime_python),
        runtime_root=str(runtime_root),
        hf_home=str(hf_home),
        muq_revision="pinned-hf-revision",
        cuda_visible_devices="2",
    )

    result = engine.analyze(b"RIFF-not-real-audio", fmt="wav")

    assert observed["command"][:2] == [str(runtime_python), "infer/infer.py"]
    assert observed["env"]["HF_HUB_OFFLINE"] == "1"
    assert observed["env"]["TRANSFORMERS_OFFLINE"] == "1"
    assert observed["env"]["CUDA_VISIBLE_DEVICES"] == "2"
    assert str(hf_home) == observed["env"]["HF_HOME"]
    assert result.segments[0].label == "intro"
    assert result.segments[1].start_seconds == 12.5
    assert result.provenance.parameters["runtime_classification"] == "INTERNAL_ONLY"
    assert result.provenance.parameters["muq_weight_license"] == "CC-BY-NC-4.0"
    assert result.provenance.parameters["muq_revision"] == "pinned-hf-revision"


def test_songformer_zero_exit_without_json_is_failure(tmp_path, monkeypatch):
    runtime_python, runtime_root, hf_home = _runtime_tree(tmp_path)
    monkeypatch.setattr(songformer_module, "_verify_md5", lambda path, expected: None)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, stdout="", stderr="upstream swallowed an item error"
        ),
    )
    engine = SongFormerEngine(
        runtime_python=str(runtime_python),
        runtime_root=str(runtime_root),
        hf_home=str(hf_home),
        muq_revision="pinned-hf-revision",
    )

    with pytest.raises(RuntimeError, match="without producing structure JSON"):
        engine.analyze(b"RIFF-not-real-audio")


def test_songformer_rejects_non_monotonic_segments(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            [
                {"start": 0.0, "end": 10.0, "label": "intro"},
                {"start": 9.0, "end": 20.0, "label": "verse"},
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="non-monotonic"):
        songformer_module._parse_segments(path)
