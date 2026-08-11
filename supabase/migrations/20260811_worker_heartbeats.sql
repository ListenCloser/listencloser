create table if not exists public.worker_heartbeats (
  worker_id text primary key,
  status text not null default 'running'
    check (status in ('running', 'draining', 'stopped')),
  capabilities jsonb not null default '[]',
  started_at timestamptz not null default now(),
  heartbeat_at timestamptz not null default now()
);

create index if not exists idx_worker_heartbeats_heartbeat
  on public.worker_heartbeats (heartbeat_at desc);

alter table public.worker_heartbeats enable row level security;

comment on table public.worker_heartbeats is
  'Service-role worker liveness records used by the aggregate queue health endpoint.';
