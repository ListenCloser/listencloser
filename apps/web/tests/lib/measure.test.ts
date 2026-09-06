import { describe, expect, it } from "vitest";
import { measureIndexAt } from "@/lib/measure";

const starts = [0, 2, 4, 6, 8, 10];

describe("measureIndexAt", () => {
  it("returns -1 for empty starts", () => {
    expect(measureIndexAt([], 0)).toBe(-1);
    expect(measureIndexAt([], 5)).toBe(-1);
  });

  it("returns -1 when time is before the first measure", () => {
    expect(measureIndexAt(starts, -1)).toBe(-1);
    expect(measureIndexAt(starts, -0.01)).toBe(-1);
  });

  it("returns 0 at the exact first measure boundary", () => {
    expect(measureIndexAt(starts, 0)).toBe(0);
  });

  it("returns the correct measure for time inside a measure", () => {
    expect(measureIndexAt(starts, 1)).toBe(0);
    expect(measureIndexAt(starts, 1.99)).toBe(0);
    expect(measureIndexAt(starts, 3)).toBe(1);
    expect(measureIndexAt(starts, 5.5)).toBe(2);
  });

  it("returns the correct measure at exact boundaries", () => {
    expect(measureIndexAt(starts, 2)).toBe(1);
    expect(measureIndexAt(starts, 4)).toBe(2);
    expect(measureIndexAt(starts, 6)).toBe(3);
    expect(measureIndexAt(starts, 8)).toBe(4);
    expect(measureIndexAt(starts, 10)).toBe(5);
  });

  it("returns the last measure when time is past all boundaries", () => {
    expect(measureIndexAt(starts, 100)).toBe(5);
    expect(measureIndexAt(starts, 10.01)).toBe(5);
  });

  it("returns the last measure when time equals the last boundary", () => {
    expect(measureIndexAt(starts, 10)).toBe(5);
  });

  it("handles a single-element starts array", () => {
    expect(measureIndexAt([5], 0)).toBe(-1);
    expect(measureIndexAt([5], 4.99)).toBe(-1);
    expect(measureIndexAt([5], 5)).toBe(0);
    expect(measureIndexAt([5], 100)).toBe(0);
  });

  it("handles forward measure transition", () => {
    expect(measureIndexAt(starts, 1.5)).toBe(0);
    expect(measureIndexAt(starts, 2)).toBe(1);
    expect(measureIndexAt(starts, 3.5)).toBe(1);
  });

  it("handles reverse seek", () => {
    expect(measureIndexAt(starts, 9)).toBe(4);
    expect(measureIndexAt(starts, 3)).toBe(1);
    expect(measureIndexAt(starts, 1)).toBe(0);
  });

  it("handles jump of several measures", () => {
    expect(measureIndexAt(starts, 0)).toBe(0);
    expect(measureIndexAt(starts, 10)).toBe(5);
  });

  it("cursor position transitions: forward playback", () => {
    // Simulates playback advancing through measures
    const positions = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 7, 8, 9, 10];
    const expected = [0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 3, 3, 4, 4, 5];
    const actual = positions.map((t) => measureIndexAt(starts, t));
    expect(actual).toEqual(expected);
  });

  it("cursor position transitions: reverse seek", () => {
    // Simulates seeking backward
    expect(measureIndexAt(starts, 9)).toBe(4);
    expect(measureIndexAt(starts, 5)).toBe(2);
    expect(measureIndexAt(starts, 1)).toBe(0);
  });

  it("cursor position transitions: pause preserves position", () => {
    // When paused at 3.5s, cursor stays at measure 1
    const paused = measureIndexAt(starts, 3.5);
    expect(paused).toBe(1);
    // Still at same position after "time passes" (no change)
    expect(measureIndexAt(starts, 3.5)).toBe(1);
  });

  it("cursor position transitions: seek forward then backward", () => {
    // Seek forward to measure 4
    expect(measureIndexAt(starts, 8.5)).toBe(4);
    // Seek backward to measure 1
    expect(measureIndexAt(starts, 2.5)).toBe(1);
    // Seek forward again to measure 3
    expect(measureIndexAt(starts, 6.5)).toBe(3);
  });
});
