-- Retire obsolete pre-domain Storage policies.
--
-- Bucket privacy is owned declaratively by supabase/config.toml and deployed
-- with `supabase seed buckets --linked`. Preserve every historical object byte
-- and remove only the old public/broad client access policies here.

drop policy if exists "analysis public read" on storage.objects;
drop policy if exists "analysis authenticated insert" on storage.objects;
drop policy if exists "enhanced public read" on storage.objects;
drop policy if exists "enhanced authenticated insert" on storage.objects;
drop policy if exists "library public read" on storage.objects;
drop policy if exists "library owner insert" on storage.objects;
drop policy if exists "library owner delete" on storage.objects;
drop policy if exists "midi public read" on storage.objects;
drop policy if exists "midi authenticated insert" on storage.objects;
drop policy if exists "transcriptions public read" on storage.objects;
drop policy if exists "transcriptions owner insert" on storage.objects;
