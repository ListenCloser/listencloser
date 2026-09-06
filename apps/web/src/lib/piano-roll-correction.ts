export type EditablePianoRollNote = {
  id?: string;
  pitch: number;
  start: number;
  end: number;
  velocity: number;
};

export type CorrectionNotePayload = {
  pitch: number;
  start: number;
  end: number;
  velocity: number;
};

export type CorrectionReplacement = {
  correctedNotes: CorrectionNotePayload[];
  selectionStart: number;
  selectionEnd: number;
  added: number;
  removed: number;
  pitchChanged: number;
};

const EPSILON = 1e-6;

function validNote(note: EditablePianoRollNote): boolean {
  return (
    Number.isInteger(note.pitch)
    && note.pitch >= 0
    && note.pitch <= 127
    && Number.isFinite(note.start)
    && note.start >= 0
    && Number.isFinite(note.end)
    && note.end > note.start
    && Number.isInteger(note.velocity)
    && note.velocity >= 0
    && note.velocity <= 127
  );
}

function sameNote(a: EditablePianoRollNote, b: EditablePianoRollNote): boolean {
  return (
    a.pitch === b.pitch
    && Math.abs(a.start - b.start) <= EPSILON
    && Math.abs(a.end - b.end) <= EPSILON
    && a.velocity === b.velocity
  );
}

function assertValidNotes(notes: readonly EditablePianoRollNote[]): void {
  if (notes.some((note) => !validNote(note))) {
    throw new Error("Correction contains an invalid MIDI note.");
  }
}

export function transposeDraftNotes(
  notes: readonly EditablePianoRollNote[],
  noteIds: readonly string[],
  semitones: number,
): EditablePianoRollNote[] {
  const targets = new Set(noteIds);
  if (!targets.size || !Number.isInteger(semitones) || semitones === 0) return [...notes];
  return notes.map((note) => {
    if (!note.id || !targets.has(note.id)) return note;
    const pitch = note.pitch + semitones;
    if (pitch < 0 || pitch > 127) throw new Error("Pitch correction would leave the MIDI range.");
    return { ...note, pitch };
  });
}

export function removeDraftNotes(
  notes: readonly EditablePianoRollNote[],
  noteIds: readonly string[],
): EditablePianoRollNote[] {
  const targets = new Set(noteIds);
  return notes.filter((note) => !note.id || !targets.has(note.id));
}

export function addDraftNote(
  notes: readonly EditablePianoRollNote[],
  note: EditablePianoRollNote,
): EditablePianoRollNote[] {
  assertValidNotes([note]);
  return [...notes, note];
}

/**
 * Build the exact region-replacement payload expected by the existing `correct`
 * capability. The backend removes every source note fully contained in the
 * selected span before inserting `corrected_notes`, so every unchanged draft
 * note fully contained by that span MUST also be included here.
 */
export function buildCorrectionReplacement(
  sourceNotes: readonly EditablePianoRollNote[],
  draftNotes: readonly EditablePianoRollNote[],
): CorrectionReplacement | null {
  assertValidNotes(sourceNotes);
  assertValidNotes(draftNotes);

  const sourceById = new Map(
    sourceNotes.flatMap((note) => note.id ? [[note.id, note] as const] : []),
  );
  const draftById = new Map(
    draftNotes.flatMap((note) => note.id ? [[note.id, note] as const] : []),
  );

  const changedSpans: Array<{ start: number; end: number }> = [];
  let removed = 0;
  let pitchChanged = 0;

  for (const source of sourceNotes) {
    if (!source.id) continue;
    const draft = draftById.get(source.id);
    if (!draft) {
      removed += 1;
      changedSpans.push({ start: source.start, end: source.end });
      continue;
    }
    if (!sameNote(source, draft)) {
      if (source.pitch !== draft.pitch) pitchChanged += 1;
      changedSpans.push({
        start: Math.min(source.start, draft.start),
        end: Math.max(source.end, draft.end),
      });
    }
  }

  const addedNotes = draftNotes.filter((note) => note.id && !sourceById.has(note.id));
  for (const note of addedNotes) changedSpans.push({ start: note.start, end: note.end });

  if (!changedSpans.length) return null;
  const selectionStart = Math.min(...changedSpans.map((span) => span.start));
  const selectionEnd = Math.max(...changedSpans.map((span) => span.end));
  if (!(selectionEnd > selectionStart)) throw new Error("Correction span must have positive duration.");

  const correctedNotes = draftNotes
    .filter((note) => note.start >= selectionStart && note.end <= selectionEnd)
    .map(({ pitch, start, end, velocity }) => ({ pitch, start, end, velocity }))
    .sort((a, b) => a.start - b.start || a.pitch - b.pitch || a.end - b.end);

  return {
    correctedNotes,
    selectionStart,
    selectionEnd,
    added: addedNotes.length,
    removed,
    pitchChanged,
  };
}
