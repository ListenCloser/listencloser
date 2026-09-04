"use client";

import { resolveBreakdownFindingActions, type LiveBreakdownAction } from "@/lib/inspector/breakdown-actions";
import type { BreakdownFinding } from "@/lib/inspector/breakdown";
import { requestWorkspaceOrientation } from "@/lib/inspector/orientation";
import { formatTime } from "@/lib/format";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";
import styles from "./BreakdownFindingCard.module.css";

type VisibleFindingAction = Exclude<LiveBreakdownAction, { type: "ask" }>;

function inspectLabel(action: Extract<VisibleFindingAction, { type: "show" }>): string {
  return action.representationId === "listen" ? "Inspect waveform" : "Inspect piano roll";
}

export default function BreakdownFindingCard({ finding }: { finding: BreakdownFinding }) {
  const {
    workspace,
    setSelection,
    setActiveRepresentation,
  } = useWorkspace();
  const { transport, play, seek, setLoop, toggleLoop } = useTransport();
  const supportInsightKinds = finding.supportInsightIds.map(
    (supportId) => workspace.insights.find((insight) => insight.id === supportId)?.kind ?? null,
  );
  const actions = resolveBreakdownFindingActions(finding, {
    activeSourceRole: transport.activeSource?.role ?? null,
    durationSeconds: transport.duration,
    availableRepresentationKinds: workspace.representations.map((entry) => entry.kind),
    activeRepresentation: workspace.activeRepresentation,
    activeWorkId: workspace.activeWorkId,
    supportInsightKinds,
  });
  // Ask already consumes the shared workspace selection. Repeating Ask on every
  // finding turns a concise musical observation into a toolbar. Select/focus the
  // passage here; the stable Inspector Ask tab is the single path into Ask.
  const visibleActions = actions.filter(
    (action): action is VisibleFindingAction => action.type !== "ask",
  );

  const selectFinding = () => {
    setSelection({
      timeRange: { start: finding.startSeconds, end: finding.endSeconds, domain: "performance" },
      provenance: { origin: null, timeExact: false, measureApproximate: true },
    });
  };

  const focusFinding = () => {
    seek(finding.startSeconds);
    selectFinding();
    requestWorkspaceOrientation();
  };

  const handleAction = (action: VisibleFindingAction) => {
    switch (action.type) {
      case "loop":
        seek(finding.startSeconds);
        selectFinding();
        setLoop(finding.startSeconds, finding.endSeconds);
        if (!transport.loopEnabled) toggleLoop();
        play();
        break;
      case "show":
        focusFinding();
        setActiveRepresentation(action.representationId);
        break;
    }
  };

  return (
    <article className={`inspector-breakdown-finding ${styles.finding}`}>
      <button
        type="button"
        className="inspector-breakdown-focus"
        onClick={focusFinding}
        aria-label={`Focus ${formatTime(finding.startSeconds)} to ${formatTime(finding.endSeconds)}: ${finding.headline}`}
      >
        <span className="inspector-breakdown-time">{formatTime(finding.startSeconds)}–{formatTime(finding.endSeconds)}</span>
        <span className="inspector-breakdown-headline">{finding.headline}</span>
        {finding.evidenceSummary && (
          <span className="inspector-breakdown-support">{finding.evidenceSummary}</span>
        )}
        {finding.maturity === "experimental" && (
          <span className="inspector-breakdown-maturity">Experimental melody evidence</span>
        )}
      </button>

      {visibleActions.length > 0 && (
        <div className="inspector-breakdown-actions" aria-label="Finding actions">
          {visibleActions.map((action) => {
            const label = action.type === "loop" ? "Hear" : "Inspect";
            const ariaLabel = action.type === "loop"
              ? `Hear ${formatTime(finding.startSeconds)} to ${formatTime(finding.endSeconds)}`
              : inspectLabel(action);
            return (
              <button
                type="button"
                className="inspector-breakdown-action"
                key={action.type}
                onClick={() => handleAction(action)}
                aria-label={ariaLabel}
                title={ariaLabel}
              >
                {label}
              </button>
            );
          })}
        </div>
      )}
    </article>
  );
}
