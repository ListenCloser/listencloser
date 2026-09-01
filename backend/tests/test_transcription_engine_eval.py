from __future__ import annotations

from engines.base import EngineProvenance, TranscriptionResult
from evaluation.transcription_engine import _transcribe_engine, comparison_payload


class _NamedEngine:
    def __init__(self, name: str) -> None:
        self._name = name

    def transcribe(self, audio_bytes: bytes, fmt: str) -> TranscriptionResult:
        assert audio_bytes == b"wav"
        assert fmt == "wav"
        return TranscriptionResult(
            midi=b"midi",
            wav=b"",
            notes=[{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 80}],
            num_notes=1,
            cleanup_report={},
            provenance=EngineProvenance(engine=self._name, library_version="test"),
        )


def test_explicit_evaluator_bypasses_profiles() -> None:
    seen_names: list[str | None] = []

    def engine_factory(*, name: str | None = None) -> _NamedEngine:
        seen_names.append(name)
        assert name is not None
        return _NamedEngine(name)

    notes, provenance = _transcribe_engine(
        b"wav",
        "tsumugi",
        engine_factory=engine_factory,
    )

    assert seen_names == ["tsumugi"]
    assert [(note.pitch, note.start, note.end) for note in notes] == [(60, 0.0, 0.5)]
    assert provenance == {"engine": "tsumugi", "library_version": "test"}


def test_comparison_payload_reports_candidate_minus_baseline() -> None:
    baseline = [
        {
            "id": "clip",
            "status": "ok",
            "category": "guitar",
            "metrics": {
                "note_f1": 0.5,
                "onset_f1": 0.6,
                "excessive_count": 2,
                "predicted_count": 10,
                "missed_count": 3,
                "reference_count": 10,
            },
            "time_s": 1.0,
        }
    ]
    candidate = [
        {
            "id": "clip",
            "status": "ok",
            "category": "guitar",
            "metrics": {
                "note_f1": 0.7,
                "onset_f1": 0.65,
                "excessive_count": 1,
                "predicted_count": 10,
                "missed_count": 2,
                "reference_count": 10,
            },
            "time_s": 1.5,
        }
    ]

    payload = comparison_payload(
        "real_audio_v1",
        "basic_pitch",
        "tsumugi",
        baseline,
        candidate,
    )

    assert payload["baseline_engine"] == "basic_pitch"
    assert payload["candidate_engine"] == "tsumugi"
    assert payload["delta_candidate_minus_baseline"]["guitar"] == {
        "note_f1": 0.2,
        "onset_f1": 0.05,
        "excessive_rate": -0.1,
        "missed_rate": -0.1,
        "avg_runtime_s": 0.5,
    }
