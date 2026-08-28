# Transactional pgmq signal prototype

Status: **evaluation complete; not productionized**.

This evaluation is the follow-up to the pgmq delivery bakeoff in #359. It proves a consistency property that would be required if hello-ai ever adopted pgmq as a worker-delivery signal. It does **not** install pgmq, create a production trigger, or change the deployed worker transport.

## Result

The hypothesis passed on real PostgreSQL + pgmq in the repository's fresh-Supabase integration environment:

- queued INSERT emitted the exact inserted `job_id`;
- non-queued INSERT emitted no message;
- running → queued emitted a message;
- queued → queued emitted no duplicate message;
- rolling back a queued INSERT left neither the Job row nor a queue message;
- rolling back a running → queued transition restored the previous Job stage and left no queue message.

The critical conclusion is that a Postgres trigger calling `pgmq.send(...)` can participate in the **same database transaction** as the authoritative Job mutation. That removes the application-level dual-write window for this prototype.

Historical CI evidence included:

- `test_queued_transitions_emit_exact_job_identity` — passed;
- `test_job_and_queue_signal_share_transaction_rollback` — passed.

## Why this mattered

A naive future pgmq integration could perform two separate operations:

```text
insert/update public.jobs
send pgmq {job_id}
```

A crash or network failure between those operations can create either:

- a queued authoritative Job with no delivery signal; or
- a delivery signal whose authoritative Job transaction did not commit.

The evaluated trigger shape instead keeps the handoff inside PostgreSQL:

```text
API / retry / orphan recovery
          │
          ▼
  public.jobs mutation
          │ same transaction
          ▼
 trigger: entered queued?
          │
          └── pgmq.send({job_id})
```

The signal contains only `{job_id}`. Lifecycle, progress, inputs, outputs, provenance, retries, and terminal state remain in `public.jobs`.

## Prototype safety shape

`scripts/queue_transactional_signal_prototype.py` creates only uniquely named scratch objects and refuses non-local databases by default:

1. a minimal scratch Job table;
2. a disposable pgmq queue;
3. a `SECURITY INVOKER` trigger function with a fixed/empty search path;
4. an INSERT/UPDATE trigger.

The trigger fires only when a row **enters `queued`**.

This is deliberately not a browser-facing API. Any future production implementation should keep queue operations server/service-role only and revoke client-role access as appropriate.

## Production decision after the experiment

Although the transactional trigger approach is technically viable, hello-ai did **not** adopt pgmq for the current product/runtime envelope.

The simpler zero-cost option was sufficient: keep `public.jobs` as the authoritative queue and move worker claiming into one atomic Postgres operation using `FOR UPDATE SKIP LOCKED`. That shipped and was production-verified in #367.

This preserves:

- one authoritative Job model;
- existing leases and orphan recovery;
- retries/backoff and cancellation semantics;
- at-least-once execution with replay-safe/idempotent handlers;
- no new production queue abstraction or operational surface.

## When pgmq should be revisited

The transactional trigger result should be retained as reusable evidence, but pgmq should only be reconsidered if measured workload shows the atomic jobs-table transport is insufficient.

A future adoption would still require all of the following:

1. evidence of queue-age/throughput contention under real workload;
2. a worker transport abstraction with a safe fallback;
3. acknowledgement only after authoritative terminal/requeue state is persisted;
4. cancellation semantics for stale delivery signals;
5. orphan-recovery behavior for expired running leases;
6. queue depth/age observability integrated with existing telemetry;
7. extension/queue migration and rollback procedure;
8. storage-budget validation against the Supabase free-tier constraint;
9. a canary rollout before replacing the jobs-table delivery path.

If those gates are ever met, prefer this proven **transactional database-trigger signal** over an unsafe application dual write or an unnecessary separately operated dispatcher.

## Explicit non-goals

- no claim of exactly-once business execution;
- no production pgmq extension install;
- no production trigger migration;
- no queue Data API exposure;
- no Redis/Celery/RabbitMQ/SQS dependency;
- no provider migration;
- no paid infrastructure.