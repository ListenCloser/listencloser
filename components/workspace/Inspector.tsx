"use client";

import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import { categorizeInsights, filterByCategory, insightStartSeconds } from "@/lib/inspector/insights";
import { formatTime } from "@/lib/format";
import AskPanel from "./AskPanel";
import type { MusicalSelection } from "@/lib/stores/workspace";
import type { Insight } from "@/lib/domain.types";

function describeSelection(selection: MusicalSelection): string {
  if (selection.measureRange) {
    const { start, end } = selection.measureRange;
    return `Measures ${start}\u2013${end}`;
  }
  if (selection.timeRange) {
    return `${formatTime(selection.timeRange.start)}\u2013${formatTime(selection.timeRange.end)}`;
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
  return null;
}

function renderFact(label: string, value: string, confidence?: string) {
  return (
    <div key={label} className="inspector-fact">
      <strong className="inspector-fact-value">{value}</strong>
      <span className="inspector-fact-label">{label}{confidence ? ` \u00b7 ${confidence}` : ""}</span>
    </div>
  );
}

/** Compact arrow-separated sequence for chords, RN, and harmonic function. */
function SequenceBlock({
  title,
  insights,
  bpm,
  onSeek,
  setSelection,
  dataKind,
}: {
  title: string;
  insights: Insight[];
  bpm: number;
  onSeek: (s: number) => void;
  setSelection: (s: MusicalSelection | null) => void;
  dataKind?: string;
}) {
  if (insights.length === 0) return null;

  const handleClick = (item: Insight) => {
    const seconds = insightStartSeconds(item, bpm);
    if (seconds !== null) onSeek(seconds);
    if (item.span.start_seconds != null && item.span.end_seconds != null) {
      setSelection({
        timeRange: { start: item.span.start_seconds, end: item.span.end_seconds, domain: "notation" },
        provenance: { origin: "score", timeExact: false, measureApproximate: true },
      });
    }
  };

  return (
    <div className="inspector-block" data-kind={dataKind}>
      <h4>{title}</h4>
      <div className="inspector-sequence">
        {insights.map((item, i) => (
          <span key={item.id} className="inspector-sequence-items">
            <button
              type="button"
              className="inspector-seq-btn"
              onClick={() => handleClick(item)}
              title={item.claim}
            >
              {item.claim}
            </button>
            {i < insights.length - 1 && <span className="inspector-seq-arrow"> \u2192 </span>}
          </span>
        ))}
      </div>
    </div>
  );
}

function renderInsightList(
  insights: Insight[],
  onSeek: (seconds: number) => void,
  bpm: number,
  setSelection: (selection: MusicalSelection | null) => void,
) {
  if (insights.length === 0) return null;
  const seekable = (item: Insight) => {
    const seconds = insightStartSeconds(item, bpm);
    return seconds !== null;
  };

  const sections = insights.filter((item) => item.kind === "section" && seekable(item)).slice(0, 12);
  const chords = insights.filter((item) => item.kind === "chord" && seekable(item));
  const romanNumerals = insights.filter((item) => item.kind === "roman_numeral" && seekable(item));
  const harmonicFunctions = insights.filter((item) => item.kind === "harmonic_function" && seekable(item));
  const observations = insights.filter(
    (item) => !["key", "tempo", "time_signature", "audio_tempo", "chord", "section", "roman_numeral", "harmonic_function"].includes(item.kind),
  );

  return (
    <>
      {sections.length > 0 && (
        <div className="inspector-block">
          <h4>Form</h4>
          <div className="rn-chips">
            {sections.map((item) => (
              <button type="button" className="rn-chip" key={item.id} onClick={() => {
                const s = insightStartSeconds(item, bpm);
                if (s !== null) onSeek(s);
              }}>
                {item.claim}
              </button>
            ))}
          </div>
        </div>
      )}
      <SequenceBlock
        title="Chords"
        insights={chords}
        bpm={bpm}
        onSeek={onSeek}
        setSelection={setSelection}
        dataKind="harmony"
      />
      <SequenceBlock
        title="Roman Numerals"
        insights={romanNumerals}
        bpm={bpm}
        onSeek={onSeek}
        setSelection={setSelection}
        dataKind="harmony"
      />
      <SequenceBlock
        title="Harmonic Function"
        insights={harmonicFunctions}
        bpm={bpm}
        onSeek={onSeek}
        setSelection={setSelection}
        dataKind="harmony"
      />
      {observations.length > 0 && (
        <div className="inspector-block">
          <h4>Observations</h4>
          {observations.map((item) => {
            const seconds = insightStartSeconds(item, bpm);
            if (seconds === null) {
              return (
                <div className="inspector-observation-static" key={item.id}>
                  <span>{item.claim}</span>
                </div>
              );
            }
            return (
              <button type="button" className="inspector-observation" key={item.id} onClick={() => onSeek(seconds)}>
                <span>{item.claim}</span>
              </button>
            );
          })}
        </div>
      )}
    </>
  );
}

export default function InspectorPanel() {
  const { workspace, setInspectorMode, setSelection } = useWorkspace();
  const { seek } = useTransport();
  const { timeline } = useTimeline();
  const mode = workspace.inspectorMode;

  return (
    <aside className="inspector">
      <header className="inspector-header">
        <nav className="inspector-mode-tabs" role="tablist" aria-label="Inspector mode">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "analysis"}
            className={mode === "analysis" ? "active" : ""}
            onClick={() => setInspectorMode("analysis")}
          >
            Analysis
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "ask"}
            className={mode === "ask" ? "active" : ""}
            onClick={() => setInspectorMode("ask")}
          >
            Ask
          </button>
        </nav>
        {mode === "analysis" && (
          <InsightScopeHeader scope={workspace.selection ? "selection" : "whole-work"} selection={workspace.selection} />
        )}
      </header>

      {mode === "analysis"
        ? <AnalysisContent workspace={workspace} seek={seek} bpm={timeline.bpm} setSelection={setSelection} />
        : <div className="inspector-content ask-content"><AskPanel /></div>}
    </aside>
  );
}

function AnalysisContent({
  workspace,
  seek,
  bpm,
  setSelection,
}: {
  workspace: ReturnType<typeof useWorkspace>["workspace"];
  seek: (seconds: number) => void;
  bpm: number;
  setSelection: (selection: MusicalSelection | null) => void;
}) {
  const hasSelection = workspace.selection != null;

  const categorized = categorizeInsights(workspace.insights, workspace.selection, bpm);
  const selectionInsights = filterByCategory(categorized, "selection");
  const wholeWorkInsights = filterByCategory(categorized, "whole-work");

  const confident = (insights: Insight[]) =>
    insights.filter((item) => item.confidence == null || item.confidence >= 0.5);

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

  return (
    <div className="inspector-content">
      {!hasSelection && (
        <section className="inspector-section">
          <h3>Overview</h3>
          <div className="inspector-facts">
            {renderFact("Key", claimValue(keyFact(confWholeWork)))}
            {renderFact("Tempo", claimValue(tempoFact(confWholeWork)))}
            {renderFact("Meter", claimValue(meterFact(confWholeWork)))}
          </div>
        </section>
      )}

      {hasSelection && confSelection.length > 0 && (
        <section className="inspector-section">
          <h3>Selection findings</h3>
          {renderInsightList(confSelection, seek, bpm, setSelection)}
        </section>
      )}

      {hasSelection && confSelection.length === 0 && (
        <section className="inspector-section">
          <h3>Selection</h3>
          <p className="inspector-empty">No specific analysis is available for this selection yet.</p>
        </section>
      )}

      <section className="inspector-section">
        <h3>{hasSelection ? "Whole-piece context" : "Findings"}</h3>
        {renderInsightList(confWholeWork, seek, bpm, setSelection)}
        {confWholeWork.length === 0 && <p className="inspector-empty">No analysis findings yet.</p>}
      </section>
    </div>
  );
}
