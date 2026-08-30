# Transcription routing note

> **Status:** compatibility/orientation note, not a source of truth. Exact routing lives in `backend/engines/registry.py` and the capability/job code that supplies transcription parameters.

## Durable routing invariant

Transcription is routed through an engine adapter/profile contract rather than by silently guessing instrumentation in the browser.

At the time this compatibility path was introduced:

- an explicit `solo_piano` profile selected the piano-specialist Transkun adapter;
- ordinary/general/unspecified transcription used the default general transcription path;
- there was no automatic piano/genre classifier deciding that profile for the user;
- provenance recorded the chosen engine/profile/routing reason so downstream artifacts could be audited.

Those principles remain useful, but **do not use this file to infer the current default engine, supported profiles, environment overrides, or product UI**. Inspect the engine registry, current capability implementation, tests, and capability metadata instead.

If routing semantics intentionally change, update the canonical code/tests/provenance contract. Delete this note once no compatibility/history value remains.
