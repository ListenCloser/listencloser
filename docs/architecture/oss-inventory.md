# OSS / model responsibility inventory

This is a **responsibility map**, not a dependency lockfile and not an endorsement list.

Versions are intentionally not copied here. Read `package.json` / package lock and `backend/pyproject.toml` / `backend/uv.lock` for installed versions, and read `backend/config/capabilities.json` plus durable evaluation evidence for product maturity.

## Frontend / product runtime

| OSS | Boundary | Responsibility | Authority / warning |
|---|---|---|---|
| Next.js | web app / proxy | application routing, server/runtime integration, `/api/v1` proxy surface, production build | package manifest + application code |
| React | browser UI | workspace/component rendering and state composition | package manifest |
| TanStack Query | browser server-state layer | request/cache orchestration where used | application imports/config; cache is not durable truth |
| Supabase JS | browser | Auth/session plus authorized signed Storage transfer | browser must not gain service-role/domain write authority |
| OpenSheetMusicDisplay | representation renderer | render MusicXML score in browser | renderer only; does not own notation correctness |
| Tailwind/PostCSS | styling/build | CSS build/tooling | global style ownership remains under #523 |
| Playwright | verification | application E2E, real-stack browser proof, visual/interaction diagnostics | not production runtime |
| Vitest / Testing Library | verification | frontend unit/component behavior | not production runtime |

## Backend platform runtime

| OSS | Boundary | Responsibility | Authority / warning |
|---|---|---|---|
| FastAPI | API | HTTP routing/schema/lifespan/middleware | OpenAPI generated from this boundary owns wire schema |
| Uvicorn | API process | ASGI server | deployment/runtime concern |
| Pydantic | domain/API | immutable domain values + request/response validation | does not replace DB migration authority |
| Supabase Python | API + worker | service-role Postgres/Auth/Storage client | caller authorization remains repository/domain responsibility |
| httpx | API | shared outbound HTTP client (including optional provider paths) | instrumented by OTel |
| SlowAPI | API | request rate limiting | policy lives in backend auth/API config |
| OpenTelemetry | API + worker | portable traces/metrics/instrumentation | #637 owns semantic/propagation/SLO contract |
| Sentry SDK | API + worker | configured error/performance reporting | consumer/vendor, not the telemetry domain model |

## Music processing runtime

The stable caller concept should be a **capability**; vendor/model names belong at adapter, evaluation and provenance boundaries.

| OSS/model | Adapter/capability role | Current architectural status |
|---|---|---|
| Basic Pitch | audio → performance-note/MIDI transcription | production-capable default/general transcription path; quality/domain remains evaluated, not universal |
| Transkun | piano-oriented transcription profile | available specialized engine; do not globally route without profile/evaluation evidence |
| librosa | audio DSP and current default beat path; perceptual-series preprocessing | production dependency; individual evidence claims have separate maturity |
| Beat This | alternative beat/downbeat engine | installed/evaluated candidate; registry availability does not imply effective production routing |
| lv-chordia | audio harmony/chord evidence | production deployment config selects this for harmony; product exposure still capability-gated |
| music21 | symbolic analysis, key/theory support and notation engine; harmony fallback/default in registry | multiple roles; registry default may differ from deployed effective harmony path |
| LStoM model/runtime | melody extraction | experimental/product-bounded melody evidence; validated domain recorded in capability registry |
| skyline melody heuristic | melody baseline | evaluation-only legacy baseline; existence is for comparison, not product fallback |
| AllIn1 | audio structure candidate | evaluation-only/withheld structure path unless current capability policy says otherwise |
| Partitura | symbolic/notation tooling | supporting notation/symbolic processing dependency |
| pretty_midi | MIDI I/O/manipulation | supporting representation/evaluation/processing utility |
| FluidSynth / pyFluidSynth | MIDI/rendered audio playback generation | derived audio rendering; renderer does not establish transcription correctness |
| Torch / torchaudio | ML runtime substrate | worker/ML footprint; target for dependency ownership split (#287) |
| TensorFlow (via Basic Pitch extra) | Basic Pitch inference runtime | worker/ML footprint; currently constrains parts of telemetry/protobuf dependency graph |
| soundfile / scipy / NumPy / soxr | audio/scientific primitives | shared DSP/data substrate; should not leak into API-only queries when persisted schemas/arithmetic suffice (#642) |

## Engine selection is not one table

Effective engine routing is determined by several layers:

```text
capability / handler
  → explicit engine/profile request (if any)
  → engine registry
  → environment/deployment override
  → registry fallback/default
  → actual installed adapter/model
```

For example, the harmony registry defaults to `music21`, while production-shaped Compose explicitly sets `HARMONY_ENGINE=lv_chordia`. Persisted provenance should make the actual producing engine inspectable after the fact.

Do not update architecture prose every time an environment default changes; the point of this file is to explain ownership.

## Capability maturity is independent from installation

An installed/runnable package may be:

- production;
- experimental;
- evaluation-only;
- withheld;
- a fallback/compatibility path.

`backend/config/capabilities.json` is the current product evidence maturity/exposure authority. Examples on the verified baseline include production chord/key/rhythm/perceptual evidence, experimental melody families, and withheld/evaluation-only cadence/structure families.

A future agent must not infer product safety from any of:

- package is in `pyproject.toml`;
- adapter imports successfully;
- handler is registered;
- model returns output;
- one qualitative example looks good.

## Evaluation / research tooling

Evaluation code intentionally consumes additional datasets, metric libraries and candidate wrappers that are not automatically part of production runtime. #287/#636 own making that dependency/code boundary explicit.

The target lifecycle for a substantial music dependency/model is:

```text
research question
→ candidate adapter
→ task-standard dataset/metric
→ quality + failure distribution
→ license + operational measurement
→ ADOPT / RESEARCH / REJECT / REVISIT decision
→ capability policy / production routing if justified
```

## Dependency-pressure findings

Current backend dependency ownership has several architectural consequences:

1. API and worker share one default Python dependency graph, so lightweight request-serving CI/runtime can pull TensorFlow/Torch/music inference dependencies (#287).
2. OTel versions are currently constrained partly by Basic Pitch/TensorFlow protobuf compatibility, demonstrating how an ML dependency can affect unrelated platform packages when boundaries are not split.
3. API relation-query code has recently been shown to transitively import DSP dependencies merely to read persisted evidence contracts; PR #642 is extracting that lightweight schema/arithmetic seam.
4. dynamic adapters/plugins mean a static "unused dependency" result is evidence to investigate, not permission to auto-delete.

## Addition rule

Before adding a substantial new OSS/model dependency, record:

- exact user/product capability it enables;
- why an existing dependency cannot satisfy it;
- code license and model-weight license separately;
- training/data restrictions when relevant;
- CPU/GPU/ARM/container compatibility;
- model/package size and memory/latency profile;
- evaluation evidence and validated domain;
- whether it belongs to core/API, worker/ML, dev/test or evaluation/research.

Prefer replacing/consolidating an existing responsibility over accumulating multiple permanent libraries for the same task without a fallback/evaluation rationale.