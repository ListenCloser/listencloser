from __future__ import annotations

from uuid import uuid4

import pytest

from domain.models import Version
from domain.storage_locator_policy import (
    StorageLocatorKind,
    classify_version_storage_locator,
)


@pytest.fixture
def ids():
    return {
        "owner": str(uuid4()),
        "project": uuid4(),
        "artifact": uuid4(),
        "job": uuid4(),
    }


def _version(ids, storage_key: str, *, job_id=None, created_by=None, bucket="artifacts") -> Version:
    return Version(
        artifact_id=ids["artifact"],
        storage_key=storage_key,
        storage_bucket=bucket,
        created_by=ids["owner"] if created_by is None else created_by,
        produced_by_job_id=job_id,
    )


def _classify(version: Version, ids, *, jobs=None):
    return classify_version_storage_locator(
        version,
        owner_id=ids["owner"],
        project_id=ids["project"],
        artifact_id=ids["artifact"],
        allowed_job_ids=set(jobs or []),
    )


def test_owner_artifact_path_is_trusted(ids):
    version = _version(
        ids,
        f'{ids["owner"]}/{ids["project"]}/{ids["artifact"]}/{uuid4().hex}.wav',
    )

    decision = _classify(version, ids)

    assert decision.trusted is True
    assert decision.kind is StorageLocatorKind.owner_upload


def test_pending_direct_upload_path_is_trusted(ids):
    version = _version(
        ids,
        f'{ids["owner"]}/{ids["project"]}/pending/{uuid4().hex}.wav',
    )

    assert _classify(version, ids).trusted is True


def test_worker_output_requires_same_work_job_and_attempt_path(ids):
    version = _version(
        ids,
        f'jobs/{ids["job"]}/attempt-2/score.musicxml',
        job_id=ids["job"],
    )

    decision = _classify(version, ids, jobs={ids["job"]})

    assert decision.trusted is True
    assert decision.kind is StorageLocatorKind.worker_output


@pytest.mark.parametrize(
    ("storage_key", "reason"),
    [
        ("transcriptions/legacy.mid", "owner_path_shape"),
        ("it/test-output.mid", "owner_path_shape"),
        ("../artifacts/foreign.wav", "unsafe_path"),
    ],
)
def test_unproven_legacy_or_unsafe_paths_are_rejected(ids, storage_key, reason):
    decision = _classify(_version(ids, storage_key), ids)

    assert decision.trusted is False
    assert decision.kind is StorageLocatorKind.untrusted
    assert decision.reason == reason


def test_owner_path_rejects_foreign_owner_or_project(ids):
    other_owner = str(uuid4())
    other_project = uuid4()

    owner_mismatch = _version(
        ids,
        f'{other_owner}/{ids["project"]}/{ids["artifact"]}/take.wav',
    )
    project_mismatch = _version(
        ids,
        f'{ids["owner"]}/{other_project}/{ids["artifact"]}/take.wav',
    )

    assert _classify(owner_mismatch, ids).reason == "owner_project_mismatch"
    assert _classify(project_mismatch, ids).reason == "owner_project_mismatch"


def test_owner_path_requires_matching_creator(ids):
    version = _version(
        ids,
        f'{ids["owner"]}/{ids["project"]}/{ids["artifact"]}/take.wav',
        created_by=str(uuid4()),
    )

    assert _classify(version, ids).reason == "creator_mismatch"


def test_worker_output_rejects_job_from_another_work(ids):
    version = _version(
        ids,
        f'jobs/{ids["job"]}/attempt-0/output.mid',
        job_id=ids["job"],
    )

    assert _classify(version, ids, jobs=set()).reason == "job_not_in_work"


def test_worker_output_rejects_forged_job_path(ids):
    other_job = uuid4()
    version = _version(
        ids,
        f'jobs/{other_job}/attempt-0/output.mid',
        job_id=ids["job"],
    )

    assert _classify(version, ids, jobs={ids["job"]}).reason == "job_path_mismatch"


def test_unexpected_bucket_is_never_trusted(ids):
    version = _version(
        ids,
        f'{ids["owner"]}/{ids["project"]}/{ids["artifact"]}/take.wav',
        bucket="library",
    )

    assert _classify(version, ids).reason == "unexpected_bucket"
