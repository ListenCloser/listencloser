# Backend test tiers

> **Authority:** pytest markers/default selection live in `backend/pyproject.toml`; GitHub Actions workflows define what CI actually runs. This file explains intent only and must not freeze test counts or duplicate dependency manifests.

The backend uses explicit pytest markers so deterministic unit tests stay cheap while model, database, provider, and benchmark work can opt into the environment it actually requires.

## Tiers

| Tier | Marker | Purpose | Typical command |
|---|---|---|---|
| Required unit | none | deterministic offline backend behavior | `uv run --project backend --locked python -m pytest backend/tests` |
| Real-model integration | `integration` | inference through real ML/model adapters | `uv run --project backend --locked python -m pytest backend/tests -m integration` |
| Database / real stack | `real_stack` | live Supabase/Postgres, migrations, RLS, persistence | `uv run --project backend --locked python -m pytest backend/tests -m real_stack` |
| External provider | `external_provider` | opt-in real external LLM/provider smoke | `uv run --project backend --locked python -m pytest backend/tests -m external_provider` |
| Benchmark/evaluation | `benchmark` | result-bearing evaluation outside normal unit semantics | `uv run --project backend --locked python -m pytest backend/tests -m benchmark` |

The default `addopts` in `backend/pyproject.toml` excludes `integration`, `real_stack`, `benchmark`, and `external_provider`. Therefore the first command above runs the required unit tier unless a caller explicitly overrides marker selection.

## Contracts

- Required unit tests must not silently download models or depend on external services.
- A real-model test belongs in `integration`, even if it is deterministic once the model exists.
- Database/RLS/migration behavior belongs in `real_stack` and must be exercised against a real local/test database shape rather than repository mocks.
- External-provider tests are opt-in and must name the required configuration; missing credentials are not a product-success signal.
- Benchmark tests produce evaluation evidence and should not be confused with ordinary correctness CI.
- `skip`/`xfail` must have a specific, reviewable reason. Do not hide a broken required path behind optional-dependency logic.
- A mocked unit/browser test cannot be cited as proof that a model, worker, database, or deployed service works.

## CI mapping

The exact mapping of paths/risks to workflows is owned by `.github/workflows/` and the repository merge-evidence policy. In broad terms:

- routine backend static/unit coverage runs in CI;
- database integration starts/applies the real local Supabase schema before `real_stack` tests;
- critical cross-boundary product behavior is covered by the separate real-stack E2E workflow;
- heavyweight model/evaluation protocols run only where their owning workflow/manual process explicitly requires them.

Do not copy current pass counts, deselected-test inventories, dependency filenames, or workflow internals into this document. They become stale immediately and Git/pytest already provide that information.

See root `AGENTS.md` and `docs/AGENT_EXECUTION_PLAYBOOK.md` for the repository-wide evidence ladder and definition of done.
