"use client";

import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import { categorizeInsights, filterByCategory, insightStartSeconds } from "@/lib/inspector/insights";
import { isInspectorExposed, isExperimental } from "@/lib/inspector/capabilities";
import { deriveFindings } from "@/lib/inspector/findings";
import { formatTime } from "@/lib/format";
import TabStrip from "@/components/ui/TabStrip";
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

function AnalysisOverview({
  insights,
  findings,
  selection,
}: {
  insights: Insight[];
  findings: TemporalFinding[];
  selection: MusicalSelection | null;
}) {
  const items = overviewItems(insights);
  const values = Object.fromEntries(items.map((item) => [item.label, item.value]));
  const summaryParts: string[] = [];

  if (values.Key && values.Tempo && values.Meter) {
    summaryParts.push(`The strongest global reading is ${values.Key}, around ${values.Tempo}, in ${values.Meter}.`);
  } else if (values.Key && values.Tempo) {
    summaryParts.push(`The strongest tonal reading is ${values.Key}, with a pulse near ${values.Tempo}.`);
  } else if (values.Key) {
    summaryParts.push(`The strongest global tonal reading is ${values.Key}.`);
  } else if (values.Tempo) {
    summaryParts.push(`A stable pulse is estimated near ${values.Tempo}.`);
  }

  const firstFinding = findings[0];
  if (firstFinding) {
    const finding = normalizeMusicText(firstFinding.label).replace(/[.]+$/, "");
    summaryParts.push(`The clearest time-linked observation is ${finding} near ${formatTime(firstFinding.startSeconds)}.`);
  }

  if (summaryParts.length === 0) {
    summaryParts.push(
      selection
        ? "There is not enough stable evidence in this selection for a useful high-level claim yet."
        : "There is not enough stable global evidence for a useful high-level claim yet.",
    );
  }

  return (
    <section className="inspector-section inspector-overview-section">
      <div className="inspector-section-heading"><h3>Overview</h3></div>
      <p className="inspector-summary">{summaryParts.join(" ")}</p>
      {items.length > 0 && (
        <dl className="inspector-meta-line" aria-label="Analysis metadata">
          {items.map((item) => (
            <div className="inspector-meta-item" key={item.label}>
              <dt>{item.label}</dt>
              <dd>{item.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

type HarmonyMoment = {
  id: string;
  start: number;
  end: number | null;
  chord: string | null;
  roman: string | null;
  harmonicFunction: string | null;
};

function harmonyMoments(insights: Insight[], bpm: number): HarmonyMoment[] {
  const harmonicKinds = new Set(["chord", "roman_numeral", "harmonic_function"]);
  const temporal = insights
    .filter((item) => harmonicKinds.has(item.kind))
    .map((item) => ({ item, start: insightStartSeconds(item, bpm) }))
    .filter((entry): entry is { item: Insight; start: number } => entry.start !== null)
    .sort((a, b) => a.start - b.start);

  const moments: HarmonyMoment[] = [];
  for (const { item, start } of temporal) {
    // These three insight families are parallel descriptions of the same
    // harmonic event. Their persisted timestamps can differ by a few ms, so
    // fold near-identical starts into one event rather than three sequences.
    let moment = moments.find((candidate) => Math.abs(candidate.start - start) <= 0.12);
    if (!moment) {
      moment = {
        id: item.id,
        start,
        end: item.span.end_seconds,
        chord: null,
        roman: null,
        harmonicFunction: null,
      };
      moments.push(moment);
    } else if (item.span.end_seconds != null) {
      moment.end = moment.end == null ? item.span.end_seconds : Math.max(moment.end, item.span.end_seconds);
    }

    const value = normalizeMusicText(stripClaimPrefix(item.claim));
    if (item.kind === "chord") moment.chord = value;
    if (item.kind === "roman_numeral") moment.roman = value;
    if (item.kind === "harmonic_function") moment.harmonicFunction = value;
  }
  return moments;
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
  const moments = harmonyMoments(insights, bpm);
  if (moments.length === 0) return null;

  const handleClick = (moment: HarmonyMoment) => {
    onSeek(moment.start);
    if (moment.end != null && moment.end > moment.start) {
      setSelection({
        timeRange: { start: moment.start, end: moment.end, domain: "notation" },
        provenance: { origin: "score", timeExact: false, measureApproximate: true },
      });
    }
  };

  return (
    <div className="inspector-evidence-body inspector-harmony-moments">
      {moments.map((moment) => {
        const primary = moment.chord ?? moment.roman ?? moment.harmonicFunction ?? "Harmony";
        const context = [moment.roman, moment.harmonicFunction]
          .filter((value): value is string => Boolean(value) && value !== primary)
          .filter((value, index, values) => values.indexOf(value) === index);
        return (
          <button
            type="button"
            className="inspector-harmony-moment"
            key={`${moment.id}-${moment.start}`}
            onClick={() => handleClick(moment)}
            title={[primary, ...context].join(" · ")}
          >
            <span className="inspector-harmony-time">{formatTime(moment.start)}</span>
            <span className="inspector-harmony-primary">{primary}</span>
            {context.length > 0 && <span className="inspector-harmony-context">{context.join(" · ")}</span>}
          </button>
        );
      })}
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

function EvidenceDisclosure({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <details className="inspector-evidence-group">
      <summary><span>{title}</span></summary>
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
        <h3>Notable moments</h3>
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
        <TabStrip
          className="inspector-mode-tabs"
          label="Inspector mode"
          items={[
            { id: "analysis", label: "Analysis" },
            { id: "ask", label: "Ask" },
          ]}
          value={mode}
          onChange={setInspectorMode}
        />
        {mode === "analysis" && workspace.selection && (
          <div className="inspector-scope">
            <span className="inspector-scope-value">{describeSelection(workspace.selection)}</span>
            <button type="button" className="inspector-scope-clear" onClick={clearSelection} aria-label="Clear selection">×</button>
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
  const hasKeyContext = overviewItems(activeInsights).some((item) => item.label === "Key");
  const evidenceInsights = activeInsights
    .filter((item) => item.confidence == null || item.confidence >= 0.65)
    .filter((item) => {
      if (["roman_numeral", "harmonic_function"].includes(item.kind)) return hasKeyContext;
      if (item.kind.startsWith("melody_") && item.kind !== "melody_interval_summary") return false;
      return true;
    });
  const hasHarmony = evidenceInsights.some(
    (item) => ["chord", "roman_numeral", "harmonic_function"].includes(item.kind) && insightStartSeconds(item, bpm) !== null,
  );
  const hasRhythm = evidenceInsights.some((item) => ["rhythm", "rhythm_density", "rhythm_rests"].includes(item.kind));
  const hasMelody = evidenceInsights.some((item) => item.kind === "melody" || item.kind === "melody_interval_summary");

  if (activeInsights.length === 0 && findings.length === 0) {
    return (
      <div className="inspector-content inspector-empty-state">
        <strong>No confident findings yet</strong>
        <p>{workspace.selection ? "Try a wider selection or inspect the whole piece." : "Analysis will appear here when there is enough musical evidence."}</p>
      </div>
    );
  }

  return (
    <div className="inspector-content inspector-analysis-content">
      <AnalysisOverview insights={activeInsights} findings={findings} selection={workspace.selection} />

      <FindingsSection findings={findings} onSeek={seek} setSelection={setSelection} />

      {(hasHarmony || hasRhythm || hasMelody) && (
        <section className="inspector-section inspector-evidence-section">
          <div className="inspector-section-heading">
            <h3>Supporting evidence</h3>
          </div>
          <div className="inspector-evidence-groups">
            {hasHarmony && (
              <EvidenceDisclosure title="Harmony">
                <HarmonyEvidence insights={evidenceInsights} bpm={bpm} onSeek={seek} setSelection={setSelection} />
              </EvidenceDisclosure>
            )}
            {hasRhythm && (
              <EvidenceDisclosure title="Rhythm">
                <RhythmEvidence insights={evidenceInsights} onSeek={seek} />
              </EvidenceDisclosure>
            )}
            {hasMelody && (
              <EvidenceDisclosure title="Melody">
                <MelodyEvidence insights={evidenceInsights} onSeek={seek} setSelection={setSelection} />
              </EvidenceDisclosure>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
