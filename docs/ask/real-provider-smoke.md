# Real Ask Provider Smoke Test Report

**Date:** 2026-08-14  
**PR:** #228 (`feat: add grounded contextual ask backend`)  
**Branch:** `feat/grounded-ask-backend`  
**Commit:** `4bbabc9`

---

## Configuration

| Setting | Value |
|---------|-------|
| Provider | OpenRouter (`https://openrouter.ai/api/v1`) |
| Model | `openrouter/free` (router to available free models) |
| API Key | `<REDACTED>` |
| Timeout | 60s |
| Rate Limit | 10/minute |

**Free models available on this key:** 18 models (NVIDIA Nemotron, Google Gemma, LiquidAI LFM, Poolside Laguna, Cohere North, OpenAI gpt-oss-20b). Direct model calls hit 429/403; `openrouter/free` router works.

---

## Infrastructure Status

| Component | Status |
|-----------|--------|
| Supabase (local) | ✅ Running on `http://127.0.0.1:54321` |
| FastAPI Backend | ✅ Running on `http://127.0.0.1:8000` |
| Next.js Frontend | ✅ Running on `http://127.0.0.1:3000` |
| Ask Endpoint (`POST /api/v1/ask`) | ✅ Registered, auth + ownership working |

---

## Test 1: No Selection — Whole-Work Question

**Question:** "What key is this piece in?"

**AskContext (redacted):**
```json
{
  "question": "What key is this piece in?",
  "context": {
    "workId": "141977fe-ce13-4d9d-851b-d847977466c8",
    "representationId": "score",
    "currentTime": 2.0,
    "playbackSourceId": "source-1",
    "selection": null,
    "visibleInsights": [{
      "insight": {
        "id": "insight-key",
        "version_id": "version-1",
        "kind": "key",
        "claim": "Key: C major",
        "span": { "start_seconds": 0.0, "end_seconds": 4.0 },
        "entity_ids": []
      },
      "category": "whole-work"
    }]
  }
}
```

**Raw Provider Output (200 OK):**
```json
{
  "answer": "The piece is in C major, as indicated by the whole-work insight.",
  "references": [{"type": "insight", "id": "insight-key"}],
  "suggestedActions": [{"type": "show_representation", "representationId": "score"}]
}
```

**Sanitized AskResponse:** ✅ Identical (all references grounded)

**Latency:** ~5s total (auth 1s + provider 4s)

---

## Test 2: With Selection — Passage Question

**Question:** "What is happening in this selected passage?"

**AskContext (redacted):**
```json
{
  "question": "What is happening in this selected passage?",
  "context": {
    "workId": "141977fe-ce13-4d9d-851b-d847977466c8",
    "representationId": "score",
    "currentTime": 2.0,
    "playbackSourceId": "source-1",
    "selection": {
      "timeRange": {"start": 1.0, "end": 3.0, "domain": "performance"},
      "noteIds": ["note-1", "note-2"],
      "provenance": {"origin": "piano_roll", "timeExact": true, "measureApproximate": false}
    },
    "visibleInsights": [
      {
        "insight": {
          "id": "insight-selection",
          "version_id": "version-1",
          "kind": "chord",
          "claim": "Chord: G7",
          "span": {"start_seconds": 1.5, "end_seconds": 2.5},
          "entity_ids": []
        },
        "category": "selection"
      },
      {
        "insight": {
          "id": "insight-key",
          "version_id": "version-1",
          "kind": "key",
          "claim": "Key: C major",
          "span": {"start_seconds": 0.0, "end_seconds": 4.0},
          "entity_ids": []
        },
        "category": "whole-work"
      }
    ]
  }
}
```

**Raw Provider Output (200 OK):**
```json
{
  "answer": "The selected passage (notes note-1 and note-2, from 1.0 to 3.0 seconds) contains a G7 chord, as indicated by the selection-specific insight. This chord occurs within the overall key of C major, which spans the entire work from 0.0 to 4.0 seconds.",
  "references": [
    {"type": "insight", "id": "insight-selection"},
    {"type": "insight", "id": "insight-key"},
    {"type": "notes", "ids": ["note-1", "note-2"]},
    {"type": "time", "start": 1.0, "end": 3.0, "domain": "performance"}
  ],
  "suggestedActions": [
    {"type": "seek", "seconds": 1.0, "domain": "performance"},
    {"type": "loop", "start": 1.0, "end": 3.0, "domain": "performance"},
    {"type": "show_representation", "representationId": "score"}
  ]
}
```

**Sanitized AskResponse:** ✅ Identical (all references/actions grounded in evidence)

**Latency:** ~16s total (larger prompt)

---

## Grounding Audit

| Test | Claim | Evidence Source | Classification |
|------|-------|----------------|----------------|
| Test 1 | "The piece is in C major" | `insight-key` (whole-work) | ✅ SUPPORTED_BY_WHOLE_WORK_EVIDENCE |
| Test 2 | "selected passage contains a G7 chord" | `insight-selection` (selection) | ✅ SUPPORTED_BY_SELECTION_EVIDENCE |
| Test 2 | "chord occurs within the overall key of C major" | `insight-key` (whole-work) | ✅ SUPPORTED_BY_WHOLE_WORK_EVIDENCE |
| Test 2 | "from 1.0 to 3.0 seconds" | `selection.timeRange` | ✅ SUPPORTED_BY_SELECTION_EVIDENCE |
| Test 2 | "notes note-1 and note-2" | `selection.noteIds` | ✅ SUPPORTED_BY_SELECTION_EVIDENCE |

**UNSUPPORTED factual claims:** 0

---

## References/Actions Validation

### Test 1 (No Selection)

| Item | Type | Grounding | Retained |
|------|------|-----------|----------|
| `insight-key` | insight ref | exists in visibleInsights | ✅ |
| `show_representation(score)` | action | canonical representation | ✅ |

**Emitted:** 2 | **Retained:** 2 | **Dropped:** 0

### Test 2 (With Selection)

| Item | Type | Grounding | Retained |
|------|------|-----------|----------|
| `insight-selection` | insight ref | exists in visibleInsights (category=selection) | ✅ |
| `insight-key` | insight ref | exists in visibleInsights (category=whole-work) | ✅ |
| `note-1`, `note-2` | notes ref | both in selection.noteIds | ✅ |
| time 1.0–3.0 perf | time ref | within selection.timeRange | ✅ |
| seek 1.0 perf | action | within selection.timeRange | ✅ |
| loop 1.0–3.0 perf | action | within selection.timeRange | ✅ |
| show_representation(score) | action | canonical representation | ✅ |

**Emitted:** 7 | **Retained:** 7 | **Dropped:** 0

---

## Failure Behavior Verification

| Scenario | Expected | Actual |
|----------|----------|--------|
| Missing API key (`LLM_API_KEY` unset) | 503 "Ask is not configured" | ✅ Unit test passes |
| Invalid provider response (4xx/5xx) | Safe UI error (502) | ✅ 429/403/404 → 502 "Ask provider unavailable" |
| Provider timeout | Safe UI error (504) | ✅ Unit test passes |
| Malformed model output | 502 "Ask returned an invalid response" | ✅ Tested: model returned non-JSON → 502 |
| Rest of workspace unaffected | Other endpoints work | ✅ `/health`, `/api/v1/projects`, etc. functional |

---

## Issues Found

1. **Free tier rate limits** — Direct model calls hit 429/403; `openrouter/free` router works but has variable latency (5–16s). Production should use a paid tier with dedicated capacity.

2. **No real musical evidence** — Test work has synthetic insights (no real analysis pipeline run). Real grounding validation requires a work processed through the full pipeline (transcribe → chord detection → key detection → insights).

3. **Model output quality varies** — Free models occasionally return malformed JSON (caught by sanitization → 502). Paid models with structured output support would be more reliable.

---

## Recommendation

**GO for initial use with caveats:**

| Aspect | Status |
|--------|--------|
| Architecture | ✅ Solid — auth, ownership, grounding, sanitization all verified |
| Unit tests | ✅ 80 tests pass |
| Real provider integration | ✅ Works with `openrouter/free` router |
| Grounding enforcement | ✅ Strict — unsupported claims dropped |
| Error handling | ✅ Safe failures (502/503/504) |

**Required for production:**
1. Valid OpenRouter key with paid credits (or self-hosted model) for reliable latency
2. Run real analysis pipeline on audio to generate actual insights
3. Consider adding request/response logging for production monitoring

---

## Appendix: Running the Smoke Test

```bash
# 1. Set environment
export LLM_BASE_URL=https://openrouter.ai/api/v1
export LLM_API_KEY=<your-working-openrouter-key>
export LLM_MODEL=openrouter/free
export ASK_LLM_TIMEOUT_SECONDS=60

# 2. Start backend
cd backend
set -a; source ../.env.local; set +a
uvicorn main:app --host 127.0.0.1 --port 8000

# 3. Run Ask smoke test (requires valid key)
ASK_REAL_PROVIDER=1 python -m pytest backend/tests/test_ask_smoke.py -v -s
```
