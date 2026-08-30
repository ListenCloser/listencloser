begin;

select plan(10);

-- Exercise row-level security as the same Postgres role used by authenticated
-- Supabase requests. auth.uid() reads request.jwt.claim.sub, so deterministic
-- UUID claims are enough to test policy behavior without provisioning Auth users.
set local role authenticated;

select set_config('request.jwt.claim.sub', '11111111-1111-1111-1111-111111111111', true);

insert into public.projects (id, owner_id, name, description)
values (
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  '11111111-1111-1111-1111-111111111111',
  'User A project',
  ''
);

insert into public.works (id, project_id, title)
values (
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'User A work'
);

insert into public.workflows (id, project_id, kind)
values (
  'cccccccc-cccc-cccc-cccc-cccccccccccc',
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'understand'
);

select is(
  (select count(*) from public.projects where id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'),
  1::bigint,
  'owner can select own project'
);

select is(
  (select count(*) from public.works where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'),
  1::bigint,
  'owner can select work through project ownership'
);

select set_config('request.jwt.claim.sub', '22222222-2222-2222-2222-222222222222', true);

select is(
  (select count(*) from public.projects where id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'),
  0::bigint,
  'foreign project is invisible'
);

select is(
  (select count(*) from public.works where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'),
  0::bigint,
  'foreign work is invisible through ownership chain'
);

select is(
  (
    with changed as (
      update public.projects
      set name = 'Hijacked'
      where id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
      returning 1
    )
    select count(*) from changed
  ),
  0::bigint,
  'foreign project update affects no rows'
);

select is(
  (
    with changed as (
      update public.works
      set title = 'Hijacked'
      where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
      returning 1
    )
    select count(*) from changed
  ),
  0::bigint,
  'foreign work update affects no rows'
);

select is(
  (
    with removed as (
      delete from public.works
      where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
      returning 1
    )
    select count(*) from removed
  ),
  0::bigint,
  'foreign work delete affects no rows'
);

select throws_ok(
  $$
    insert into public.works (project_id, title)
    values ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Foreign insert')
  $$,
  '42501',
  null,
  'cannot insert a work into another user project'
);

select set_config('request.jwt.claim.sub', '11111111-1111-1111-1111-111111111111', true);

select throws_ok(
  $$
    insert into public.jobs (
      workflow_id,
      capability_name,
      capability_version
    ) values (
      'cccccccc-cccc-cccc-cccc-cccccccccccc',
      'understand',
      '1.0'
    )
  $$,
  '42501',
  null,
  'authenticated owners cannot write backend-managed jobs'
);

insert into public.workspace_states (
  id,
  project_id,
  owner_id,
  tab
) values (
  'dddddddd-dddd-dddd-dddd-dddddddddddd',
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  '11111111-1111-1111-1111-111111111111',
  'analyze'
);

select set_config('request.jwt.claim.sub', '22222222-2222-2222-2222-222222222222', true);

select is(
  (select count(*) from public.workspace_states where id = 'dddddddd-dddd-dddd-dddd-dddddddddddd'),
  0::bigint,
  'workspace state is isolated by owner'
);

select * from finish();

rollback;
