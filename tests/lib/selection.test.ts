import { describe, expect, it } from "vitest";
import {
  composeMeasureSelection,
  composeNoteSelection,
  composeTimeSelection,
  measureRangeFromTime,
  noteIdsInRange,
  timeRangeFromMeasures,
  timeRangeFromNotes,
} from "@/lib/selection";

const measureStarts = [0, 2, 4, 6, 8, 10];
const notes = [
  { id: "n1", start: 0.5, end: 1.5 },
  { id: "n2", start: 1.2, end: 2.4 },
  { id: "n3", start: 5.0, end: 6.0 },
];

describe("selection mapping helpers", () => {
  it("maps a single measure to its exact boundary interval on the score timeline", () => {
    const range = timeRangeFromMeasures(2, 2, measureStarts);
    expect(range).toEqual({ start: 4, end: 6, domain: "notation" });
  });

  it("maps a measure range end to the next measure boundary", () => {
    const range = timeRangeFromMeasures(0, 2, measureStarts);
    expect(range).toEqual({ start: 0, end: 6, domain: "notation" });
  });

  it("returns null for the final measure when no scoreDuration is provided", () => {
    const range = timeRangeFromMeasures(5, 5, measureStarts);
    expect(range).toBeNull();
  });

  it("derives timeRange for final measure when scoreDuration is provided", () => {
    const range = timeRangeFromMeasures(5, 5, measureStarts, 12);
    expect(range).toEqual({ start: 10, end: 12, domain: "notation" });
  });

  it("derives a coarse approximate measure range from a time range", () => {
    const measures = measureRangeFromTime(2, 5, measureStarts);
    expect(measures).toEqual({ start: 1, end: 2 });
  });

  it("returns the containing measure for a short selection inside one measure", () => {
    const measures = measureRangeFromTime(1.5, 1.6, measureStarts);
    expect(measures).toEqual({ start: 0, end: 0 });
  });

  it("maps to the last measure when time is past all boundaries", () => {
    const measures = measureRangeFromTime(20, 21, measureStarts);
    expect(measures).toEqual({ start: 5, end: 5 });
  });

  it("returns null for empty measureStarts", () => {
    expect(measureRangeFromTime(1, 2, [])).toBeNull();
  });

  it("collects note ids overlapping a time range", () => {
    expect(noteIdsInRange(notes, 1.0, 2.0)).toEqual(["n1", "n2"]);
    expect(noteIdsInRange(notes, 0.4, 5.5)).toEqual(["n1", "n2", "n3"]);
  });

  it("computes the exact time extent of selected notes", () => {
    expect(timeRangeFromNotes(notes, ["n1", "n2"])).toEqual({ start: 0.5, end: 2.4 });
    expect(timeRangeFromNotes(notes, [])).toBeNull();
  });

  it("composes a time selection with exact provenance and derived note ids", () => {
    const selection = composeTimeSelection(1.0, 2.0, notes, "waveform");
    expect(selection.timeRange).toEqual({ start: 1, end: 2, domain: "performance" });
    expect(selection.noteIds).toEqual(["n1", "n2"]);
    expect(selection.provenance).toEqual({
      origin: "waveform",
      timeExact: true,
      measureApproximate: false,
    });
  });

  it("composes a measure selection with exact measure provenance and score-timeline time", () => {
    const selection = composeMeasureSelection(1, 3, measureStarts);
    expect(selection.measureRange).toEqual({ start: 1, end: 3 });
    expect(selection.timeRange).toEqual({ start: 2, end: 8, domain: "notation" });
    expect(selection.provenance).toEqual({
      origin: "score",
      timeExact: false,
      measureApproximate: false,
    });
  });

  it("composes a note selection with exact provenance and a derived time range", () => {
    const selection = composeNoteSelection(notes, ["n1", "n2"]);
    expect(selection?.noteIds).toEqual(["n1", "n2"]);
    expect(selection?.timeRange).toEqual({ start: 0.5, end: 2.4, domain: "performance" });
    expect(selection?.provenance.timeExact).toBe(true);
    expect(composeNoteSelection(notes, [])).toBeNull();
  });
});