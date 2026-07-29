# Agent SOT — hello-ai·music-studio

This file is the Source of Truth for AI coding agents working on this
project. Read it before making any changes.

## Overview

This project is a Music AI Studio — upload/record audio, transcribe to MIDI,
analyze key/tempo/chords, and manage a library of transcriptions.

| Concern | Location |
|---------|----------|
| Page shell | `components/Studio.tsx` (tabbed shell) |
| Workspace shell | `components/workspace/WorkspaceShell.tsx` |
| Transport | `components/workspace/Transport.tsx` |
| Timeline | `components/workspace/Timeline.tsx` |
| Inspector | `components/workspace/Inspector.tsx` |
| Transcribe | `components/transcribe/index.tsx`, `components/PianoRoll.tsx` |
| Library | `components/library/index.tsx`, `components/Visualizer.tsx` |
| Analyze | `components/analyze/index.tsx` |
| Domain contracts (Python) | `backend/domain/models.py` |
| Domain types (TypeScript) | `lib/domain.types.ts` |
| Backend | `backend/main.py` (FastAPI) |

## Before acting

1. Read `docs/PRODUCT_VISION.md` — understand the north star.
2. Read `docs/ROADMAP.md` — understand current phase.
3. Read `docs/ORCHESTRATION.md` — understand the architectural roadmap and
   domain model migration status.
4. Read `docs/ARCHITECTURE.md` — understand the stack and file layout.
5. Check `docs/CHANGELOG.md` — know what changed recently.
6. Run `npm run dev` to verify the app starts.
7. Run `npx playwright test` to verify all tests pass.

## How to propose changes

1. **Audit first** — read the relevant code, run the app, identify issues.
2. **Present options** — structure proposals as options the user can
   accept/decline. Use numbered lists.
3. **Implement after approval** — once the user picks, implement with
   tests and documentation.
4. **Verify** — `npm run typecheck`, `npx playwright test`, `npm run build`
   must all pass before considering done.

## Code conventions

- **Components** — one component per file in `components/<feature>/index.tsx`.
  No barrel exports. Use `"use client"` only when needed.
- **CSS** — all styles in `app/globals.css`. Use design tokens from
  `design/tokens.json` as CSS variables (`--bg`, `--panel`, `--accent`,
  `--fs-sm`, `--s-*`, `--r-*`, `--fw-*`, `--dur`, `--ease`, `--shadow-*`, `--ring`).
  Never hardcode colors, font sizes, or spacing. If you need a color that
  does not exist as a token, add it to `app/globals.css` — do NOT inline a hex.
- **API routes** — one file per route in `app/api/<feature>/route.ts`.
  Use `proxyToBackend` for backend calls, return JSON.
- **Backend** — FastAPI in `backend/`. One file per domain. No dead imports.
- **Tests** — E2E in `tests/e2e/`, visual in `tests/visual/`. Mock external
  APIs. Keep tests deterministic — no network calls to real backends.
- **No comments in code** — self-documenting code. Use docs/ for explanations.

## Backend security checklist (mandatory)

Every new or modified backend endpoint MUST satisfy all of the following.
CI enforces parts of this via `backend/tests/test_security.py`, but reviewers
and agents must check manually too:

1. **Upload size** — any base64 audio decoded from request body MUST be checked
   against `MAX_UPLOAD_BYTES` (25 MB) before further processing. Return `413`.
2. **Storage path validation** — any caller-supplied storage key (`library_path`,
   `dataset_path`, `adapter_path`) MUST pass through `_valid_library_key()` (or a
   regex limiting to the bucket prefix + UUID). Never do `key = path.replace("library/", "")`
   directly — that allows `../` traversal.
3. **Format sanitization** — any user `fmt`/extension used to build a filename or
   content-type MUST pass through `_sanitize_fmt()`. Never interpolate raw `fmt`
   into a path (`f"input.{req.fmt}"` is a write-traversal risk).
4. **Subprocess timeouts** — every `subprocess.run` (ffmpeg, etc.) MUST set
   `timeout=` so a hung binary cannot hang the worker.
5. **No error leakage** — 5xx `detail` messages MUST NOT include raw exception
   text (`detail=f"x failed: {e}"`). Log server-side with `logger.exception`,
   return a generic message to the client.
6. **Timestamps** — job timestamps MUST use real UTC ISO via `_now()`. Never store
   the string `"now()"` — it is not evaluated by the client SDK and persists literally.
7. **Auth** — every state-changing route MUST depend on `verify_token`. Do not
   weaken auth without explicit product sign-off.

## Parallel agent workflow

Multiple AI agents work on this repo concurrently. To avoid the branch flips and
cross-PR conflicts seen historically:

- **One feature = one branch**, named `feat/<slug>` or `fix/<slug>`, based on
  current `origin/main`. Never commit to `main` or to another agent's branch.
- **Rebase, do not merge**, onto `origin/main` before opening/updating a PR:
  `git fetch origin && git rebase origin/main`. Resolve conflicts in your branch only.
- **Assume sibling PRs will land** — if another PR adds an endpoint you also touch,
  do not copy its code into your branch. Rebase onto the merged `main` and build on it.
- **No cross-contamination** — never `git checkout` a teammate's branch and leave
  uncommitted edits; stash or commit before switching.
- **Self-enforcing changes** — when you fix a class of bug, add a regression test
  (e.g. under `backend/tests/` or `tests/`) so future agents cannot reintroduce it.

## Testing before committing

Frontend (always run in order):
```
npm run typecheck
npx playwright test --reporter=line
npm run build
```

Backend (run before any backend change):
```
cd backend
python -m ruff check . && python -m ruff format --check .
python -m pytest tests/ -q
```

If build or any check fails, fix the issue before committing.

## CI gates (what blocks a merge)

These run on every PR to `main` and must be green:

- `build.yml` — `npm run build` + `npm test` (component tests). **Blocking.**
- `ci.yml` — `npm run lint`, `npm run typecheck`, `ruff`, `ruff format --check`,
  and `pytest backend/tests/` (units + **security** + **contract**).
  **Blocking.**
- `e2e.yml` — Playwright against a real Next.js build. **Blocking** (was
  `continue-on-error` historically; do not relax this).
- `gitleaks.yml` — secret scan. **Blocking.**
- `codeql.yml` — SAST (js + python). **Blocking.**
- `dependency-review.yml` — dependency CVE review. **Blocking.**

### Self-enforcing checks you should rely on
- `backend/tests/test_security.py` — asserts upload-size, path-traversal,
  fmt-sanitization, and error-leak invariants. Add a case here whenever you
  touch a storage endpoint.
- `backend/tests/test_contract.py` — asserts every `app/api/*` proxy target has
  a matching FastAPI route. Catches frontend↔backend drift.

## Local pre-commit + commit convention

Install the pre-commit framework once to block bad commits before CI:
```
pip install pre-commit && pre-commit install
```
It runs ruff, ruff-format, the security + contract pytest, and trailing-whitespace
/ large-file checks on every commit.

Commits follow **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`,
`style:`, `refactor:`, `test:`, `perf:`, `build:`, `ci:`). Opt in with:
```
git config core.hooksPath .githooks
```
This enforces the convention via `commitlint` (the `commit` script still uses
`aicommits` for message drafting).

## Supabase credentials (stored securely, not in repo)

- **URL**: `https://cijhpddqvvzyzfzmkdnn.supabase.co`
- **Project ref**: `cijhpddqvvzyzfzmkdnn`
- **Service role key**: stored in GitHub secret `SUPABASE_SERVICE_ROLE_KEY` and VM env `SUPABASE_SERVICE_ROLE_KEY`
- **Anon key**: stored in GitHub secret `NEXT_PUBLIC_SUPABASE_ANON_KEY` and `.env.local`
- **DB password**: use env var or `~/.supabase/` config — not stored in repo
- **PAT** (Supabase CLI auth): saved to `~/.supabase/access-token` via `supabase login` — persists permanently
- **Supabase CLI**: project is linked. Run `supabase db query --linked -f <file.sql>` to apply migrations.
- **Note**: DB only accessible via IPv6. VM (129.146.52.142) has no IPv6 route. Use Supabase CLI `--linked` flag (management API) or Dashboard SQL editor for migrations.

## What to do when stuck

- Read the docs/ directory for context
- Search the codebase with grep for similar patterns
- Ask the user for clarification with specific options

## Delegation patterns

- **Code exploration** — use `explore` agent with thoroughness "medium"
- **Implementation** — use `general` agent with clear task description
- **Testing** — write the test first, then ask `general` to run it
- **Documentation** — read existing docs, then write/update

## Local dev environment (Docker)

The repo ships prebuilt images; the coding agent may run **natively** or inside
the `music-ai-opencode` container — both are valid. Notes:

- `hello-ai-backend` image already contains `ffmpeg` + `torch` + `librosa` +
  `basic-pitch`. To run the real backend locally: `docker compose up backend`
  (serves FastAPI on :8000).
- `hello-ai-frontend` image runs `npm run dev` on :3000.
- CI does **not** use these images; it installs deps fresh on `ubuntu-latest`.
  That is intentional (reproducible, no image rebuild needed per PR).
- The `music-ai-opencode` container bind-mounts the repo at `/workspace`; edits
  made there and edits made natively land in the same working tree, so keep git
  state clean (commit/stash before switching branches) to avoid cross-contamination.
