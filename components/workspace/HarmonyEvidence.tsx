import type { Insight } from "@/lib/domain.types";
import { formatTime } from "@/lib/format";
import { insightStartSeconds } from "@/lib/inspector/insights";
import type { MusicalSelection } from "@/lib/stores/workspace";
import styles from "./HarmonyEvidence.module.css";

type HarmonicKind = "chord" | "roman_numeral" | "harmonic_function";

export type HarmonicMoment = {
  key: string;
  startSeconds: number;
  chords: Insight[];
  romanNumerals: Insight[];
  harmonicFunctions: Insight[];
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

    // Only align records that share the same source boundary. Including the
    // explicit end prevents unrelated labels that merely begin together from
    // being presented as one harmonic event. Beat-only evidence still groups
    // conservatively by its derived start when no second boundary is present.
    const endSeconds = item.span.end_seconds;
    const key = `${startSeconds.toFixed(3)}:${endSeconds == null ? "open" : endSeconds.toFixed(3)}`;
    const moment = moments.get(key) ?? {
      key,
      startSeconds,
      chords: [],
      romanNumerals: [],
      harmonicFunctions: [],
    };
    if (item.kind === "chord") moment.chords.push(item);
    if (item.kind === "roman_numeral") moment.romanNumerals.push(item);
    if (item.kind === "harmonic_function") moment.harmonicFunctions.push(item);
    moments.set(key, moment);
  }

  return [...moments.values()].sort((left, right) => left.startSeconds - right.startSeconds || left.key.localeCompare(right.key));
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

  const renderEvidence = (kind: HarmonicKind, items: Insight[], startSeconds: number) => {
    if (items.length === 0) return <span className={styles.empty} aria-hidden="true">—</span>;
    return (
      <div className={styles.cell}>
        {items.map((item) => {
          const visibleLabel = kind === "chord"
            ? chordEvidenceLabel(item)
            : kind === "roman_numeral"
              ? romanNumeralEvidenceLabel(item)
              : harmonicFunctionEvidenceLabel(item);
          const kindClass = kind === "chord" ? styles.chord : kind === "roman_numeral" ? styles.degree : styles.function;
          return (
            <button
              type="button"
              className={`${styles.value} ${kindClass}`}
              key={item.id}
              onClick={() => handleClick(item)}
              title={normalizeMusicText(item.claim)}
              aria-label={evidenceButtonLabel(kind, item, visibleLabel, startSeconds)}
            >
              {visibleLabel}
            </button>
          );
        })}
      </div>
    );
  };

  return (
    <div className={`inspector-evidence-body ${styles.timeline}`} role="table" aria-label="Harmonic timeline">
      <div className={styles.header} role="row">
        <span role="columnheader">Time</span>
        <span role="columnheader">Chord</span>
        <span role="columnheader">Degree</span>
        <span role="columnheader">Function</span>
      </div>
      {moments.map((moment) => (
        <div className={styles.moment} role="row" key={moment.key}>
          <span className={styles.time} role="cell">{formatTime(moment.startSeconds)}</span>
          <div role="cell">{renderEvidence("chord", moment.chords, moment.startSeconds)}</div>
          <div role="cell">{renderEvidence("roman_numeral", moment.romanNumerals, moment.startSeconds)}</div>
          <div role="cell">{renderEvidence("harmonic_function", moment.harmonicFunctions, moment.startSeconds)}</div>
        </div>
      ))}
    </div>
  );
}
