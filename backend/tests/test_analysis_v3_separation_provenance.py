from __future__ import annotations

import pytest

from backend.evaluation.analysis_v3.separation.adapters import demucs


def test_stage_two_pins_current_demucs_package_version():
    demucs._require_expected_package_version("4.1.0")

    with pytest.raises(RuntimeError, match="requires exactly demucs==4.1.0"):
        demucs._require_expected_package_version("4.0.1")


def test_htdemucs_metadata_records_checkpoint_and_license_provenance():
    metadata = demucs.DemucsAdapter().metadata()

    assert metadata.model_id == "demucs:htdemucs@955717e8"
    assert metadata.checkpoint_id == "955717e8"
    assert metadata.checkpoint_file == "955717e8-8726e21a.th"
    assert metadata.checkpoint_sha256_prefix == "8726e21a"
    assert metadata.code_license == "MIT"
    assert metadata.code_license_source == "https://pypi.org/project/demucs/4.1.0/"
    assert metadata.weight_license == "MIT"
    assert metadata.weight_license_source == "https://huggingface.co/adefossez/HTDemucs"
