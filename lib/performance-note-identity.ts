export const MIDI_SERIALIZATION_TOLERANCE_SECONDS = 0.005;

export type AlignmentPerformanceEventIdentity = {
  event_id: string;
  pitch: number;
  onset_seconds: number;
  duration_seconds: number;
  velocity: number;
};

export type PianoRollEntityNote = {
  id?: string;
  pitch: number;
  start: number;
  end: number;
  velocity: number;
};

function finite(value: number): boolean {
  return Number.isFinite(value);
}

function withinSerializationTolerance(left: number, right: number): boolean {
  return finite(left)
    && finite(right)
    && Math.abs(left - right) <= MIDI_SERIALIZATION_TOLERANCE_SECONDS;
}

/**
 * Resolve a Partitura performance event back to the LC note entity that was
 * serialized into the exact MIDI Version.
 *
 * This is not an alignment heuristic: pitch and velocity must match exactly,
 * onset and duration must both survive the bounded MIDI round-trip tolerance,
 * and exactly one entity may satisfy the descriptor. We never choose a nearest
 * candidate.
 */
export function matchPerformanceEventToPianoRollNote(
  event: AlignmentPerformanceEventIdentity,
  notes: readonly PianoRollEntityNote[],
): PianoRollEntityNote | null {
  if (
    !Number.isSafeInteger(event.pitch)
    || event.pitch < 0
    || event.pitch > 127
    || !Number.isSafeInteger(event.velocity)
    || event.velocity < 0
    || event.velocity > 127
    || !finite(event.onset_seconds)
    || !finite(event.duration_seconds)
    || event.duration_seconds < 0
  ) {
    return null;
  }

  const eventEnd = event.onset_seconds + event.duration_seconds;
  const matches = notes.filter((note) =>
    Boolean(note.id)
    && note.pitch === event.pitch
    && note.velocity === event.velocity
    && withinSerializationTolerance(note.start, event.onset_seconds)
    && withinSerializationTolerance(note.end, eventEnd),
  );
  return matches.length === 1 ? matches[0] : null;
}

/** Resolve a relation's performed events only when every event maps uniquely. */
export function matchPerformanceEventsToPianoRollNoteIds(
  events: readonly AlignmentPerformanceEventIdentity[],
  notes: readonly PianoRollEntityNote[],
): string[] | null {
  if (events.length === 0) return null;
  const ids: string[] = [];
  for (const event of events) {
    const note = matchPerformanceEventToPianoRollNote(event, notes);
    if (!note?.id) return null;
    ids.push(note.id);
  }
  return [...new Set(ids)];
}
