-- Establish trusted exact-byte identity for uploaded input Versions on existing worker reads.
--
-- The worker supplies the SHA-256 it measured from bytes it already downloaded.
-- This function is deliberately narrower than a generic Version update: one
-- current Job attempt may enrich only one of its declared input Versions, only
-- from NULL, while same-digest retries are idempotent and conflicts fail closed.

create function public.fenced_job_verify_input_sha256(
  p_job_id uuid,
  p_execution_token uuid,
  p_version_id uuid,
  p_sha256 text
)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_input_version_ids uuid[];
  v_existing_sha256 text;
begin
  if p_sha256 is null or p_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023',
      message = 'verified input sha256 must be 64 lowercase hexadecimal characters';
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

  if not (p_version_id = any(coalesce(v_input_version_ids, '{}'::uuid[]))) then
    raise exception using
      errcode = '42501',
      message = 'job cannot verify a Version outside its declared inputs';
  end if;

  select sha256
  into v_existing_sha256
  from public.artifact_versions
  where id = p_version_id
  for update;

  if not found then
    raise exception using
      errcode = '23503',
      message = 'declared input Version does not exist';
  end if;

  if v_existing_sha256 is null then
    update public.artifact_versions
    set sha256 = p_sha256
    where id = p_version_id
      and sha256 is null;
    return p_sha256;
  end if;

  if v_existing_sha256 = p_sha256 then
    return v_existing_sha256;
  end if;

  raise exception using
    errcode = 'P0001',
    message = 'input Version sha256 conflicts with measured bytes';
end;
$$;

comment on function public.fenced_job_verify_input_sha256(uuid, uuid, uuid, text) is
  'Monotonically enriches exact-byte SHA-256 for one current Job declared input Version.';

revoke all on function public.fenced_job_verify_input_sha256(uuid, uuid, uuid, text) from public;
revoke all on function public.fenced_job_verify_input_sha256(uuid, uuid, uuid, text)
  from anon, authenticated;
grant execute on function public.fenced_job_verify_input_sha256(uuid, uuid, uuid, text)
  to service_role;
