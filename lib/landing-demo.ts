export const LANDING_DEMO_SCHEMA_VERSION = 1 as const;

export type LandingDemoWindow = {
  startSeconds: number;
  endSeconds: number;
};

export type LandingDemoSource = {
  assetPath: string;
  sha256: string;
  provenance: string;
  publicUseApproved: boolean;
  durationSeconds: number;
};

export type LandingDemoWaveformBin = {
  min: number;
  max: number;
};

export type LandingDemoNote = {
  id: string;
  pitch: number;
  startSeconds: number;
  endSeconds: number;
  velocity: number | null;
};

export type LandingDemoScore = {
  musicxmlPath: string;
  sha256: string;
  measureStartsSeconds: number[];
};

export type LandingDemoEvidenceSpan = {
  id: string;
  kind: string;
  label: string;
  provenance: string;
  startSeconds: number;
  endSeconds: number;
};

export type LandingDemoManifest = {
  schemaVersion: typeof LANDING_DEMO_SCHEMA_VERSION;
  source: LandingDemoSource;
  window: LandingDemoWindow;
  waveform: {
    bins: LandingDemoWaveformBin[];
  };
  notes: LandingDemoNote[];
  score: LandingDemoScore;
  evidence: LandingDemoEvidenceSpan[];
};

export type LandingDemoValidationOptions = {
  requirePublicUseApproval?: boolean;
};

const SHA256_PATTERN = /^[a-f0-9]{64}$/i;
const FORBIDDEN_TEMPORAL_GEOMETRY_KEYS = new Set([
  "x",
  "x1",
  "x2",
  "xPercent",
  "leftPercent",
  "widthPercent",
]);

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function overlapsWindow(startSeconds: number, endSeconds: number, window: LandingDemoWindow): boolean {
  return endSeconds > window.startSeconds && startSeconds < window.endSeconds;
}

function findForbiddenTemporalGeometry(value: unknown, path = "manifest"): string[] {
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => findForbiddenTemporalGeometry(item, `${path}[${index}]`));
  }
  if (value === null || typeof value !== "object") return [];

  return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) => {
    const errors = FORBIDDEN_TEMPORAL_GEOMETRY_KEYS.has(key)
      ? [`${path}.${key} must not be stored; derive temporal geometry from seconds at render time`]
      : [];
    return errors.concat(findForbiddenTemporalGeometry(child, `${path}.${key}`));
  });
}

export function projectLandingDemoTime(seconds: number, window: LandingDemoWindow): number {
  if (!isFiniteNumber(seconds)) throw new Error("Landing demo time must be finite");
  if (!isFiniteNumber(window.startSeconds) || !isFiniteNumber(window.endSeconds) || window.endSeconds <= window.startSeconds) {
    throw new Error("Landing demo window must have finite, increasing bounds");
  }
  if (seconds < window.startSeconds || seconds > window.endSeconds) {
    throw new Error(`Landing demo time ${seconds} is outside [${window.startSeconds}, ${window.endSeconds}]`);
  }
  return (seconds - window.startSeconds) / (window.endSeconds - window.startSeconds);
}

export function projectLandingDemoRange(
  startSeconds: number,
  endSeconds: number,
  window: LandingDemoWindow,
): { start: number; end: number } | null {
  if (!isFiniteNumber(startSeconds) || !isFiniteNumber(endSeconds) || endSeconds <= startSeconds) {
    throw new Error("Landing demo range must have finite, increasing bounds");
  }
  if (!overlapsWindow(startSeconds, endSeconds, window)) return null;

  const clippedStart = Math.max(startSeconds, window.startSeconds);
  const clippedEnd = Math.min(endSeconds, window.endSeconds);
  return {
    start: projectLandingDemoTime(clippedStart, window),
    end: projectLandingDemoTime(clippedEnd, window),
  };
}

export function validateLandingDemoManifest(
  manifest: LandingDemoManifest,
  options: LandingDemoValidationOptions = {},
): string[] {
  const errors = findForbiddenTemporalGeometry(manifest);
  const { source, window } = manifest;

  if (manifest.schemaVersion !== LANDING_DEMO_SCHEMA_VERSION) {
    errors.push(`schemaVersion must be ${LANDING_DEMO_SCHEMA_VERSION}`);
  }

  if (!source.assetPath.trim()) errors.push("source.assetPath is required");
  if (!SHA256_PATTERN.test(source.sha256)) errors.push("source.sha256 must be a SHA-256 hex digest");
  if (!source.provenance.trim()) errors.push("source.provenance is required");
  if (!isFiniteNumber(source.durationSeconds) || source.durationSeconds <= 0) {
    errors.push("source.durationSeconds must be positive and finite");
  }
  if (options.requirePublicUseApproval && source.publicUseApproved !== true) {
    errors.push("source.publicUseApproved must be true before the manifest can ship on the public landing page");
  }

  if (!isFiniteNumber(window.startSeconds) || !isFiniteNumber(window.endSeconds) || window.endSeconds <= window.startSeconds) {
    errors.push("window must have finite, increasing bounds");
  } else if (
    isFiniteNumber(source.durationSeconds)
    && (window.startSeconds < 0 || window.endSeconds > source.durationSeconds)
  ) {
    errors.push("window must stay inside source.durationSeconds");
  }

  if (manifest.waveform.bins.length < 2) {
    errors.push("waveform.bins must contain at least two source-derived min/max bins");
  }
  manifest.waveform.bins.forEach((bin, index) => {
    if (!isFiniteNumber(bin.min) || !isFiniteNumber(bin.max)) {
      errors.push(`waveform.bins[${index}] must contain finite min/max values`);
      return;
    }
    if (bin.min < -1 || bin.max > 1 || bin.min > bin.max) {
      errors.push(`waveform.bins[${index}] must satisfy -1 <= min <= max <= 1`);
    }
  });

  const noteIds = new Set<string>();
  let visibleNoteCount = 0;
  manifest.notes.forEach((note, index) => {
    if (!note.id.trim()) errors.push(`notes[${index}].id is required`);
    if (noteIds.has(note.id)) errors.push(`notes[${index}].id must be unique`);
    noteIds.add(note.id);
    if (!Number.isInteger(note.pitch) || note.pitch < 0 || note.pitch > 127) {
      errors.push(`notes[${index}].pitch must be an integer MIDI pitch from 0 to 127`);
    }
    if (!isFiniteNumber(note.startSeconds) || !isFiniteNumber(note.endSeconds) || note.endSeconds <= note.startSeconds) {
      errors.push(`notes[${index}] must have finite startSeconds < endSeconds`);
    } else {
      if (note.startSeconds < 0 || note.endSeconds > source.durationSeconds) {
        errors.push(`notes[${index}] must stay inside source.durationSeconds`);
      }
      if (overlapsWindow(note.startSeconds, note.endSeconds, window)) visibleNoteCount += 1;
    }
    if (note.velocity !== null && (!Number.isInteger(note.velocity) || note.velocity < 0 || note.velocity > 127)) {
      errors.push(`notes[${index}].velocity must be null or an integer from 0 to 127`);
    }
  });
  if (visibleNoteCount === 0) errors.push("notes must contain at least one event overlapping the landing window");

  if (!manifest.score.musicxmlPath.trim()) errors.push("score.musicxmlPath is required");
  if (!SHA256_PATTERN.test(manifest.score.sha256)) errors.push("score.sha256 must be a SHA-256 hex digest");
  if (manifest.score.measureStartsSeconds.length === 0) {
    errors.push("score.measureStartsSeconds must contain at least one aligned measure boundary");
  }
  let previousMeasureStart = -Infinity;
  let scoreReachesLandingWindow = false;
  manifest.score.measureStartsSeconds.forEach((startSeconds, index) => {
    if (!isFiniteNumber(startSeconds) || startSeconds < 0 || startSeconds > source.durationSeconds) {
      errors.push(`score.measureStartsSeconds[${index}] must stay inside source.durationSeconds`);
      return;
    }
    if (startSeconds <= previousMeasureStart) {
      errors.push("score.measureStartsSeconds must be strictly increasing");
    }
    previousMeasureStart = startSeconds;
    if (startSeconds <= window.endSeconds) scoreReachesLandingWindow = true;
  });
  if (!scoreReachesLandingWindow) {
    errors.push("score must contain an aligned measure boundary at or before the landing window end");
  }

  if (manifest.evidence.length === 0) {
    errors.push("evidence must contain at least one supported source-time span");
  }
  const evidenceIds = new Set<string>();
  manifest.evidence.forEach((span, index) => {
    if (!span.id.trim()) errors.push(`evidence[${index}].id is required`);
    if (evidenceIds.has(span.id)) errors.push(`evidence[${index}].id must be unique`);
    evidenceIds.add(span.id);
    if (!span.kind.trim()) errors.push(`evidence[${index}].kind is required`);
    if (!span.label.trim()) errors.push(`evidence[${index}].label is required`);
    if (!span.provenance.trim()) errors.push(`evidence[${index}].provenance is required`);
    if (!isFiniteNumber(span.startSeconds) || !isFiniteNumber(span.endSeconds) || span.endSeconds <= span.startSeconds) {
      errors.push(`evidence[${index}] must have finite startSeconds < endSeconds`);
      return;
    }
    if (span.startSeconds < 0 || span.endSeconds > source.durationSeconds) {
      errors.push(`evidence[${index}] must stay inside source.durationSeconds`);
    }
    if (!overlapsWindow(span.startSeconds, span.endSeconds, window)) {
      errors.push(`evidence[${index}] must overlap the landing window`);
    }
  });

  return errors;
}
