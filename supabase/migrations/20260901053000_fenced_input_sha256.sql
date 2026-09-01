-- Establish exact-byte identity for declared Job inputs on bytes the worker already reads.
--
-- Browser uploads may finalize a Version before a trusted digest is known. The first
-- normal worker read can measure those stored bytes, but enrichment must stay inside
-- the execution-attempt authority boundary: only a current running Job may enrich one
-- of its declared input locators, NULL may move to the measured digest, identical
-- retries are idempotent, and conflicting history fails closed.

create function public.fenced_job_verify_input_sha256(
  p_job_id uuid,
  p_execution_token uuid,
  p_storage_bucket text,
  p_storage_key text,
  p_sha256 text
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_input_version_ids uuid[];
begin
  if p_sha256 is null or p_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023',
      message = 'verified SHA-256 must be 64 lowercase hex characters';
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
      message = 'stale job execution cannot verify input integrity';
  end if;

  -- Lock every declared input Version that resolves to the exact Storage object
  -- already downloaded by the worker. Composite workflows also read same-Job
  -- generated outputs through this Storage facade; those are deliberately a no-op
  -- here because generated-output identity is established at publication time.
  perform 1
  from public.artifact_versions version
  where version.id = any(coalesce(v_input_version_ids, '{}'::uuid[]))
    and version.storage_bucket = p_storage_bucket
    and version.storage_key = p_storage_key
  for update;

  if not found then
    return false;
  end if;

  if exists (
    select 1
    from public.artifact_versions version
    where version.id = any(coalesce(v_input_version_ids, '{}'::uuid[]))
      and version.storage_bucket = p_storage_bucket
      and version.storage_key = p_storage_key
      and version.sha256 is not null
      and version.sha256 <> p_sha256
  ) then
    raise exception using
      errcode = '22000',
      message = 'stored Version SHA-256 conflicts with verified bytes';
  end if;

  update public.artifact_versions as version
  set sha256 = p_sha256
  where version.id = any(coalesce(v_input_version_ids, '{}'::uuid[]))
    and version.storage_bucket = p_storage_bucket
    and version.storage_key = p_storage_key
    and version.sha256 is null;

  return true;
end;
$$;

comment on function public.fenced_job_verify_input_sha256(uuid, uuid, text, text, text) is
  'Locks the current Job attempt and monotonically verifies SHA-256 for an exact declared-input Storage locator.';

revoke all on function public.fenced_job_verify_input_sha256(uuid, uuid, text, text, text) from public;
revoke all on function public.fenced_job_verify_input_sha256(uuid, uuid, text, text, text) from anon, authenticated;
grant execute on function public.fenced_job_verify_input_sha256(uuid, uuid, text, text, text) to service_role;
