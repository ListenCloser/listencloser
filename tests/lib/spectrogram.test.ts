import { describe, expect, it } from "vitest";
import {
  computeSpectrogram,
  frequencyToY,
  logarithmicBinMap,
  timeToX,
  xToTime,
} from "@/lib/spectrogram";

describe("spectrogram coordinate mapping", () => {
  it("maps time to x and back within the performance timeline", () => {
    expect(timeToX(15, 60, 800)).toBe(200);
    expect(xToTime(200, 800, 60)).toBe(15);
    expect(xToTime(-10, 800, 60)).toBe(0);
    expect(xToTime(900, 800, 60)).toBe(60);
  });

  it("uses a logarithmic frequency axis", () => {
    expect(frequencyToY(40, 40, 20_000, 400)).toBe(400);
    expect(frequencyToY(20_000, 40, 20_000, 400)).toBe(0);
    expect(frequencyToY(400, 40, 20_000, 400)).toBeCloseTo(252, 0);
  });

  it("generates monotonic logarithmic FFT bin rows", () => {
    expect([...logarithmicBinMap(6, 44_100, 2048, 40)]).toEqual(
      expect.arrayContaining([expect.any(Number)]),
    );
    const map = logarithmicBinMap(6, 44_100, 2048, 40);
    expect([...map].every((value, index) => index === 0 || value >= map[index - 1])).toBe(true);
  });
});

describe("spectrogram computation", () => {
  it("is deterministic and finds energy in a sine-wave fixture", async () => {
    const sampleRate = 8_000;
    const samples = Float32Array.from(
      { length: 1024 },
      (_, index) => Math.sin((2 * Math.PI * 440 * index) / sampleRate),
    );
    const options = {
      fftSize: 256,
      bins: 24,
      maxColumns: 8,
      minFrequency: 40,
      yieldToBrowser: async () => undefined,
    };
    const first = await computeSpectrogram(samples, sampleRate, options);
    const second = await computeSpectrogram(samples, sampleRate, options);
    expect(first).toEqual(second);
    expect(first.columns).toBeGreaterThan(0);
    expect(first.values.some((value) => value > 0)).toBe(true);
  });
});
