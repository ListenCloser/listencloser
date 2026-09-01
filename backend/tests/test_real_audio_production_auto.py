from __future__ import annotations

from engines.base import EngineProvenance, TranscriptionResult
from evaluation.real_audio import _result_payload, _transcribe_auto


class _AutoEngine:
    def transcribe(self, audio_bytes: bytes, fmt: str) -> TranscriptionResult:
        assert audio_bytes == b"wav"
        assert fmt == "wav"
        return TranscriptionResult(
            midi=b"midi",
            wav=b"",
            notes=[{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 80}],
            num_notes=1,
            cleanup_report={},
            provenance=EngineProvenance(engine="basic_pitch", library_version="test"),
        )


def test_real_audio_evaluator_uses_exact_production_auto_profile() -> None:
    seen_profiles: list[str | None] = []

    def engine_factory(*, profile: str | None = None) -> _AutoEngine:
        seen_profiles.append(profile)
        return _AutoEngine()

    notes, provenance = _transcribe_auto(b"wav", engine_factory=engine_factory)

    assert seen_profiles == ["auto"]
    assert [(note.pitch, note.start, note.end) for note in notes] == [(60, 0.0, 0.5)]
    assert provenance == {"engine": "basic_pitch", "library_version": "test"}


def test_result_payload_preserves_per_clip_provenance() -> None:
    payload = _result_payload(
        "real_audio_v1",
        [
            {
                "id": "guitar",
                "status": "ok",
                "category": "guitar",
                "effective_engine": "basic_pitch",
                "provenance": {"engine": "basic_pitch", "library_version": "test"},
                "metrics": {
                    "note_f1": 0.5,
                    "onset_f1": 0.7,
                    "excessive_count": 1,
                    "predicted_count": 2,
                    "missed_count": 1,
                    "reference_count": 2,
                },
                "time_s": 1.2,
            }
        ],
    )

    assert payload["requested_profile"] == "auto"
    assert payload["rows"][0]["provenance"]["engine"] == "basic_pitch"
    assert payload["summary"]["guitar"]["note_f1"] == 0.5
