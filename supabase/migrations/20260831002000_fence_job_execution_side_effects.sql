-- Fence product-visible worker side effects to one exact lease/claim generation.
--
-- Queue delivery remains at-least-once. Inference is deliberately not wrapped in
-- a database transaction; only the short persistence statement locks the Job
-- row, checks the execution token, and mutates output rows atomically.

alter table public.jobs
  add column execution_token uuid;

comment on column public.jobs.execution_token is
  'Fresh per-claim generation token used to fence worker lifecycle and product-visible persistence.';

create or replace function public.claim_next_job(
  p_worker_id text,
  p_lease_seconds double precision default 30.0
)
returns setof public.jobs
language sql
security definer
set search_path = ''
as $$
  with next_job as (
    select id
    from public.jobs
    where stage = 'queued'
    order by created_at asc
    for update skip locked
    limit 1
  )
  update public.jobs as j
  set
    stage = 'claimed',
    worker_id = p_worker_id,
    lease_expires_at = now() + make_interval(secs => p_lease_seconds),
    execution_token = gen_random_uuid()
  from next_job
  where j.id = next_job.id
  returning j.*;
$$;

revoke all on function public.claim_next_job(text, double precision) from public;
revoke all on function public.claim_next_job(text, double precision) from anon, authenticated;
grant execute on function public.claim_next_job(text, double precision) to service_role;

create function public.fenced_job_publish_version(
  p_job_id uuid,
  p_execution_token uuid,
  p_artifact jsonb,
  p_version jsonb
)
returns setof jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_workflow_id uuid;
  v_artifact public.artifacts%rowtype;
  v_version public.artifact_versions%rowtype;
  v_published jsonb;
begin
  if jsonb_typeof(p_artifact) <> 'object' or jsonb_typeof(p_version) <> 'object' then
    raise exception using
      errcode = '22023',
      message = 'fenced version publication requires one Artifact and one Version object';
  end if;

  select workflow_id
  into v_workflow_id
  from public.jobs
  where id = p_job_id
    and stage = 'running'
    and execution_token = p_execution_token
  for update;

  if not found then
    raise exception using
      errcode = 'P0001',
      message = 'stale job execution cannot publish output';
  end if;

  select *
  into v_artifact
  from jsonb_populate_record(null::public.artifacts, p_artifact);

  select *
  into v_version
  from jsonb_populate_record(null::public.artifact_versions, p_version);

  if v_artifact.id is null
    or v_version.id is null
    or v_version.artifact_id is distinct from v_artifact.id then
    raise exception using
      errcode = '22023',
      message = 'fenced Version must reference its paired Artifact';
  end if;

  if not exists (
    select 1
    from public.works w
    join public.workflows wf on wf.project_id = w.project_id
    where wf.id = v_workflow_id
      and w.id = v_artifact.work_id
  ) then
    raise exception using
      errcode = '42501',
      message = 'job cannot publish an Artifact outside its Workflow project';
  end if;

  insert into public.artifacts (
    id,
    work_id,
    kind,
    mime_type,
    created_at
  ) values (
    v_artifact.id,
    v_artifact.work_id,
    v_artifact.kind,
    v_artifact.mime_type,
    coalesce(v_artifact.created_at, now())
  );

  insert into public.artifact_versions as published (
    id,
    artifact_id,
    parent_version_id,
    lineage,
    storage_bucket,
    storage_key,
    byte_size,
    sha256,
    metadata,
    label,
    produced_by_job_id,
    created_at,
    created_by
  ) values (
    v_version.id,
    v_version.artifact_id,
    v_version.parent_version_id,
    coalesce(v_version.lineage, '{}'::uuid[]),
    v_version.storage_bucket,
    v_version.storage_key,
    v_version.byte_size,
    v_version.sha256,
    coalesce(v_version.metadata, '{}'::jsonb),
    v_version.label,
    p_job_id,
    coalesce(v_version.created_at, now()),
    v_version.created_by
  )
  returning to_jsonb(published)
  into v_published;

  return next v_published;
  return;
end;
$$;

comment on function public.fenced_job_publish_version(uuid, uuid, jsonb, jsonb) is
  'Atomically locks the current Job attempt and publishes one Artifact+Version pair.';

create function public.fenced_job_insert(
  p_job_id uuid,
  p_execution_token uuid,
  p_table text,
  p_rows jsonb
)
returns setof jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_input_version_ids uuid[];
  v_rows jsonb;
  v_relation regclass;
  v_columns text;
  v_select text;
begin
  if p_table is null or p_table not in ('entities', 'insights', 'alignments') then
    raise exception using
      errcode = '22023',
      message = 'unsupported fenced output table';
  end if;

  if jsonb_typeof(p_rows) = 'object' then
    v_rows := jsonb_build_array(p_rows);
  elsif jsonb_typeof(p_rows) = 'array' then
    v_rows := p_rows;
  else
    raise exception using
      errcode = '22023',
      message = 'fenced output rows must be a JSON object or array';
  end if;

  if jsonb_array_length(v_rows) = 0 then
    return;
  end if;

  if exists (
    select 1
    from jsonb_array_elements(v_rows) as element
    where jsonb_typeof(element) <> 'object'
  ) then
    raise exception using
      errcode = '22023',
      message = 'every fenced output row must be a JSON object';
  end if;

  select input_version_ids
  into v_input_version_ids
  from public.jobs
  where id = p_job_id
    and stage = 'running'
    and execution_token = p_execution_token
  for update;

  if not found then
    raise exception using
      errcode = 'P0001',
      message = 'stale job execution cannot publish output';
  end if;

  -- Evidence may attach either to one of the Job's declared inputs or to a
  -- Version that this same logical Job has already published (composite flows
  -- such as understand/variation use the latter).
  if p_table in ('entities', 'insights') and exists (
    select 1
    from jsonb_array_elements(v_rows) as element
    where not exists (
      select 1
      from public.artifact_versions av
      where av.id = (element ->> 'version_id')::uuid
        and (
          av.id = any(v_input_version_ids)
          or av.produced_by_job_id = p_job_id
        )
    )
  ) then
    raise exception using
      errcode = '42501',
      message = 'job output references a Version outside its input/output graph';
  end if;

  if p_table = 'alignments' and exists (
    select 1
    from jsonb_array_elements(v_rows) as element
    where not exists (
      select 1
      from public.artifact_versions av
      where av.id = (element ->> 'version_id')::uuid
        and (av.id = any(v_input_version_ids) or av.produced_by_job_id = p_job_id)
    )
    or not exists (
      select 1
      from public.artifact_versions av
      where av.id = (element ->> 'target_version_id')::uuid
        and (av.id = any(v_input_version_ids) or av.produced_by_job_id = p_job_id)
    )
  ) then
    raise exception using
      errcode = '42501',
      message = 'job Alignment references a Version outside its input/output graph';
  end if;

  if p_table in ('insights', 'alignments') then
    select jsonb_agg(element || jsonb_build_object('produced_by_job_id', p_job_id))
    into v_rows
    from jsonb_array_elements(v_rows) as element;
  end if;

  v_relation := to_regclass(format('public.%I', p_table));

  if exists (
    select 1
    from jsonb_array_elements(v_rows) as element
    cross join lateral jsonb_object_keys(element) as supplied(key)
    where not exists (
      select 1
      from pg_catalog.pg_attribute attribute
      where attribute.attrelid = v_relation
        and attribute.attnum > 0
        and not attribute.attisdropped
        and attribute.attname = supplied.key
    )
  ) then
    raise exception using
      errcode = '22023',
      message = 'fenced output contains an unknown table column';
  end if;

  select
    string_agg(format('%I', attribute.attname), ', ' order by attribute.attnum),
    string_agg(format('populated.%I', attribute.attname), ', ' order by attribute.attnum)
  into v_columns, v_select
  from pg_catalog.pg_attribute attribute
  where attribute.attrelid = v_relation
    and attribute.attnum > 0
    and not attribute.attisdropped
    and exists (
      select 1
      from jsonb_array_elements(v_rows) as element
      where element ? attribute.attname
    );

  if v_columns is null then
    raise exception using
      errcode = '22023',
      message = 'fenced output contains no insertable columns';
  end if;

  return query execute format(
    'with inserted as (
       insert into public.%I (%s)
       select %s
       from jsonb_populate_recordset(null::public.%I, $1) as populated
       returning *
     )
     select to_jsonb(inserted) from inserted',
    p_table,
    v_columns,
    v_select,
    p_table
  ) using v_rows;
end;
$$;

comment on function public.fenced_job_insert(uuid, uuid, text, jsonb) is
  'Locks the current Job attempt, then inserts admitted Entity/Insight/Alignment rows in the same transaction.';

create function public.fenced_job_delete(
  p_job_id uuid,
  p_execution_token uuid,
  p_table text,
  p_match jsonb
)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_retry_of uuid;
  v_count integer;
begin
  select case
    when provenance ? 'retry_of_job_id'
      and (provenance ->> 'retry_of_job_id') <> ''
    then (provenance ->> 'retry_of_job_id')::uuid
    else null
  end
  into v_retry_of
  from public.jobs
  where id = p_job_id
    and stage = 'running'
    and execution_token = p_execution_token
  for update;

  if not found then
    raise exception using
      errcode = 'P0001',
      message = 'stale job execution cannot mutate output';
  end if;

  if p_table = 'artifacts'
    and jsonb_typeof(p_match -> 'id_in') = 'array'
    and (select count(*) from jsonb_object_keys(p_match)) = 1 then
    delete from public.artifacts artifact
    where artifact.id in (
      select value::uuid
      from jsonb_array_elements_text(p_match -> 'id_in') as requested(value)
    )
    and exists (
      select 1
      from public.artifact_versions av
      where av.artifact_id = artifact.id
        and (
          av.produced_by_job_id = p_job_id
          or (v_retry_of is not null and av.produced_by_job_id = v_retry_of)
        )
    )
    and not exists (
      select 1
      from public.artifact_versions av
      where av.artifact_id = artifact.id
        and av.produced_by_job_id is distinct from p_job_id
        and (v_retry_of is null or av.produced_by_job_id is distinct from v_retry_of)
    );
  elsif p_table = 'entities'
    and p_match ? 'version_id'
    and p_match ? 'kind'
    and (select count(*) from jsonb_object_keys(p_match)) = 2 then
    delete from public.entities entity
    where entity.version_id = (p_match ->> 'version_id')::uuid
      and entity.kind::text = p_match ->> 'kind'
      and exists (
        select 1
        from public.artifact_versions av
        where av.id = entity.version_id
          and av.produced_by_job_id = p_job_id
      );
  else
    raise exception using
      errcode = '22023',
      message = 'unsupported fenced output delete';
  end if;

  get diagnostics v_count = row_count;
  return v_count;
end;
$$;

comment on function public.fenced_job_delete(uuid, uuid, text, jsonb) is
  'Locks the current Job attempt before the two admitted worker output-cleanup delete shapes.';

revoke all on function public.fenced_job_publish_version(uuid, uuid, jsonb, jsonb) from public;
revoke all on function public.fenced_job_publish_version(uuid, uuid, jsonb, jsonb) from anon, authenticated;
grant execute on function public.fenced_job_publish_version(uuid, uuid, jsonb, jsonb) to service_role;

revoke all on function public.fenced_job_insert(uuid, uuid, text, jsonb) from public;
revoke all on function public.fenced_job_insert(uuid, uuid, text, jsonb) from anon, authenticated;
grant execute on function public.fenced_job_insert(uuid, uuid, text, jsonb) to service_role;

revoke all on function public.fenced_job_delete(uuid, uuid, text, jsonb) from public;
revoke all on function public.fenced_job_delete(uuid, uuid, text, jsonb) from anon, authenticated;
grant execute on function public.fenced_job_delete(uuid, uuid, text, jsonb) to service_role;
