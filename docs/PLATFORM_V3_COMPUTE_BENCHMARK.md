# Platform V3 compute benchmark protocol

Last updated: 2026-08-28

Related: #329, #353, #356, #357

## Purpose

Provider discussions should end in measured comparisons, not architecture-by-brand.

This protocol defines the minimum evidence required before moving `listencloser` API or worker compute away from the current Oracle Always Free baseline.

The first target candidate is Google Cloud Run because it accepts ordinary container workloads and has a recurring usage free tier. Azure Container Apps is a useful second serverless-container comparison because Azure currently advertises an always-free allowance of 180,000 vCPU-seconds, 360,000 GiB-seconds, and 2 million requests per month. Specialized ML/GPU providers such as Modal should be evaluated separately because they answer a different question: burst model execution rather than generic application hosting.

## Principles

1. **Same release.** Compare the same Git SHA and, whenever supported, the same OCI image produced by #356.
2. **Same inputs.** Use the same representative fixture/corpus and capability parameters.
3. **No provider SDK in product code.** Provider-specific deployment configuration belongs at the deployment boundary.
4. **Cold and warm measurements are separate.** A scale-to-zero host should not hide cold-start cost inside an average.
5. **Measure user-visible and worker behavior.** Fast `/health` does not prove that a MIR analysis job is usable.
6. **Cost is a benchmark output.** Record monthly free allowance, observed resource use, and estimated cost at current and 10x workload.
7. **Do not cut over merely because a candidate is faster.** Operational complexity and rollback must be included in the decision.

---

## Stage A: external API host probe

`scripts/benchmark_api_host.py` is deliberately provider-neutral and dependency-free.

Example:

```bash
python scripts/benchmark_api_host.py \
  https://api.example.com \
  --label oracle \
  --requests 50 \
  --concurrency 4 \
  --output artifacts/platform/oracle-api.json
```

Run the exact same command against each candidate host.

Default paths:

- `/health/live`
- `/health/ready`

Record:

- success rate
- HTTP status distribution
- min / mean / p50 / p95 / p99 / max latency
- request count and concurrency
- measurement timestamp

The script exits non-zero if any probe fails, which makes it usable in a smoke-test or deployment experiment.

### Cold-start probe

For scale-to-zero candidates:

1. allow the service to become idle according to the provider's documented behavior
2. issue exactly one `/health/live` request
3. record end-to-end latency
4. immediately run the warm probe
5. repeat across at least five cold cycles if practical

Do not mix cold and warm samples into one percentile set.

---

## Stage B: representative job benchmark

The HTTP host probe is necessary but insufficient.

Use the existing canonical real-stack audio fixture(s) and execute representative capabilities through the normal job path.

At minimum measure:

- one transcription/transform job
- one analysis job
- one heavier Analysis V3 candidate when available

For each job capture:

- enqueue timestamp
- worker claim timestamp
- handler start timestamp
- completion timestamp
- queue wait
- handler runtime
- total end-to-end runtime
- success/failure/retry result
- worker CPU/RAM peak where available
- artifact/result equivalence across hosts

#353 should be the canonical in-process telemetry source when merged; do not build a second metrics stack just for this benchmark.

---

## Stage C: concurrency ladder

Run the same representative job at:

```text
1 concurrent job
2 concurrent jobs
4 concurrent jobs
```

Stop increasing concurrency once the host is clearly saturated or the free-tier experiment could incur unbounded cost.

Measure:

- queue drain time
- p50/p95 queue wait
- p50/p95 job runtime
- API readiness/latency during worker load
- failure/retry rate
- CPU/RAM saturation
- database pressure

This tells us whether the current Oracle problem is:

- deployment/build CPU only
- API/worker resource contention
- single-job compute speed
- lack of horizontal worker capacity
- database/queue coordination

Those lead to different fixes.

---

## Stage D: worker failure semantics

Every candidate must pass the same reliability scenarios:

1. worker dies after delivery/claim, before handler starts
2. worker dies during handler
3. handler succeeds but worker dies before final acknowledgement/status update
4. retryable handler failure
5. permanently failing handler
6. queued cancellation
7. running cancellation
8. deployment while a job is active

The expected application contract is **at-least-once execution with replay-safe/idempotent handlers** unless a specific handler can prove stronger transactional semantics.

A platform's marketing claim of “exactly once” delivery must not be interpreted as exactly-once product side effects.

---

## Stage E: cost normalization

For each candidate record two numbers:

### Current workload

Estimate from actual measurements, not provider calculators alone.

```text
monthly API requests
monthly API vCPU-seconds
monthly worker vCPU-seconds
monthly memory GiB-seconds
monthly jobs
storage/egress attributable to compute host
estimated monthly charge after free allowance
```

### 10x workload

Apply the same workload shape at 10x volume to expose pricing cliffs.

The preferred candidate at current scale is not necessarily the preferred candidate at 10x.

---

## Candidate-specific experiments

### Oracle Always Free — baseline

Oracle remains the reference because it provides scarce indefinite always-on general-purpose free VM compute.

Measure it **after #356** so image building no longer contaminates deployment/resource observations.

Key questions:

- Does removing on-host builds materially improve deployment reliability/time?
- What is one representative job's CPU wall time?
- Does one CPU-heavy worker noticeably degrade API latency?
- Can API and worker containers be assigned useful resource limits on the existing VM?
- Is concurrency 2 already slower than serial execution because of CPU saturation?

### Google Cloud Run — first generic container candidate

Use the same OCI release where possible.

Test API hosting first, with scale-to-zero/request-based billing. Then test a bounded job execution path separately rather than assuming an HTTP service is also the right durable worker.

Do not migrate Supabase, storage, auth, or the frontend as part of this experiment.

### Azure Container Apps — second generic serverless-container candidate

Azure currently advertises an always-free monthly Container Apps allowance of:

- 180,000 vCPU-seconds
- 360,000 GiB-seconds
- 2 million requests

This is interesting enough to benchmark if Cloud Run is unsatisfactory, but there is no benefit in running both experiments simultaneously before the first yields evidence.

### Google Compute Engine e2-micro — fallback VM comparison

Google's recurring free tier currently includes one non-preemptible `e2-micro` VM in eligible US regions. This is useful as an availability/portability fallback, but its small machine class is unlikely to outperform Oracle for CPU-heavy MIR.

Do not migrate merely because it is another indefinite-free VM; benchmark the actual job.

### Modal — specialized model-compute candidate

Do not compare Modal to Oracle using `/health` latency. Compare a **specific capability**:

```text
input artifact -> engine invocation -> output artifact/evidence
```

Examples:

- source separation
- embedding extraction
- audio-language inference
- large transcription model

Measure quality as well as latency/cost. A faster model with worse musical evidence is not a platform win.

---

## Decision table template

| Metric | Oracle | Candidate A | Candidate B |
|---|---:|---:|---:|
| Git SHA / image digest | | | |
| Warm API p50 | | | |
| Warm API p95 | | | |
| Cold start p50 | n/a | | |
| Representative job runtime | | | |
| Queue wait @ 2 jobs | | | |
| Queue wait @ 4 jobs | | | |
| API p95 during worker load | | | |
| Peak RAM | | | |
| Failure/replay scenarios passed | | | |
| Current monthly estimate | `$0` | | |
| 10x monthly estimate | | | |
| Operational steps | | | |
| Rollback complexity | | | |

## Migration gate

A candidate should replace Oracle production compute only when:

- it wins a measured user-facing or reliability bottleneck
- the expected current workload remains within the intended `$0` envelope, or the user explicitly accepts spend
- the deployment remains portable and reversible
- job semantics remain correct
- observability is at least equivalent
- the migration does not drag unrelated state/frontend services with it

Until then, the benchmark result is research evidence, not a migration mandate.
