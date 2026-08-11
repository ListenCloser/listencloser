export interface Project {
  id: string
  owner_id: string
  name: string
  description: string
  created_at: string
  updated_at: string
  archived_at: string | null
}

export interface Work {
  id: string
  project_id: string
  title: string
  composer: string | null
  created_at: string
  updated_at: string
}

export type ArtifactKind =
  | "audio_original"
  | "audio_enhanced"
  | "audio_rendered"
  | "midi_performance"
  | "midi_corrected"
  | "musicxml_score"
  | "rendered_score"
  | "stems"
  | "analysis_report"

export interface Artifact {
  id: string
  work_id: string
  kind: ArtifactKind
  mime_type: string
  created_at: string
}

export interface Version {
  id: string
  artifact_id: string
  parent_version_id: string | null
  lineage: string[]
  storage_key: string
  storage_bucket: string
  byte_size: number | null
  sha256: string | null
  created_at: string
  created_by: string | null
  produced_by_job_id: string | null
  label: string
  metadata: Record<string, unknown>
}

export type EntityKind =
  | "note"
  | "chord"
  | "beat"
  | "measure"
  | "phrase"
  | "section"
  | "cadence"
  | "motif"

export interface NoteEntity {
  pitch: number
  start_seconds: number
  end_seconds: number
  velocity: number
  voice: number
}

export interface ChordEntity {
  root: string
  quality: string
  bass: string | null
  start_seconds: number
  end_seconds: number
}

export interface Cadence {
  kind: string
  chords: string[]
  position_seconds: number
}

export interface Span {
  start_seconds: number | null
  end_seconds: number | null
  start_beat: number | null
  end_beat: number | null
  start_measure: number | null
  end_measure: number | null
}

export interface Entity {
  id: string
  version_id: string
  kind: EntityKind
  span: Span
  note: NoteEntity | null
  chord: ChordEntity | null
  cadence: Cadence | null
  label: string
}

export interface Insight {
  id: string
  version_id: string
  kind: string
  claim: string
  span: Span
  entity_ids: string[]
  evidence: Record<string, unknown>
  confidence: number
  provenance: Record<string, unknown>
  created_at: string
  created_by: string | null
  produced_by_job_id: string | null
}

export type AlignmentKind = "timeline" | "version" | "performance"

export type TimelineUnit =
  | "seconds"
  | "samples"
  | "beats"
  | "measures"
  | "ticks"
  | "score_position"

export interface Alignment {
  id: string
  version_id: string
  target_version_id: string
  kind: AlignmentKind
  source_unit: TimelineUnit
  target_unit: TimelineUnit
  mapping_data: Record<string, unknown>
  confidence: number
  created_at: string
  produced_by_job_id: string | null
}

export interface Selection {
  time_start_seconds: number | null
  time_end_seconds: number | null
  beat_start: number | null
  beat_end: number | null
  measure_start: number | null
  measure_end: number | null
  note_indices: number[]
  entity_ids: string[]
}

export type WorkflowKind = "understand" | "correct" | "compare" | "create" | "export"

export interface Capability {
  name: string
  version: string
  accepted_input_kinds: ArtifactKind[]
  produces_output_kinds: ArtifactKind[]
  parameters: Record<string, unknown>
  failure_modes: string[]
}

export interface Workflow {
  id: string
  project_id: string
  kind: WorkflowKind
  target_version_id: string | null
  parameters: Record<string, unknown>
  created_at: string
}

export type JobStage = "queued" | "claimed" | "running" | "succeeded" | "failed" | "cancelled"

export interface ProcessingStatus {
  stage: JobStage
  progress: number
  message: string
  started_at: string | null
  completed_at: string | null
}

export interface JobLifecycle {
  current: JobStage
  progress: number
  message: string
  stages: ProcessingStatus[]
  retry_count: number
  max_retries: number
  lease_expires_at: string | null
  started_at: string | null
  completed_at: string | null
}

export interface Job {
  id: string
  workflow_id: string
  capability: Capability
  lifecycle: JobLifecycle
  input_version_ids: string[]
  output_version_ids: string[]
  parameters: Record<string, unknown>
  cache_key: string | null
  error: string | null
  error_details: Record<string, unknown>
  provenance: Record<string, unknown>
  created_at: string
  created_by: string | null
}

export interface JobStatus {
  id: string
  workflow_id: string
  capability: string
  stage: JobStage
  progress: number
  message: string
  error: string | null
  input_version_ids: string[]
  output_version_ids: string[]
}

export interface VersionResource {
  version: Version
  artifact: Artifact
  signed_url: string
}

export interface WorkBundleArtifact {
  artifact: Artifact
  versions: Version[]
  latest_version: Version | null
  signed_url: string | null
}

export interface WorkBundle {
  work: Work
  artifacts: WorkBundleArtifact[]
  jobs: Job[]
}
