/**
 * Analysis annotations — temporal evidence rendered on music representations.
 *
 * Extracts time-bounded annotations from the Insight store for rendering
 * on Waveform, Piano Roll, and Score. Reuses the existing Insight type;
 * no new DB schema.
 *
 * Semantic categories:
 *   rhythm  → muted ochre
 *   harmony → muted green
 *
 * These are lighter than playback (blue) and selection (terracotta).
 */

import type { Insight } from "@/lib/domain.types";

export type AnnotationCategory = "rhythm" | "harmony" | "theory";

export interface AnalysisAnnotation {
  id: string;
  kind: string;
  category: AnnotationCategory;
  startSeconds: number;
  endSeconds: number;
  label: string;
  summary: string;
  confidence: number | null;
  insight: Insight;
}

/** Map insight kind → semantic category. */
function categorizeKind(kind: string): AnnotationCategory | null {
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

/**
 * Extract temporal annotations from insights that have valid time spans.
 * Only includes the kinds we currently render: rhythm_density, rhythm_rests,
 * harmonic_rhythm.
 */
export function extractAnnotations(insights: Insight[]): AnalysisAnnotation[] {
  const annotations: AnalysisAnnotation[] = [];

  for (const insight of insights) {
    const category = categorizeKind(insight.kind);
    if (!category) continue;

    const start = insight.span.start_seconds;
    const end = insight.span.end_seconds;
    if (start == null || end == null || end <= start) continue;

    annotations.push({
      id: insight.id,
      kind: insight.kind,
      category,
      startSeconds: start,
      endSeconds: end,
      label: deriveLabel(insight),
      summary: insight.claim,
      confidence: insight.confidence,
      insight,
    });
  }

  return annotations;
}

function deriveLabel(insight: Insight): string {
  switch (insight.kind) {
    case "rhythm_density":
      return "Note density";
    case "rhythm_rests":
      return "Rest";
    case "harmonic_rhythm":
      return "Chord activity";
    case "chord":
      return String(insight.claim || "Chord");
    case "roman_numeral":
      return String(insight.claim || insight.evidence?.numeral || "Roman numeral");
    case "harmonic_function":
      return String(insight.claim || insight.evidence?.function || "Function");
    default:
      return insight.kind;
  }
}

/**
 * Extract per-window density data from a rhythm_density or harmonic_rhythm
 * insight's evidence. Returns time → density pairs for rendering activity
 * bands.
 */
export function extractDensityWindows(
  insight: Insight,
): { start: number; end: number; density: number }[] {
  const windows = (insight.evidence?.windows ?? []) as {
    start?: number;
    end?: number;
    density?: number;
  }[];
  return windows
    .filter((w) => w.start != null && w.end != null && w.density != null)
    .map((w) => ({
      start: w.start!,
      end: w.end!,
      density: w.density!,
    }));
}

/**
 * Extract rest segments from a rhythm_rests insight's evidence.
 */
export function extractRestSegments(
  insight: Insight,
): { start: number; end: number; duration: number }[] {
  const rests = (insight.evidence?.rests ?? []) as {
    start?: number;
    end?: number;
    duration?: number;
  }[];
  return rests
    .filter((r) => r.start != null && r.end != null)
    .map((r) => ({
      start: r.start!,
      end: r.end!,
      duration: r.duration ?? r.end! - r.start!,
    }));
}

/**
 * CSS color variables for annotation categories.
 * These are lighter/subtler than playback (blue) and selection (terracotta).
 */
export const ANNOTATION_COLORS: Record<AnnotationCategory, { fill: string; stroke: string }> = {
  rhythm: { fill: "var(--color-rhythm-soft)", stroke: "var(--color-rhythm)" },
  harmony: { fill: "var(--color-harmony-soft)", stroke: "var(--color-harmony)" },
  theory: { fill: "var(--color-theory-soft, #e8e0f0)", stroke: "var(--color-theory, #8b5cf6)" },
};

/**
 * Map an annotation's time span to a measure range using existing
 * measure_starts_seconds metadata.  Returns null when measureStarts is
 * empty or the annotation falls outside the score.
 */
export function annotationToMeasureRange(
  annotation: AnalysisAnnotation,
  measureStarts: number[],
): { start: number; end: number } | null {
  if (measureStarts.length === 0) return null;
  let start = -1;
  let end = -1;
  for (let i = 0; i < measureStarts.length; i += 1) {
    if (measureStarts[i] <= annotation.startSeconds) start = i;
    if (measureStarts[i] <= annotation.endSeconds) end = i;
  }
  if (start < 0 || end < 0) return null;
  return { start, end };
}
