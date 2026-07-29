# Schema and Storage Inventory

Baseline as of 2026-07-29. Generated from `supabase/migrations/` and runtime inspection.

## Database Tables

| Table | Purpose | RLS | Migration |
|---|---|---|---|
| `public.tracks` | Stored music generations (metadata only) | Public SELECT, Authenticated INSERT | `20260716_init_tracks.sql` |
| `public.jobs` | Async job records (status, worker, progress) | Public SELECT, Authenticated INSERT, no client UPDATE | `20260716_finetune_studio.sql` |
| `public.trained_models` | LoRA fine-tuning metadata | Public SELECT | `20260716_finetune_studio.sql` |

### `public.tracks` schema
```sql
id uuid PRIMARY KEY DEFAULT gen_random_uuid()
prompt text NOT NULL
model text NOT NULL DEFAULT 'Xenova/musicgen-small'
duration integer NOT NULL
guidance_scale real NOT NULL
temperature real NOT NULL
audio_path text NOT NULL
created_at timestamptz NOT NULL DEFAULT now()
```

### `public.jobs` schema
```sql
id uuid PRIMARY KEY DEFAULT gen_random_uuid()
model text NOT NULL
status text NOT NULL DEFAULT 'queued'
progress integer DEFAULT 0
worker text
audio_path text
result_path text
error text
created_at timestamptz NOT NULL DEFAULT now()
updated_at timestamptz NOT NULL DEFAULT now()
```

### `public.trained_models` schema
```sql
id uuid PRIMARY KEY DEFAULT gen_random_uuid()
name text NOT NULL
base_model text NOT NULL
fine_tune_model text NOT NULL
lora_path text
status text NOT NULL DEFAULT 'queued'
created_at timestamptz NOT NULL DEFAULT now()
```

## Storage Buckets

| Bucket | Purpose | Access | RLS Policy |
|---|---|---|---|
| `library` | User-uploaded audio files | Public read, Owner write | `library owner insert/delete` (uid-scoped) |
| `midi` | Generated MIDI files | Public read, Authenticated write | `midi authenticated insert` |
| `transcriptions` | Transcription JSON blobs | Public read, Owner write | `transcriptions owner insert` (uid-scoped) |
| `enhanced` | Processed/enhanced audio | Public read, Authenticated write | `enhanced authenticated insert` |
| `analysis` | Analysis result files | Public read, Authenticated write | `analysis authenticated insert` |
| `audio` | Generated audio | Public read, Authenticated write | `audio authenticated insert` |
| `datasets` | Training datasets | Public read, Authenticated write | `datasets authenticated insert` |
| `adapters` | Adapter state/config | Public read, Authenticated write | `adapters authenticated insert` |
| `soundfonts` | FluidSynth soundfonts | Public read | No custom policy |

## Migration History

| Migration | Date | Description |
|---|---|---|
| `20260716_init_tracks.sql` | 2026-07-16 | Initial tracks table + audio bucket |
| `20260716_finetune_studio.sql` | 2026-07-16 | Jobs, trained_models, additional buckets |
| `20260719_library_storage.sql` | 2026-07-19 | Library, MIDI, transcription, enhanced, analysis buckets |
| `20260720_rls_hardening.sql` | 2026-07-20 | Owner-scoped RLS, anonymous write holes closed |

## Gaps vs. Domain Model Target

| Missing | Plan |
|---|---|
| `projects` table | Phase 1 domain contracts → Phase 2 migration |
| `works` table | Phase 1 domain contracts → Phase 2 migration |
| `artifacts` table | Phase 1 domain contracts → Phase 2 migration |
| `artifact_versions` table | Phase 1 domain contracts → Phase 2 migration |
| `entities` table | Phase 1 domain contracts → Phase 2 migration |
| `insights` table | Phase 1 domain contracts → Phase 2 migration |
| `alignments` table | Phase 1 domain contracts → Phase 2 migration |
| `workspace_states` table | Phase 3 workspace foundation |
| `conversations` / `messages` tables | Phase 4+ AI integration |
| Job lifecycle (lease, heartbeat, retry) | Phase 2 durable workers |
| `job_inputs` / `job_outputs` tables | Phase 2 durable workers |
| Bucket privacy (signed URLs) | Phase 2 storage hardening |

## Current Data Flow

```
Browser upload → library bucket (key: library/<uid>/<ts>-<name>.ext)
               → POST /api/music/transcribe {library_path} 
               → Backend downloads from storage (service role)
               → Basic Pitch transcription
               → Backend uploads: midi bucket, transcriptions bucket, enhanced bucket
               → Response: {notes, midi_base64, analysis, midi_url}
               → Frontend stores in localStorage + sessionStorage
               → Save: transcription JSON blob to transcriptions bucket
               → Library lists: cross-references library + transcriptions buckets by filename
```

## Key Architectural Problems

1. **Storage path = identity** — `library/<uid>/<ts>-<name>.ext` used as the file `id`
2. **One transcription JSON = many outputs** — notes, MIDI, analysis, MusicXML all in one blob
3. **No lineage** — can't trace which audio produced which MIDI which produced which score
4. **Implicit relationship** — library file ↔ transcription via filename convention (`<name>.json`)
5. **No versioning** — saving overwrites the existing transcription JSON
6. **Public reads** — most buckets are publicly readable, relying on path obscurity
