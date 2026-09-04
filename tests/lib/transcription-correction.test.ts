import { describe, expect, it } from "vitest";

import { buildCorrectionPayload, type CorrectionNote } from "@/lib/transcription-correction";

const notes: CorrectionNote[] = [
  { id: "left", pitch: 60, start: 1, end: 1.5, velocity: 70 },
  { id: "target", pitch: 64, start: 2, end: 2.5, velocity: 80 },
  { id: "chord", pitch: 67, start: 2, end: 2.5, velocity: 75 },
  { id: "right", pitch: 72, start: 3, end: 3.5, velocity: 90 },
];

describe("buildCorrectionPayload", () => {
  it("removes only the selected note and re-emits unchanged chord neighbors", () => {
    const payload = buildCorrectionPayload(notes, { start: 2, end: 2.5 }, {
      kind: "remove",
      noteIds: ["target"],
    });

    expect(payload).toEqual({
      selectionStart: 2,
      selectionEnd: 2.5,
      correctedNotes: [{ pitch: 67, start: 2, end: 2.5, velocity: 75 }],
    });
  });

  it("changes pitch without changing note timing or neighboring notes", () => {
    const payload = buildCorrectionPayload(notes, { start: 2, end: 2.5 }, {
      kind: "pitch",
      noteId: "target",
      pitch: 65,
    });

    expect(payload.correctedNotes).toEqual([
      { pitch: 65, start: 2, end: 2.5, velocity: 80 },
      { pitch: 67, start: 2, end: 2.5, velocity: 75 },
    ]);
  });

  it("adds a missing note while preserving the passage note world", () => {
    const payload = buildCorrectionPayload(notes, { start: 1.8, end: 2.8 }, {
      kind: "add",
      pitch: 55,
      start: 2.1,
      end: 2.4,
      velocity: 88,
    });

    expect(payload.correctedNotes).toEqual([
      { pitch: 64, start: 2, end: 2.5, velocity: 80 },
      { pitch: 67, start: 2, end: 2.5, velocity: 75 },
      { pitch: 55, start: 2.1, end: 2.4, velocity: 88 },
    ]);
  });

  it("rejects invalid pitch and edits outside the selected passage", () => {
    expect(() => buildCorrectionPayload(notes, { start: 2, end: 2.5 }, {
      kind: "pitch",
      noteId: "target",
      pitch: 128,
    })).toThrow("Pitch must be a MIDI note from 0 to 127.");

    expect(() => buildCorrectionPayload(notes, { start: 2, end: 2.5 }, {
      kind: "add",
      pitch: 60,
      start: 1.9,
      end: 2.2,
    })).toThrow("The added note must stay inside the selected passage.");
  });
});
