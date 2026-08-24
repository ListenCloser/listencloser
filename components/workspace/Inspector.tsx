"use client";

import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import { categorizeInsights, filterByCategory, insightStartSeconds } from "@/lib/inspector/insights";
import { isInspectorExposed, isExperimental } from "@/lib/inspector/capabilities";
import { deriveFindings } from "@/lib/inspector/findings";
import { formatTime } from "@/lib/format";
import AskPanel from "./AskPanel";
import type { MusicalSelection } from "@/lib/stores/workspace";
import type { Insight } from "@/lib/domain.types";
import type { TemporalFinding } from "@/lib/inspector/findings";

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

function stripClaimPrefix(claim: string): string {
  return claim.replace(/^[^:]+:\s*/, "");
}

function OverviewRow({ insights }: { insights: Insight[] }) {
  const keyInsight = insights.find((i) => i.kind === "key");
  const tempoInsight = insights.find((i) => i.kind === "audio_tempo") ?? insights.find((i) => i.kind === "tempo");
  const meterInsight = insights.find((i) => i.kind === "time_signature");

  const keyValue = keyInsight ? stripClaimPrefix(keyInsight.claim) : "\u2014";
  const tempoValue = tempoInsight ? stripClaimPrefix(tempoInsight.claim) : "\u2014";
  const meterValue = meterInsight ? stripClaimPrefix(meterInsight.claim) : "\u2014";

  return (
    <div className="inspector-overview-row">
      <div className="inspector-overview-item">
        <span className="inspector-overview-label">Key</span>
        <span className="inspector-overview-value">{keyValue}</span>
      </div>
      <div className="inspector-overview-item">
        <span className="inspector-overview-label">Tempo</span>
        <span className="inspector-overview-value">{tempoValue}</span>
      </div>
      <div className="inspector-overview-item">
        <span className="inspector-overview-label">Meter</span>
        <span className="inspector-overview-value">{meterValue}</span>
      </div>
    </div>
  );
}

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

function HarmonySection({
  insights,
  bpm,
  onSeek,
  setSelection,
}: {
  insights: Insight[];
  bpm: number;
  onSeek: (s: number) => void;
  setSelection: (s: MusicalSelection | null) => void;
}) {
  const chords = insights.filter((i) => i.kind === "chord" && insightStartSeconds(i, bpm) !== null);
  const romanNumerals = insights.filter((i) => i.kind === "roman_numeral" && insightStartSeconds(i, bpm) !== null);
  const harmonicFunctions = insights.filter((i) => i.kind === "harmonic_function" && insightStartSeconds(i, bpm) !== null);

  if (chords.length === 0 && romanNumerals.length === 0 && harmonicFunctions.length === 0) return null;

  return (
    <section className="inspector-section">
      <h3>Harmony</h3>
      <SequenceBlock title="Chords" insights={chords} bpm={bpm} onSeek={onSeek} setSelection={setSelection} dataKind="harmony" />
      <SequenceBlock title="Roman numerals" insights={romanNumerals} bpm={bpm} onSeek={onSeek} setSelection={setSelection} dataKind="harmony" />
      <SequenceBlock title="Function" insights={harmonicFunctions} bpm={bpm} onSeek={onSeek} setSelection={setSelection} dataKind="harmony" />
    </section>
  );
}

function RhythmSection({ insights }: { insights: Insight[] }) {
  const densityInsights = insights.filter((i) => i.kind === "rhythm_density");
  const restInsights = insights.filter((i) => i.kind === "rhythm_rests");

  if (densityInsights.length === 0 && restInsights.length === 0) return null;

  const observations: { label: string; time: number | null }[] = [];

  for (const insight of densityInsights) {
    const windows = (insight.evidence?.windows ?? []) as { start?: number; end?: number; density?: number }[];
    if (windows.length > 0) {
      const maxWindow = windows.reduce((max, w) => (w.density ?? 0) > (max.density ?? 0) ? w : max, windows[0]);
      if (maxWindow.density != null && maxWindow.start != null) {
        observations.push({
          label: `Peak note density at ${formatTime(maxWindow.start)}`,
          time: maxWindow.start,
        });
      }
    }
  }

  for (const insight of restInsights) {
    const rests = (insight.evidence?.rests ?? []) as { start?: number; end?: number; duration?: number }[];
    if (rests.length > 0) {
      const longestRest = rests.reduce((max, r) => (r.duration ?? 0) > (max.duration ?? 0) ? r : max, rests[0]);
      if (longestRest.start != null) {
        observations.push({
          label: `Rest at ${formatTime(longestRest.start)}`,
          time: longestRest.start,
        });
      }
    }
  }

  if (observations.length === 0) return null;

  return (
    <section className="inspector-section">
      <h3>Rhythm</h3>
      <div className="inspector-rhythm-observations">
        {observations.map((obs, i) => (
          <div key={i} className="inspector-rhythm-obs">
            {obs.label}
          </div>
        ))}
      </div>
    </section>
  );
}

function MelodySection({ insights }: { insights: Insight[] }) {
  if (!isExperimental("melody")) return null;
  const melodyInsights = insights.filter((i) => i.kind === "melody");
  if (melodyInsights.length === 0) return null;

  return (
    <section className="inspector-section">
      <h3>
        Melody
        <span className="inspector-experimental-badge">experimental</span>
      </h3>
      <div className="inspector-melody-items">
        {melodyInsights.slice(0, 6).map((item) => (
          <div key={item.id} className="inspector-melody-item">
            {item.claim}
          </div>
        ))}
      </div>
    </section>
  );
}

function FindingsSection({
  findings,
  onSeek,
  setSelection,
}: {
  findings: TemporalFinding[];
  onSeek: (seconds: number) => void;
  setSelection: (s: MusicalSelection | null) => void;
}) {
  if (findings.length === 0) return null;

  const handleClick = (finding: TemporalFinding) => {
    onSeek(finding.startSeconds);
    setSelection({
      timeRange: { start: finding.startSeconds, end: finding.endSeconds, domain: "performance" },
      provenance: { origin: null, timeExact: false, measureApproximate: true },
    });
  };

  return (
    <section className="inspector-section">
      <h3>Findings</h3>
      <div className="inspector-findings">
        {findings.map((finding) => (
          <button
            key={finding.id}
            type="button"
            className="inspector-finding"
            onClick={() => handleClick(finding)}
          >
            {finding.label}
          </button>
        ))}
      </div>
    </section>
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

  const exposed = (insights: Insight[]) =>
    confident(insights).filter((item) => isInspectorExposed(item.kind));

  const selExposed = exposed(selectionInsights);
  const wholeExposed = exposed(wholeWorkInsights);

  // Derive temporal findings from exposed insights
  const findings = deriveFindings(hasSelection ? selExposed : wholeExposed);

  if (hasSelection) {
    return (
      <div className="inspector-content">
        <section className="inspector-section">
          <h3>Selection</h3>
          <OverviewRow insights={selExposed} />
        </section>
        <HarmonySection insights={selExposed} bpm={bpm} onSeek={seek} setSelection={setSelection} />
        <RhythmSection insights={selExposed} />
        <MelodySection insights={selExposed} />
        <FindingsSection findings={findings} onSeek={seek} setSelection={setSelection} />
        {selExposed.length === 0 && (
          <p className="inspector-empty">No analysis available for this selection.</p>
        )}
      </div>
    );
  }

  return (
    <div className="inspector-content">
      <section className="inspector-section">
        <h3>Analysis</h3>
        <OverviewRow insights={wholeExposed} />
      </section>
      <HarmonySection insights={wholeExposed} bpm={bpm} onSeek={seek} setSelection={setSelection} />
      <RhythmSection insights={wholeExposed} />
      <MelodySection insights={wholeExposed} />
      <FindingsSection findings={findings} onSeek={seek} setSelection={setSelection} />
    </div>
  );
}
