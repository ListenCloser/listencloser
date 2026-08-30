# PGMQ worker-equivalence and deletion gate

Issue: #651. Related correctness owner: #539.

This document is the decision-oriented continuation of the already-merged PGMQ evidence from #359 and #360. It does not repeat those experiments and it does not enable PGMQ in production.

## Existing evidence we reuse

The repository already has executable evidence that:

- PGMQ consumers do not suffer the old select-then-conditional-claim queue-head collision under the tested concurrent-consumer contract;
- an unacknowledged message becomes visible again after its visibility timeout and increments `read_ct`;
- a `{job_id}` PGMQ signal can be emitted in the same PostgreSQL transaction as authoritative Job creation/requeue, including rollback atomicity.

#367 fixed the immediate queue-head contention by shipping `claim_next_job()` with `FOR UPDATE SKIP LOCKED`. That was a valid throughput fix. #651 asks a different question: whether PGMQ can now delete generic queue control-plane code while keeping `jobs` as the product/domain read model.

## Current production queue contract inventory

| Concern | Current production owner | PGMQ target / retained product owner |
| --- | --- | --- |
| durable Job status/audit | `public.jobs` | **KEEP `public.jobs`** |
| enqueue identity | Job row enters `queued` | Job mutation + transactional `{job_id}` queue signal |
| oldest-job claim | `public.claim_next_job()` / `FOR UPDATE SKIP LOCKED` | PGMQ `read()` |
| specific conditional claim | `JobWorker._claim_job()` | normally unnecessary for delivery; retain only if a real product/debug caller exists |
| lease duration | `lease_expires_at` + worker configuration | PGMQ visibility timeout |
| lease renewal | `JobWorker._renew_lease()` heartbeat | PGMQ `set_vt()` |
| crashed-worker recovery | `JobWorker._recover_orphans()` | visibility expiry + redelivery |
| periodic orphan scan | worker main-loop recovery timer | delete if PGMQ cutover succeeds |
| delivery attempt count | Job retry/requeue bookkeeping | PGMQ `read_ct` as delivery-attempt evidence; product retry policy may still be recorded on Job |
| retry delay | worker sleep/backoff + Job requeue | visibility extension/delayed re-visibility; max retries remains product policy |
| acknowledgement | Job terminal mutation implicitly removes it from queue eligibility | PGMQ archive/delete after successful fenced commit |
| concurrent delivery | custom claim RPC + leases | PGMQ visibility semantics |
| queue depth / oldest age | repository-owned Job queries/health logic | PGMQ `metrics()` for transport; product Job health can remain where useful |
| worker liveness | `worker_heartbeats` + health file | **KEEP**; this is operational worker state, not message delivery |
| cancellation | Job domain stage + worker/handler checks | **KEEP as Job semantics**; worker archives a cancelled delivery without executing, and in-flight cooperative cancellation remains product behavior |
| progress | fenced Job update by current worker/stage | **KEEP as Job semantics**, later fenced by attempt identity rather than delivery lease machinery |
| cache/idempotency | Job cache key + handler replay-safe behavior | **KEEP**; at-least-once delivery remains |
| stale-attempt side effects | job-row writes use worker/stage checks, but handler persistence can outlive ownership (#539) | fresh attempt token per delivery + fenced authoritative persistence boundary |

## Remaining bakeoff implemented here

`scripts/pgmq_worker_equivalence.py` creates only uniquely named scratch tables and a basic logged PGMQ queue on a local/disposable Postgres instance.

It verifies the decision-critical behavior not already covered by #359/#360:

1. `set_vt()` extends visibility for a long-running attempt;
2. successful work can be archived instead of left in the active queue;
3. PGMQ exposes queue length/age/total-message metrics without a repository-owned queue scan;
4. worker A receives delivery attempt 1;
5. its visibility expires without acknowledgement;
6. worker B receives the same message as attempt 2;
7. B installs a fresh execution token on the Job read model;
8. A's late publication is rejected by one fenced commit boundary;
9. B can publish the authoritative output and finish the Job;
10. the message is archived only after the current attempt commits.

The scratch output table has one logical output per Job. The publication CTE first proves `{job_id, attempt_token, stage=running}` ownership and only then inserts the authoritative output and marks the Job succeeded. This models the generic contract #539 needs without changing any production handler or migration in this evaluation PR.

## What this proves — and what it does not

A green test proves that PGMQ redelivery is compatible with a small attempt-token fencing contract. It does **not** prove the current production handlers are already fenced. #539 remains the production correctness gate: all product-visible persistence paths must use the fenced boundary or be explicitly proven intrinsically idempotent before the old lease/orphan transport is deleted.

PGMQ still provides at-least-once processing across visibility expiry. The phrase "exactly once within a visibility timeout" describes concurrent delivery visibility, not globally exactly-once capability side effects.

## Complexity/deletion accounting if adopted

A production cutover should be considered a simplification only if it actually deletes the generic machinery below rather than keeping two queue systems:

### Delete or substantially collapse

- `JobWorker._claim_next_job()` transport logic;
- `public.claim_next_job()` and its queue-specific migration/function contract;
- `JobWorker._claim_job()` if no durable non-queue caller remains;
- Job lease expiry as the delivery mechanism;
- `JobWorker._renew_lease()` delivery heartbeat;
- `JobWorker._recover_orphans()`;
- periodic orphan-recovery scheduling;
- transport-level requeue mechanics that only recreate visibility/redelivery;
- custom queue-depth/oldest-age queries where `pgmq.metrics()` is sufficient.

### Keep because it is product/operational logic

- `public.jobs` / Workflow status and audit history;
- capability routing and execution;
- progress and user-visible status;
- cancellation semantics;
- maximum retry / terminal-failure product policy;
- cache/idempotency semantics;
- worker liveness heartbeat/health file;
- release/provenance/observability;
- attempt fencing and safe output publication.

The migration fails the simplification test if a PGMQ adapter is added while most lease/orphan/claim machinery remains indefinitely.

## Cost, portability, and exposure

Target production shape:

- **basic/logged PGMQ queue**, not an unlogged queue;
- same existing Postgres/Supabase topology; no Redis/Celery/SQS/Temporal/Kafka;
- service-side worker access only; do not expose the queue through the browser/Data API;
- no new external queue service or runtime daemon;
- PostgreSQL-native/open-source PGMQ keeps the transport portable to compatible self-hosted Postgres if provider needs change.

## Decision gate

If the fresh local-Supabase integration tests in this PR pass, the architectural direction is:

**ADOPT PGMQ as the preferred delivery transport, while retaining `public.jobs` as the product/domain read model.**

Production cutover/removal should wait for both:

1. the shared migration/deployment lane to be clear; and
2. #539's fenced persistence boundary to cover real production side effects.

Then migrate one path, run two-worker crash/takeover + real-stack evidence, and delete the superseded claim/lease/orphan transport rather than preserving it as a fallback.
