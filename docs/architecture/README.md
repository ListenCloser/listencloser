# Shipped architecture map

This directory describes the **currently shipped system**, not the target product architecture.

Verified baseline: `main@e808e7077c3bf6272140e922a065ff50b4798aaf` (2026-08-30).

## Why this exists

A contributor should be able to answer the following without reconstructing the system from old pull requests:

- what runs in the browser, API process, worker process, database, and storage;
- how an import becomes durable derived artifacts and evidence;
- which component owns authentication, authorization, workflow intent, execution, persistence, and rendering;
- which state is durable and which is browser-local;
- which OSS/models are used for which responsibility and what actually makes one production-safe;
- how evaluation flows from dataset/baseline/metric to durable result and capability policy;
- where production engine selection differs from library defaults;
- which files are authoritative when documentation and code disagree.

These documents are descriptive. If a diagram cannot be made truthful without inventing a clean boundary that does not exist in code, the ambiguity is an architecture finding rather than something to hide in the drawing.

## Map

| View | Purpose |
|---|---|
| [System context](context.md) | Product boundary, people, external systems and trust boundaries |
| [Containers](containers.md) | Runtime processes/services and their responsibilities |
| [Backend components](backend-components.md) | FastAPI, repositories, workflow construction, durable worker and engines |
| [Frontend components](frontend-components.md) | Workspace coordinator, API/data layer, representations, transport and Inspector |
| [Data model](data-model.md) | Project/Work/Artifact/Version lineage plus evidence and durable execution |
| [Understand sequence](dynamic-understand.md) | Import → persist → queue → execute → hydrate/reopen |
| [OSS/model inventory](oss-inventory.md) | Framework/model responsibility map without duplicating lockfile versions |
| [Evaluation architecture](evaluation.md) | Dataset → exact baseline/candidate → metric → result → product decision |
| [Control plane](control-plane.md) | Local checks, CI evidence tiers, build/deploy/smoke boundary |
| [Sources of truth](sot.md) | Question → canonical machine/code authority |

## Diagram rules

The diagrams follow the spirit of C4 without creating a diagramming platform:

1. do not mix system, container and component abstraction levels without saying so;
2. every arrow is directional and names the interaction;
3. synchronous HTTP and durable asynchronous work are visually distinct;
4. production and evaluation are separate boundaries;
5. volatile facts such as package versions and capability maturity link to machine authorities instead of being copied here;
6. trust boundaries are explicit: browser user token, service-role backend/worker access, private Storage, and signed resource URLs.

## Authority and freshness

Architecture prose is not allowed to become a second configuration system.

When a fact has a machine authority, that authority wins:

- HTTP contract → FastAPI OpenAPI and checked-in generated `lib/api-types.ts`;
- database shape/security → `supabase/migrations/` plus database integration tests;
- capability maturity/exposure → `backend/config/capabilities.json` and policy tests;
- engine construction/routing → `backend/engines/registry.py` plus deployment environment configuration;
- dependency versions → `package*.json`, `backend/pyproject.toml`, `backend/uv.lock`;
- CI behavior → `.github/workflows/`, protected branch configuration and repository check scripts;
- product/future architecture → `docs/MASTER_SPEC.md` and accepted ADRs.

`docs/ARCHITECTURE.md` remains the short orientation page. This directory is the deeper descriptive map.

## Known architecture findings surfaced by the map

These are tracked elsewhere and are **not rationalized away** here:

- `backend/domain/capabilities.py` combines persistence helpers, orchestration, handlers and registration (#417);
- `app/page.tsx` remains an application coordinator as well as a page (#417);
- backend import/package ownership is ambiguous enough that pytest currently needs multiple import roots (#417);
- public API exposure and worker handler registration are not yet fully independent (#632);
- API/core and worker/ML dependency ownership is not yet split (#287);
- async HTTP → persisted Job → worker trace continuity needs an explicit propagation contract (#637);
- evaluation code, durable result evidence and product promotion decisions need one traceable architecture (#636);
- frontend global styling still contains historical versioned override layers (#523).

Parent reconstruction program: #634. Architecture implementation/refactor owner: #417.