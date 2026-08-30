# Test Environment

How to set up, use, and tear down test environments for the listencloser feedback loop.

## Quickstart

```bash
# 1. Source the setup (exports TEST_RUN_ID, TEST_PROJECT_ID, etc.)
source <(./scripts/test-env-setup.sh)

# 2. Run tests against the seeded environment
TEST_RUN_ID=$TEST_RUN_ID npx playwright test tests/e2e/
TEST_RUN_ID=$TEST_RUN_ID python -m pytest backend/tests/ -k integration

# 3. Tear down
source <(./scripts/test-env-teardown.sh)
```

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `SUPABASE_URL` | yes | Supabase project URL (`https://<ref>.supabase.co`) |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | Service-role JWT for admin operations |
| `TEST_RUN_ID` | yes (teardown) | Namespaces all test records |
| `SUPABASE_ANON_KEY` | no | Used for token exchange (falls back to service role) |
| `TEST_USER_EMAIL` | no | Base email for test users |
| `TEST_USER_PASSWORD` | no | Password for test users (auto-generated if unset) |
| `TEST_AUDIO_DIR` | no | Path to audio fixtures (default: `tests/fixtures/audio`) |

## Environments

### Local

Use the local Supabase CLI stack or a dedicated test project:

```bash
supabase start                          # local Supabase
export SUPABASE_URL=http://localhost:54321
export SUPABASE_SERVICE_ROLE_KEY=<from supabase status>
./scripts/test-env-setup.sh
```

### CI (GitHub Actions)

Store credentials as GitHub secrets. The CI workflow should:

1. Source `test-env-setup.sh` at job start
2. Run tests with `TEST_RUN_ID` exported
3. Always run `test-env-teardown.sh` in a post-job step (even on failure)

Example workflow step:

```yaml
- name: Setup test environment
  run: source <(./scripts/test-env-setup.sh)
  env:
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
    BYPASS_PROD_GUARD: "1"

- name: Run integration tests
  run: python -m pytest backend/tests/ -k integration -v
  env:
    TEST_RUN_ID: ${{ env.TEST_RUN_ID }}
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}

- name: Teardown
  if: always()
  run: source <(./scripts/test-env-teardown.sh --full)
  env:
    TEST_RUN_ID: ${{ env.TEST_RUN_ID }}
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
```

### Preview (staging)

Use a dedicated test Supabase project. Never point these scripts at production —
the `.env.test-guard` safety check enforces this. Create the guard file:

```bash
echo "test-only" > .env.test-guard
```

## Seed / reset workflow

```
┌─────────────────┐
│  test-env-setup  │  creates users → seeds project → exports TEST_RUN_ID
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   run tests     │  uses TEST_RUN_ID to scope database queries
└────────┬────────┘
         │
         ▼
┌──────────────────┐
│ test-env-teardown │  deletes projects, works, storage objects
│   (--full)       │  also removes test users
└──────────────────┘
```

The scripts are idempotent:
- **Setup** — detects existing users by email (skips creation if present)
- **Teardown** — safe to run multiple times; finds records by project name pattern and/or `.test-run-*.json` metadata

## Python seed helpers

`backend/tests/fixtures/seed_data.py` provides functions for programmatic seeding:

```python
from supabase import create_client
from fixtures.seed_data import create_test_project, upload_test_audio, wait_for_job

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

# Create a project
proj = create_test_project(sb, owner_id="abc-123", name="Integration Test")

# Upload audio
result = upload_test_audio(sb, proj["id"], "tests/fixtures/audio/c_major.wav")

# Kick off a workflow and wait (if job worker is running)
job = wait_for_job(sb, job_id, timeout=30)
```

These use the service-role client directly — no running API server needed, no auth token exchange.

## Adding new test fixtures

1. Place audio files in `tests/fixtures/audio/`:

   | File | Duration | Purpose |
   |---|---|---|
   | `c_major.wav` | ~10s | Clean monophonic melody (PR fixtures) |
   | `simple_piano.wav` | ~5s | Minimal piano (PR fixtures) |
   | `dense_piano.wav` | ~60s | Dense piano (nightly fixtures) |

2. Register fixture metadata in `tests/fixtures/manifest.json`:

   ```json
   {
     "c_major.wav": {
       "source": "synthetic",
       "license": "CC0",
       "checksum": "sha256:...",
       "duration_s": 10.2,
       "characteristics": ["monophonic", "major_scale", "steady_tempo"],
       "expected_capabilities": ["transcribe", "analyze", "convert"]
     }
   }
   ```

3. Use in tests:

   ```python
   def test_transcribe_fixture(supabase_client):
       proj = create_test_project(supabase_client, "user-1")
       result = upload_test_audio(supabase_client, proj["id"], "tests/fixtures/audio/c_major.wav")
       assert result["version"]["byte_size"] > 0
   ```

4. For bash-level seeding, add audio files to `TEST_AUDIO_DIR` and the setup script will report them.

## Safety

- **Production guard** — scripts refuse to run without `.env.test-guard` or `BYPASS_PROD_GUARD=1`
- **Namespace isolation** — every record is tagged by `TEST_RUN_ID` in project names; teardown only touches matching records
- **Service-role key** — never hardcoded, read from environment only
- **No secrets in repo** — `.test-run-*.json` files are gitignored
