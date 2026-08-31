"""Execution-attempt fencing for durable capability handlers.

The base :class:`JobWorker` remains the one queue/lease/retry implementation.
This module adds the production persistence policy that queue ownership alone
cannot express: every claim gets a fresh execution token, and every
product-visible handler mutation must prove that token is still current in the
same database transaction as the mutation.

The handler-facing Supabase client is intentionally narrower than the service
client. Reads remain ordinary PostgREST reads; Job progress is token-scoped;
Artifact + Version publication is one atomic RPC; other admitted output inserts
and the two existing cleanup delete shapes use fenced RPCs. Unknown mutations
fail closed. Storage bytes are attempt-scoped so a stale attempt can leave, at
worst, private unreferenced blob garbage rather than overwrite or delete a
current attempt's object.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from observability import get_tracer

from .job_worker import JobWorker
from .models import Job

_DIRECT_OUTPUT_TABLES = frozenset({"entities", "insights", "alignments"})
_MUTABLE_OUTPUT_TABLES = frozenset(
    {"artifacts", "artifact_versions", *_DIRECT_OUTPUT_TABLES}
)

_tracer = get_tracer("listencloser-worker-execution-fence")


class _LifecycleJobsTable:
    """Apply the current execution token to worker-thread Job updates."""

    def __init__(self, table: Any, execution_token: str) -> None:
        self._table = table
        self._execution_token = execution_token

    def update(self, values: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        return self._table.update(values, *args, **kwargs).eq(
            "execution_token", self._execution_token
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._table, name)


class _LifecycleClient:
    """Raw worker client plus an automatic execution-token Job update filter."""

    def __init__(self, client: Any, execution_token: str) -> None:
        self._client = client
        self._execution_token = execution_token

    def table(self, name: str) -> Any:
        table = self._client.table(name)
        if name == "jobs":
            return _LifecycleJobsTable(table, self._execution_token)
        return table

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class _FencedInsert:
    def __init__(
        self,
        client: _HandlerClient,
        table_name: str,
        rows: dict[str, Any] | list[dict[str, Any]],
    ) -> None:
        self._client = client
        self._table_name = table_name
        self._rows = rows

    def execute(self) -> Any:
        source_rows = self._rows if isinstance(self._rows, list) else [self._rows]
        rows = [self._client.rewrite_output_row(dict(row)) for row in source_rows]

        # ArtifactRepo immediately creates a Version for every new Artifact.
        # Holding the Artifact row in memory until that Version arrives prevents
        # takeover between two separate INSERTs from leaving a durable empty
        # Artifact behind. The publish RPC inserts both rows under one Job-row
        # ownership lock and one database transaction.
        if self._table_name == "artifacts":
            if len(rows) != 1:
                raise RuntimeError("job handlers may publish one Artifact at a time")
            self._client.defer_artifact(rows[0])
            return SimpleNamespace(data=[rows[0]])

        if self._table_name == "artifact_versions":
            if len(rows) != 1:
                raise RuntimeError("job handlers may publish one Version at a time")
            version = rows[0]
            artifact = self._client.pending_artifact(str(version.get("artifact_id")))
            result = self._client._raw.rpc(
                "fenced_job_publish_version",
                {
                    "p_job_id": self._client.job_id,
                    "p_execution_token": self._client.execution_token,
                    "p_artifact": artifact,
                    "p_version": version,
                },
            ).execute()
            self._client.release_artifact(str(version.get("artifact_id")))
            return result

        if self._table_name not in _DIRECT_OUTPUT_TABLES:
            raise RuntimeError(f"job handler insert is not allowed for {self._table_name!r}")
        return self._client._raw.rpc(
            "fenced_job_insert",
            {
                "p_job_id": self._client.job_id,
                "p_execution_token": self._client.execution_token,
                "p_table": self._table_name,
                "p_rows": rows,
            },
        ).execute()


class _FencedDelete:
    """Collect the supported immutable-output cleanup filters, then fence delete."""

    def __init__(self, client: _HandlerClient, table_name: str) -> None:
        self._client = client
        self._table_name = table_name
        self._eq: dict[str, Any] = {}
        self._in: dict[str, list[Any]] = {}

    def eq(self, column: str, value: Any) -> _FencedDelete:
        self._eq[column] = value
        return self

    def in_(self, column: str, values: list[Any]) -> _FencedDelete:
        self._in[column] = list(values)
        return self

    def execute(self) -> Any:
        if self._table_name == "artifacts" and not self._eq and set(self._in) == {"id"}:
            match = {"id_in": self._in["id"]}
        elif (
            self._table_name == "entities"
            and not self._in
            and set(self._eq) == {"version_id", "kind"}
        ):
            match = dict(self._eq)
        else:
            raise RuntimeError(
                "job handler output delete is not an admitted fenced mutation shape"
            )
        return self._client._raw.rpc(
            "fenced_job_delete",
            {
                "p_job_id": self._client.job_id,
                "p_execution_token": self._client.execution_token,
                "p_table": self._table_name,
                "p_match": match,
            },
        ).execute()


class _PendingArtifactSelect:
    """Provide read-your-writes for an Artifact held until Version publication.

    ``VersionRepo.create`` verifies the Artifact owner before issuing its insert.
    A fenced Artifact is deliberately not durable yet, so that repository lookup
    must see the in-memory row or atomic Artifact+Version publication can never
    reach the database RPC.
    """

    def __init__(self, client: _HandlerClient, query: Any, columns: str) -> None:
        self._client = client
        self._query = query
        self._columns = columns
        self._artifact_id: str | None = None

    def eq(self, column: str, value: Any) -> _PendingArtifactSelect:
        self._query = self._query.eq(column, value)
        if column == "id":
            self._artifact_id = str(value)
        return self

    def execute(self) -> Any:
        if self._artifact_id is not None:
            artifact = self._client.find_pending_artifact(self._artifact_id)
            if artifact is not None:
                if self._columns.strip() == "*":
                    row = dict(artifact)
                else:
                    selected = [column.strip() for column in self._columns.split(",")]
                    row = {column: artifact.get(column) for column in selected}
                return SimpleNamespace(data=[row])
        return self._query.execute()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._query, name)


class _HandlerTable:
    """Read-through table facade with fail-closed handler mutation policy."""

    def __init__(self, client: _HandlerClient, name: str) -> None:
        self._client = client
        self._name = name
        self._table = client._raw.table(name)

    def select(self, columns: str = "*", *args: Any, **kwargs: Any) -> Any:
        query = self._table.select(columns, *args, **kwargs)
        if self._name == "artifacts" and not args and not kwargs:
            return _PendingArtifactSelect(self._client, query, columns)
        return query

    def insert(
        self,
        rows: dict[str, Any] | list[dict[str, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> _FencedInsert:
        if args or kwargs:
            raise RuntimeError("fenced handler inserts do not accept transport overrides")
        if self._name not in _MUTABLE_OUTPUT_TABLES:
            raise RuntimeError(f"job handler insert is not allowed for table {self._name!r}")
        return _FencedInsert(self._client, self._name, rows)

    def update(self, values: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        if self._name != "jobs":
            raise RuntimeError(f"job handler update is not allowed for table {self._name!r}")
        return self._table.update(values, *args, **kwargs).eq(
            "execution_token", self._client.execution_token
        )

    def delete(self, *args: Any, **kwargs: Any) -> _FencedDelete:
        if args or kwargs:
            raise RuntimeError("fenced handler deletes do not accept transport overrides")
        if self._name not in _MUTABLE_OUTPUT_TABLES:
            raise RuntimeError(f"job handler delete is not allowed for table {self._name!r}")
        return _FencedDelete(self._client, self._name)

    def upsert(self, *_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError(f"job handler upsert is not allowed for table {self._name!r}")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._table, name)


class _HandlerStorageBucket:
    def __init__(self, bucket: Any, client: _HandlerClient) -> None:
        self._bucket = bucket
        self._client = client

    def download(self, path: str, *args: Any, **kwargs: Any) -> Any:
        return self._bucket.download(path, *args, **kwargs)

    def upload(self, path: str, *args: Any, **kwargs: Any) -> Any:
        fenced_path = self._client.scope_storage_key(path)
        self._client.remember_storage_key(path, fenced_path)
        return self._bucket.upload(fenced_path, *args, **kwargs)

    def remove(self, _paths: list[str], *_args: Any, **_kwargs: Any) -> list[Any]:
        """Leave cleanup bytes for GC instead of racing a successor attempt.

        Supabase Storage deletion is an external API operation, so it cannot be
        made atomic with the Job-row execution-token check. The database graph
        cleanup remains fenced; retaining private unreferenced bytes is safer
        than allowing a stale attempt to delete a successor's live object.
        """
        return []

    def __getattr__(self, name: str) -> Any:
        raise RuntimeError(f"job handlers cannot access unfenced storage operation {name}")


class _HandlerStorage:
    def __init__(self, storage: Any, client: _HandlerClient) -> None:
        self._storage = storage
        self._client = client

    def from_(self, bucket: str) -> _HandlerStorageBucket:
        return _HandlerStorageBucket(self._storage.from_(bucket), self._client)

    def __getattr__(self, name: str) -> Any:
        raise RuntimeError(f"job handlers cannot access unfenced storage operation {name}")


class _HandlerClient:
    """Capability-facing persistence boundary for one exact Job execution."""

    def __init__(self, raw: Any, job_id: str, execution_token: str) -> None:
        self._raw = raw
        self.job_id = job_id
        self.execution_token = execution_token
        self._storage_keys: dict[str, str] = {}
        self._pending_artifacts: dict[str, dict[str, Any]] = {}
        self.storage = _HandlerStorage(raw.storage, self)

    def table(self, name: str) -> _HandlerTable:
        return _HandlerTable(self, name)

    def rpc(self, *_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("job handlers cannot call unfenced database RPCs")

    def scope_storage_key(self, path: str) -> str:
        prefix = f"jobs/{self.job_id}/"
        if not path.startswith(prefix):
            raise RuntimeError(
                "job handler storage writes must stay within the current Job namespace"
            )
        suffix = path[len(prefix) :]
        scoped_prefix = f"execution-{self.execution_token}/"
        if suffix.startswith(scoped_prefix):
            return path
        return f"{prefix}{scoped_prefix}{suffix}"

    def remember_storage_key(self, original: str, fenced: str) -> None:
        self._storage_keys[original] = fenced

    def rewrite_output_row(self, row: dict[str, Any]) -> dict[str, Any]:
        storage_key = row.get("storage_key")
        if isinstance(storage_key, str):
            row["storage_key"] = self._storage_keys.get(storage_key, storage_key)
        return row

    def defer_artifact(self, artifact: dict[str, Any]) -> None:
        artifact_id = artifact.get("id")
        if not artifact_id:
            raise RuntimeError("fenced Artifact publication requires a durable id")
        key = str(artifact_id)
        if key in self._pending_artifacts:
            raise RuntimeError(f"Artifact {key} is already pending publication")
        self._pending_artifacts[key] = artifact

    def find_pending_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        artifact = self._pending_artifacts.get(artifact_id)
        return dict(artifact) if artifact is not None else None

    def pending_artifact(self, artifact_id: str) -> dict[str, Any]:
        artifact = self._pending_artifacts.get(artifact_id)
        if artifact is None:
            raise RuntimeError(
                "Version publication requires its Artifact to be created in the same execution"
            )
        return artifact

    def release_artifact(self, artifact_id: str) -> None:
        self._pending_artifacts.pop(artifact_id, None)

    def __getattr__(self, name: str) -> Any:
        raise RuntimeError(f"job handlers cannot access raw client operation {name}")


class FencedJobWorker(JobWorker):
    """Production JobWorker with per-claim execution-generation fencing."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._execution_tokens: dict[str, str] = {}
        self._execution_tokens_lock = threading.Lock()
        self._thread_attempt = threading.local()

    @property
    def client(self) -> Any:
        raw = super().client
        token = getattr(self._thread_attempt, "execution_token", None)
        if token:
            return _LifecycleClient(raw, token)
        return raw

    def _raw_client(self) -> Any:
        return super().client

    def _remember_execution_token(self, job_id: str, token: str) -> None:
        with self._execution_tokens_lock:
            self._execution_tokens[job_id] = token

    def _execution_token(self, job_id: str) -> str:
        with self._execution_tokens_lock:
            token = self._execution_tokens.get(job_id)
        if not token:
            raise RuntimeError(f"job {job_id} has no active execution token")
        return token

    def _forget_execution_token(self, job_id: str, expected_token: str) -> None:
        """Forget only the generation owned by the finishing execution."""
        with self._execution_tokens_lock:
            if self._execution_tokens.get(job_id) == expected_token:
                self._execution_tokens.pop(job_id, None)

    def _handler_client(self, job_id: str) -> _HandlerClient:
        """Return the exact-attempt persistence client for internal tests/adapters."""
        return _HandlerClient(self._raw_client(), job_id, self._execution_token(job_id))

    def _claim_job(self, job_id: str) -> bool:
        # A direct/specific-id path must not create a second local generation
        # while this process still owns an execution of the same logical Job.
        with self._execution_tokens_lock:
            if job_id in self._execution_tokens:
                return False

        token = str(uuid4())
        expires = (datetime.now(UTC) + timedelta(seconds=self._lease_duration)).isoformat()
        result = (
            self._raw_client()
            .table("jobs")
            .update(
                {
                    "stage": "claimed",
                    "worker_id": self._worker_id,
                    "lease_expires_at": expires,
                    "execution_token": token,
                }
            )
            .eq("id", job_id)
            .eq("stage", "queued")
            .execute()
        )
        claimed = bool(result.data) if result.data is not None else False
        if claimed:
            self._remember_execution_token(job_id, token)
            self._thread_attempt.job_id = job_id
            self._thread_attempt.execution_token = token
        return claimed

    def _claim_next_job(self) -> dict[str, Any] | None:
        # Preserve the base worker's fail-soft polling behavior. The migrated RPC
        # now returns execution_token as part of the claimed Job row.
        row = super()._claim_next_job()
        if row is None:
            return None
        job_id = str(row["id"])
        token = row.get("execution_token")
        if not token:
            raise RuntimeError("claim_next_job returned no execution token")
        token = str(token)

        # A retry can become queued just before its old future's done callback
        # removes the Job from _in_flight. Do not let the polling thread create a
        # successor generation in that tiny window: the old heartbeat would
        # otherwise look up the new token and could extend the successor lease.
        with self._in_flight_lock:
            duplicate_local = job_id in self._in_flight
        if duplicate_local:
            (
                self._raw_client()
                .table("jobs")
                .update(
                    {
                        "stage": "queued",
                        "worker_id": None,
                        "lease_expires_at": None,
                        "execution_token": None,
                    }
                )
                .eq("id", job_id)
                .eq("worker_id", self._worker_id)
                .eq("execution_token", token)
                .eq("stage", "claimed")
                .execute()
            )
            return None

        self._remember_execution_token(job_id, token)
        return row

    def _renew_lease(self, job_id: str) -> None:
        """Extend only the exact execution generation that started this heartbeat."""
        token = self._execution_token(job_id)
        expires = (datetime.now(UTC) + timedelta(seconds=self._lease_duration)).isoformat()
        self._raw_client().table("jobs").update({"lease_expires_at": expires}).eq(
            "id", job_id
        ).eq("worker_id", self._worker_id).eq("execution_token", token).eq(
            "stage", "running"
        ).execute()

    def register(self, name: str, version: str, handler: Callable[..., list[str]]) -> None:
        def fenced_handler(job: Job, _raw_client: Any) -> list[str]:
            job_id = str(job.id)
            token = self._execution_token(job_id)
            with _tracer.start_as_current_span(
                "job.execution_attempt",
                attributes={
                    "job_id": job_id,
                    "worker_id": self._worker_id,
                    "execution_token": token,
                    "capability": f"{name}:{version}",
                },
            ):
                return handler(job, self._handler_client(job_id))

        super().register(name, version, fenced_handler)

    def _execute_job(self, job_row: dict, *, already_claimed: bool = False) -> None:
        job_id = str(job_row["id"])
        if already_claimed:
            token = self._execution_token(job_id)
            self._thread_attempt.job_id = job_id
            self._thread_attempt.execution_token = token
        try:
            super()._execute_job(job_row, already_claimed=already_claimed)
        finally:
            attempt_token = getattr(self._thread_attempt, "execution_token", None)
            self._thread_attempt.job_id = None
            self._thread_attempt.execution_token = None
            if attempt_token:
                self._forget_execution_token(job_id, str(attempt_token))

    def update_progress(self, job_id: str, progress: float, message: str = "") -> None:
        """Fence externally-invoked progress updates even outside the handler thread."""
        token = self._execution_token(job_id)
        clamped = max(0.0, min(1.0, float(progress)))
        self._raw_client().table("jobs").update(
            {"progress": clamped, "status_message": message}
        ).eq("id", job_id).eq("worker_id", self._worker_id).eq(
            "execution_token", token
        ).eq("stage", "running").execute()