import type { TranscribeResult } from "./music";

export type NoteStats = {
  pitchRange: { low: number; high: number; span: number };
  density: number;
};

export function computeNoteStats(notes: TranscribeResult["notes"]): NoteStats {
  if (!notes.length) {
    return {
      pitchRange: { low: 0, high: 0, span: 0 },
      density: 0,
    };
  }

  let minPitch = Infinity;
  let maxPitch = -Infinity;
  let minStart = Infinity;
  let maxEnd = -Infinity;

  for (const n of notes) {
    if (n.pitch < minPitch) minPitch = n.pitch;
    if (n.pitch > maxPitch) maxPitch = n.pitch;
    if (n.start < minStart) minStart = n.start;
    if (n.end > maxEnd) maxEnd = n.end;
  }

  const duration = maxEnd - minStart || 1;

  return {
    pitchRange: { low: minPitch, high: maxPitch, span: maxPitch - minPitch },
    density: Math.round((notes.length / duration) * 100) / 100,
  };
}
