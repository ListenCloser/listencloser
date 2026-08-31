begin;

select plan(16);

create temp table __execution_tokens (
  label text primary key,
  token uuid not null
);

insert into public.projects (id, owner_id, name)
values (
  '00000000-0000-0000-0000-000000539001',
  '00000000-0000-0000-0000-000000539000',
  'execution fence pgTAP'
);

insert into public.works (id, project_id, title)
values (
  '00000000-0000-0000-0000-000000539002',
  '00000000-0000-0000-0000-000000539001',
  'takeover fixture'
);

insert into public.workflows (id, project_id, kind)
values (
  '00000000-0000-0000-0000-000000539003',
  '00000000-0000-0000-0000-000000539001',
  'understand'
);

insert into public.jobs (
  id,
  workflow_id,
  capability_name,
  capability_version,
  created_at
) values (
  '00000000-0000-0000-0000-000000539004',
  '00000000-0000-0000-0000-000000539003',
  'execution_fence_test',
  '1.0',
  '2026-08-30 00:00:00+00'
);

select col_type_is(
  'public',
  'jobs',
  'execution_token',
  'uuid',
  'Jobs carry a per-claim execution token'
);

insert into __execution_tokens (label, token)
select 'attempt-a', execution_token
from public.claim_next_job('pg-tap-worker-a', 30.0)
where id = '00000000-0000-0000-0000-000000539004';

select ok(
  (select token is not null from __execution_tokens where label = 'attempt-a'),
  'claim_next_job assigns a non-null execution token'
);

update public.jobs
set
  stage = 'queued',
  worker_id = null,
  lease_expires_at = null
where id = '00000000-0000-0000-0000-000000539004';

insert into __execution_tokens (label, token)
select 'attempt-b', execution_token
from public.claim_next_job('pg-tap-worker-b', 30.0)
where id = '00000000-0000-0000-0000-000000539004';

select isnt(
  (select token from __execution_tokens where label = 'attempt-a'),
  (select token from __execution_tokens where label = 'attempt-b'),
  'every takeover claim receives a fresh execution token'
);

update public.jobs
set stage = 'running'
where id = '00000000-0000-0000-0000-000000539004';

-- Model the Storage API's committed metadata for a successful current-attempt
-- upload. fenced_job_publish_version must require this exact bucket+key row,
-- not merely a key string that happens to contain the execution token.
insert into storage.objects (bucket_id, name)
select
  'artifacts',
  format(
    'jobs/00000000-0000-0000-0000-000000539004/execution-%s/current.json',
    token::text
  )
from __execution_tokens
where label = 'attempt-b';

select is(
  (
    select count(*)
    from public.fenced_job_publish_version(
      '00000000-0000-0000-0000-000000539004',
      (select token from __execution_tokens where label = 'attempt-b'),
      jsonb_build_object(
        'id', '00000000-0000-0000-0000-000000539005',
        'work_id', '00000000-0000-0000-0000-000000539002',
        'kind', 'analysis_report',
        'mime_type', 'application/json'
      ),
      jsonb_build_object(
        'id', '00000000-0000-0000-0000-000000539006',
        'artifact_id', '00000000-0000-0000-0000-000000539005',
        'lineage', jsonb_build_array(),
        'storage_bucket', 'artifacts',
        'storage_key', format(
          'jobs/00000000-0000-0000-0000-000000539004/execution-%s/current.json',
          (select token::text from __execution_tokens where label = 'attempt-b')
        ),
        'byte_size', 2,
        'metadata', jsonb_build_object(),
        'label', 'current attempt'
      )
    )
  ),
  1::bigint,
  'the current attempt atomically publishes one Artifact/Version pair'
);

select ok(
  exists (
    select 1
    from public.artifacts artifact
    join public.artifact_versions version on version.artifact_id = artifact.id
    where artifact.id = '00000000-0000-0000-0000-000000539005'
      and version.id = '00000000-0000-0000-0000-000000539006'
      and version.produced_by_job_id = '00000000-0000-0000-0000-000000539004'
  ),
  'current publication is durable and attributed to the logical Job'
);

select throws_ok(
  format(
    $sql$
      select *
      from public.fenced_job_publish_version(
        '00000000-0000-0000-0000-000000539004'::uuid,
        %L::uuid,
        '{"id":"00000000-0000-0000-0000-000000539007","work_id":"00000000-0000-0000-0000-000000539002","kind":"analysis_report","mime_type":"application/json"}'::jsonb,
        '{"id":"00000000-0000-0000-0000-000000539008","artifact_id":"00000000-0000-0000-0000-000000539007","lineage":[],"storage_bucket":"artifacts","storage_key":"jobs/539/stale.json","byte_size":2,"metadata":{},"label":"stale attempt"}'::jsonb
      )
    $sql$,
    (select token::text from __execution_tokens where label = 'attempt-a')
  ),
  'P0001',
  'stale job execution cannot publish output',
  'a stale takeover generation cannot publish a Version'
);

select ok(
  not exists (
    select 1
    from public.artifacts
    where id = '00000000-0000-0000-0000-000000539007'
  )
  and not exists (
    select 1
    from public.artifact_versions
    where id = '00000000-0000-0000-0000-000000539008'
  ),
  'rejected stale publication leaves no durable Artifact or Version'
);

select is(
  (
    select count(*)
    from public.fenced_job_insert(
      '00000000-0000-0000-0000-000000539004',
      (select token from __execution_tokens where label = 'attempt-b'),
      'entities',
      jsonb_build_object(
        'id', '00000000-0000-0000-0000-000000539009',
        'version_id', '00000000-0000-0000-0000-000000539006',
        'kind', 'note',
        'start_seconds', 0.0,
        'end_seconds', 1.0,
        'note_pitch', 60,
        'note_start_seconds', 0.0,
        'note_end_seconds', 1.0,
        'note_velocity', 64
      )
    )
  ),
  1::bigint,
  'the current attempt can persist evidence on its own Version'
);

select throws_ok(
  format(
    $sql$
      select *
      from public.fenced_job_insert(
        '00000000-0000-0000-0000-000000539004'::uuid,
        %L::uuid,
        'entities',
        '{"id":"00000000-0000-0000-0000-00000053900a","version_id":"00000000-0000-0000-0000-000000539006","kind":"note","start_seconds":1.0,"end_seconds":2.0,"note_pitch":62,"note_start_seconds":1.0,"note_end_seconds":2.0,"note_velocity":64}'::jsonb
      )
    $sql$,
    (select token::text from __execution_tokens where label = 'attempt-a')
  ),
  'P0001',
  'stale job execution cannot publish output',
  'the same fence protects Entity/Insight/Alignment persistence'
);

insert into public.artifacts (id, work_id, kind, mime_type)
values (
  '00000000-0000-0000-0000-00000053900b',
  '00000000-0000-0000-0000-000000539002',
  'analysis_report',
  'application/json'
);

insert into public.artifact_versions (
  id,
  artifact_id,
  storage_bucket,
  storage_key,
  byte_size,
  produced_by_job_id
) values
  (
    '00000000-0000-0000-0000-00000053900c',
    '00000000-0000-0000-0000-00000053900b',
    'artifacts',
    'jobs/539/mixed-current.json',
    2,
    '00000000-0000-0000-0000-000000539004'
  ),
  (
    '00000000-0000-0000-0000-00000053900d',
    '00000000-0000-0000-0000-00000053900b',
    'artifacts',
    'jobs/539/mixed-unrelated.json',
    2,
    null
  );

select throws_ok(
  format(
    $sql$
      select *
      from public.fenced_job_publish_version(
        '00000000-0000-0000-0000-000000539004'::uuid,
        %L::uuid,
        '{"id":"00000000-0000-0000-0000-00000053900e","work_id":"00000000-0000-0000-0000-000000539002","kind":"analysis_report","mime_type":"application/json"}'::jsonb,
        '{"id":"00000000-0000-0000-0000-00000053900f","artifact_id":"00000000-0000-0000-0000-00000053900e","parent_version_id":"00000000-0000-0000-0000-00000053900d","lineage":["00000000-0000-0000-0000-00000053900d"],"storage_bucket":"artifacts","storage_key":"jobs/539/unrelated-parent.json","byte_size":2,"metadata":{},"label":"invalid parent"}'::jsonb
      )
    $sql$,
    (select token::text from __execution_tokens where label = 'attempt-b')
  ),
  '42501',
  'job cannot parent a Version outside its input/output graph',
  'output parentage is constrained to the Job input/output graph'
);

select throws_ok(
  format(
    $sql$
      select *
      from public.fenced_job_publish_version(
        '00000000-0000-0000-0000-000000539004'::uuid,
        %L::uuid,
        '{"id":"00000000-0000-0000-0000-000000539010","work_id":"00000000-0000-0000-0000-000000539002","kind":"analysis_report","mime_type":"application/json"}'::jsonb,
        '{"id":"00000000-0000-0000-0000-000000539011","artifact_id":"00000000-0000-0000-0000-000000539010","lineage":[],"storage_bucket":"artifacts","storage_key":"jobs/539/unscoped.json","byte_size":2,"metadata":{},"label":"invalid storage"}'::jsonb
      )
    $sql$,
    (select token::text from __execution_tokens where label = 'attempt-b')
  ),
  '42501',
  'job Version storage key is not scoped to the current execution',
  'Version storage references are bound to the exact execution namespace'
);

select throws_ok(
  format(
    $sql$
      select *
      from public.fenced_job_publish_version(
        '00000000-0000-0000-0000-000000539004'::uuid,
        %L::uuid,
        '{"id":"00000000-0000-0000-0000-000000539012","work_id":"00000000-0000-0000-0000-000000539002","kind":"analysis_report","mime_type":"application/json"}'::jsonb,
        jsonb_build_object(
          'id', '00000000-0000-0000-0000-000000539013',
          'artifact_id', '00000000-0000-0000-0000-000000539012',
          'lineage', jsonb_build_array(),
          'storage_bucket', 'artifacts',
          'storage_key', format(
            'jobs/00000000-0000-0000-0000-000000539004/execution-%s/missing.json',
            %L
          ),
          'byte_size', 2,
          'metadata', jsonb_build_object(),
          'label', 'fabricated scoped storage'
        )
      )
    $sql$,
    (select token::text from __execution_tokens where label = 'attempt-b'),
    (select token::text from __execution_tokens where label = 'attempt-b')
  ),
  '42501',
  'job Version storage object does not exist in declared bucket',
  'a fabricated execution-scoped key cannot be published without a successful upload'
);

select is(
  public.fenced_job_delete(
    '00000000-0000-0000-0000-000000539004',
    (select token from __execution_tokens where label = 'attempt-b'),
    'artifacts',
    jsonb_build_object(
      'id_in', jsonb_build_array('00000000-0000-0000-0000-00000053900b')
    )
  ),
  0,
  'Artifact cleanup refuses to cascade across an unrelated Version'
);

select is(
  public.fenced_job_delete(
    '00000000-0000-0000-0000-000000539004',
    (select token from __execution_tokens where label = 'attempt-b'),
    'entities',
    jsonb_build_object(
      'version_id', '00000000-0000-0000-0000-000000539006',
      'kind', 'note'
    )
  ),
  1,
  'the current attempt can use the admitted Entity cleanup shape'
);

select is(
  public.fenced_job_delete(
    '00000000-0000-0000-0000-000000539004',
    (select token from __execution_tokens where label = 'attempt-b'),
    'artifacts',
    jsonb_build_object(
      'id_in', jsonb_build_array('00000000-0000-0000-0000-000000539005')
    )
  ),
  1,
  'the current attempt can clean up its own published Artifact graph'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.fenced_job_publish_version(uuid,uuid,jsonb,jsonb)',
    'EXECUTE'
  )
  and not has_function_privilege(
    'authenticated',
    'public.fenced_job_insert(uuid,uuid,text,jsonb)',
    'EXECUTE'
  )
  and not has_function_privilege(
    'anon',
    'public.fenced_job_delete(uuid,uuid,text,jsonb)',
    'EXECUTE'
  )
  and has_function_privilege(
    'service_role',
    'public.fenced_job_publish_version(uuid,uuid,jsonb,jsonb)',
    'EXECUTE'
  )
  and has_function_privilege(
    'service_role',
    'public.fenced_job_insert(uuid,uuid,text,jsonb)',
    'EXECUTE'
  )
  and has_function_privilege(
    'service_role',
    'public.fenced_job_delete(uuid,uuid,text,jsonb)',
    'EXECUTE'
  ),
  'only the service-side worker can invoke execution-fenced persistence RPCs'
);

select * from finish();

rollback;