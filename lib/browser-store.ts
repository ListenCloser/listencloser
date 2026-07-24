import type { TranscribeResult } from "./music";

const STORAGE_KEY = "localTranscription";
const TAB_KEY = "studio:tab";
const RESULT_KEY = "studio:lastResult";
const ANALYSIS_KEY = "studio:analysis";
const AUDIO_NAME_KEY = "studio:audioName";

export type LocalTranscription = {
  name: string;
  notes: TranscribeResult["notes"];
  midi_base64?: string;
  audioDataUrl?: string;
  audioBlob?: Blob;
  analysis?: TranscribeResult["analysis"];
};

let cached: LocalTranscription | null = null;

export function saveLocalTranscription(
  name: string,
  notes: TranscribeResult["notes"],
  midiBase64?: string,
  audioBlob?: Blob,
  analysis?: TranscribeResult["analysis"],
): void {
  const entry: LocalTranscription = { name, notes, midi_base64: midiBase64, analysis };

  if (audioBlob) {
    const url = URL.createObjectURL(audioBlob);
    entry.audioDataUrl = url;
    entry.audioBlob = audioBlob;
  }

  cached = entry;

  try {
    const serialized = { name, notes, midi_base64: midiBase64, analysis };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(serialized));
  } catch {}
}

export function loadLocalTranscription(): LocalTranscription | null {
  if (cached) return cached;

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.notes || !Array.isArray(parsed.notes)) return null;
    cached = parsed;
    return cached;
  } catch {
    return null;
  }
}

export function clearLocalTranscription(): void {
  cached = null;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {}
}

// ── Tab persistence ──────────────────────────────────────────────────────

export function saveTab(tab: string): void {
  try { sessionStorage.setItem(TAB_KEY, tab); } catch {}
}

export function loadTab(): string | null {
  try { return sessionStorage.getItem(TAB_KEY); } catch { return null; }
}

// ── Last result persistence (survives refresh within session) ────────────

type PersistedResult = {
  notes: TranscribeResult["notes"];
  num_notes: number;
  midi_base64?: string;
  wav_url?: string;
};

export function saveLastResult(result: TranscribeResult | null): void {
  try {
    if (!result) {
      sessionStorage.removeItem(RESULT_KEY);
      return;
    }
    const slim: PersistedResult = {
      notes: result.notes,
      num_notes: result.num_notes,
      midi_base64: result.midi_base64,
      wav_url: result.wav_url,
    };
    sessionStorage.setItem(RESULT_KEY, JSON.stringify(slim));
  } catch {}
}

export function loadLastResult(): PersistedResult | null {
  try {
    const raw = sessionStorage.getItem(RESULT_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch { return null; }
}

// ── Analysis persistence ────────────────────────────────────────────────

export function saveAnalysis(analysis: TranscribeResult["analysis"] | null): void {
  try {
    if (!analysis) {
      sessionStorage.removeItem(ANALYSIS_KEY);
      return;
    }
    sessionStorage.setItem(ANALYSIS_KEY, JSON.stringify(analysis));
  } catch {}
}

export function loadAnalysis(): TranscribeResult["analysis"] | null {
  try {
    const raw = sessionStorage.getItem(ANALYSIS_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch { return null; }
}

// ── Audio name persistence ──────────────────────────────────────────────

export function saveAudioName(name: string): void {
  try { sessionStorage.setItem(AUDIO_NAME_KEY, name); } catch {}
}

export function loadAudioName(): string {
  try { return sessionStorage.getItem(AUDIO_NAME_KEY) ?? ""; } catch { return ""; }
}
