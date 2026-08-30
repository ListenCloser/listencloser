begin;

select plan(6);

-- Exercise the defaults directly instead of only inspecting pg_default_acl.
create table public.__default_grant_probe (
  id bigint primary key
);

create sequence public.__default_grant_probe_seq;

create function public.__default_grant_probe_fn()
returns integer
language sql
as $$ select 1 $$;

create function extensions.__default_grant_probe_fn()
returns integer
language sql
as $$ select 1 $$;

select ok(
  not exists (
    select 1
    from (values ('anon'), ('authenticated'), ('service_role')) as roles(role_name)
    cross join (values ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE'), ('TRUNCATE'), ('REFERENCES'), ('TRIGGER')) as privileges(privilege_name)
    where has_table_privilege(
      roles.role_name,
      'public.__default_grant_probe',
      privileges.privilege_name
    )
  ),
  'future public tables require explicit grants'
);

select ok(
  not exists (
    select 1
    from (values ('anon'), ('authenticated'), ('service_role')) as roles(role_name)
    cross join (values ('USAGE'), ('SELECT'), ('UPDATE')) as privileges(privilege_name)
    where has_sequence_privilege(
      roles.role_name,
      'public.__default_grant_probe_seq',
      privileges.privilege_name
    )
  ),
  'future public sequences require explicit grants'
);

-- Inspect the function ACL itself rather than effective privileges. Supabase's
-- privileged service role can gain effective capability through platform role
-- relationships; the fail-closed contract here is that creating an application
-- function does not automatically GRANT EXECUTE to PUBLIC or any Data API role.
select ok(
  not exists (
    select 1
    from pg_proc p
    cross join lateral aclexplode(
      coalesce(p.proacl, acldefault('f', p.proowner))
    ) as acl
    where p.oid = 'public.__default_grant_probe_fn()'::regprocedure
      and acl.privilege_type = 'EXECUTE'
      and (
        acl.grantee = 0
        or acl.grantee in (
          select oid
          from pg_roles
          where rolname in ('anon', 'authenticated', 'service_role')
        )
      )
  ),
  'future public functions require explicit grants'
);

select ok(
  exists (
    select 1
    from pg_proc p
    cross join lateral aclexplode(
      coalesce(p.proacl, acldefault('f', p.proowner))
    ) as acl
    where p.oid = 'extensions.__default_grant_probe_fn()'::regprocedure
      and acl.privilege_type = 'EXECUTE'
      and acl.grantee = 0
  ),
  'future extension functions retain PUBLIC execute'
);

select ok(
  not exists (
    select 1
    from (values ('anon'), ('authenticated')) as roles(role_name)
    cross join (values ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE'), ('TRUNCATE'), ('REFERENCES'), ('TRIGGER')) as privileges(privilege_name)
    where has_table_privilege(
      roles.role_name,
      'public.worker_heartbeats',
      privileges.privilege_name
    )
  ),
  'browser roles have no worker heartbeat privileges'
);

select ok(
  has_table_privilege('service_role', 'public.worker_heartbeats', 'SELECT')
  and has_table_privilege('service_role', 'public.worker_heartbeats', 'INSERT')
  and has_table_privilege('service_role', 'public.worker_heartbeats', 'UPDATE')
  and has_table_privilege('service_role', 'public.worker_heartbeats', 'DELETE'),
  'service role retains worker heartbeat CRUD access'
);

select * from finish();

rollback;
