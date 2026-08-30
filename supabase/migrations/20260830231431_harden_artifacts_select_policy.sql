begin;

drop policy if exists "artifacts owner select" on storage.objects;
create policy "artifacts owner select" on storage.objects
  for select to authenticated
  using (
    bucket_id = 'artifacts'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

commit;
