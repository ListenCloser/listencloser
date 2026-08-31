-- Retire the legacy browser PostgREST data plane for ListenCloser domain state.
--
-- The product now routes Projects, Works, artifacts, evidence, workflows, and jobs
-- through FastAPI. Browser Supabase usage is limited to Auth/session operations and
-- authorized Storage uploads. Keep RLS policies as defense in depth, but remove the
-- table ACLs that make these domain tables callable through anon/authenticated roles.
-- Retained owner RLS policies are therefore an internal safety net, not a supported
-- browser API contract.
--
-- service_role remains unchanged because FastAPI and the worker use it for trusted
-- persistence. worker_heartbeats is included idempotently after the fail-closed
-- default-grants migration so this file states the complete browser-table boundary.

begin;

revoke all privileges on table
  public.projects,
  public.works,
  public.artifacts,
  public.artifact_versions,
  public.entities,
  public.insights,
  public.alignments,
  public.workflows,
  public.jobs,
  public.workspace_states,
  public.worker_heartbeats
from anon, authenticated;

commit;
