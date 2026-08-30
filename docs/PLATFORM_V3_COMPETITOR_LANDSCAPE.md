# Platform V3 competitor landscape

Last verified: 2026-08-28

Related: #329, #283, #356

## Decision in one page

`listencloser` should **not** migrate the whole stack to AWS or another single provider merely to look more conventional. Under the current hard `$0/month` baseline, the existing Vercel + Supabase + Oracle topology remains unusually strong, provided we make the application portable at the contracts that matter.

The near-term recommendation is:

1. **Keep Oracle Always Free for the production API + durable CPU worker** while it remains adequate.
2. **Keep Supabase Free for Postgres/Auth/Storage** rather than fragmenting the state layer.
3. **Keep Vercel Hobby only while the deployment remains eligible for Vercel's non-commercial personal-use restriction.** Treat this as a commercial-launch migration/upgrade trigger, not a reason to move today.
4. **Use GitHub Actions + GHCR as the portable build/release boundary** (#356) so Oracle is only a container host.
5. **Use Google Cloud Run as the first generic OCI/container experiment** when we need bursty API/job capacity beyond Oracle.
6. **Use Modal as the first specialized ML/GPU burst-compute experiment** when an evaluated MIR/model capability materially benefits from faster CPU/GPU hardware.
7. **Keep Cloudflare R2 as a storage/egress pressure-release option**, not as another dependency today.
8. Do not add Redis/Celery/SQS/Kubernetes merely because another hosting provider makes them easy. Keep the Postgres job contract until measured concurrency or reliability evidence requires a different queue.

This separates two questions that are easy to conflate:

- **free production baseline**: can the service stay online continuously at $0?
- **free experiment capacity**: can we borrow useful burst compute/GPUs at $0 without making it production-critical?

Oracle is currently strongest at the first. Cloud Run and Modal are stronger at the second.

---

## Evaluation criteria

Every candidate is evaluated against the actual `listencloser` workload rather than generic PaaS popularity:

- perpetual `$0` feasibility, not introductory credits alone
- production suitability of the free tier
- FastAPI / OCI container fit
- long-running background-worker fit
- CPU available for MIR/transcription/separation
- GPU path for future models
- scale-to-zero / burst economics
- architecture portability and exit cost
- operational complexity
- compatibility with Supabase Postgres/Auth/Storage
- ability to run API and workers independently

`$0` does not mean “never use a service that has billing.” It means the baseline must be deliberately bounded so normal development and low-volume operation do not require monthly spend.

---

## Compute / backend competitors

| Provider | Current free position | API fit | durable worker fit | GPU path | portability | Decision |
|---|---|---:|---:|---:|---:|---|
| **Oracle Cloud Always Free** | Always Free VM resources for life of account within limits; current docs describe up to two E2 micro VMs and Ampere allowance equivalent to 2 OCPU / 12 GB total | Good | **Good** | Poor | **High** with OCI images | **KEEP baseline** |
| **Google Cloud Run** | Monthly free usage for services/jobs; usage-billed and scale-to-zero | **Excellent** | Good for Jobs; always-on workers are not inherently free | No general GPU-free baseline | **High** | **FIRST generic compute experiment** |
| **Modal** | Starter `$0` plus `$30/month` included compute; 100 containers / 10 GPU concurrency currently advertised | Good, but Python/Modal-native | **Excellent for burst jobs** | **Excellent** | Medium | **FIRST ML/GPU experiment** |
| **Northflank** | Free Sandbox: 2 services, 2 jobs, 1 addon; docs explicitly say not production | Good | Good for experiments | Good paid path | High | **EXPERIMENT only** |
| **Render** | Free web service; 750 free instance-hours/workspace; spins down; docs explicitly say not production | Fair | Free background worker unavailable | Paid | High | **REJECT for core worker** |
| **Koyeb** | One free web instance: 0.1 vCPU / 512 MB / 2 GB; cannot be Worker Service; docs say not production | Weak for this backend | **No** on free tier | Paid | High | **REJECT for MIR worker** |
| **Railway** | Free plan currently provides only `$1/month` resource credit after trial | Good | Good if paid | Limited / evolving | High | **REJECT under hard $0** |
| **Fly.io** | Official docs: no free account/free tier; tiny trial only | Good | Good | Paid | High | **REJECT under hard $0** |
| **AWS** | New-customer free plan is up to `$200` credits and at most 6 months; some always-free services remain | Excellent | Excellent | Excellent | Medium-high | **DEFER whole-stack migration** |
| **Runpod** | Usage-priced CPU/GPU; no perpetual free baseline | Not primary API target | Excellent burst GPU | **Excellent** | Medium | **Paid GPU fallback later** |

### Oracle: why it remains valuable

Oracle's current Always Free documentation still provides something most competitors no longer do: general-purpose VM compute free for the life of the account. That makes it valuable even if its CPU is slow. The correct response to slow deployment/runtime is to make Oracle a replaceable execution target, not to discard scarce free compute prematurely.

#356 moves image building out of Oracle. The next scaling work should make workers safe to replicate. Once those boundaries exist, Oracle can later become staging, low-priority batch, or fallback compute without changing application semantics.

Primary source:
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm

### Google Cloud Run: best generic escape hatch

Cloud Run is the strongest first portability experiment because it consumes ordinary containers, supports services and Jobs, bills by usage, and has a monthly free allowance. It is much closer to our target deployment abstraction than an AWS-wide redesign.

Current Cloud Run pricing documents a Jobs free tier of 240,000 vCPU-seconds and 450,000 GiB-seconds per month (free-tier application and exact service billing vary by execution/billing mode and region). A low-volume HTTP API that can scale to zero is therefore plausible at `$0`; a continuously running worker should be assumed paid once it exceeds the monthly allowance.

Use Cloud Run when we need to answer a concrete question such as:

- Can the exact #356 OCI artifact serve FastAPI with materially better p95 latency than Oracle?
- Can a bounded background job complete substantially faster without maintaining another VM?
- What is the cost per representative analysis job after free allowance?

Do **not** migrate until the same representative corpus/job is measured on both Oracle and the candidate.

Primary source:
- https://cloud.google.com/run/pricing

### Modal: strongest free burst-ML complement

Modal is not a generic drop-in OCI host, so it has more provider coupling than Cloud Run. But its economics are unusually relevant to `listencloser`: the Starter plan currently advertises `$30/month` of included compute, up to 100 containers and 10 concurrent GPUs, with scale-to-zero endpoints.

That makes Modal a strong research/production-candidate boundary for capabilities such as:

- source separation
- embedding extraction
- audio-language inference
- larger transcription models
- occasional GPU-backed analysis

The architecture rule is that a Modal function must sit **behind an engine/capability interface** and consume/produce ordinary artifacts. Core workflows must not become Modal-specific.

Primary sources:
- https://modal.com/pricing
- https://modal.com/docs/guide/endpoints

### Northflank: useful portability proof, not a free production answer

Northflank's free Sandbox is generous enough to test our API/worker split: 2 services, 2 jobs and 1 addon/database, with always-on compute. However, its own documentation says the free tier should not be used for production applications.

That makes it useful only if we want a second generic-container portability proof after #356. Cloud Run is higher priority because its usage-based free tier has a clearer path to legitimate low-volume production.

Primary sources:
- https://northflank.com/docs/v1/application/billing/pricing-on-northflank
- https://northflank.com/pricing

### Render / Koyeb / Railway / Fly.io

These are good developer platforms in general, but their current free economics do not beat our Oracle baseline for CPU-heavy music work:

- Render explicitly labels free services non-production, spins them down after idle, and does not provide free background workers.
- Koyeb's free instance is 0.1 vCPU / 512 MB and cannot be used as a Worker Service.
- Railway's ongoing Free plan is currently only `$1/month` of resource credit after its trial.
- Fly.io explicitly states that there is no free account/free tier.

Primary sources:
- https://render.com/docs/free
- https://www.koyeb.com/docs/reference/instances
- https://docs.railway.com/pricing/free-trial
- https://docs.railway.com/pricing/plans
- https://fly.io/docs/about/cost-management/

### AWS: production-standard, but not the zero-cost answer

AWS is a reasonable future destination when scale, security controls, organizational needs, or committed spend justify it. It is not a reason to rewrite today's platform.

For new customers, AWS's current Free plan is an introductory program: up to `$200` in credits and up to 6 months. AWS also has always-free offers for some services, but the general-purpose application/worker path should not be treated as an Oracle-like indefinitely free compute replacement.

An AWS migration would also introduce an unnecessary bundle of decisions (ECR, ECS/Fargate or EC2, IAM, networking, load balancing, logging, queueing, budgets) before the application needs them.

Primary source:
- https://aws.amazon.com/free/free-tier-faqs/

### Runpod: later paid GPU fallback

Runpod is attractive when GPU throughput itself becomes the bottleneck, but current serverless GPU usage is paid. It belongs in a later benchmark against Modal and other GPU providers once a production capability has demonstrated that GPU acceleration is worth real money.

Primary source:
- https://www.runpod.io/pricing

---

## Frontend / edge competitors

| Provider | Free position | Relevant constraint | Decision |
|---|---|---|---|
| **Vercel Hobby** | `$0` | Officially restricted to **non-commercial personal use** | **KEEP pre-commercial; explicit launch trigger** |
| **Netlify Free** | `$0`, 300-credit hard monthly limit | Workloads pause when credits are exhausted | **WATCH as frontend escape hatch** |
| **Cloudflare Pages + Workers Free** | Static asset requests free/unlimited; Functions share Workers quota | Workers Free currently has 100k requests/day but only 10 ms CPU/invocation | **WATCH for frontend/edge, not MIR** |

Vercel remains the best fit for the current Next.js frontend because it removes deployment/CDN/preview friction. But the commercial-use restriction is a real architecture constraint: before `listencloser` becomes a commercial SaaS, either upgrade Vercel or benchmark/migrate the frontend.

This is a **launch checklist item**, not an immediate infrastructure project.

Primary sources:
- https://vercel.com/docs/plans/hobby
- https://vercel.com/docs/limits/fair-use-guidelines
- https://www.netlify.com/pricing/
- https://developers.cloudflare.com/pages/functions/pricing/
- https://developers.cloudflare.com/workers/platform/limits/

---

## Database / auth competitors

| Provider | Free position | What we gain | What we lose | Decision |
|---|---|---|---|---|
| **Supabase Free** | 500 MB DB/project, 2 free projects; no automatic backups; inactive projects can pause | Postgres + Auth + Storage + RLS + one operational surface | Current free storage/DB limits | **KEEP** |
| **Neon Free** | 100 CU-hours/project/month, 0.5 GB/project, scale-to-zero, Auth included | Excellent serverless Postgres/branching economics | No equivalent integrated object-storage product in this architecture | **WATCH DB-only** |
| **Firebase Spark** | Free quotas available | Mature managed ecosystem | Non-Postgres data model and major rewrite | **REJECT migration** |

Neon is a legitimate Postgres competitor, but replacing Supabase today would solve no demonstrated problem while splitting Auth/DB/storage responsibilities. The lower-lock-in strategy is to keep ordinary SQL/migrations and thin auth/storage boundaries so a future move is possible.

Primary sources:
- https://supabase.com/pricing
- https://neon.com/pricing

---

## Object-storage competitor

Cloudflare R2 deserves a specific watch item because music artifacts can make storage and egress limits matter before Postgres does.

Current Standard-storage free tier:

- 10 GB-month storage/month
- 1 million Class A operations/month
- 10 million Class B operations/month
- no internet egress charge
- S3-compatible APIs / presigned requests

This is materially more free object-storage headroom than the current Supabase free allocation. However, adding R2 now would create another state provider before we need it.

**Trigger:** benchmark R2 when Supabase Storage capacity/egress becomes a recurring constraint or when direct artifact delivery cost becomes a meaningful part of the paid plan.

Primary source:
- https://developers.cloudflare.com/r2/pricing/

---

## Recommended target topology

### Phase 0 — current `$0` baseline

```text
Browser
  -> Vercel Next.js
  -> FastAPI container on Oracle Always Free

FastAPI / worker
  -> Supabase Auth/Postgres/Storage
  -> Postgres jobs table

GitHub Actions
  -> test
  -> build immutable OCI image
  -> GHCR
  -> Oracle pulls exact artifact
```

### Phase 1 — portable burst compute, still targeting `$0`

```text
                     +-> Oracle CPU worker (baseline)
Postgres jobs ------+-> Cloud Run Job (generic burst experiment)
                     +-> Modal engine (ML/GPU experiment)

All paths:
  input = stable artifact reference + capability parameters
  output = stable artifact/evidence contract
```

This must not become three implicit production schedulers. Candidate providers stay behind explicit capability/worker boundaries until benchmark evidence selects a production route.

### Phase 2 — paid only after a trigger

Possible future topology:

```text
Vercel/other FE
       |
managed API containers
       |
Postgres + object storage
       |
queue
  +----+----+
 CPU      GPU
workers  workers
```

AWS, GCP, Modal, Runpod, or another provider can supply individual boxes in that diagram without changing product-domain semantics.

---

## Migration triggers

Do not migrate based on provider aesthetics. Revisit a boundary when one of these is true:

| Boundary | Concrete trigger |
|---|---|
| Oracle API | sustained unacceptable API p95/p99 after deployment-build work is removed, or API contention with worker remains material after process separation |
| Oracle worker | representative jobs have unacceptable queue wait/runtime, or concurrency >1 causes sustained resource saturation |
| Postgres queue | atomic DB claim + indexed polling becomes a measurable DB bottleneck or operational semantics require features Postgres cannot provide cheaply |
| Vercel | commercial launch makes Hobby ineligible, or real Next.js hosting cost/restrictions exceed alternatives |
| Supabase DB | storage/compute/connection/backup requirements exceed free tier and competitor TCO is materially better than upgrading |
| Supabase Storage | artifact capacity or egress becomes a measured constraint |
| CPU -> GPU | an evaluated model materially improves product quality and GPU acceleration has favorable quality/latency/cost per analysis |
| single worker class | capabilities have clearly different CPU/RAM/GPU/runtime characteristics and shared scheduling harms throughput |

Required evidence for a compute migration:

- same immutable release/artifact where technically possible
- same representative input corpus
- cold + warm latency
- wall-clock job runtime
- CPU/RAM/GPU use
- queue wait under 1/2/4 concurrent jobs
- failure/retry behavior
- estimated monthly cost at current usage and 10x usage
- operational steps and rollback path

---

## Lock-in policy

The product should use managed services aggressively while keeping replaceable contracts:

- **compute:** OCI image or capability adapter
- **database:** PostgreSQL + checked-in migrations
- **auth:** standard JWT/OIDC boundary; provider code isolated
- **storage:** artifact-storage adapter + signed upload/download contract
- **queue:** queue interface separate from capability handlers
- **observability:** OpenTelemetry
- **models:** engine protocol + versioned artifact/provenance

Do not introduce cloud-specific business logic into domain handlers.

This means vendor diversity is not itself a problem. An unnecessary middleman is a service that adds no product/operational value; a managed service that removes meaningful operational work is useful even when it is a different vendor.

---

## What not to build now

- whole-stack AWS migration
- Kubernetes / EKS / GKE
- Kafka
- Redis/Celery merely to appear production-grade
- self-hosted Supabase
- home-grown object storage
- multi-cloud active/active deployment
- generic provider abstraction over every possible cloud primitive
- a GPU fleet before an evaluated production capability needs one
- a second observability stack alongside the existing OTEL/Grafana/Sentry path

---

## Bounded next experiments

1. **Land #356** and verify one real Oracle release pulls the CI-built image rather than rebuilding.
2. **Harden the Postgres queue for multiple workers** with a DB-side atomic claim and at-least-once/idempotent semantics.
3. **Use #353 telemetry** to establish Oracle API/job baselines rather than creating another metrics implementation.
4. Run a representative `1 / 2 / 4` concurrent-job Oracle load probe.
5. If Oracle is materially limiting the API, deploy the **same OCI image** to Cloud Run as a non-production benchmark.
6. If an Analysis V3 model needs burst acceleration, implement a **single capability adapter** on Modal and compare quality/latency/cost against Oracle CPU.
7. Revisit R2 only when real artifact storage/egress data says Supabase Storage is the constraint.

The default remains: **measure first, keep `$0`, and pay only at a boundary whose value we can quantify.**
