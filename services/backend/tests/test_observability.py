from fastapi.testclient import TestClient


def test_health_returns_request_id_header(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
    assert resp.json()["status"] == "ok"


def test_health_ready_shape(client: TestClient):
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"ready", "degraded"}
    assert "supabase" in body


def test_request_id_passed_through(client: TestClient):
    resp = client.get("/health/live", headers={"x-request-id": "abc-123"})
    assert resp.headers["x-request-id"] == "abc-123"
