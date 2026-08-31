begin;

select plan(3);

select is(
  (
    select count(*)
    from storage.buckets
    where id in ('analysis', 'enhanced', 'library', 'midi', 'transcriptions')
      and public = false
  ),
  5::bigint,
  'remaining legacy buckets exist and are private'
);

select ok(
  not exists (
    select 1
    from pg_policies
    where schemaname = 'storage'
      and tablename = 'objects'
      and policyname in (
        'analysis public read',
        'analysis authenticated insert',
        'enhanced public read',
        'enhanced authenticated insert',
        'library public read',
        'library owner insert',
        'library owner delete',
        'midi public read',
        'midi authenticated insert',
        'transcriptions public read',
        'transcriptions owner insert'
      )
  ),
  'legacy bucket read and write policies are absent'
);

select ok(
  exists (
    select 1
    from storage.buckets
    where id = 'artifacts'
      and public = false
  )
  and exists (
    select 1
    from pg_policies
    where schemaname = 'storage'
      and tablename = 'objects'
      and policyname = 'artifacts owner insert'
  )
  and exists (
    select 1
    from pg_policies
    where schemaname = 'storage'
      and tablename = 'objects'
      and policyname = 'artifacts owner select'
  ),
  'active private artifacts storage contract remains intact'
);

select * from finish();

rollback;
