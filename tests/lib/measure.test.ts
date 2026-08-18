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
});
