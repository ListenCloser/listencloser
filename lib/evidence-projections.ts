import type { Insight } from "@/lib/domain.types";

/**
 * Cross-representation evidence projection contract.
 *
 * Persisted evidence is the source of truth. This module only describes how
 * admitted evidence may be presented on a representation; it does not create
 * representation-specific copies of evidence or infer cross-Version authority.
 *
 * Projection precision MUST be supplied by the caller that owns representation
 * authority/alignment. A shared Work id or overlapping time span is never enough
 * to upgrade precision here.
 */

export type EvidenceProjectionTarget = "listen" | "piano_roll" | "score" | "spectrogram";

export type EvidenceProjectionMode =
  | "time-region"
  | "time-boundary"
  | "ruler-segment"
  | "note-highlight"
  | "beat-guide"
  | "score-symbol"
  | "score-region"
  | "frequency-region"
  | "none";

export type EvidenceProjectionPrecision = "exact" | "adequate" | "approximate" | "unsupported";

/**
 * Presentation-only grouping used by the legacy annotation color system.
 * This is deliberately not a permanent musical ontology.
 */
export type EvidencePresentationFamily = "rhythm" | "harmony" | "theory";

export type EvidenceProjectionPolicy = {
  preferredMode: EvidenceProjectionMode;
  /** Minimum authority/alignment required before preferredMode may be used. */
  minimumPrecision: Exclude<EvidenceProjectionPrecision, "unsupported">;
  /** Conservative locator when the preferred native projection is too precise. */
  fallbackMode?: EvidenceProjectionMode;
  /** Whether preferredMode directly expresses the evidence on this representation. */
  native: boolean;
  /** Passive background layer default; focused evidence can still be located when false. */
  passiveByDefault: boolean;
  /** Context required before an interpretive label may be shown. */
  requiresContext?: readonly ("key")[];
};

export type ResolvedEvidenceProjection = {
  kind: string;
  target: EvidenceProjectionTarget;
  mode: EvidenceProjectionMode;
  precision: EvidenceProjectionPrecision;
  native: boolean;
  passiveByDefault: boolean;
  requiresContext: readonly ("key")[];
};

const NONE_POLICY: EvidenceProjectionPolicy = {
  preferredMode: "none",
  minimumPrecision: "exact",
  native: false,
  passiveByDefault: false,
};

const POLICIES: Record<string, Partial<Record<EvidenceProjectionTarget, EvidenceProjectionPolicy>>> = {
  chord: {
    listen: {
      preferredMode: "time-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: false,
    },
    piano_roll: {
      preferredMode: "ruler-segment",
      minimumPrecision: "adequate",
      fallbackMode: "time-region",
      native: true,
      passiveByDefault: true,
    },
    score: {
      preferredMode: "score-symbol",
      minimumPrecision: "adequate",
      fallbackMode: "score-region",
      native: true,
      passiveByDefault: true,
    },
    spectrogram: {
      preferredMode: "time-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: false,
    },
  },
  roman_numeral: {
    listen: {
      preferredMode: "time-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: false,
      requiresContext: ["key"],
    },
    piano_roll: {
      preferredMode: "ruler-segment",
      minimumPrecision: "adequate",
      fallbackMode: "time-region",
      native: true,
      passiveByDefault: false,
      requiresContext: ["key"],
    },
    score: {
      preferredMode: "score-symbol",
      minimumPrecision: "adequate",
      fallbackMode: "score-region",
      native: true,
      passiveByDefault: false,
      requiresContext: ["key"],
    },
  },
  harmonic_function: {
    listen: {
      preferredMode: "time-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: false,
      requiresContext: ["key"],
    },
    piano_roll: {
      preferredMode: "ruler-segment",
      minimumPrecision: "adequate",
      fallbackMode: "time-region",
      native: true,
      passiveByDefault: false,
      requiresContext: ["key"],
    },
    score: {
      preferredMode: "score-symbol",
      minimumPrecision: "adequate",
      fallbackMode: "score-region",
      native: true,
      passiveByDefault: false,
      requiresContext: ["key"],
    },
  },
  harmonic_rhythm: {
    listen: {
      preferredMode: "time-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: true,
    },
    piano_roll: {
      preferredMode: "time-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: true,
    },
    score: {
      preferredMode: "score-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: true,
    },
    spectrogram: {
      preferredMode: "time-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: true,
    },
  },
  rhythm_density: {
    listen: {
      preferredMode: "time-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: true,
    },
    piano_roll: {
      preferredMode: "time-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: true,
    },
    score: {
      preferredMode: "score-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: true,
    },
    spectrogram: {
      preferredMode: "time-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: true,
    },
  },
  rhythm_rests: {
    listen: {
      preferredMode: "time-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: true,
    },
    piano_roll: {
      preferredMode: "time-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: true,
    },
    score: {
      preferredMode: "score-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: true,
    },
    spectrogram: {
      preferredMode: "time-region",
      minimumPrecision: "approximate",
      native: false,
      passiveByDefault: true,
    },
  },
};

const PRECISION_RANK: Record<EvidenceProjectionPrecision, number> = {
  unsupported: 0,
  approximate: 1,
  adequate: 2,
  exact: 3,
};

export function presentationFamilyForKind(kind: string): EvidencePresentationFamily | null {
  switch (kind) {
    case "rhythm_density":
    case "rhythm_rests":
      return "rhythm";
    case "harmonic_rhythm":
      return "harmony";
    case "roman_numeral":
    case "harmonic_function":
    case "chord":
      return "theory";
    default:
      return null;
  }
}

export function projectionPolicyForKind(
  kind: string,
  target: EvidenceProjectionTarget,
): EvidenceProjectionPolicy {
  return POLICIES[kind]?.[target] ?? NONE_POLICY;
}

/**
 * Resolve a display mode without inventing authority.
 *
 * Example: approximate time→measure alignment may locate a chord on Score, but
 * it must fall back from `score-symbol` to `score-region` rather than implying
 * exact/adequate musical placement.
 */
export function resolveEvidenceProjection(
  kind: string,
  target: EvidenceProjectionTarget,
  precision: EvidenceProjectionPrecision,
): ResolvedEvidenceProjection {
  const policy = projectionPolicyForKind(kind, target);
  const requiresContext = policy.requiresContext ?? [];

  if (precision === "unsupported" || policy.preferredMode === "none") {
    return {
      kind,
      target,
      mode: "none",
      precision: "unsupported",
      native: false,
      passiveByDefault: false,
      requiresContext,
    };
  }

  if (PRECISION_RANK[precision] >= PRECISION_RANK[policy.minimumPrecision]) {
    return {
      kind,
      target,
      mode: policy.preferredMode,
      precision,
      native: policy.native,
      passiveByDefault: policy.passiveByDefault,
      requiresContext,
    };
  }

  if (policy.fallbackMode) {
    return {
      kind,
      target,
      mode: policy.fallbackMode,
      precision,
      native: false,
      passiveByDefault: false,
      requiresContext,
    };
  }

  return {
    kind,
    target,
    mode: "none",
    precision: "unsupported",
    native: false,
    passiveByDefault: false,
    requiresContext,
  };
}

/** Convenience overload for callers already holding a persisted Insight. */
export function resolveInsightProjection(
  insight: Insight,
  target: EvidenceProjectionTarget,
  precision: EvidenceProjectionPrecision,
): ResolvedEvidenceProjection {
  return resolveEvidenceProjection(insight.kind, target, precision);
}
