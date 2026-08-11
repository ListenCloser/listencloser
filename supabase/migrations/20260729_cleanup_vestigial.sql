-- Migration: drop vestigial MusicGen prototype tables and buckets
-- These were part of the early prototype and are now superseded by the domain
-- model (see docs/adr/ADR-007.md). No active code paths read or write to them.

-- Storage owns its tables and rejects direct SQL deletion. Retire these
-- buckets safely by making them private and removing every access policy;
-- any physical object deletion is an operational Storage API task.
update storage.buckets
set public = false
where id in ('audio', 'datasets', 'adapters');

drop policy if exists "audio public read" on storage.objects;
drop policy if exists "audio public insert" on storage.objects;
drop policy if exists "datasets public read" on storage.objects;
drop policy if exists "datasets public insert" on storage.objects;
drop policy if exists "adapters public read" on storage.objects;
drop policy if exists "adapters public insert" on storage.objects;

-- Drop vestigial tables (RLS policies cascade with the tables)
drop table if exists public.tracks cascade;
drop table if exists public.models cascade;
drop table if exists public.jobs cascade;
