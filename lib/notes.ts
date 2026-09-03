export const SHARP_NOTE_NAMES = [
  "C",
  "C#",
  "D",
  "D#",
  "E",
  "F",
  "F#",
  "G",
  "G#",
  "A",
  "A#",
  "B",
] as const;

export const FLAT_NOTE_NAMES = [
  "C",
  "Db",
  "D",
  "Eb",
  "E",
  "F",
  "Gb",
  "G",
  "Ab",
  "A",
  "Bb",
  "B",
] as const;

export function pitchClass(pitch: number): number {
  return ((pitch % 12) + 12) % 12;
}

function pitchOctave(pitch: number): number {
  return Math.floor(pitch / 12) - 1;
}

export function pitchToName(pitch: number): string {
  return `${SHARP_NOTE_NAMES[pitchClass(pitch)]}${pitchOctave(pitch)}`;
}

export type NoteInput = { pitch: number; start: number; end: number };

export function computeChroma(notes: NoteInput[]): number[] {
  const bins = new Array(12).fill(0);
  for (const n of notes) {
    const dur = Math.max(n.end - n.start, 0);
    bins[pitchClass(n.pitch)] += dur;
  }
  const total = bins.reduce((a, b) => a + b, 0) || 1;
  return bins.map((v) => v / total);
}
