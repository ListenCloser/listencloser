begin;

select plan(4);

select ok(
  exists (
    select 1
    from pg_indexes
    where schemaname = 'public'
      and tablename = 'workflows'
      and indexname = 'idx_workflows_target_version'
      and indexdef ilike '%(target_version_id)%'
  ),
  'workflows target-version foreign key has a covering index'
);

select ok(
  not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = any(array[
        'projects', 'works', 'artifacts', 'artifact_versions', 'entities',
        'insights', 'alignments', 'workflows', 'jobs'
      ])
      and roles <> array['authenticated']::name[]
  ),
  'retained domain RLS policies are scoped to authenticated callers'
);

select ok(
  not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = any(array[
        'projects', 'works', 'artifacts', 'artifact_versions', 'entities',
        'insights', 'alignments', 'workflows', 'jobs'
      ])
      and (
        coalesce(qual, '') ilike '%auth.uid()%'
        or coalesce(with_check, '') ilike '%auth.uid()%'
      )
      and concat_ws(' ', qual, with_check) not ilike '%select auth.uid()%'
  ),
  'domain RLS caches auth.uid once per statement through an initPlan'
);

select is(
  (
    select count(*)
    from pg_policies
    where schemaname = 'public'
      and (
        (tablename = 'projects' and policyname = 'projects owner update')
        or (tablename = 'works' and policyname = 'works owner update')
      )
      and with_check is not null
  ),
  2::bigint,
  'owner-mutable rows validate both old and new ownership on update'
);

select * from finish();

rollback;
