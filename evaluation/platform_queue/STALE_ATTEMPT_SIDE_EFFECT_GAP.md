# Stale-attempt product-side-effect gap (#539)

This is a bounded before-state characterization for the worker fencing problem. It does not change queue semantics or propose exactly-once execution.

## What is already fenced

`JobWorker` lifecycle writes are conditional on the current `worker_id` and Job stage:

- claimed → running;
- lease renewal;
- progress through `JobWorker.update_progress()`;
- success/failure/requeue.

After a genuine cross-worker takeover, a stale worker's later Job-row updates no longer match. That is useful, but it is not an output-commit fence.

## What is not fenced today

Capability handlers receive `handler(job, client)`. The `Job` records the logical execution and retry count, but not one claim/takeover generation. The service-role client can still perform product-visible persistence after another worker owns the Job.

The production output paths inspected for this slice include:

| Path | Product-visible writes | Existing replay aid | Stale-attempt gap |
| --- | --- | --- | --- |
| common capability helpers | Artifact + Version; Entity/Insight/Alignment helpers | `produced_by_job_id`; retry-scoped storage key | output repositories do not assert current execution ownership |
| transcription / score / correction family | immutable storage objects plus Artifact/Version rows; correction also replaces note Entities | storage keys include Job/retry identity; rows point to producing Job | stale attempt can create a new output graph after takeover |
| `audio_structure` / `analyze` | measured/derived Entity and Insight rows associated with a Version | `produced_by_job_id` where modeled | no per-claim identity at persistence boundary |
| corrected-MIDI entity sync | delete + recreate note Entities for the produced Version | deterministic source MIDI | stale correction attempt can mutate an output Version's entity world |
| `perceptual_series` | storage object + Artifact + Version | Job/retry-scoped storage key; immutable Version | Artifact/Version publication is not current-attempt fenced |

Storage writes alone are less dangerous than durable row publication: private blobs are not part of the product graph until an Artifact/Version or other durable record points at them. They can be orphan-cleaned. The critical invariant is therefore **which attempt is allowed to make durable product rows authoritative**.

## Executable characterization

`backend/tests/integration/test_stale_attempt_side_effects.py` uses the real disposable Supabase schema, real `JobWorker` lease/recovery methods, and the normal `_create_output_version()` production helper:

1. worker A claims and starts a Job;
2. A's lease is forced expired;
3. worker B performs normal orphan recovery, claims the same Job, and starts it;
4. B is now the authoritative worker in `public.jobs`;
5. stale worker A creates a new Artifact/Version through the normal production persistence path;
6. A's later `_mark_succeeded()` does not change the Job, proving Job-row fencing works;
7. the stale Version nevertheless exists and is tagged `produced_by_job_id = job_id`, proving the remaining product-side-effect gap.

The test intentionally asserts this unsafe before-state. The production #539 fix should invert the output assertion rather than preserving the characterization forever.

## Smallest plausible production contract

The evidence points toward one generic execution identity and publication fence, not handler-specific polling:

```text
claim / PGMQ delivery
  -> fresh execution_token
  -> Job execution context carries {job_id, execution_token}
  -> expensive DSP/model/storage work may run without a long DB transaction
  -> durable product publication verifies execution_token is still current
  -> current attempt commits rows and terminal Job state
  -> stale attempt fails publication
```

A robust implementation should prefer the existing common repository/output boundaries over checks scattered through detectors. The exact schema/API is intentionally not selected in this characterization PR.

Important constraints for the implementation:

- token changes on every successful claim/takeover, including same-process re-delivery;
- do not use `worker_id` alone as the attempt identity;
- no transaction is held across model inference or DSP;
- no DB poll on every inner processing operation;
- private stale storage blobs may be cleaned asynchronously, but stale durable output rows must not become authoritative;
- intrinsic uniqueness/idempotency remains complementary to fencing;
- preserve at-least-once recovery and legitimate retries.

## Relation to PGMQ

PGMQ visibility/redelivery does not remove this problem. The #651 worker-equivalence bakeoff demonstrates that a fresh attempt token can fence a late stale publication after redelivery. This characterization proves why the equivalent contract is required on the real production persistence path before the old queue control plane is deleted.
