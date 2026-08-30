-- Make repository-created public objects fail closed at the Postgres grant layer.
--
-- Historical migration 202608140001 granted ALL default privileges to Data API
-- roles so fresh local Supabase matched the older hosted-project behavior. The
-- current product owns Data API exposure explicitly, and Supabase now recommends
-- opt-in grants for new public objects. Existing object grants are intentionally
-- unchanged here; only future objects created by the repository migration role
-- lose ambient access.

begin;

-- Repository migrations create application objects as postgres. Force every new
-- table/sequence/function to declare its Data API contract in the same migration
-- that creates it, including service_role access when the backend needs it.
alter default privileges for role postgres in schema public
  revoke all privileges on tables from anon, authenticated, service_role;

alter default privileges for role postgres in schema public
  revoke all privileges on sequences from anon, authenticated, service_role;

alter default privileges for role postgres in schema public
  revoke all privileges on functions from anon, authenticated, service_role;

-- PostgreSQL's built-in function default includes EXECUTE for PUBLIC unless it is
-- explicitly revoked. Keep future public functions opt-in even for roles that
-- inherit PUBLIC.
alter default privileges for role postgres in schema public
  revoke execute on functions from public;

-- worker_heartbeats is an internal liveness table. It was intended to be
-- service-role-only, but legacy table defaults left redundant browser grants in
-- hosted production. RLS already blocked those roles; remove the ambient grants
-- so least privilege no longer depends on that second layer.
revoke all privileges on table public.worker_heartbeats from anon, authenticated;
grant all privileges on table public.worker_heartbeats to service_role;

commit;
