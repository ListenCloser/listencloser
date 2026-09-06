# Listen Closer

Listen Closer is a music-understanding workspace for moving through a recording, its musical representations, and evidence-backed analysis without losing your place in the music.

Import a recording once, then listen and inspect the same persistent Work through synchronized Waveform, Piano Roll, Score, Spectrogram, Breakdown, and Ask surfaces. Derived results keep exact lineage back to their source rather than silently replacing it.

```text
recording
  ↓
persistent Work + immutable source Version
  ↓
durable processing
  ↓
versioned musical evidence + derived artifacts
  ↓
synchronized listening / inspection / analysis
```

The product prefers an explicit unavailable/unknown state over fabricating musical facts or confidence.

## Quick start

Requirements are checked by the repository itself:

```bash
npm run doctor
npm run bootstrap
npm run dev
```

The web app runs through the `apps/web` workspace. The FastAPI API and durable worker are the independent uv project under `services/backend`.

Common verification commands:

```bash
npm run check:fast       # normal inner-loop gate
npm run check:frontend   # frontend only
npm run check:backend    # backend only
npm run check:e2e        # built web app + browser tests
npm run check:realstack  # isolated full-stack golden path
```

`check:realstack` and database verification require Docker and the pinned local tooling described by `npm run doctor`.

## Repository map

```text
apps/web/                  Next.js application, frontend source, browser tests, public assets
services/backend/          FastAPI API, durable worker, music-engine adapters, Python tests
docs/                      architecture, product, operations, ADRs, evaluation methodology
supabase/                  database/storage migrations and local Supabase configuration
openapi/                   checked generated API contract
evaluation/                durable decision evidence and benchmark results
observability/             repository-owned observability configuration
scripts/                   repository development, verification, deployment and recovery commands
.github/                   hosted execution and repository automation
contract-dependencies.json minimal hard dependency graph between focused GitHub contracts
```

The root intentionally owns only cross-project contracts and tool-required configuration. Feature-private code belongs with the feature that changes with it; shared code should be promoted only when it has a real second consumer.

### Web

```text
apps/web/src/app/          Next.js routes and route composition
apps/web/src/components/   product UI and genuinely shared React primitives
apps/web/src/lib/          cross-feature frontend contracts and client infrastructure
apps/web/tests/            frontend, browser and system verification
```

### Backend

The backend is a modular monolith: one API/worker project with replaceable music-engine adapters, not a collection of per-model services. Product capability contracts and persisted provenance are stable even when an engine changes.

For the current runtime boundaries and data flow, read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Engineering rules

A few repository principles matter more than the exact folder names:

- **Delete before abstracting.** Prefer framework/platform behavior over repository-owned commodity machinery.
- **Colocate by responsibility.** Code that changes together should normally live together.
- **Promote sharing deliberately.** Do not create generic `shared`, `common`, or `utils` layers preemptively.
- **Keep product truth exact.** Work/Version lineage, playback authority, evidence provenance, and durable Job state must not be guessed from recency or UI state.
- **Keep engines replaceable.** A new MIR engine should normally fit behind an existing semantic capability boundary instead of creating a new API, persistence model, UI architecture, or service.
- **Use the same verification locally and in CI.** GitHub Actions should execute repository-owned checks rather than implement a second test algorithm.

Autonomous contributors should read [`AGENTS.md`](AGENTS.md) before changing code.

## Documentation

Use the narrowest authority for the question you are answering:

- [`docs/product/PRODUCT.md`](docs/product/PRODUCT.md) — durable product identity and principles
- [`docs/product/ROADMAP.md`](docs/product/ROADMAP.md) — current product sequencing and portfolio posture
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — shipped runtime architecture
- [`docs/EVALUATION_METHODOLOGY.md`](docs/EVALUATION_METHODOLOGY.md) — evaluation and benchmark method
- [`docs/EVALUATION_DECISIONS.md`](docs/EVALUATION_DECISIONS.md) — current cross-track evaluation conclusions
- [`docs/OPS.md`](docs/OPS.md) / [`docs/RECOVERY.md`](docs/RECOVERY.md) — production operation and recovery
- [`docs/adr/`](docs/adr/) — durable architectural decisions and revisit conditions

Executable code, migrations, generated contracts, and the deployed release identity take precedence when prose drifts from the running system.
