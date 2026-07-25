/**
 * Shared types for the music domain.
 *
 * WHY: These types define the contract between the frontend and backend.
 * The backend's AnalysisResult TypedDict in analyze.py must stay in sync
 * with TranscribeResult["analysis"]. Any change to the analysis schema
 * requires updating both sides.
 *
 * WHERE USED:
 * - TranscribeResult: transcribe/index.tsx, Studio.tsx, viz/index.tsx, MusicChat.tsx
 * - LibFile: library/index.tsx, Studio.tsx, viz/index.tsx
 * - Transcription: library/index.tsx, Studio.tsx
 */

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
