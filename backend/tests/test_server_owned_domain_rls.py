"""Security regression tests for server-authoritative domain tables.

ListenCloser domain state is read and written through FastAPI/the worker. Browser
Supabase access is reserved for Auth and authorized Storage operations, so an
authenticated owner must not be able to read or forge domain rows through the
PostgREST Data API directly.
"""

from __future__ import annotations

import os
import uuid
from contextlib import suppress

import pytest

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

pytestmark = [
    pytest.mark.real_stack,
    pytest.mark.skipif(not SUPABASE_URL, reason="SUPABASE_URL not set"),
]


def _service_client():
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def _user_client(access_token: str):
    from supabase import create_client

    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client


def _create_user():
    from supabase import create_client

    service = _service_client()
    email = f"server-owned-{uuid.uuid4().hex[:10]}@example.com"
    password = "test-password-123"
    user_response = service.auth.admin.create_user(
        {"email": email, "password": password, "email_confirm": True}
    )
    anon = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    session = anon.auth.sign_in_with_password({"email": email, "password": password})
    return user_response.user.id, session.session.access_token


def _browser_select(client, table: str, row_id: str):
    try:
        return client.table(table).select("id").eq("id", row_id).execute().data
    except Exception:
        return None


def _browser_insert(client, table: str, payload: dict):
    try:
        return client.table(table).insert(payload).execute().data
    except Exception:
        return None


def test_browser_cannot_access_server_authoritative_domain_rows():
    if not (SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY):
        pytest.skip("SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY required")

    service = _service_client()
    user_id, token = _create_user()
    browser = _user_client(token)

    project_id = str(uuid.uuid4())
    work_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())

    try:
        # Seed a representative domain graph through the trusted service-role path.
        service.table("projects").insert(
            {
                "id": project_id,
                "owner_id": user_id,
                "name": "Server-owned RLS fixture",
                "description": "",
            }
        ).execute()
        service.table("works").insert(
            {"id": work_id, "project_id": project_id, "title": "Fixture"}
        ).execute()
        service.table("artifacts").insert(
            {"id": artifact_id, "work_id": work_id, "kind": "audio_original"}
        ).execute()
        service.table("artifact_versions").insert(
            {
                "id": version_id,
                "artifact_id": artifact_id,
                "storage_key": f"users/{user_id}/fixture.wav",
                "storage_bucket": "artifacts",
                "lineage": [],
            }
        ).execute()
        service.table("workflows").insert(
            {"id": workflow_id, "project_id": project_id, "kind": "understand"}
        ).execute()

        # The trusted persistence path remains readable after browser ACL removal.
        trusted_rows = {
            "projects": project_id,
            "works": work_id,
            "artifacts": artifact_id,
            "artifact_versions": version_id,
            "workflows": workflow_id,
        }
        for table, row_id in trusted_rows.items():
            rows = service.table(table).select("id").eq("id", row_id).execute().data
            assert rows, f"service role unexpectedly lost access to {table}"

        # Owner-scoped RLS remains defense in depth, but browser roles no longer
        # receive table privileges that make the domain schema a second data API.
        for table, row_id in trusted_rows.items():
            assert not _browser_select(
                browser, table, row_id
            ), f"authenticated browser must not directly SELECT from {table}"

        forged = {
            "artifacts": {
                "id": str(uuid.uuid4()),
                "work_id": work_id,
                "kind": "audio_original",
            },
            "artifact_versions": {
                "id": str(uuid.uuid4()),
                "artifact_id": artifact_id,
                "storage_key": "forged/known-object-key",
                "storage_bucket": "artifacts",
                "lineage": [],
            },
            "entities": {
                "id": str(uuid.uuid4()),
                "version_id": version_id,
                "kind": "note",
                "label": "forged",
            },
            "insights": {
                "id": str(uuid.uuid4()),
                "version_id": version_id,
                "kind": "summary",
                "claim": "forged",
            },
            "alignments": {
                "id": str(uuid.uuid4()),
                "version_id": version_id,
                "target_version_id": version_id,
                "kind": "timeline",
                "source_unit": "seconds",
                "target_unit": "seconds",
            },
            "workflows": {
                "id": str(uuid.uuid4()),
                "project_id": project_id,
                "kind": "understand",
            },
            "jobs": {
                "id": str(uuid.uuid4()),
                "workflow_id": workflow_id,
                "capability_name": "security.test",
                "capability_version": "1",
            },
        }

        for table, payload in forged.items():
            result = _browser_insert(browser, table, payload)
            assert not result, f"authenticated browser must not directly INSERT into {table}"

        # No attempted row may exist behind a swallowed PostgREST/ACL error.
        for table, payload in forged.items():
            rows = service.table(table).select("id").eq("id", payload["id"]).execute().data
            assert rows == [], f"forged row unexpectedly persisted in {table}"
    finally:
        service.table("projects").delete().eq("id", project_id).execute()
        with suppress(Exception):
            service.auth.admin.delete_user(user_id)
