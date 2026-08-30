import type { Insight } from "@/lib/domain.types";

export type ObservedPulseGrid = {
  versionId: string;
  beatsSeconds: number[];
  downbeatsSeconds: number[];
  provenance: Record<string, unknown>;
};

function increasingSeconds(value: unknown): number[] | null {
  if (!Array.isArray(value)) return null;
  const result: number[] = [];
  for (const item of value) {
    if (typeof item !== "number" || !Number.isFinite(item) || item < 0) return null;
    if (result.length > 0 && item <= result[result.length - 1]) return null;
    result.push(item);
  }
  return result;
}

function createdAtMillis(insight: Insight): number {
  const value = Date.parse(insight.created_at);
  return Number.isFinite(value) ? value : 0;
}

/**
 * Return the newest valid observed pulse grid for exactly one representation Version.
 *
 * Pulse coordinates are persisted on the broad `rhythm` evidence object because
 * that is already the version-scoped pulse-derived analysis contract. Consumers
 * should use this adapter rather than reverse-engineering beat positions from
 * density-window boundaries.
 */
export function extractObservedPulseGrid(
  insights: Insight[],
  versionId: string | null | undefined,
): ObservedPulseGrid | null {
  if (!versionId) return null;

  const candidates = insights
    .filter((insight) => insight.kind === "rhythm" && insight.version_id === versionId)
    .sort((a, b) => createdAtMillis(b) - createdAtMillis(a));

  for (const insight of candidates) {
    const beats = increasingSeconds(insight.evidence?.beats_seconds);
    const downbeats = increasingSeconds(insight.evidence?.downbeats_seconds);
    if (!beats || beats.length < 2 || !downbeats) continue;
    if (insight.evidence?.pulse_coordinate_unit !== "seconds") continue;

    return {
      versionId,
      beatsSeconds: beats,
      downbeatsSeconds: downbeats,
      provenance: (insight.provenance ?? {}) as Record<string, unknown>,
    };
  }

  return null;
}
