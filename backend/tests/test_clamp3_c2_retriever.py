import json
from pathlib import Path
from types import SimpleNamespace

import mido
import pytest

from engines.retrieval.clamp3_c2 import CLaMP3TextPerformanceRetriever
from engines.retrieval.clamp3_c2_runtime import (
    _timed_events,
    _window_starts,
    _window_to_mtf,
)


def test_c2_window_policy_includes_exact_tail_without_duplicate():
    assert _window_starts(33.0, 10.0, 5.0) == [0.0, 5.0, 10.0, 15.0, 20.0, 23.0]
    assert _window_starts(8.0, 10.0, 5.0) == [0.0]


def test_c2_midi_window_uses_performance_seconds_and_m3_compatible_mtf(tmp_path):
    midi_path = tmp_path / "performance.mid"
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name="private title", time=0))
    track.append(mido.Message("note_on", note=60, velocity=80, time=0))
    track.append(mido.Message("note_off", note=60, velocity=0, time=480))
    track.append(mido.Message("note_on", note=67, velocity=90, time=480))
    track.append(mido.Message("note_off", note=67, velocity=0, time=480))
    midi.save(midi_path)

    ticks_per_beat, events, duration_seconds = _timed_events(str(midi_path))

    assert ticks_per_beat == 480
    assert duration_seconds == pytest.approx(1.5)
    assert events[2].seconds == pytest.approx(0.5)
    mtf = _window_to_mtf(
        ticks_per_beat,
        events,
        start_seconds=0.0,
        end_seconds=1.0 + 1e-9,
    )
    assert mtf is not None
    assert mtf.startswith("ticks_per_beat 480\n")
    assert "private title" not in mtf
    assert "note_on" in mtf


def test_c2_retriever_forces_offline_child_and_parses_bounded_result(
    monkeypatch, tmp_path
):
    runtime_python = tmp_path / "python"
    checkout = tmp_path / "clamp3"
    weights = tmp_path / "weights.pth"
    text = tmp_path / "text"
    for path in (runtime_python, weights):
        path.write_bytes(b"x")
    for path in (checkout, text):
        path.mkdir()

    retriever = CLaMP3TextPerformanceRetriever(
        runtime_python=str(runtime_python),
        checkout_path=str(checkout),
        weight_path=str(weights),
        weight_sha256="a" * 64,
        text_model_path=str(text),
        text_dir_sha256="b" * 64,
    )
    monkeypatch.setattr(
        retriever,
        "_required_paths",
        lambda: (runtime_python, checkout, weights, text),
    )
    monkeypatch.setattr(retriever, "_verify_assets", lambda *args: None)

    child_env = {}

    def fake_run(command, **kwargs):
        assert command[0] == str(runtime_python)
        assert "--midi" in command
        assert "--mert-model" not in command
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

    monkeypatch.setattr("engines.retrieval.clamp3_c2.subprocess.run", fake_run)

    result = retriever.retrieve(b"MThd-performance", "sparse piano", max_matches=2)

    assert len(result.candidates) == 2
    assert result.candidates[0].start_seconds == 5.0
    assert result.embedding_dim == 768
    assert result.provenance["model"] == "CLaMP3-C2"
    assert result.provenance["rights_classification"] == "permissive"
    assert result.provenance["canonical_default"] is False
    assert result.provenance["music_modality"] == "performance_midi_mtf"
    assert child_env["HF_HUB_OFFLINE"] == "1"
    assert child_env["HF_DATASETS_OFFLINE"] == "1"
    assert child_env["TRANSFORMERS_OFFLINE"] == "1"


def test_c2_retriever_rejects_out_of_bounds_child_result(monkeypatch, tmp_path):
    runtime_python = tmp_path / "python"
    checkout = tmp_path / "clamp3"
    weights = tmp_path / "weights.pth"
    text = tmp_path / "text"
    for path in (runtime_python, weights):
        path.write_bytes(b"x")
    for path in (checkout, text):
        path.mkdir()

    retriever = CLaMP3TextPerformanceRetriever()
    monkeypatch.setattr(
        retriever,
        "_required_paths",
        lambda: (runtime_python, checkout, weights, text),
    )
    monkeypatch.setattr(retriever, "_verify_assets", lambda *args: None)

    def fake_run(command, **kwargs):
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

    monkeypatch.setattr("engines.retrieval.clamp3_c2.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="invalid passage locator"):
        retriever.retrieve(b"midi", "query")


def test_c2_retriever_requires_complete_pinned_runtime():
    retriever = CLaMP3TextPerformanceRetriever(
        runtime_python=None,
        checkout_path=None,
        weight_path=None,
        weight_sha256=None,
        text_model_path=None,
        text_dir_sha256=None,
    )

    with pytest.raises(RuntimeError, match="not fully pinned"):
        retriever.retrieve(b"midi", "query")
