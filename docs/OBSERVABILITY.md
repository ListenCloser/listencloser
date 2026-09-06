# Production observability contract

This document is the maintained contract for turning Listen Closer's shipped traces, logs, metrics, health signals, and release identity into operational evidence. Normal deployment procedures remain in [`OPS.md`](OPS.md); incident recovery remains in [`RECOVERY.md`](RECOVERY.md). The machine-readable metric/formula companion is [`observability_contract.json`](observability_contract.json).

**Status:** baseline first; alert/SLO thresholds are intentionally unset.

## Shipped signal model

The API and worker share the OpenTelemetry bootstrap in `backend/observability.py`. When `OTEL_EXPORTER_OTLP_ENDPOINT` is absent, telemetry stays disabled so local development and ordinary CI do not require a remote observability service.

Structured JSON logs always include service and release identity. When a valid span is active, the formatter also includes `trace_id` and `span_id`.

### Durable API -> Job -> worker trace continuity

The durable Job boundary is asynchronous and at-least-once, so it must not be represented as one synchronous parent/child call stack.

Current contract:

1. workflow/Job creation injects the active W3C `traceparent` and optional `tracestate` into existing Job provenance under `trace_context`;
2. OpenTelemetry baggage is not persisted;
3. values are bounded and malformed/oversized carriers are ignored;
4. an existing persisted carrier wins on explicit retry, preserving the original producer context;
5. every worker `job.execution_attempt` creates its own span and attaches the producer context as a **span link**;
6. retries/takeovers therefore remain separately observable execution attempts while still being navigable back to the producer trace.

Request IDs remain a useful human log-correlation aid, but they are not trace context and must not be promoted into metric labels.

## Cardinality and privacy

Metrics may use only bounded dimensions that describe route/capability classes:

- HTTP method, FastAPI route template, and response status class;
- Job capability and bounded execution outcome;
- OpenTelemetry resource attributes such as service, release, and environment.

Do **not** use user, Project, Work, Version, Job, request IDs, raw request paths, filenames, or musical content as metric dimensions. Operational identifiers may appear in traces/logs when they are necessary and privacy-safe.

## Current OTLP instruments

The runtime currently emits:

| Instrument | Type | Unit | Dimensions |
| --- | --- | --- | --- |
| `hello_ai.http.server.requests` | counter | `{request}` | method, route template, status class |
| `hello_ai.http.server.duration` | histogram | `ms` | method, route template, status class |
| `hello_ai.worker.job.executions` | counter | `{job}` | capability, outcome |
| `hello_ai.worker.job.duration` | histogram | `s` | capability, outcome |
| `hello_ai.worker.orphans_recovered` | counter | `{job}` | none |

The `hello_ai.*` prefix is the current shipped instrument identity. Product naming changed later; documentation must not silently rename telemetry that still exists under the legacy stable name.

Current worker execution outcomes are `succeeded`, `failed`, `cancelled`, and `retry`. `retry` describes an execution attempt that will be retried; it is not a terminal Job state.

`hello_ai.worker.orphans_recovered` belongs to the legacy custom queue/lease transport. #651 owns the active PGMQ cutover and eventual deletion of superseded transport machinery, so this diagnostic must not be promoted into a durable SLO before that cutover settles.

## Initial measurement formulas

The formulas are vendor-neutral; the backend may translate OTLP names/histograms into provider-specific series.

### API

For each method + route template and reporting window, record request count and status-class distribution.

- **non-5xx rate** = non-5xx requests / all requests;
- **server error rate** = 5xx requests / all requests;
- **client error rate** = 4xx requests / all requests, reported separately;
- **latency** = p50 / p95 / p99 of request duration, always with sample count.

Non-5xx rate is an operational availability proxy, not product-task success. Authentication, authorization, validation, and not-found responses can legitimately be 4xx.

### Worker

For each capability:

- report counts for `succeeded`, `failed`, `cancelled`, and `retry`;
- **terminal success rate** = succeeded / (succeeded + failed + cancelled);
- **terminal failure rate** = failed / (succeeded + failed + cancelled);
- **cancelled rate** = cancelled / (succeeded + failed + cancelled);
- **retry-attempt rate** = retry / all execution attempts;
- **duration** = p50 / p95 / p99 by capability + outcome, always with sample count.

Cancellation is not failure. Retry pressure is operationally important but must not be counted as a terminal Job failure.

## Other initial operability signals

Not every useful signal is currently an OTLP metric.

- `GET /health/queue` is the current worker-heartbeat/capability-availability view.
- `GET /health/ready` plus telemetry/log release fields prove release identity; deployment verification must match the expected SHA.
- Production-shaped verification provides point evidence for the canonical understand workflow.

Queue wait / oldest queued age is deliberately not defined here while #651 owns the PGMQ production cutover and transport telemetry. Canonical end-to-end understand completion latency also lacks a continuous bounded OTLP instrument today. These are explicit owner gaps, not permission to invent high-cardinality metrics.

## Production baseline procedure

Before proposing a latency, availability, or Job-success threshold, capture at least:

1. one release-scoped production window;
2. one rolling multi-day production window after release-specific anomalies settle.

For every baseline record:

- absolute UTC start/end;
- release SHA(s);
- `service.name` and `service.version`;
- request and worker sample counts;
- p50/p95/p99 only where sample count is adequate;
- HTTP status-class distribution;
- worker outcome distribution including retries and cancellations;
- deploys/incidents that materially distort the sample;
- the provider query/dashboard expression used to implement the vendor-neutral formula.

A production baseline is evidence, not a placeholder. Do not manufacture values from CI timing or a one-off local run.

## Debugging recipe

When a production workflow fails:

1. **Identify release and surface.** Record what the user saw, the response/request reference if present, and the deployed SHA from readiness.
2. **Find the API log/trace.** Use request ID for log search when available; use the log's active `trace_id` for trace navigation.
3. **Cross the durable boundary.** Inspect the Job and its provenance. A valid `trace_context` identifies the original producer trace.
4. **Find execution attempts.** Worker `job.execution_attempt` spans link to that producer context. Treat each retry/takeover as a distinct attempt; use Job lifecycle/execution-token fields to reason about ownership rather than inferring one synchronous trace.
5. **Locate the failing boundary.** Use span status plus structured logs to identify DB/RLS, Storage, queue/worker, engine/model, evidence parser, provider, or release mismatch.
6. **Check bounded impact.** Use route/capability metrics only when the failure should affect a population-level operational measure. Do not create a new metric solely to make one incident easier to search.
7. **Route ownership.** Product defects remain with their focused issue; #637 owns the observability contract, not every failure discovered through it.

Dashboard/provider URLs and credentials are deployment/account data and belong in owner configuration, not source control. [`OPS.md`](OPS.md) records the maintained ways to reach Sentry, logs, health, and the opt-in Grafana/Loki stack.

## Threshold policy

Thresholds remain unset until production baselines are sufficient and the product target is explicit. In particular:

- do not use hosted CI wall-clock time as a production latency SLO;
- do not collapse expected 4xx into server failure;
- do not collapse user cancellation or retry attempts into terminal processing failure;
- do not create an SLO per endpoint, model, or incident.

Once a threshold is justified, update this document and `observability_contract.json` in the same focused change and state the measured baseline that supports it.

Refs #637 #651 #1011 #353.
