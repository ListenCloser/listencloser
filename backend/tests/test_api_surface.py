from main import app


def _routes() -> set[tuple[str, str]]:
    return {
        (route.path, method) for route in app.routes for method in getattr(route, "methods", set())
    }


def test_domain_surface_contains_the_complete_understand_loop():
    routes = _routes()
    expected = {
        ("/api/v1/projects", "GET"),
        ("/api/v1/projects", "POST"),
        ("/api/v1/projects/{project_id}/works", "GET"),
        ("/api/v1/projects/{project_id}/artifacts/upload", "POST"),
        ("/api/v1/projects/{project_id}/artifacts/upload-intent", "POST"),
        ("/api/v1/projects/{project_id}/artifacts/finalize-upload", "POST"),
        ("/api/v1/workflows/understand", "POST"),
        ("/api/v1/workflows/variation", "POST"),
        ("/api/v1/workflows/compare", "POST"),
        ("/api/v1/jobs/{job_id}", "GET"),
        ("/api/v1/jobs/{job_id}/cancel", "POST"),
        ("/api/v1/jobs/{job_id}/retry", "POST"),
        ("/api/v1/works/{work_id}", "GET"),
        ("/api/v1/versions/{version_id}/entities", "GET"),
        ("/api/v1/versions/{version_id}/insights", "GET"),
    }

    assert expected <= routes


def test_legacy_music_surface_is_not_exposed():
    assert all(not route.path.startswith("/music/") for route in app.routes)


def test_domain_mutations_require_authentication(client):
    assert (
        client.post(
            "/api/v1/projects",
            json={"name": "unauthorized"},
        ).status_code
        == 401
    )


def test_direct_upload_lifecycle_requires_authentication(client):
    project_id = "00000000-0000-0000-0000-000000000001"
    descriptor = {
        "filename": "take.wav",
        "byte_size": 4,
        "content_type": "audio/wav",
    }
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/artifacts/upload-intent",
            json=descriptor,
        ).status_code
        == 401
    )
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/artifacts/finalize-upload",
            json={**descriptor, "storage_key": "not-authorized"},
        ).status_code
        == 401
    )


def test_job_controls_require_authentication(client):
    job_id = "00000000-0000-0000-0000-000000000001"

    assert client.post(f"/api/v1/jobs/{job_id}/cancel").status_code == 401
    assert client.post(f"/api/v1/jobs/{job_id}/retry").status_code == 401


def test_studio_workflows_require_authentication(client):
    body = {
        "version_id": "00000000-0000-0000-0000-000000000001",
        "project_id": "00000000-0000-0000-0000-000000000002",
    }
    assert (
        client.post(
            "/api/v1/workflows/variation", json={**body, "transpose_semitones": 2}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/workflows/compare",
            json={**body, "version_id_a": body["version_id"], "version_id_b": body["project_id"]},
        ).status_code
        == 401
    )
