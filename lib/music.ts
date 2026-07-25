/**
 * Music API client and library management.
 *
 * This module is the primary interface for:
 * 1. Backend API calls (transcribe, enhance, analyze, synth, convert)
 * 2. Supabase library CRUD (upload, list, save, delete)
 * 3. Shared types used across the frontend
 *
 * MIDI encoding lives in lib/midi.ts.
 * Format utilities live in lib/format.ts.
 */

import { supabase } from "./supabase";
import { apiFetch } from "./api";

// ── Re-exports ──────────────────────────────────────────────────────────────
// Centralize imports so consumers only need to import from "lib/music".

export { notesToMidiBase64, type NoteInput } from "./midi";
export { blobToBase64, formatTime, audioFmtFromBlob, audioFmtFromName } from "./format";

// ── Types ───────────────────────────────────────────────────────────────────

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

// ── Internal helpers ────────────────────────────────────────────────────────

const LIBRARY_BUCKET = "library";
const TRANSCRIPTIONS_BUCKET = "transcriptions";

async function userId(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.user?.id ?? null;
}

async function userPrefix(): Promise<string> {
  const uid = await userId();
  return `library/${uid ?? "dev"}`;
}

// ── Library CRUD ────────────────────────────────────────────────────────────

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
  const { uploadFile, getPublicUrl } = await import("./storage");
  await uploadFile(LIBRARY_BUCKET, path, blob, contentType, true);
  return { url: getPublicUrl(LIBRARY_BUCKET, path), id: path };
}

export async function listLibrary(): Promise<LibFile[]> {
  const uid = await userId();
  if (!uid) return [];
  const { listFiles, getPublicUrl, downloadText } = await import("./storage");
  const prefix = await userPrefix();
  const files = await listFiles(LIBRARY_BUCKET, prefix);

  // Batch-check which transcriptions exist to avoid N+1 downloads
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

// ── Backend API calls ───────────────────────────────────────────────────────

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
