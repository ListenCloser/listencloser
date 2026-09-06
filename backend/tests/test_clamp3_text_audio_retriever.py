import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from engines.retrieval.clamp3 import CLaMP3TextAudioRetriever
from engines.retrieval.clamp3_runtime import _overlap, _window_starts


def test_runtime_window_policy_includes_exact_tail_without_duplicate():
    sample_rate = 10
    starts = _window_starts(
        total_samples=33 * sample_rate,
        window_samples=10 * sample_rate,
        hop_samples=5 * sample_rate,
    )

    assert starts == [0, 50, 100, 150, 200, 230]
    assert _overlap(0, 10, 10, 20) is False
    assert _overlap(0, 10, 9.9, 20) is True


def test_retriever_forces_offline_child_and_parses_bounded_result(
    monkeypatch, tmp_path
):
    runtime_python = tmp_path / "python"
    checkout = tmp_path / "clamp3"
    weights = tmp_path / "weights.pth"
    mert = tmp_path / "mert"
    text = tmp_path / "text"
    for path in (runtime_python, weights):
        path.write_bytes(b"x")
    for path in (checkout, mert, text):
        path.mkdir()

    retriever = CLaMP3TextAudioRetriever(
        runtime_python=str(runtime_python),
        checkout_path=str(checkout),
        weight_path=str(weights),
        weight_sha256="a" * 64,
        mert_model_path=str(mert),
        mert_dir_sha256="b" * 64,
        text_model_path=str(text),
        text_dir_sha256="c" * 64,
    )
    monkeypatch.setattr(
        retriever,
        "_required_paths",
        lambda: (runtime_python, checkout, weights, mert, text),
    )
    monkeypatch.setattr(retriever, "_verify_assets", lambda *args: None)

    child_env = {}

    def fake_run(command, **kwargs):
        if command[0] == "ffmpeg":
            Path(command[-1]).write_bytes(b"RIFF-normalized")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        assert command[0] == str(runtime_python)
        output_path = Path(command[command.index("--output") + 1])
        output_path.write_text(
            json.dumps(
                {
                    "candidates": [
                        {
                            "start_seconds": 5.0,
                            "end_seconds": 15.0,
                            "similarity": 0.71,
                        },
                        {
                            "start_seconds": 25.0,
                            "end_seconds": 35.0,
                            "similarity": 0.62,
                        },
                    ],
                    "embedding_dim": 768,
                    "duration_seconds": 60.0,
                    "runtime_seconds": 3.5,
                }
            ),
            encoding="utf-8",
        )
        child_env.update(kwargs["env"])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("engines.retrieval.clamp3.subprocess.run", fake_run)

    result = retriever.retrieve(b"source-audio", "sparse piano", max_matches=2)

    assert len(result.candidates) == 2
    assert result.candidates[0].start_seconds == 5.0
    assert result.embedding_dim == 768
    assert result.provenance["exposure"] == "INTERNAL_ONLY"
    assert result.provenance["commercial_default_eligible"] is False
    assert child_env["HF_HUB_OFFLINE"] == "1"
    assert child_env["HF_DATASETS_OFFLINE"] == "1"
    assert child_env["TRANSFORMERS_OFFLINE"] == "1"


def test_retriever_rejects_malformed_or_out_of_bounds_child_result(
    monkeypatch, tmp_path
):
    runtime_python = tmp_path / "python"
    checkout = tmp_path / "clamp3"
    weights = tmp_path / "weights.pth"
    mert = tmp_path / "mert"
    text = tmp_path / "text"
    for path in (runtime_python, weights):
        path.write_bytes(b"x")
    for path in (checkout, mert, text):
        path.mkdir()

    retriever = CLaMP3TextAudioRetriever()
    monkeypatch.setattr(
        retriever,
        "_required_paths",
        lambda: (runtime_python, checkout, weights, mert, text),
    )
    monkeypatch.setattr(retriever, "_verify_assets", lambda *args: None)

    def fake_run(command, **kwargs):
        if command[0] == "ffmpeg":
            Path(command[-1]).write_bytes(b"RIFF-normalized")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        output_path = Path(command[command.index("--output") + 1])
        output_path.write_text(
            json.dumps(
                {
                    "candidates": [
                        {
                            "start_seconds": 50.0,
                            "end_seconds": 70.0,
                            "similarity": 0.4,
                        }
                    ],
                    "embedding_dim": 768,
                    "duration_seconds": 60.0,
                    "runtime_seconds": 1.0,
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("engines.retrieval.clamp3.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="invalid passage locator"):
        retriever.retrieve(b"audio", "query")


def test_retriever_requires_complete_pinned_runtime():
    retriever = CLaMP3TextAudioRetriever(
        runtime_python=None,
        checkout_path=None,
        weight_path=None,
        weight_sha256=None,
        mert_model_path=None,
        mert_dir_sha256=None,
        text_model_path=None,
        text_dir_sha256=None,
    )

    with pytest.raises(RuntimeError, match="not fully pinned"):
        retriever.retrieve(b"audio", "query")
