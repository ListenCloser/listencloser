"""Response DTOs for top-level API endpoints."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


class HealthLiveResponse(BaseModel):
    status: Literal["alive"]
    release: str


class HealthReadyResponse(BaseModel):
    status: Literal["ready", "degraded"]
    supabase: bool
    database: bool
    storage: bool
    release: str
    reason: str | None = None


class HealthQueueResponse(BaseModel):
    status: Literal["ready", "degraded"]
    workers: int
    queued: int
    running: int
    stale_leases: int
    reason: str | None = None
    heartbeat_source: str | None = None
