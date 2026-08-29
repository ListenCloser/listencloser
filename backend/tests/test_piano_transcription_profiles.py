from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pretty_midi

from engines.base import EngineProvenance, TranscriptionResult
from evaluation.piano_transcription_profiles import run_profile_comparison


def _write_midi(path: Path, notes: list[tuple[int, float, float]]) -> None:
    midi = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=0)
    for pitch, start, end in notes:
        instrument.notes.append(
            pretty_midi.Note(
                velocity=80,
                pitch=pitch,
                start=start,
                end=end,
            )
        )
    midi.instruments.append(instrument)
    midi.write(str(path))


class _FakeEngine:
    def __init__(self, profile: str, *, fail: bool = False) -> None:
        self.profile = profile
        self.fail = fail

    def transcribe(self, audio_bytes: bytes, fmt: str, **kwargs: Any) -> TranscriptionResult:
        del audio_bytes, fmt, kwargs
        if self.fail:
            raise RuntimeError(f"{self.profile} failed")

        notes = [
            {"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 80},
        ]
        if self.profile == "auto":
            notes.append(
                {"pitch": 72, "start": 0.75, "end": 0.9, "velocity": 55}
            )
        engine = "transkun" if self.profile == "solo_piano" else "basic_pitch"
        model = "transkun_2.0" if engine == "transkun" else None
        return TranscriptionResult(
            midi=b"midi",
            wav=b"wav",
            notes=notes,
            num_notes=len(notes),
            cleanup_report={"profile": f"product-{self.profile}"},
            provenance=EngineProvenance(
                engine=engine,
                library_version="test-version",
                model=model,
                parameters={"test": True},
            ),
            tempo_is_placeholder=engine == "basic_pitch",
            meter_is_placeholder=engine == "basic_pitch",
            supports_meter=False,
        )


class _FakeFactory:
    def __init__(self, *, failing_profile: str | None = None) -> None:
        self.profiles: list[str] = []
        self.failing_profile = failing_profile

    def __call__(self, *, profile: str, **kwargs: Any) -> _FakeEngine:
        del kwargs
        self.profiles.append(profile)
        return _FakeEngine(profile, fail=profile == self.failing_profile)


def _manifest(
    tmp_path: Path,
    *,
    include_reference: bool = True,
) -> Path:
    (tmp_path / "clip.wav").write_bytes(b"fake-audio")
    clip: dict[str, Any] = {
        "id": "piano",
        "audio": "clip.wav",
        "category": "solo_piano",
        "dataset": "test-set",
        "split": "test",
        "source_id": "piece-1",
        "license": "test-license",
    }
    if include_reference:
        _write_midi(tmp_path / "reference.mid", [(60, 0.0, 0.5)])
        clip["reference_midi"] = "reference.mid"

    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "name": "piano_profiles_test",
                "clips": [clip],
            }
        )
    )
    return path


def _fingerprint(provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": provenance.get("model"),
        "sha256": f"fake-{provenance['engine']}",
        "reason": None,
    }


def test_profile_comparison_uses_exact_requested_profiles_and_records_evidence(
    tmp_path: Path,
) -> None:
    factory = _FakeFactory()
    payload = run_profile_comparison(
        str(_manifest(tmp_path)),
        hello_ai_sha="deadbeef",
        engine_factory=factory,
        checkpoint_resolver=_fingerprint,
    )

    assert factory.profiles == ["auto", "solo_piano"]
    assert len(payload["rows"]) == 2
    rows = {row["requested_profile"]: row for row in payload["rows"]}

    auto = rows["auto"]
    assert auto["status"] == "measured"
    assert auto["effective_engine"] == "basic_pitch"
    assert auto["cleanup_report"] == {"profile": "product-auto"}
    assert auto["checkpoint"]["sha256"] == "fake-basic_pitch"
    assert auto["metrics"]["onset_precision"] == 0.5
    assert auto["metrics"]["onset_recall"] == 1.0
    assert auto["metrics"]["onset_f1"] == 0.6667
    assert auto["note_count_ratio"] == 2.0
    assert auto["metrics"]["excessive_count"] == 1

    solo = rows["solo_piano"]
    assert solo["status"] == "measured"
    assert solo["effective_engine"] == "transkun"
    assert solo["provenance"]["model"] == "transkun_2.0"
    assert solo["metrics"]["note_f1"] == 1.0
    assert solo["duration_error"]["p95_absolute_seconds"] == 0.0
    assert solo["clip_provenance"]["source_id"] == "piece-1"

    assert payload["summary"]["auto"]["measured"] == 1
    assert payload["summary"]["solo_piano"]["macro_note_f1"] == 1.0


def test_profile_comparison_retains_unscored_rows_without_reference_midi(
    tmp_path: Path,
) -> None:
    factory = _FakeFactory()
    payload = run_profile_comparison(
        str(_manifest(tmp_path, include_reference=False)),
        hello_ai_sha="deadbeef",
        engine_factory=factory,
        checkpoint_resolver=_fingerprint,
    )

    assert len(payload["rows"]) == 2
    assert {row["status"] for row in payload["rows"]} == {"ineligible"}
    assert all(row["metrics"] is None for row in payload["rows"])
    assert all(row["reference_midi"]["status"] == "not_provided" for row in payload["rows"])
    assert payload["summary"]["auto"]["ineligible"] == 1
    assert payload["summary"]["solo_piano"]["ineligible"] == 1


def test_profile_comparison_records_failed_profile_instead_of_dropping_it(
    tmp_path: Path,
) -> None:
    factory = _FakeFactory(failing_profile="solo_piano")
    payload = run_profile_comparison(
        str(_manifest(tmp_path)),
        hello_ai_sha="deadbeef",
        engine_factory=factory,
        checkpoint_resolver=_fingerprint,
    )

    rows = {row["requested_profile"]: row for row in payload["rows"]}
    assert rows["auto"]["status"] == "measured"
    assert rows["solo_piano"]["status"] == "failed"
    assert rows["solo_piano"]["error"] == "solo_piano failed"
    assert payload["summary"]["solo_piano"]["failed"] == 1
