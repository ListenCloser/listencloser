begin;

select plan(18);

-- Seed the durable graph as the database owner. Derived domain state is
-- server-owned, while Projects/Works remain user-owned through RLS.
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

insert into public.artifacts (id, work_id, kind)
values (
  'dddddddd-dddd-dddd-dddd-dddddddddddd',
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'audio_original'
);

insert into public.artifact_versions (
  id,
  artifact_id,
  storage_key,
  storage_bucket,
  lineage
) values (
  'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
  'dddddddd-dddd-dddd-dddd-dddddddddddd',
  'rls-test/source.wav',
  'artifacts',
  array[]::uuid[]
);

insert into public.workflows (id, project_id, kind)
values (
  'cccccccc-cccc-cccc-cccc-cccccccccccc',
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'understand'
);

insert into public.jobs (
  id,
  workflow_id,
  capability_name,
  capability_version,
  stage
) values (
  'ffffffff-ffff-ffff-ffff-ffffffffffff',
  'cccccccc-cccc-cccc-cccc-cccccccccccc',
  'understand',
  '1.0',
  'queued'
);

-- Exercise RLS as the same Postgres role used by authenticated Supabase
-- requests. auth.uid() reads request.jwt.claim.sub, so deterministic UUID claims
-- are sufficient for policy tests; real Auth/JWT/PostgREST wiring stays in the
-- thin Python smoke test.
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
  'owner can select own work'
);
select is(
  (select count(*) from public.artifacts where id = 'dddddddd-dddd-dddd-dddd-dddddddddddd'),
  1::bigint,
  'owner can select server-owned artifact through work ownership'
);
select is(
  (select count(*) from public.artifact_versions where id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'),
  1::bigint,
  'owner can select server-owned version through artifact ownership'
);
select is(
  (select count(*) from public.workflows where id = 'cccccccc-cccc-cccc-cccc-cccccccccccc'),
  1::bigint,
  'owner can select server-owned workflow through project ownership'
);
select is(
  (select count(*) from public.jobs where id = 'ffffffff-ffff-ffff-ffff-ffffffffffff'),
  1::bigint,
  'owner can select server-owned job through workflow ownership'
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
  'foreign work is invisible'
);
select is(
  (select count(*) from public.artifacts where id = 'dddddddd-dddd-dddd-dddd-dddddddddddd'),
  0::bigint,
  'foreign artifact is invisible'
);
select is(
  (select count(*) from public.artifact_versions where id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'),
  0::bigint,
  'foreign artifact version is invisible'
);
select is(
  (select count(*) from public.workflows where id = 'cccccccc-cccc-cccc-cccc-cccccccccccc'),
  0::bigint,
  'foreign workflow is invisible'
);
select is(
  (select count(*) from public.jobs where id = 'ffffffff-ffff-ffff-ffff-ffffffffffff'),
  0::bigint,
  'foreign job is invisible'
);

-- RLS-filtered UPDATE/DELETE statements succeed at the SQL level but affect no
-- rows. Execute them as user B, then inspect durable state as the database owner.
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
  '99999999-9999-9999-9999-999999999999',
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  '11111111-1111-1111-1111-111111111111',
  'analyze'
);

select set_config('request.jwt.claim.sub', '22222222-2222-2222-2222-222222222222', true);

select is(
  (select count(*) from public.workspace_states where id = '99999999-9999-9999-9999-999999999999'),
  0::bigint,
  'workspace state is isolated by owner'
);

select * from finish();

rollback;
