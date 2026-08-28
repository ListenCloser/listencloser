# Transactional pgmq signal prototype

Status: **evaluation only**. This is stacked on the pgmq delivery bakeoff and does not install pgmq or a trigger in production.

## Problem

PR #359 showed that pgmq clears the local concurrent-delivery and visibility-timeout gate. The remaining architectural risk is a dual write:

```text
insert public.jobs row
send pgmq {job_id}
```

If those are separate application/database requests, a process or network failure can leave:

- a queued authoritative Job with no delivery signal, or
- a delivery signal whose authoritative Job transaction did not commit.

That is not an acceptable production handoff.

## Hypothesis

Because pgmq is a PostgreSQL extension inside the same database, the signal can be emitted by an `AFTER INSERT OR UPDATE OF stage` trigger on the authoritative Job row.

The trigger emits only when a row **enters `queued`**:

- queued job INSERT → signal;
- running/claimed/failed → queued transition → signal;
- queued → queued metadata update → no new signal;
- non-queued insert → no signal.

The message contains only `{job_id}`. All lifecycle/progress/input/output/provenance state remains in `public.jobs`.

Conceptually:

```text
API / retry / orphan recovery
          │
          ▼
  public.jobs mutation
          │ same Postgres transaction
          ▼
   trigger: entered queued?
          │
          └── pgmq.send({job_id})
```

If `pgmq.send` participates in the surrounding PostgreSQL transaction, rollback of the Job mutation must also roll back the queue message. That removes the application dual-write window without introducing an outbox dispatcher.

## What this PR proves

`scripts/queue_transactional_signal_prototype.py` creates only uniquely named scratch objects in a local database by default:

1. a minimal scratch Job table;
2. a disposable pgmq queue;
3. a `SECURITY INVOKER` trigger function;
4. an INSERT/UPDATE trigger.

The real-stack integration assertions verify:

- queued INSERT emits the exact inserted job ID;
- non-queued INSERT is silent;
- running → queued emits a signal;
- queued → queued does not emit a duplicate signal;
- rolling back a queued INSERT leaves neither the Job row nor queue signal;
- rolling back a running → queued transition leaves the previous Job stage and no queue signal.

A rollback test is the key result: if it passes against real Postgres/pgmq, the queue signal has the same commit boundary as authoritative Job state.

## Security shape for a later production migration

This prototype deliberately avoids a `SECURITY DEFINER` trigger. A production function should remain `SECURITY INVOKER`, use a fixed/empty `search_path`, and not become a browser-callable API. Execute privileges should be revoked from `PUBLIC`/client roles as appropriate.

The queue itself remains worker/server infrastructure. `public.jobs` RLS continues to govern the user-visible job model.

## Remaining gates even if this passes

A successful transactional signal does **not** make pgmq production-ready by itself. We still need:

1. a worker transport abstraction so the current table poller remains a fallback;
2. pgmq message acknowledgement only after authoritative terminal/requeue state is safely persisted;
3. cancellation behavior for stale queued signals;
4. orphan recovery behavior when a running Job lease expires;
5. queue depth/age observability integrated with #353;
6. extension/queue migration and rollback procedure;
7. a short canary period before removing table polling;
8. confirmation that pgmq storage stays comfortably inside the Supabase free DB budget.

## Decision if rollback is atomic

Prefer a **transactional database-trigger signal** over an application dual-write or a separately operated outbox dispatcher. It is smaller, keeps the consistency boundary in one database transaction, and adds no service.

If the rollback test fails, do not adopt this pattern. Fall back to an explicit outbox table written in the Job transaction or retain the current jobs-table delivery with an atomic `FOR UPDATE SKIP LOCKED` claim.
