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


def test_mr_mt3_program_metrics_are_gated_by_serializer_equivalence() -> None:
    result = _measured_result()
    validity = result["serializer_validity"]

    assert result["mr_mt3"]["decision"] == "RESEARCH"
    assert result["mr_mt3"]["macro"]["onset_flat_f1"] == 0.3366
    assert result["mr_mt3"]["macro"]["onset_program_family_f1"] == 0.3147
    assert result["mr_mt3"]["macro"]["onset_program_exact_f1"] == 0.2286

    for evidence in validity["equivalence"].values():
        assert evidence["predicted_note_count_equal"] is True
        assert evidence["raw_note_event_sequence_equal_ignoring_channel"] is True
        assert evidence["stock_onset_flat_f1"] == evidence["patched_onset_flat_f1"]
        assert (
            evidence["normalized_note_event_sha256_stock"]
            == evidence["normalized_note_event_sha256_patched"]
        )
