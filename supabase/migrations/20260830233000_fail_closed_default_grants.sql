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

-- PostgreSQL grants EXECUTE on new functions to PUBLIC by default. That built-in
-- grant is global, so it must be revoked globally; a schema-scoped REVOKE cannot
-- subtract a global default. Preserve today's behavior for Supabase extension
-- functions explicitly, while leaving application functions in public fail-closed.
alter default privileges for role postgres
  revoke execute on functions from public;

alter default privileges for role postgres in schema extensions
  grant execute on functions to public;

alter default privileges for role postgres in schema public
  revoke all privileges on functions from anon, authenticated, service_role;

-- worker_heartbeats is an internal worker liveness surface. RLS already blocks
-- browser rows, but ACLs should express the same service-only contract directly.
revoke all privileges on table public.worker_heartbeats from anon, authenticated;
grant select, insert, update, delete on table public.worker_heartbeats to service_role;

commit;
