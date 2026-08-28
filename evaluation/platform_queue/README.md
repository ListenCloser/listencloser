# Platform V3 queue transport bakeoff

Status: **evaluation only; production decision completed**.

This evaluation compared hello-ai's former two-request jobs-table claim path with Postgres-native `pgmq` delivery. It does **not** enable Supabase Queues or `pgmq` in production.

## Outcome

The bakeoff established two useful facts:

1. the former `select oldest queued row -> conditional UPDATE` path creates avoidable queue-head contention when several workers poll at once; and
2. `pgmq` provides useful durable delivery primitives, including visibility timeouts and redelivery after an unacknowledged read.

For the current workload and hard `$0/month` constraint, hello-ai chose the simpler production option from this evaluation's decision gate: keep `public.jobs` authoritative and move claiming into one atomic Postgres operation using `FOR UPDATE SKIP LOCKED`.

That production change shipped in #367. The deployed worker therefore no longer uses the two-request claim path measured by this harness.

`pgmq` remains a future transport option if measured scale justifies another delivery layer. Adopting it would still require a safe enqueue transaction boundary and replay-safe handlers.

## Architecture boundary

`public.jobs` remains the authoritative domain record in every evaluated option. Queue delivery is an implementation detail for assigning/waking workers with a `job_id`; progress, provenance, retries visible to the product, inputs, outputs, and terminal state remain in the domain table.

The business-level guarantee is **at-least-once execution with replay-safe/idempotent handlers**, not exactly-once side effects.

## Why `pgmq` was evaluated

Supabase Queues is Postgres-native and built on the PostgreSQL-licensed `pgmq` extension. It provides a visibility timeout, durable logged queues, delete/archive acknowledgement, and safe concurrent reads without introducing Redis, RabbitMQ, SQS, or another paid service.

Primary references verified during the 2026-08-28 evaluation:

- https://supabase.com/docs/guides/queues
- https://supabase.com/docs/guides/queues/quickstart
- https://supabase.com/docs/guides/queues/api
- https://github.com/pgmq/pgmq

The live Supabase project exposed `pgmq` 1.5.1 as an available extension at evaluation time, but this work intentionally did **not** install it there.

## Historical jobs-table path evaluated

Before #367, the worker did:

1. select the oldest `stage='queued'` row;
2. issue a separate conditional update for that `job_id` with `stage='queued'`;
3. only the worker whose update returned a row won the lease.

The conditional update prevented duplicate ownership at the claim transition, but several workers could select the same oldest row and all but one lose the update. That created avoidable database round trips and head-of-queue contention.

#367 replaced this path with an atomic database claim while preserving leases, orphan recovery, retries, and at-least-once semantics.

## What the harness tests

`scripts/queue_transport_bakeoff.py` operates only on a local Postgres URL by default and creates disposable objects:

- a scratch table that reproduces the former select-then-conditional-claim path;
- a disposable basic `pgmq` queue.

It checks two dimensions.

### Contention

With N worker processes synchronized on the former pattern, all workers select the same head row and only one conditional update wins. The harness records lost claims and database calls per successful claim.

With `pgmq.read(queue, vt, qty)`, concurrent readers should receive distinct visible messages. The harness records empty reads, duplicate message IDs, and calls per successful claim.

This is a **contention/round-trip diagnostic**, not a production throughput benchmark: the tool launches `psql` subprocesses, so wall-clock timings mostly measure process startup rather than queue performance.

### Visibility timeout / replay

The harness verifies that:

1. a read message becomes invisible to another consumer;
2. an unacknowledged message becomes visible after the visibility timeout;
3. the same message is redelivered with `read_ct` incremented;
4. a successful consumer can delete it.

That behavior is useful for worker-crash recovery, but it also demonstrates why arbitrary music-processing side effects still require idempotency.

## Safety

The CLI refuses non-local database hosts unless `--allow-remote` is passed explicitly. CI runs it only against the ephemeral `supabase start` database.

No production migration enables `pgmq`. No `pgmq_public` schema is exposed to browsers. Any future queue adoption should remain server-side/service-role only.

## Run locally

With the local Supabase stack running:

```bash
supabase start
eval "$(supabase status -o env | grep '^DB_URL=')"
python scripts/queue_transport_bakeoff.py "$DB_URL" --messages 12 --workers 4
```

Fresh-database CI also runs the semantic assertions in `backend/tests/integration/test_pgmq_queue_bakeoff.py`.

## Future `pgmq` adoption gate

Revisit `pgmq` delivery only if measured workload shows the atomic jobs-table transport is insufficient and all of these remain true:

- local real-Postgres integration proves visibility/replay and concurrent distinct claims;
- queue storage remains within the Supabase database budget;
- operational behavior is understandable from existing Postgres/Supabase tooling;
- enqueueing can be made consistent with `public.jobs` creation without dual-write loss;
- worker handlers remain replay-safe.

A possible future shape would be:

```text
transaction / backend command
    -> public.jobs row (authoritative state)
    -> pgmq message {job_id} (delivery signal)

worker
    -> pgmq.read(... visibility timeout ...)
    -> load/claim public.jobs job_id
    -> execute idempotent handler
    -> persist terminal public.jobs state
    -> pgmq.delete/archive(message)
```

The enqueue transaction boundary must be proven before adoption. If inserting `public.jobs` and sending the queue signal cannot share one reliable database transaction through the application access path, use a database trigger/outbox design rather than an unsafe application dual write. The follow-up evaluation in #360 specifically tests the Postgres-trigger option.

## Explicit non-goals

- no claim of exactly-once music processing;
- no production `pgmq` extension install;
- no queue Data API exposure;
- no Redis/Celery/RabbitMQ/SQS dependency;
- no provider migration;
- no paid infrastructure.