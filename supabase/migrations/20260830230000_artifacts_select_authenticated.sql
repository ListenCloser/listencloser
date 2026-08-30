begin;

-- Keep private artifact reads owner-scoped, but let Postgres role membership
-- decide whether the policy is even evaluated for unauthenticated requests.
drop policy if exists "artifacts owner select" on storage.objects;
create policy "artifacts owner select" on storage.objects
  for select to authenticated
  using (
    bucket_id = 'artifacts'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

commit;
