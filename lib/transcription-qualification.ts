export const GENERAL_TRANSCRIPTION_LIMITATION =
  "General transcription draft — dense or full mixes may miss notes or add extra notes.";

/**
 * Return the product-facing limitation carried by a persisted transcription Version.
 *
 * The Version metadata is authoritative for an already-processed Work. Deliberately
 * do not consult the workspace's current import-mode selector: that setting only
 * controls future processing requests and can change after this Version was made.
 */
export function getSymbolicTranscriptionQualification(metadata: unknown): string | null {
  if (!metadata || typeof metadata !== "object") return null;

  const profile = (metadata as Record<string, unknown>).transcription_profile;
  return profile === "auto" ? GENERAL_TRANSCRIPTION_LIMITATION : null;
}

/** Apply the same upstream transcription qualification to every symbolic view. */
export function qualifySymbolicSourceLabel(baseLabel: string, metadata: unknown): string {
  const qualification = getSymbolicTranscriptionQualification(metadata);
  return qualification ? `${baseLabel} · ${qualification}` : baseLabel;
}
