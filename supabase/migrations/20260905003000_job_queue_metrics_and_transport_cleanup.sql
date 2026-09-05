-- #651: finish the bounded PGMQ rollout.
--
-- PGMQ is now the only production delivery authority. Expose its own metrics to
-- the service-role health endpoint, remove the overlap shim that respected
-- Jobs-table leases during rollout, and delete the superseded custom claim RPC.

create or replace function public.job_queue_metrics()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'queue_ready', true,
    'queue_depth', metrics.queue_length,
    'queue_visible_depth', metrics.queue_visible_length,
    'oldest_age_seconds', metrics.oldest_msg_age_sec,
    'total_messages', metrics.total_messages,
    'sampled_at', metrics.scrape_time
  )
  from pgmq.metrics('job_delivery') as metrics;
$$;

revoke all on function public.job_queue_metrics() from public, anon, authenticated;
grant execute on function public.job_queue_metrics() to service_role;

create or replace function public.receive_job_delivery(
  p_worker_id text,
  p_visibility_seconds integer,
  p_in_flight_job_ids uuid[] default '{}'::uuid[]
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_delivery pgmq.message_record;
  v_job public.jobs%rowtype;
  v_job_id uuid;
  v_visibility integer := greatest(1, p_visibility_seconds);
  v_scan integer;
begin
  if p_worker_id is null or btrim(p_worker_id) = '' then
    raise exception 'worker id is required';
  end if;

  -- Skip permanently unactionable messages in the same call so one stale
  -- delivery cannot pin the queue head. Keep the cleanup bounded.
  for v_scan in 1..32 loop
    select *
      into v_delivery
      from pgmq.read('job_delivery', v_visibility, 1)
      limit 1;

    if not found then
      return null;
    end if;

    begin
      v_job_id := (v_delivery.message ->> 'job_id')::uuid;
    exception
      when invalid_text_representation or null_value_not_allowed then
        perform pgmq.archive('job_delivery', v_delivery.msg_id);
        continue;
    end;

    -- One process never starts two local generations for the same Job. Across
    -- processes PGMQ visibility plus the execution-token fence own takeover.
    if v_job_id = any(coalesce(p_in_flight_job_ids, '{}'::uuid[])) then
      perform pgmq.set_vt('job_delivery', v_delivery.msg_id, 1);
      continue;
    end if;

    select *
      into v_job
      from public.jobs
      where id = v_job_id
      for update;

    if not found then
      perform pgmq.archive('job_delivery', v_delivery.msg_id);
      continue;
    end if;

    if v_job.stage in ('succeeded', 'failed', 'cancelled') then
      perform pgmq.archive('job_delivery', v_delivery.msg_id);
      continue;
    end if;

    if v_job.stage not in ('queued', 'claimed', 'running') then
      perform pgmq.archive('job_delivery', v_delivery.msg_id);
      continue;
    end if;

    update public.jobs
       set stage = 'claimed',
           worker_id = p_worker_id,
           lease_expires_at = null,
           execution_token = gen_random_uuid()
     where id = v_job_id
     returning * into v_job;

    return to_jsonb(v_job) || jsonb_build_object(
      '_queue_msg_id', v_delivery.msg_id,
      '_queue_read_ct', v_delivery.read_ct,
      '_queue_vt', v_delivery.vt
    );
  end loop;

  return null;
end;
$$;

revoke all on function public.receive_job_delivery(text, integer, uuid[])
  from public, anon, authenticated;
grant execute on function public.receive_job_delivery(text, integer, uuid[])
  to service_role;

drop function if exists public.claim_next_job(text, double precision);
