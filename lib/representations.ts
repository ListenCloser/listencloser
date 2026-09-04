import type { RepresentationAvailability } from "@/lib/representation-availability";

/** Stable representation identifiers shared by workspace state and Ask actions. */
export type RepresentationId = "listen" | "piano_roll" | "score" | "spectrogram";

/**
 * Pure product metadata for one representation.
 *
 * This catalog deliberately has no React/component ownership. Shared consumers
 * such as Ask can resolve a label or validate an id without importing the
 * workspace renderer graph.
 */
export type RepresentationMetadata = {
  id: RepresentationId;
  title: string;
  description: string;
  /** Whether this view follows the moving playhead. */
  temporal: boolean;
  available: (availability: RepresentationAvailability) => boolean;
};

export const REPRESENTATION_CATALOG: readonly RepresentationMetadata[] = [
  {
    id: "listen",
    title: "Waveform",
    description: "Audio waveform visualization with time ruler and selection.",
    temporal: true,
    available: (availability) => availability.originalAudio,
  },
  {
    id: "piano_roll",
    title: "Piano Roll",
    description: "Every detected note with its timing and pitch.",
    temporal: true,
    available: (availability) => availability.performanceMidi,
  },
  {
    id: "score",
    title: "Score",
    description: "Score playback follows the written timing.",
    temporal: true,
    available: (availability) => availability.score,
  },
  {
    id: "spectrogram",
    title: "Spectrogram",
    description: "Frequency over performance time with shared playback and selection.",
    temporal: true,
    available: (availability) => availability.originalAudio,
  },
];

export function representationById(id: RepresentationId): RepresentationMetadata | undefined {
  return REPRESENTATION_CATALOG.find((definition) => definition.id === id);
}
