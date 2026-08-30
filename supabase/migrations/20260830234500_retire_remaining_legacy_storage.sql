-- Retire the remaining legacy public Storage access surface.
--
-- Current domain Versions use only the private `artifacts` bucket. Preserve
-- every historical object in the legacy buckets, but stop exposing or accepting
-- writes through policies that belonged to the pre-domain storage model.

begin;

update storage.buckets
set public = false
where id in ('analysis', 'enhanced', 'library', 'midi', 'transcriptions');

drop policy if exists "analysis public read" on storage.objects;
drop policy if exists "analysis authenticated insert" on storage.objects;
drop policy if exists "enhanced public read" on storage.objects;
drop policy if exists "enhanced authenticated insert" on storage.objects;
drop policy if exists "library public read" on storage.objects;
drop policy if exists "library owner insert" on storage.objects;
drop policy if exists "library owner delete" on storage.objects;
drop policy if exists "midi public read" on storage.objects;
drop policy if exists "midi authenticated insert" on storage.objects;
drop policy if exists "transcriptions public read" on storage.objects;
drop policy if exists "transcriptions owner insert" on storage.objects;

commit;
