export type Rational = {
  numerator: number;
  denominator: number;
};

export type AlignmentScoreEventIdentity = {
  event_id: string;
  measure_index: number;
  pitch: number;
  voice: number | null;
  staff: number | null;
  is_grace: boolean;
  rel_onset_div: number | null;
  total_measure_divs: number | null;
};

export type RenderedScoreNoteIdentity = {
  measureIndex: number;
  pitch: number;
  voice: number;
  staff: number;
  isGrace: boolean;
  relativeOnset: Rational;
  noteheads: Element[];
};

type FractionLike = {
  Numerator?: number;
  Denominator?: number;
  WholeValue?: number;
} | null | undefined;

type SourceMeasureLike = {
  measureListIndex?: number;
  Duration?: FractionLike;
};

type VoiceLike = { VoiceId?: number } | null | undefined;
type VoiceEntryLike = {
  Timestamp?: FractionLike;
  ParentVoice?: VoiceLike;
  IsGrace?: boolean;
} | null | undefined;
type StaffLike = { Id?: number } | null | undefined;
type StaffEntryLike = { ParentStaff?: StaffLike } | null | undefined;
type PitchLike = { getHalfTone?: () => number } | null | undefined;

type SourceNoteLike = {
  // OSMD's note.halfTone is explicitly transposed. Partitura parses the source
  // MusicXML pitch, so use Note.Pitch.getHalfTone() instead.
  Pitch?: PitchLike;
  IsGraceNote?: boolean;
  ParentVoiceEntry?: VoiceEntryLike;
  ParentStaffEntry?: StaffEntryLike;
  SourceMeasure?: SourceMeasureLike | null;
  isRest?: () => boolean;
};

type GraphicalNoteLike = {
  sourceNote?: SourceNoteLike;
  getNoteheadSVGs?: () => Element[];
};

type GraphicalVoiceEntryLike = { notes?: GraphicalNoteLike[] };
type GraphicalStaffEntryLike = { graphicalVoiceEntries?: GraphicalVoiceEntryLike[] };
type GraphicalMeasureLike = { staffEntries?: GraphicalStaffEntryLike[] };
type OsmdLike = { GraphicSheet?: { MeasureList?: GraphicalMeasureLike[][] } };

function finiteInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value);
}

function fractionParts(value: FractionLike): { numerator: number; denominator: number } | null {
  const numerator = value?.Numerator;
  const denominator = value?.Denominator;
  const whole = value?.WholeValue ?? 0;
  if (!finiteInteger(numerator) || !finiteInteger(denominator) || !finiteInteger(whole) || denominator <= 0) {
    return null;
  }
  const improper = whole * denominator + numerator;
  if (!Number.isSafeInteger(improper)) return null;
  return { numerator: improper, denominator };
}

function gcd(left: number, right: number): number {
  let a = Math.abs(left);
  let b = Math.abs(right);
  while (b !== 0) {
    const next = a % b;
    a = b;
    b = next;
  }
  return a || 1;
}

/** Exact rational position within a measure, derived only from OSMD source fractions. */
export function relativeMeasurePosition(
  timestamp: FractionLike,
  measureDuration: FractionLike,
): Rational | null {
  const position = fractionParts(timestamp);
  const duration = fractionParts(measureDuration);
  if (!position || !duration || duration.numerator <= 0) return null;

  const numerator = position.numerator * duration.denominator;
  const denominator = position.denominator * duration.numerator;
  if (!Number.isSafeInteger(numerator) || !Number.isSafeInteger(denominator) || denominator <= 0) {
    return null;
  }
  const divisor = gcd(numerator, denominator);
  return {
    numerator: numerator / divisor,
    denominator: denominator / divisor,
  };
}

/**
 * Extract identities from OSMD's exact source-note object graph after render.
 * No transport time or pixel geometry participates in identity.
 */
export function buildRenderedScoreNoteIdentities(
  osmd: OsmdLike | null | undefined,
): RenderedScoreNoteIdentity[] {
  const measureList = osmd?.GraphicSheet?.MeasureList;
  if (!Array.isArray(measureList)) return [];

  const identities: RenderedScoreNoteIdentity[] = [];
  for (const graphicalMeasures of measureList) {
    for (const graphicalMeasure of graphicalMeasures ?? []) {
      for (const staffEntry of graphicalMeasure?.staffEntries ?? []) {
        for (const voiceEntry of staffEntry.graphicalVoiceEntries ?? []) {
          for (const graphicalNote of voiceEntry.notes ?? []) {
            const note = graphicalNote.sourceNote;
            if (!note || note.isRest?.() === true) continue;

            const sourceMeasure = note.SourceMeasure;
            const sourceVoiceEntry = note.ParentVoiceEntry;
            const measureIndex = sourceMeasure?.measureListIndex;
            let pitch: number | null = null;
            try {
              const sourcePitch = note.Pitch?.getHalfTone?.();
              if (finiteInteger(sourcePitch)) pitch = sourcePitch;
            } catch {
              pitch = null;
            }
            const voice = sourceVoiceEntry?.ParentVoice?.VoiceId;
            const staff = note.ParentStaffEntry?.ParentStaff?.Id;
            const relativeOnset = relativeMeasurePosition(
              sourceVoiceEntry?.Timestamp,
              sourceMeasure?.Duration,
            );
            if (
              !finiteInteger(measureIndex)
              || measureIndex < 0
              || pitch == null
              || pitch < 0
              || pitch > 127
              || !finiteInteger(voice)
              || !finiteInteger(staff)
              || !relativeOnset
            ) {
              continue;
            }

            let noteheads: Element[];
            try {
              noteheads = (graphicalNote.getNoteheadSVGs?.() ?? []).filter(Boolean);
            } catch {
              continue;
            }
            if (noteheads.length === 0) continue;

            identities.push({
              measureIndex,
              pitch,
              voice,
              staff,
              isGrace: note.IsGraceNote === true || sourceVoiceEntry?.IsGrace === true,
              relativeOnset,
              noteheads,
            });
          }
        }
      }
    }
  }
  return identities;
}

function sameRationalPosition(
  rendered: Rational,
  relOnsetDiv: number,
  totalMeasureDivs: number,
): boolean {
  if (
    !Number.isSafeInteger(relOnsetDiv)
    || !Number.isSafeInteger(totalMeasureDivs)
    || totalMeasureDivs <= 0
  ) {
    return false;
  }
  return BigInt(rendered.numerator) * BigInt(totalMeasureDivs)
    === BigInt(relOnsetDiv) * BigInt(rendered.denominator);
}

/**
 * Bridge one rendered OSMD note to exactly one Partitura score event.
 * Zero or multiple matches are unsupported; there is deliberately no nearest fallback.
 */
export function matchRenderedScoreNoteEvent(
  rendered: RenderedScoreNoteIdentity,
  candidates: readonly AlignmentScoreEventIdentity[],
): AlignmentScoreEventIdentity | null {
  const matches = candidates.filter((candidate) =>
    candidate.measure_index === rendered.measureIndex
    && candidate.pitch === rendered.pitch
    && candidate.voice === rendered.voice
    && candidate.staff === rendered.staff
    && candidate.is_grace === rendered.isGrace
    && candidate.rel_onset_div != null
    && candidate.total_measure_divs != null
    && sameRationalPosition(
      rendered.relativeOnset,
      candidate.rel_onset_div,
      candidate.total_measure_divs,
    ),
  );
  return matches.length === 1 ? matches[0] : null;
}
