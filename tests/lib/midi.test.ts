import { describe, it, expect } from 'vitest';
import { notesToMidiBase64 } from '@/lib/midi';

describe('notesToMidiBase64', () => {
  it('returns valid base64', () => {
    const result = notesToMidiBase64([
      { pitch: 60, start: 0, end: 0.5, velocity: 100 },
    ]);
    expect(typeof result).toBe('string');
    expect(() => atob(result)).not.toThrow();
  });

  it('produces MIDI with correct header', () => {
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

  it('handles empty notes', () => {
    const result = notesToMidiBase64([]);
    expect(typeof result).toBe('string');
    expect(() => atob(result)).not.toThrow();
  });

  it('clamps out-of-range pitches', () => {
    const result = notesToMidiBase64([
      { pitch: 200, start: 0, end: 0.5, velocity: 100 },
      { pitch: -5, start: 0.5, end: 1.0, velocity: 100 },
    ]);
    expect(typeof result).toBe('string');
  });

  it('sorts notes by start time', () => {
    const result = notesToMidiBase64([
      { pitch: 60, start: 1.0, end: 1.5, velocity: 100 },
      { pitch: 64, start: 0.0, end: 0.5, velocity: 80 },
      { pitch: 67, start: 0.5, end: 1.0, velocity: 90 },
    ]);
    expect(typeof result).toBe('string');
  });
});
