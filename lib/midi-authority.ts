import type { WorkArtifactBundle, WorkBundle } from "./domain.types";

export type MidiSemanticRole =
  | "performance_transcription"
  | "edited_performance"
  | "creative_take"
  | "score_reconstruction"
  | "notation_normalized"
  | "unknown";

export type MidiRepresentationDescriptor = {
  role: MidiSemanticRole;
  artifact: WorkArtifactBundle;
  versionId: string;
};

export type MidiAuthority = {
  canonicalPerformance: MidiRepresentationDescriptor | null;
  defaultPianoRoll: MidiRepresentationDescriptor | null;
  representations: MidiRepresentationDescriptor[];
};

export type PianoRollSourceOption = {
  versionId: string;
  role: "performance_transcription" | "edited_performance" | "creative_take";
  label: string;
};

const EXPLICIT_PIANO_ROLL_ROLES = new Set<MidiSemanticRole>([
  "performance_transcription",
  "edited_performance",
  "creative_take",
]);

const PIANO_ROLL_ROLE_ORDER: Record<PianoRollSourceOption["role"], number> = {
  performance_transcription: 0,
  edited_performance: 1,
  creative_take: 2,
};

function metadataString(metadata: Record<string, unknown>, key: string): string | null {
  const value = metadata[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function producingCapabilityName(
  bundle: WorkBundle,
  producedByJobId: string | null | undefined,
): string | null {
  if (!producedByJobId) return null;
  return bundle.jobs.find((job) => job.id === producedByJobId)?.capability.name ?? null;
}

/**
 * Classify the exact latest MIDI Version of one artifact from immutable artifact,
 * Version metadata, and producing-job provenance.
 *
 * Broad `midi_corrected` kind is deliberately insufficient: legacy rows that do
 * not prove which semantic world they belong to remain `unknown`.
 */
export function describeMidiRepresentation(
  bundle: WorkBundle,
  artifact: WorkArtifactBundle,
): MidiRepresentationDescriptor | null {
  const version = artifact.latest_version;
  if (!version) return null;

  if (artifact.artifact.kind === "midi_performance") {
    return {
      role: "performance_transcription",
      artifact,
      versionId: version.id,
    };
  }

  if (artifact.artifact.kind !== "midi_corrected") return null;

  const metadata = (version.metadata ?? {}) as Record<string, unknown>;
  const operation = metadataString(metadata, "operation");
  const scoreEngine = metadataString(metadata, "score_engine_requested");
  const capability = producingCapabilityName(bundle, version.produced_by_job_id);

  let role: MidiSemanticRole = "unknown";
  if (operation === "transpose" || capability === "transform" || capability === "variation") {
    role = "creative_take";
  } else if (capability === "correct") {
    role = "edited_performance";
  } else if (scoreEngine === "pm2s") {
    role = "score_reconstruction";
  } else if (scoreEngine || capability === "score") {
    role = "notation_normalized";
  }

  return { role, artifact, versionId: version.id };
}

/**
 * Resolve the safe default authority for current product surfaces.
 *
 * The Piano Roll default remains the canonical performance transcription. A
 * corrected or creative take may be focused explicitly, but its mere presence
 * or recency is not permission to supersede the performance interpretation.
 */
export function resolveMidiAuthority(bundle: WorkBundle): MidiAuthority {
  const representations = bundle.artifacts.flatMap((artifact) => {
    if (!artifact.signed_url) return [];
    const descriptor = describeMidiRepresentation(bundle, artifact);
    return descriptor ? [descriptor] : [];
  });
  const canonicalPerformance = representations.find(
    (descriptor) => descriptor.role === "performance_transcription",
  ) ?? null;

  return {
    canonicalPerformance,
    defaultPianoRoll: canonicalPerformance,
    representations,
  };
}

/**
 * Resolve an intentional Piano Roll focus by exact Version identity.
 * Score-domain and ambiguous MIDI are never silently projected into performance
 * space, even when the caller supplies their exact Version id.
 */
export function resolveExplicitPianoRollMidi(
  bundle: WorkBundle,
  versionId: string,
): MidiRepresentationDescriptor | null {
  const descriptor = resolveMidiAuthority(bundle).representations.find(
    (candidate) => candidate.versionId === versionId,
  );
  if (!descriptor || !EXPLICIT_PIANO_ROLL_ROLES.has(descriptor.role)) return null;
  return descriptor;
}

/**
 * Resolve the one corrected performance MIDI produced by a completed correction
 * Job, independent of output array order or auxiliary outputs such as playback.
 */
export function resolveCorrectionOutputMidi(
  bundle: WorkBundle,
  producingJobId: string,
  outputVersionIds: readonly string[],
): MidiRepresentationDescriptor | null {
  const outputIds = new Set(outputVersionIds);
  const matches = resolveMidiAuthority(bundle).representations.filter((descriptor) => (
    descriptor.role === "edited_performance"
    && outputIds.has(descriptor.versionId)
    && descriptor.artifact.latest_version?.produced_by_job_id === producingJobId
  ));
  return matches.length === 1 ? matches[0] : null;
}

/**
 * Find synthesized playback proven to belong to one exact MIDI Version.
 *
 * New renders carry an explicit source_midi_version_id and parent the source
 * MIDI directly. Older canonical transcription renders predate that contract,
 * so same producing-Job identity is accepted as their bounded compatibility
 * proof. An explicit source id, when present, is authoritative and cannot be
 * overridden by Job coincidence.
 */
export function resolveRenderedPlaybackForMidi(
  bundle: WorkBundle,
  midiVersionId: string,
): WorkArtifactBundle | null {
  const midiDescriptor = resolveMidiAuthority(bundle).representations.find(
    (candidate) => candidate.versionId === midiVersionId,
  );
  const midiVersion = midiDescriptor?.artifact.latest_version;
  if (!midiDescriptor || !midiVersion) return null;

  return bundle.artifacts.find((artifact) => {
    const version = artifact.latest_version;
    if (
      artifact.artifact.kind !== "audio_rendered"
      || !artifact.signed_url
      || !version
      || version.metadata?.representation === "melody_playback"
    ) {
      return false;
    }

    const metadata = (version.metadata ?? {}) as Record<string, unknown>;
    const explicitSource = metadataString(metadata, "source_midi_version_id");
    if (explicitSource !== null) return explicitSource === midiVersionId;
    if (version.parent_version_id === midiVersionId) return true;

    return Boolean(
      midiVersion.produced_by_job_id
      && version.produced_by_job_id === midiVersion.produced_by_job_id,
    );
  }) ?? null;
}

/**
 * Product-facing interpretations that may intentionally drive the Piano Roll.
 * Score reconstruction / notation MIDI and ambiguous legacy rows stay hidden;
 * users choose musical interpretations, never internal Artifact/Version kinds.
 */
export function pianoRollSourceOptions(bundle: WorkBundle): PianoRollSourceOption[] {
  return resolveMidiAuthority(bundle).representations
    .flatMap((descriptor): PianoRollSourceOption[] => {
      if (!EXPLICIT_PIANO_ROLL_ROLES.has(descriptor.role)) return [];
      const role = descriptor.role as PianoRollSourceOption["role"];
      const label = role === "performance_transcription"
        ? "Original transcription"
        : role === "edited_performance"
          ? "Corrected transcription"
          : "Creative take";
      return [{ versionId: descriptor.versionId, role, label }];
    })
    .sort((a, b) => PIANO_ROLL_ROLE_ORDER[a.role] - PIANO_ROLL_ROLE_ORDER[b.role]);
}
