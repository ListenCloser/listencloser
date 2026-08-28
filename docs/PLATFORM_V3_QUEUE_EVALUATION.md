# Platform V3 queue evaluation

Last verified: 2026-08-28

Related: #329, #353, #356, #357

## Decision summary

Do **not** add Redis, Celery, RabbitMQ, SQS, or another paid queue merely to make the platform look more production-like.

Also do **not** immediately spend engineering effort hardening the current hand-written lease protocol. There is now a stronger zero-cost candidate already available inside the state layer we use: **Supabase Queues / `pgmq`**.

Recommended sequence:

1. Keep the existing `public.jobs` table and worker behavior as the production baseline today.
2. Correct the architecture language: the current lease/retry design should be treated as **at-least-once execution with idempotent handlers**, not mathematically exactly-once processing.
3. Run a bounded local/real-stack `pgmq` bakeoff against the current queue before changing production persistence.
4. If the bakeoff is positive, use `pgmq` for **delivery/claim/retry visibility semantics** while preserving `public.jobs` as the product-domain job record and audit/status model.
5. Only introduce a separate cloud queue when Postgres queue throughput, isolation, or operational requirements become a measured bottleneck.

The key design distinction is:

```text
Product job state                     Delivery mechanism
-----------------                     ------------------
workflow/job identity                 message visibility
capability/version                    atomic consumer claim
user-visible progress                 retry delivery
outputs/errors/provenance             acknowledgement/archive
ownership/RLS                         queue depth

public.jobs                            current polling OR pgmq
(stable domain contract)               (replaceable transport)
```

This avoids forcing an infrastructure queue to become the product's source of truth.

---

## Current queue: what we actually have

`backend/domain/job_worker.py` currently:

- uses Supabase/Postgres `public.jobs`
- polls the oldest `queued` row
- conditionally updates that row to `claimed`
- attaches `worker_id` and `lease_expires_at`
- transitions `claimed -> running -> succeeded/failed`
- renews leases from a heartbeat thread
- recovers expired `claimed`/`running` jobs back to `queued`
- retries failures with application-side exponential backoff
- checks `cache_key` for idempotency assistance
- publishes worker heartbeats

This is already much better than an in-memory background task, and it has one major advantage: job status is directly queryable as application data.

### Correct semantics

The module currently describes the lease as ensuring “exactly-once processing.” That is too strong.

Example failure:

1. handler produces external/database side effects
2. process dies before `jobs.stage` is committed to `succeeded`
3. lease expires
4. another worker recovers and executes the job again

A cache key can reduce duplicate work, but it cannot generally prove that arbitrary handler side effects happen exactly once.

The safe contract is:

> **At-least-once execution. Handlers that can be replayed must be idempotent, deduplicated, transactional, or otherwise replay-safe.**

This remains true for most real queues, including visibility-timeout systems: “exactly once delivery within a visibility timeout” is not the same as exactly-once business-side-effect execution.

### Current multi-worker inefficiency

The worker first selects the oldest queued row and then attempts a conditional update on it. Two or more workers can therefore all observe the same oldest row and race to claim it. Only one should win, but the losers pay avoidable query/update round-trips and can repeatedly contend on the head of the queue.

If we keep the bespoke queue, the correct repair is a DB-side atomic claim using one transaction and `FOR UPDATE SKIP LOCKED`.

Before writing that code ourselves, compare `pgmq`.

---

## Candidates

| Candidate | Extra infra | Python fit | Postgres-native | retry / visibility | dashboard/ops | `$0` baseline | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| **Current `public.jobs` leases** | None | Excellent | Yes | Hand-written | Existing app health only | **Yes** | **KEEP baseline** |
| **Supabase Queues / `pgmq`** | **None** | Good via SQL/RPC | **Yes** | **Built in** | **Supabase dashboard + archive** | **Yes; runs in DB** | **BAKE OFF FIRST** |
| **Procrastinate** | None beyond Postgres | **Excellent** | Yes | Built in | Library tooling | Yes | WATCH / fallback |
| **TaskIQ + PostgreSQL plugin** | None beyond Postgres | Excellent | Yes | Framework-managed | Framework tooling | Yes | WATCH; immature plugin risk |
| **Inngest Cloud** | Hosted service | Python supported | No | Strong | **Strong** | Free Hobby limits | DEFER; new vendor/control plane |
| **Hatchet Cloud** | Hosted service | Python supported | No | Strong | **Strong** | First 100k task runs included | DEFER; new vendor/control plane |
| **Celery / Dramatiq / RQ** | Redis/RabbitMQ normally | Excellent | No | Mature | Extra tooling | Broker must be hosted | REJECT now |
| **AWS SQS** | AWS service | Excellent | No | Mature visibility model | CloudWatch/AWS | Requests have free allowance but creates AWS dependency | DEFER |

---

## 1. Supabase Queues / PGMQ

Supabase Queues is a first-party Postgres-native queue built on the open-source `pgmq` extension.

Relevant capabilities:

- durable logged queues
- pull-based consumption
- customizable visibility timeout
- messages remain until explicitly deleted/archived
- guaranteed delivery
- exactly-once **delivery to one consumer inside a visibility window**
- archive tables for replay/audit
- dashboard queue/message management
- RLS/permission controls if exposed through the Data API
- no separate queue infrastructure

Supabase's own Queues announcement says it runs entirely in the database and has **no additional feature cost**; database compute/disk usage still counts against the project's normal limits.

The open-source `pgmq` project uses the PostgreSQL license and explicitly aims for SQS/RSMQ-like semantics.

### Live project compatibility

The current `hello-ai` Supabase project exposes `pgmq` version `1.5.1` as an available extension. It is **not installed** today. That is the ideal state for an evaluation: no migration has occurred and no production queue behavior has changed.

### Proposed role

Do not copy the entire `jobs` row into a queue message and delete the domain table.

Instead:

```text
Create workflow/job
       |
       +--> public.jobs row (domain/audit/status truth)
       |
       +--> pgmq message { job_id }

worker pgmq.read(... visibility_timeout ...)
       |
       +--> load public.jobs
       +--> execute capability
       +--> update public.jobs
       +--> pgmq.archive/delete message on success
```

This separates scheduling from product state and keeps a future queue migration cheap.

### Risks

- Supabase Queues is currently labeled Public Alpha in Supabase's feature page.
- Queue messages consume the same Postgres disk/compute budget as the rest of the free project.
- We need to verify local Supabase/CI support for the exact `pgmq` version.
- Long MIR tasks need a visibility timeout / lease-extension strategy longer than expected execution time or an explicit visibility extension.
- We need a clear transaction/outbox story so a `public.jobs` row and its queue message cannot silently diverge.
- Client access is unnecessary: server-side service-role/Postgres access should remain the default.

### Decision gate

Adopt `pgmq` only if a real-stack test proves:

- two or more worker processes claim distinct messages without duplicate simultaneous delivery
- an unacked message becomes available again after visibility timeout
- successful completion archives/deletes the delivery message
- `public.jobs` remains authoritative for user-visible state
- cancellation semantics remain correct
- crash-after-handler behavior is understood and documented as replayable/at-least-once
- queue operations do not materially worsen database latency at representative load

Primary sources:
- https://supabase.com/docs/guides/queues
- https://supabase.com/docs/guides/queues/pgmq
- https://supabase.com/docs/guides/queues/quickstart
- https://supabase.com/blog/supabase-queues
- https://github.com/pgmq/pgmq

---

## 2. Procrastinate

Procrastinate is an MIT-licensed, production/stable-classified Python task queue built directly on PostgreSQL 13+.

It provides more application-level task semantics than raw `pgmq`, including:

- sync/async workers
- retries
- periodic tasks
- locks
- scheduling
- PostgreSQL persistence
- ASGI-friendly integration

It is a plausible choice if `pgmq` proves too low-level and we want a Python-native worker framework without Redis.

Why it is **not** first choice:

1. Supabase already makes `pgmq` available inside our current project.
2. Procrastinate introduces its own task schema/runtime conventions and direct Postgres connection requirements.
3. We already have capability handlers and a `Job` domain model; adopting a full task framework could create duplicate abstractions.
4. The project is maintained, but its repository explicitly says it is looking for additional maintainers, which is a small maintenance-risk signal worth monitoring.

Primary sources:
- https://github.com/procrastinate-org/procrastinate
- https://procrastinate.readthedocs.io/

---

## 3. TaskIQ PostgreSQL

TaskIQ itself is a modern Python task-queue ecosystem. A separate `taskiq-postgresql` plugin offers a PostgreSQL broker/result backend/scheduler with multiple drivers.

The plugin is interesting but currently much smaller/younger than `pgmq` or Procrastinate. Do not make a core reliability primitive depend on it without a stronger maturity audit.

Primary source:
- https://github.com/z22092/taskiq-postgresql

---

## 4. Inngest

Inngest's current Hobby plan is `$0`, with 50k executions, 5 concurrent steps, up to 3 connected workers, and built-in tracing/metrics/queueing. Its Python SDK supports persistent worker connections.

This is a credible product if workflow orchestration becomes substantially more complex than `analysis job -> capability handler`.

Why defer:

- another external control plane and vendor contract
- free-tier limits rather than infrastructure we already own
- duplicates existing `Workflow` / `Job` concepts
- current complexity does not justify replacing Postgres delivery with a workflow SaaS

Revisit if workflows become multi-step durable graphs with waits/events/fan-out where maintaining orchestration logic is a larger cost than the vendor dependency.

Primary sources:
- https://www.inngest.com/pricing
- https://www.inngest.com/docs/setup/connect

---

## 5. Hatchet

Hatchet is an open-source durable task platform with a hosted Developer tier. Current hosted pricing includes the first 100k task runs on the free tier.

It should be considered in the same future category as Inngest: valuable if durable workflow orchestration becomes a product requirement, not as a fix for one polling race.

Primary source:
- https://hatchet.run/pricing

---

## Why not Redis/Celery now

Celery is mature and widely used, but adopting it normally means adding and operating Redis or RabbitMQ (or adopting another hosted broker). That creates:

- another stateful service
- another failure domain
- another security/backup/monitoring surface
- another bill or another workload on the already-constrained Oracle VM

For the current scale, Postgres already has the durability and coordination primitives we need. Redis/Celery becomes justified only if measurements show the DB queue is a bottleneck or Celery-specific ecosystem functionality becomes valuable enough to pay for the complexity.

---

## Bakeoff protocol

### Corpus

Use synthetic no-op/sleep jobs first; do **not** burn MIR CPU merely to test delivery semantics.

Scenarios:

1. 100 queued short jobs, 1 worker
2. 100 queued short jobs, 2 workers
3. 100 queued short jobs, 4 workers
4. consumer crash after claim/read before handler
5. consumer crash after handler side effect but before acknowledgement
6. job cancellation while queued
7. job cancellation while running
8. retryable handler failure
9. permanently failing job
10. long-running job exceeding the initial visibility/lease window

### Metrics

- claim/read latency p50/p95
- DB round trips per job
- duplicate simultaneous deliveries
- replay count after worker crash
- queue drain time
- Postgres CPU/load impact
- queue table growth / archive growth
- complexity in worker code
- operational inspectability

### Acceptance threshold for replacing current delivery

`pgmq` should win on **correctness and simplification**, not merely throughput. A small queue at current product scale does not need exotic performance.

Adopt if it:

- removes hand-written claim contention logic
- preserves/clarifies replay semantics
- makes multi-worker behavior easier to prove
- does not compromise cancellation/progress/domain state
- adds no bill and little operational burden
- works in local Supabase + real-stack CI

Otherwise keep the current table and implement one well-tested `FOR UPDATE SKIP LOCKED` claim function.

---

## What remains invariant regardless of queue choice

Every worker transport must obey the same capability contract:

```text
input:
  job_id
  capability + version
  immutable input artifact/version references
  parameters

output:
  immutable output artifacts/versions
  evidence/provenance
  terminal job status
```

Handlers must assume replay is possible.

That invariant is what lets Oracle, Cloud Run, Modal, or a future worker host consume work without turning the queue provider into product architecture.
