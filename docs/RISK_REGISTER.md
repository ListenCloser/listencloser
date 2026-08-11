# Risk Register

Generated from bundle `05_EXECUTION/05_RISK_REGISTER.md` — adapted to repository reality.

| ID | Risk | Consequence | Likelihood | Impact | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|---|
| R01 | Big-bang rewrite | Product stops working | Medium | Critical | Compatibility layers, vertical slices, preserve existing behavior until verified | Orchestrator | Mitigated |
| R02 | Poor transcription quality | Unusable score and analysis | High | High | Fixture benchmarks (manifest.json), correction UX, replaceable Basic Pitch adapter | Backend agent | Active |
| R03 | Timeline drift | Misleading comparisons | Medium | High | Explicit alignment artifacts with confidence metadata | Frontend agent | Future |
| R04 | Public or weak storage access | User data exposure | Medium | Critical | Private buckets, signed URLs, RLS tests (20260720_rls_hardening.sql) | Domain/Data agent | Partially mitigated |
| R05 | Agent contract drift | Incompatible parallel work | High | High | Single contract owner, contract tests (test_contract.py), ADR gate | Orchestrator | Mitigated |
| R06 | UI improvisation | Incoherent product | High | Medium | Design SOT as guardrail, UX agent review per change | Design/UX agent | Mitigated |
| R07 | Endless dual architecture | Permanent complexity | Medium | High | Removal condition for every compatibility adapter, migration phases | Domain/Data agent | Future |
| R08 | OSS abandonment/license issue | Blocked deployment | Low | High | Capability evaluations, fallback adapters, no hard coupling | Research agent | Future |
| R09 | Request-bound ML | Timeouts and data loss | Low | Medium | Durable jobs, separate workers, leases, cancel/retry, and worker health | Backend agent | Mitigated |
| R10 | Analysis hallucination | User distrust | Medium | Medium | Structured evidence and provenance on every insight | Backend agent | Future |
| R11 | Current `LibFile` model migration | Data corruption during migration | High | Critical | Dual-read/write strategy, backfill validation, rollback SQL | Domain/Data agent | Future |
| R12 | Host proxy 1MB body limit | Large uploads fail with 413 | High (current) | Medium | In-repo Caddy config or browser signed upload to Supabase | Backend agent | Active |

## Current active risks

### R09 — Request-bound ML
**Status:** The request path only persists and queues work. A separate worker
claims jobs with renewable leases, records liveness, and prevents cancellation
from being overwritten by completion or retry. Remaining risk is capacity and
blocking model calls, not request loss.

### R12 — Host proxy body limit
**Status:** The Oracle VM's host-level reverse proxy enforces ~1MB body limit. Large audio uploads fail with HTTP 413.  
**Plan:** Short-term: browser signed-upload to Supabase, pass `library_path`. Long-term: in-repo Caddy config.

### R04 — Storage access hardening
**Status:** `20260720_rls_hardening.sql` tightened library and transcription buckets to owner-scoped. But some buckets (audio, midi, enhanced, analysis) remain publicly readable. Current app relies on `getPublicUrl()` for playback.  
**Plan:** Phase 2 introduces signed URLs for private bucket access, preserving RLS ownership.

## Risk review cadence
- Review at each phase gate
- Escalate to user for irreversible data-risk decisions only
