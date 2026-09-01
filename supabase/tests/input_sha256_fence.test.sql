begin;

select plan(10);

insert into public.projects (id, owner_id, name)
values (
  '00000000-0000-0000-0000-000000847001',
  '00000000-0000-0000-0000-000000847000',
  'input sha256 fence pgTAP'
);

insert into public.works (id, project_id, title)
values (
  '00000000-0000-0000-0000-000000847002',
  '00000000-0000-0000-0000-000000847001',
  'trusted input read fixture'
);

insert into public.artifacts (id, work_id, kind, mime_type)
values (
  '00000000-0000-0000-0000-000000847003',
  '00000000-0000-0000-0000-000000847002',
  'audio_original',
  'audio/wav'
);

insert into public.artifact_versions (
  id,
  artifact_id,
  storage_bucket,
  storage_key,
  byte_size
) values
  (
    '00000000-0000-0000-0000-000000847004',
    '00000000-0000-0000-0000-000000847003',
    'artifacts',
    'uploads/declared-input.wav',
    4
  ),
  (
    '00000000-0000-0000-0000-000000847005',
    '00000000-0000-0000-0000-000000847003',
    'artifacts',
    'jobs/847/generated-output.wav',
    4
  );

insert into public.workflows (id, project_id, kind)
values (
  '00000000-0000-0000-0000-000000847006',
  '00000000-0000-0000-0000-000000847001',
  'understand'
);

insert into public.jobs (
  id,
  workflow_id,
  capability_name,
  capability_version,
  stage,
  input_version_ids,
  execution_token
) values (
  '00000000-0000-0000-0000-000000847007',
  '00000000-0000-0000-0000-000000847006',
  'input_sha256_test',
  '1.0',
  'running',
  array['00000000-0000-0000-0000-000000847004'::uuid],
  '00000000-0000-0000-0000-000000847008'
);

select has_function(
  'public',
  'fenced_job_verify_input_sha256',
  array['uuid', 'uuid', 'text', 'text', 'text'],
  'declared-input SHA-256 verification is a dedicated fenced RPC'
);

select is(
  public.fenced_job_verify_input_sha256(
    '00000000-0000-0000-0000-000000847007',
    '00000000-0000-0000-0000-000000847008',
    'artifacts',
    'uploads/declared-input.wav',
    repeat('a', 64)
  ),
  true,
  'the current attempt verifies an exact declared-input Storage locator'
);

select is(
  (select sha256 from public.artifact_versions where id = '00000000-0000-0000-0000-000000847004'),
  repeat('a', 64),
  'a previously unknown input digest moves monotonically from NULL to verified SHA-256'
);

select is(
  public.fenced_job_verify_input_sha256(
    '00000000-0000-0000-0000-000000847007',
    '00000000-0000-0000-0000-000000847008',
    'artifacts',
    'uploads/declared-input.wav',
    repeat('a', 64)
  ),
  true,
  're-verifying the same digest is idempotent'
);

select is(
  public.fenced_job_verify_input_sha256(
    '00000000-0000-0000-0000-000000847007',
    '00000000-0000-0000-0000-000000847008',
    'artifacts',
    'jobs/847/generated-output.wav',
    repeat('c', 64)
  ),
  false,
  'a same-workflow read outside Job input_version_ids is ignored'
);

select is(
  (select sha256 from public.artifact_versions where id = '00000000-0000-0000-0000-000000847005'),
  null::text,
  'non-input Versions keep honest unknown digest state'
);

select throws_ok(
  $$
    select public.fenced_job_verify_input_sha256(
      '00000000-0000-0000-0000-000000847007'::uuid,
      '00000000-0000-0000-0000-000000847008'::uuid,
      'artifacts',
      'uploads/declared-input.wav',
      repeat('b', 64)
    )
  $$,
  '22000',
  'stored Version SHA-256 conflicts with verified bytes',
  'a different measured digest fails closed instead of rewriting history'
);

select is(
  (select sha256 from public.artifact_versions where id = '00000000-0000-0000-0000-000000847004'),
  repeat('a', 64),
  'an integrity conflict leaves the authoritative digest unchanged'
);

select throws_ok(
  $$
    select public.fenced_job_verify_input_sha256(
      '00000000-0000-0000-0000-000000847007'::uuid,
      '00000000-0000-0000-0000-000000847009'::uuid,
      'artifacts',
      'uploads/declared-input.wav',
      repeat('a', 64)
    )
  $$,
  'P0001',
  'stale job execution cannot verify input integrity',
  'a stale execution token cannot enrich input identity'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.fenced_job_verify_input_sha256(uuid,uuid,text,text,text)',
    'EXECUTE'
  )
  and not has_function_privilege(
    'authenticated',
    'public.fenced_job_verify_input_sha256(uuid,uuid,text,text,text)',
    'EXECUTE'
  )
  and has_function_privilege(
    'service_role',
    'public.fenced_job_verify_input_sha256(uuid,uuid,text,text,text)',
    'EXECUTE'
  ),
  'input integrity enrichment is service-role-only'
);

select * from finish();
rollback;
