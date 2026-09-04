begin;

select plan(8);

insert into public.projects (id, owner_id, name)
values (
  '00000000-0000-0000-0000-000000593001',
  '00000000-0000-0000-0000-000000593000',
  'storage re-home fence pgTAP'
);

insert into public.works (id, project_id, title)
values (
  '00000000-0000-0000-0000-000000593002',
  '00000000-0000-0000-0000-000000593001',
  'storage re-home fixture'
);

insert into public.artifacts (id, work_id, kind, mime_type)
values
  (
    '00000000-0000-0000-0000-000000593003',
    '00000000-0000-0000-0000-000000593002',
    'midi_performance',
    'audio/midi'
  ),
  (
    '00000000-0000-0000-0000-000000593010',
    '00000000-0000-0000-0000-000000593002',
    'midi_performance',
    'audio/midi'
  );

insert into public.artifact_versions (
  id,
  artifact_id,
  lineage,
  storage_bucket,
  storage_key,
  byte_size,
  sha256,
  metadata,
  label,
  created_at,
  created_by
) values
  (
    '00000000-0000-0000-0000-000000593004',
    '00000000-0000-0000-0000-000000593003',
    '{}',
    'artifacts',
    'transcriptions/legacy-a.mid',
    4,
    repeat('a', 64),
    '{}',
    'legacy a',
    '2026-09-03 19:00:00+00',
    '00000000-0000-0000-0000-000000593000'
  ),
  (
    '00000000-0000-0000-0000-000000593011',
    '00000000-0000-0000-0000-000000593010',
    '{}',
    'artifacts',
    'transcriptions/legacy-b.mid',
    4,
    repeat('b', 64),
    '{}',
    'legacy b',
    '2026-09-03 19:00:00+00',
    '00000000-0000-0000-0000-000000593000'
  );

select has_function(
  'public',
  'enforce_storage_locator_rehome_fence',
  array[]::text[],
  'storage re-home write-time fence exists'
);

select has_trigger(
  'public',
  'artifact_versions',
  'artifact_versions_storage_locator_rehome_fence',
  'artifact_versions applies the storage re-home write-time fence'
);

-- The replacement object must already exist before publication.
insert into storage.objects (bucket_id, name)
values (
  'artifacts',
  '00000000-0000-0000-0000-000000593000/00000000-0000-0000-0000-000000593001/00000000-0000-0000-0000-000000593003/rehome-a.mid'
);

select lives_ok(
  $sql$
    insert into public.artifact_versions (
      id,
      artifact_id,
      parent_version_id,
      lineage,
      storage_bucket,
      storage_key,
      byte_size,
      sha256,
      metadata,
      label,
      created_at,
      created_by
    ) values (
      '00000000-0000-0000-0000-000000593005',
      '00000000-0000-0000-0000-000000593003',
      '00000000-0000-0000-0000-000000593004',
      array['00000000-0000-0000-0000-000000593004'::uuid],
      'artifacts',
      '00000000-0000-0000-0000-000000593000/00000000-0000-0000-0000-000000593001/00000000-0000-0000-0000-000000593003/rehome-a.mid',
      4,
      repeat('c', 64),
      jsonb_build_object(
        'storage_locator_rehome',
        jsonb_build_object(
          'method', 'storage_locator_rehome_v1',
          'source_version_id', '00000000-0000-0000-0000-000000593004'
        )
      ),
      'replacement a',
      '2026-09-03 19:01:00+00',
      '00000000-0000-0000-0000-000000593000'
    )
  $sql$,
  'latest source can publish one authoritative re-home replacement'
);

select ok(
  exists (
    select 1
    from public.artifact_versions
    where id = '00000000-0000-0000-0000-000000593005'
      and parent_version_id = '00000000-0000-0000-0000-000000593004'
  ),
  'accepted re-home replacement preserves immutable parent lineage'
);

-- Ordinary Version insertion remains outside the special recovery path.
select lives_ok(
  $sql$
    insert into public.artifact_versions (
      id,
      artifact_id,
      lineage,
      storage_bucket,
      storage_key,
      byte_size,
      sha256,
      metadata,
      label,
      created_at,
      created_by
    ) values (
      '00000000-0000-0000-0000-000000593012',
      '00000000-0000-0000-0000-000000593010',
      '{}',
      'artifacts',
      'jobs/ordinary/current.mid',
      4,
      repeat('d', 64),
      '{}',
      'newer normal version',
      '2026-09-03 19:02:00+00',
      '00000000-0000-0000-0000-000000593000'
    )
  $sql$,
  'ordinary Version publication is unaffected by the recovery-only trigger branch'
);

-- This models the real TOCTOU: the recovery process planned against source
-- 593011 while it was latest, then normal publication 593012 landed before the
-- copied replacement metadata was inserted.
insert into storage.objects (bucket_id, name)
values (
  'artifacts',
  '00000000-0000-0000-0000-000000593000/00000000-0000-0000-0000-000000593001/00000000-0000-0000-0000-000000593010/rehome-b.mid'
);

select throws_ok(
  $sql$
    insert into public.artifact_versions (
      id,
      artifact_id,
      parent_version_id,
      lineage,
      storage_bucket,
      storage_key,
      byte_size,
      sha256,
      metadata,
      label,
      created_at,
      created_by
    ) values (
      '00000000-0000-0000-0000-000000593013',
      '00000000-0000-0000-0000-000000593010',
      '00000000-0000-0000-0000-000000593011',
      array['00000000-0000-0000-0000-000000593011'::uuid],
      'artifacts',
      '00000000-0000-0000-0000-000000593000/00000000-0000-0000-0000-000000593001/00000000-0000-0000-0000-000000593010/rehome-b.mid',
      4,
      repeat('e', 64),
      jsonb_build_object(
        'storage_locator_rehome',
        jsonb_build_object(
          'method', 'storage_locator_rehome_v1',
          'source_version_id', '00000000-0000-0000-0000-000000593011'
        )
      ),
      'stale recovery replacement',
      '2026-09-03 19:03:00+00',
      '00000000-0000-0000-0000-000000593000'
    )
  $sql$,
  'P0001',
  'storage re-home source is no longer latest',
  'write-time fence rejects a source that lost latest authority after planning'
);

select ok(
  not exists (
    select 1
    from public.artifact_versions
    where id = '00000000-0000-0000-0000-000000593013'
  ),
  'rejected stale recovery leaves no replacement Version'
);

select is(
  (
    select id
    from public.artifact_versions
    where artifact_id = '00000000-0000-0000-0000-000000593010'
    order by created_at desc, id desc
    limit 1
  ),
  '00000000-0000-0000-0000-000000593012'::uuid,
  'normal newer Version remains canonical after stale recovery rejection'
);

select * from finish();
rollback;
