/**
 * Shared types for the music domain.
 *
 * WHY: These types define the contract between the frontend and backend.
 * The backend's AnalysisResult TypedDict in analyze.py must stay in sync
 * with TranscribeResult["analysis"]. Any change to the analysis schema
 * requires updating both sides.
 *
 * ARCHITECTURE: LibFile is the canonical source of track state. Every
 * downstream feature (Transform, Visualize, Analysis, Chat) reads from
 * LibFile's track_state field instead of independently determining
 * what processing has occurred.
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
    phrases?: { start: number; end: number; kind: string }[];
    rhythm?: {
      beat_count: number;
      avg_note_duration: number;
      syncopation_ratio: number;
      rhythmic_density: number;
    };
  };
};

/**
 * Persistent processing state for a track.
 * Derived from what data exists on the LibFile — not stored separately.
 * This is the source of truth for what processing has been completed.
 */
export type TrackState = {
  uploaded: boolean;
  transcribed: boolean;
  sheetMusic: boolean;
  analysis: boolean;
  hasMidi: boolean;
};

export function deriveTrackState(file: LibFile): TrackState {
  return {
    uploaded: true,
    transcribed: Boolean(file.notes && file.notes.length > 0),
    sheetMusic: Boolean(file.musicxml),
    analysis: Boolean(file.analysis),
    hasMidi: Boolean(file.midi_base64),
  };
}

export type LibFile = {
  name: string;
  url: string;
  id: string;
  size?: number;
  created_at?: string;
  notes?: { pitch: number; start: number; end: number; velocity: number }[];
  midi_base64?: string;
  musicxml?: string;
  synth_wav_base64?: string;
  analysis?: TranscribeResult["analysis"];
};

export type Transcription = {
  id: string;
  title: string;
  notes: { pitch: number; start: number; end: number; velocity: number }[];
  wav_url?: string;
  created_at?: string;
};
