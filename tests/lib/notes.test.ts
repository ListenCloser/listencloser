import { describe, it, expect } from "vitest";
import { pitchToName, pitchClass, computeChroma, SHARP_NOTE_NAMES, FLAT_NOTE_NAMES } from "@/lib/notes";

describe("pitchToName", () => {
  it("returns C4 for MIDI 60", () => {
    expect(pitchToName(60)).toBe("C4");
  });

  it("returns A4 for MIDI 69", () => {
    expect(pitchToName(69)).toBe("A4");
  });

  it("returns C5 for MIDI 72", () => {
    expect(pitchToName(72)).toBe("C5");
  });

  it("returns C#4 for MIDI 61", () => {
    expect(pitchToName(61)).toBe("C#4");
  });
});

describe("pitchClass", () => {
  it("returns 0 for C (MIDI 60)", () => {
    expect(pitchClass(60)).toBe(0);
  });

  it("returns 9 for A (MIDI 69)", () => {
    expect(pitchClass(69)).toBe(9);
  });

  it("wraps around for high pitches", () => {
    expect(pitchClass(72)).toBe(0); // C5
  });
});

describe("computeChroma", () => {
  it("computes chroma distribution for a single note", () => {
    const notes = [{ pitch: 60, start: 0, end: 1, velocity: 100 }];
    const chroma = computeChroma(notes);
    expect(chroma).toHaveLength(12);
    expect(chroma[0]).toBeGreaterThan(0); // C
    expect(chroma.slice(1).every((v) => v === 0)).toBe(true);
  });

  it("normalizes by total duration", () => {
    const notes = [
      { pitch: 60, start: 0, end: 1, velocity: 100 },
      { pitch: 64, start: 0, end: 1, velocity: 100 },
    ];
    const chroma = computeChroma(notes);
    const total = chroma.reduce((a, b) => a + b, 0);
    expect(total).toBeCloseTo(1.0, 5);
  });

  it("returns zeros for empty notes", () => {
    const chroma = computeChroma([]);
    expect(chroma).toHaveLength(12);
    expect(chroma.every((v) => v === 0)).toBe(true);
  });
});

describe("note name constants", () => {
  it("SHARP_NOTE_NAMES has 12 entries", () => {
    expect(SHARP_NOTE_NAMES).toHaveLength(12);
    expect(SHARP_NOTE_NAMES[0]).toBe("C");
    expect(SHARP_NOTE_NAMES[9]).toBe("A");
  });

  it("FLAT_NOTE_NAMES has 12 entries", () => {
    expect(FLAT_NOTE_NAMES).toHaveLength(12);
    expect(FLAT_NOTE_NAMES[0]).toBe("C");
  });
});
