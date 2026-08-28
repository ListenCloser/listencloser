from __future__ import annotations

import json
from pathlib import Path


def _measured_result() -> dict:
    path = (
        Path(__file__).parents[1]
        / "evaluation"
        / "analysis_v3"
        / "multitrack_transcription"
        / "results"
        / "slakh_redux_subset_results.json"
    )
    return json.loads(path.read_text())


def test_measured_result_does_not_treat_basic_pitch_programs_as_evidence() -> None:
    result = _measured_result()
    basic_pitch = result["basic_pitch"]

    assert result["adoption_eligible"] is False
    assert basic_pitch["instrument_program_output"].startswith("unsupported")
    assert set(basic_pitch["macro"]) == {"onset_flat_f1", "note_flat_f1"}
    assert result["decision"]["production_change"] is False


def test_measured_result_counts_match_archived_run() -> None:
    result = _measured_result()
    expected = {
        "Track01876": (379, 297, 300),
        "Track01877": (136, 172, 127),
        "Track01878": (164, 147, 128),
        "Track01880": (651, 170, 534),
        "Track01881": (565, 399, 594),
    }

    for track_id, (reference_notes, basic_notes, mr_notes) in expected.items():
        basic = result["basic_pitch"]["tracks"][track_id]
        mr = result["mr_mt3"]["tracks"][track_id]
        assert basic["reference_notes"] == reference_notes
        assert mr["reference_notes"] == reference_notes
        assert basic["predicted_notes"] == basic_notes
        assert mr["predicted_notes"] == mr_notes


def test_mr_mt3_quality_uses_pre_serializer_decoder_evidence() -> None:
    result = _measured_result()
    mr = result["mr_mt3"]
    validity = result["serializer_validity"]
    sidecar = validity["decoder_sidecar_run"]

    assert mr["decision"] == "RESEARCH"
    assert mr["measurement_level"].startswith("decoded NoteSequence")
    assert mr["macro"]["onset_flat_f1"] == 0.7898
    assert mr["macro"]["note_flat_f1"] == 0.2415
    assert mr["macro"]["onset_program_family_f1"] == 0.755
    assert mr["macro"]["onset_program_exact_f1"] == 0.4999
    assert sidecar["workflow_run_id"] == 33218294887
    assert sidecar["artifact_digest"] == (
        "sha256:484581f59d444cfbbc1333da128f8ecb663aa4d0bc0d819a64b72ce8d0818dc8"
    )
    assert sidecar["sidecar_to_evaluator_midi_max_timing_quantization_seconds"] <= 0.0011
    assert validity["stock_serializer_macro_f1"]["onset_flat_f1"] == 0.3366
    assert validity["patched_serializer_macro_f1"]["onset_flat_f1"] == 0.3366


def test_intermediate_serializer_equivalence_remains_auditable() -> None:
    result = _measured_result()
    validity = result["serializer_validity"]

    for evidence in validity["equivalence"].values():
        assert evidence["predicted_note_count_equal"] is True
        assert evidence["raw_note_event_sequence_equal_ignoring_channel"] is True
        assert evidence["stock_onset_flat_f1"] == evidence["patched_onset_flat_f1"]
        assert (
            evidence["normalized_note_event_sha256_stock"]
            == evidence["normalized_note_event_sha256_patched"]
        )
