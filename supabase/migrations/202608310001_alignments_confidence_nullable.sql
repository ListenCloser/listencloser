-- Migration: make alignments.confidence nullable to match truthful domain semantics.
--
-- Alignment confidence is optional unless a producer has a measured/calibrated
-- score. The historical NOT NULL DEFAULT 1.0 manufactured certainty for rows
-- whose producers did not define confidence semantics.
--
-- This migration is intentionally prospective: existing numeric values are not
-- reinterpreted or backfilled here.

begin;

alter table public.alignments
  alter column confidence drop not null;

alter table public.alignments
  alter column confidence drop default;

commit;
