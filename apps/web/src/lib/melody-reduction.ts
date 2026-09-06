import type { Insight } from "@/lib/domain.types";
import type { RepresentationEntry } from "@/lib/stores/workspace";

export const MELODY_NOTE_MATCH_EPSILON_SECONDS = 0.005;

type MelodyCandidateNote = {
  pitch: number;
  startSeconds: number;
  endSeconds: number;
  velocity: number | null;
};

export type MelodyReductionNote = MelodyCandidateNote & {
  id: string;
};

export type MelodyReductionProjection =
  | {
      status: "supported";
      sourceVersionId: string;
      notes: MelodyReductionNote[];
      startSeconds: number;
      endSeconds: number;
    }
  | {
      status: "unavailable";
      reason: string;
    };

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function parseCandidateNote(value: unknown): MelodyCandidateNote | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  const pitch = finiteNumber(item.pitch);
  const startSeconds = finiteNumber(item.start_seconds);
  const endSeconds = finiteNumber(item.end_seconds);
  const velocity = finiteNumber(item.velocity);
  if (
    pitch === null ||
    startSeconds === null ||
    endSeconds === null ||
    !Number.isInteger(pitch) ||
    pitch < 0 ||
    pitch > 127 ||
    startSeconds < 0 ||
    endSeconds <= startSeconds
  ) {
    return null;
  }
  return { pitch, startSeconds, endSeconds, velocity };
}

/**
 * Resolve the model's persisted note tuples back to the exact note-entity IDs
 * already owned by the same immutable MIDI Version.
 *
 * LStoM evidence is serialized to four decimal places while MIDI parsing may
 * round-trip times at tick precision, so the tuple reconciliation permits only
 * a 5 ms boundary tolerance. Identity is still fail-closed: a tuple must map to
 * exactly one unused source entity. No pitch-only, nearest-note, or top-voice
 * fallback is allowed.
 */
export function projectMelodyReduction(
  insight: Insight & { version_id?: string },
  pianoRoll: RepresentationEntry,
): MelodyReductionProjection {
  if (insight.kind !== "melody") {
    return { status: "unavailable", reason: "not melody evidence" };
  }
  if (pianoRoll.kind !== "piano_roll" || !pianoRoll.versionId || !pianoRoll.notes?.length) {
    return { status: "unavailable", reason: "exact Piano Roll note evidence is unavailable" };
  }
  if (!insight.version_id || insight.version_id !== pianoRoll.versionId) {
    return { status: "unavailable", reason: "melody evidence and Piano Roll do not share one exact Version" };
  }

  const rawNotes = insight.evidence?.notes;
  if (!Array.isArray(rawNotes) || rawNotes.length === 0) {
    return { status: "unavailable", reason: "melody evidence has no proposed note objects" };
  }
  const candidates = rawNotes.map(parseCandidateNote);
  if (candidates.some((note) => note === null)) {
    return { status: "unavailable", reason: "melody note evidence is malformed" };
  }

  const sourceNotes = pianoRoll.notes.filter(
    (note): note is typeof note & { id: string } =>
      typeof note.id === "string" && note.id.length > 0,
  );
  const usedIds = new Set<string>();
  const matched: MelodyReductionNote[] = [];

  for (const candidate of candidates as MelodyCandidateNote[]) {
    const matches = sourceNotes.filter((source) =>
      !usedIds.has(source.id) &&
      source.pitch === candidate.pitch &&
      Math.abs(source.start - candidate.startSeconds) <= MELODY_NOTE_MATCH_EPSILON_SECONDS &&
      Math.abs(source.end - candidate.endSeconds) <= MELODY_NOTE_MATCH_EPSILON_SECONDS,
    );
    if (matches.length !== 1) {
      return {
        status: "unavailable",
        reason: matches.length === 0
          ? "a proposed melody note cannot be mapped to an exact source note entity"
          : "a proposed melody note maps ambiguously to multiple source note entities",
      };
    }
    const source = matches[0];
    usedIds.add(source.id);
    matched.push({
      id: source.id,
      pitch: source.pitch,
      startSeconds: source.start,
      endSeconds: source.end,
      velocity: Number.isFinite(source.velocity) ? source.velocity : candidate.velocity,
    });
  }

  return {
    status: "supported",
    sourceVersionId: pianoRoll.versionId,
    notes: matched,
    startSeconds: Math.min(...matched.map((note) => note.startSeconds)),
    endSeconds: Math.max(...matched.map((note) => note.endSeconds)),
  };
}
