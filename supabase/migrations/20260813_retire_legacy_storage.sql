-- Forward repair for installations where the original cleanup migration was
-- already recorded. Storage-managed rows cannot be deleted directly in SQL,
-- so make legacy prototype buckets private and remove their access policies.
update storage.buckets
set public = false
where id in ('audio', 'datasets', 'adapters');

drop policy if exists "audio public read" on storage.objects;
drop policy if exists "audio public insert" on storage.objects;
drop policy if exists "audio authenticated insert" on storage.objects;
drop policy if exists "datasets public read" on storage.objects;
drop policy if exists "datasets public insert" on storage.objects;
drop policy if exists "datasets authenticated insert" on storage.objects;
drop policy if exists "adapters public read" on storage.objects;
drop policy if exists "adapters public insert" on storage.objects;
drop policy if exists "adapters authenticated insert" on storage.objects;
