begin;

select plan(6);

select ok(
  not exists (
    select 1
    from pg_default_acl d
    join pg_roles owner_role on owner_role.oid = d.defaclrole
    join pg_namespace n on n.oid = d.defaclnamespace
    cross join lateral aclexplode(d.defaclacl) acl
    where owner_role.rolname = 'postgres'
      and n.nspname = 'public'
      and d.defaclobjtype = 'r'
      and acl.grantee in (
        select oid from pg_roles where rolname in ('anon', 'authenticated', 'service_role')
      )
  ),
  'future public tables require explicit Data API grants'
);

select ok(
  not exists (
    select 1
    from pg_default_acl d
    join pg_roles owner_role on owner_role.oid = d.defaclrole
    join pg_namespace n on n.oid = d.defaclnamespace
    cross join lateral aclexplode(d.defaclacl) acl
    where owner_role.rolname = 'postgres'
      and n.nspname = 'public'
      and d.defaclobjtype = 'S'
      and acl.grantee in (
        select oid from pg_roles where rolname in ('anon', 'authenticated', 'service_role')
      )
  ),
  'future public sequences require explicit Data API grants'
);

select ok(
  not exists (
    select 1
    from pg_default_acl d
    join pg_roles owner_role on owner_role.oid = d.defaclrole
    join pg_namespace n on n.oid = d.defaclnamespace
    cross join lateral aclexplode(d.defaclacl) acl
    where owner_role.rolname = 'postgres'
      and n.nspname = 'public'
      and d.defaclobjtype = 'f'
      and (
        acl.grantee = 0
        or acl.grantee in (
          select oid from pg_roles where rolname in ('anon', 'authenticated', 'service_role')
        )
      )
  ),
  'future public functions require explicit execute grants'
);

select is(
  (
    select count(*)
    from information_schema.role_table_grants
    where table_schema = 'public'
      and table_name = 'worker_heartbeats'
      and grantee in ('anon', 'authenticated')
  ),
  0::bigint,
  'worker_heartbeats has no browser table privileges'
);

select ok(
  has_table_privilege('service_role', 'public.worker_heartbeats', 'SELECT')
  and has_table_privilege('service_role', 'public.worker_heartbeats', 'INSERT')
  and has_table_privilege('service_role', 'public.worker_heartbeats', 'UPDATE')
  and has_table_privilege('service_role', 'public.worker_heartbeats', 'DELETE'),
  'worker_heartbeats remains writable by the service role'
);

select ok(
  not exists (
    select 1
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.prosecdef
      and (
        has_function_privilege('anon', p.oid, 'EXECUTE')
        or has_function_privilege('authenticated', p.oid, 'EXECUTE')
      )
  ),
  'no browser-executable SECURITY DEFINER function exists in public'
);

select * from finish();
rollback;
