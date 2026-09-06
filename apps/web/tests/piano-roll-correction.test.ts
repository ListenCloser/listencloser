import { describe, expect, it } from "vitest";
import {
  addDraftNote,
  buildCorrectionReplacement,
  removeDraftNotes,
  transposeDraftNotes,
  type EditablePianoRollNote,
} from "@/lib/piano-roll-correction";

const source: EditablePianoRollNote[] = [
  { id: "low", pitch: 48, start: 0.0, end: 2.0, velocity: 70 },
  { id: "target", pitch: 60, start: 0.5, end: 1.0, velocity: 90 },
  { id: "neighbor", pitch: 64, start: 0.6, end: 0.9, velocity: 80 },
  { id: "later", pitch: 67, start: 1.4, end: 1.8, velocity: 85 },
];

describe("buildCorrectionReplacement", () => {
  it("preserves every unchanged note fully contained by a pitch-edit span", () => {
    const draft = transposeDraftNotes(source, ["target"], 1);
    const replacement = buildCorrectionReplacement(source, draft);

    expect(replacement).toMatchObject({
      selectionStart: 0.5,
      selectionEnd: 1,
      added: 0,
      removed: 0,
      pitchChanged: 1,
    });
    expect(replacement?.correctedNotes).toEqual([
      { pitch: 61, start: 0.5, end: 1, velocity: 90 },
      { pitch: 64, start: 0.6, end: 0.9, velocity: 80 },
    ]);
  });

  it("omits a removed note while preserving polyphonic neighbors", () => {
    const draft = removeDraftNotes(source, ["target"]);
    const replacement = buildCorrectionReplacement(source, draft);

    expect(replacement).toMatchObject({ removed: 1, pitchChanged: 0, added: 0 });
    expect(replacement?.correctedNotes).toEqual([
      { pitch: 64, start: 0.6, end: 0.9, velocity: 80 },
    ]);
  });

  it("adds a missing note without duplicating a source note crossing the replacement boundary", () => {
    const draft = addDraftNote(source, {
      id: "draft:add-1",
      pitch: 72,
      start: 0.75,
      end: 1.25,
      velocity: 88,
    });
    const replacement = buildCorrectionReplacement(source, draft);

    expect(replacement).toMatchObject({
      selectionStart: 0.75,
      selectionEnd: 1.25,
      added: 1,
      removed: 0,
      pitchChanged: 0,
    });
    // `low` crosses the span and therefore is not removed by the backend. It
    // must not be reinserted here or the persisted MIDI would duplicate it.
    expect(replacement?.correctedNotes).toEqual([
      { pitch: 72, start: 0.75, end: 1.25, velocity: 88 },
    ]);
  });

  it("returns null for cancel/no-save state with no draft change", () => {
    expect(buildCorrectionReplacement(source, source.map((note) => ({ ...note })))).toBeNull();
  });

  it("fails closed for an invalid edit", () => {
    expect(() => transposeDraftNotes(source, ["target"], 80)).toThrow(
      "Pitch correction would leave the MIDI range.",
    );
  });
});
