"use client";

import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import { categorizeInsights, filterByCategory } from "@/lib/inspector/insights";
import { formatTime } from "@/lib/format";
import type { MusicalSelection } from "@/lib/stores/workspace";
import type { Insight } from "@/lib/domain.types";

function describeSelection(selection: MusicalSelection): string {
  if (selection.measureRange) {
    const { start, end } = selection.measureRange;
    return `Measures ${start}–${end}`;
  }
  if (selection.timeRange) {
    return `${formatTime(selection.timeRange.start)}–${formatTime(selection.timeRange.end)}`;
  }
  return "";
}

function InsightScopeHeader({ scope, selection }: { scope: "selection" | "whole-work"; selection: MusicalSelection | null }) {
  if (scope === "selection" && selection) {
    return (
      <div className="inspector-scope">
        <span className="inspector-scope-label">Selection</span>
        <span className="inspector-scope-value">{describeSelection(selection)}</span>
      </div>
    );
  }
  return (
    <div className="inspector-scope">
      <span className="inspector-scope-label">Whole piece</span>
    </div>
  );
}

function renderFact(label: string, value: string) {
  return (
    <div key={label} className="inspector-fact">
      <span className="inspector-fact-label">{label}</span>
      <strong className="inspector-fact-value">{value}</strong>
    </div>
  );
}

function renderInsightList(
  insights: Insight[],
  onSeek: (seconds: number) => void,
) {
  if (insights.length === 0) return null;
  const chords = insights.filter((item) => item.kind === "chord").slice(0, 12);
  const sections = insights.filter((item) => item.kind === "section").slice(0, 12);
  const observations = insights.filter(
    (item) => !["key", "tempo", "time_signature", "audio_tempo", "chord", "section"].includes(item.kind),
  );
  const goTo = (item: Insight) =>
    onSeek(item.span.start_seconds ?? 0);

  return (
    <>
      {sections.length > 0 && (
        <div className="inspector-block">
          <h4>Form</h4>
          <div className="rn-chips">
            {sections.map((item) => (
              <button type="button" className="rn-chip" key={item.id} onClick={() => goTo(item)}>
                {item.claim}
              </button>
            ))}
          </div>
        </div>
      )}
      {chords.length > 0 && (
        <div className="inspector-block">
          <h4>Harmonic path</h4>
          <div className="rn-chips">
            {chords.map((item) => (
              <button type="button" className="rn-chip" key={item.id} onClick={() => goTo(item)}>
                {item.claim}
              </button>
            ))}
          </div>
        </div>
      )}
      {observations.length > 0 && (
        <div className="inspector-block">
          <h4>Observations</h4>
          {observations.map((item) => (
            <button type="button" className="inspector-observation" key={item.id} onClick={() => goTo(item)}>
              <span>{item.claim}</span>
            </button>
          ))}
        </div>
      )}
    </>
  );
}

export default function InspectorPanel() {
  const { workspace } = useWorkspace();
  const { transport, seek } = useTransport();
  const { timeline } = useTimeline();
  if (workspace.inspectorMode !== "analysis") {
    return null;
  }
  const hasSelection = workspace.selection != null;

  const categorized = categorizeInsights(workspace.insights, workspace.selection, timeline.bpm);
  const selectionInsights = filterByCategory(categorized, "selection");
  const wholeWorkInsights = filterByCategory(categorized, "whole-work");

  const confident = (insights: Insight[]) =>
    insights.filter((item) => item.confidence != null && item.confidence >= 0.5);

  const confSelection = confident(selectionInsights);
  const confWholeWork = confident(wholeWorkInsights);

  const keyFact = (insights: Insight[]) =>
    insights.find((item) => item.kind === "key");
  const tempoFact = (insights: Insight[]) =>
    insights.find((item) => item.kind === "audio_tempo") ?? insights.find((item) => item.kind === "tempo");
  const meterFact = (insights: Insight[]) =>
    insights.find((item) => item.kind === "time_signature");

  const claimValue = (item?: Insight) =>
    item ? item.claim.replace(/^[^:]+:\s*/, "") : "Not confidently detected";

  const filteredCount = categorized.filter((c) => c.category === "unrelated").length;

  return (
    <aside className="inspector">
      <header className="inspector-header">
        <h2>Analysis</h2>
        <InsightScopeHeader scope={hasSelection ? "selection" : "whole-work"} selection={workspace.selection} />
      </header>

      <div className="inspector-content">
        {!hasSelection && (
          <section className="inspector-section">
            <h3>Overview</h3>
            <div className="inspector-facts">
              {renderFact("Key", claimValue(keyFact(confWholeWork)))}
              {renderFact("Tempo", claimValue(tempoFact(confWholeWork)))}
              {renderFact("Time signature", claimValue(meterFact(confWholeWork)))}
            </div>
          </section>
        )}

        {hasSelection && confSelection.length > 0 && (
          <section className="inspector-section">
            <h3>Selection findings</h3>
            {renderInsightList(confSelection, seek)}
          </section>
        )}

        {hasSelection && confSelection.length === 0 && (
          <section className="inspector-section">
            <h3>Selection</h3>
            <p className="inspector-empty">No specific analysis is available for this selection yet.</p>
          </section>
        )}

        <section className="inspector-section">
          <h3>Whole-piece findings</h3>
          {renderInsightList(confWholeWork, seek)}
          {confWholeWork.length === 0 && <p className="inspector-empty">No confident whole-piece findings.</p>}
        </section>

        {filteredCount > 0 && (
          <p className="inspector-filtered-notice">
            Some uncertain findings were omitted.
          </p>
        )}
      </div>
    </aside>
  );
}
