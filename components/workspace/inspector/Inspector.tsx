"use client";

import type { ReactNode } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import { categorizeInsights, filterByCategory } from "@/lib/inspector/insights";
import { isInspectorExposed, isExperimental } from "@/lib/inspector/capabilities";
import { deriveFindings } from "@/lib/inspector/findings";
import { rankBreakdownFindings, type BreakdownFinding } from "@/lib/inspector/breakdown";
import { formatTime } from "@/lib/format";
import TabStrip from "@/components/ui/TabStrip";
import AskPanel from "./AskPanel";
import BreakdownFindingCard from "./BreakdownFindingCard";
import HarmonyEvidence, { harmonyEvidenceRowCount, harmonyEvidenceSummary } from "./HarmonyEvidence";
import MeasuredChanges from "./MeasuredChanges";
import PassageCompare from "./PassageCompare";
import type { MusicalSelection } from "@/lib/stores/workspace";
import type { Insight } from "@/lib/domain.types";
import styles from "./Inspector.module.css";

const MELODY_TEMPORAL_KINDS = new Set([
  "melody_register_peak",
  "melody_register_low",
  "melody_contour_ascending",
  "melody_contour_descending",
  "melody_activity_dense",
  "melody_activity_sparse",
]);

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

function OverviewSection({ insights }: { insights: Insight[] }) {
  const items = overviewItems(insights);
  if (items.length === 0) return null;

  return (
    <section className="inspector-section inspector-breakdown-context">
      <div className="inspector-section-heading"><h3>Overview</h3></div>
      <dl className="inspector-meta-line" aria-label="Musical overview">
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
  const temporal = insights.filter((item) => MELODY_TEMPORAL_KINDS.has(item.kind) && item.span.start_seconds != null);

  if (summaries.length === 0 && !intervalSummary && temporal.length === 0) return null;

  return (
    <div className="inspector-evidence-body">
      {[...summaries.slice(0, 2), ...(intervalSummary ? [intervalSummary] : [])].map((item) => (
        <p className="inspector-evidence-copy" key={item.id}>{normalizeMusicText(item.claim)}</p>
      ))}
      {temporal.map((item) => (
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

function rhythmEvidenceSummary(insights: Insight[]): string | null {
  const labels: string[] = [];
  if (insights.some((item) => item.kind === "rhythm")) labels.push("beat placement");
  if (insights.some((item) => item.kind === "rhythm_density")) labels.push("note density");
  if (insights.some((item) => item.kind === "rhythm_rests")) labels.push("rests and gaps");
  return labels.length > 0 ? labels.join(" · ") : null;
}

function melodyEvidenceSummary(insights: Insight[]): string | null {
  const labels: string[] = [];
  if (insights.some((item) => item.kind === "melody")) labels.push("melodic summary");
  if (insights.some((item) => item.kind === "melody_interval_summary")) labels.push("interval profile");
  if (insights.some((item) => MELODY_TEMPORAL_KINDS.has(item.kind))) labels.push("time-linked observations");
  return labels.length > 0 ? labels.join(" · ") : null;
}

function AnalysisGroup({ title, summary, children }: { title: string; summary: string | null; children: ReactNode }) {
  if (!summary || !children) return null;
  return (
    <section className={styles.analysisGroup} aria-label={`${title} analysis`}>
      <header className={styles.analysisGroupHeader}>
        <h4>{title}</h4>
        <span>{summary}</span>
      </header>
      {children}
    </section>
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
  analysisState,
}: {
  findings: BreakdownFinding[];
  selection: MusicalSelection | null;
  analysisState: ReturnType<typeof useWorkspace>["workspace"]["analysisState"];
}) {
  const emptyCopy = analysisState === "analyzing"
    ? {
        title: "Still looking for a strong time-linked finding",
        body: "Supported overview and analysis that has arrived is available below while analysis continues.",
      }
    : analysisState === "completed"
      ? {
          title: "No supported time-linked finding",
          body: selection
            ? "Analysis completed without a reliable localized claim for this selection. Try a wider passage or Ask about the available analysis."
            : "Analysis completed without a reliable time-linked summary. Available overview and analysis remain below.",
        }
      : {
          title: "No strong time-linked finding here yet",
          body: selection
            ? "The current analysis does not support a reliable localized claim for this selection. Try a wider passage or Ask about what is available."
            : "The current analysis does not support a reliable time-linked summary yet. Available overview and analysis remain below.",
        };
  const primaryFindings = findings.slice(0, 3);
  const moreFindings = findings.slice(3);

  return (
    <section className="inspector-section inspector-breakdown-section">
      <div className="inspector-section-heading">
        <h3>{selection ? "About this selection" : "What stands out"}</h3>
      </div>

      {findings.length === 0 ? (
        <div className="inspector-breakdown-sparse">
          <strong>{emptyCopy.title}</strong>
          <p>{emptyCopy.body}</p>
        </div>
      ) : (
        <>
          <div className="inspector-breakdown-findings">
            {primaryFindings.map((finding) => (
              <BreakdownFindingCard key={finding.id} finding={finding} />
            ))}
          </div>
          {moreFindings.length > 0 && (
            <details className={styles.moreFindings}>
              <summary>More findings <span>{moreFindings.length}</span></summary>
              <div className={styles.moreFindingsList}>
                {moreFindings.map((finding) => (
                  <BreakdownFindingCard key={finding.id} finding={finding} />
                ))}
              </div>
            </details>
          )}
        </>
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
        {workspace.selection && (
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
  const rankedFindings = rankBreakdownFindings(rawFindings, timeRange, 8)
    .filter((finding) => overlapsSelection(finding, workspace.selection));

  const scopedInsights = workspace.selection
    ? exposed([...selectionInsights, ...wholeWorkInsights])
    : exposedAll;
  const overviewInsights = exposed(wholeWorkInsights);
  const hasKeyContext = overviewItems(overviewInsights).some((item) => item.label === "Key");
  const analysisInsights = scopedInsights
    .filter((item) => item.confidence == null || item.confidence >= 0.65)
    .filter((item) => !["key", "tempo", "audio_tempo", "time_signature"].includes(item.kind))
    .filter((item) => !["roman_numeral", "harmonic_function"].includes(item.kind) || hasKeyContext);

  const harmonyCount = harmonyEvidenceRowCount(analysisInsights, bpm);
  const rhythmCount = analysisInsights.filter((item) => ["rhythm", "rhythm_density", "rhythm_rests"].includes(item.kind)).length;
  const melodyCount = analysisInsights.filter((item) => item.kind === "melody" || item.kind.startsWith("melody_")).length;
  const totalAnalysisCount = harmonyCount + rhythmCount + melodyCount;
  const harmonySummary = harmonyEvidenceSummary(analysisInsights, bpm);
  const rhythmSummary = rhythmEvidenceSummary(analysisInsights);
  const melodySummary = melodyEvidenceSummary(analysisInsights);
  const analysisDomains = [
    harmonySummary ? "Harmony" : null,
    rhythmSummary ? "Rhythm" : null,
    melodySummary ? "Melody" : null,
  ].filter((item): item is string => item !== null).join(" · ");
  const overviewCount = overviewItems(overviewInsights).length;

  if (exposedAll.length === 0 && rankedFindings.length === 0) {
    const emptyState = workspace.analysisState === "analyzing"
      ? {
          title: "Analysis is still in progress",
          body: workspace.selection
            ? "Supported findings will appear here as analysis becomes available for this selection."
            : "Breakdown will fill in as supported musical analysis becomes available. You can keep listening or move between views while processing continues.",
        }
      : workspace.analysisState === "completed"
        ? {
            title: "Analysis complete — no supported findings",
            body: workspace.selection
              ? "Processing finished, but the available analysis did not support a confident finding for this selection. Try a wider passage or Ask about the recording."
              : "Processing finished, but the available analysis did not support a confident Breakdown. You can still Ask about the recording or inspect the available representations.",
          }
        : {
            title: "No confident findings yet",
            body: workspace.selection
              ? "Try a wider selection or Ask about what is available."
              : "Breakdown will appear here when there is enough musical analysis.",
          };

    return (
      <div className="inspector-content inspector-analysis-content inspector-breakdown-content">
        <div className="inspector-empty-state" aria-live="polite">
          <strong>{emptyState.title}</strong>
          <p>{emptyState.body}</p>
        </div>
        <MeasuredChanges />
        <PassageCompare />
      </div>
    );
  }

  return (
    <div className="inspector-content inspector-analysis-content inspector-breakdown-content">
      <BreakdownSection
        findings={rankedFindings}
        selection={workspace.selection}
        analysisState={workspace.analysisState}
      />

      <MeasuredChanges />
      <PassageCompare />

      {overviewCount > 0 && <OverviewSection insights={overviewInsights} />}

      {totalAnalysisCount > 0 && (
        <section className="inspector-section inspector-evidence-section inspector-breakdown-evidence-section">
          <details className={styles.analysisDisclosure}>
            <summary className={styles.analysisRootSummary}>
              <span>Analysis</span>
              <span className={styles.analysisRootMeta}>{analysisDomains}</span>
            </summary>
            <div className={styles.analysisGroups}>
              <AnalysisGroup title="Harmony" summary={harmonySummary}>
                <HarmonyEvidence insights={analysisInsights} bpm={bpm} onSeek={seek} setSelection={setSelection} />
              </AnalysisGroup>
              <AnalysisGroup title="Rhythm" summary={rhythmSummary}>
                <RhythmEvidence insights={analysisInsights} onSeek={seek} />
              </AnalysisGroup>
              <AnalysisGroup title="Melody" summary={melodySummary}>
                <MelodyEvidence insights={analysisInsights} onSeek={seek} setSelection={setSelection} />
              </AnalysisGroup>
            </div>
          </details>
        </section>
      )}
    </div>
  );
}
