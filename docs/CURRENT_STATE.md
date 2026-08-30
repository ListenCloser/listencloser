# Current state orientation

> **Purpose:** fast orientation to current `main` without duplicating volatile engine versions, benchmark metrics, or recent-PR inventories.
>
> This is a convenience document, not a machine-readable authority. For conflicts, follow [`docs/README.md`](README.md).

## Product shell

The current application is organized around a persistent musical **Work** with:

- authenticated private import;
- durable background processing;
- immutable artifact/version lineage;
- global transport;
- representation selection independent from playback-source selection;
- shared time selection across supported representations;
- persisted evidence/analysis and grounded product findings;
- reload/reconnect behavior over durable state.

Supported representations and playback sources are capability/artifact dependent. Do not hard-code availability from this document.

## Runtime shape

```text
Browser / Next.js
  -> authenticated /api/v1 proxy
  -> FastAPI
  -> Supabase Postgres + private Storage

Durable worker
  -> queued jobs in Supabase/Postgres
  -> music-engine adapters
  -> immutable derived artifacts/evidence
```

See `ARCHITECTURE.md` for the maintained runtime contract and runtime code/config for exact behavior.

## Analysis truthfulness

`backend/config/capabilities.json` is the machine-readable authority for analysis maturity and product exposure. Before changing or exposing analysis, inspect the registry, its policy/tests, the actual engine routing, and the relevant evaluation result.

Important invariants:

- a model/library returning output does not make a capability production-ready;
- unknown/unsupported/withheld/failed are distinct states;
- confidence must not be invented from an uncalibrated model score;
- derived claims inherit the quality/applicability limits of their required evidence;
- Score/MIDI are useful representations for some material, not universal ontology;
- experimental/evaluation adapters may intentionally remain in the repository without being product-routed.

For exact engine names, maturity, evaluation references, or validation domains, read the registry and current source rather than copying values from this page.

## Development/verification foundation

The repository currently has:

- locked Node/Python dependency manifests;
- generated OpenAPI -> TypeScript contracts;
- static checks and unit/component tests;
- database/migration/RLS integration coverage;
- mocked browser E2E;
- fresh real-stack product E2E for critical cross-boundary flows;
- security scanning;
- OpenTelemetry instrumentation plus Sentry exception reporting;
- exact-release/deployment verification contracts.

Use the evidence ladder in root `AGENTS.md`. A mocked browser run cannot prove worker/model/storage/deployed behavior, and a model benchmark cannot prove the complete product path.

## Where to look next

- **Current runtime architecture:** `ARCHITECTURE.md`
- **Product/target direction:** `MASTER_SPEC.md`
- **Agent/engineering rules:** root `AGENTS.md`
- **Operations:** `OPS.md`
- **Analysis maturity/exposure:** `backend/config/capabilities.json`
- **Accepted architecture decisions:** `adr/`
- **Open work:** GitHub issues and current PRs
- **Research/evaluation evidence:** owning evaluation reports/results

Do not maintain a “recent merged PRs” section here. Git history and GitHub already provide that information more accurately than a manually refreshed snapshot.
