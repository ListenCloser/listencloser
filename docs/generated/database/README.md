# Listen Closer application database

## Description

Generated from the fresh local Supabase/Postgres schema. Migrations are authoritative.

## Tables

| Name | Columns | Comment | Type |
| ---- | ------- | ------- | ---- |
| [public.alignments](public.alignments.md) | 10 |  | BASE TABLE |
| [public.artifact_versions](public.artifact_versions.md) | 13 |  | BASE TABLE |
| [public.artifacts](public.artifacts.md) | 5 |  | BASE TABLE |
| [public.entities](public.entities.md) | 24 |  | BASE TABLE |
| [public.insights](public.insights.md) | 12 |  | BASE TABLE |
| [public.jobs](public.jobs.md) | 23 |  | BASE TABLE |
| [public.projects](public.projects.md) | 7 |  | BASE TABLE |
| [public.worker_heartbeats](public.worker_heartbeats.md) | 5 | Service-role worker liveness records used by the aggregate queue health endpoint. | BASE TABLE |
| [public.workflows](public.workflows.md) | 6 |  | BASE TABLE |
| [public.works](public.works.md) | 6 |  | BASE TABLE |

## Stored procedures and functions

| Name | ReturnType | Arguments | Type |
| ---- | ------- | ------- | ---- |
| public.claim_next_job | jobs | p_worker_id text, p_lease_seconds double precision DEFAULT 30.0 | FUNCTION |
| public.enqueue_job_delivery | trigger |  | FUNCTION |
| public.extend_job_delivery | bool | p_job_id uuid, p_execution_token uuid, p_msg_id bigint, p_visibility_seconds integer | FUNCTION |
| public.fenced_job_delete | int4 | p_job_id uuid, p_execution_token uuid, p_table text, p_match jsonb | FUNCTION |
| public.fenced_job_insert | jsonb | p_job_id uuid, p_execution_token uuid, p_table text, p_rows jsonb | FUNCTION |
| public.fenced_job_publish_version | jsonb | p_job_id uuid, p_execution_token uuid, p_artifact jsonb, p_version jsonb | FUNCTION |
| public.fenced_job_verify_input_sha256 | text | p_job_id uuid, p_execution_token uuid, p_version_id uuid, p_sha256 text | FUNCTION |
| public.finish_job_delivery | text | p_job_id uuid, p_execution_token uuid, p_msg_id bigint, p_retry_delay_seconds integer DEFAULT 0 | FUNCTION |
| public.receive_job_delivery | jsonb | p_worker_id text, p_visibility_seconds integer, p_in_flight_job_ids uuid[] DEFAULT '{}'::uuid[] | FUNCTION |

## Enums

| Name | Values |
| ---- | ------- |
| auth.aal_level | aal1, aal2, aal3 |
| auth.code_challenge_method | plain, s256 |
| auth.factor_status | unverified, verified |
| auth.factor_type | phone, totp, webauthn |
| auth.oauth_authorization_status | approved, denied, expired, pending |
| auth.oauth_client_type | confidential, public |
| auth.oauth_registration_type | dynamic, manual |
| auth.oauth_response_type | code |
| auth.one_time_token_type | confirmation_token, email_change_token_current, email_change_token_new, phone_change_token, reauthentication_token, recovery_token |
| net.request_status | ERROR, PENDING, SUCCESS |
| public.alignment_kind_enum | performance, timeline, version |
| public.artifact_kind | analysis_report, audio_enhanced, audio_original, audio_rendered, midi_corrected, midi_performance, musicxml_score, rendered_score, stems |
| public.entity_kind | beat, cadence, chord, measure, motif, note, phrase, section |
| public.job_stage | cancelled, claimed, failed, queued, running, succeeded |
| public.timeline_unit_enum | beats, measures, samples, score_position, seconds, ticks |
| public.workflow_kind | compare, correct, create, export, understand |
| realtime.action | DELETE, ERROR, INSERT, TRUNCATE, UPDATE |
| realtime.equality_op | eq, gt, gte, ilike, imatch, in, is, isdistinct, like, lt, lte, match, neq |
| storage.buckettype | ANALYTICS, STANDARD, VECTOR |

## Relations

```mermaid
erDiagram

"public.alignments" }o--|| "public.artifact_versions" : "FOREIGN KEY (target_version_id) REFERENCES artifact_versions(id) ON DELETE CASCADE"
"public.alignments" }o--|| "public.artifact_versions" : "FOREIGN KEY (version_id) REFERENCES artifact_versions(id) ON DELETE CASCADE"
"public.artifact_versions" }o--|| "public.artifacts" : "FOREIGN KEY (artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE"
"public.artifact_versions" }o--o| "public.artifact_versions" : "FOREIGN KEY (parent_version_id) REFERENCES artifact_versions(id) ON DELETE SET NULL"
"public.artifacts" }o--|| "public.works" : "FOREIGN KEY (work_id) REFERENCES works(id) ON DELETE CASCADE"
"public.entities" }o--|| "public.artifact_versions" : "FOREIGN KEY (version_id) REFERENCES artifact_versions(id) ON DELETE CASCADE"
"public.insights" }o--|| "public.artifact_versions" : "FOREIGN KEY (version_id) REFERENCES artifact_versions(id) ON DELETE CASCADE"
"public.jobs" }o--|| "public.workflows" : "FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE"
"public.workflows" }o--|| "public.projects" : "FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE"
"public.workflows" }o--o| "public.artifact_versions" : "FOREIGN KEY (target_version_id) REFERENCES artifact_versions(id) ON DELETE SET NULL"
"public.works" }o--|| "public.projects" : "FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE"

"public.alignments" {
  double_precision confidence
  timestamp_with_time_zone created_at
  uuid id
  alignment_kind_enum kind
  jsonb mapping_data
  uuid produced_by_job_id
  timeline_unit_enum source_unit
  timeline_unit_enum target_unit
  uuid target_version_id FK
  uuid version_id FK
}
"public.artifact_versions" {
  uuid artifact_id FK
  bigint byte_size
  timestamp_with_time_zone created_at
  uuid created_by
  uuid id
  text label
  uuid__ lineage
  jsonb metadata
  uuid parent_version_id FK
  uuid produced_by_job_id
  text sha256
  text storage_bucket
  text storage_key
}
"public.artifacts" {
  timestamp_with_time_zone created_at
  uuid id
  artifact_kind kind
  text mime_type
  uuid work_id FK
}
"public.entities" {
  jsonb cadence_chords
  text cadence_kind
  double_precision cadence_position_seconds
  text chord_bass
  double_precision chord_end_seconds
  text chord_quality
  text chord_root
  double_precision chord_start_seconds
  double_precision end_beat
  integer end_measure
  double_precision end_seconds
  uuid id
  entity_kind kind
  text label
  double_precision note_amplitude
  double_precision note_end_seconds
  integer note_pitch
  double_precision note_start_seconds
  integer note_velocity
  integer note_voice
  double_precision start_beat
  integer start_measure
  double_precision start_seconds
  uuid version_id FK
}
"public.insights" {
  text claim
  double_precision confidence
  timestamp_with_time_zone created_at
  uuid created_by
  uuid__ entity_ids
  jsonb evidence
  uuid id
  text kind
  uuid produced_by_job_id
  jsonb provenance
  jsonb span
  uuid version_id FK
}
"public.jobs" {
  text cache_key
  text capability_name
  text capability_version
  timestamp_with_time_zone completed_at
  timestamp_with_time_zone created_at
  uuid created_by
  jsonb error_details
  text error_message
  uuid execution_token
  uuid id
  uuid__ input_version_ids
  timestamp_with_time_zone lease_expires_at
  integer max_retries
  uuid__ output_version_ids
  jsonb parameters
  double_precision progress
  jsonb provenance
  integer retry_count
  job_stage stage
  timestamp_with_time_zone started_at
  text status_message
  text worker_id
  uuid workflow_id FK
}
"public.projects" {
  timestamp_with_time_zone archived_at
  timestamp_with_time_zone created_at
  text description
  uuid id
  text name
  uuid owner_id
  timestamp_with_time_zone updated_at
}
"public.worker_heartbeats" {
  jsonb capabilities
  timestamp_with_time_zone heartbeat_at
  timestamp_with_time_zone started_at
  text status
  text worker_id
}
"public.workflows" {
  timestamp_with_time_zone created_at
  uuid id
  workflow_kind kind
  jsonb parameters
  uuid project_id FK
  uuid target_version_id FK
}
"public.works" {
  text composer
  timestamp_with_time_zone created_at
  uuid id
  uuid project_id FK
  text title
  timestamp_with_time_zone updated_at
}
```

---

> Generated by [tbls](https://github.com/k1LoW/tbls)
