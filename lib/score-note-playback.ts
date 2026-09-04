const FALLBACK_MEASURE_SECONDS = 2;

export const SCORE_PLAYBACK_ACTIVE_ATTR = "data-score-playback-active";

export type ScoreNotePlaybackEvent = {
  startSeconds: number;
  endSeconds: number;
  noteheads: Element[];
};

type FractionLike = { RealValue?: number } | null | undefined;

type SourceNoteLike = {
  Length?: FractionLike;
  isRest?: () => boolean;
};

type GraphicalNoteLike = {
  sourceNote?: SourceNoteLike;
  getNoteheadSVGs?: () => Element[];
};

type GraphicalVoiceEntryLike = {
  notes?: GraphicalNoteLike[];
};

type GraphicalStaffEntryLike = {
  relInMeasureTimestamp?: FractionLike;
  graphicalVoiceEntries?: GraphicalVoiceEntryLike[];
};

type GraphicalMeasureLike = {
  parentSourceMeasure?: { Duration?: FractionLike };
  staffEntries?: GraphicalStaffEntryLike[];
};

type OsmdLike = {
  GraphicSheet?: {
    MeasureList?: GraphicalMeasureLike[][];
  };
};

function realValue(value: FractionLike): number | null {
  const result = value?.RealValue;
  return typeof result === "number" && Number.isFinite(result) ? result : null;
}

function measureEndSeconds(
  measureStarts: number[],
  measureIndex: number,
  scoreDuration: number | null | undefined,
): number | null {
  const start = measureStarts[measureIndex];
  if (!Number.isFinite(start)) return null;

  const next = measureStarts[measureIndex + 1];
  if (Number.isFinite(next) && next > start) return next;
  if (typeof scoreDuration === "number" && Number.isFinite(scoreDuration) && scoreDuration > start) {
    return scoreDuration;
  }

  const previous = measureStarts[measureIndex - 1];
  const previousSpan = Number.isFinite(previous) ? start - previous : 0;
  return start + (previousSpan > 0 ? previousSpan : FALLBACK_MEASURE_SECONDS);
}

/**
 * Build the playback-time -> rendered-notehead map once after OSMD renders.
 *
 * OSMD exposes a stable graphical/source-note object model even though its
 * cursor iterator is stateful. We use each GraphicalStaffEntry's timestamp
 * relative to its SourceMeasure and scale it onto ListenCloser's persisted
 * notation-time measure starts. This keeps the shared transport authoritative
 * and avoids advancing/resetting OSMD's cursor on every React playhead update.
 */
export function buildScoreNotePlaybackEvents(
  osmd: OsmdLike | null | undefined,
  measureStarts: number[],
  scoreDuration?: number | null,
): ScoreNotePlaybackEvent[] {
  const measureList = osmd?.GraphicSheet?.MeasureList;
  if (!Array.isArray(measureList) || measureStarts.length === 0) return [];

  const events: ScoreNotePlaybackEvent[] = [];
  const measureCount = Math.min(measureList.length, measureStarts.length);

  for (let measureIndex = 0; measureIndex < measureCount; measureIndex += 1) {
    const measureStart = measureStarts[measureIndex];
    const measureEnd = measureEndSeconds(measureStarts, measureIndex, scoreDuration);
    if (!Number.isFinite(measureStart) || measureEnd == null || measureEnd <= measureStart) continue;

    const graphicalMeasures = measureList[measureIndex] ?? [];
    const sourceDuration = graphicalMeasures
      .map((measure) => realValue(measure?.parentSourceMeasure?.Duration))
      .find((duration): duration is number => duration != null && duration > 0);
    if (sourceDuration == null) continue;

    const measureSpanSeconds = measureEnd - measureStart;

    for (const graphicalMeasure of graphicalMeasures) {
      for (const staffEntry of graphicalMeasure?.staffEntries ?? []) {
        const relativeStart = realValue(staffEntry?.relInMeasureTimestamp);
        if (relativeStart == null) continue;

        for (const voiceEntry of staffEntry.graphicalVoiceEntries ?? []) {
          for (const graphicalNote of voiceEntry.notes ?? []) {
            const sourceNote = graphicalNote.sourceNote;
            if (!sourceNote || sourceNote.isRest?.() === true) continue;

            const noteLength = realValue(sourceNote.Length);
            if (noteLength == null || noteLength <= 0) continue;

            let noteheads: Element[];
            try {
              noteheads = (graphicalNote.getNoteheadSVGs?.() ?? []).filter(Boolean);
            } catch {
              continue;
            }
            if (noteheads.length === 0) continue;

            const startSeconds = measureStart + (relativeStart / sourceDuration) * measureSpanSeconds;
            const unclampedEnd = startSeconds + (noteLength / sourceDuration) * measureSpanSeconds;
            const endSeconds = Math.min(measureEnd, unclampedEnd);
            if (!Number.isFinite(startSeconds) || !Number.isFinite(endSeconds) || endSeconds <= startSeconds) continue;

            events.push({ startSeconds, endSeconds, noteheads });
          }
        }
      }
    }
  }

  events.sort((left, right) => left.startSeconds - right.startSeconds || left.endSeconds - right.endSeconds);
  return events;
}

export function activeScoreNoteheadsAt(events: ScoreNotePlaybackEvent[], playheadTime: number): Set<Element> {
  const active = new Set<Element>();
  if (!Number.isFinite(playheadTime)) return active;

  for (const event of events) {
    if (event.startSeconds > playheadTime) break;
    if (playheadTime >= event.startSeconds && playheadTime < event.endSeconds) {
      for (const notehead of event.noteheads) active.add(notehead);
    }
  }
  return active;
}

export function clearScoreActiveNoteheads(activeNoteheads: Set<Element>): void {
  for (const notehead of activeNoteheads) notehead.removeAttribute(SCORE_PLAYBACK_ACTIVE_ATTR);
  activeNoteheads.clear();
}

/** Apply only the active-note delta so transport ticks never rerender OSMD. */
export function syncScoreActiveNoteheads(
  events: ScoreNotePlaybackEvent[],
  playheadTime: number,
  previousActive: Set<Element>,
): Set<Element> {
  const nextActive = activeScoreNoteheadsAt(events, playheadTime);

  for (const notehead of previousActive) {
    if (!nextActive.has(notehead)) notehead.removeAttribute(SCORE_PLAYBACK_ACTIVE_ATTR);
  }
  for (const notehead of nextActive) {
    if (!previousActive.has(notehead)) notehead.setAttribute(SCORE_PLAYBACK_ACTIVE_ATTR, "true");
  }

  return nextActive;
}
