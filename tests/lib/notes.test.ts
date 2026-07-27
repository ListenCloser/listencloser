import { describe, it, expect } from 'vitest';
import { pitchToName, pitchClass, computeChroma, SHARP_NOTE_NAMES, FLAT_NOTE_NAMES } from '@/lib/notes';

describe('pitchToName', () => {
  it('returns C4 for MIDI 60', () => {
    expect(pitchToName(60)).toBe('C4');
  });

  it('returns A4 for MIDI 69', () => {
    expect(pitchToName(69)).toBe('A4');
  });

  it('returns C#4 for MIDI 61', () => {
    expect(pitchToName(61)).toBe('C#4');
  });
});

describe('pitchClass', () => {
  it('returns 0 for C (MIDI 60)', () => {
    expect(pitchClass(60)).toBe(0);
  });

  it('returns 9 for A (MIDI 69)', () => {
    expect(pitchClass(69)).toBe(9);
  });

  it('wraps around for high pitches', () => {
    expect(pitchClass(72)).toBe(0); // C5
  });
});

describe('computeChroma', () => {
  it('returns zeros for empty notes', () => {
    const chroma = computeChroma([]);
    expect(chroma).toHaveLength(12);
    expect(chroma.every((v) => v === 0)).toBe(true);
  });

  it('returns non-zero for C note', () => {
    const notes = [{ pitch: 60, start: 0, end: 1, velocity: 100 }];
    const chroma = computeChroma(notes);
    expect(chroma[0]).toBeGreaterThan(0);
  });

  it('normalizes to sum to ~1', () => {
    const notes = [
      { pitch: 60, start: 0, end: 1, velocity: 100 },
      { pitch: 64, start: 0, end: 1, velocity: 100 },
    ];
    const chroma = computeChroma(notes);
    const sum = chroma.reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(1.0, 5);
  });
});

describe('note name constants', () => {
  it('SHARP_NOTE_NAMES has 12 entries', () => {
    expect(SHARP_NOTE_NAMES).toHaveLength(12);
    expect(SHARP_NOTE_NAMES[0]).toBe('C');
  });

  it('FLAT_NOTE_NAMES has 12 entries', () => {
    expect(FLAT_NOTE_NAMES).toHaveLength(12);
  });
});
