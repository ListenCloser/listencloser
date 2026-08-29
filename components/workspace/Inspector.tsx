"use client";

import type { ReactNode } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import { categorizeInsights, filterByCategory, insightStartSeconds } from "@/lib/inspector/insights";
import { isInspectorExposed, isExperimental } from "@/lib/inspector/capabilities";
import { deriveFindings } from "@/lib/inspector/findings";
import { rankBreakdownFindings, type BreakdownFinding } from "@/lib/inspector/breakdown";
import { formatTime } from "@/lib/format";
import TabStrip from "@/components/ui/TabStrip";
import AskPanel from "./AskPanel";
import BreakdownFindingCard from "./BreakdownFindingCard";
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

function stripClaimPrefix(claim: string): string {
  return claim.replace(/^[^:]+:\s*/, "");
}

type OverviewItem = { label: string; value: string };

function normalizeMusicText(value: string): string {
  return value
    .replace(/\b([A-G])- (?=(?:major|minor)\b)/g, "$1♭ ")
    .replace(/\s+/g, " ")
    .trim();
}

function cleanOverviewValue(insight: Insight | undefined): string | null {
  if (!insight) return null;
  const value = normalizeMusicText(stripClaimPrefix(insight.claim));
  if (!value || value === "—" || value === "-" || /^(unknown|unavailable|not confidently detected)$/i.test(value)) return null;
  return value;
}

function overviewItems(insights: Insight[]): OverviewItem[] {
  const key = cleanOverviewValue(insights.find((item) => item.kind === "key"));
  const tempo = cleanOverviewValue(
    insights.find((item) => item.kind === "audio_tempo") ?? insights.find((item) => item.kind === "tempo"),
  );
  const meter = cleanOverviewValue(insights.find((item) => item.kind === "time_signature"));
  return [
    key ? { label: "Key", value: key } : null,
    tempo ? { label: "Tempo", value: tempo } : null,
    meter ? { label: "Meter", value: meter } : null,
  ].filter((item): item is OverviewItem => item !== null);
}

function ContextSection({ insights }: { insights: Insight[] }) {
  const items = overviewItems(insights);
  if (items.length === 0) return null;

  return (
    <section className="inspector-section inspector-breakdown-context">
      <div className="inspector-section-heading"><h3>Context</h3></div>
      <dl className="inspector-meta-line" aria-label="Musical context">
        {items.map((item) => (
          <div className="inspector-meta-item" key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
    </section>
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
            title={normalizeMusicText(item.claim)}
          >
            {normalizeMusicText(item.claim)}
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
        <p className="inspector-evidence-copy" key={item.id}>{normalizeMusicText(item.claim)}</p>
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
          <span>{normalizeMusicText(item.claim)}</span>
        </button>
      ))}
    </div>
  );
}

function EvidenceDisclosure({ title, count, children }: { title: string; count: number; children: ReactNode }) {
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

function overlapsSelection(finding: BreakdownFinding, selection: MusicalSelection | null): boolean {
  const range = selection?.timeRange;
  if (!range) return true;
  return finding.startSeconds < range.end && finding.endSeconds > range.start;
}

function BreakdownSection({
  findings,
  selection,
}: {
  findings: BreakdownFinding[];
  selection: MusicalSelection | null;
}) {
  return (
    <section className="inspector-section inspector-breakdown-section">
      <div className="inspector-section-heading">
        <h3>{selection ? "About this selection" : "What stands out"}</h3>
        {findings.length > 0 && <span>{findings.length}</span>}
      </div>

      {findings.length === 0 ? (
        <div className="inspector-breakdown-sparse">
          <strong>No strong time-linked finding here yet</strong>
          <p>{selection
            ? "The current evidence does not support a reliable localized claim for this selection. Try a wider passage or Ask about what is available."
            : "The current evidence does not support a reliable time-linked summary yet. Available context and source evidence remain below."}</p>
        </div>
      ) : (
        <div className="inspector-breakdown-findings">
          {findings.map((finding) => (
            <BreakdownFindingCard key={finding.id} finding={finding} />
          ))}
        </div>
      )}
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
        <TabStrip
          className="inspector-mode-tabs"
          label="Inspector mode"
          items={[
            { id: "analysis", label: "Breakdown" },
            { id: "ask", label: "Ask" },
          ]}
          value={mode}
          onChange={setInspectorMode}
        />
        {mode === "analysis" && workspace.selection && (
          <div className="inspector-scope">
            <span className="inspector-scope-label">Selected</span>
            <span className="inspector-scope-value">{describeSelection(workspace.selection)}</span>
            <button type="button" className="inspector-scope-clear" onClick={clearSelection} aria-label="Clear selection">×</button>
          </div>
        )}
      </header>

      {mode === "analysis"
        ? <BreakdownContent workspace={workspace} seek={seek} bpm={timeline.bpm} setSelection={setSelection} />
        : <div className="inspector-content ask-content"><AskPanel /></div>}
    </aside>
  );
}

function BreakdownContent({
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
  const exposed = (insights: Insight[]) => insights
    .filter((item) => item.confidence == null || item.confidence >= 0.5)
    .filter((item) => isInspectorExposed(item.kind));

  const exposedAll = exposed(workspace.insights);
  const categorized = categorizeInsights(exposedAll, workspace.selection, bpm);
  const selectionInsights = filterByCategory(categorized, "selection");
  const wholeWorkInsights = filterByCategory(categorized, "whole-work");

  const rawFindings = workspace.selection && !workspace.selection.timeRange
    ? deriveFindings(exposed(selectionInsights))
    : deriveFindings(exposedAll);
  const timeRange = workspace.selection?.timeRange
    ? { start: workspace.selection.timeRange.start, end: workspace.selection.timeRange.end }
    : null;
  const rankedFindings = rankBreakdownFindings(rawFindings, timeRange, 5)
    .filter((finding) => overlapsSelection(finding, workspace.selection));

  const scopedInsights = workspace.selection
    ? exposed([...selectionInsights, ...wholeWorkInsights])
    : exposedAll;
  const contextInsights = exposed(wholeWorkInsights);
  const hasKeyContext = overviewItems(contextInsights).some((item) => item.label === "Key");
  const evidenceInsights = scopedInsights
    .filter((item) => item.confidence == null || item.confidence >= 0.65)
    .filter((item) => {
      if (["roman_numeral", "harmonic_function"].includes(item.kind)) return hasKeyContext;
      if (item.kind.startsWith("melody_") && item.kind !== "melody_interval_summary") return false;
      return true;
    });

  const harmonyCount = evidenceInsights.filter((item) => ["chord", "roman_numeral", "harmonic_function"].includes(item.kind)).length;
  const rhythmCount = evidenceInsights.filter((item) => ["rhythm", "rhythm_density", "rhythm_rests"].includes(item.kind)).length;
  const melodyCount = evidenceInsights.filter((item) => item.kind === "melody" || item.kind === "melody_interval_summary").length;
  const totalEvidenceCount = harmonyCount + rhythmCount + melodyCount;
  const contextCount = overviewItems(contextInsights).length;

  if (exposedAll.length === 0 && rankedFindings.length === 0) {
    return (
      <div className="inspector-content inspector-empty-state">
        <strong>No confident findings yet</strong>
        <p>{workspace.selection
          ? "Try a wider selection or Ask about what is available."
          : "Breakdown will appear here when there is enough musical evidence."}</p>
      </div>
    );
  }

  return (
    <div className="inspector-content inspector-analysis-content inspector-breakdown-content">
      <BreakdownSection findings={rankedFindings} selection={workspace.selection} />

      {contextCount > 0 && <ContextSection insights={contextInsights} />}

      {totalEvidenceCount > 0 && (
        <section className="inspector-section inspector-evidence-section inspector-breakdown-evidence-section">
          <details className="inspector-breakdown-evidence-root">
            <summary>
              <span>Evidence details</span>
              <span className="inspector-evidence-count">{totalEvidenceCount}</span>
            </summary>
            <div className="inspector-evidence-groups">
              <EvidenceDisclosure title="Harmony" count={harmonyCount}>
                <HarmonyEvidence insights={evidenceInsights} bpm={bpm} onSeek={seek} setSelection={setSelection} />
              </EvidenceDisclosure>
              <EvidenceDisclosure title="Rhythm" count={rhythmCount}>
                <RhythmEvidence insights={evidenceInsights} onSeek={seek} />
              </EvidenceDisclosure>
              <EvidenceDisclosure title="Melody" count={melodyCount}>
                <MelodyEvidence insights={evidenceInsights} onSeek={seek} setSelection={setSelection} />
              </EvidenceDisclosure>
            </div>
          </details>
        </section>
      )}
    </div>
  );
}
