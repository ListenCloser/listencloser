/**
 * Music domain — barrel re-export.
 *
 * WHY: This file re-exports from the focused modules so existing
 * imports like `import { transcribeAudio } from "@/lib/music"` continue
 * to work. New code should import directly from the specific module:
 *   - import { transcribeAudio } from "@/lib/music-api"
 *   - import { listLibrary } from "@/lib/library"
 *   - import { notesToMidiBase64 } from "@/lib/midi"
 *   - import { formatTime } from "@/lib/format"
 *   - import type { TranscribeResult } from "@/lib/types"
 *
 * This barrel exists only for backward compatibility during migration.
 */

// Types
export type { TranscribeResult, LibFile, Transcription, TrackState } from "./types";
export { deriveTrackState } from "./types";

// API calls
export { transcribeAudio, enhanceAudio, analyzeAudio, synthAudio, synthMusicXml, convertMusicFormat } from "./music-api";

// Library CRUD
export { uploadToLibrary, listLibrary, saveTranscription, deleteFromLibrary, listTranscriptions } from "./library";

// MIDI encoding
export { notesToMidiBase64, type NoteInput } from "./midi";

// Format utilities
export { blobToBase64, formatTime, audioFmtFromBlob, audioFmtFromName } from "./format";
