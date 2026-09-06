/**
 * MIDI file encoding.
 *
 * Converts note events (pitch, start, end, velocity) into a standard
 * MIDI file (base64-encoded). The output is a single-track Type 0 MIDI
 * file with a fixed tempo of 120 BPM (500,000 μs/quarter).
 *
 * MIDI file format reference:
 * - Header: "MThd" + 6 bytes (format=0, 1 track, ticks-per-quarter)
 * - Track: "MTrk" + length + event data
 * - Events: delta-time (variable-length) + status byte + data bytes
 * - Note On: 0x90 + pitch + velocity
 * - Note Off: 0x80 + pitch + 0
 * - End of Track: 0xFF 0x2F 0x00
 */

export type NoteInput = { pitch: number; start: number; end: number; velocity: number };

/** Ticks per quarter note — determines timing resolution. */
const TPQ = 480;

/** Tempo in microseconds per quarter note (500000 = 120 BPM). */
const TEMPO_MICROS = 500000;

/**
 * Convert note events to a base64-encoded MIDI file.
 *
 * Each note produces a Note-On event at `start` and a Note-Off event at `end`.
 * Notes are sorted by time, then by off-before-on within the same tick.
 * Pitch and velocity are clamped to valid MIDI ranges (0-127).
 */
export function notesToMidiBase64(notes: NoteInput[]): string {
  const events: number[] = [];

  // Tempo meta-event: FF 51 03 tt tt tt
  events.push(0, 0xFF, 0x51, 0x03,
    (TEMPO_MICROS >> 16) & 0xFF,
    (TEMPO_MICROS >> 8) & 0xFF,
    TEMPO_MICROS & 0xFF,
  );

  // Build note-on/off events with clamped values
  const sorted = [...notes].sort((a, b) => a.start - b.start || a.end - b.end);
  const pending: { tick: number; pitch: number; velocity: number; off: boolean }[] = [];

  for (const n of sorted) {
    const start = Math.max(0, n.start);
    const end = Math.max(start, n.end);
    const pitch = Math.min(127, Math.max(0, n.pitch));
    const vel = Math.min(127, Math.max(0, n.velocity));
    pending.push({ tick: Math.round(start * TPQ), pitch, velocity: vel, off: false });
    pending.push({ tick: Math.round(end * TPQ), pitch, velocity: 0, off: true });
  }

  // Sort: by tick, then off events before on events at the same tick
  pending.sort((a, b) => a.tick - b.tick || (a.off ? 0 : 1) - (b.off ? 0 : 1));

  // Encode events with variable-length delta times
  let lastTick = 0;
  for (const ev of pending) {
    events.push(...encodeVarLen(ev.tick - lastTick));
    events.push(ev.off ? 0x80 : 0x90, ev.pitch, ev.velocity);
    lastTick = ev.tick;
  }

  // End of track
  events.push(0, 0xFF, 0x2F, 0x00);

  // Build MIDI file: header (14 bytes) + track chunk
  const trackLen = events.length + 8; // "MTrk" + 4-byte length + events
  const buf = new Uint8Array(14 + trackLen);
  let p = 0;

  // Header chunk: "MThd", length=6, format=0, tracks=1, TPQ
  buf[p++] = 0x4D; buf[p++] = 0x54; buf[p++] = 0x68; buf[p++] = 0x64; // "MThd"
  buf[p++] = 0; buf[p++] = 0; buf[p++] = 0; buf[p++] = 6;
  buf[p++] = 0; buf[p++] = 0; // format 0
  buf[p++] = 0; buf[p++] = 1; // 1 track
  buf[p++] = (TPQ >> 8) & 0xFF; buf[p++] = TPQ & 0xFF;

  // Track chunk: "MTrk", length, events
  buf[p++] = 0x4D; buf[p++] = 0x54; buf[p++] = 0x72; buf[p++] = 0x6B; // "MTrk"
  buf[p++] = (events.length >> 24) & 0xFF;
  buf[p++] = (events.length >> 16) & 0xFF;
  buf[p++] = (events.length >> 8) & 0xFF;
  buf[p++] = events.length & 0xFF;
  for (const b of events) buf[p++] = b;

  // Convert to base64
  let binary = "";
  for (let i = 0; i < buf.length; i++) binary += String.fromCharCode(buf[i]);
  return btoa(binary);
}

/** Encode an integer as MIDI variable-length quantity (VLQ). */
function encodeVarLen(val: number): number[] {
  const result: number[] = [];
  result.push(val & 0x7F);
  val >>= 7;
  while (val > 0) {
    result.push((val & 0x7F) | 0x80);
    val >>= 7;
  }
  result.reverse();
  return result;
}
