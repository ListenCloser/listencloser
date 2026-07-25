/**
 * Backend API calls for music processing.
 *
 * WHY: This module exists because the browser cannot talk to the FastAPI
 * backend directly (CORS, auth, VM URL exposure). All requests go through
 * Next.js API routes which proxy to the backend. This module wraps those
 * proxy calls with type-safe fetch wrappers.
 *
 * ARCHITECTURE:
 *   Browser → this module → Next.js API route → lib/backend.ts → FastAPI
 *
 * Each function maps 1:1 to a FastAPI endpoint in backend/main.py.
 * The return types mirror the backend's Pydantic response models.
 */

import { apiFetch } from "./api";
import type { TranscribeResult } from "./types";

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
