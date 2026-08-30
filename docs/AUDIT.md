# Historical application audit

> **Status: historical context, not current runtime authority.**
>
> This document records the architectural cleanup that removed the older browser-orchestrated/tabbed prototype. For current behavior use [`ARCHITECTURE.md`](ARCHITECTURE.md), runtime code/config, and the documentation authority map in [`README.md`](README.md).

## Durable decision from this audit

The product is one persistent, audio-first music-understanding application. The former tabbed prototype, browser-only library, direct legacy music endpoints, duplicate transport/state paths, and placeholder feature surfaces were removed because maintaining multiple state/workflow authorities caused persistence loss, orchestration drift, and UI claims that were not backed by durable capabilities.

The durable principles that still matter are:

- one persistent Work/domain model rather than disconnected mini-apps;
- long-running processing owned by the durable backend worker rather than browser state;
- private persisted artifacts exposed through authenticated/signed access;
- immutable versions and provenance for derived outputs;
- product-visible analysis backed by persisted evidence and capability policy;
- real-stack/deployed evidence for cross-boundary claims rather than mocks alone.

## Historical implementation snapshot

At the time of the original audit, the product already had durable audio import, queued processing, transcription, Piano Roll, derived playback, MusicXML/Score, persisted analysis, and Work reopen behavior. Individual transport paths, upload mechanics, engine choices, capability maturity, and product surfaces have evolved since then.

In particular, do not use old implementation descriptions in this file to infer the current upload path, engine routing, analysis taxonomy, or current product feature set. Those belong to current code, `ARCHITECTURE.md`, and `backend/config/capabilities.json`.

## Why retain this file

It documents an important anti-regression boundary for future agents: **do not resurrect a second browser-only workflow/state authority or a disconnected feature prototype merely because it is easier to implement locally.**

Unresolved or future work belongs in current GitHub issues/roadmap documents rather than in this historical audit.
