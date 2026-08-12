-- Migration: make insights.confidence nullable to match the domain model.
--
-- Conservative-analysis work (#200) intentionally writes heuristic/unsupported
-- evidence with confidence = NULL, because those scores are not calibrated
-- probabilities. The previous NOT NULL constraint rejected such rows.
--
-- Rule enforced by this migration (see scripts/verify_database.sql):
--   Any persisted-model change to nullability, enum values, or columns must be
--   accompanied by (or explicitly verify) a database migration.

begin;

alter table public.insights
  alter column confidence drop not null;

-- The domain model's default is NULL (Insight.confidence defaults to None);
-- the old numeric default of 1.0 implied confidence where none was measured.
alter table public.insights
  alter column confidence drop default;

commit;
