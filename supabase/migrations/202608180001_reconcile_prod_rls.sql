-- Forward repair: reconcile the production database with the canonical schema
-- encoded by the migration set and enforced by backend/tests/test_rls_domain.py.
--
-- The production Supabase project retained permissive policies from earlier
-- migrations (20260716_finetune_studio.sql public jobs/models policies, and the
-- public insert/delete storage variants from 20260719_library_storage.sql) that
-- later canonical migrations (20260720_rls_hardening.sql,
-- 20260729_cleanup_vestigial.sql, 20260813_retire_legacy_storage.sql) intended
-- to remove. It also contains a manually-created set of `anon` storage policies
-- that exist in no migration.
--
-- This migration is idempotent: on a fresh database (all migrations applied)
-- every statement is a no-op; on a drifted database it removes the surplus
-- policies and the vestigial `models` table.

-- ── jobs: only the owner-scoped SELECT policy is canonical ──────────────────
-- INSERT/UPDATE are denied by default; the durable worker writes via the
-- service role, which bypasses RLS.
drop policy if exists "jobs public read" on public.jobs;
drop policy if exists "jobs public insert" on public.jobs;
drop policy if exists "jobs public update" on public.jobs;

-- ── models: vestigial LoRA-adapter table from 20260716 ──────────────────────
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