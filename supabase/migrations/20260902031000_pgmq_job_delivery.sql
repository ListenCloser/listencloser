-- Replace Jobs-table polling/leases with one durable PGMQ delivery signal per Job.
--
-- public.jobs remains the product/domain read model. PGMQ owns delivery,
-- visibility, redelivery and acknowledgement. Execution-token fencing remains
-- the product-visible publication authority.

create extension if not exists pgmq;

select pgmq.create('job_delivery');

create or replace function public.enqueue_job_delivery()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  -- A Job is a new logical delivery only when the row is created. Worker retry
  -- reuses the same PGMQ message; user retry creates a new Job row through
  -- JobRepo.retry(), so it naturally receives a new message.
  perform pgmq.send(
    'job_delivery',
    jsonb_build_object('job_id', new.id::text),
    0
  );
  return new;
end;
$$;

revoke all on function public.enqueue_job_delivery() from public;

create trigger jobs_enqueue_pgmq_delivery
after insert on public.jobs
for each row
when (new.stage = 'queued')
execute function public.enqueue_job_delivery();

-- Jobs that were already queued when the migration lands need exactly one
-- transport signal. This runs in the migration transaction, so a failed deploy
-- cannot leave a partial backfill.
select pgmq.send(
  'job_delivery',
  jsonb_build_object('job_id', id::text),
  0
)
from public.jobs
where stage = 'queued';

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
  v_legacy_delay integer;
  v_scan integer;
begin
  if p_worker_id is null or btrim(p_worker_id) = '' then
    raise exception 'worker id is required';
  end if;

  -- Skip stale messages left by deleted/terminal Jobs in the same call so one
  -- poison delivery cannot pin the queue head. The bound prevents an RPC from
  -- becoming an unbounded cleanup loop.
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

    -- Do not create two execution generations for one Job inside the same
    -- process. FencedJobWorker intentionally keeps one active token per local
    -- Job; a different worker may still take over after this short deferral.
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

    -- During the bounded rollout an old worker may have claimed a backfilled
    -- Job before the new worker receives its PGMQ signal. Respect that live
    -- legacy lease instead of manufacturing an overlapping attempt. New PGMQ
    -- attempts always clear lease_expires_at, so this branch disappears with
    -- the follow-up deletion of legacy transport.
    if v_job.stage in ('claimed', 'running')
       and v_job.lease_expires_at is not null
       and v_job.lease_expires_at > clock_timestamp() then
      v_legacy_delay := greatest(
        1,
        ceil(extract(epoch from (v_job.lease_expires_at - clock_timestamp())))::integer
      );
      perform pgmq.set_vt('job_delivery', v_delivery.msg_id, v_legacy_delay);
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

create or replace function public.extend_job_delivery(
  p_job_id uuid,
  p_execution_token uuid,
  p_msg_id bigint,
  p_visibility_seconds integer
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (
    select 1
      from public.jobs
     where id = p_job_id
       and execution_token = p_execution_token
       and stage = 'running'
  ) then
    return false;
  end if;

  perform pgmq.set_vt(
    'job_delivery',
    p_msg_id,
    greatest(1, p_visibility_seconds)
  );
  return true;
end;
$$;

create or replace function public.finish_job_delivery(
  p_job_id uuid,
  p_execution_token uuid,
  p_msg_id bigint,
  p_retry_delay_seconds integer default 0
)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_job public.jobs%rowtype;
begin
  select *
    into v_job
    from public.jobs
   where id = p_job_id
   for update;

  -- Deleting a Job makes its transport message permanently unactionable.
  if not found then
    perform pgmq.archive('job_delivery', p_msg_id);
    return 'archived_missing';
  end if;

  -- A late attempt must never acknowledge or alter visibility for the current
  -- attempt's message. This is the transport equivalent of the #954 publication
  -- fence and is checked in the same transaction as the PGMQ mutation.
  if v_job.execution_token is distinct from p_execution_token then
    return 'stale';
  end if;

  if v_job.stage in ('succeeded', 'failed', 'cancelled') then
    perform pgmq.archive('job_delivery', p_msg_id);
    return 'archived';
  end if;

  if v_job.stage = 'queued' then
    perform pgmq.set_vt(
      'job_delivery',
      p_msg_id,
      greatest(0, p_retry_delay_seconds)
    );
    return 'released';
  end if;

  -- Claimed/running means the attempt did not durably finish. Leave the
  -- message unacknowledged so visibility expiry can redeliver it.
  return 'retained';
end;
$$;

revoke all on function public.receive_job_delivery(text, integer, uuid[]) from public, anon, authenticated;
revoke all on function public.extend_job_delivery(uuid, uuid, bigint, integer) from public, anon, authenticated;
revoke all on function public.finish_job_delivery(uuid, uuid, bigint, integer) from public, anon, authenticated;

grant execute on function public.receive_job_delivery(text, integer, uuid[]) to service_role;
grant execute on function public.extend_job_delivery(uuid, uuid, bigint, integer) to service_role;
grant execute on function public.finish_job_delivery(uuid, uuid, bigint, integer) to service_role;
