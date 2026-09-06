-- Library, MIDI, transcription, enhanced, and analysis storage buckets.
-- These are referenced by apps/web/src/lib/music.ts / apps/web/src/lib/storage.ts but were missing
-- their bucket rows + RLS policies, causing "new row violates row-level
-- security policy" on upload.

-- Buckets (idempotent).
insert into storage.buckets (id, name, public)
values ('library', 'library', true)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('midi', 'midi', true)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('transcriptions', 'transcriptions', true)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('enhanced', 'enhanced', true)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('analysis', 'analysis', true)
on conflict (id) do nothing;

-- Library bucket: public read, insert allowed (uploadToLibrary requires auth
-- in app code before calling storage).
drop policy if exists "library public read" on storage.objects;
create policy "library public read" on storage.objects
  for select using (bucket_id = 'library');

drop policy if exists "library public insert" on storage.objects;
create policy "library public insert" on storage.objects
  for insert with check (bucket_id = 'library');

drop policy if exists "library public delete" on storage.objects;
create policy "library public delete" on storage.objects
  for delete using (bucket_id = 'library');

-- MIDI bucket.
drop policy if exists "midi public read" on storage.objects;
create policy "midi public read" on storage.objects
  for select using (bucket_id = 'midi');

drop policy if exists "midi public insert" on storage.objects;
create policy "midi public insert" on storage.objects
  for insert with check (bucket_id = 'midi');

-- Transcriptions bucket.
drop policy if exists "transcriptions public read" on storage.objects;
create policy "transcriptions public read" on storage.objects
  for select using (bucket_id = 'transcriptions');

drop policy if exists "transcriptions public insert" on storage.objects;
create policy "transcriptions public insert" on storage.objects
  for insert with check (bucket_id = 'transcriptions');

-- Enhanced audio bucket.
drop policy if exists "enhanced public read" on storage.objects;
create policy "enhanced public read" on storage.objects
  for select using (bucket_id = 'enhanced');

drop policy if exists "enhanced public insert" on storage.objects;
create policy "enhanced public insert" on storage.objects
  for insert with check (bucket_id = 'enhanced');

-- Analysis bucket.
drop policy if exists "analysis public read" on storage.objects;
create policy "analysis public read" on storage.objects
  for select using (bucket_id = 'analysis');

drop policy if exists "analysis public insert" on storage.objects;
create policy "analysis public insert" on storage.objects
  for insert with check (bucket_id = 'analysis');
