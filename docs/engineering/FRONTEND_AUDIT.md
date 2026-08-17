# Frontend Audit — Findings & Fix (Task 2)

> **Audit date:** 2026-08-17 · **Target:** `app/page.tsx`, `components/workspace/`, `lib/stores/`, `app/api/v1/`
> **Method:** Live browser audit against the production Supabase backend + local frontend/worker, using accessibility snapshots, DOM measurements, console/network logs, and a real processed work (`real-piano`, version `efd96ecb-f6ce-4d50-a3bd-cc5b8980519e`).

---

## 1. Critical: infinite render loop (P0)

### Symptom
`Maximum update depth exceeded` fired continuously:

| State | Before fix | After fix |
|---|---|---|
| Authenticated empty workspace (0 pieces) | ~106 errors/sec forever (532 lines/5s; 3245+ entries) | **0 errors**; log delta 0 lines/5s |
| Fresh work load (while representations empty) | 454 errors over ~4.7s per load | **0 errors** |

### Root cause
`components/workspace/RepresentationStack.tsx:13` — `availableRepresentations(availability)` returns a **fresh array on every call**. The effect at `:18-21` used it as a dependency, so it re-ran on every render. When `available` was empty (empty library or during load), it called `setActiveRepresentation(null)`; `lib/stores/workspace.tsx:299-304` had **no equality guard**, so it always produced a new state object → re-render → new array → loop.

### Fix (merged in PR #233)
1. `lib/stores/workspace.tsx`: equality guard in `setActiveRepresentation` (mirrors `setActiveWorkId`).
2. `components/workspace/RepresentationStack.tsx`: `useMemo` for `availability`/`available`.

Verified in browser: both worst cases 0 errors; Listen/Piano roll/Score switching unaffected. `tsc --noEmit` passes.

---

## 2. Findings by severity

### P1 — Score layout at ≤1024px: OSMD zero-width warnings
- At 1024px, no horizontal overflow, but the piano-roll canvas is squeezed to 358px and OSMD logs `SkyBottomLineCalculator: width not > 0 in measure 1..27`.
- At 768px, the layout stacks (library full-width 762px, canvas below 730px, page scrolls at 1422px) — no horizontal overflow, but the score's auto-resize (`components/SheetMusic.tsx` `autoResize: true`) cannot derive a width during that pass.
- **Impact:** cosmetic/edge; score still renders after a resize event.

### P1/P2 — Measured insights hidden by the confidence gate
- DB has real insights for the audited version: `key` (conf 0.854), `tempo: 75.0 BPM` (conf `None`), `melody` (conf `None`), `rhythm` (conf `None`).
- Inspector shows only `Key: C major`. Tempo reads **"Not confidently detected"** and "Whole-piece findings" is empty because the `confident()` filter requires `confidence >= 0.5` — but tempo/melody/rhythm have `confidence=None`.
- **Assessment:** honest (never fabricates), but it hides *measured* values that have no calibrated confidence. A BPM actually derived from the pulse evidence is reported to the user as "not confidently detected."

### P2 — Ask provider not configured in this environment
- Ask panel returned: "Ask is not available right now. Please try again." Backend 503 `ask_provider_unconfigured`.
- Cause: local backend `.env` lacks `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` (`backend/ask/config.py`). Graceful degradation is correct; not a code bug.

### P3 — Minor
- `Cannot close a closed AudioContext.` logged on transport/tab switches (audio cleanup ordering).
- Next.js dev issues badge showed "2 Issues" (route-static dev warnings, nothing substantive).

---

## 3. What works well

- **Transport:** Playback position advances (19.06s on "Original"); source switching Original / Transcription / Score rendition works.
- **Compare:** A: Original vs B: Transcription with active-side toggle and clean exit.
- **Piano roll:** 234 notes over 54.1s with velocity tooltips.
- **Score:** 27 measures of notation render.
- **Selection:** Piano-roll drag creates `Selection 0:43–1:03`; the Inspector correctly switches scope and shows "No specific analysis is available for this selection yet."; selection persists across views (Score view also shows the selection).
- **Landing (signed out):** 0 console errors.
- **Empty state:** "Start with a recording… Import audio" — clean.

---

## 4. Recommended next steps (not blockers)

1. Score resize: re-render/measure after layout (or give the container a stable width at ≤1024px) to clear OSMD warnings. *Verification:* no OSMD zero-width warnings at 1024px/768px.
2. Consider displaying measured-but-uncalibrated insights with explicit low-confidence labeling instead of "Not confidently detected" (product decision). *Verification:* tempo shows "75 BPM (uncalibrated)" rather than "Not confidently detected."
3. Wire real LLM env vars for Ask locally to validate the real-music Ask path (per the earlier real-music-evaluation plan). *Verification:* Ask returns a real answer from the local backend.
4. **Solo-piano transcription toggle** (added, merged in PR #235): the import surface now has a compact `[Auto] [Solo piano]` control. *Verification:* real-stack upload with Solo piano routes to Transkun (provenance `engine: transkun`, 102 notes) and opens Piano Roll/Score; Auto remains Basic Pitch (234 notes).