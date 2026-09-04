import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

import domain.source_separation as separation
from domain.models import Capability, Job
from domain.source_separation import (
    HTDEMUCS_CHECKPOINT,
    HTDEMUCS_CHECKPOINT_LICENSE,
    HTDEMUCS_CHECKPOINT_SHA256,
    HTDEMUCS_CODE_LICENSE,
    HTDEMUCS_MODEL_SIGNATURE,
    STEM_ROLES,
    register_source_separation,
    run_htdemucs,
    stem_metadata,
)


def _wav_bytes() -> bytes:
    return b"RIFF" + (100).to_bytes(4, "little") + b"WAVE" + (b"\x00" * 96)


class FakeProcess:
    def __init__(self, returncode: int | None = 0):
        self.returncode = returncode
        self.pid = 4242
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("demucs", timeout)
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9


def _write_stems(command: list[str], roles=STEM_ROLES, *, malformed_role: str | None = None):
    output_root = Path(command[command.index("--out") + 1])
    input_path = Path(command[-1])
    stem_dir = output_root / "htdemucs" / input_path.stem
    stem_dir.mkdir(parents=True)
    for role in roles:
        payload = b"not-a-wave" if role == malformed_role else _wav_bytes()
        (stem_dir / f"{role}.wav").write_bytes(payload)


def test_run_htdemucs_uses_exact_offline_model_and_literal_four_stem_contract(monkeypatch):
    observed: list[str] = []
    process = FakeProcess(0)
    popen_kwargs = {}

    def fake_popen(command, **kwargs):
        observed.extend(command)
        popen_kwargs.update(kwargs)
        _write_stems(command)
        return process

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    stems = run_htdemucs(_wav_bytes(), "wav", runtime_python="/runtime/python")

    assert list(stems) == list(STEM_ROLES)
    assert observed[:3] == ["/runtime/python", "-m", "demucs"]
    assert observed[observed.index("-n") + 1] == "htdemucs"
    assert observed[observed.index("--shifts") + 1] == "0"
    assert observed[observed.index("-d") + 1] == "cpu"
    assert popen_kwargs["start_new_session"] is True
    assert popen_kwargs["env"]["HF_HUB_OFFLINE"] == "1"
    assert popen_kwargs["env"]["OMP_NUM_THREADS"] == "2"


def test_run_htdemucs_fails_closed_when_a_role_is_missing(monkeypatch):
    def fake_popen(command, **_kwargs):
        _write_stems(command, STEM_ROLES[:-1])
        return FakeProcess(0)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    with pytest.raises(RuntimeError, match="missing the other stem"):
        run_htdemucs(_wav_bytes(), "wav", runtime_python="/runtime/python")


def test_run_htdemucs_rejects_malformed_stem_media(monkeypatch):
    def fake_popen(command, **_kwargs):
        _write_stems(command, malformed_role="bass")
        return FakeProcess(0)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    with pytest.raises(RuntimeError, match="valid bass WAV"):
        run_htdemucs(_wav_bytes(), "wav", runtime_python="/runtime/python")


def test_run_htdemucs_terminates_child_when_job_is_cancelled(monkeypatch):
    process = FakeProcess(None)
    termination_calls = []

    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: process)

    def fake_terminate(candidate):
        termination_calls.append(candidate)
        candidate.returncode = -15

    monkeypatch.setattr(separation, "_terminate_process", fake_terminate)

    with pytest.raises(RuntimeError, match="was cancelled"):
        run_htdemucs(
            _wav_bytes(),
            "wav",
            runtime_python="/runtime/python",
            is_cancelled=lambda: True,
            poll_seconds=0.001,
        )

    assert termination_calls
    assert all(candidate is process for candidate in termination_calls)
    assert process.poll() == -15


def test_run_htdemucs_terminates_child_on_timeout(monkeypatch):
    process = FakeProcess(None)
    termination_calls = []
    clock = iter([100.0, 102.0])

    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(separation.time, "monotonic", lambda: next(clock))

    def fake_terminate(candidate):
        termination_calls.append(candidate)
        candidate.returncode = -15

    monkeypatch.setattr(separation, "_terminate_process", fake_terminate)

    with pytest.raises(RuntimeError, match="timed out"):
        run_htdemucs(
            _wav_bytes(),
            "wav",
            runtime_python="/runtime/python",
            timeout_seconds=1.0,
            poll_seconds=0.001,
        )

    assert termination_calls
    assert process.poll() == -15


def test_nonzero_child_exit_fails_locally_and_next_invocation_still_works(monkeypatch):
    attempts = iter([3, 0])

    def fake_popen(command, **_kwargs):
        returncode = next(attempts)
        if returncode == 0:
            _write_stems(command)
        return FakeProcess(returncode)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    with pytest.raises(RuntimeError, match="source separation failed"):
        run_htdemucs(_wav_bytes(), "wav", runtime_python="/runtime/python")

    stems = run_htdemucs(_wav_bytes(), "wav", runtime_python="/runtime/python")
    assert list(stems) == list(STEM_ROLES)


def test_stem_metadata_keeps_separator_facts_without_duplicating_structural_lineage():
    source_version_id = uuid4()
    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="separate", version="1.0"),
        input_version_ids=[source_version_id],
        created_by="owner",
    )

    metadata = stem_metadata(source_version_id, "vocals", job)

    assert "source_version_id" not in metadata
    assert "separation_job_id" not in metadata
    assert metadata["stem_role"] == "vocals"
    assert metadata["parameters"] == {"device": "cpu", "shifts": 0}
    assert metadata["separator"]["model_signature"] == HTDEMUCS_MODEL_SIGNATURE
    assert metadata["separator"]["checkpoint"] == HTDEMUCS_CHECKPOINT
    assert metadata["separator"]["checkpoint_sha256"] == HTDEMUCS_CHECKPOINT_SHA256
    assert metadata["separator"]["wrapper_license"] == HTDEMUCS_CODE_LICENSE == "MIT"
    assert metadata["separator"]["checkpoint_license"] == HTDEMUCS_CHECKPOINT_LICENSE == "MIT"


def test_registration_is_capability_local_and_does_not_replace_worker_scheduling():
    registrations = []

    class Worker:
        def register(self, name, version, handler):
            registrations.append((name, version, handler))

    register_source_separation(Worker())

    assert len(registrations) == 1
    assert registrations[0][:2] == ("separate", "1.0")
    assert registrations[0][2] is separation.handle_separate
