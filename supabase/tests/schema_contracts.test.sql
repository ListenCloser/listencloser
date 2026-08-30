begin;

select plan(17);

select ok(
  to_regclass('public.jobs') is not null,
  'jobs table exists'
);

select ok(
  to_regclass('public.worker_heartbeats') is not null,
  'worker_heartbeats table exists'
);

select is(
  (
    select count(*)
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'jobs'
      and column_name = any(array[
        'id', 'workflow_id', 'capability_name', 'capability_version', 'stage',
        'progress', 'status_message', 'worker_id', 'lease_expires_at',
        'retry_count', 'max_retries', 'input_version_ids', 'output_version_ids',
        'parameters', 'cache_key', 'error_message', 'error_details', 'provenance',
        'started_at', 'completed_at', 'created_at', 'created_by'
      ])
  ),
  22::bigint,
  'jobs exposes the complete durable lifecycle contract'
);

select ok(
  exists (
    select 1
    from pg_type t
    join pg_enum e on e.enumtypid = t.oid
    where t.typname = 'job_stage'
      and e.enumlabel = 'running'
  ),
  'job_stage enum supports running jobs'
);

select ok(
  exists (
    select 1
    from pg_indexes
    where schemaname = 'public'
      and tablename = 'jobs'
      and indexdef ilike '%unique%cache_key%'
  ),
  'jobs cache keys remain unique'
);

select ok(
  exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'jobs'
      and policyname = 'jobs owner select'
  ),
  'jobs retain the owner-scoped select policy'
);

select is(
  (
    select count(*)
    from pg_policies
    where schemaname = 'public'
      and tablename = 'jobs'
  ),
  1::bigint,
  'jobs expose no browser mutation policies'
);

select ok(
  not exists (
    select 1
    from pg_indexes
    where schemaname = 'public'
      and tablename = 'jobs'
      and indexname = 'jobs_created_at_idx'
  ),
  'legacy jobs_created_at_idx is absent'
);

select ok(
  to_regclass('public.models') is null,
  'vestigial models table is absent'
);

select ok(
  not exists (
    select 1
    from pg_policies
    where schemaname = 'storage'
      and tablename = 'objects'
      and policyname in (
        'adapters public read', 'adapters public insert',
        'datasets public read', 'datasets public insert',
        'analysis public insert', 'enhanced public insert',
        'library public insert', 'library public delete',
        'midi public insert', 'transcriptions public insert',
        'anon select library', 'anon insert library',
        'anon select midi', 'anon insert midi'
      )
  ),
  'legacy permissive storage policies are absent'
);

select ok(
  exists (
    select 1
    from storage.buckets
    where id = 'artifacts'
      and public = false
  ),
  'artifacts storage bucket remains private'
);

select ok(
  not exists (
    select 1
    from (
      values
        ('artifacts'),
        ('artifact_versions'),
        ('entities'),
        ('insights'),
        ('alignments'),
        ('workflows'),
        ('jobs')
    ) as owned(table_name)
    cross join (
      values ('anon'), ('authenticated')
    ) as browser(role_name)
    where not has_table_privilege(
      browser.role_name,
      format('public.%I', owned.table_name),
      'SELECT'
    )
      or has_table_privilege(browser.role_name, format('public.%I', owned.table_name), 'INSERT')
      or has_table_privilege(browser.role_name, format('public.%I', owned.table_name), 'UPDATE')
      or has_table_privilege(browser.role_name, format('public.%I', owned.table_name), 'DELETE')
      or has_table_privilege(browser.role_name, format('public.%I', owned.table_name), 'TRUNCATE')
      or has_table_privilege(browser.role_name, format('public.%I', owned.table_name), 'REFERENCES')
      or has_table_privilege(browser.role_name, format('public.%I', owned.table_name), 'TRIGGER')
  ),
  'browser roles can only select server-owned domain tables'
);

select ok(
  not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and (
        (tablename = 'artifacts' and policyname = 'artifacts owner insert') or
        (tablename = 'artifact_versions' and policyname = 'versions owner insert') or
        (tablename = 'entities' and policyname = 'entities owner insert') or
        (tablename = 'insights' and policyname = 'insights owner insert') or
        (tablename = 'alignments' and policyname = 'alignments owner insert') or
        (tablename = 'workflows' and policyname = 'workflows owner insert')
      )
  ),
  'legacy browser insert policies are absent from server-owned state'
);

select ok(
  exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'insights'
      and column_name = 'confidence'
      and is_nullable = 'YES'
  ),
  'insights confidence remains nullable'
);

select ok(
  not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'insights'
      and column_name = 'confidence'
      and column_default is not null
  ),
  'insights confidence has no fabricated numeric default'
);

insert into public.projects (id, owner_id, name)
values (
  '00000000-0000-4000-8000-000000000102',
  '00000000-0000-4000-8000-000000000101',
  'migration verification'
);

insert into public.workflows (id, project_id, kind)
values (
  '00000000-0000-4000-8000-000000000103',
  '00000000-0000-4000-8000-000000000102',
  'understand'
);

insert into public.jobs (
  id,
  workflow_id,
  capability_name,
  capability_version,
  cache_key,
  created_by
) values (
  '00000000-0000-4000-8000-000000000104',
  '00000000-0000-4000-8000-000000000103',
  'understand',
  '1.0',
  'migration-verification',
  '00000000-0000-4000-8000-000000000101'
);

update public.jobs
set
  stage = 'claimed',
  worker_id = 'migration-test',
  lease_expires_at = now() + interval '30 seconds'
where id = '00000000-0000-4000-8000-000000000104'
  and stage = 'queued';

select is(
  (
    select stage::text
    from public.jobs
    where id = '00000000-0000-4000-8000-000000000104'
  ),
  'claimed',
  'queued job can be atomically claimed'
);

update public.jobs
set stage = 'running'
where id = '00000000-0000-4000-8000-000000000104'
  and worker_id = 'migration-test';

update public.jobs
set
  stage = 'succeeded',
  progress = 1,
  completed_at = now()
where id = '00000000-0000-4000-8000-000000000104'
  and stage = 'running'
  and worker_id = 'migration-test';

select is(
  (
    select stage::text
    from public.jobs
    where id = '00000000-0000-4000-8000-000000000104'
  ),
  'succeeded',
  'durable job lifecycle reaches succeeded'
);

select * from finish();

rollback;
