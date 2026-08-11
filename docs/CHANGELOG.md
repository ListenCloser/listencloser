# Changelog

## 2026-08-11 — Product-quality audio understanding release candidate

- Prevented cross-work stale media and isolated optional artifact load failures.
- Distinguished durable-job observation loss from terminal failure and added
  reconnect/resume plus saved-source recovery.
- Preserved playback position/state while switching original and transcription.
- Reworked insights into grouped, confidence-aware, evidence-seeking controls;
  removed misleading representation actions and clarified deterministic shortcuts.
- Added responsive panel defaults, semantic disclosures/tabs, live notices, and
  accessible playback/import controls.
- Added upload compensation, understand-request idempotency, capability-aware
  readiness, worker Sentry initialization, and production SoundFont provisioning.
- Added clean Supabase migration integration CI and full schema/lifecycle checks.
- Made deployment exact-SHA and rollback health/SHA-gated.
- Recorded the free three-plane infrastructure decision in ADR-009.
