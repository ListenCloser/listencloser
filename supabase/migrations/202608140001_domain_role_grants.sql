-- Migration: grant the standard Supabase roles access to the domain tables.
--
-- Production Supabase grants anon/authenticated/service_role automatically,
-- but a fresh local Supabase (as used by the database-integration and
-- real-stack-e2e CI jobs) does not. The backend persists through the service
-- role via PostgREST, and RLS-protected client access depends on the anon and
-- authenticated grants. Make them explicit so the schema is self-contained and
-- reproducible from zero.

begin;

grant all on table public.projects to anon, authenticated, service_role;
grant all on table public.works to anon, authenticated, service_role;
grant all on table public.artifacts to anon, authenticated, service_role;
grant all on table public.artifact_versions to anon, authenticated, service_role;
grant all on table public.entities to anon, authenticated, service_role;
grant all on table public.insights to anon, authenticated, service_role;
grant all on table public.alignments to anon, authenticated, service_role;
grant all on table public.workflows to anon, authenticated, service_role;
grant all on table public.jobs to anon, authenticated, service_role;
grant all on table public.workspace_states to anon, authenticated, service_role;
grant all on table public.worker_heartbeats to service_role;

alter default privileges in schema public
  grant all on tables to anon, authenticated, service_role;

commit;
