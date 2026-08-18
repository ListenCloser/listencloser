-- Migration: hello-ai finetune studio schema
-- Jobs (training runs), trained models (LoRA adapters), and storage buckets
-- for datasets + adapters. RLS allows public read + insert (demo project).

-- ---------------------------------------------------------------------------
-- jobs: one row per training run
-- ---------------------------------------------------------------------------
create table if not exists public.jobs (
  id uuid primary key default gen_random_uuid(),
  base_model text not null,
  params jsonb not null default '{}'::jsonb,
  dataset_path text,
  status text not null default 'queued'
    check (status in ('queued', 'running', 'done', 'error')),
  loss_log text not null default '',
  error text,
  created_at timestamptz not null default now(),
  finished_at timestamptz
);

create index if not exists jobs_created_at_idx on public.jobs (created_at desc);

-- ---------------------------------------------------------------------------
-- models: one row per resulting LoRA adapter
-- ---------------------------------------------------------------------------
create table if not exists public.models (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  base_model text not null,
  job_id uuid references public.jobs (id) on delete set null,
  adapter_path text not null,
  created_at timestamptz not null default now()
);

create index if not exists models_created_at_idx on public.models (created_at desc);

-- ---------------------------------------------------------------------------
-- storage buckets
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('datasets', 'datasets', true)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('adapters', 'adapters', true)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- RLS: allow public read + insert on jobs/models (demo). Tighten if needed.
-- ---------------------------------------------------------------------------
alter table public.jobs enable row level security;
alter table public.models enable row level security;

drop policy if exists "jobs public read" on public.jobs;
create policy "jobs public read" on public.jobs
  for select using (true);

drop policy if exists "jobs public insert" on public.jobs;
create policy "jobs public insert" on public.jobs
  for insert with check (true);

drop policy if exists "jobs public update" on public.jobs;
create policy "jobs public update" on public.jobs
  for update using (true);

drop policy if exists "models public read" on public.models;
create policy "models public read" on public.models
  for select using (true);

drop policy if exists "models public insert" on public.models;
create policy "models public insert" on public.models
  for insert with check (true);

-- Storage: public read, authenticated+anon insert (demo).
drop policy if exists "datasets public read" on storage.objects;
create policy "datasets public read" on storage.objects
  for select using (bucket_id = 'datasets');

drop policy if exists "datasets public insert" on storage.objects;
create policy "datasets public insert" on storage.objects
  for insert with check (bucket_id = 'datasets');

drop policy if exists "adapters public read" on storage.objects;
create policy "adapters public read" on storage.objects
  for select using (bucket_id = 'adapters');

drop policy if exists "adapters public insert" on storage.objects;
create policy "adapters public insert" on storage.objects
  for insert with check (bucket_id = 'adapters');
