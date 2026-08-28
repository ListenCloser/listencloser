from __future__ import annotations

import json
from pathlib import Path

import pytest
from backend.evaluation.analysis_v3.multitrack_transcription.datasets.slakh import (
    build_slakh_manifest,
)
from backend.evaluation.analysis_v3.multitrack_transcription.metrics import (
    NoteEvent,
    instrument_detection,
    match_notes,
    score_by_program,
    score_events,
)
from backend.evaluation.analysis_v3.multitrack_transcription.run import (
    _validate_model_run,
    load_reference_evidence,
)


def note(
    pitch: int,
    start: float = 0.0,
    end: float = 1.0,
    program: int = 0,
    is_drum: bool = False,
) -> NoteEvent:
    return NoteEvent(
        pitch=pitch,
        start=start,
        end=end,
        program=program,
        is_drum=is_drum,
    )


def test_flat_match_ignores_program_but_exact_program_does_not() -> None:
    reference = [note(60, program=32)]
    predicted = [note(60, program=0)]

    assert match_notes(reference, predicted).f1 == 1.0
    assert match_notes(reference, predicted, program_mode="exact").f1 == 0.0


def test_task_standard_matching_uses_maximum_bipartite_assignment() -> None:
    reference = [note(60, start=0.0, end=1.0), note(60, start=0.01, end=1.01)]
    predicted = [note(60, start=0.01, end=1.01), note(60, start=0.06, end=1.06)]

    metrics = match_notes(reference, predicted)

    assert metrics.matched_notes == 2
    assert metrics.f1 == 1.0


def test_program_family_accepts_different_programs_within_same_gm_family() -> None:
    reference = [note(60, program=24)]
    predicted = [note(60, program=31)]

    assert match_notes(reference, predicted, program_mode="family").f1 == 1.0
    assert match_notes(reference, predicted, program_mode="exact").f1 == 0.0


def test_note_metric_requires_offset_with_standard_relative_tolerance() -> None:
    reference = [note(60, end=1.0)]
    predicted = [note(60, end=1.19)]
    too_late = [note(60, end=1.21)]

    assert match_notes(reference, predicted, require_offset=True).f1 == 1.0
    assert match_notes(reference, too_late, require_offset=True).f1 == 0.0


def test_drum_label_is_distinct_from_melodic_programs() -> None:
    reference = [note(36, program=0, is_drum=True)]
    predicted_drum = [note(36, program=0, is_drum=True)]
    predicted_piano = [note(36, program=0, is_drum=False)]

    assert match_notes(reference, predicted_drum, program_mode="exact").f1 == 1.0
    assert match_notes(reference, predicted_piano, program_mode="exact").f1 == 0.0


def test_instrument_detection_scores_active_programs_not_note_count() -> None:
    reference = [note(60, program=0), note(64, program=0), note(40, program=32)]
    predicted = [note(60, program=0), note(67, program=0)]

    metrics = instrument_detection(reference, predicted, mode="exact")

    assert metrics.reference_notes == 2
    assert metrics.predicted_notes == 1
    assert metrics.matched_notes == 1
    assert metrics.precision == 1.0
    assert metrics.recall == 0.5


def test_per_program_breakdown_exposes_instrument_specific_failure() -> None:
    reference = [note(60, program=0), note(40, program=32)]
    predicted = [note(60, program=0)]

    breakdown = score_by_program(reference, predicted, mode="exact")

    assert breakdown["exact:0"]["f1"] == 1.0
    assert breakdown["exact:32"]["f1"] == 0.0


def test_score_events_exposes_flat_and_instrument_aware_views() -> None:
    scored = score_events([note(60, program=32)], [note(60, program=0)])

    assert scored["onset_flat"]["f1"] == 1.0
    assert scored["onset_program_exact"]["f1"] == 0.0
    assert scored["onset_program_exact"]["by_program"]["exact:32"]["f1"] == 0.0
    assert "instrument_detection_family" in scored


def test_slakh_manifest_uses_per_source_midi_and_is_deterministic(tmp_path: Path) -> None:
    root = tmp_path / "slakh"
    split = root / "test"
    for track_name in ("Track00002", "Track00001"):
        track = split / track_name
        (track / "MIDI").mkdir(parents=True)
        (track / "mix.flac").write_bytes(b"fake-flac")
        (track / "all_src.mid").write_bytes(b"do-not-use")
        (track / "MIDI" / "S01.mid").write_bytes(b"source-1")
        (track / "MIDI" / "S00.mid").write_bytes(b"source-0")

    manifest = build_slakh_manifest(root, split="test", limit=1)

    assert manifest["entries"][0]["id"] == "Track00001"
    assert manifest["entries"][0]["reference_midis"] == [
        "test/Track00001/MIDI/S00.mid",
        "test/Track00001/MIDI/S01.mid",
    ]
    assert all("all_src.mid" not in path for path in manifest["entries"][0]["reference_midis"])


def test_slakh_manifest_can_record_checksums(tmp_path: Path) -> None:
    root = tmp_path / "slakh"
    track = root / "test" / "Track00001"
    (track / "MIDI").mkdir(parents=True)
    (track / "mix.flac").write_bytes(b"audio")
    (track / "MIDI" / "S00.mid").write_bytes(b"midi")

    manifest = build_slakh_manifest(root, split="test", limit=1, hash_files=True)
    entry = manifest["entries"][0]

    assert len(entry["mix_sha256"]) == 64
    assert len(entry["reference_midi_sha256"]["test/Track00001/MIDI/S00.mid"]) == 64


def test_slakh_manifest_fails_closed_when_dataset_is_missing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no Slakh tracks"):
        build_slakh_manifest(tmp_path, split="test", limit=1)


def valid_model_run() -> dict:
    return {
        "evaluation_id": "eval-1",
        "hello_ai_sha": "abc",
        "candidate": "candidate",
        "candidate_revision": "revision",
        "model_checksum": None,
        "code_license": "MIT",
        "weight_license": "MIT",
        "dataset_manifest": {"path": "manifest.json", "sha256": "a" * 64},
        "environment": {"device": "cpu"},
        "entries": [{"id": "Track00001", "predicted_midi": "Track00001.mid"}],
    }


def test_model_run_requires_provenance() -> None:
    payload = valid_model_run()
    del payload["weight_license"]

    with pytest.raises(ValueError, match="weight_license"):
        _validate_model_run(payload)


def test_model_run_rejects_duplicate_track_ids() -> None:
    payload = valid_model_run()
    payload["entries"].append(dict(payload["entries"][0]))

    with pytest.raises(ValueError, match="duplicate"):
        _validate_model_run(payload)


def test_reference_evidence_has_traceable_sources_and_canonical_decisions() -> None:
    payload = load_reference_evidence()

    assert payload["local_model_inference_performed"] is False
    assert {candidate["decision"] for candidate in payload["candidates"]} <= {
        "ADOPT",
        "RESEARCH",
        "REJECT",
        "REVISIT",
    }


def test_model_run_requires_dataset_manifest_checksum() -> None:
    payload = valid_model_run()
    payload["dataset_manifest"] = {"path": "manifest.json"}

    with pytest.raises(ValueError, match="sha256"):
        _validate_model_run(payload)


def test_reference_evidence_rejects_untraceable_dataset_source(tmp_path: Path) -> None:
    source = load_reference_evidence()
    source["dataset"]["source_refs"] = ["missing-source"]
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(source))

    with pytest.raises(ValueError, match="unknown source refs"):
        load_reference_evidence(path)


def test_model_run_template_is_valid_json() -> None:
    path = (
        Path(__file__).parents[1]
        / "evaluation"
        / "analysis_v3"
        / "multitrack_transcription"
        / "schemas"
        / "model_run_template.json"
    )
    payload = json.loads(path.read_text())

    assert payload["candidate_revision"] == "<immutable commit/checkpoint revision>"
