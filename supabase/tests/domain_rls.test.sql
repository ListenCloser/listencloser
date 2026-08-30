begin;

select plan(10);

-- Seed server-owned lineage as the database owner. Browser roles deliberately
-- cannot create Workflows/Jobs after the server-owned-domain migration.
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

-- Exercise row-level security as the same Postgres role used by authenticated
-- Supabase requests. auth.uid() reads request.jwt.claim.sub, so deterministic
-- UUID claims are enough to test policy behavior without provisioning Auth users.
set local role authenticated;
select set_config('request.jwt.claim.sub', '11111111-1111-1111-1111-111111111111', true);

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

-- RLS-filtered UPDATE/DELETE statements succeed at the SQL level but affect no
-- rows. Execute them as user B, then inspect the durable state as the database
-- owner instead of wrapping data-modifying CTEs inside pgTAP assertions.
update public.projects
set name = 'Hijacked'
where id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

update public.works
set title = 'Hijacked'
where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';

delete from public.works
where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';

reset role;

select is(
  (select name from public.projects where id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'),
  'User A project',
  'foreign project update is blocked'
);

select is(
  (select title from public.works where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'),
  'User A work',
  'foreign work update is blocked'
);

select is(
  (select count(*) from public.works where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'),
  1::bigint,
  'foreign work delete is blocked'
);

set local role authenticated;
select set_config('request.jwt.claim.sub', '22222222-2222-2222-2222-222222222222', true);

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
