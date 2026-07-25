import { supabase } from "./supabase";
import { apiFetch } from "./api";

async function userId(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.user?.id ?? null;
}

export async function blobToBase64(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunkSize = 8192;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

export type TranscribeResult = {
  notes: { pitch: number; start: number; end: number; velocity: number }[];
  num_notes: number;
  midi_base64?: string;
  wav_base64?: string;
  midi_url?: string;
  wav_url?: string;
  analysis?: {
    key: { tonic: string; mode: string; confidence: number };
    tempo?: { bpm: number; confidence: number };
    time_signature?: { numerator: number; denominator: number; confidence: number };
    chords?: { root: string; quality: string; start: number; end: number }[];
    roman_numerals?: { figure: string; root: string; quality: string; start: number; end: number }[];
    cadences?: { type: string; chords: string[]; position: number }[];
    modulations?: { from_key: string; to_key: string; position: number }[];
    voice_leading?: {
      parallel: number;
      contrary: number;
      oblique: number;
      similar: number;
      motion_summary: string;
    };
  };
};

export type LibFile = {
  name: string;
  url: string;
  id: string;
  size?: number;
  created_at?: string;
  notes?: { pitch: number; start: number; end: number; velocity: number }[];
  midi_base64?: string;
  musicxml?: string;
  analysis?: TranscribeResult["analysis"];
};

export type Transcription = {
  id: string;
  title: string;
  notes: { pitch: number; start: number; end: number; velocity: number }[];
  wav_url?: string;
  created_at?: string;
};

const LIBRARY_BUCKET = "library";
const TRANSCRIPTIONS_BUCKET = "transcriptions";

async function userPrefix(): Promise<string> {
  const uid = await userId();
  return `library/${uid ?? "dev"}`;
}

export async function uploadToLibrary(name: string, blob: Blob): Promise<{ url: string; id: string }> {
  if (!supabase) throw new Error("Supabase not configured");
  const uid = await userId();
  if (!uid) throw new Error("Sign in to save to library");
  const ext = (name.split(".").pop() || "wav").toLowerCase();
  const safeName = name.replace(/[^a-z0-9.\-_\u00C0-\u024F ]/gi, "_");
  const prefix = await userPrefix();
  const path = `${prefix}/${Date.now()}-${safeName}`;
  const contentType = ext === "musicxml" || ext === "xml"
    ? "application/xml"
    : ext === "mid" || ext === "midi"
      ? "audio/midi"
      : `audio/${ext}`;
  await apiFetch("/api/music/library", {
    method: "POST",
    body: JSON.stringify({ name: path, data_base64: await blobToBase64(blob), fmt: ext }),
  });
  const { getPublicUrl } = await import("./storage");
  return { url: getPublicUrl(LIBRARY_BUCKET, path), id: path };
}

export async function listLibrary(): Promise<LibFile[]> {
  const uid = await userId();
  if (!uid) return [];
  const { listFiles, getPublicUrl, downloadText } = await import("./storage");
  const prefix = await userPrefix();
  const files = await listFiles(LIBRARY_BUCKET, prefix);

  let notesNames = new Set<string>();
  try {
    const noteFiles = await listFiles(TRANSCRIPTIONS_BUCKET, uid);
    notesNames = new Set(noteFiles.filter((f) => !f.name.endsWith("/")).map((f) => f.name));
  } catch {
    notesNames = new Set();
  }

  const items = await Promise.all(
    files
      .filter((f) => !f.name.endsWith("/"))
      .map(async (f) => {
        const path = `${prefix}/${f.name}`;
        const displayName = f.name.replace(/^\d+-/, "").replace(/_/g, " ");
        const baseName = f.name.replace(/\.[^.]+$/, "");
        let notes;
        let midi_base64;
        let analysis;
        let musicxml;
        if (notesNames.has(`${baseName}.json`)) {
          try {
            const raw = await downloadText(TRANSCRIPTIONS_BUCKET, `${uid}/${baseName}.json`);
            if (raw) {
              const parsed = JSON.parse(raw);
              if (Array.isArray(parsed)) {
                notes = parsed;
              } else {
                notes = parsed.notes;
                midi_base64 = parsed.midi_base64;
                analysis = parsed.analysis;
                musicxml = parsed.musicxml;
              }
            }
          } catch {
            notes = undefined;
          }
        }
        return {
          name: displayName,
          url: getPublicUrl(LIBRARY_BUCKET, path),
          id: `${prefix}/${f.name}`,
          size: f.metadata?.size,
          created_at: f.created_at,
          notes,
          midi_base64,
          musicxml,
          analysis,
        };
      }),
  );
  return items;
}

export async function saveTranscription(
  id: string,
  notes: { pitch: number; start: number; end: number; velocity: number }[],
  midi_base64?: string,
  analysis?: TranscribeResult["analysis"],
  musicxml?: string,
): Promise<void> {
  if (!supabase) return;
  const uid = await userId();
  if (!uid) return;
  const { uploadFile } = await import("./storage");
  const baseName = (id.split("/").pop() ?? id).replace(/\.[^.]+$/, "");
  const path = `${uid}/${baseName}.json`;
  const payload: Record<string, unknown> = { notes };
  if (midi_base64) payload.midi_base64 = midi_base64;
  if (analysis) payload.analysis = analysis;
  if (musicxml) payload.musicxml = musicxml;
  await uploadFile(TRANSCRIPTIONS_BUCKET, path, JSON.stringify(payload), "application/json", true);
}

export async function deleteFromLibrary(id: string): Promise<void> {
  if (!supabase) throw new Error("Supabase not configured");
  const { deleteFile } = await import("./storage");
  await deleteFile(LIBRARY_BUCKET, id);
  const uid = await userId();
  if (uid) {
    const baseName = (id.split("/").pop() ?? id).replace(/\.[^.]+$/, "");
    try {
      await deleteFile(TRANSCRIPTIONS_BUCKET, `${uid}/${baseName}.json`);
    } catch {}
  }
}

export async function listTranscriptions(): Promise<Transcription[]> {
  const uid = await userId();
  if (!uid) return [];
  const { listFiles, getPublicUrl } = await import("./storage");
  const prefix = uid;
  const files = await listFiles(TRANSCRIPTIONS_BUCKET, prefix);
  return files
    .filter((f) => !f.name.endsWith("/"))
    .map((f) => {
      const path = `${prefix}/${f.name}`;
      return {
        id: path,
        title: f.name.replace(/^\d+-/, "").replace(/_/g, " ").replace(/\.json$/i, ""),
        notes: [],
        wav_url: getPublicUrl(TRANSCRIPTIONS_BUCKET, path),
        created_at: f.created_at,
      } satisfies Transcription;
    });
}

export async function transcribeAudio(
  dataBase64?: string,
  fmt = "wav",
  libraryPath?: string,
): Promise<TranscribeResult> {
  const body: Record<string, unknown> = { fmt, upload: true };
  if (libraryPath) body.library_path = libraryPath;
  else body.audio_base64 = dataBase64;
  return apiFetch("/api/music/transcribe", {
    method: "POST",
    body: JSON.stringify(body),
  }) as Promise<TranscribeResult>;
}

export async function enhanceAudio(
  dataBase64: string,
  fmt = "wav",
): Promise<{ wav_base64: string; url?: string }> {
  return apiFetch("/api/music/enhance", {
    method: "POST",
    body: JSON.stringify({ audio_base64: dataBase64, fmt, upload: false }),
  }) as Promise<{ wav_base64: string; url?: string }>;
}

export async function analyzeAudio(
  midiBase64?: string,
): Promise<TranscribeResult["analysis"]> {
  return apiFetch("/api/music/analyze", {
    method: "POST",
    body: JSON.stringify({ midi_base64: midiBase64 }),
  }) as Promise<TranscribeResult["analysis"]>;
}

type NoteInput = { pitch: number; start: number; end: number; velocity: number };

export function notesToMidiBase64(notes: NoteInput[]): string {
  const TPQ = 480;
  const tempoMicros = 500000;
  const events: number[] = [];

  events.push(0, 0xFF, 0x51, 0x03, (tempoMicros >> 16) & 0xFF, (tempoMicros >> 8) & 0xFF, tempoMicros & 0xFF);

  const sorted = [...notes].sort((a, b) => a.start - b.start || a.end - b.end);
  let lastTick = 0;
  const pending: { tick: number; pitch: number; velocity: number; off: boolean }[] = [];

  for (const n of sorted) {
    const clampedStart = Math.max(0, n.start);
    const clampedEnd = Math.max(clampedStart, n.end);
    const clampedPitch = Math.min(127, Math.max(0, n.pitch));
    const clampedVel = Math.min(127, Math.max(0, n.velocity));
    const onTick = Math.round(clampedStart * TPQ);
    const offTick = Math.round(clampedEnd * TPQ);
    pending.push({ tick: onTick, pitch: clampedPitch, velocity: clampedVel, off: false });
    pending.push({ tick: offTick, pitch: clampedPitch, velocity: 0, off: true });
  }

  pending.sort((a, b) => a.tick - b.tick || (a.off ? 0 : 1) - (b.off ? 0 : 1));

  for (const ev of pending) {
    const delta = ev.tick - lastTick;
    lastTick = ev.tick;
    events.push(...encodeVarLen(delta));
    events.push(ev.off ? 0x80 : 0x90, ev.pitch, ev.velocity);
  }

  events.push(0, 0xFF, 0x2F, 0x00);

  const trackChunk = events.length + 8;
  const totalLen = 14 + trackChunk;
  const buf = new Uint8Array(totalLen);
  let p = 0;

  buf[p++] = 0x4D; buf[p++] = 0x54; buf[p++] = 0x68; buf[p++] = 0x64;
  buf[p++] = 0; buf[p++] = 0; buf[p++] = 0; buf[p++] = 6;
  buf[p++] = 0; buf[p++] = 0;
  buf[p++] = 0; buf[p++] = 1;
  buf[p++] = (TPQ >> 8) & 0xFF; buf[p++] = TPQ & 0xFF;

  buf[p++] = 0x4D; buf[p++] = 0x54; buf[p++] = 0x72; buf[p++] = 0x6B;
  buf[p++] = (events.length >> 24) & 0xFF;
  buf[p++] = (events.length >> 16) & 0xFF;
  buf[p++] = (events.length >> 8) & 0xFF;
  buf[p++] = events.length & 0xFF;
  for (const b of events) buf[p++] = b;

  let binary = "";
  for (let i = 0; i < buf.length; i++) binary += String.fromCharCode(buf[i]);
  return btoa(binary);
}

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

export async function synthAudio(
  midiBase64: string,
): Promise<{ wav_base64: string }> {
  return apiFetch("/api/music/synth", {
    method: "POST",
    body: JSON.stringify({ midi_base64: midiBase64 }),
  }) as Promise<{ wav_base64: string }>;
}

export async function synthMusicXml(
  musicXmlBase64: string,
): Promise<{ wav_base64: string }> {
  const converted = await convertMusicFormat(musicXmlBase64, "musicxml", "midi");
  return synthAudio(converted.data_base64);
}

export async function convertMusicFormat(
  dataBase64: string,
  source: "midi" | "musicxml",
  target: "midi" | "musicxml" | "auto" = "auto",
): Promise<{ data_base64: string; format: string }> {
  return apiFetch("/api/music/convert", {
    method: "POST",
    body: JSON.stringify({ source, data_base64: dataBase64, target }),
  }) as Promise<{ data_base64: string; format: string }>;
}

export function formatTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function audioFmtFromBlob(blob: Blob): string {
  const type = blob.type.toLowerCase();
  if (type.includes("ogg")) return "ogg";
  if (type.includes("mp4") || type.includes("m4a")) return "mp4";
  if (type.includes("flac")) return "flac";
  if (type.includes("mp3") || type.includes("mpeg")) return "mp3";
  return "wav";
}

export function audioFmtFromName(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (["ogg", "mp4", "m4a", "flac", "mp3", "wav", "webm"].includes(ext)) return ext === "m4a" ? "mp4" : ext;
  return "wav";
}
