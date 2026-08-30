# Repository census

This directory is the checked-in evidence ledger for #289 / reconstruction program #634.

It is intentionally **not** a generic code-quality score. The census records concrete repository objects/responsibilities that should be deleted, consolidated, renamed/moved, refactored, kept, or investigated.

## Current artifact

`repository-census.json` is a partial baseline anchored to an exact `main` SHA. It records which inventory passes have been performed and which remain, so a small initial audit cannot be mistaken for complete repository coverage.

Validate its structural contract with:

```bash
python scripts/validate_repository_census.py
```

The validator is intentionally stdlib-only and report-oriented. It checks schema/enum/required-field integrity; it does **not** decide whether an architectural judgment is correct.

## Classification semantics

### `DELETE`

Proven unreachable/superseded and safe to remove once the listed verification is satisfied.

Static-tool output by itself is never sufficient evidence for DELETE.

### `CONSOLIDATE`

Two or more sources own substantially the same responsibility and one canonical replacement/owner can be named.

### `RENAME_MOVE`

Behavior is intentional, but location/name/lifecycle communicates the wrong ownership or historical convention.

### `REFACTOR`

The responsibility is active, but boundaries are demonstrably unsafe/ambiguous/high-contention. Typical evidence: independently changing responsibilities in one coordinator, import ambiguity, public/internal policy conflation, or retry/authority semantics that cannot be expressed cleanly.

### `KEEP`

Explicitly reviewed and intentional. KEEP is useful in a cleanup census because it prevents later agents from rediscovering and deleting a dynamic/fallback/research path whose purpose is known.

### `INVESTIGATE`

There is a credible smell, but runtime/dynamic/history evidence is insufficient for another classification. Investigation is the correct default for framework registration, dynamic engine selection, historical data/workflows, or provider-owned behavior.

## Evidence standard

A finding should name evidence appropriate to its type:

- imports/references and known framework entry points;
- runtime registration and deployment configuration;
- API/OpenAPI callers;
- DB migration/policy + live/integration contract;
- engine/capability/evaluation provenance;
- CI trigger/protected-check behavior;
- telemetry consumer/operational question;
- visual/browser evidence for styling changes;
- durable replacement/supersession links for docs/results.

Do not use file size, cyclomatic complexity, "looks old", or an LLM judgment as sufficient evidence.

## Workflow

```text
inventory pass
  → candidate finding
  → classify with evidence
  → point at canonical owner/replacement
  → execute bounded subsystem PR
  → verify required evidence
  → update/remove finding when resolved
  → later enable static ratchet that prevents recurrence
```

The census is therefore transitional: success means many findings disappear because the repository becomes simpler, while permanent invariants migrate into normal type/schema/import/dependency/CI checks (#639).

## Ownership routing

Do not duplicate focused issues. Current major owners include:

- backend/frontend architecture seams → #417;
- dependency grouping → #287;
- CSS cascade → #523;
- historical eval workflows → #557;
- representation authority → #613;
- public/internal workflow dispatch → #632;
- evaluation evidence architecture → #636;
- observability → #637;
- static-analysis ratchets → #639.

The census can discover work; the focused issue owns its implementation.
