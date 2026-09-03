"""FastAPI execution-boundary invariants for synchronous persistence clients."""

from __future__ import annotations

import importlib
import inspect

from ask.api import create_ask

PERSISTENCE_MODULES = (
    "domain.api.projects_works",
    "domain.api.artifacts_versions",
    "domain.api.evidence",
    "domain.api.workflows_jobs",
    "domain.relation_api",
    "domain.upload_api",
)


def test_persistence_router_endpoints_are_sync() -> None:
    async_endpoints = []
    for module_name in PERSISTENCE_MODULES:
        router = importlib.import_module(module_name).router
        async_endpoints.extend(
            route.endpoint.__name__
            for route in router.routes
            if inspect.iscoroutinefunction(route.endpoint)
        )
    assert async_endpoints == []


def test_ask_keeps_real_async_provider_boundary_and_offloads_sync_reads() -> None:
    assert inspect.iscoroutinefunction(create_ask)
    assert inspect.getsource(create_ask).count("await run_in_threadpool(") == 2
