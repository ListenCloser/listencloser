-- Migration: Private artifact storage bucket
-- Companion to 20260728_domain_tables.sql

begin;

-- ===========================================================================
-- Private artifact storage bucket — replaces public buckets for domain artifacts
-- ===========================================================================
insert into storage.buckets (id, name, public)
values ('artifacts', 'artifacts', false)
on conflict (id) do update set public = false;

-- ===========================================================================
-- RLS: artifacts bucket — owner-scoped read/write
-- ===========================================================================
create policy "artifacts owner select" on storage.objects
  for select using (
    bucket_id = 'artifacts'
    and auth.role() = 'authenticated'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

create policy "artifacts owner insert" on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'artifacts'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- Tighten existing buckets: make reads authenticated-only where possible.
-- Keep public reads for buckets that existing frontend uses getPublicUrl() on.

-- library: already owner-scoped writes; reads remain public for now
-- transcriptions: already owner-scoped writes; reads remain public for now
-- midi / enhanced / analysis / audio: remain public-read for existing frontend

commit;
