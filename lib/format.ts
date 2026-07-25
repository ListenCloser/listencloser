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
