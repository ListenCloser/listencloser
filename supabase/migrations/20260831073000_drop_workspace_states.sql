-- Retire production-only legacy workspace state after browser Data API cleanup.
-- Current repository migrations no longer create or consume this table, and the
-- production table was reverified empty before this migration was authored.
-- Avoid CASCADE so any unexpected dependency fails deployment rather than being
-- removed implicitly.

drop table if exists public.workspace_states;
