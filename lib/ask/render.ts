import { formatTime } from "@/lib/format";
import type { Insight } from "@/lib/domain.types";
import type { MusicalSelection } from "@/lib/stores/workspace";
import type { PlaybackSource } from "@/lib/stores/transport";
import { representationById } from "@/lib/representations";
import { insightStartSeconds } from "@/lib/inspector/insights";
import { composeNoteSelection, timeRangeFromMeasures, type NoteLike } from "@/lib/selection";
import type { AskAction, AskReference } from "./types";

/**
 * Compact user-facing label for the current Ask context: "Whole piece", a
 * selection's time range, or its measure range (score) — never both at once.
 */
export function describeAskContext(selection: MusicalSelection | null): string {
  if (selection?.measureRange) {
    return `Measures ${selection.measureRange.start}–${selection.measureRange.end}`;
  }
  if (selection?.timeRange) {
    return formatTimeRange(selection.timeRange.start, selection.timeRange.end);
  }
  return "Whole piece";
}

/**
 * The time domain a playback source lives in. The Score rendition plays in
 * notation time; everything else (original, transcription, derived audio)
 * plays in performance time.
 */
export function playbackSourceDomain(
  source: PlaybackSource | null,
): "performance" | "notation" | null {
  if (!source) return null;
  return source.role === "score" ? "notation" : "performance";
}

/** True when the reference/action domain matches the active source's domain. */
export function canSeekInDomain(
  domain: "performance" | "notation",
  source: PlaybackSource | null,
): boolean {
  return playbackSourceDomain(source) === domain;
}

export function formatTimeRange(start: number, end?: number): string {
  return `${formatTime(start)}–${formatTime(end ?? start)}`;
}

/**
 * Render a reference's compact evidence label. `resolveInsight` returns the
 * claim/label for an insight id, or null when it cannot be resolved — the
 * caller never guesses a label.
 */
export function formatReference(
  ref: AskReference,
  resolveInsight: (id: string) => string | null,
): string {
  switch (ref.type) {
    case "time":
      return formatTimeRange(ref.start, ref.end);
    case "measure":
      return ref.end !== undefined && ref.end !== ref.start
        ? `Measures ${ref.start}–${ref.end}`
        : `Measure ${ref.start}`;
    case "notes":
      return `Notes (${ref.ids.length})`;
    case "insight":
      return resolveInsight(ref.id) ?? "Insight";
  }
}

/**
 * Validate a suggested action against the active playback source and the
 * canonical representation registry. Returns `{ allowed: true }` when safe to
 * execute, otherwise a user-facing reason. Actions are never executed without
 * an explicit user click, and domain mismatches never silently cross
 * performance ↔ notation.
 */
export function validateAction(
  action: AskAction,
  activeSource: PlaybackSource | null,
): { allowed: boolean; reason?: string } {
  switch (action.type) {
    case "seek":
    case "loop":
      if (!canSeekInDomain(action.domain, activeSource)) {
        return {
          allowed: false,
          reason: "This matches a different timeline than the active source.",
        };
      }
      return { allowed: true };
    case "show_representation":
      if (!representationById(action.representationId)) {
        return { allowed: false, reason: "That view isn't available." };
      }
      return { allowed: true };
  }
}

/**
 * Resolve what clicking an evidence reference should do, given the current
 * workspace. Returns a block reason (never fabricating) or a safe action:
 *   - time    → seek ONLY when the reference domain matches the active source.
 *   - measure → open the Score; optionally seek when a trustworthy measure→time
 *               mapping exists (score measure data present) and the reference
 *               domain matches the active source.
 *   - notes   → open Piano Roll and select the referenced notes when they
 *               resolve cleanly, otherwise just open Piano Roll.
 *   - insight → seek to a defensible start; never default unresolved to 0.
 */
export type ReferenceResolution =
  | { kind: "seek"; seconds: number }
  | { kind: "open-representation"; representationId: "score" | "piano_roll" }
  | { kind: "select-notes"; representationId: "piano_roll"; ids: string[] }
  | { kind: "blocked"; reason: string };

export type ReferenceContext = {
  activeSource: PlaybackSource | null;
  insights: Insight[];
  bpm: number;
  measureStarts: number[];
  scoreDuration?: number | null;
  notes: NoteLike[];
};

export function resolveReference(
  ref: AskReference,
  ctx: ReferenceContext,
): ReferenceResolution {
  switch (ref.type) {
    case "time": {
      if (!canSeekInDomain(ref.domain, ctx.activeSource)) {
        return { kind: "blocked", reason: "This reference uses a different timeline than the active source." };
      }
      return { kind: "seek", seconds: ref.start };
    }
    case "measure": {
      if (ctx.measureStarts.length > 0 && canSeekInDomain("notation", ctx.activeSource)) {
        const range = timeRangeFromMeasures(ref.start, ref.end ?? ref.start, ctx.measureStarts, ctx.scoreDuration);
        if (range) {
          return { kind: "seek", seconds: range.start };
        }
      }
      return { kind: "open-representation", representationId: "score" };
    }
    case "notes": {
      if (ref.ids.length > 0 && composeNoteSelection(ctx.notes, ref.ids)) {
        return { kind: "select-notes", representationId: "piano_roll", ids: ref.ids };
      }
      return { kind: "open-representation", representationId: "piano_roll" };
    }
    case "insight": {
      const insight = ctx.insights.find((item) => item.id === ref.id);
      if (!insight) {
        return { kind: "blocked", reason: "This insight is no longer available for this work." };
      }
      const seconds = insightStartSeconds(insight, ctx.bpm);
      if (seconds === null) {
        return { kind: "blocked", reason: "This insight has no reliable location to jump to." };
      }
      return { kind: "seek", seconds };
    }
  }
}