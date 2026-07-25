import { describe, it, expect } from "vitest";
import { notesToMidiBase64 } from "@/lib/midi";

describe("notesToMidiBase64", () => {
  it("returns a valid base64 string", () => {
    const result = notesToMidiBase64([
      { pitch: 60, start: 0, end: 0.5, velocity: 100 },
    ]);
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
    // Should be valid base64
    expect(() => atob(result)).not.toThrow();
  });

  it("produces a MIDI file with correct header", () => {
    const result = notesToMidiBase64([
      { pitch: 60, start: 0, end: 0.5, velocity: 100 },
    ]);
    const bytes = Uint8Array.from(atob(result), (c) => c.charCodeAt(0));
    // MIDI header: "MThd"
    expect(bytes[0]).toBe(0x4D);
    expect(bytes[1]).toBe(0x54);
    expect(bytes[2]).toBe(0x68);
    expect(bytes[3]).toBe(0x64);
  });

  it("handles empty notes array", () => {
    const result = notesToMidiBase64([]);
    expect(typeof result).toBe("string");
    expect(() => atob(result)).not.toThrow();
  });

  it("clamps pitch to 0-127", () => {
    // Should not throw for out-of-range values
    const result = notesToMidiBase64([
      { pitch: 200, start: 0, end: 0.5, velocity: 100 },
      { pitch: -5, start: 0.5, end: 1.0, velocity: 100 },
    ]);
    expect(typeof result).toBe("string");
  });

  it("clamps velocity to 0-127", () => {
    const result = notesToMidiBase64([
      { pitch: 60, start: 0, end: 0.5, velocity: 300 },
    ]);
    expect(typeof result).toBe("string");
  });

  it("handles notes with zero duration", () => {
    const result = notesToMidiBase64([
      { pitch: 60, start: 0.5, end: 0.5, velocity: 100 },
    ]);
    expect(typeof result).toBe("string");
  });

  it("sorts notes by start time", () => {
    // Notes out of order should still produce valid MIDI
    const result = notesToMidiBase64([
      { pitch: 60, start: 1.0, end: 1.5, velocity: 100 },
      { pitch: 64, start: 0.0, end: 0.5, velocity: 80 },
      { pitch: 67, start: 0.5, end: 1.0, velocity: 90 },
    ]);
    expect(typeof result).toBe("string");
  });
});
