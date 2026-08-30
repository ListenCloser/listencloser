-- Fail closed for future application-owned objects in the public schema.
--
-- ListenCloser migrations create public domain objects as postgres. The historical
-- default grants made every new table/sequence/function reachable by browser roles
-- (and service_role) before the migration that created it made an explicit access
-- decision. Existing object grants are intentionally unchanged here, except for the
-- service-only worker heartbeat table.
--
-- Supabase's platform-managed supabase_admin defaults are intentionally left alone:
-- current ListenCloser public tables/functions are postgres-owned, so mutating the
-- platform role would broaden this migration beyond application-owned objects.

begin;

alter default privileges for role postgres in schema public
  revoke all privileges on tables from anon, authenticated, service_role;

alter default privileges for role postgres in schema public
  revoke all privileges on sequences from anon, authenticated, service_role;

alter default privileges for role postgres in schema public
  revoke all privileges on functions from public, anon, authenticated, service_role;

-- worker_heartbeats is an internal worker liveness surface. RLS already blocks
-- browser rows, but ACLs should express the same service-only contract directly.
revoke all privileges on table public.worker_heartbeats from anon, authenticated;
grant select, insert, update, delete on table public.worker_heartbeats to service_role;

commit;
