# Platform V3 queue transport bakeoff

Status: **evaluation only**. This does not enable Supabase Queues or `pgmq` in production.

## Question

Should hello-ai keep hand-written `public.jobs` polling/lease delivery, replace only the delivery layer with Supabase Queues / `pgmq`, or harden the existing table claim path with one atomic Postgres claim function?

`public.jobs` remains the authoritative domain record in every option. Queue delivery is an implementation detail for waking a worker up with a `job_id`; progress, provenance, retries visible to the product, inputs, outputs, and terminal state remain in the domain table.

## Why `pgmq` is the first competitor

Supabase Queues is Postgres-native and built on the PostgreSQL-licensed `pgmq` extension. It provides a visibility timeout, durable logged queues, delete/archive acknowledgement, and safe concurrent reads without introducing Redis, RabbitMQ, SQS, or another paid service.

Primary references (verified 2026-08-28):

- https://supabase.com/docs/guides/queues
- https://supabase.com/docs/guides/queues/quickstart
- https://supabase.com/docs/guides/queues/api
- https://github.com/pgmq/pgmq

The live Supabase project exposes `pgmq` 1.5.1 as an available extension, but it is intentionally **not installed** by this evaluation.

## Current implementation being compared

The current worker does:

1. select the oldest `stage='queued'` row;
2. issue a separate conditional update for that `job_id` with `stage='queued'`;
3. only the worker whose update returns a row wins the lease.

That is safe against duplicate ownership at the claim transition, but multiple workers can select the same oldest row and then lose the conditional update. As worker count increases, this creates avoidable database round trips and head-of-queue contention.

The worker also uses lease expiry/orphan recovery. Therefore the business-level guarantee is **at-least-once execution with replay-safe/idempotent handlers**, not exactly-once side effects.

## What the harness tests

`scripts/queue_transport_bakeoff.py` operates only on a local Postgres URL by default and creates disposable objects:

- a scratch table that reproduces select-then-conditional-claim;
- a disposable basic `pgmq` queue.

It then checks:

### Contention

With N worker processes synchronized on the current pattern, all workers select the same head row and only one conditional update wins. The harness records those lost claims and the database calls required per successful claim.

With `pgmq.read(queue, vt, qty)`, concurrent readers should receive distinct visible messages. The harness records empty reads, duplicate message IDs, and calls per successful claim.

This is a **contention/round-trip diagnostic**, not a production throughput benchmark: the tool launches `psql` subprocesses, so its wall-clock timings would mostly measure process startup rather than queue performance.

### Visibility timeout / replay

The harness verifies that:

1. a read message becomes invisible to another consumer;
2. an unacknowledged message becomes visible after the visibility timeout;
3. the same message is redelivered with `read_ct` incremented;
4. a successful consumer can delete it.

This is the behavior needed for worker-crash recovery, but it also proves why arbitrary music-processing side effects still need idempotency.

## Safety

The CLI refuses non-local database hosts unless `--allow-remote` is passed explicitly. CI runs it only against the ephemeral `supabase start` database.

No production migration enables `pgmq`. No `pgmq_public` schema is exposed to browsers. If adopted later, hello-ai workers should use server-side database access/service credentials only; queue APIs should not become a client authorization boundary.

## Run locally

With the local Supabase stack running:

```bash
supabase start
eval "$(supabase status -o env | grep '^DB_URL=')"
python scripts/queue_transport_bakeoff.py "$DB_URL" --messages 12 --workers 4
```

The fresh-database CI also runs the semantic assertions in `backend/tests/integration/test_pgmq_queue_bakeoff.py`.

## Decision gate

### Prefer `pgmq` delivery if

- local real-Postgres integration proves visibility/replay and concurrent distinct claims;
- contention is materially simpler than the current two-request claim path;
- queue storage remains small enough for the existing Supabase database budget;
- operational behavior is understandable from Postgres/Supabase tooling;
- enqueueing can be made consistent with `public.jobs` creation without dual-write loss;
- worker handlers remain replay-safe.

A production design would likely be:

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

The enqueue transaction boundary must be proven before adoption. If inserting `public.jobs` and sending the queue message cannot share one reliable database transaction through our application access path, use an outbox-style trigger/dispatcher rather than an unsafe dual write.

### Keep the current jobs-table transport if

- measured Oracle workload is low enough that collisions are negligible;
- `pgmq` adds database/storage/operational cost without meaningful queue benefit;
- its deployment/extension lifecycle is materially harder than the current table.

If we keep it and horizontal workers become necessary, replace select-then-update with one DB-side atomic claim using `FOR UPDATE SKIP LOCKED` rather than adding Redis/Celery.

## Explicit non-goals

- no claim of exactly-once music processing;
- no production `pgmq` extension install;
- no queue Data API exposure;
- no Redis/Celery/RabbitMQ/SQS dependency;
- no provider migration;
- no paid infrastructure.
