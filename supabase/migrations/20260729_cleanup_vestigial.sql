-- Migration: drop vestigial MusicGen prototype tables and buckets
-- These were part of the early prototype and are now superseded by the domain
-- model (see docs/adr/ADR-007.md). No active code paths read or write to them.

-- Storage cleanup: remove objects and policies before dropping buckets
delete from storage.objects where bucket_id = 'audio';
delete from storage.objects where bucket_id = 'datasets';
delete from storage.objects where bucket_id = 'adapters';

drop policy if exists "audio public read" on storage.objects;
drop policy if exists "audio public insert" on storage.objects;
drop policy if exists "datasets public read" on storage.objects;
drop policy if exists "datasets public insert" on storage.objects;
drop policy if exists "adapters public read" on storage.objects;
drop policy if exists "adapters public insert" on storage.objects;

delete from storage.buckets where id = 'audio';
delete from storage.buckets where id = 'datasets';
delete from storage.buckets where id = 'adapters';

-- Drop vestigial tables (RLS policies cascade with the tables)
drop table if exists public.tracks cascade;
drop table if exists public.models cascade;
drop table if exists public.jobs cascade;
