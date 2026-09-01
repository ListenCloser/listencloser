begin;

select plan(2);

insert into public.projects (id, owner_id, name)
values
  (
    '10000000-0000-4000-8000-000000000001',
    '11111111-1111-1111-1111-111111111111',
    'Owner A project'
  ),
  (
    '20000000-0000-4000-8000-000000000002',
    '22222222-2222-2222-2222-222222222222',
    'Owner B project'
  );

insert into public.works (id, project_id, title)
values (
  '30000000-0000-4000-8000-000000000003',
  '10000000-0000-4000-8000-000000000001',
  'Owner A work'
);

-- Production browser table ACLs are revoked. Grant only inside this rollback-only
-- test so the retained RLS safety net can be exercised directly.
grant select, update on table public.projects, public.works to authenticated;

set local role authenticated;
select set_config(
  'request.jwt.claim.sub',
  '11111111-1111-1111-1111-111111111111',
  true
);

select throws_ok(
  $$
    update public.projects
    set owner_id = '22222222-2222-2222-2222-222222222222'
    where id = '10000000-0000-4000-8000-000000000001'
  $$,
  '42501',
  null,
  'project owner cannot reassign an owned row to another owner'
);

select throws_ok(
  $$
    update public.works
    set project_id = '20000000-0000-4000-8000-000000000002'
    where id = '30000000-0000-4000-8000-000000000003'
  $$,
  '42501',
  null,
  'work owner cannot re-parent an owned row into another owner project'
);

select * from finish();

rollback;
