import type { MusicalSelection, SelectionOrigin } from "@/lib/stores/workspace";

export type NoteLike = { id?: string; start: number; end: number };

/**
 * Exact measure→time mapping on the score: measure index i starts at
 * measurement[i]; the range's end is the start of the measure after the last
 * selected measure (or the last available boundary when end is the final
 * measure). This is a direct reading of the score's own measure timing data,
 * so it is NOT approximate on the score's timeline.
 *
 * If the selection includes the final measure and there is no next boundary,
 * returns null (cannot honestly derive an end time without fabricating).
 */
export function timeRangeFromMeasures(
  startMeasure: number,
  endMeasure: number,
  measureStarts: number[],
  scoreDuration?: number | null,
): { start: number; end: number; domain: "notation" } | null {
  const startIndex = Math.max(0, Math.min(startMeasure, measureStarts.length - 1));
  const endIndex = Math.max(startIndex, Math.min(endMeasure, measureStarts.length - 1));
  const start = measureStarts[startIndex] ?? 0;
  const nextStart = measureStarts[endIndex + 1];
  if (nextStart != null) {
    return { start, end: nextStart, domain: "notation" };
  }
  // Final measure: use scoreDuration if provided and > start; otherwise we
  // cannot honestly determine the end boundary — return null instead of
  // fabricating a zero-length range.
  if (scoreDuration != null && scoreDuration > start) {
    return { start, end: scoreDuration, domain: "notation" };
  }
  return null;
}

/**
 * Coarse, explicitly-approximate measure derivation from a time-based
 * selection: every measure whose start boundary falls inside [timeStart,
 * timeEnd] is included. The score plays in notation time while the waveform
 * and piano roll play in performance time, so this mapping crosses timing
 * domains and is only ever presented as approximate.
 */
export function measureRangeFromTime(
  timeStart: number,
  timeEnd: number,
  measureStarts: number[],
): { start: number; end: number } | null {
  if (measureStarts.length === 0) return null;
  let start: number | null = null;
  let end: number | null = null;
  measureStarts.forEach((boundary, index) => {
    if (boundary >= timeStart && boundary <= timeEnd) {
      if (start === null) start = index;
      end = index;
    }
  });
  // If the selection is shorter than a measure but sits inside one, still map
  // approximately to that containing measure so a highlight is always visible.
  if (start === null || end === null) {
    for (let index = 0; index < measureStarts.length; index += 1) {
      const next = measureStarts[index + 1] ?? Number.POSITIVE_INFINITY;
      if (timeStart < next && timeEnd >= measureStarts[index]) {
        start = index;
        end = index;
        break;
      }
    }
  }
  if (start === null || end === null) return null;
  return { start, end };
}

/** Note ids whose span overlaps the given time range (exact, same timeline). */
export function noteIdsInRange(notes: NoteLike[], timeStart: number, timeEnd: number): string[] {
  return notes
    .filter((note) => note.start < timeEnd && note.end > timeStart)
    .map((note) => note.id)
    .filter((id): id is string => Boolean(id));
}

/**
 * Time extent of a set of piano-roll notes (exact — notes and the shared
 * transport share the performance timeline).
 */
export function timeRangeFromNotes(notes: NoteLike[], ids: string[]): { start: number; end: number } | null {
  const selected = notes.filter((note) => ids.includes(note.id ?? ""));
  if (selected.length === 0) return null;
  const start = Math.min(...selected.map((note) => note.start));
  const end = Math.max(...selected.map((note) => note.end));
  return { start, end };
}

/**
 * Composes a selection object for a pixel-level (time-range-only) selection,
 * e.g. waveform drag-select or piano-roll region select.
 */
export function composeTimeSelection(
  start: number,
  end: number,
  notes: NoteLike[] = [],
  origin: Exclude<SelectionOrigin, null>,
): MusicalSelection {
  const timeRange = { start, end, domain: "performance" as const };
  const selection: MusicalSelection = {
    timeRange,
    provenance: { origin, timeExact: true, measureApproximate: false },
  };
  const ids = noteIdsInRange(notes, start, end);
  if (ids.length > 0) selection.noteIds = ids;
  return selection;
}

/**
 * Composes a selection object from a direct score-measure selection: the
 * measure range is exact on the score, and the accompanying timeRange is an
 * exact reading of the score's measure timing data (notation time). If the
 * measure range includes the final measure and no honest end boundary exists,
 * timeRange is omitted.
 */
export function composeMeasureSelection(
  startMeasure: number,
  endMeasure: number,
  measureStarts: number[],
  scoreDuration?: number | null,
  origin: "score" | null = "score",
): MusicalSelection {
  const timeRange = timeRangeFromMeasures(startMeasure, endMeasure, measureStarts, scoreDuration);
  const selection: MusicalSelection = {
    measureRange: { start: startMeasure, end: endMeasure },
    provenance: { origin, timeExact: false, measureApproximate: false },
  };
  if (timeRange) {
    selection.timeRange = timeRange;
  }
  return selection;
}

/**
 * Composes a selection object from a piano-roll note selection: noteIds and
 * their time extent are both exact readings.
 */
export function composeNoteSelection(
  notes: NoteLike[],
  ids: string[],
  origin: "piano_roll" = "piano_roll",
): MusicalSelection | null {
  const timeRange = timeRangeFromNotes(notes, ids);
  if (!timeRange) return null;
  return {
    timeRange: { ...timeRange, domain: "performance" },
    noteIds: ids,
    provenance: { origin, timeExact: true, measureApproximate: false },
  };
}