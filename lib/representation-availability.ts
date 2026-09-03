import type { Job } from "./domain.types";
import type { RepresentationId } from "./representations";
import type { RepresentationEntry, RepresentationKind } from "./stores/workspace";

export type RepresentationAvailability = {
  originalAudio: boolean;
  performanceMidi: boolean;
  score: boolean;
  analysis: boolean;
  byKind: Map<RepresentationKind, RepresentationEntry>;
  availableKinds: RepresentationKind[];
};

export type RepresentationReadiness = "ready" | "preparing" | "failed" | "unavailable";
export type RepresentationReadinessById = Record<RepresentationId, RepresentationReadiness>;

const ACTIVE_JOB_STATES = new Set(["queued", "claimed", "running"]);
const JOB_TARGET_IDS = new Set<RepresentationId>(["piano_roll", "score"]);

function targetList(value: unknown): RepresentationId[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (target): target is RepresentationId => typeof target === "string" && JOB_TARGET_IDS.has(target as RepresentationId),
  );
}

function declaredTargets(job: Job): RepresentationId[] {
  return targetList(job.parameters.representation_targets);
}

function failedTargets(job: Job): RepresentationId[] {
  return targetList(job.error_details.failed_representation_targets);
}

function readinessFromJobs(target: RepresentationId, jobs: Job[]): RepresentationReadiness {
  for (const job of jobs) {
    if (!declaredTargets(job).includes(target)) continue;

    if (ACTIVE_JOB_STATES.has(job.lifecycle.current)) return "preparing";
    if (job.lifecycle.current === "failed" && failedTargets(job).includes(target)) return "failed";

    // Work-bundle Jobs are newest-first. The newest authoritative attempt that
    // declared responsibility for this output settles the interpretation. A
    // succeeded/cancelled attempt without a usable Version, or a failed attempt
    // that did not identify this output, is unavailable rather than guessed-failed.
    return "unavailable";
  }
  return "unavailable";
}

/**
 * Canonical derivation of what a loaded work has available.
 *
 * All consumers (RepresentationStack, LibraryPanel, etc.) should derive
 * availability from `workspace.representations` through this single helper so
 * that "is the score here?", "is there a piano roll?", etc. never drift.
 */
export function deriveAvailability(
  representations: RepresentationEntry[],
  insightCount: number,
): RepresentationAvailability {
  const byKind = new Map(representations.map((item) => [item.kind, item]));
  return {
    originalAudio: byKind.has("waveform"),
    performanceMidi: byKind.has("piano_roll"),
    score: byKind.has("score"),
    analysis: insightCount > 0,
    byKind,
    availableKinds: [...byKind.keys()],
  };
}

/**
 * Derive user-facing readiness from durable outputs plus server Job truth.
 *
 * A materialized representation is always Ready, even when an older Job failed.
 * Missing outputs are interpreted only from the newest Job that explicitly
 * declared responsibility for that output. Malformed/ambiguous metadata fails
 * closed to Unavailable rather than manufacturing a failure state.
 */
export function deriveRepresentationReadiness(
  representations: RepresentationEntry[],
  jobs: Job[],
): RepresentationReadinessById {
  const byKind = new Map(representations.map((item) => [item.kind, item]));
  const originalReady = byKind.has("waveform");

  return {
    listen: originalReady ? "ready" : "unavailable",
    spectrogram: originalReady ? "ready" : "unavailable",
    piano_roll: byKind.has("piano_roll") ? "ready" : readinessFromJobs("piano_roll", jobs),
    score: byKind.has("score") ? "ready" : readinessFromJobs("score", jobs),
  };
}
