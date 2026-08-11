from types import SimpleNamespace
from unittest.mock import MagicMock

import main


def test_health_live(client):
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"
    assert "release" in r.json()


def test_health_ready(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("ready", "degraded")
    assert "supabase" in data


def test_queue_health_degrades_without_supabase(client, monkeypatch):
    monkeypatch.setattr(main, "get_supabase_client", lambda: None)

    response = client.get("/health/queue")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_queue_health_reports_worker_and_active_jobs(client, monkeypatch):
    jobs = MagicMock()
    jobs.select.return_value.in_.return_value.execute.return_value = SimpleNamespace(
        data=[
            {"stage": "queued", "lease_expires_at": None},
            {"stage": "running", "lease_expires_at": "2999-01-01T00:00:00+00:00"},
        ]
    )
    workers = MagicMock()
    workers.select.return_value.gte.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "status": "running",
                "heartbeat_at": "2999-01-01T00:00:00+00:00",
                "capabilities": ["understand:1.0"],
            }
        ]
    )
    supabase = MagicMock()
    supabase.table.side_effect = lambda name: (jobs if name == "jobs" else workers)
    monkeypatch.setattr(main, "get_supabase_client", lambda: supabase)

    response = client.get("/health/queue")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "workers": 1,
        "queued": 1,
        "running": 1,
        "stale_leases": 0,
        "heartbeat_source": "database",
    }
