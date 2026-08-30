-- Make backend/worker-produced domain state server-write-only.
--
-- The current product routes domain mutations through FastAPI / the worker using
-- the service-role client. Browser roles only need owner-scoped reads for these
-- tables. Historical owner INSERT policies therefore grant unnecessary authority
-- to fabricate artifact lineage, evidence, workflows, and Storage locators.
--
-- Keep Projects, Works, and workspace state unchanged in this migration: those
-- have separate user-owned mutation semantics. Service-role privileges are also
-- unchanged.

begin;

-- Preserve only the existing browser read surface for server-authoritative
-- tables. REVOKE ALL also removes incidental TRUNCATE/REFERENCES/TRIGGER grants
-- inherited from the historical `grant all` migration.
revoke all privileges on table public.artifacts from anon, authenticated;
grant select on table public.artifacts to anon, authenticated;

revoke all privileges on table public.artifact_versions from anon, authenticated;
grant select on table public.artifact_versions to anon, authenticated;

revoke all privileges on table public.entities from anon, authenticated;
grant select on table public.entities to anon, authenticated;

revoke all privileges on table public.insights from anon, authenticated;
grant select on table public.insights to anon, authenticated;

revoke all privileges on table public.alignments from anon, authenticated;
grant select on table public.alignments to anon, authenticated;

revoke all privileges on table public.workflows from anon, authenticated;
grant select on table public.workflows to anon, authenticated;

revoke all privileges on table public.jobs from anon, authenticated;
grant select on table public.jobs to anon, authenticated;

-- These policies represented a legacy direct-Data-API write model. The server
-- pipeline is now the authority for artifact/evidence/workflow provenance.
drop policy if exists "artifacts owner insert" on public.artifacts;
drop policy if exists "versions owner insert" on public.artifact_versions;
drop policy if exists "entities owner insert" on public.entities;
drop policy if exists "insights owner insert" on public.insights;
drop policy if exists "alignments owner insert" on public.alignments;
drop policy if exists "workflows owner insert" on public.workflows;

commit;
