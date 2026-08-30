# Data recovery runbook

This runbook covers durable ListenCloser user state in Supabase Postgres and Storage. Application rollback in `scripts/deploy.sh` is **not** database or Storage recovery.

## Current contract

At the last verified production check (2026-08-30):

- the Supabase organization is on the **Free** plan;
- Postgres is small enough for a logical backup (about 32 MB at that check);
- Storage is about 2.03 GiB total, with the private `artifacts` bucket holding the canonical product artifacts;
- all persisted `artifact_versions` point at the private `artifacts` bucket.

Treat those sizes and the plan as observations, not permanent configuration. Re-check provider capabilities before changing the recovery design.

Until a restore drill proves otherwise, the operating targets are:

- **RPO target: 24 hours** — one complete off-site backup per day;
- **RTO target: 4 hours** — restore and verify an isolated environment within four hours.

These are targets, not guarantees. The repository must not claim the RPO is met until a completed bundle is moved to an approved off-site destination on schedule.

## Why there are two backup planes

Supabase database backups do not contain the bytes stored in Storage. A usable recovery therefore needs both:

1. **Database state** — roles, schema, table data, Auth users, Storage metadata, and migration history.
2. **Storage bytes** — every object in every current bucket.

Current Supabase platform-to-self-hosted guidance says the standard three-file CLI dump preserves `auth.users`. The capture script verifies that claim against the produced `data.sql` whenever Auth rows exist; it also verifies that Storage object metadata is present. If either invariant stops holding after a CLI/platform change, backup capture fails instead of producing a misleading `BACKUP_COMPLETE` marker.

Provider documentation:

- https://supabase.com/docs/guides/self-hosting/restore-from-platform
- https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore
- https://supabase.com/docs/guides/storage/management/download-objects

## Capture a private recovery bundle

Prerequisites:

- Supabase CLI **2.113.0** (kept aligned with real-stack CI);
- Docker, because `supabase db dump` runs `pg_dump` in a Supabase container;
- `psql`;
- Python 3;
- a Supabase personal access token with access to the project;
- the database connection URL and database password.

Never put these credentials in Git or command examples with real values.

Run from a trusted operator machine:

```bash
export SUPABASE_PROJECT_REF='<project-ref>'
export SUPABASE_DB_URL='<session-or-direct-postgres-url>'
export SUPABASE_DB_PASSWORD='<database-password>'
export SUPABASE_ACCESS_TOKEN='<short-lived-or-owner-managed-personal-access-token>'

# Optional. Defaults to ~/.listencloser-recovery and is rejected if it resolves
# inside this Git repository.
export RECOVERY_OUTPUT_ROOT='/private/recovery/staging'

bash scripts/recovery/backup-supabase.sh
```

The script:

- uses `umask 077` and refuses an output root inside the repository;
- emits separate roles/schema/data and migration-history SQL files;
- checks that a non-empty Auth schema actually appears in the data dump;
- checks that non-empty Storage metadata actually appears in the data dump;
- queries the live bucket inventory instead of keeping a hard-coded bucket list;
- copies every object from every current bucket with the linked Supabase Storage CLI;
- verifies copied object counts and byte totals when Storage metadata has sizes for every object;
- writes SHA-256 hashes for every SQL file and Storage object into a **private** manifest;
- writes `BACKUP_COMPLETE` only after every required step passes.

The bundle contains user data, Auth records, object paths, and object bytes. Treat the whole directory as sensitive. Do not attach it to GitHub issues, Actions artifacts, logs, or the public repository.

A successful local capture is not yet a disaster-recovery backup. Move the completed bundle to the approved off-site destination outside the Supabase project/provider failure domain, then verify that destination independently.

## What is not captured by the database dump

Even when Auth users are present in the database dump, a replacement Supabase project still needs configuration recreated deliberately, including as applicable:

- Auth provider/OAuth configuration and redirect URLs;
- JWT/API keys and application secrets;
- SMTP/email settings;
- Edge Functions;
- Realtime/project settings;
- custom domains/DNS;
- Vercel, Oracle, GitHub, Sentry, and other external account configuration.

Do not copy secrets into the recovery bundle merely to make the runbook shorter. Keep secret/configuration ownership in the provider/deployment systems that already own it.

## Restore drill — isolated only

There is intentionally **no automated production restore command** in this repository. A destructive production restore requires owner review and provider-aware execution.

The first proof must use an isolated local/self-hosted Supabase target with no production traffic or user content. Follow the current Supabase restore guide rather than inventing a restore order. At a high level:

```text
fresh isolated Supabase target
→ restore roles.sql + schema.sql + data.sql with ON_ERROR_STOP
→ restore migration history
→ recreate required Auth/provider configuration with test credentials
→ recreate/verify Storage buckets and upload backed-up object bytes
→ verify hashes/counts
→ verify RLS/grants/security
→ verify Auth user count without exposing identities
→ verify exact Work → Artifact → Version lineage
→ verify private object sign/read
→ run canonical product reload/playback/analysis/delete smoke on test data
```

Supabase's current SQL restore sequence uses one transaction and disables triggers during the data load to avoid double-encryption. Follow the version-current provider instructions during the drill; do not paste a permanently frozen restore command into an emergency without checking the generated dump and target Postgres/Supabase versions first.

If the restore requires editing generated SQL because managed Auth/Storage versions differ, record that as a failed portability assumption and update this runbook before declaring the drill successful.

## Drill evidence

For each drill record only privacy-safe operational evidence in the repository/issue:

- source and isolated target type (not credentials);
- capture timestamp and repository SHA;
- database size;
- bucket/object counts and aggregate bytes;
- restore start/end and total duration;
- RLS/security verification result;
- Auth count parity result;
- Version/Storage lineage verification result;
- canonical product smoke result;
- any manual repair required.

Do not record user names, email addresses, filenames, raw object keys, tokens, passwords, or backup contents.

## Failure rules

- No `BACKUP_COMPLETE` marker: the bundle is incomplete and must not count toward RPO.
- Local bundle not copied off-site: RPO is not satisfied.
- Database restored but Storage bytes missing: recovery is incomplete.
- Storage bytes restored without matching authoritative Version metadata: recovery is incomplete.
- Auth users restored but provider configuration missing: sign-in recovery is incomplete.
- Application Git rollback succeeds: says nothing about data recovery.
- Never weaken RLS/grants or make buckets public to force a restore smoke to pass.

## Open decision

The remaining operational decision is the off-site destination. Prefer an existing durable primitive before adding another service. The destination needs restricted credentials, enough capacity for current Storage growth, retention, and a failure domain independent from the active Supabase project. Once selected, automate **copy + freshness verification**; do not automate production restore.
