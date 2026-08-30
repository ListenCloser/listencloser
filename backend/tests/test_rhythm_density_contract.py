"""Truthfulness contract for production rhythm-density evidence."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pretty_midi

import analyze
from domain import capabilities
from domain.models import Capability, Job


def _write_midi(path: Path, onsets: list[float]) -> None:
    midi = pretty_midi.PrettyMIDI(initial_tempo=120)
    instrument = pretty_midi.Instrument(program=0)
    for onset in onsets:
        instrument.notes.append(
            pretty_midi.Note(
                velocity=80,
                pitch=60,
                start=onset,
                end=onset + 0.2,
            )
        )
    midi.instruments.append(instrument)
    midi.write(str(path))


def test_seconds_density_is_explicit_events_per_second() -> None:
    windows = analyze._compute_windowed_density(
        [0.0, 0.5, 1.0, 1.5],
        duration=2.25,
        window=2.0,
        step=1.0,
    )

    assert windows[0] == {
        "start": 0.0,
        "end": 2.0,
        "density": 2.0,
        "mode": "seconds",
        "unit": "events_per_second",
        "coordinate_unit": "seconds",
        "window_size": 2.0,
        "step_size": 1.0,
    }
    # The tail window uses its actual seconds denominator instead of silently
    # pretending it is another full two-second window.
    assert windows[-1]["window_size"] == 0.25
    assert windows[-1]["unit"] == "events_per_second"


def test_beat_relative_density_is_normalized_events_per_beat() -> None:
    windows = analyze._compute_beat_relative_density(
        [0.0, 0.5, 1.0, 1.5],
        [0.0, 1.0, 2.0, 3.0, 4.0],
        window_beats=2,
        step_beats=1,
    )

    assert windows[0]["start"] == 0.0
    assert windows[0]["end"] == 2.0
    assert windows[0]["density"] == 2.0
    assert windows[0]["mode"] == "beat_relative"
    assert windows[0]["unit"] == "events_per_beat"
    assert windows[0]["coordinate_unit"] == "beats"
    assert windows[0]["window_size"] == 2.0
    assert windows[0]["step_size"] == 1.0


def test_equivalent_event_rate_is_stable_across_beat_window_lengths() -> None:
    onsets = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
    beats = [0.0, 1.0, 2.0, 3.0, 4.0]

    one_beat = analyze._compute_beat_relative_density(
        onsets,
        beats,
        window_beats=1,
        step_beats=1,
    )
    two_beats = analyze._compute_beat_relative_density(
        onsets,
        beats,
        window_beats=2,
        step_beats=1,
    )

    assert {window["density"] for window in one_beat} == {2.0}
    assert {window["density"] for window in two_beats} == {2.0}


def test_beat_step_is_honored() -> None:
    windows = analyze._compute_beat_relative_density(
        [0.25, 1.25, 2.25, 3.25, 4.25, 5.25],
        [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        window_beats=2,
        step_beats=2,
    )

    assert [window["start"] for window in windows] == [0.0, 2.0, 4.0]
    assert [window["end"] for window in windows] == [2.0, 4.0, 6.0]


def test_incomplete_beat_tail_is_not_emitted() -> None:
    windows = analyze._compute_beat_relative_density(
        [0.25, 1.25, 2.25],
        [0.0, 1.0, 2.0, 3.0],
        window_beats=2,
        step_beats=1,
    )

    assert [(window["start"], window["end"]) for window in windows] == [
        (0.0, 2.0),
        (1.0, 3.0),
    ]
    assert all(window["window_size"] == 2.0 for window in windows)


def test_invalid_beat_grid_fails_closed() -> None:
    assert (
        analyze._compute_beat_relative_density(
            [0.5, 1.5],
            [0.0, 1.0, 1.0, 2.0],
            window_beats=1,
            step_beats=1,
        )
        == []
    )


def test_midi_rhythm_keeps_seconds_fallback_out_of_promoted_fields(tmp_path: Path) -> None:
    midi_path = tmp_path / "rhythm.mid"
    _write_midi(midi_path, [0.0, 0.5, 1.0, 1.5, 2.0])

    result = analyze._midi_rhythm(str(midi_path), pulse=None)

    assert result is not None
    assert result["note_density_over_time"] == []
    assert result["onset_density_over_time"] == []
    assert result["note_density_seconds_over_time"]
    assert result["note_density_seconds_over_time"][0]["unit"] == "events_per_second"


def test_midi_rhythm_promotes_only_self_describing_beat_density(tmp_path: Path) -> None:
    midi_path = tmp_path / "rhythm.mid"
    _write_midi(midi_path, [0.0, 0.5, 1.0, 1.5, 2.0, 2.5])

    result = analyze._midi_rhythm(
        str(midi_path),
        pulse={"beats": [0.0, 1.0, 2.0, 3.0], "bpm": 60.0},
    )

    assert result is not None
    windows = result["note_density_over_time"]
    assert windows
    assert all(window["mode"] == "beat_relative" for window in windows)
    assert all(window["unit"] == "events_per_beat" for window in windows)
    assert all(window["window_size"] == 2.0 for window in windows)
    assert all(window["step_size"] == 1.0 for window in windows)


def _minimal_analysis(note_density: list[dict]) -> dict:
    return {
        "key": None,
        "tempo": None,
        "time_signature": None,
        "chords": [],
        "roman_numerals": [],
        "cadences": [],
        "voice_leading": None,
        "phrases": [],
        "melody": None,
        "rhythm": {
            "beat_count": 0,
            "avg_note_duration": 0.2,
            "offbeat_onset_ratio": None,
            "rhythmic_density": 1.0,
            "offbeat_onset_available": False,
            "note_density_over_time": note_density,
            "onset_density_over_time": [],
            "note_density_seconds_over_time": [],
            "onset_density_seconds_over_time": [],
            "rest_segments": [],
            "beat_phase_distribution": [],
        },
        "harmony_provenance": {},
        "melody_provenance": None,
        "pulse_provenance": None,
    }


def _patch_handle_analyze_shell(monkeypatch, analysis_result: dict) -> list[dict]:
    persisted: list[dict] = []
    input_version_id = uuid4()

    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda *_args: "owner")
    monkeypatch.setattr(capabilities, "_update_progress", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        capabilities,
        "_lookup_version",
        lambda *_args: SimpleNamespace(id=input_version_id, metadata={}),
    )
    monkeypatch.setattr(capabilities, "download_version_bytes", lambda *_args: b"midi")
    monkeypatch.setattr(analyze, "analyze_midi", lambda *_args, **_kwargs: analysis_result)

    def capture_insight(
        _client,
        _version_id,
        kind,
        claim,
        evidence=None,
        **_kwargs,
    ):
        persisted.append({"kind": kind, "claim": claim, "evidence": evidence or {}})
        return uuid4()

    monkeypatch.setattr(capabilities, "_create_insight", capture_insight)

    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="analyze", version="1.0"),
        input_version_ids=[input_version_id],
    )
    capabilities.handle_analyze(job, object())
    return persisted


def test_handle_analyze_does_not_persist_seconds_fallback_as_rhythm_density(monkeypatch) -> None:
    persisted = _patch_handle_analyze_shell(monkeypatch, _minimal_analysis([]))

    assert "rhythm" in {item["kind"] for item in persisted}
    assert "rhythm_density" not in {item["kind"] for item in persisted}


def test_persisted_rhythm_density_windows_are_machine_readable(monkeypatch) -> None:
    beat_windows = analyze._compute_beat_relative_density(
        [0.25, 1.25, 2.25],
        [0.0, 1.0, 2.0, 3.0],
        window_beats=2,
        step_beats=1,
    )
    persisted = _patch_handle_analyze_shell(monkeypatch, _minimal_analysis(beat_windows))

    density = next(item for item in persisted if item["kind"] == "rhythm_density")
    window = density["evidence"]["windows"][0]
    assert window["mode"] == "beat_relative"
    assert window["unit"] == "events_per_beat"
    assert window["coordinate_unit"] == "beats"
    assert window["window_size"] == 2.0
    assert window["step_size"] == 1.0


def test_persisted_rhythm_density_keeps_complete_series_and_declares_coverage(
    monkeypatch,
) -> None:
    beats = [float(index) for index in range(82)]
    onsets = [float(index) + 0.25 for index in range(81)]
    beat_windows = analyze._compute_beat_relative_density(
        onsets,
        beats,
        window_beats=2,
        step_beats=1,
    )
    assert len(beat_windows) > 50

    persisted = _patch_handle_analyze_shell(monkeypatch, _minimal_analysis(beat_windows))
    density = next(item for item in persisted if item["kind"] == "rhythm_density")
    evidence = density["evidence"]

    assert evidence["windows"] == beat_windows
    assert evidence["coverage"] == {
        "policy_version": "complete_series_v1",
        "total_generated_window_count": len(beat_windows),
        "stored_window_count": len(beat_windows),
        "start_seconds": beat_windows[0]["start"],
        "end_seconds": beat_windows[-1]["end"],
        "truncated": False,
    }


def test_rhythm_density_capability_maturity_is_unchanged() -> None:
    registry_path = Path(__file__).parents[1] / "config" / "capabilities.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    capability = registry["capabilities"]["rhythm_density"]
    assert capability["status"] == "production"
    assert capability["input"] == "midi+beats"
