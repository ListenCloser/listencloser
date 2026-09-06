from types import SimpleNamespace
from unittest.mock import MagicMock

import health_api


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
    monkeypatch.setattr(health_api, "get_supabase", lambda: None)

    response = client.get("/health/queue")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "workers": 0,
        "queue_ready": False,
        "queue_depth": 0,
        "queue_visible_depth": 0,
        "total_messages": 0,
        "reason": "supabase not configured",
    }


def test_queue_health_reports_pgmq_metrics_and_worker(client, monkeypatch):
    supabase = MagicMock()
    supabase.rpc.return_value.execute.return_value = SimpleNamespace(
        data={
            "queue_ready": True,
            "queue_depth": 3,
            "queue_visible_depth": 2,
            "oldest_age_seconds": 17,
            "total_messages": 41,
            "sampled_at": "2026-09-05T00:27:06+00:00",
        }
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
    supabase.table.return_value = workers
    monkeypatch.setattr(health_api, "get_supabase", lambda: supabase)

    response = client.get("/health/queue")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "workers": 1,
        "queue_ready": True,
        "queue_depth": 3,
        "queue_visible_depth": 2,
        "oldest_age_seconds": 17,
        "total_messages": 41,
        "sampled_at": "2026-09-05T00:27:06Z",
        "heartbeat_source": "database",
    }
    supabase.rpc.assert_called_once_with("job_queue_metrics", {})


def test_queue_health_degrades_when_pgmq_metrics_fail(client, monkeypatch):
    supabase = MagicMock()
    supabase.rpc.return_value.execute.side_effect = RuntimeError("pgmq unavailable")
    monkeypatch.setattr(health_api, "get_supabase", lambda: supabase)

    response = client.get("/health/queue")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "workers": 0,
        "queue_ready": False,
        "queue_depth": 0,
        "queue_visible_depth": 0,
        "total_messages": 0,
        "reason": "job queue unavailable",
    }
