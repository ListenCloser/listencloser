/**
 * Frontend capability exposure policy.
 *
 * Mirrors backend/config/capabilities.json exposure flags.
 * The Inspector must never expose insights whose kind maps to a
 * capability with inspector: false, even if the backend accidentally
 * returns them.
 *
 * This is the single source of truth for what the UI may display.
 */

type CapabilityExposure = {
  inspector: boolean;
  annotations: boolean;
  ask: boolean;
};

type CapabilityEntry = {
  status: "production" | "withheld" | "experimental" | "evaluation_only";
  exposure: CapabilityExposure;
};

const CAPABILITIES: Record<string, CapabilityEntry> = {
  key: {
    status: "production",
    exposure: { inspector: true, annotations: false, ask: true },
  },
  chord: {
    status: "production",
    exposure: { inspector: true, annotations: true, ask: true },
  },
  roman_numeral: {
    status: "production",
    exposure: { inspector: true, annotations: true, ask: true },
  },
  harmonic_function: {
    status: "production",
    exposure: { inspector: true, annotations: true, ask: true },
  },
  cadence: {
    status: "withheld",
    exposure: { inspector: false, annotations: false, ask: false },
  },
  key_region: {
    status: "withheld",
    exposure: { inspector: false, annotations: false, ask: false },
  },
  tempo: {
    status: "production",
    exposure: { inspector: true, annotations: false, ask: true },
  },
  rhythm: {
    status: "production",
    exposure: { inspector: true, annotations: true, ask: true },
  },
  melody: {
    status: "experimental",
    exposure: { inspector: true, annotations: false, ask: true },
  },
  time_signature: {
    status: "production",
    exposure: { inspector: true, annotations: false, ask: true },
  },
  audio_tempo: {
    status: "production",
    exposure: { inspector: true, annotations: false, ask: true },
  },
  section: {
    status: "evaluation_only",
    exposure: { inspector: false, annotations: false, ask: false },
  },
  audio_structure: {
    status: "evaluation_only",
    exposure: { inspector: false, annotations: false, ask: false },
  },
  rhythm_density: {
    status: "production",
    exposure: { inspector: true, annotations: false, ask: false },
  },
  rhythm_rests: {
    status: "production",
    exposure: { inspector: true, annotations: false, ask: false },
  },
  harmonic_rhythm: {
    status: "withheld",
    exposure: { inspector: false, annotations: false, ask: false },
  },
  voice_leading: {
    status: "withheld",
    exposure: { inspector: false, annotations: false, ask: false },
  },
  structure: {
    status: "evaluation_only",
    exposure: { inspector: false, annotations: false, ask: false },
  },
};

/** Whether a capability kind is exposed in the Inspector. */
export function isInspectorExposed(kind: string): boolean {
  return CAPABILITIES[kind]?.exposure.inspector ?? false;
}

/** Whether a capability kind is experimental. */
export function isExperimental(kind: string): boolean {
  return CAPABILITIES[kind]?.status === "experimental";
}

/** Whether a capability kind is withheld. */
export function isWithheld(kind: string): boolean {
  return CAPABILITIES[kind]?.status === "withheld";
}

/** Kinds that may appear in the Inspector. */
export const INSPECTOR_EXPOSED_KINDS = Object.entries(CAPABILITIES)
  .filter(([, entry]) => entry.exposure.inspector)
  .map(([kind]) => kind);
