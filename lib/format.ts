/**
 * Format utilities — audio encoding, time formatting, format detection.
 *
 * These are pure functions with no side effects. Used across library,
 * transcribe, and viz components.
 */

/** Convert a Blob to base64 string using chunked processing for large files. */
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

/** Format seconds as "M:SS". */
export function formatTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/** Detect audio format from Blob MIME type. */
export function audioFmtFromBlob(blob: Blob): string {
  const type = blob.type.toLowerCase();
  if (type.includes("ogg")) return "ogg";
  if (type.includes("mp4") || type.includes("m4a")) return "mp4";
  if (type.includes("flac")) return "flac";
  if (type.includes("mp3") || type.includes("mpeg")) return "mp3";
  return "wav";
}

/** Detect audio format from file extension. */
export function audioFmtFromName(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (["ogg", "mp4", "m4a", "flac", "mp3", "wav", "webm"].includes(ext)) {
    return ext === "m4a" ? "mp4" : ext;
  }
  return "wav";
}

const AUDIO_EXTENSION = /\.(wav|mp3|m4a|flac|ogg|aac|mp4|webm|aiff|aif)$/i;

/**
 * Present a work title safely in headings and library rows. Strips a trailing
 * audio extension (older recordings may keep it), collapses whitespace, and
 * truncates so pathological raw filenames (e.g. "+_+", long hash names) render
 * cleanly instead of breaking layout. Never invents a nicer name — this is
 * presentation only.
 */
export function presentableTitle(title: string): string {
  const cleaned = title.trim().replace(/\s+/g, " ").replace(AUDIO_EXTENSION, "");
  const fallback = cleaned.length > 0 ? cleaned : "Untitled piece";
  return truncateMiddle(fallback, 48);
}

/** Truncate long titles gracefully, preserving the meaningful ending. */
export function truncateMiddle(value: string, maxLength: number): string {
  if (value.length <= maxLength) return value;
  const keep = maxLength - 1;
  const head = Math.ceil(keep * 0.6);
  const tailStart = value.length - (keep - head);
  return `${value.slice(0, head)}…${value.slice(tailStart)}`;
}

/**
 * Translate the durable job's overall progress into a concise, user-facing
 * stage label. The understand pipeline maps its stages onto these progress
 * ranges in the backend: transcription 0–0.65, analysis 0.65–0.90, score
 * 0.90–1.0. Falling back to a simple honest state keeps the copy truthful
 * without exposing internal status_message strings.
 */
export function understandStageLabel(progress: number): string {
  if (progress < 0.3) return "Preparing your recording…";
  if (progress < 0.65) return "Transcribing notes…";
  if (progress < 0.9) return "Analyzing the music…";
  return "Building the score…";
}
