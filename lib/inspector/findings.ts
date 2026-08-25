/**
 * Deterministic temporal findings — musically meaningful observations
 * derived from existing analysis evidence.
 *
 * DERIVATION RULES:
 *
 * density_peak:
 *   - Source: rhythm_density insight evidence.windows[]
 *   - Threshold: density > 0, at least 2 windows
 *   - Derivation: window with highest density value
 *   - Label: "Peak note density around {time}"
 *
 * density_valley:
 *   - Source: rhythm_density insight evidence.windows[]
 *   - Threshold: valley density < peak density * 0.5 (significant difference)
 *   - Derivation: window with lowest non-zero density
 *   - Label: "Quieter passage around {time}"
 *
 * rest:
 *   - Source: rhythm_rests insight evidence.rests[]
 *   - Threshold: duration >= 0.5s (observed silence, not phrase boundary)
 *   - Derivation: longest rest segment
 *   - Label: "Pronounced rest around {time}"
 *
 * harmonic_activity:
 *   - Source: chord insight spans
 *   - Threshold: >= 4 chords with valid timestamps, density ratio > 1.5x
 *   - Derivation: sliding window of 3 chords, highest chords/second
 *   - Meaning: chord-change activity, NOT harmonic tension
 *   - Label: "Harmonic changes become more frequent around {time}"
 *
 * RULES:
 * - Zero findings is acceptable (sparse evidence → empty array)
 * - Confidence is never fabricated (uses null from source insights)
 * - Findings are sorted by time
 * - Maximum 8 findings per piece
 * - No withheld kinds are processed
 */

import type { Insight } from "@/lib/domain.types";
import { formatTime } from "@/lib/format";

export interface TemporalFinding {
  id: string;
  kind: "density_peak" | "density_valley" | "rest" | "harmonic_activity" | "melody_register_peak" | "melody_register_low";
  category: "rhythm" | "harmony" | "melody";
  startSeconds: number;
  endSeconds: number;
  label: string;
  evidence: Record<string, unknown>;
}

/**
 * Derive temporal findings from existing insights.
 * Returns 0-8 findings. Zero is acceptable for sparse evidence.
 */
export function deriveFindings(insights: Insight[]): TemporalFinding[] {
  const findings: TemporalFinding[] = [];

  // Density findings
  findings.push(...deriveDensityFindings(insights));

  // Rest findings
  findings.push(...deriveRestFindings(insights));

  // Harmonic activity findings
  findings.push(...deriveHarmonicActivityFindings(insights));

  // Melody findings
  findings.push(...deriveMelodyFindings(insights));

  // Sort by time and limit
  findings.sort((a, b) => a.startSeconds - b.startSeconds);
  return findings.slice(0, 8);
}

function deriveDensityFindings(insights: Insight[]): TemporalFinding[] {
  const findings: TemporalFinding[] = [];
  const densityInsights = insights.filter((i) => i.kind === "rhythm_density");

  for (const insight of densityInsights) {
    const windows = extractDensityWindows(insight);
    if (windows.length < 2) continue; // Need at least 2 windows for comparison

    // Peak density
    const peak = windows.reduce((max, w) => w.density > max.density ? w : max, windows[0]);
    if (peak.density <= 0) continue; // Skip if no actual density

    findings.push({
      id: `density-peak-${insight.id}`,
      kind: "density_peak",
      category: "rhythm",
      startSeconds: peak.start,
      endSeconds: peak.end,
      label: `Peak note density around ${formatTime(peak.start)}`,
      evidence: { density: peak.density, windowStart: peak.start, windowEnd: peak.end },
    });

    // Valley density (only if significantly different from peak)
    const nonZero = windows.filter((w) => w.density > 0);
    if (nonZero.length === 0) continue;

    const valley = nonZero.reduce((min, w) => w.density < min.density ? w : min, nonZero[0]);
    if (valley.density >= peak.density * 0.5) continue; // Not significantly different

    findings.push({
      id: `density-valley-${insight.id}`,
      kind: "density_valley",
      category: "rhythm",
      startSeconds: valley.start,
      endSeconds: valley.end,
      label: `Quieter passage around ${formatTime(valley.start)}`,
      evidence: { density: valley.density, windowStart: valley.start, windowEnd: valley.end },
    });
  }

  return findings;
}

function deriveRestFindings(insights: Insight[]): TemporalFinding[] {
  const findings: TemporalFinding[] = [];
  const restInsights = insights.filter((i) => i.kind === "rhythm_rests");

  for (const insight of restInsights) {
    const rests = extractRestSegments(insight);
    if (rests.length === 0) continue;

    // Longest rest (must be >= 500ms to be musically meaningful)
    const longest = rests.reduce((max, r) => r.duration > max.duration ? r : max, rests[0]);
    if (longest.duration < 0.5) continue;

    findings.push({
      id: `rest-${insight.id}`,
      kind: "rest",
      category: "rhythm",
      startSeconds: longest.start,
      endSeconds: longest.end,
      label: `Pronounced rest around ${formatTime(longest.start)}`,
      evidence: { duration: longest.duration, start: longest.start, end: longest.end },
    });
  }

  return findings;
}

function deriveHarmonicActivityFindings(insights: Insight[]): TemporalFinding[] {
  const findings: TemporalFinding[] = [];
  const chordInsights = insights.filter((i) => i.kind === "chord");

  // Need at least 4 chords to detect meaningful activity patterns
  if (chordInsights.length < 4) return findings;

  const sortedChords = chordInsights
    .filter((i) => i.span.start_seconds != null)
    .sort((a, b) => a.span.start_seconds! - b.span.start_seconds!);

  // Need at least 3 chords with valid timestamps for sliding window
  if (sortedChords.length < 3) return findings;

  // Find most active passage (highest chord-change density)
  let maxDensity = 0;
  let maxStart = 0;
  let maxEnd = 0;

  for (let i = 0; i <= sortedChords.length - 3; i++) {
    const windowStart = sortedChords[i].span.start_seconds!;
    const windowEnd = sortedChords[i + 2].span.end_seconds ?? sortedChords[i + 2].span.start_seconds! + 2;
    const windowDuration = windowEnd - windowStart;
    if (windowDuration <= 0) continue;

    const density = 3 / windowDuration; // chords per second
    if (density > maxDensity) {
      maxDensity = density;
      maxStart = windowStart;
      maxEnd = windowEnd;
    }
  }

  // Find least active passage
  let minDensity = Infinity;
  for (let i = 0; i <= sortedChords.length - 3; i++) {
    const windowStart = sortedChords[i].span.start_seconds!;
    const windowEnd = sortedChords[i + 2].span.end_seconds ?? sortedChords[i + 2].span.start_seconds! + 2;
    const windowDuration = windowEnd - windowStart;
    if (windowDuration <= 0) continue;

    const density = 3 / windowDuration;
    if (density < minDensity) {
      minDensity = density;
    }
  }

  // Only emit if there's a meaningful difference (1.5x ratio)
  if (maxDensity > 0 && minDensity < Infinity && maxDensity > minDensity * 1.5) {
    findings.push({
      id: "harmonic-activity-peak",
      kind: "harmonic_activity",
      category: "harmony",
      startSeconds: maxStart,
      endSeconds: maxEnd,
      label: `Harmonic changes become more frequent around ${formatTime(maxStart)}`,
      evidence: { chordDensity: maxDensity, windowStart: maxStart, windowEnd: maxEnd },
    });
  }

  return findings;
}

function extractDensityWindows(insight: Insight): { start: number; end: number; density: number }[] {
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

function extractRestSegments(insight: Insight): { start: number; end: number; duration: number }[] {
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

function deriveMelodyFindings(insights: Insight[]): TemporalFinding[] {
  const findings: TemporalFinding[] = [];
  // Only include register events (trivial max/min projection)
  // Other melody findings (interval, contour, motif) are evaluation_only
  const melodyKinds = ["melody_register_peak", "melody_register_low"];

  for (const kind of melodyKinds) {
    const kindInsights = insights.filter((i) => i.kind === kind);
    for (const insight of kindInsights) {
      if (insight.span.start_seconds == null || insight.span.end_seconds == null) continue;

      const category = "melody" as const;
      findings.push({
        id: `${kind}-${insight.id}`,
        kind: kind as TemporalFinding["kind"],
        category,
        startSeconds: insight.span.start_seconds,
        endSeconds: insight.span.end_seconds,
        label: insight.claim,
        evidence: insight.evidence ?? {},
      });
    }
  }

  return findings;
}