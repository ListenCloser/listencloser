from __future__ import annotations

import pytest
from backend.evaluation.analysis_v3.multitrack_transcription import persistent_runtime


def test_mirror_url_is_pinned_to_immutable_revision():
    url = persistent_runtime._mirror_url("Track01876")

    assert persistent_runtime.MIRROR_REVISION in url
    assert url.endswith("data/Slakh2100_redux/test/Track01876/mix.flac")


def test_validate_prepared_manifest_requires_canonical_track_hashes():
    payload = {
        "entries": [
            {
                "id": track_id,
                "cropped_sha256": persistent_runtime.EXPECTED_CROPPED_MIX_SHA256[track_id],
            }
            for track_id in persistent_runtime.TRACK_IDS
        ]
    }

    persistent_runtime.validate_prepared_manifest(payload)

    payload["entries"][0]["cropped_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="canonical quality run"):
        persistent_runtime.validate_prepared_manifest(payload)


def test_summarize_comparison_reports_paired_speedup_and_parity():
    control = [
        {
            "id": track_id,
            "runtime_seconds": float((index + 1) * 10),
        }
        for index, track_id in enumerate(persistent_runtime.TRACK_IDS)
    ]
    resident = [
        {
            "id": track_id,
            "runtime_seconds": float((index + 1) * 2),
            "matches_cli_semantics": True,
            "matches_cli_note_count": True,
        }
        for index, track_id in enumerate(persistent_runtime.TRACK_IDS)
    ]

    summary = persistent_runtime.summarize_comparison(
        control,
        resident,
        model_load_seconds=3.0,
    )

    assert summary["mean_speedup"] == pytest.approx(5.0)
    assert summary["median_speedup"] == pytest.approx(5.0)
    assert summary["cli_total_seconds"] == pytest.approx(150.0)
    assert summary["persistent_five_track_inference_seconds"] == pytest.approx(30.0)
    assert summary["persistent_load_plus_five_tracks_seconds"] == pytest.approx(33.0)
    assert summary["all_cli_semantics_equal"] is True
    assert summary["all_cli_note_counts_equal"] is True
