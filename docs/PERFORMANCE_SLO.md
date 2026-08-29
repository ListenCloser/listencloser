# Performance and reliability measurement contract

Status: **baseline first; thresholds intentionally unset**.

This document turns hello-ai's existing OpenTelemetry instruments into a repeatable latency and reliability report. It does not introduce another telemetry vendor or treat CI wall-clock time as production performance evidence.

The machine-readable source of truth is [`performance_slo_contract.json`](./performance_slo_contract.json).

## Existing production instruments

The backend and worker already emit these vendor-neutral OTLP metrics from `backend/observability.py`:

| Instrument | Type | Unit | Bounded dimensions |
|---|---|---|---|
| `hello_ai.http.server.requests` | counter | requests | method, route template, status class |
| `hello_ai.http.server.duration` | histogram | ms | method, route template, status class |
| `hello_ai.worker.job.executions` | counter | jobs | capability, outcome |
| `hello_ai.worker.job.duration` | histogram | s | capability, outcome |
| `hello_ai.worker.orphans_recovered` | counter | jobs | none |

Never add user/project/work/version/job IDs, raw request paths, filenames, or musical content as metric labels. Those dimensions would create high-cardinality telemetry and leak product data into an operational system.

## API report

For each production reporting window record:

1. request volume by route;
2. p50 / p95 / p99 request duration by route;
3. 5xx rate by route;
4. 4xx rate separately from 5xx;
5. sample count for every percentile series.

The first performance-critical route is:

`GET /api/v1/works/{work_id}`

This route should be reported separately because it is the server-side entry point for opening a saved Work.

### Availability vs task success

Do not call `1 - 4xx - 5xx` the success rate.

For operational API availability, server 5xx responses are failures. A 4xx can be an expected authentication, authorization, validation, or not-found result and must remain separately observable.

A future product-task success metric may classify selected 4xx outcomes differently, but it must be based on explicit workflow semantics rather than HTTP status alone.

## Worker report

For every worker capability record:

- executions by terminal outcome: `succeeded`, `failed`, `cancelled`;
- p50 / p95 / p99 handler duration;
- sample count;
- orphan-recovery count/rate.

Always show cancelled separately. A user cancellation is not equivalent to a processing failure, even if an aggregate terminal-success calculation uses all terminal outcomes as its denominator.

## Product-level latency

HTTP latency alone does not explain the user-visible complaint that switching recordings feels slow. The saved-Work browser benchmark tracked in #483 measures a separate product path:

- `source_ready_ms` — click/select to durable playback-source availability;
- `evidence_ready_ms` — click/select to analysis evidence settling;
- `workspace_artifacts_ready_ms` — click/select to available representation artifacts (currently Piano Roll + Score) settling;
- `score_render_ready_ms` — selecting Score to actual rendered VexFlow measure availability.

These should be compared for at least:

- a cold first open;
- a warm A → B → A revisit;
- a revisit after signed-URL rotation/cache expiry;
- an active-job progressive refresh.

A latency optimization PR should name the stage it expects to improve and include before/after evidence for that stage.

## Baseline procedure

For a production baseline, record all of the following in one checked-in report or issue comment:

- absolute UTC start/end timestamps;
- production release SHA(s);
- service version/resource attribute;
- request/job sample counts;
- p50 / p95 / p99 where sample count is adequate;
- 2xx/3xx/4xx/5xx request distribution;
- worker succeeded/failed/cancelled distribution;
- known incidents or deploy windows that materially distort the sample.

Use at least one release-scoped window and one rolling multi-day window before proposing alert thresholds.

## Threshold policy

No p95, p99, availability, or worker-success threshold is specified yet. That is deliberate.

Choose thresholds only after:

1. production baselines exist with sample counts;
2. the product target is explicit (for example, what a good warm Work revisit should feel like);
3. expected 4xx and cancellation semantics are separated from true failures;
4. one-off deploy/cold-start effects are understood;
5. the threshold can be monitored continuously rather than only in CI.

Hosted CI may enforce deterministic contracts such as request count, cache hit behavior, decode count, FFT count, or output correctness. It should not fail a PR because one shared runner took an arbitrary number of milliseconds.

## Query translation note

OTLP metric names and attributes are canonical. Grafana/Prometheus-compatible backends may translate dots, units, or histogram suffixes during ingestion. Build dashboard queries from the ingested series corresponding to the OTLP instruments above rather than treating one vendor's translated metric name as the source of truth.

The mathematical queries are defined in `performance_slo_contract.json` so the same contract can be rendered in Grafana, another OTLP backend, or an offline export.

## Next instrumentation gaps

Only add new production metrics when the existing instruments cannot answer a product question. The current highest-value gaps are:

1. Work-bundle phase decomposition: persistence snapshot vs signed-URL generation;
2. workflow queue wait;
3. first durable derived-artifact latency;
4. end-to-end workflow terminal latency;
5. sampled browser Work-open latency after the local benchmark contract stabilizes.

Do not add high-cardinality IDs to solve any of these. Use bounded stage/capability dimensions and correlate individual incidents through traces/logs when necessary.

Refs #482 #483 #485
