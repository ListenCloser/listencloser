"""Thin Auth/JWT/PostgREST smoke for domain RLS.

Durable row-policy semantics are tested directly and deterministically in
``supabase/tests/domain_rls.test.sql`` via ``supabase test db``. This file keeps
only the integration boundary SQL tests cannot prove: real Auth user creation,
JWT propagation through PostgREST, owner-scoped reads, browser write denial on
server-owned state, and service-role mutation.
"""

import contextlib
import os
import uuid

import pytest
from postgrest.exceptions import APIError

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

pytestmark = [
    pytest.mark.real_stack,
    pytest.mark.skipif(not SUPABASE_URL, reason="SUPABASE_URL not set"),
]


def _sb_service():
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def _sb_anon():
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def _client_as_user(access_token: str):
    from supabase import create_client

    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client


def _create_user(prefix: str, password: str = "test-password-123") -> dict[str, str]:
    service = _sb_service()
    email = f"rls-{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    try:
        user_resp = service.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        )
        session = _sb_anon().auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception as exc:
        pytest.skip(f"Cannot provision local Auth user: {exc}")

    return {
        "uid": str(user_resp.user.id),
        "token": session.session.access_token,
    }


@pytest.fixture(scope="module")
def users():
    if not (SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY):
        pytest.skip("SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY required")

    service = _sb_service()
    user_a = _create_user("a")
    user_b = _create_user("b")
    yield user_a, user_b

    for user in (user_a, user_b):
        # The local database is ephemeral in CI; user cleanup is best-effort and
        # must not mask the RLS contract result.
        with contextlib.suppress(Exception):
            service.auth.admin.delete_user(user["uid"])


def test_real_auth_jwt_postgrest_rls_boundary(users):
    """Real JWTs enforce ownership while service_role retains server authority."""
    user_a, user_b = users
    service = _sb_service()
    client_a = _client_as_user(user_a["token"])
    client_b = _client_as_user(user_b["token"])

    project_id = str(uuid.uuid4())
    work_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    # Prove Auth -> JWT -> PostgREST reaches the owner-scoped INSERT policy.
    created_project = client_a.table("projects").insert(
        {
            "id": project_id,
            "owner_id": user_a["uid"],
            "name": "RLS smoke",
            "description": "",
        }
    ).execute()
    assert len(created_project.data) == 1

    # Seed derived/server-owned lineage through the service role.
    service.table("works").insert(
        {"id": work_id, "project_id": project_id, "title": "RLS work"}
    ).execute()
    service.table("artifacts").insert(
        {"id": artifact_id, "work_id": work_id, "kind": "audio_original"}
    ).execute()
    service.table("artifact_versions").insert(
        {
            "id": version_id,
            "artifact_id": artifact_id,
            "storage_key": "rls-smoke/source.wav",
            "storage_bucket": "artifacts",
            "lineage": [],
        }
    ).execute()
    service.table("workflows").insert(
        {"id": workflow_id, "project_id": project_id, "kind": "understand", "parameters": {}}
    ).execute()
    service.table("jobs").insert(
        {
            "id": job_id,
            "workflow_id": workflow_id,
            "capability_name": "understand",
            "capability_version": "1.0",
            "stage": "queued",
        }
    ).execute()

    owned_rows = {
        "projects": project_id,
        "works": work_id,
        "artifacts": artifact_id,
        "artifact_versions": version_id,
        "workflows": workflow_id,
        "jobs": job_id,
    }
    for table, row_id in owned_rows.items():
        assert len(client_a.table(table).select("id").eq("id", row_id).execute().data) == 1
        assert len(client_b.table(table).select("id").eq("id", row_id).execute().data) == 0

    workspace = client_a.table("workspace_states").insert(
        {"project_id": project_id, "owner_id": user_a["uid"], "tab": "analyze"}
    ).execute()
    assert len(workspace.data) == 1
    workspace_id = workspace.data[0]["id"]
    assert (
        len(client_b.table("workspace_states").select("id").eq("id", workspace_id).execute().data)
        == 0
    )

    # Browser JWTs have SELECT-only grants on server-owned Jobs. The direct SQL
    # suite proves the broader policy/privilege matrix; this proves PostgREST
    # surfaces the denial rather than bypassing it.
    with pytest.raises(APIError):
        client_a.table("jobs").insert(
            {
                "workflow_id": workflow_id,
                "capability_name": "understand",
                "capability_version": "1.0",
            }
        ).execute()

    # Conversely, the service-role API path must retain server mutation authority.
    service.table("jobs").update({"stage": "running"}).eq("id", job_id).execute()
    job = service.table("jobs").select("stage").eq("id", job_id).single().execute()
    assert job.data["stage"] == "running"

    service.table("projects").delete().eq("id", project_id).execute()
