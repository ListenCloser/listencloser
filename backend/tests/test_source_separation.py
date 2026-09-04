from pathlib import Path
import subprocess
from uuid import uuid4

import pytest

from domain.models import Capability, Job
from domain.source_separation import (
    HTDEMUCS_CHECKPOINT,
    HTDEMUCS_CHECKPOINT_LICENSE,
    HTDEMUCS_CHECKPOINT_SHA256,
    HTDEMUCS_CODE_LICENSE,
    HTDEMUCS_MODEL_SIGNATURE,
    STEM_ROLES,
    run_htdemucs,
    stem_metadata,
)


def _wav_bytes() -> bytes:
    return b"RIFF" + (100).to_bytes(4, "little") + b"WAVE" + (b"\x00" * 96)


def test_run_htdemucs_uses_exact_model_and_literal_four_stem_contract(monkeypatch):
    observed: list[str] = []

    def fake_run(command, **_kwargs):
        observed.extend(command)
        output_root = Path(command[command.index("--out") + 1])
        input_path = Path(command[-1])
        stem_dir = output_root / "htdemucs" / input_path.stem
        stem_dir.mkdir(parents=True)
        for role in STEM_ROLES:
            (stem_dir / f"{role}.wav").write_bytes(_wav_bytes())
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    stems = run_htdemucs(_wav_bytes(), "wav", runtime_python="/runtime/python")

    assert list(stems) == list(STEM_ROLES)
    assert observed[:3] == ["/runtime/python", "-m", "demucs"]
    assert observed[observed.index("-n") + 1] == "htdemucs"
    assert observed[observed.index("--shifts") + 1] == "0"
    assert observed[observed.index("-d") + 1] == "cpu"


def test_run_htdemucs_fails_closed_when_a_role_is_missing(monkeypatch):
    def fake_run(command, **_kwargs):
        output_root = Path(command[command.index("--out") + 1])
        input_path = Path(command[-1])
        stem_dir = output_root / "htdemucs" / input_path.stem
        stem_dir.mkdir(parents=True)
        for role in STEM_ROLES[:-1]:
            (stem_dir / f"{role}.wav").write_bytes(_wav_bytes())
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="missing the other stem"):
        run_htdemucs(_wav_bytes(), "wav", runtime_python="/runtime/python")


def test_stem_metadata_persists_code_weight_and_source_provenance_separately():
    source_version_id = uuid4()
    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="separate", version="1.0"),
        input_version_ids=[source_version_id],
        created_by="owner",
    )

    metadata = stem_metadata(source_version_id, "vocals", job)

    assert metadata["source_version_id"] == str(source_version_id)
    assert metadata["separation_job_id"] == str(job.id)
    assert metadata["stem_role"] == "vocals"
    assert metadata["parameters"] == {"device": "cpu", "shifts": 0}
    assert metadata["separator"]["model_signature"] == HTDEMUCS_MODEL_SIGNATURE
    assert metadata["separator"]["checkpoint"] == HTDEMUCS_CHECKPOINT
    assert metadata["separator"]["checkpoint_sha256"] == HTDEMUCS_CHECKPOINT_SHA256
    assert metadata["separator"]["wrapper_license"] == HTDEMUCS_CODE_LICENSE == "MIT"
    assert metadata["separator"]["checkpoint_license"] == HTDEMUCS_CHECKPOINT_LICENSE == "MIT"
