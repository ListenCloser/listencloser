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


def test_measured_dataset_identity_matches_canonical_sidecar_artifact() -> None:
    result = _measured_result()
    dataset = result["dataset"]

    assert dataset["manifest_sha256"] == (
        "7ad55174f83f2f0097898624a269e1ff25899183f18dac9dd7da38005c971b99"
    )
    expected_mix_hashes = {
        "Track01876": "b7f3a32155a14e7a2e8ea3c8d46e4fd924384d28f20de214945302004a236d9a",
        "Track01877": "620b11c7bc00e494d609d9145a715927cf0b429dc865af73d37bee67e1a9b1d4",
        "Track01878": "f2f54d66c5a1ab9ec430b8571f7fff0c7498dc4343bb1f820dd8cfe1483c0923",
        "Track01880": "9c632afea1f59ac23cb032d8340a096076504dabdb7d0ce8995faea9ead036f4",
        "Track01881": "6762066f29458258d56b86c02f2bdbda3c713d60ea92d0526b51f227eaced992",
    }
    for track_id, expected_hash in expected_mix_hashes.items():
        assert dataset["entries"][track_id]["mix_sha256"] == expected_hash

    assert set(dataset["entries"]["Track01877"]["reference_midi_sha256"]) == {
        "Track01877/MIDI/S00.mid",
        "Track01877/MIDI/S03.mid",
        "Track01877/MIDI/S09.mid",
    }


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
    assert sidecar["stock_midi_serializer_modified"] is False
    assert sidecar["sidecar_to_evaluator_midi_max_timing_quantization_seconds"] <= 0.0011


def test_serializer_diagnostics_distinguish_program_loss_from_timing_drift() -> None:
    validity = _measured_result()["serializer_validity"]

    assert validity["stock_serializer_macro_f1"]["onset_flat_f1"] == 0.3366
    assert validity["patched_serializer_macro_f1"]["onset_flat_f1"] == 0.3366
    assert validity["patched_serializer_macro_f1"]["instrument_detection_family_f1"] == 0.9113
    assert validity["decoder_macro_f1"]["onset_flat_f1"] == 0.7898
    assert any("integer MIDI ticks" in bug for bug in validity["upstream_bugs"])

    drift = validity["stock_vs_decoder_timing_drift"]
    expected_medians = {
        "Track01876": -0.092727,
        "Track01877": -0.064,
        "Track01878": -0.042545,
        "Track01880": -0.190727,
        "Track01881": -0.123909,
    }
    for track_id, expected_median in expected_medians.items():
        evidence = drift[track_id]
        assert evidence["stock_vs_decoder_note_count_equal"] is True
        assert evidence["stock_minus_decoder_onset_seconds"]["median"] == expected_median

    assert drift["Track01880"]["stock_minus_decoder_onset_seconds"]["min"] == -0.324273
