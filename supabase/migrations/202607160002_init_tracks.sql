-- Migration: hello-ai music studio schema
-- Creates the tracks table, audio storage bucket, and RLS policies.

-- Stored generations (metadata only; audio lives in Storage).
create table if not exists public.tracks (
  id uuid primary key default gen_random_uuid(),
  prompt text not null,
  model text not null default 'Xenova/musicgen-small',
  duration integer not null,
  guidance_scale real not null,
  temperature real not null,
  audio_path text not null,
  created_at timestamptz not null default now()
);

-- Allow anonymous read so the public gallery works without login.
alter table public.tracks enable row level security;
drop policy if exists "public read" on public.tracks;
create policy "public read" on public.tracks
  for select using (true);

-- Allow anonymous insert (open demo). Tighten with auth later if needed.
drop policy if exists "public insert" on public.tracks;
create policy "public insert" on public.tracks
  for insert with check (true);

-- Storage bucket for audio files.
insert into storage.buckets (id, name, public)
values ('audio', 'audio', true)
on conflict (id) do nothing;

drop policy if exists "audio public read" on storage.objects;
create policy "audio public read" on storage.objects
  for select using (bucket_id = 'audio');

drop policy if exists "audio public insert" on storage.objects;
create policy "audio public insert" on storage.objects
  for insert with check (bucket_id = 'audio');
