# Backend Test Tiers

The backend suite is split into explicit tiers so it is obvious which tests run on
every PR, which need real ML models, which need a live database, which need a real
external provider, and why anything is skipped or deselected. Tier membership is
enforced with pytest markers; the default `addopts` deselects everything outside the
required unit tier.

## Tiers

| Tier | Marker | Purpose | Command | Dependencies | Actual execution path |
|---|---|---|---|---|---|
| **UNIT_REQUIRED** | (none) | Deterministic, offline unit tests. No model downloads, no external services, no silent skips. | `pytest backend/tests/ -m "not integration and not real_stack and not benchmark and not external_provider"` | Python + `backend/requirements.txt` | Every PR (CI `ci.yml`, step "Run required Python unit tests") |
| **INTEGRATION_ML** | `integration` | Real ML model inference (Basic Pitch, Transkun, piano-transcription) against real audio. | `pytest backend/tests/ -m integration` | `basic-pitch`, `transkun`, `pytorch`, real audio fixtures (`tests/fixtures/*.m4a`) | Intentional runs only (no CI runner); not part of the required unit suite |
| **REAL_STACK** | `real_stack` | Live local/remote Supabase/Postgres: RLS policies, domain persistence, pipeline smoke. | `pytest backend/tests/ -m real_stack` | Live Supabase (`SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_ANON_KEY`) | CI `database-integration.yml` (starts local Supabase via `supabase start` + `supabase db reset`, then runs `-m real_stack` over the whole backend suite); opt-in locally |
| **EXTERNAL_PROVIDER** | `external_provider` | Real external LLM/provider smoke (opt-in). Requires `ASK_REAL_PROVIDER=1` and configured `LLM_*` env. | `pytest backend/tests/ -m external_provider` | Live LLM provider (`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`) | Intentional/local runs only; no CI job yet (no secret-backed runner). Not part of the database `real_stack` tier |
| **EVALUATION_BENCHMARK** | `benchmark` | Evaluation benchmark runs kept out of required unit semantics. | `pytest backend/tests/ -m benchmark` | Evaluation harness + models/fixtures | Intentional runs only |
| **OPTIONAL_DEPENDENCY** | (skip) | Tests that skip only when a clearly named optional dependency or external artifact is absent; the skip reason names the dependency. | Same as UNIT_REQUIRED; skips surface in the run summary | Optional external artifacts (e.g. `hello-ai-autonomous-handoff` fixture manifest) | Every PR; skipped when the optional artifact is absent |
| **LEGACY_DELETE** | n/a | Tests that no longer protect any current behavior. | n/a | n/a | Removed (none currently) |

## Marker inventory

Registered in `backend/pytest.ini`:

- `integration` — real-model inference tests. Excluded from the default unit suite.
- `real_stack` — live database/external-service tests. Excluded from the default unit suite.
- `external_provider` — real external LLM/provider smoke. Excluded from the default unit suite.
- `benchmark` — evaluation benchmark runs. Excluded from the default unit suite.

The default `addopts` is:

```
addopts = -m "not integration and not real_stack and not benchmark and not external_provider"
```

## Current deselected tests by tier

**INTEGRATION_ML** (`-m integration`):

- `backend/tests/test_benchmarks.py` — `test_transcribe_fixture_has_notes`,
  `test_transcribe_detects_pitches`, `test_transcribe_produces_midi_bytes`,
  `test_transcribe_produces_wav_bytes` (real Basic Pitch inference)
- `backend/tests/test_transcription_evidence.py` — `test_transcribe_preserves_model_note_events`
- `backend/tests/test_transcription_profile_routing.py` — `test_transcribe_with_engine_provenance_includes_profile` (real Transkun + Basic Pitch)
- `backend/tests/test_engines/test_bakeoff_fixes.py` — `test_piano_transcription_handles_m4a`,
  `test_piano_transcription_output_time_aligned`, `test_basic_pitch_handles_m4a`,
  `test_ineligible_clip_still_runs_inference`

**REAL_STACK** (`-m real_stack`, run by CI `database-integration.yml`):

- `backend/tests/integration/test_analyze_truthfulness.py` (3 tests)
- `backend/tests/integration/test_insight_confidence_roundtrip.py` (1 test)
- `backend/tests/integration/test_pipeline_smoke.py` (1 test)
- `backend/tests/test_rls_domain.py` (19 tests, skip if `SUPABASE_URL` unset)

**EXTERNAL_PROVIDER** (`-m external_provider`):

- `backend/tests/test_ask_smoke.py` (1 test, skip unless `ASK_REAL_PROVIDER=1`)

## Remaining skips in the default suite

Skips are only permitted for OPTIONAL_DEPENDENCY reasons that name the missing
artifact:

- `backend/tests/test_fixture_manifest.py` — skips when the external
  `hello-ai-autonomous-handoff` fixture manifest is absent (looked for at
  `~/Downloads/hello-ai-autonomous-handoff/09_FIXTURES/manifest.json` and
  `<repo>/fixtures/manifest.json`).
- Defensive `pytest.importorskip` guards for declared dependencies
  (`music21`, `pretty_midi`, `basic_pitch`, `librosa`). These dependencies are in
  `backend/requirements.txt`, so the guards do not fire in CI; they only prevent a
  confusing failure in a partially provisioned local environment.

There are no `skip`/`xfail` markers hiding genuine failures.

## Current verification snapshot

Default unit suite (`-m "not integration and not real_stack and not benchmark and not external_provider"`):

- 497 passed, 0 skipped, 35 deselected, 0 failed

Integration suite (`-m integration`, with `TEST_FIXTURES_DIR` pointing at `tests/fixtures`):

- 10 passed, 0 skipped, 0 failed

Real-stack suite (`-m real_stack`) against a fresh local Supabase
(`supabase start` + `supabase db reset`, then run the whole backend suite with `-m real_stack`):

- 24 passed, 0 skipped, 0 failed
- Without `SUPABASE_URL` env vars the same tests skip (they run in CI's
  `database-integration` job, which starts a local Supabase and applies every migration
  before running `-m real_stack` over the whole backend suite)

External-provider suite (`-m external_provider`) locally without `ASK_REAL_PROVIDER`:

- 1 skipped (explicitly classified as EXTERNAL_PROVIDER; not part of database CI)

Note: `backend/tests/test_engines/test_wrappers.py` scopes its `basic_pitch`/`librosa`/`soundfile`
mocks to its own module and restores the real modules afterwards. This prevents the mocks from
leaking into other test files in the same process, which previously broke the real-model
integration tests when the whole suite was run in one pytest invocation.