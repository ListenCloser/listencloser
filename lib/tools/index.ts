/**
 * Tool Registry — each tool is a self-contained definition.
 * To add a new tool: create a file in this directory, export `toolDefinition`.
 * The chat route auto-imports everything here.
 */
import { tool } from "ai";
import { z } from "zod";

function getBackendUrl(): string {
  const url = process.env.MUSIC_BACKEND_URL;
  if (!url) throw new Error("MUSIC_BACKEND_URL not set");
  return url;
}

async function backendPost(path: string, body: Record<string, unknown>) {
  const res = await fetch(`${getBackendUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? (data as { detail?: unknown }).detail
        : undefined;
    throw new Error(
      typeof detail === "string" ? detail : `Backend error ${res.status}`
    );
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Tool: transcribe_audio
// ---------------------------------------------------------------------------
export const transcribeAudioTool = tool({
  description:
    "Transcribe an audio file to MIDI notes. Use when the user wants to convert audio to notes, sheet music, or MIDI.",
  inputSchema: z.object({
    audio_base64: z
      .string()
      .describe("Base64-encoded audio data (WAV, MP3, M4A, OGG, FLAC)"),
    format: z
      .enum(["wav", "mp3", "m4a", "ogg", "flac"])
      .default("wav")
      .describe("Audio format"),
  }),
  execute: async ({ audio_base64, format }) => {
    const result = await backendPost("/music/transcribe", {
      audio_base64,
      fmt: format,
      upload: false,
    });
    return {
      num_notes: result.num_notes,
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
  description:
    "Analyze a MIDI file for music theory: key, tempo, time signature, chords, Roman numerals, cadences, modulations, and voice leading.",
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
  description:
    "Clean and denoise an audio recording. Removes background noise, clips, and normalizes volume.",
  inputSchema: z.object({
    audio_base64: z.string().describe("Base64-encoded audio data"),
    format: z
      .enum(["wav", "mp3", "m4a", "ogg", "flac"])
      .default("wav")
      .describe("Audio format"),
  }),
  execute: async ({ audio_base64, format }) => {
    const result = await backendPost("/music/enhance", {
      audio_base64,
      fmt: format,
      upload: false,
    });
    return {
      success: true,
      wav_base64: result.wav_base64,
      message: "Audio enhanced successfully",
    };
  },
});

// ---------------------------------------------------------------------------
// Tool: convert_format
// ---------------------------------------------------------------------------
export const convertFormatTool = tool({
  description:
    "Convert between MIDI and MusicXML formats. Use when the user wants sheet music from MIDI or vice versa.",
  inputSchema: z.object({
    data_base64: z.string().describe("Base64-encoded file data"),
    source: z.enum(["midi", "musicxml"]).describe("Source format"),
    target: z
      .enum(["midi", "musicxml", "auto"])
      .default("auto")
      .describe("Target format"),
  }),
  execute: async ({ data_base64, source, target }) => {
    const result = await backendPost("/music/convert", {
      source,
      data_base64,
      target,
    });
    return {
      data_base64: result.data_base64,
      format: result.format,
      message: `Converted to ${result.format}`,
    };
  },
});

// ---------------------------------------------------------------------------
// Registry — export all tools as a single map.
// To add a new tool: import it above and add it here. That's it.
// ---------------------------------------------------------------------------
export const musicTools = {
  transcribe_audio: transcribeAudioTool,
  analyze_midi: analyzeMidiTool,
  enhance_audio: enhanceAudioTool,
  convert_format: convertFormatTool,
};
