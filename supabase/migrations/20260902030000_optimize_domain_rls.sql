-- Clear actionable Supabase planner warnings without changing the domain data plane.
--
-- Browser access to these tables remains revoked by
-- 20260831001000_retire_browser_domain_data_api.sql. The policies below are retained
-- only as defense in depth for rollback/test scenarios, but should still be scoped
-- narrowly and planner-friendly.

begin;

-- Cover the nullable workflows.target_version_id foreign key so deletes/updates of
-- referenced artifact_versions do not require scanning workflows.
create index if not exists idx_workflows_target_version
  on public.workflows (target_version_id);

-- Evaluate the authenticated user id once per statement rather than once per row.
-- Scope every retained domain policy to authenticated instead of the implicit public
-- role. Projects/Works UPDATE policies explicitly constrain both the old and new row
-- so a rollback that re-enables table ACLs cannot reassign ownership.

alter policy "projects owner select" on public.projects
  to authenticated
  using (owner_id = (select auth.uid()));

alter policy "projects owner insert" on public.projects
  to authenticated
  with check (owner_id = (select auth.uid()));

alter policy "projects owner update" on public.projects
  to authenticated
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

alter policy "projects owner delete" on public.projects
  to authenticated
  using (owner_id = (select auth.uid()));

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
