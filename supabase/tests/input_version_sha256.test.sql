begin;

select plan(10);

insert into public.projects (id, owner_id, name)
values (
  '00000000-0000-0000-0000-000000847001',
  '00000000-0000-0000-0000-000000847000',
  'input sha256 pgTAP'
);

insert into public.works (id, project_id, title)
values (
  '00000000-0000-0000-0000-000000847002',
  '00000000-0000-0000-0000-000000847001',
  'integrity fixture'
);

insert into public.artifacts (id, work_id, kind, mime_type)
values
  (
    '00000000-0000-0000-0000-000000847003',
    '00000000-0000-0000-0000-000000847002',
    'audio_original',
    'audio/wav'
  ),
  (
    '00000000-0000-0000-0000-000000847004',
    '00000000-0000-0000-0000-000000847002',
    'audio_original',
    'audio/wav'
  );

insert into public.artifact_versions (
  id,
  artifact_id,
  storage_bucket,
  storage_key,
  byte_size,
  sha256
) values
  (
    '00000000-0000-0000-0000-000000847005',
    '00000000-0000-0000-0000-000000847003',
    'artifacts',
    'uploads/user/original.wav',
    7,
    null
  ),
  (
    '00000000-0000-0000-0000-000000847006',
    '00000000-0000-0000-0000-000000847004',
    'artifacts',
    'uploads/user/not-an-input.wav',
    7,
    null
  );

insert into public.workflows (id, project_id, kind)
values (
  '00000000-0000-0000-0000-000000847007',
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
  execution_token,
  created_at
) values (
  '00000000-0000-0000-0000-000000847008',
  '00000000-0000-0000-0000-000000847007',
  'understand',
  '1.0',
  'running',
  array['00000000-0000-0000-0000-000000847005'::uuid],
  '00000000-0000-0000-0000-000000847009',
  '2026-09-01 00:00:00+00'
);

select is(
  public.fenced_job_verify_input_sha256(
    '00000000-0000-0000-0000-000000847008',
    '00000000-0000-0000-0000-000000847009',
    '00000000-0000-0000-0000-000000847005',
    repeat('a', 64)
  ),
  repeat('a', 64),
  'current trusted read enriches a NULL declared-input digest'
);

select is(
  (select sha256 from public.artifact_versions where id = '00000000-0000-0000-0000-000000847005'),
  repeat('a', 64),
  'the verified digest is persisted on the Version'
);

select is(
  public.fenced_job_verify_input_sha256(
    '00000000-0000-0000-0000-000000847008',
    '00000000-0000-0000-0000-000000847009',
    '00000000-0000-0000-0000-000000847005',
    repeat('a', 64)
  ),
  repeat('a', 64),
  'same-digest retry is idempotent'
);

select throws_ok(
  $$
    select public.fenced_job_verify_input_sha256(
      '00000000-0000-0000-0000-000000847008',
      '00000000-0000-0000-0000-000000847009',
      '00000000-0000-0000-0000-000000847005',
      repeat('b', 64)
    )
  $$,
  'P0001',
  'input Version sha256 conflicts with measured bytes',
  'a different measured digest fails closed'
);

select is(
  (select sha256 from public.artifact_versions where id = '00000000-0000-0000-0000-000000847005'),
  repeat('a', 64),
  'a conflict cannot overwrite the established digest'
);

select throws_ok(
  $$
    select public.fenced_job_verify_input_sha256(
      '00000000-0000-0000-0000-000000847008',
      '00000000-0000-0000-0000-000000847009',
      '00000000-0000-0000-0000-000000847006',
      repeat('c', 64)
    )
  $$,
  '42501',
  'job cannot verify a Version outside its declared inputs',
  'the fenced mutation cannot target a non-input Version'
);

select is(
  (select sha256 from public.artifact_versions where id = '00000000-0000-0000-0000-000000847006'),
  null,
  'rejected non-input enrichment leaves historical NULL unchanged'
);

select throws_ok(
  $$
    select public.fenced_job_verify_input_sha256(
      '00000000-0000-0000-0000-000000847008',
      '00000000-0000-0000-0000-000000847099',
      '00000000-0000-0000-0000-000000847005',
      repeat('a', 64)
    )
  $$,
  'P0001',
  'stale job execution cannot verify input integrity',
  'a stale execution token cannot enrich input integrity'
);

select throws_ok(
  $$
    select public.fenced_job_verify_input_sha256(
      '00000000-0000-0000-0000-000000847008',
      '00000000-0000-0000-0000-000000847009',
      '00000000-0000-0000-0000-000000847005',
      'ABC'
    )
  $$,
  '22023',
  'verified input sha256 must be 64 lowercase hexadecimal characters',
  'malformed or non-canonical digests are rejected'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.fenced_job_verify_input_sha256(uuid,uuid,uuid,text)',
    'EXECUTE'
  )
  and not has_function_privilege(
    'authenticated',
    'public.fenced_job_verify_input_sha256(uuid,uuid,uuid,text)',
    'EXECUTE'
  )
  and has_function_privilege(
    'service_role',
    'public.fenced_job_verify_input_sha256(uuid,uuid,uuid,text)',
    'EXECUTE'
  ),
  'input integrity enrichment is service-role-only'
);

select * from finish();
rollback;
