-- Clear actionable Supabase database-advisor findings without reopening the
-- retired browser domain Data API.
--
-- FastAPI/service_role remains the authoritative domain persistence path.
-- These RLS policies are retained as defense in depth and for rollback-only
-- contract tests. Scope them explicitly to authenticated callers and cache the
-- stable auth.uid() value once per statement via an initPlan.

begin;

-- PostgreSQL does not automatically index the referencing side of a foreign key.
-- Cover workflows.target_version_id so Version deletion / FK validation and
-- target-version lookups do not require a workflows scan as the table grows.
create index if not exists idx_workflows_target_version
  on public.workflows (target_version_id);

-- Projects are directly owner-scoped. UPDATE needs both USING and WITH CHECK so
-- a caller who owns the old row cannot move it to a different owner.
alter policy "projects owner select" on public.projects
  to authenticated
  using ((select auth.uid()) = owner_id);

alter policy "projects owner insert" on public.projects
  to authenticated
  with check ((select auth.uid()) = owner_id);

alter policy "projects owner update" on public.projects
  to authenticated
  using ((select auth.uid()) = owner_id)
  with check ((select auth.uid()) = owner_id);

alter policy "projects owner delete" on public.projects
  to authenticated
  using ((select auth.uid()) = owner_id);

-- Works inherit ownership from their Project. The WITH CHECK predicate prevents
-- an owner from re-parenting an owned Work into another user's Project.
alter policy "works owner select" on public.works
  to authenticated
  using (
    exists (
      select 1
      from public.projects
      where projects.id = works.project_id
        and projects.owner_id = (select auth.uid())
    )
  );

alter policy "works owner insert" on public.works
  to authenticated
  with check (
    exists (
      select 1
      from public.projects
      where projects.id = works.project_id
        and projects.owner_id = (select auth.uid())
    )
  );

alter policy "works owner update" on public.works
  to authenticated
  using (
    exists (
      select 1
      from public.projects
      where projects.id = works.project_id
        and projects.owner_id = (select auth.uid())
    )
  )
  with check (
    exists (
      select 1
      from public.projects
      where projects.id = works.project_id
        and projects.owner_id = (select auth.uid())
    )
  );

alter policy "works owner delete" on public.works
  to authenticated
  using (
    exists (
      select 1
      from public.projects
      where projects.id = works.project_id
        and projects.owner_id = (select auth.uid())
    )
  );

-- Server-owned derived state remains readable only through the owner chain when
-- RLS is deliberately exercised. Writes continue to have no browser policies.
alter policy "artifacts owner select" on public.artifacts
  to authenticated
  using (
    exists (
      select 1
      from public.works
      join public.projects on projects.id = works.project_id
      where works.id = artifacts.work_id
        and projects.owner_id = (select auth.uid())
    )
  );

alter policy "versions owner select" on public.artifact_versions
  to authenticated
  using (
    exists (
      select 1
      from public.artifacts
      join public.works on works.id = artifacts.work_id
      join public.projects on projects.id = works.project_id
      where artifacts.id = artifact_versions.artifact_id
        and projects.owner_id = (select auth.uid())
    )
  );

alter policy "entities owner select" on public.entities
  to authenticated
  using (
    exists (
      select 1
      from public.artifact_versions
      join public.artifacts on artifacts.id = artifact_versions.artifact_id
      join public.works on works.id = artifacts.work_id
      join public.projects on projects.id = works.project_id
      where artifact_versions.id = entities.version_id
        and projects.owner_id = (select auth.uid())
    )
  );

alter policy "insights owner select" on public.insights
  to authenticated
  using (
    exists (
      select 1
      from public.artifact_versions
      join public.artifacts on artifacts.id = artifact_versions.artifact_id
      join public.works on works.id = artifacts.work_id
      join public.projects on projects.id = works.project_id
      where artifact_versions.id = insights.version_id
        and projects.owner_id = (select auth.uid())
    )
  );

alter policy "alignments owner select" on public.alignments
  to authenticated
  using (
    exists (
      select 1
      from public.artifact_versions
      join public.artifacts on artifacts.id = artifact_versions.artifact_id
      join public.works on works.id = artifacts.work_id
      join public.projects on projects.id = works.project_id
      where artifact_versions.id = alignments.version_id
        and projects.owner_id = (select auth.uid())
    )
  );

alter policy "workflows owner select" on public.workflows
  to authenticated
  using (
    exists (
      select 1
      from public.projects
      where projects.id = workflows.project_id
        and projects.owner_id = (select auth.uid())
    )
  );

alter policy "jobs owner select" on public.jobs
  to authenticated
  using (
    exists (
      select 1
      from public.workflows
      join public.projects on projects.id = workflows.project_id
      where workflows.id = jobs.workflow_id
        and projects.owner_id = (select auth.uid())
    )
  );

commit;
