-- Fence one-off historical Storage re-home publication at the durable Version
-- insert boundary.
--
-- The operator may spend time reading/copying Storage bytes after its audit
-- snapshot. A normal writer can publish a newer Version during that work. Every
-- Version insert therefore takes the same parent-Artifact KEY SHARE lock that
-- the FK requires, but takes it at the beginning of the BEFORE INSERT trigger.
-- Recovery inserts alone upgrade that parent lock to FOR UPDATE before checking
-- latest authority. That makes a competing insert either commit first and become
-- visible to the recovery check, or wait until the recovery transaction ends.

create function public.enforce_storage_locator_rehome_fence()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_source public.artifact_versions%rowtype;
  v_artifact public.artifacts%rowtype;
  v_owner_id uuid;
  v_project_id uuid;
  v_latest_id uuid;
  v_expected_lineage uuid[];
begin
  -- Acquire the ordinary FK-compatible parent lock before returning from this
  -- trigger, rather than waiting for PostgreSQL's later FK check. This is the
  -- coordination point that allows a recovery insert to take an exclusive row
  -- lock and make the latest check race-free.
  perform 1
  from public.artifacts
  where id = new.artifact_id
  for key share;

  if coalesce(new.metadata, '{}'::jsonb) #>> '{storage_locator_rehome,method}'
     is distinct from 'storage_locator_rehome_v1' then
    return new;
  end if;

  if new.parent_version_id is null then
    raise exception using
      errcode = '42501',
      message = 'storage re-home replacement requires a source parent Version';
  end if;

  select *
  into v_source
  from public.artifact_versions
  where id = new.parent_version_id;

  if not found then
    raise exception using
      errcode = '23503',
      message = 'storage re-home source Version does not exist';
  end if;

  -- Upgrade the same parent row to FOR UPDATE. Any ordinary Version insert that
  -- reached this trigger first holds KEY SHARE until its transaction commits;
  -- any insert arriving later blocks at the KEY SHARE acquisition above.
  select *
  into v_artifact
  from public.artifacts
  where id = v_source.artifact_id
  for update;

  if not found then
    raise exception using
      errcode = '23503',
      message = 'storage re-home source Artifact does not exist';
  end if;

  select project.id, project.owner_id
  into v_project_id, v_owner_id
  from public.works work
  join public.projects project on project.id = work.project_id
  where work.id = v_artifact.work_id;

  if v_project_id is null or v_owner_id is null then
    raise exception using
      errcode = '42501',
      message = 'storage re-home source has no authoritative Project owner';
  end if;

  v_expected_lineage := coalesce(v_source.lineage, '{}'::uuid[]);
  if not (v_source.id = any(v_expected_lineage)) then
    v_expected_lineage := array_append(v_expected_lineage, v_source.id);
  end if;

  if new.artifact_id is distinct from v_source.artifact_id
    or new.lineage is distinct from v_expected_lineage
    or new.storage_bucket is distinct from 'artifacts'
    or new.storage_key is null
    or new.storage_key not like format(
      '%s/%s/%s/%%',
      v_owner_id::text,
      v_project_id::text,
      v_source.artifact_id::text
    )
    or new.byte_size is null
    or new.sha256 is null
    or new.created_by is distinct from v_owner_id
    or new.produced_by_job_id is not null
    or new.metadata #>> '{storage_locator_rehome,source_version_id}'
       is distinct from v_source.id::text then
    raise exception using
      errcode = '42501',
      message = 'replacement Version violates storage re-home authority contract';
  end if;

  select id
  into v_latest_id
  from public.artifact_versions
  where artifact_id = v_source.artifact_id
  order by created_at desc, id desc
  limit 1;

  if v_latest_id is distinct from v_source.id then
    raise exception using
      errcode = 'P0001',
      message = 'storage re-home source is no longer latest';
  end if;

  if (new.created_at, new.id) <= (v_source.created_at, v_source.id) then
    raise exception using
      errcode = '22023',
      message = 'storage re-home replacement must advance canonical Version ordering';
  end if;

  if not exists (
    select 1
    from storage.objects object
    where object.bucket_id = new.storage_bucket
      and object.name = new.storage_key
  ) then
    raise exception using
      errcode = '42501',
      message = 'replacement Storage object does not exist in declared bucket';
  end if;

  return new;
end;
$$;

comment on function public.enforce_storage_locator_rehome_fence() is
  'Serializes Version inserts on their Artifact and atomically revalidates storage_locator_rehome_v1 latest authority.';

revoke all on function public.enforce_storage_locator_rehome_fence() from public;
revoke all on function public.enforce_storage_locator_rehome_fence() from anon, authenticated;

create trigger artifact_versions_storage_locator_rehome_fence
before insert on public.artifact_versions
for each row
execute function public.enforce_storage_locator_rehome_fence();
