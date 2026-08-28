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

function stripClaimPrefix(claim: string): string {
  return claim.replace(/^[^:]+:\s*/, "");
}

function OverviewRow({ insights }: { insights: Insight[] }) {
  const keyInsight = insights.find((item) => item.kind === "key");
  const tempoInsight = insights.find((item) => item.kind === "audio_tempo") ?? insights.find((item) => item.kind === "tempo");
  const meterInsight = insights.find((item) => item.kind === "time_signature");

  const items = [
    ["Key", keyInsight ? stripClaimPrefix(keyInsight.claim) : "\u2014"],
    ["Tempo", tempoInsight ? stripClaimPrefix(tempoInsight.claim) : "\u2014"],
    ["Meter", meterInsight ? stripClaimPrefix(meterInsight.claim) : "\u2014"],
  ];

  return (
    <div className="inspector-overview-row" aria-label="Analysis overview">
      {items.map(([label, value]) => (
        <div className="inspector-overview-item" key={label}>
          <span className="inspector-overview-label">{label}</span>
          <span className="inspector-overview-value">{value}</span>
        </div>
      ))}
    </div>
  );
}

function SequenceBlock({
  title,
  insights,
  bpm,
  onSeek,
  setSelection,
}: {
  title: string;
  insights: Insight[];
  bpm: number;
  onSeek: (seconds: number) => void;
  setSelection: (selection: MusicalSelection | null) => void;
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
    <div className="inspector-block">
      <h4>{title}</h4>
      <div className="inspector-sequence">
        {insights.map((item) => (
          <button
            type="button"
            className="inspector-seq-btn"
            key={item.id}
            onClick={() => handleClick(item)}
            title={item.claim}
          >
            {item.claim}
          </button>
        ))}
      </div>
    </div>
  );
}

function HarmonyEvidence({
  insights,
  bpm,
  onSeek,
  setSelection,
}: {
  insights: Insight[];
  bpm: number;
  onSeek: (seconds: number) => void;
  setSelection: (selection: MusicalSelection | null) => void;
}) {
  const chords = insights.filter((item) => item.kind === "chord" && insightStartSeconds(item, bpm) !== null);
  const romanNumerals = insights.filter((item) => item.kind === "roman_numeral" && insightStartSeconds(item, bpm) !== null);
  const harmonicFunctions = insights.filter((item) => item.kind === "harmonic_function" && insightStartSeconds(item, bpm) !== null);

  if (chords.length === 0 && romanNumerals.length === 0 && harmonicFunctions.length === 0) return null;

  return (
    <div className="inspector-evidence-body">
      <SequenceBlock title="Chords" insights={chords} bpm={bpm} onSeek={onSeek} setSelection={setSelection} />
      <SequenceBlock title="Roman numerals" insights={romanNumerals} bpm={bpm} onSeek={onSeek} setSelection={setSelection} />
      <SequenceBlock title="Function" insights={harmonicFunctions} bpm={bpm} onSeek={onSeek} setSelection={setSelection} />
    </div>
  );
}

function RhythmEvidence({ insights, onSeek }: { insights: Insight[]; onSeek: (seconds: number) => void }) {
  const rhythmInsights = insights.filter((item) => item.kind === "rhythm");
  const densityInsights = insights.filter((item) => item.kind === "rhythm_density");
  const restInsights = insights.filter((item) => item.kind === "rhythm_rests");
  const observations: { label: string; time: number | null }[] = [];

  for (const insight of densityInsights) {
    const windows = (insight.evidence?.windows ?? []) as { start?: number; end?: number; density?: number }[];
    if (windows.length > 0) {
      const peak = windows.reduce((max, window) => (window.density ?? 0) > (max.density ?? 0) ? window : max, windows[0]);
      if (peak.density != null && peak.start != null) observations.push({ label: `Peak note density at ${formatTime(peak.start)}`, time: peak.start });
    }
  }

  for (const insight of restInsights) {
    const rests = (insight.evidence?.rests ?? []) as { start?: number; end?: number; duration?: number }[];
    if (rests.length > 0) {
      const longest = rests.reduce((max, rest) => (rest.duration ?? 0) > (max.duration ?? 0) ? rest : max, rests[0]);
      if (longest.start != null) observations.push({ label: `Longest observed gap at ${formatTime(longest.start)}`, time: longest.start });
    }
  }

  for (const insight of rhythmInsights) {
    const phases = (insight.evidence?.beat_phase_distribution ?? []) as { phase_start?: number; fraction?: number }[];
    if (phases.length === 4 && phases.every((phase) => phase.fraction != null)) {
      const nearBeat = (phases[0].fraction ?? 0) + (phases[3].fraction ?? 0);
      const betweenBeats = (phases[1].fraction ?? 0) + (phases[2].fraction ?? 0);
      observations.push({
        label: nearBeat >= 0.6
          ? `Most note attacks fall close to detected beats (${Math.round(nearBeat * 100)}%).`
          : betweenBeats >= 0.6
            ? `Many note attacks fall between detected beats (${Math.round(betweenBeats * 100)}%).`
            : "Note attacks are distributed across detected beat intervals.",
        time: null,
      });
    }
  }

  if (observations.length === 0) return null;

  return (
    <div className="inspector-evidence-body inspector-rhythm-observations">
      {observations.map((observation, index) => observation.time == null ? (
        <p className="inspector-evidence-copy" key={`${observation.label}-${index}`}>{observation.label}</p>
      ) : (
        <button className="inspector-evidence-jump" type="button" key={`${observation.label}-${index}`} onClick={() => onSeek(observation.time!)}>
          <span>{formatTime(observation.time)}</span>
          <span>{observation.label}</span>
        </button>
      ))}
    </div>
  );
}

function MelodyEvidence({ insights, onSeek, setSelection }: {
  insights: Insight[];
  onSeek: (seconds: number) => void;
  setSelection: (selection: MusicalSelection | null) => void;
}) {
  if (!isExperimental("melody")) return null;

  const summaries = insights.filter((item) => item.kind === "melody");
  const intervalSummary = insights.find((item) => item.kind === "melody_interval_summary");
  const temporalKinds = new Set([
    "melody_register_peak",
    "melody_register_low",
    "melody_contour_ascending",
    "melody_contour_descending",
    "melody_activity_dense",
    "melody_activity_sparse",
  ]);
  const temporal = insights.filter((item) => temporalKinds.has(item.kind) && item.span.start_seconds != null);

  if (summaries.length === 0 && !intervalSummary && temporal.length === 0) return null;

  return (
    <div className="inspector-evidence-body">
      {[...summaries.slice(0, 2), ...(intervalSummary ? [intervalSummary] : [])].map((item) => (
        <p className="inspector-evidence-copy" key={item.id}>{item.claim}</p>
      ))}
      {temporal.slice(0, 6).map((item) => (
        <button
          key={item.id}
          type="button"
          className="inspector-evidence-jump"
          onClick={() => {
            const start = item.span.start_seconds;
            if (start == null) return;
            onSeek(start);
            if (item.span.end_seconds != null) {
              setSelection({
                timeRange: { start, end: item.span.end_seconds, domain: "performance" },
                provenance: { origin: null, timeExact: true, measureApproximate: false },
              });
            }
          }}
        >
          <span>{formatTime(item.span.start_seconds!)}</span>
          <span>{item.claim}</span>
        </button>
      ))}
    </div>
  );
}

function EvidenceDisclosure({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  if (count === 0 || !children) return null;
  return (
    <details className="inspector-evidence-group">
      <summary>
        <span>{title}</span>
        <span className="inspector-evidence-count">{count}</span>
      </summary>
      {children}
    </details>
  );
}

function FindingsSection({
  findings,
  onSeek,
  setSelection,
}: {
  findings: TemporalFinding[];
  onSeek: (seconds: number) => void;
  setSelection: (selection: MusicalSelection | null) => void;
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
    <section className="inspector-section inspector-findings-section">
      <div className="inspector-section-heading">
        <h3>Moments</h3>
        <span>{findings.length}</span>
      </div>
      <div className="inspector-findings">
        {findings.map((finding) => (
          <button
            key={finding.id}
            type="button"
            className={`inspector-finding inspector-finding-${finding.category}`}
            onClick={() => handleClick(finding)}
          >
            <span className="inspector-finding-time">{formatTime(finding.startSeconds)}</span>
            <span className="inspector-finding-label">{finding.label}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

export default function InspectorPanel() {
  const { workspace, setInspectorMode, setSelection, clearSelection } = useWorkspace();
  const { seek } = useTransport();
  const { timeline } = useTimeline();
  const mode = workspace.inspectorMode;

  return (
    <aside className="inspector inspector-v4">
      <header className="inspector-header">
        <nav className="inspector-mode-tabs" role="tablist" aria-label="Inspector mode">
          <button type="button" role="tab" aria-selected={mode === "analysis"} className={mode === "analysis" ? "active" : ""} onClick={() => setInspectorMode("analysis")}>Analysis</button>
          <button type="button" role="tab" aria-selected={mode === "ask"} className={mode === "ask" ? "active" : ""} onClick={() => setInspectorMode("ask")}>Ask</button>
        </nav>
        {mode === "analysis" && workspace.selection && (
          <div className="inspector-scope">
            <span className="inspector-scope-value">{describeSelection(workspace.selection)}</span>
            <button type="button" className="inspector-scope-clear" onClick={clearSelection} aria-label="Clear selection">\u00d7</button>
          </div>
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
  const categorized = categorizeInsights(workspace.insights, workspace.selection, bpm);
  const selectionInsights = filterByCategory(categorized, "selection");
  const wholeWorkInsights = filterByCategory(categorized, "whole-work");

  const exposed = (insights: Insight[]) => insights
    .filter((item) => item.confidence == null || item.confidence >= 0.5)
    .filter((item) => isInspectorExposed(item.kind));

  const activeInsights = exposed(workspace.selection ? selectionInsights : wholeWorkInsights);
  const findings = deriveFindings(activeInsights);
  const harmonyCount = activeInsights.filter((item) => ["chord", "roman_numeral", "harmonic_function"].includes(item.kind)).length;
  const rhythmCount = activeInsights.filter((item) => ["rhythm", "rhythm_density", "rhythm_rests"].includes(item.kind)).length;
  const melodyCount = activeInsights.filter((item) => item.kind.startsWith("melody")).length;

  if (activeInsights.length === 0 && findings.length === 0) {
    return (
      <div className="inspector-content inspector-empty-state">
        <span className="inspector-empty-mark">\u223f</span>
        <strong>No confident findings yet</strong>
        <p>{workspace.selection ? "Try a wider selection or inspect the whole piece." : "Analysis will appear here when there is enough musical evidence."}</p>
      </div>
    );
  }

  return (
    <div className="inspector-content inspector-analysis-content">
      <section className="inspector-section inspector-overview-section">
        <div className="inspector-section-heading">
          <h3>{workspace.selection ? "Selection" : "At a glance"}</h3>
        </div>
        <OverviewRow insights={activeInsights} />
      </section>

      <FindingsSection findings={findings} onSeek={seek} setSelection={setSelection} />

      {(harmonyCount > 0 || rhythmCount > 0 || melodyCount > 0) && (
        <section className="inspector-section inspector-evidence-section">
          <div className="inspector-section-heading">
            <h3>Evidence</h3>
            <span className="inspector-section-hint">Details</span>
          </div>
          <div className="inspector-evidence-groups">
            <EvidenceDisclosure title="Harmony" count={harmonyCount}>
              <HarmonyEvidence insights={activeInsights} bpm={bpm} onSeek={seek} setSelection={setSelection} />
            </EvidenceDisclosure>
            <EvidenceDisclosure title="Rhythm" count={rhythmCount}>
              <RhythmEvidence insights={activeInsights} onSeek={seek} />
            </EvidenceDisclosure>
            <EvidenceDisclosure title="Melody" count={melodyCount}>
              <MelodyEvidence insights={activeInsights} onSeek={seek} setSelection={setSelection} />
            </EvidenceDisclosure>
          </div>
        </section>
      )}
    </div>
  );
}