import type { Insight } from "@/lib/domain.types";

export type ObservedPulseGrid = {
  versionId: string;
  beatsSeconds: number[];
  downbeatsSeconds: number[];
  provenance: Record<string, unknown>;
  source: "explicit_pulse" | "beat_relative_windows";
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

function downbeatsBelongToBeats(downbeats: number[], beats: number[]): boolean {
  if (downbeats.length === 0) return true;
  let beatIndex = 0;
  for (const downbeat of downbeats) {
    while (beatIndex < beats.length && beats[beatIndex] < downbeat - 1e-9) {
      beatIndex += 1;
    }
    if (beatIndex >= beats.length || Math.abs(beats[beatIndex] - downbeat) > 1e-9) {
      return false;
    }
  }
  return true;
}

function beatsFromOneBeatWindows(value: unknown): number[] | null {
  if (!Array.isArray(value) || value.length === 0) return null;
  const beats: number[] = [];

  for (const item of value) {
    if (!item || typeof item !== "object") return null;
    const window = item as Record<string, unknown>;
    if (
      window.mode !== "beat_relative"
      || window.unit !== "events_per_beat"
      || window.window_size !== 1
      || window.step_size !== 1
    ) {
      return null;
    }
    const start = window.start;
    const end = window.end;
    if (
      typeof start !== "number"
      || typeof end !== "number"
      || !Number.isFinite(start)
      || !Number.isFinite(end)
      || start < 0
      || end <= start
    ) {
      return null;
    }
    if (beats.length === 0) {
      beats.push(start);
    } else if (Math.abs(start - beats[beats.length - 1]) > 1e-9) {
      return null;
    }
    beats.push(end);
  }

  return increasingSeconds(beats);
}

function createdAtMillis(insight: Insight): number {
  const value = Date.parse(insight.created_at);
  return Number.isFinite(value) ? value : 0;
}

/**
 * Return the newest valid observed pulse grid for exactly one representation Version.
 *
 * New analyses may persist explicit `beats_seconds` / `downbeats_seconds` on the
 * version-scoped rhythm evidence. Existing saved analyses already preserve the
 * observed beat coordinates losslessly as consecutive one-beat density-window
 * boundaries, so this adapter can recover those beats without inventing BPM
 * subdivisions. Downbeats are never reconstructed from those windows because
 * meter/bar-start semantics are not encoded there.
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
    const explicitBeats = increasingSeconds(insight.evidence?.beats_seconds);
    const explicitDownbeats = insight.evidence?.downbeats_seconds === undefined
      ? []
      : increasingSeconds(insight.evidence.downbeats_seconds);
    if (
      explicitBeats
      && explicitBeats.length >= 2
      && explicitDownbeats
      && downbeatsBelongToBeats(explicitDownbeats, explicitBeats)
      && insight.evidence?.pulse_coordinate_unit === "seconds"
    ) {
      return {
        versionId,
        beatsSeconds: explicitBeats,
        downbeatsSeconds: explicitDownbeats,
        provenance: (insight.provenance ?? {}) as Record<string, unknown>,
        source: "explicit_pulse",
      };
    }

    const recoveredBeats = beatsFromOneBeatWindows(
      insight.evidence?.onset_density_over_time,
    );
    if (recoveredBeats && recoveredBeats.length >= 2) {
      return {
        versionId,
        beatsSeconds: recoveredBeats,
        downbeatsSeconds: [],
        provenance: (insight.provenance ?? {}) as Record<string, unknown>,
        source: "beat_relative_windows",
      };
    }
  }

  return null;
}
