-- Atomically claim the oldest queued job without queue-head collisions.
-- Delivery remains at-least-once: expired leases are recovered and handlers must
-- remain replay-safe/idempotent.
begin;

create or replace function public.claim_next_job(
  p_worker_id text,
  p_lease_seconds double precision default 30.0
)
returns setof public.jobs
language sql
security invoker
set search_path = ''
as $$
  with next_job as (
    select id
    from public.jobs
    where stage = 'queued'
    order by created_at, id
    for update skip locked
    limit 1
  )
  update public.jobs as jobs
  set stage = 'claimed',
      worker_id = p_worker_id,
      lease_expires_at = clock_timestamp()
        + greatest(p_lease_seconds, 0.001) * interval '1 second'
  from next_job
  where jobs.id = next_job.id
    and jobs.stage = 'queued'
  returning jobs.*;
$$;

revoke all on function public.claim_next_job(text, double precision) from public;
revoke all on function public.claim_next_job(text, double precision) from anon;
revoke all on function public.claim_next_job(text, double precision) from authenticated;
grant execute on function public.claim_next_job(text, double precision) to service_role;

commit;
