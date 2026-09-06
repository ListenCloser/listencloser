import type { RepresentationEntry, RepresentationKind } from "./stores/workspace";

export type RepresentationAvailability = {
  originalAudio: boolean;
  performanceMidi: boolean;
  score: boolean;
  analysis: boolean;
  byKind: Map<RepresentationKind, RepresentationEntry>;
  availableKinds: RepresentationKind[];
};

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
