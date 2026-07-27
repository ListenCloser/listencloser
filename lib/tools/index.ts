/**
 * Tool Registry — fully self-contained chat workspace.
 *
 * Each tool maps a user intent to a backend operation. Tools run
 * server-side with access to the user's auth token (via request headers).
 *
 * Available operations:
 * - list_library: Browse user's tracks
 * - upload_audio: Upload audio to library
 * - transcribe_audio: Convert audio to MIDI
 * - analyze_midi: Music theory analysis
 * - enhance_audio: Clean/denoise audio
 * - convert_format: MIDI ↔ MusicXML
 */

import { tool } from "ai";
import { z } from "zod";

function getBackendUrl(): string {
  const url = process.env.MUSIC_BACKEND_URL;
  if (!url) throw new Error("MUSIC_BACKEND_URL not set");
  return url;
}

let requestAuthHeader: string | undefined;
export function setRequestAuthHeader(header: string | undefined) {
  requestAuthHeader = header;
}

async function backendPost(path: string, body: Record<string, unknown>) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (requestAuthHeader) headers["Authorization"] = requestAuthHeader;
  const res = await fetch(`${getBackendUrl()}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? (data as { detail?: unknown }).detail
        : undefined;
    throw new Error(typeof detail === "string" ? detail : `Backend error ${res.status}`);
  }
  return res.json();
}

async function backendGet(path: string) {
  const headers: Record<string, string> = {};
  if (requestAuthHeader) headers["Authorization"] = requestAuthHeader;
  const res = await fetch(`${getBackendUrl()}${path}`, { headers });
  if (!res.ok) throw new Error(`Backend error ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Tool: list_library
// ---------------------------------------------------------------------------
export const listLibraryTool = tool({
  description:
    "List the user's audio library with track names, processing status, and available actions.",
  inputSchema: z.object({}),
  execute: async () => {
    try {
      const tracks = await backendGet("/music/library");
      if (!Array.isArray(tracks) || tracks.length === 0) {
        return { tracks: [], message: "Your library is empty. Upload an audio file to get started!" };
      }
      return {
        tracks: tracks.map((t: Record<string, unknown>) => ({
          name: t.name,
          id: t.id,
          hasNotes: Array.isArray(t.notes) && t.notes.length > 0,
          hasMidi: Boolean(t.midi_base64),
          hasAnalysis: Boolean(t.analysis),
          hasSheetMusic: Boolean(t.musicxml),
        })),
        count: tracks.length,
        message: `Found ${tracks.length} track(s) in your library.`,
      };
    } catch {
      return { tracks: [], message: "Could not access library. Please sign in first." };
    }
  },
});

// ---------------------------------------------------------------------------
// Tool: upload_audio
// ---------------------------------------------------------------------------
export const uploadAudioTool = tool({
  description: "Upload an audio file to the user's library.",
  inputSchema: z.object({
    audio_base64: z.string().describe("Base64-encoded audio data"),
    filename: z.string().describe("Original filename with extension"),
    format: z.enum(["wav", "mp3", "m4a", "ogg", "flac"]).default("wav"),
  }),
  execute: async ({ audio_base64, filename, format }) => {
    const result = await backendPost("/music/library", {
      name: filename,
      data_base64: audio_base64,
      fmt: format,
    });
    return { success: true, path: result.path, url: result.url, message: `Uploaded "${filename}" to your library.` };
  },
});

// ---------------------------------------------------------------------------
// Tool: transcribe_audio
// ---------------------------------------------------------------------------
export const transcribeAudioTool = tool({
  description: "Transcribe an audio file to MIDI notes. Returns notes, MIDI data, and a summary.",
  inputSchema: z.object({
    audio_base64: z.string().describe("Base64-encoded audio data"),
    format: z.enum(["wav", "mp3", "m4a", "ogg", "flac"]).default("wav"),
  }),
  execute: async ({ audio_base64, format }) => {
    const result = await backendPost("/music/transcribe", {
      audio_base64,
      fmt: format,
      upload: false,
    });
    return {
      num_notes: result.num_notes,
      notes: result.notes,
      notes_summary: `Transcribed ${result.num_notes} notes`,
      midi_base64: result.midi_base64,
      wav_url: result.wav_url,
    };
  },
});

// ---------------------------------------------------------------------------
// Tool: analyze_midi
// ---------------------------------------------------------------------------
export const analyzeMidiTool = tool({
  description: "Analyze MIDI for music theory: key, tempo, chords, cadences, modulations, voice leading.",
  inputSchema: z.object({
    midi_base64: z.string().describe("Base64-encoded MIDI file data"),
  }),
  execute: async ({ midi_base64 }) => {
    return backendPost("/music/analyze", { midi_base64 });
  },
});

// ---------------------------------------------------------------------------
// Tool: enhance_audio
// ---------------------------------------------------------------------------
export const enhanceAudioTool = tool({
  description: "Clean and denoise an audio recording.",
  inputSchema: z.object({
    audio_base64: z.string().describe("Base64-encoded audio data"),
    format: z.enum(["wav", "mp3", "m4a", "ogg", "flac"]).default("wav"),
  }),
  execute: async ({ audio_base64, format }) => {
    const result = await backendPost("/music/enhance", {
      audio_base64,
      fmt: format,
      upload: false,
    });
    return { success: true, wav_base64: result.wav_base64, message: "Audio enhanced successfully" };
  },
});

// ---------------------------------------------------------------------------
// Tool: convert_format
// ---------------------------------------------------------------------------
export const convertFormatTool = tool({
  description: "Convert between MIDI and MusicXML formats.",
  inputSchema: z.object({
    data_base64: z.string().describe("Base64-encoded file data"),
    source: z.enum(["midi", "musicxml"]).describe("Source format"),
    target: z.enum(["midi", "musicxml", "auto"]).default("auto"),
  }),
  execute: async ({ data_base64, source, target }) => {
    const result = await backendPost("/music/convert", { source, data_base64, target });
    return { data_base64: result.data_base64, format: result.format, message: `Converted to ${result.format}` };
  },
});

export const musicTools = {
  list_library: listLibraryTool,
  upload_audio: uploadAudioTool,
  transcribe_audio: transcribeAudioTool,
  analyze_midi: analyzeMidiTool,
  enhance_audio: enhanceAudioTool,
  convert_format: convertFormatTool,
};
