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
        ("/api/v1/workflows/understand", "POST"),
        ("/api/v1/jobs/{job_id}", "GET"),
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
