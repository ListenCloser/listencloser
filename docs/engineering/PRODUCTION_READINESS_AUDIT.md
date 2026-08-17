# Production Readiness Audit

> **Audit date:** 2026-08-17 · **Branch audited:** `main` (d04a776 → 33784d3, all fixes merged: #234, #233, #232, #235, #236)
> **Environment:** production Supabase (`cijhpddqvvzyzfzmkdnn`), Oracle VM backend/worker via `scripts/deploy.sh`, Vercel frontend. Docker unavailable locally, so the deployed pipeline was validated against the production DB/storage with a local backend + worker + frontend.

---

## 1. Blocking findings

### P0-A — Every transcription job fails in production (`TypeError`)
`backend/domain/capabilities.py:490-494` (`handle_transcribe`):

```python
engine = music_features.get_transcription_engine_for_job(
    engine_name, onset_threshold, frame_threshold, profile=profile
)
```

The callee signature is `get_transcription_engine_for_job(name, profile, onset_threshold, frame_threshold)`. Passing `engine_name, onset_threshold, frame_threshold` positionally binds `name=engine_name`, `profile=onset_threshold`, `onset_threshold=frame_threshold`, then the keyword `profile=profile` collides:

```
TypeError: get_transcription_engine_for_job() got multiple values for argument 'profile'
```

This means **the `transcribe` capability raises before any audio is processed** in production. The bug was introduced in PR #229 (`9e52c8c`) and is present on `main`. Locally it is masked because the audited works predate the merge and the pipeline smoke tests bypass the durable handler.

**Fix:** call with explicit keywords `name=engine_name, profile=profile, onset_threshold=onset_threshold, frame_threshold=frame_threshold`. **Fixed and merged in PR #234**, with regression test `TestHandleTranscribeCallSite` that reproduced the exact production `TypeError` on the old code and passes with the fix.

### P0-B — Frontend infinite render loop (now fixed in PR #233)
Continuous `Maximum update depth exceeded` on the empty authenticated workspace (~106 errors/sec) and during every work load (~454 errors). Root cause: `RepresentationStack.tsx` produced a fresh dependency array each render and `setActiveRepresentation(null)` produced new state unconditionally. **Fixed and merged in PR #233** (0 errors in both worst-case states).

### P1 — Solo-piano transcription is unreachable from normal UX (new)
The routing contract supports `transcription_profile="solo_piano"` → Transkun (the piano-specialist engine), but **no frontend/API path sets it** (`backend/CURRENT_USER_BEHAVIOR.md`). Every upload defaults to `auto`/Basic Pitch, so the piano improvement from PR #229 is effectively unused. **Fixed and merged in PR #235** (`feat/solo-piano-profile-ux`): a compact `[Auto] [Solo piano]` toggle, verified end-to-end in production — job carries `transcription_profile: solo_piano`, routes to Transkun, provenance confirms `engine: transkun`, 102 notes, Piano Roll/Score open. Auto path unchanged (basic_pitch, 234 notes). The idempotency identity now includes the profile so re-requesting the same version with a different profile creates a distinct job.

---

## 2. Test-suite health (CI is red; the deploy-time gate is bypassed)

On clean `main`, **13–16 tests fail** in the CI/canonical environment. The intended deploy-time gate in `scripts/deploy.sh:94-98` is:

```bash
if python3 -m pytest --version >/dev/null 2>&1; then
  python3 -m pytest tests/ -x -q || { echo "pytest failed — aborting"; exit 1; }
else
  echo "pytest not installed — skipping (tests ran in CI)"
fi
```

**On the deployment host, pytest is not installed, so the gate prints `pytest not installed — skipping (tests ran in CI)` and is effectively bypassed** (verified in the deploy logs). It does **not** currently abort deploys, and it provides no test protection on the host. The gate's "tests ran in CI" message is misleading because CI is red.

| Failure | Root cause | Classification |
|---|---|---|
| `test_notation/test_quantize.py` (4) | test/code naming drift from #197: code returns `preserved_no_meter`, tests assert `preserved_no_grid` | genuine drift |
| `test_cleanup.py`, `test_transcription_cleanup.py` (3) | assertion drift on merge/number counts (0 vs 1, 0.0295 vs 0.03, 0.5 vs 0.69) | drift, needs re-baselining |
| `test_benchmarks.py` (4) | pass in isolation, fail in full-suite (`basic_pitch.predict` returns 0 values under suite load) | test isolation / resource |
| `test_engines/test_bakeoff_fixes.py`, `test_real_pipeline_contracts.py` (2) | m4a decode + mock contract assertion | env/mock |
| `test_beat_this*`, `test_transcription_evidence*` (main-only files) | optional engine not installed + note-amplitude migration assertion | env |

All of these are **pre-existing on `main`** (verified via a clean main worktree) and are not introduced by the merged PRs. **Direction (not a weakening):** make required CI genuinely green (re-baseline the drift + fix benchmark isolation), deploy the **exact tested commit/artifact**, and rely on the existing small deployment smoke/readiness gate (health + queue-heartbeat). The deploy-time full-suite `pytest -x` gate should either be removed (it is dead on the host) or replaced by a reliable check that runs in the built image where pytest exists — not left as a misleading no-op.

---

## 3. Configuration gaps

### Ask (LLM) is not wired into the deployment
- `docker-compose.yml` passes only Supabase/Sentry/env vars to `backend` and `worker`; **no `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`**.
- `deploy-backend.yml` and `scripts/deploy.sh` do not forward LLM env vars.
- Result: in production the Ask capability returns `503 ask_provider_unconfigured` (verified locally with an unconfigured backend). The FE degrades gracefully ("Ask is not available right now"). This is a **feature unavailability**, not a crash — but any Ask launch requires adding these vars to the deploy pipeline and docker-compose.

### Local dev env gap
Backend entrypoints do not load `.env`; the `.env` (with Supabase keys and LLM vars) must be sourced manually before running `uvicorn`/`worker.py`. Docker uses compose env instead, so production is unaffected. For local Ask testing this requires the LLM vars to be present.

---

## 3b. Harmony baseline (evaluation finding, PR #236)

The production music21 symbolic harmony path has **no scorable chord baseline**: the adapter filters chords on `Chord.impliedQuality`, which is absent on MIDI-derived chords, so it emits **0 chords** on GuitarSet. Key accuracy is **0.8** (4/5) once music21's `E-`/`A-` spelling is normalized to `Eb`/`Ab`; one genuine key miss (SS3_solo: G minor vs Bb major). A diagnostic extraction using `Chord.quality` produces 21–156 chords/clip — the library can extract them; the adapter's quality source is the blocker.

**Severity:** P2 (harmony is a secondary analysis; no production crash). **Evidence:** `evaluation/reports/harmony_feasibility.md` + `evaluation/harmony_feasibility.py` (**merged in PR #236**, which also fixed the evaluation semantics: zero-prediction chord baseline scores 0/0/0, and music21 symbolic offsets are converted to seconds before scoring). **User consequence:** harmonic analysis currently surfaces no chords on real audio-derived works. **Recommended fix:** a small production PR changing the adapter's chord-quality source (e.g. `Chord.quality` with root-aware fallback). **Verification:** re-run `evaluation/harmony_feasibility.py` → non-zero chord F1; production Harmony view shows chords. Out of scope for the audit itself (no candidate integrated).

---

## 4. What is solid

- **Deploy pipeline** (`scripts/deploy.sh`): build-first, health-gated, rollback-on-failure; keeps the previous release online while building; removes stale worker heartbeat before switching; waits for live worker queue health.
- **Database migrations**: `deploy-backend.yml` links the project, repairs two known revert states, and runs `db push --include-all` before the app switch.
- **Durable worker**: lease/cancel/retry/heartbeat coverage; concurrency configurable (`WORKER_CONCURRENCY`).
- **Security posture**: Gitleaks + CodeQL + dependency-review + semgrep in CI; private storage + owner checks + short-lived signed URLs; owner-scoped routes.
- **Backend canonical suite**: 462 passed in the canonical environment (the 13–16 failures above are the known env/drift set).

---

## 5. Recommended priority order (remaining work)

P0/P1 items above are now merged (#234 transcription TypeError, #233 render loop, #235 solo-piano). Remaining backlog:

1. **Re-baseline the pre-existing test failures** (quantize naming, cleanup counts, benchmark isolation) so required CI is genuinely green and the deploy-time test gate is trustworthy (per §2 direction — not a weakening). *Verification:* CI full-suite green; `deploy.sh` gate, if retained, runs in the built image where pytest exists.
2. **Wire LLM env vars** through `docker-compose.yml` + `deploy-backend.yml` when Ask is ready to launch. *Verification:* Ask returns a real answer (not `503 ask_provider_unconfigured`) from the deployed backend.
3. **Harmony adapter chord-quality fix** (P2, from #236): change the music21 adapter's chord-quality source (e.g. `Chord.quality`) so the symbolic harmony path emits chords and is scorable. *Verification:* `evaluation/harmony_feasibility.py` → non-zero chord F1.
4. FRONTEND_AUDIT.md follow-ups (score resize at ≤1024px, measured-insight confidence labeling).

---

## 6. Files referenced

| File | Role |
|---|---|
| `backend/domain/capabilities.py:490` | P0-A transcription call site |
| `backend/music_features.py:676` | `get_transcription_engine_for_job` signature |
| `components/workspace/RepresentationStack.tsx`, `lib/stores/workspace.tsx` | P0-B loop (fixed in #233) |
| `scripts/deploy.sh` | deploy gate + container switch |
| `backend/docker-compose.yml` | env passed to backend/worker |
| `.github/workflows/deploy-backend.yml` | migration + SSH deploy |
| `backend/notation/quantize.py:31-34` | `preserved_no_*` naming drift |
| `backend/ask/config.py` | LLM env read (`LLM_BASE_URL` etc.) |