\set ON_ERROR_STOP on

do $$
declare
  required_columns text[] := array[
    'id', 'workflow_id', 'capability_name', 'capability_version', 'stage',
    'progress', 'status_message', 'worker_id', 'lease_expires_at',
    'retry_count', 'max_retries', 'input_version_ids', 'output_version_ids',
    'parameters', 'cache_key', 'error_message', 'error_details', 'provenance',
    'started_at', 'completed_at', 'created_at', 'created_by'
  ];
  missing_columns text[];
begin
  if to_regclass('public.jobs') is null then
    raise exception 'public.jobs is missing';
  end if;
  if to_regclass('public.worker_heartbeats') is null then
    raise exception 'public.worker_heartbeats is missing';
  end if;
  select array_agg(required.column_name)
    into missing_columns
  from unnest(required_columns) as required(column_name)
  where not exists (
    select 1 from information_schema.columns c
    where c.table_schema = 'public'
      and c.table_name = 'jobs'
      and c.column_name = required.column_name
  );
  if missing_columns is not null then
    raise exception 'public.jobs missing columns: %', missing_columns;
  end if;
  if not exists (
    select 1 from pg_type t join pg_enum e on e.enumtypid = t.oid
    where t.typname = 'job_stage' and e.enumlabel = 'running'
  ) then
    raise exception 'job_stage enum is incompatible';
  end if;
  if not exists (
    select 1 from pg_indexes
    where schemaname = 'public' and tablename = 'jobs'
      and indexdef ilike '%unique%cache_key%'
  ) then
    raise exception 'jobs cache-key uniqueness is missing';
  end if;
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'jobs'
      and policyname = 'jobs owner select'
  ) then
    raise exception 'jobs owner select policy is missing';
  end if;
  if not exists (
    select 1 from storage.buckets where id = 'artifacts' and public = false
  ) then
    raise exception 'private artifacts bucket is missing';
  end if;
end $$;

-- Null confidence is an intentional domain contract (heuristic insights store
-- NULL). A NOT NULL default of 1.0 would silently invent confidence and was
-- the source of the production "confidence not-null" regression.
do $$
begin
  if not exists (
    select 1 from information_schema.columns c
    where c.table_schema = 'public'
      and c.table_name = 'insights'
      and c.column_name = 'confidence'
      and c.is_nullable = 'YES'
  ) then
    raise exception 'insights.confidence must be nullable (see 202608140002_insights_confidence_nullable.sql)';
  end if;
  if exists (
    select 1 from information_schema.columns c
    where c.table_schema = 'public'
      and c.table_name = 'insights'
      and c.column_name = 'confidence'
      and c.column_default is not null
  ) then
    raise exception 'insights.confidence must not carry a numeric default';
  end if;
end $$;

-- Exercise the minimum durable lifecycle against the actual schema. This is
-- rolled back so it is safe both in local CI and after production migration.
begin;
do $$
declare
  owner_id uuid := '00000000-0000-4000-8000-000000000101';
  project_id uuid := '00000000-0000-4000-8000-000000000102';
  workflow_id uuid := '00000000-0000-4000-8000-000000000103';
  job_id uuid := '00000000-0000-4000-8000-000000000104';
  claimed integer;
begin
  insert into public.projects (id, owner_id, name)
    values (project_id, owner_id, 'migration verification');
  insert into public.workflows (id, project_id, kind)
    values (workflow_id, project_id, 'understand');
  insert into public.jobs (
    id, workflow_id, capability_name, capability_version, cache_key, created_by
  ) values (
    job_id, workflow_id, 'understand', '1.0', 'migration-verification', owner_id
  );
  update public.jobs
    set stage = 'claimed', worker_id = 'migration-test', lease_expires_at = now() + interval '30 seconds'
    where id = job_id and stage = 'queued';
  get diagnostics claimed = row_count;
  if claimed <> 1 then raise exception 'atomic claim failed'; end if;
  update public.jobs set stage = 'running' where id = job_id and worker_id = 'migration-test';
  update public.jobs set stage = 'succeeded', progress = 1, completed_at = now()
    where id = job_id and stage = 'running' and worker_id = 'migration-test';
  if not exists (select 1 from public.jobs where id = job_id and stage = 'succeeded') then
    raise exception 'job lifecycle verification failed';
  end if;
end $$;
rollback;
