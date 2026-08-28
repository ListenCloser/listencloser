import type { BreakdownFinding } from "@/lib/inspector/breakdown";
import { isAskExposed } from "@/lib/inspector/capabilities";
import type { RepresentationId } from "@/lib/representations";
import type { PlaybackSource } from "@/lib/stores/transport";
import type { RepresentationKind } from "@/lib/stores/workspace";

export type LiveBreakdownAction =
  | { type: "loop" }
  | { type: "show"; representationId: RepresentationId }
  | { type: "ask" };

export type BreakdownActionContext = {
  activeSourceRole: PlaybackSource["role"] | null;
  durationSeconds: number;
  availableRepresentationKinds: readonly RepresentationKind[];
  activeRepresentation: RepresentationId | null;
  activeWorkId: string | null;
  sourceInsightKind: string | null;
};

function preferredRepresentationId(finding: BreakdownFinding): RepresentationId {
  return finding.primaryRepresentation === "waveform" ? "listen" : "piano_roll";
}

function hasLoopablePerformanceSpan(
  finding: BreakdownFinding,
  context: BreakdownActionContext,
): boolean {
  if (!context.activeSourceRole || context.activeSourceRole === "score") return false;
  if (!Number.isFinite(context.durationSeconds) || context.durationSeconds <= 0) return false;
  if (!Number.isFinite(finding.startSeconds) || !Number.isFinite(finding.endSeconds)) return false;
  if (finding.startSeconds < 0 || finding.endSeconds <= finding.startSeconds) return false;
  return finding.endSeconds <= context.durationSeconds;
}

/**
 * Resolve the actions the live workspace can truthfully execute for a finding.
 *
 * The pure ranking adapter deliberately guarantees only Focus. This resolver
 * composes that evidence with live playback/representation/workspace state.
 * It never invents a fallback representation or exposes an Ask path for a
 * capability the backend registry marks `ask: false`.
 */
export function resolveBreakdownFindingActions(
  finding: BreakdownFinding,
  context: BreakdownActionContext,
): LiveBreakdownAction[] {
  const actions: LiveBreakdownAction[] = [];

  if (hasLoopablePerformanceSpan(finding, context)) {
    actions.push({ type: "loop" });
  }

  const representationId = preferredRepresentationId(finding);
  if (
    context.availableRepresentationKinds.includes(finding.primaryRepresentation)
    && context.activeRepresentation !== representationId
  ) {
    actions.push({ type: "show", representationId });
  }

  if (
    context.activeWorkId
    && context.sourceInsightKind
    && isAskExposed(context.sourceInsightKind)
  ) {
    actions.push({ type: "ask" });
  }

  return actions;
}
