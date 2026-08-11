-- Migration: Domain model tables
-- Phase 2 — Normalized project/work/artifact/version/job persistence
-- Matches backend/domain/models.py contracts

begin;

-- ===========================================================================
-- ENUMS
-- ===========================================================================
create type artifact_kind as enum (
  'audio_original', 'audio_enhanced', 'midi_performance', 'midi_corrected',
  'musicxml_score', 'rendered_score', 'stems', 'analysis_report'
);

create type entity_kind as enum (
  'note', 'chord', 'beat', 'measure', 'phrase', 'section', 'cadence', 'motif'
);

create type workflow_kind as enum (
  'understand', 'correct', 'compare', 'create', 'export'
);

create type alignment_kind_enum as enum (
  'timeline', 'version', 'performance'
);

create type timeline_unit_enum as enum (
  'seconds', 'samples', 'beats', 'measures', 'ticks', 'score_position'
);

create type job_stage as enum (
  'queued', 'claimed', 'running', 'succeeded', 'failed', 'cancelled'
);

-- ===========================================================================
-- PROJECTS
-- ===========================================================================
create table projects (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null,
  name text not null,
  description text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  archived_at timestamptz
);

create index idx_projects_owner on projects (owner_id);

-- ===========================================================================
-- WORKS
-- ===========================================================================
create table works (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  title text not null,
  composer text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_works_project on works (project_id);

-- ===========================================================================
-- ARTIFACTS
-- ===========================================================================
create table artifacts (
  id uuid primary key default gen_random_uuid(),
  work_id uuid not null references works(id) on delete cascade,
  kind artifact_kind not null default 'audio_original',
  mime_type text not null default 'application/octet-stream',
  created_at timestamptz not null default now()
);

create index idx_artifacts_work on artifacts (work_id);

-- ===========================================================================
-- ARTIFACT VERSIONS (immutable)
-- ===========================================================================
create table artifact_versions (
  id uuid primary key default gen_random_uuid(),
  artifact_id uuid not null references artifacts(id) on delete cascade,
  parent_version_id uuid references artifact_versions(id),
  lineage uuid[] not null default '{}',
  storage_key text not null,
  storage_bucket text not null,
  byte_size bigint,
  sha256 text,
  label text not null default '',
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  created_by uuid,
  produced_by_job_id uuid
);

create index idx_versions_artifact on artifact_versions (artifact_id);
create index idx_versions_parent on artifact_versions (parent_version_id);
create index idx_versions_job on artifact_versions (produced_by_job_id);

-- ===========================================================================
-- ENTITIES
-- ===========================================================================
create table entities (
  id uuid primary key default gen_random_uuid(),
  version_id uuid not null references artifact_versions(id) on delete cascade,
  kind entity_kind not null,
  start_seconds double precision,
  end_seconds double precision,
  start_beat double precision,
  end_beat double precision,
  start_measure integer,
  end_measure integer,
  label text not null default '',
  note_pitch integer,
  note_start_seconds double precision,
  note_end_seconds double precision,
  note_velocity integer,
  note_voice integer,
  chord_root text,
  chord_quality text,
  chord_bass text,
  chord_start_seconds double precision,
  chord_end_seconds double precision,
  cadence_kind text,
  cadence_chords jsonb,
  cadence_position_seconds double precision
);

create index idx_entities_version on entities (version_id);
create index idx_entities_kind on entities (kind);

-- ===========================================================================
-- INSIGHTS
-- ===========================================================================
create table insights (
  id uuid primary key default gen_random_uuid(),
  version_id uuid not null references artifact_versions(id) on delete cascade,
  kind text not null,
  claim text not null,
  span jsonb not null default '{}',
  entity_ids uuid[] not null default '{}',
  evidence jsonb not null default '{}',
  confidence double precision not null default 1.0
    check (confidence >= 0 and confidence <= 1),
  provenance jsonb not null default '{}',
  created_at timestamptz not null default now(),
  created_by uuid,
  produced_by_job_id uuid
);

create index idx_insights_version on insights (version_id);
create index idx_insights_kind on insights (kind);

-- ===========================================================================
-- ALIGNMENTS
-- ===========================================================================
create table alignments (
  id uuid primary key default gen_random_uuid(),
  version_id uuid not null references artifact_versions(id) on delete cascade,
  target_version_id uuid not null references artifact_versions(id) on delete cascade,
  kind alignment_kind_enum not null,
  source_unit timeline_unit_enum not null,
  target_unit timeline_unit_enum not null,
  mapping_data jsonb not null default '{}',
  confidence double precision not null default 1.0
    check (confidence >= 0 and confidence <= 1),
  created_at timestamptz not null default now(),
  produced_by_job_id uuid
);

create index idx_alignments_version on alignments (version_id);
create index idx_alignments_target on alignments (target_version_id);

-- ===========================================================================
-- WORKFLOWS
-- ===========================================================================
create table workflows (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  kind workflow_kind not null,
  target_version_id uuid references artifact_versions(id),
  parameters jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index idx_workflows_project on workflows (project_id);

-- ===========================================================================
-- JOBS (supersedes the vestigial public.jobs from 20260716)
-- ===========================================================================
drop table if exists public.jobs cascade;

create table jobs (
  id uuid primary key default gen_random_uuid(),
  workflow_id uuid not null references workflows(id) on delete cascade,
  capability_name text not null,
  capability_version text not null,
  stage job_stage not null default 'queued',
  progress double precision not null default 0.0
    check (progress >= 0 and progress <= 1),
  status_message text not null default '',
  worker_id text,
  lease_expires_at timestamptz,
  retry_count integer not null default 0,
  max_retries integer not null default 3,
  input_version_ids uuid[] not null default '{}',
  output_version_ids uuid[] not null default '{}',
  parameters jsonb not null default '{}',
  cache_key text,
  error_message text,
  error_details jsonb not null default '{}',
  provenance jsonb not null default '{}',
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  created_by uuid
);

create index idx_jobs_workflow on jobs (workflow_id);
create index idx_jobs_stage on jobs (stage);
create index idx_jobs_worker on jobs (worker_id);
create unique index idx_jobs_cache_key on jobs (cache_key) where cache_key is not null;

-- ===========================================================================
-- WORKSPACE STATE (UI persistence)
-- ===========================================================================
create table workspace_states (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  owner_id uuid not null,
  tab text not null default 'explore',
  open_version_ids uuid[] not null default '{}',
  expanded_version_ids uuid[] not null default '{}',
  focus_version_id uuid,
  selection jsonb not null default '{}',
  transport jsonb not null default '{}',
  updated_at timestamptz not null default now()
);

create unique index idx_workspace_state_owner
  on workspace_states (owner_id, project_id);

-- ===========================================================================
-- RLS: Enable on all domain tables
-- ===========================================================================
alter table projects enable row level security;
alter table works enable row level security;
alter table artifacts enable row level security;
alter table artifact_versions enable row level security;
alter table entities enable row level security;
alter table insights enable row level security;
alter table alignments enable row level security;
alter table workflows enable row level security;
alter table jobs enable row level security;
alter table workspace_states enable row level security;

-- ===========================================================================
-- RLS: projects — owner-scoped
-- ===========================================================================
create policy "projects owner select" on projects
  for select using (owner_id = auth.uid());

create policy "projects owner insert" on projects
  for insert with check (owner_id = auth.uid());

create policy "projects owner update" on projects
  for update using (owner_id = auth.uid());

create policy "projects owner delete" on projects
  for delete using (owner_id = auth.uid());

-- ===========================================================================
-- RLS: works — inherited through project ownership
-- ===========================================================================
create policy "works owner select" on works
  for select using (
    exists (select 1 from projects where projects.id = works.project_id and projects.owner_id = auth.uid())
  );

create policy "works owner insert" on works
  for insert with check (
    exists (select 1 from projects where projects.id = works.project_id and projects.owner_id = auth.uid())
  );

create policy "works owner update" on works
  for update using (
    exists (select 1 from projects where projects.id = works.project_id and projects.owner_id = auth.uid())
  );

create policy "works owner delete" on works
  for delete using (
    exists (select 1 from projects where projects.id = works.project_id and projects.owner_id = auth.uid())
  );

-- ===========================================================================
-- RLS: artifacts — inherited through work → project ownership
-- ===========================================================================
create policy "artifacts owner select" on artifacts
  for select using (
    exists (
      select 1 from works join projects on projects.id = works.project_id
      where works.id = artifacts.work_id and projects.owner_id = auth.uid()
    )
  );

create policy "artifacts owner insert" on artifacts
  for insert with check (
    exists (
      select 1 from works join projects on projects.id = works.project_id
      where works.id = artifacts.work_id and projects.owner_id = auth.uid()
    )
  );

-- ===========================================================================
-- RLS: artifact_versions — inherited through artifact chain
-- ===========================================================================
create policy "versions owner select" on artifact_versions
  for select using (
    exists (
      select 1
      from artifacts
        join works on works.id = artifacts.work_id
        join projects on projects.id = works.project_id
      where artifacts.id = artifact_versions.artifact_id
        and projects.owner_id = auth.uid()
    )
  );

create policy "versions owner insert" on artifact_versions
  for insert with check (
    exists (
      select 1
      from artifacts
        join works on works.id = artifacts.work_id
        join projects on projects.id = works.project_id
      where artifacts.id = artifact_versions.artifact_id
        and projects.owner_id = auth.uid()
    )
  );

-- ===========================================================================
-- RLS: entities — inherited through version chain
-- ===========================================================================
create policy "entities owner select" on entities
  for select using (
    exists (
      select 1
      from artifact_versions
        join artifacts on artifacts.id = artifact_versions.artifact_id
        join works on works.id = artifacts.work_id
        join projects on projects.id = works.project_id
      where artifact_versions.id = entities.version_id
        and projects.owner_id = auth.uid()
    )
  );

create policy "entities owner insert" on entities
  for insert with check (
    exists (
      select 1
      from artifact_versions
        join artifacts on artifacts.id = artifact_versions.artifact_id
        join works on works.id = artifacts.work_id
        join projects on projects.id = works.project_id
      where artifact_versions.id = entities.version_id
        and projects.owner_id = auth.uid()
    )
  );

-- ===========================================================================
-- RLS: insights — inherited through version chain
-- ===========================================================================
create policy "insights owner select" on insights
  for select using (
    exists (
      select 1
      from artifact_versions
        join artifacts on artifacts.id = artifact_versions.artifact_id
        join works on works.id = artifacts.work_id
        join projects on projects.id = works.project_id
      where artifact_versions.id = insights.version_id
        and projects.owner_id = auth.uid()
    )
  );

create policy "insights owner insert" on insights
  for insert with check (
    exists (
      select 1
      from artifact_versions
        join artifacts on artifacts.id = artifact_versions.artifact_id
        join works on works.id = artifacts.work_id
        join projects on projects.id = works.project_id
      where artifact_versions.id = insights.version_id
        and projects.owner_id = auth.uid()
    )
  );

-- ===========================================================================
-- RLS: alignments — inherited through version chain
-- ===========================================================================
create policy "alignments owner select" on alignments
  for select using (
    exists (
      select 1
      from artifact_versions
        join artifacts on artifacts.id = artifact_versions.artifact_id
        join works on works.id = artifacts.work_id
        join projects on projects.id = works.project_id
      where artifact_versions.id = alignments.version_id
        and projects.owner_id = auth.uid()
    )
  );

create policy "alignments owner insert" on alignments
  for insert with check (
    exists (
      select 1
      from artifact_versions
        join artifacts on artifacts.id = artifact_versions.artifact_id
        join works on works.id = artifacts.work_id
        join projects on projects.id = works.project_id
      where artifact_versions.id = alignments.version_id
        and projects.owner_id = auth.uid()
    )
  );

-- ===========================================================================
-- RLS: workflows — owner-scoped through project
-- ===========================================================================
create policy "workflows owner select" on workflows
  for select using (
    exists (select 1 from projects where projects.id = workflows.project_id and projects.owner_id = auth.uid())
  );

create policy "workflows owner insert" on workflows
  for insert with check (
    exists (select 1 from projects where projects.id = workflows.project_id and projects.owner_id = auth.uid())
  );

-- ===========================================================================
-- RLS: jobs — read through workflow → project ownership; write via service_role only
-- ===========================================================================
create policy "jobs owner select" on jobs
  for select using (
    exists (
      select 1
      from workflows join projects on projects.id = workflows.project_id
      where workflows.id = jobs.workflow_id and projects.owner_id = auth.uid()
    )
  );

-- Only service_role can insert/update jobs (backend manages job lifecycle)
-- Client users cannot create or mutate jobs directly.

-- ===========================================================================
-- RLS: workspace_states — owner-scoped
-- ===========================================================================
create policy "workspace owner all" on workspace_states
  for all using (owner_id = auth.uid())
  with check (owner_id = auth.uid());

commit;
