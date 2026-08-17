"""RLS verification tests for the domain model tables.

Tests that row-level-security policies in the 20260728_domain_tables migration
correctly enforce:
  - Cross-user isolation (ownership chains)
  - Unauthorized INSERT / UPDATE / DELETE rejection
  - Service-role bypass
  - Job write-protection for normal users
  - Workspace state isolation

Requires a live Supabase project with the domain-tables migration applied.
Set SUPABASE_URL, SUPABASE_ANON_KEY, and SUPABASE_SERVICE_ROLE_KEY in the
environment.  Tests are skipped gracefully when those variables are missing.
"""

import os
import uuid

import pytest

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

pytestmark = pytest.mark.skipif(not SUPABASE_URL, reason="SUPABASE_URL not set")

# ── helpers ──────────────────────────────────────────────────────────────────


def _sb_service():
    """Return a Supabase client that bypasses RLS (service_role key)."""
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def _sb_anon():
    """Return a Supabase client using the anon key (no user identity)."""
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def _client_as_user(access_token: str):
    """Create an anon-key client and set the JWT so RLS sees auth.uid()."""
    from supabase import create_client

    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client


def _insert_via_user(token: str, table: str, data: dict | list):
    """Insert rows as an authenticated user; returns data or None on RLS block."""
    try:
        client = _client_as_user(token)
        result = client.table(table).insert(data).execute()
        return result.data
    except Exception:
        return None


def _update_via_user(token: str, table: str, match: dict, patch: dict):
    """Update rows as an authenticated user; returns data or None on RLS block."""
    try:
        client = _client_as_user(token)
        q = client.table(table).update(patch)
        for col, val in match.items():
            q = q.eq(col, val)
        result = q.execute()
        return result.data
    except Exception:
        return None


def _delete_via_user(token: str, table: str, match: dict):
    """Delete rows as an authenticated user; returns data or None on RLS block."""
    try:
        client = _client_as_user(token)
        q = client.table(table).delete()
        for col, val in match.items():
            q = q.eq(col, val)
        result = q.execute()
        return result.data
    except Exception:
        return None


def _create_user(email: str, password: str = "test-password-123"):
    """Create a pre-confirmed user via the Admin API; return (uid, access_token).

    Skips the test (pytest.skip) when user provisioning is unavailable.
    """
    service = _sb_service()
    try:
        user_resp = service.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        )
    except Exception as exc:
        pytest.skip(f"Cannot create test user via admin API: {exc}")

    uid = user_resp.user.id

    anon = _sb_anon()
    try:
        session = anon.auth.sign_in_with_password({"email": email, "password": password})
        token = session.session.access_token
    except Exception as exc:
        pytest.skip(f"Cannot sign in as {email} (check email-confirmation settings): {exc}")

    return uid, token


# ── module-scoped user fixtures (created once, reused across tests) ──────────


@pytest.fixture(scope="module")
def user_a():
    """Data-owner user A."""
    if not (SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY):
        pytest.skip("SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY required")
    email = f"rls-a-{uuid.uuid4().hex[:8]}@example.com"
    uid, token = _create_user(email)
    return {"uid": uid, "token": token, "email": email}


@pytest.fixture(scope="module")
def user_b():
    """Unauthorised user B — must be walled off from A's data."""
    if not (SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY):
        pytest.skip("SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY required")
    email = f"rls-b-{uuid.uuid4().hex[:8]}@example.com"
    uid, token = _create_user(email)
    return {"uid": uid, "token": token, "email": email}


# ── 1. Cross-user project isolation ─────────────────────────────────────────


def test_user_a_project_invisible_to_user_b(user_a, user_b):
    """User A creates a project; User B gets zero rows on SELECT."""
    service = _sb_service()
    pid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "A-Project", "description": ""}
    ).execute()

    # User A can read it
    client_a = _client_as_user(user_a["token"])
    rows_a = client_a.table("projects").select("*").eq("id", pid).execute()
    assert len(rows_a.data) == 1
    assert rows_a.data[0]["name"] == "A-Project"

    # User B cannot read it
    client_b = _client_as_user(user_b["token"])
    rows_b = client_b.table("projects").select("*").eq("id", pid).execute()
    assert len(rows_b.data) == 0

    # Service role can see it (bypasses RLS)
    rows_sr = service.table("projects").select("*").eq("id", pid).execute()
    assert len(rows_sr.data) == 1

    # Cleanup
    service.table("projects").delete().eq("id", pid).execute()


def test_project_listing_is_scoped_to_owner(user_a, user_b):
    """User A's projects never appear in User B's list-all results."""
    service = _sb_service()
    pa = str(uuid.uuid4())
    pb = str(uuid.uuid4())

    service.table("projects").insert(
        [
            {"id": pa, "owner_id": user_a["uid"], "name": "A-Proj", "description": ""},
            {"id": pb, "owner_id": user_b["uid"], "name": "B-Proj", "description": ""},
        ]
    ).execute()

    # A sees only A's
    a_rows = _client_as_user(user_a["token"]).table("projects").select("*").execute()
    a_ids = {r["id"] for r in a_rows.data}
    assert pa in a_ids
    assert pb not in a_ids

    # B sees only B's
    b_rows = _client_as_user(user_b["token"]).table("projects").select("*").execute()
    b_ids = {r["id"] for r in b_rows.data}
    assert pb in b_ids
    assert pa not in b_ids

    service.table("projects").delete().eq("id", pa).execute()
    service.table("projects").delete().eq("id", pb).execute()


# ── 2. Full ownership chain: project → work → artifact → version ────────────


def test_ownership_chain_project_work_artifact_version(user_a, user_b):
    """User A creates the chain; User B cannot read any entity in the chain."""
    service = _sb_service()

    # Build the chain as user A via service role
    pid = str(uuid.uuid4())
    wid = str(uuid.uuid4())
    aid = str(uuid.uuid4())
    vid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "Chain-Project", "description": ""}
    ).execute()
    service.table("works").insert({"id": wid, "project_id": pid, "title": "Chain-Work"}).execute()
    service.table("artifacts").insert(
        {"id": aid, "work_id": wid, "kind": "audio_original"}
    ).execute()
    service.table("artifact_versions").insert(
        {
            "id": vid,
            "artifact_id": aid,
            "storage_key": "test/key",
            "storage_bucket": "test-bucket",
            "lineage": [],
        }
    ).execute()

    chain = {
        "projects": ("id", pid),
        "works": ("id", wid),
        "artifacts": ("id", aid),
        "artifact_versions": ("id", vid),
    }

    # User A can read every table in the chain
    client_a = _client_as_user(user_a["token"])
    for table, (col, row_id) in chain.items():
        rows = client_a.table(table).select("*").eq(col, row_id).execute()
        assert len(rows.data) == 1, f"User A should see row in {table}"

    # User B cannot read any table in the chain
    client_b = _client_as_user(user_b["token"])
    for table, (col, row_id) in chain.items():
        rows = client_b.table(table).select("*").eq(col, row_id).execute()
        assert len(rows.data) == 0, f"User B must not see row in {table}"

    # Cleanup (cascade deletes from project)
    service.table("projects").delete().eq("id", pid).execute()


# ── 3. RLS prevents unauthorized INSERT ─────────────────────────────────────


def test_cannot_insert_work_into_foreign_project(user_a, user_b):
    """User B cannot INSERT a work into User A's project."""
    service = _sb_service()
    pid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "A-Project", "description": ""}
    ).execute()

    result = _insert_via_user(
        user_b["token"],
        "works",
        {"project_id": pid, "title": "Should-Fail"},
    )
    assert result is None, "RLS should block INSERT into another user's project"

    # Verify via service role: no stray row created
    rows = service.table("works").select("*").eq("project_id", pid).execute()
    assert len(rows.data) == 0

    service.table("projects").delete().eq("id", pid).execute()


def test_cannot_insert_workspace_state_of_another_user(user_a, user_b):
    """User B cannot INSERT a workspace_state for User A's project."""
    service = _sb_service()
    pid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "WS-Proj", "description": ""}
    ).execute()

    result = _insert_via_user(
        user_b["token"],
        "workspace_states",
        {"project_id": pid, "owner_id": user_a["uid"], "tab": "analyze"},
    )
    assert result is None, "RLS should block workspace_state INSERT for another user"

    service.table("projects").delete().eq("id", pid).execute()


# ── 4. RLS prevents unauthorized UPDATE ─────────────────────────────────────


def test_cannot_update_foreign_project(user_a, user_b):
    """User B cannot UPDATE User A's project."""
    service = _sb_service()
    pid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "Original", "description": ""}
    ).execute()

    result = _update_via_user(
        user_b["token"],
        "projects",
        match={"id": pid},
        patch={"name": "Hijacked"},
    )
    assert result is None, "RLS should block UPDATE on another user's project"

    # Project name unchanged
    row = service.table("projects").select("name").eq("id", pid).single().execute()
    assert row.data["name"] == "Original"

    service.table("projects").delete().eq("id", pid).execute()


def test_cannot_update_foreign_work(user_a, user_b):
    """User B cannot UPDATE a work that belongs to User A's project."""
    service = _sb_service()
    pid = str(uuid.uuid4())
    wid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "P", "description": ""}
    ).execute()
    service.table("works").insert(
        {"id": wid, "project_id": pid, "title": "Original-Work"}
    ).execute()

    result = _update_via_user(
        user_b["token"],
        "works",
        match={"id": wid},
        patch={"title": "Hijacked-Work"},
    )
    assert result is None, "RLS should block UPDATE on another user's work"

    row = service.table("works").select("title").eq("id", wid).single().execute()
    assert row.data["title"] == "Original-Work"

    service.table("projects").delete().eq("id", pid).execute()


# ── 5. RLS prevents unauthorized DELETE ─────────────────────────────────────


def test_cannot_delete_foreign_project(user_a, user_b):
    """User B cannot DELETE User A's project."""
    service = _sb_service()
    pid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "To-Delete", "description": ""}
    ).execute()

    result = _delete_via_user(
        user_b["token"],
        "projects",
        match={"id": pid},
    )
    assert result is None, "RLS should block DELETE on another user's project"

    # Project still exists
    row = service.table("projects").select("id").eq("id", pid).execute()
    assert len(row.data) == 1

    service.table("projects").delete().eq("id", pid).execute()


def test_cannot_delete_foreign_work(user_a, user_b):
    """User B cannot DELETE a work that belongs to User A's project."""
    service = _sb_service()
    pid = str(uuid.uuid4())
    wid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "P", "description": ""}
    ).execute()
    service.table("works").insert({"id": wid, "project_id": pid, "title": "Keep-Me"}).execute()

    result = _delete_via_user(user_b["token"], "works", match={"id": wid})
    assert result is None, "RLS should block DELETE on another user's work"

    row = service.table("works").select("id").eq("id", wid).execute()
    assert len(row.data) == 1

    service.table("projects").delete().eq("id", pid).execute()


# ── 6. Service role bypasses RLS ────────────────────────────────────────────


def test_service_role_can_read_any_project(user_a, user_b):
    """The service_role key bypasses RLS and can read both users' projects."""
    service = _sb_service()
    pa = str(uuid.uuid4())
    pb = str(uuid.uuid4())

    service.table("projects").insert(
        [
            {"id": pa, "owner_id": user_a["uid"], "name": "SR-A", "description": ""},
            {"id": pb, "owner_id": user_b["uid"], "name": "SR-B", "description": ""},
        ]
    ).execute()

    rows = service.table("projects").select("*").in_("id", [pa, pb]).execute()
    seen = {r["id"] for r in rows.data}
    assert pa in seen and pb in seen, "Service role must see all projects"

    service.table("projects").delete().in_("id", [pa, pb]).execute()


def test_service_role_can_write_any_project(user_a, user_b):
    """The service_role key can INSERT/UPDATE/DELETE any user's data."""
    service = _sb_service()
    pid = str(uuid.uuid4())

    # INSERT regardless of owner
    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "Svc-Write", "description": ""}
    ).execute()

    # UPDATE regardless of owner
    service.table("projects").update({"name": "Svc-Modified"}).eq("id", pid).execute()
    row = service.table("projects").select("name").eq("id", pid).single().execute()
    assert row.data["name"] == "Svc-Modified"

    # DELETE regardless of owner
    service.table("projects").delete().eq("id", pid).execute()
    rows = service.table("projects").select("*").eq("id", pid).execute()
    assert len(rows.data) == 0


# ── 7. Jobs are read-only for authenticated users ───────────────────────────


def test_jobs_readable_by_owner(user_a):
    """Authenticated user can SELECT their own jobs (via workflow→project chain)."""
    service = _sb_service()
    pid = str(uuid.uuid4())
    wfid = str(uuid.uuid4())
    jid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "Job-Proj", "description": ""}
    ).execute()
    service.table("workflows").insert(
        {"id": wfid, "project_id": pid, "kind": "understand", "parameters": {}}
    ).execute()
    service.table("jobs").insert(
        {
            "id": jid,
            "workflow_id": wfid,
            "capability_name": "dummy",
            "capability_version": "1.0",
            "stage": "queued",
        }
    ).execute()

    client_a = _client_as_user(user_a["token"])
    rows = client_a.table("jobs").select("*").eq("id", jid).execute()
    assert len(rows.data) == 1, "Owner must be able to SELECT own jobs"

    service.table("projects").delete().eq("id", pid).execute()


def test_jobs_invisible_to_foreign_user(user_a, user_b):
    """User B cannot SELECT jobs belonging to User A's workflow chain."""
    service = _sb_service()
    pid = str(uuid.uuid4())
    wfid = str(uuid.uuid4())
    jid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "J-P", "description": ""}
    ).execute()
    service.table("workflows").insert(
        {"id": wfid, "project_id": pid, "kind": "understand", "parameters": {}}
    ).execute()
    service.table("jobs").insert(
        {
            "id": jid,
            "workflow_id": wfid,
            "capability_name": "dummy",
            "capability_version": "1.0",
            "stage": "queued",
        }
    ).execute()

    client_b = _client_as_user(user_b["token"])
    rows = client_b.table("jobs").select("*").eq("id", jid).execute()
    assert len(rows.data) == 0, "User B must not see User A's jobs"

    service.table("projects").delete().eq("id", pid).execute()


def test_user_cannot_insert_job(user_a):
    """An authenticated user cannot INSERT into jobs (no RLS insert policy)."""
    service = _sb_service()
    pid = str(uuid.uuid4())
    wfid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "J-Ins", "description": ""}
    ).execute()
    service.table("workflows").insert(
        {"id": wfid, "project_id": pid, "kind": "understand", "parameters": {}}
    ).execute()

    result = _insert_via_user(
        user_a["token"],
        "jobs",
        {
            "workflow_id": wfid,
            "capability_name": "dummy",
            "capability_version": "1.0",
            "stage": "queued",
        },
    )
    assert result is None, "RLS must block user INSERT into jobs"

    # Verify no row was created
    rows = service.table("jobs").select("*").eq("workflow_id", wfid).execute()
    assert len(rows.data) == 0

    service.table("projects").delete().eq("id", pid).execute()


def test_user_cannot_update_job(user_a):
    """An authenticated user cannot UPDATE jobs (no RLS update policy)."""
    service = _sb_service()
    pid = str(uuid.uuid4())
    wfid = str(uuid.uuid4())
    jid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "J-Up", "description": ""}
    ).execute()
    service.table("workflows").insert(
        {"id": wfid, "project_id": pid, "kind": "compare", "parameters": {}}
    ).execute()
    service.table("jobs").insert(
        {
            "id": jid,
            "workflow_id": wfid,
            "capability_name": "dummy",
            "capability_version": "1.0",
            "stage": "queued",
        }
    ).execute()

    result = _update_via_user(
        user_a["token"],
        "jobs",
        match={"id": jid},
        patch={"stage": "succeeded"},
    )
    assert result is None, "RLS must block user UPDATE on jobs"

    # Stage should be unchanged
    row = service.table("jobs").select("stage").eq("id", jid).single().execute()
    assert row.data["stage"] == "queued"

    service.table("projects").delete().eq("id", pid).execute()


def test_service_role_can_mutate_jobs(user_a):
    """Service role can INSERT and UPDATE jobs (no RLS restriction)."""
    service = _sb_service()
    pid = str(uuid.uuid4())
    wfid = str(uuid.uuid4())
    jid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "J-Svc", "description": ""}
    ).execute()
    service.table("workflows").insert(
        {"id": wfid, "project_id": pid, "kind": "export", "parameters": {}}
    ).execute()

    # INSERT via service role
    service.table("jobs").insert(
        {
            "id": jid,
            "workflow_id": wfid,
            "capability_name": "dummy",
            "capability_version": "1.0",
            "stage": "queued",
        }
    ).execute()
    rows = service.table("jobs").select("*").eq("id", jid).execute()
    assert len(rows.data) == 1

    # UPDATE via service role
    service.table("jobs").update({"stage": "running"}).eq("id", jid).execute()
    row = service.table("jobs").select("stage").eq("id", jid).single().execute()
    assert row.data["stage"] == "running"

    service.table("projects").delete().eq("id", pid).execute()


# ── 8. Workspace state isolation ────────────────────────────────────────────


def test_workspace_state_invisible_to_other_user(user_a, user_b):
    """User A's workspace state is invisible to User B."""
    service = _sb_service()
    pid = str(uuid.uuid4())
    wsid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "WS-Project", "description": ""}
    ).execute()
    service.table("workspace_states").insert(
        {
            "id": wsid,
            "project_id": pid,
            "owner_id": user_a["uid"],
            "tab": "score",
            "selection": {"notes": []},
        }
    ).execute()

    # User A sees it
    client_a = _client_as_user(user_a["token"])
    rows_a = client_a.table("workspace_states").select("*").eq("id", wsid).execute()
    assert len(rows_a.data) == 1
    assert rows_a.data[0]["tab"] == "score"

    # User B sees nothing
    client_b = _client_as_user(user_b["token"])
    rows_b = client_b.table("workspace_states").select("*").eq("id", wsid).execute()
    assert len(rows_b.data) == 0

    service.table("projects").delete().eq("id", pid).execute()


def test_workspace_state_upsert_respects_owner(user_a, user_b):
    """User A can create/update own workspace state; User B cannot touch it."""
    service = _sb_service()
    pid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "WS-Upsert", "description": ""}
    ).execute()

    # User A creates workspace state
    result_a = _insert_via_user(
        user_a["token"],
        "workspace_states",
        {"project_id": pid, "owner_id": user_a["uid"], "tab": "explore"},
    )
    assert result_a is not None, "User A must be able to INSERT own workspace state"

    # User B cannot update User A's workspace state
    result_b = _update_via_user(
        user_b["token"],
        "workspace_states",
        match={"project_id": pid, "owner_id": user_a["uid"]},
        patch={"tab": "hijacked"},
    )
    assert (
        result_b is None or len(result_b) == 0
    ), "RLS should block User B from updating A's workspace state"

    # Tab should remain unchanged
    row = service.table("workspace_states").select("tab").eq("project_id", pid).single().execute()
    assert row.data["tab"] == "explore"

    service.table("projects").delete().eq("id", pid).execute()


def test_workspace_state_listing_scoped_to_owner(user_a, user_b):
    """Each user only sees their own workspace states in list queries."""
    service = _sb_service()
    pid = str(uuid.uuid4())

    service.table("projects").insert(
        {"id": pid, "owner_id": user_a["uid"], "name": "WS-List", "description": ""}
    ).execute()

    # User A creates workspace state
    _insert_via_user(
        user_a["token"],
        "workspace_states",
        {"project_id": pid, "owner_id": user_a["uid"], "tab": "analyze"},
    )

    # User B's list does not include A's state
    client_b = _client_as_user(user_b["token"])
    rows_b = client_b.table("workspace_states").select("*").execute()
    b_ids = {r["project_id"] for r in rows_b.data}
    assert pid not in b_ids, "User B must not see User A's workspace state"

    # Verify via service role
    rows_sr = service.table("workspace_states").select("*").eq("project_id", pid).execute()
    assert len(rows_sr.data) == 1

    service.table("projects").delete().eq("id", pid).execute()
