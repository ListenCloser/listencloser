export type AnalysisDiscoveryId =
  | "structure-map"
  | "pitch-contour"
  | "layers"
  | "similar-moments"
  | "measured-changes";

export type AnalysisDiscoveryDefinition = {
  id: AnalysisDiscoveryId;
  title: string;
  description: string;
  readyDescription?: string;
  searchAliases: readonly string[];
};

export const ANALYSIS_DISCOVERY_DEFINITIONS: Record<AnalysisDiscoveryId, AnalysisDiscoveryDefinition> = {
  "structure-map": {
    id: "structure-map",
    title: "Structure Map",
    description: "Find rough candidate spans so you can jump through the recording's shape.",
    readyDescription: "Rough candidate spans are ready for navigation.",
    searchAliases: ["structure", "sections", "parts", "shape", "form", "intro", "verse", "chorus"],
  },
  "pitch-contour": {
    id: "pitch-contour",
    title: "Pitch Contour",
    description: "Trace continuous monophonic pitch against the recording and seek through it.",
    searchAliases: ["pitch", "voice", "vocal line", "singing", "intonation", "melodic line"],
  },
  layers: {
    id: "layers",
    title: "Separate layers",
    description: "Separate vocals, drums, bass, and other so you can hear each part.",
    searchAliases: ["layers", "stems", "vocals", "drums", "bass", "isolate", "separate"],
  },
  "similar-moments": {
    id: "similar-moments",
    title: "Similar moments",
    description: "Find method-qualified candidate passages like this exact selection.",
    searchAliases: ["similar", "repeat", "repeated", "sounds like this", "another passage like this"],
  },
  "measured-changes": {
    id: "measured-changes",
    title: "Changes",
    description: "Open measured change moments in Breakdown without starting another job.",
    searchAliases: ["changes", "where it changes", "contrast", "transition", "different"],
  },
};

export type ProductReachability =
  | "USER_REACHABLE"
  | "INTERNAL_PRIMITIVE"
  | "EVALUATION_ONLY"
  | "WITHHELD"
  | "ROLLBACK_ONLY"
  | "MISSING_UI";

export type ProductInspectionRuntime = {
  runtimeId: string;
  capability: string;
  reachability: ProductReachability;
  followUpIssue?: number;
};

// This is intentionally not another capability registry. backend/config/capabilities.json
// remains authority for capability maturity/exposure. This list only records known
// runtime/product-inspection exceptions that a product owner could otherwise close over.
export const PRODUCT_INSPECTION_RUNTIME_EXCEPTIONS: readonly ProductInspectionRuntime[] = [
  {
    runtimeId: "chordmini",
    capability: "chord",
    reachability: "MISSING_UI",
    followUpIssue: 1194,
  },
];

export function validateProductInspectionReachability(
  entries: readonly ProductInspectionRuntime[],
): void {
  for (const entry of entries) {
    if (entry.reachability === "MISSING_UI" && !entry.followUpIssue) {
      throw new Error(`${entry.runtimeId} is MISSING_UI without a focused UI follow-up`);
    }
  }
}

export const DISCOVERABILITY_TASK_CASES = [
  { task: "show me the shape or parts of this recording", expected: "structure-map" },
  { task: "trace the pitch or vocal line", expected: "pitch-contour" },
  { task: "isolate the vocals, drums, or bass", expected: "layers" },
  { task: "find another passage like this", expected: "similar-moments" },
  { task: "show me where the recording changes", expected: "measured-changes" },
] as const satisfies readonly { task: string; expected: AnalysisDiscoveryId }[];

export const FUTURE_DISCOVERY_DECISIONS = {
  findWithinWork: {
    issue: 1254,
    decision: "Reuse Add analysis; test a contextual Find in this recording entry before adding any global search UI.",
  },
} as const;
