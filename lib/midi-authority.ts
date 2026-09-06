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

const EXPLICIT_PIANO_ROLL_ROLES = new Set<MidiSemanticRole>([
  "performance_transcription",
  "edited_performance",
  "creative_take",
]);

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
