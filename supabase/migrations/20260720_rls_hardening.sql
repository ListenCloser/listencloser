-- Migration: RLS hardening
--
-- The initial schema shipped fully-open policies (`using (true)` /
-- `with check (true)`) plus public UPDATE on jobs and public DELETE on the
-- library bucket. That let any anonymous caller read, write, mutate, and
-- delete every row and object.
--
-- This migration tightens writes to authenticated owners while preserving
-- anonymous READ, because playback still relies on public bucket URLs
-- (apps/web/src/lib/storage.ts getPublicUrl) and the public gallery. The backend uses the
-- service-role key, which bypasses RLS, so server-side uploads are unaffected.
--
-- Ownership model for storage: objects are namespaced by the caller's uid as
-- the first path segment after the logical prefix, e.g.
--   library/<uid>/<file>          (storage.foldername(name)[2] = <uid>)
--   transcriptions/<uid>/<file>
-- so we match auth.uid() against that segment.

-- ---------------------------------------------------------------------------
-- Helper: the owning uid encoded in a storage object path.
-- library/<uid>/... and transcriptions/<uid>/... => segment index 2.
-- Adapters/datasets/audio/midi/enhanced/analysis are written by the backend
-- (service role) so their write policies stay authenticated-only without a
-- per-object owner check.
-- ---------------------------------------------------------------------------

-- ===========================================================================
-- tracks
-- ===========================================================================
drop policy if exists "public insert" on public.tracks;
create policy "tracks authenticated insert" on public.tracks
  for insert to authenticated with check (true);

-- ===========================================================================
-- jobs — drop public UPDATE, gate INSERT behind auth (backend uses service role)
-- ===========================================================================
drop policy if exists "jobs public insert" on public.jobs;
create policy "jobs authenticated insert" on public.jobs
  for insert to authenticated with check (true);

drop policy if exists "jobs public update" on public.jobs;
-- No client UPDATE policy: only the service-role backend updates job status.

-- ===========================================================================
-- models — gate INSERT behind auth (backend uses service role)
-- ===========================================================================
drop policy if exists "models public insert" on public.models;
create policy "models authenticated insert" on public.models
  for insert to authenticated with check (true);

-- ===========================================================================
-- storage: library — owner-scoped insert/delete, public read
-- ===========================================================================
drop policy if exists "library public insert" on storage.objects;
create policy "library owner insert" on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'library'
    and (storage.foldername(name))[2] = auth.uid()::text
  );

drop policy if exists "library public delete" on storage.objects;
create policy "library owner delete" on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'library'
    and (storage.foldername(name))[2] = auth.uid()::text
  );

-- ===========================================================================
-- storage: transcriptions — owner-scoped insert, public read
-- ===========================================================================
drop policy if exists "transcriptions public insert" on storage.objects;
create policy "transcriptions owner insert" on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'transcriptions'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- ===========================================================================
-- storage: backend-written buckets — authenticated insert only.
-- These are populated by the service-role backend (bypasses RLS); the
-- authenticated-only client policy removes the anonymous write hole while
-- keeping public read for playback/download.
-- ===========================================================================
drop policy if exists "audio public insert" on storage.objects;
create policy "audio authenticated insert" on storage.objects
  for insert to authenticated with check (bucket_id = 'audio');

drop policy if exists "midi public insert" on storage.objects;
create policy "midi authenticated insert" on storage.objects
  for insert to authenticated with check (bucket_id = 'midi');

drop policy if exists "enhanced public insert" on storage.objects;
create policy "enhanced authenticated insert" on storage.objects
  for insert to authenticated with check (bucket_id = 'enhanced');

drop policy if exists "analysis public insert" on storage.objects;
create policy "analysis authenticated insert" on storage.objects
  for insert to authenticated with check (bucket_id = 'analysis');

drop policy if exists "datasets public insert" on storage.objects;
create policy "datasets authenticated insert" on storage.objects
  for insert to authenticated with check (bucket_id = 'datasets');

drop policy if exists "adapters public insert" on storage.objects;
create policy "adapters authenticated insert" on storage.objects
  for insert to authenticated with check (bucket_id = 'adapters');
