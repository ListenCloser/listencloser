-- Migration: relax forward references so deleting a work does not violate FKs.
--
-- The delete flow cascades work → artifacts → artifact_versions. Two forward
-- references had NO ACTION on delete, so deleting a work with a persisted
-- workflow (which records target_version_id) or an artifact lineage (parent
-- version) raised a foreign-key violation and left the work undeletable.
--
-- These references describe provenance, not ownership, so clearing them on
-- delete (SET NULL) preserves lineage/records while allowing deletion.

begin;

alter table public.workflows
  drop constraint if exists workflows_target_version_id_fkey;
alter table public.workflows
  add constraint workflows_target_version_id_fkey
  foreign key (target_version_id) references public.artifact_versions(id)
  on delete set null;

alter table public.artifact_versions
  drop constraint if exists artifact_versions_parent_version_id_fkey;
alter table public.artifact_versions
  add constraint artifact_versions_parent_version_id_fkey
  foreign key (parent_version_id) references public.artifact_versions(id)
  on delete set null;

commit;
