"""Security regression tests for server-authoritative domain tables.

Authenticated owners may read their derived domain graph, but artifact lineage,
analysis evidence, workflows, and jobs are produced by FastAPI/the worker and
must not be forgeable directly through the browser Data API.
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
    try:
        user_response = service.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        )
        anon = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        session = anon.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:
        pytest.skip(f"Cannot provision local RLS test user: {exc}")
    return user_response.user.id, session.session.access_token


def _browser_insert(client, table: str, payload: dict):
    try:
        return client.table(table).insert(payload).execute().data
    except Exception:
        return None


def test_owner_cannot_forge_server_authoritative_domain_rows():
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
        # Seed a fully owner-visible graph through the trusted service-role path.
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

        # Browser SELECT remains available through the existing owner RLS chain.
        assert browser.table("artifacts").select("id").eq("id", artifact_id).execute().data
        assert browser.table("artifact_versions").select("id").eq("id", version_id).execute().data
        assert browser.table("workflows").select("id").eq("id", workflow_id).execute().data

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
            assert not result, f"authenticated owner must not directly INSERT into {table}"

        # No attempted row may exist behind a swallowed PostgREST/RLS error.
        for table, payload in forged.items():
            rows = service.table(table).select("id").eq("id", payload["id"]).execute().data
            assert rows == [], f"forged row unexpectedly persisted in {table}"
    finally:
        service.table("projects").delete().eq("id", project_id).execute()
        with suppress(Exception):
            service.auth.admin.delete_user(user_id)
