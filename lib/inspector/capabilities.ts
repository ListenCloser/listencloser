/**
 * Frontend presentation helpers for capability exposure.
 *
 * This is NOT a second truthfulness registry. The backend
 * (capabilities.json / capability_policy.py) is authoritative.
 *
 * These helpers exist solely to:
 * 1. Filter insights at the presentation layer (defense-in-depth)
 * 2. Provide UI hints (experimental badge, etc.)
 *
 * The backend already filters withheld capabilities before sending
 * insights to the API. This frontend filter is a safety net, not
 * the source of truth.
 *
 * To update: change backend/config/capabilities.json first,
 * then mirror the exposure flags here.
 */

/** Kinds the Inspector may display. Backend withholds all others. */
const INSPECTOR_ALLOWED = new Set([
  "key",
  "chord",
  "roman_numeral",
  "harmonic_function",
  "tempo",
  "audio_tempo",
  "time_signature",
  "rhythm",
  "rhythm_density",
  "rhythm_rests",
  "melody",
  "melody_register_peak",
  "melody_register_low",
]);

/** Kinds that are experimental (UI should show experimental badge). */
const EXPERIMENTAL = new Set([
  "melody",
]);

/** Whether a capability kind is allowed in the Inspector. */
export function isInspectorExposed(kind: string): boolean {
  return INSPECTOR_ALLOWED.has(kind);
}

/** Whether a capability kind is experimental. */
export function isExperimental(kind: string): boolean {
  return EXPERIMENTAL.has(kind);
}

/** Kinds that may appear in the Inspector. */
export const INSPECTOR_EXPOSED_KINDS = [...INSPECTOR_ALLOWED];
