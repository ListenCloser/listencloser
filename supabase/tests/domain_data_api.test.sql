begin;

select plan(2);

select ok(
  not exists (
    select 1
    from (
      values
        ('projects'),
        ('works'),
        ('artifacts'),
        ('artifact_versions'),
        ('entities'),
        ('insights'),
        ('alignments'),
        ('workflows'),
        ('jobs'),
        ('workspace_states'),
        ('worker_heartbeats')
    ) as tables(table_name)
    cross join (values ('anon'), ('authenticated')) as roles(role_name)
    cross join (
      values
        ('SELECT'),
        ('INSERT'),
        ('UPDATE'),
        ('DELETE'),
        ('TRUNCATE'),
        ('REFERENCES'),
        ('TRIGGER')
    ) as privileges(privilege_name)
    where has_table_privilege(
      roles.role_name,
      format('public.%I', tables.table_name),
      privileges.privilege_name
    )
  ),
  'browser roles have no direct privileges on domain tables'
);

select ok(
  not exists (
    select 1
    from (
      values
        ('projects'),
        ('works'),
        ('artifacts'),
        ('artifact_versions'),
        ('entities'),
        ('insights'),
        ('alignments'),
        ('workflows'),
        ('jobs'),
        ('workspace_states'),
        ('worker_heartbeats')
    ) as tables(table_name)
    cross join (values ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE')) as privileges(privilege_name)
    where not has_table_privilege(
      'service_role',
      format('public.%I', tables.table_name),
      privileges.privilege_name
    )
  ),
  'service role retains domain CRUD privileges'
);

select * from finish();

rollback;
