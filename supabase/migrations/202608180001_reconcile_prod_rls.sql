-- Forward repair: reconcile the production database with the canonical schema
-- encoded by the migration set and enforced by backend/tests/test_rls_domain.py.
--
-- Two sources of drift existed on the production Supabase project:
--
-- 1. The legacy `202607160001_finetune_studio.sql` migration (formerly
--    20260716_finetune_studio.sql) re-creates permissive public jobs/models
--    policies and the vestigial `models` table whenever it is replayed. A
--    deploy-time `migration repair --status reverted 20260716 20260728` +
--    `db push --include-all` replay made that happen on every deployment.
-- 2. The production database retained additional surplus policies (legacy
--    public insert/delete storage variants from 20260719_library_storage.sql
--    that later canonical migrations intended to remove, and a manually-created
--    set of `anon` storage policies that exist in no migration).
--
-- This migration is idempotent: on a fresh database (all migrations applied)
-- every statement is a no-op; on a drifted database it removes the surplus
-- policies, the vestigial `models` table, and the extra index that a replay of
-- `202607160001_finetune_studio.sql` would add to `public.jobs`.

-- ── jobs: only the owner-scoped SELECT policy is canonical ──────────────────
-- INSERT/UPDATE are denied by default; the durable worker writes via the
-- service role, which bypasses RLS.
drop policy if exists "jobs public read" on public.jobs;
drop policy if exists "jobs public insert" on public.jobs;
drop policy if exists "jobs public update" on public.jobs;
-- A replay of 202607160001_finetune_studio.sql creates this index on the
-- canonical jobs table; it is not part of the canonical schema.
drop index if exists jobs_created_at_idx;

-- ── models: vestigial LoRA-adapter table ────────────────────────────────────
-- Dropped by the canonical cleanup (20260729_cleanup_vestigial.sql); not part
-- of the domain schema (no backend/domain model references it).
drop table if exists public.models cascade;

-- ── storage: remove legacy permissive/anon policies ─────────────────────────
-- The active buckets keep their canonical policies (public reads, authenticated
-- /owner inserts); only the surplus public-insert/delete and manually-created
-- `anon` policies are removed.
drop policy if exists "adapters public read" on storage.objects;
drop policy if exists "adapters public insert" on storage.objects;
drop policy if exists "datasets public read" on storage.objects;
drop policy if exists "datasets public insert" on storage.objects;
drop policy if exists "analysis public insert" on storage.objects;
drop policy if exists "enhanced public insert" on storage.objects;
drop policy if exists "library public insert" on storage.objects;
drop policy if exists "library public delete" on storage.objects;
drop policy if exists "midi public insert" on storage.objects;
drop policy if exists "transcriptions public insert" on storage.objects;
drop policy if exists "anon select library" on storage.objects;
drop policy if exists "anon insert library" on storage.objects;
drop policy if exists "anon select midi" on storage.objects;
drop policy if exists "anon insert midi" on storage.objects;
