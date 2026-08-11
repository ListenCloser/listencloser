-- Forward repair: a cleanup migration accidentally dropped the durable jobs table.
do $$
begin
  if to_regclass('public.jobs') is not null
     and not exists (
       select 1 from information_schema.columns
       where table_schema = 'public' and table_name = 'jobs' and column_name = 'capability_name'
     ) then
    if to_regclass('public.jobs_legacy_20260812') is null then
      alter table public.jobs rename to jobs_legacy_20260812;
    else
      raise exception 'legacy jobs backup already exists; manual migration required';
    end if;
  end if;
end $$;

create table if not exists public.jobs (
  id uuid primary key default gen_random_uuid(),
  workflow_id uuid not null references public.workflows(id) on delete cascade,
  capability_name text not null,
  capability_version text not null,
  stage job_stage not null default 'queued',
  progress double precision not null default 0.0 check (progress >= 0 and progress <= 1),
  status_message text not null default '', worker_id text, lease_expires_at timestamptz,
  retry_count integer not null default 0, max_retries integer not null default 3,
  input_version_ids uuid[] not null default '{}', output_version_ids uuid[] not null default '{}',
  parameters jsonb not null default '{}', cache_key text, error_message text,
  error_details jsonb not null default '{}', provenance jsonb not null default '{}',
  started_at timestamptz, completed_at timestamptz, created_at timestamptz not null default now(),
  created_by uuid
);
create index if not exists idx_jobs_workflow on public.jobs (workflow_id);
create index if not exists idx_jobs_stage on public.jobs (stage);
create index if not exists idx_jobs_worker on public.jobs (worker_id);
create unique index if not exists idx_jobs_cache_key on public.jobs (cache_key) where cache_key is not null;
alter table public.jobs enable row level security;
drop policy if exists "jobs owner select" on public.jobs;
create policy "jobs owner select" on public.jobs for select using (
  exists (
    select 1 from public.workflows join public.projects on public.projects.id = public.workflows.project_id
    where public.workflows.id = jobs.workflow_id and public.projects.owner_id = auth.uid()
  )
);
