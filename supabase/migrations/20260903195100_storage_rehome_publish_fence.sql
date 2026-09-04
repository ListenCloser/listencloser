-- Publish one verified storage re-home Version only if its source is still
-- the latest Version for the Artifact at the database write boundary.
--
-- The operator performs Storage copy/verification before this RPC. The
-- table lock is therefore held only around the short latest-check+insert
-- transaction. SHARE ROW EXCLUSIVE conflicts with ordinary INSERT/UPDATE/
-- DELETE RowExclusive locks, so no Version write can slip between the
-- authoritative recheck and replacement publication.
begin;

create function public.publish_storage_rehome_version(
  p_source_version_id uuid,
  p_version jsonb
)
returns setof public.artifact_versions
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_source public.artifact_versions%rowtype;
  v_requested public.artifact_versions%rowtype;
  v_existing public.artifact_versions%rowtype;
  v_latest_id uuid;
begin
  if jsonb_typeof(p_version) <> 'object' then
    raise exception using
      errcode = '22023',
      message = 'storage re-home publication requires one Version object';
  end if;

  -- Serialize the authoritative check with every ordinary Version write.
  -- Storage I/O has already completed before this RPC is called.
  lock table public.artifact_versions in share row exclusive mode;

  select *
  into v_source
  from public.artifact_versions
  where id = p_source_version_id;

  if not found then
    raise exception using
      errcode = '22023',
      message = 'storage re-home source Version does not exist';
  end if;

  select *
  into v_requested
  from jsonb_populate_record(null::public.artifact_versions, p_version);

  if v_requested.id is null
    or v_requested.artifact_id is distinct from v_source.artifact_id
    or v_requested.parent_version_id is distinct from v_source.id then
    raise exception using
      errcode = '22023',
      message = 'storage re-home replacement must parent the selected source Artifact Version';
  end if;

  if v_requested.produced_by_job_id is not null then
    raise exception using
      errcode = '22023',
      message = 'storage re-home replacement cannot claim worker provenance';
  end if;

  -- A retry after an uncertain network outcome is idempotent. Accept the
  -- deterministic row only when all durable content/lineage fields match.
  select *
  into v_existing
  from public.artifact_versions
  where id = v_requested.id;

  if found then
    if v_existing.artifact_id is distinct from v_requested.artifact_id
      or v_existing.parent_version_id is distinct from v_requested.parent_version_id
      or v_existing.lineage is distinct from v_requested.lineage
      or v_existing.storage_bucket is distinct from v_requested.storage_bucket
      or v_existing.storage_key is distinct from v_requested.storage_key
      or v_existing.byte_size is distinct from v_requested.byte_size
      or v_existing.sha256 is distinct from v_requested.sha256
      or v_existing.metadata is distinct from v_requested.metadata
      or v_existing.label is distinct from v_requested.label
      or v_existing.created_by is distinct from v_requested.created_by
      or v_existing.produced_by_job_id is distinct from v_requested.produced_by_job_id then
      raise exception using
        errcode = '23505',
        message = 'deterministic storage re-home replacement conflicts with existing state';
    end if;
    return next v_existing;
    return;
  end if;

  select version.id
  into v_latest_id
  from public.artifact_versions as version
  where version.artifact_id = v_source.artifact_id
  order by version.created_at desc, version.id::text desc
  limit 1;

  if v_latest_id is distinct from v_source.id then
    raise exception using
      errcode = 'P0001',
      message = 'storage re-home source Version is no longer latest';
  end if;

  insert into public.artifact_versions as published (
    id,
    artifact_id,
    parent_version_id,
    lineage,
    storage_key,
    storage_bucket,
    byte_size,
    sha256,
    label,
    metadata,
    created_at,
    created_by,
    produced_by_job_id
  ) values (
    v_requested.id,
    v_requested.artifact_id,
    v_requested.parent_version_id,
    coalesce(v_requested.lineage, '{}'::uuid[]),
    v_requested.storage_key,
    v_requested.storage_bucket,
    v_requested.byte_size,
    v_requested.sha256,
    coalesce(v_requested.label, ''),
    coalesce(v_requested.metadata, '{}'::jsonb),
    coalesce(v_requested.created_at, clock_timestamp()),
    v_requested.created_by,
    null
  )
  returning published.* into v_existing;

  return next v_existing;
  return;
end;
$$;

comment on function public.publish_storage_rehome_version(uuid, jsonb) is
  'Serializes Version writes, rechecks source latestness, and atomically publishes one deterministic storage re-home replacement.';

revoke all on function public.publish_storage_rehome_version(uuid, jsonb) from public;
revoke all on function public.publish_storage_rehome_version(uuid, jsonb) from anon;
revoke all on function public.publish_storage_rehome_version(uuid, jsonb) from authenticated;
grant execute on function public.publish_storage_rehome_version(uuid, jsonb) to service_role;

commit;
