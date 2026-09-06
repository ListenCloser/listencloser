"""Response DTOs for top-level API endpoints."""

from datetime import datetime
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
    queue_ready: bool
    queue_depth: int
    queue_visible_depth: int
    oldest_age_seconds: int | None = None
    total_messages: int
    sampled_at: datetime | None = None
    reason: str | None = None
    heartbeat_source: str | None = None
