/**
 * Supabase library CRUD operations.
 *
 * WHY: Audio files and their transcriptions are stored in Supabase Storage
 * across two buckets: "library" (audio files) and "transcriptions" (JSON
 * metadata). This module handles the bidirectional mapping between
 * Supabase's flat file storage and the app's structured LibFile type.
 *
 * ARCHITECTURE:
 * - Audio files go to: library/<uid>/<timestamp>-<name>.<ext>
 * - Transcriptions go to: transcriptions/<uid>/<name>.json
 * - Each transcription JSON contains notes, midi_base64, analysis, musicxml
 * - listLibrary() joins these two buckets into a single LibFile[] result
 *
 * WHY TWO BUCKETS: Audio files are large binary blobs. Transcriptions are
 * small JSON metadata. Separating them keeps storage costs predictable
 * and allows transcription updates without re-uploading audio.
 */

import { supabase } from "./supabase";
import type { LibFile, Transcription, TranscribeResult } from "./types";

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

  // Batch-check which transcriptions exist to avoid N+1 downloads.
  // We list the transcriptions bucket once and build a set of existing
  // JSON filenames, then only download the ones that match.
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
