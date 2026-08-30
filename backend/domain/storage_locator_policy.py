"""Authorization policy for privileged Storage access through persisted Versions.

A Version row is metadata, not proof that its Storage locator is safe for the
service-role client to sign or delete.  This module binds modern persisted
locators back to the already-authorized Work graph before privileged Storage
operations are allowed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from domain.models import Version

_STORAGE_BUCKET = "artifacts"
_ATTEMPT_SEGMENT = re.compile(r"^attempt-[0-9]+$")


class StorageLocatorKind(str, Enum):
    owner_upload = "owner_upload"
    worker_output = "worker_output"
    untrusted = "untrusted"


@dataclass(frozen=True)
class StorageLocatorDecision:
    trusted: bool
    kind: StorageLocatorKind
    reason: str


def classify_version_storage_locator(
    version: Version,
    *,
    owner_id: str,
    project_id: UUID,
    artifact_id: UUID,
    allowed_job_ids: set[UUID],
) -> StorageLocatorDecision:
    """Return whether ``version`` may authorize service-role Storage access.

    Trusted modern locators have one of two repository-owned shapes:

    - direct/user upload: ``owner/project/(pending|artifact)/filename``;
    - worker output: ``jobs/job-id/attempt-N/...`` where the persisted
      ``produced_by_job_id`` belongs to the already-authorized Work snapshot.

    ``created_by`` must match the Work owner in both cases.  Historical rows
    that cannot prove either relationship stay visible as metadata but must not
    become signing/deletion authority.
    """
    if version.storage_bucket != _STORAGE_BUCKET:
        return StorageLocatorDecision(False, StorageLocatorKind.untrusted, "unexpected_bucket")

    if not version.created_by or str(version.created_by) != str(owner_id):
        return StorageLocatorDecision(False, StorageLocatorKind.untrusted, "creator_mismatch")

    parts = version.storage_key.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return StorageLocatorDecision(False, StorageLocatorKind.untrusted, "unsafe_path")

    if version.produced_by_job_id is not None:
        job_id = version.produced_by_job_id
        if job_id not in allowed_job_ids:
            return StorageLocatorDecision(False, StorageLocatorKind.untrusted, "job_not_in_work")
        if (
            len(parts) < 4
            or parts[0] != "jobs"
            or parts[1] != str(job_id)
            or not _ATTEMPT_SEGMENT.fullmatch(parts[2])
        ):
            return StorageLocatorDecision(False, StorageLocatorKind.untrusted, "job_path_mismatch")
        return StorageLocatorDecision(True, StorageLocatorKind.worker_output, "trusted_worker_output")

    if len(parts) != 4:
        return StorageLocatorDecision(False, StorageLocatorKind.untrusted, "owner_path_shape")
    if parts[0] != str(owner_id) or parts[1] != str(project_id):
        return StorageLocatorDecision(False, StorageLocatorKind.untrusted, "owner_project_mismatch")
    if parts[2] not in {"pending", str(artifact_id)}:
        return StorageLocatorDecision(False, StorageLocatorKind.untrusted, "artifact_path_mismatch")

    return StorageLocatorDecision(True, StorageLocatorKind.owner_upload, "trusted_owner_upload")
