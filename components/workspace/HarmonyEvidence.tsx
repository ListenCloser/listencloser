import type { Insight } from "@/lib/domain.types";
import { formatTime } from "@/lib/format";
import { insightStartSeconds } from "@/lib/inspector/insights";
import type { MusicalSelection } from "@/lib/stores/workspace";

type HarmonicKind = "chord" | "roman_numeral" | "harmonic_function";

export type HarmonicMoment = {
  startSeconds: number;
  chord?: Insight;
  romanNumeral?: Insight;
  harmonicFunction?: Insight;
};

function normalizeMusicText(value: string): string {
  return value
    .replace(/\b([A-G])- (?=(?:major|minor)\b)/g, "$1♭ ")
    .replace(/\s+/g, " ")
    .trim();
}

function stripClaimPrefix(claim: string): string {
  return claim.replace(/^[^:]+:\s*/, "");
}

function structuredString(item: Insight, key: string): string | null {
  const evidence = item.evidence as Record<string, unknown> | null | undefined;
  const value = evidence?.[key];
  return typeof value === "string" && value.trim() ? normalizeMusicText(value) : null;
}

function titleCaseMusicalRole(value: string): string {
  const normalized = value.replace(/_/g, " ").toLocaleLowerCase();
  return normalized.replace(/(^|\s)\S/g, (character) => character.toLocaleUpperCase());
}

export function chordEvidenceLabel(item: Insight): string {
  return normalizeMusicText(stripClaimPrefix(item.claim));
}

export function romanNumeralEvidenceLabel(item: Insight): string {
  const structured = structuredString(item, "numeral");
  if (structured) return structured;
  return normalizeMusicText(stripClaimPrefix(item.claim)).replace(/\s+\([^)]*\)\s*$/, "").trim();
}

export function harmonicFunctionEvidenceLabel(item: Insight): string {
  const structured = structuredString(item, "function");
  if (structured) return titleCaseMusicalRole(structured);
  const claim = normalizeMusicText(stripClaimPrefix(item.claim)).replace(/\s+\([^)]*\)\s*$/, "").trim();
  return titleCaseMusicalRole(claim);
}

export function groupHarmonicMoments(insights: Insight[], bpm: number): HarmonicMoment[] {
  const moments = new Map<string, HarmonicMoment>();

  for (const item of insights) {
    if (!["chord", "roman_numeral", "harmonic_function"].includes(item.kind)) continue;
    const startSeconds = insightStartSeconds(item, bpm);
    if (startSeconds === null) continue;

    // These derived harmonic labels are emitted from the same source boundary.
    // Millisecond rounding absorbs serialization noise without joining nearby
    // but genuinely distinct harmonic events.
    const key = startSeconds.toFixed(3);
    const moment = moments.get(key) ?? { startSeconds };
    if (item.kind === "chord") moment.chord = item;
    if (item.kind === "roman_numeral") moment.romanNumeral = item;
    if (item.kind === "harmonic_function") moment.harmonicFunction = item;
    moments.set(key, moment);
  }

  return [...moments.values()].sort((left, right) => left.startSeconds - right.startSeconds);
}

function evidenceButtonLabel(kind: HarmonicKind, item: Insight, visibleLabel: string, startSeconds: number): string {
  const kindLabel = kind === "chord" ? "Chord" : kind === "roman_numeral" ? "Degree" : "Function";
  return `${kindLabel} ${visibleLabel} at ${formatTime(startSeconds)}. Source evidence: ${normalizeMusicText(item.claim)}`;
}

export default function HarmonyEvidence({
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
  const moments = groupHarmonicMoments(insights, bpm);
  if (moments.length === 0) return null;

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

  const renderEvidence = (kind: HarmonicKind, item: Insight | undefined, startSeconds: number) => {
    if (!item) return <span className="inspector-harmony-empty" aria-hidden="true">—</span>;
    const visibleLabel = kind === "chord"
      ? chordEvidenceLabel(item)
      : kind === "roman_numeral"
        ? romanNumeralEvidenceLabel(item)
        : harmonicFunctionEvidenceLabel(item);
    return (
      <button
        type="button"
        className={`inspector-harmony-value inspector-harmony-${kind.replace("_", "-")}`}
        onClick={() => handleClick(item)}
        title={normalizeMusicText(item.claim)}
        aria-label={evidenceButtonLabel(kind, item, visibleLabel, startSeconds)}
      >
        {visibleLabel}
      </button>
    );
  };

  return (
    <div className="inspector-evidence-body inspector-harmony-timeline" role="table" aria-label="Harmonic timeline">
      <div className="inspector-harmony-header" role="row">
        <span role="columnheader">Time</span>
        <span role="columnheader">Chord</span>
        <span role="columnheader">Degree</span>
        <span role="columnheader">Function</span>
      </div>
      {moments.map((moment) => (
        <div className="inspector-harmony-moment" role="row" key={moment.startSeconds.toFixed(3)}>
          <span className="inspector-harmony-time" role="cell">{formatTime(moment.startSeconds)}</span>
          <div role="cell">{renderEvidence("chord", moment.chord, moment.startSeconds)}</div>
          <div role="cell">{renderEvidence("roman_numeral", moment.romanNumeral, moment.startSeconds)}</div>
          <div role="cell">{renderEvidence("harmonic_function", moment.harmonicFunction, moment.startSeconds)}</div>
        </div>
      ))}
    </div>
  );
}
