"use client";

import type { Insight } from "@/lib/domain.types";
import { formatTime } from "@/lib/format";
import { insightStartSeconds } from "@/lib/inspector/insights";
import type { MusicalSelection } from "@/lib/stores/workspace";
import styles from "./HarmonyEvidence.module.css";

type HarmonyEvidenceRow = {
  startSeconds: number;
  endSeconds: number | null;
  chord?: Insight;
  romanNumeral?: Insight;
  harmonicFunction?: Insight;
};

type HarmonyKind = "chord" | "roman_numeral" | "harmonic_function";
type HarmonySlot = "chord" | "romanNumeral" | "harmonicFunction";

const HARMONY_KINDS = new Set<HarmonyKind>(["chord", "roman_numeral", "harmonic_function"]);
const SPAN_TOLERANCE_SECONDS = 0.05;

function normalizeMusicText(value: string): string {
  return value
    .replace(/\b([A-G])- (?=(?:major|minor)\b)/g, "$1♭ ")
    .replace(/\s+/g, " ")
    .trim();
}

function evidenceString(insight: Insight, key: string): string | null {
  const evidence = insight.evidence as Record<string, unknown> | null | undefined;
  const value = evidence?.[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function slotForKind(kind: HarmonyKind): HarmonySlot {
  if (kind === "roman_numeral") return "romanNumeral";
  if (kind === "harmonic_function") return "harmonicFunction";
  return "chord";
}

function spansMatch(row: HarmonyEvidenceRow, startSeconds: number, endSeconds: number | null): boolean {
  if (Math.abs(row.startSeconds - startSeconds) > SPAN_TOLERANCE_SECONDS) return false;
  if (row.endSeconds === null || endSeconds === null) return true;
  return Math.abs(row.endSeconds - endSeconds) <= SPAN_TOLERANCE_SECONDS;
}

export function buildHarmonyEvidenceRows(insights: Insight[], bpm: number): HarmonyEvidenceRow[] {
  const temporal = insights
    .filter((item): item is Insight & { kind: HarmonyKind } => HARMONY_KINDS.has(item.kind as HarmonyKind))
    .map((item) => ({ item, startSeconds: insightStartSeconds(item, bpm) }))
    .filter((entry): entry is { item: Insight & { kind: HarmonyKind }; startSeconds: number } => entry.startSeconds !== null)
    .sort((a, b) => a.startSeconds - b.startSeconds || a.item.kind.localeCompare(b.item.kind));

  const rows: HarmonyEvidenceRow[] = [];
  for (const { item, startSeconds } of temporal) {
    const endSeconds = typeof item.span.end_seconds === "number" && Number.isFinite(item.span.end_seconds)
      ? item.span.end_seconds
      : null;
    const slot = slotForKind(item.kind);
    const existing = rows.find((row) => spansMatch(row, startSeconds, endSeconds) && row[slot] === undefined);
    const row = existing ?? { startSeconds, endSeconds };
    row[slot] = item;
    if (!existing) rows.push(row);
  }
  return rows;
}

export function harmonyEvidenceRowCount(insights: Insight[], bpm: number): number {
  return buildHarmonyEvidenceRows(insights, bpm).length;
}

export function harmonyEvidenceSummary(insights: Insight[], bpm: number): string | null {
  const rows = buildHarmonyEvidenceRows(insights, bpm);
  if (rows.length === 0) return null;
  const hasDegrees = rows.some((row) => Boolean(row.romanNumeral));
  const hasFunctions = rows.some((row) => Boolean(row.harmonicFunction));
  if (hasDegrees && hasFunctions) return "Chord timeline · degree and function context where supported";
  if (hasDegrees) return "Chord timeline · scale-degree context where supported";
  if (hasFunctions) return "Chord timeline · harmonic-function context where supported";
  return "Chord timeline";
}

function romanNumeralLabel(insight: Insight): string {
  const numeral = evidenceString(insight, "numeral");
  if (numeral) return normalizeMusicText(numeral);
  return normalizeMusicText(
    insight.claim.replace(/\s+\([^()]*(?:major|minor)[^()]*\)\s*$/i, ""),
  );
}

function harmonicFunctionLabel(insight: Insight): string {
  const raw = evidenceString(insight, "function") ?? insight.claim.replace(/\s+\([^()]*\)\s*$/, "");
  const normalized = normalizeMusicText(raw).toLowerCase();
  return normalized.replace(/(^|\s)\p{L}/gu, (match) => match.toUpperCase());
}

function chordLabel(insight: Insight): string {
  return normalizeMusicText(insight.claim);
}

function confidenceLabel(item: Insight): string | null {
  return typeof item.confidence === "number" ? `${Math.round(item.confidence * 100)}% confidence` : null;
}

function methodLabel(item: Insight): string | null {
  return evidenceString(item, "method");
}

function DetailItem({ item }: { item: Insight }) {
  const meta = [item.kind.replaceAll("_", " "), methodLabel(item), confidenceLabel(item)].filter(Boolean).join(" · ");
  return (
    <li className={styles.detailItem}>
      <span>{normalizeMusicText(item.claim)}</span>
      {meta && <span className={styles.detailMeta}>{meta}</span>}
    </li>
  );
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
  const rows = buildHarmonyEvidenceRows(insights, bpm);
  if (rows.length === 0) return null;

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
    <div className={`inspector-evidence-body ${styles.timeline}`} role="table" aria-label="Harmonic evidence timeline">
      <div className={`${styles.row} ${styles.header}`} role="row">
        <span role="columnheader">Time</span>
        <span role="columnheader">Harmony</span>
      </div>
      {rows.map((row) => {
        const primary = row.chord ?? row.romanNumeral ?? row.harmonicFunction;
        if (!primary) return null;
        const detailItems = [row.chord, row.romanNumeral, row.harmonicFunction].filter((item): item is Insight => Boolean(item));
        return (
          <div
            className={styles.row}
            role="row"
            key={`${row.startSeconds}-${row.chord?.id ?? ""}-${row.romanNumeral?.id ?? ""}-${row.harmonicFunction?.id ?? ""}`}
          >
            <span className={styles.time} role="cell">{formatTime(row.startSeconds)}</span>
            <div className={styles.harmony} role="cell">
              <button
                type="button"
                className={styles.primary}
                onClick={() => handleClick(primary)}
                title={normalizeMusicText(primary.claim)}
              >
                {row.chord ? chordLabel(row.chord) : row.romanNumeral ? romanNumeralLabel(row.romanNumeral) : harmonicFunctionLabel(row.harmonicFunction!)}
              </button>

              {(row.romanNumeral || row.harmonicFunction) && (
                <div className={styles.secondary}>
                  {row.romanNumeral && row.romanNumeral !== primary && (
                    <span className={styles.secondaryItem}>
                      <span className={styles.secondaryLabel}>Degree</span>
                      <button type="button" className={styles.secondaryButton} onClick={() => handleClick(row.romanNumeral!)}>
                        {romanNumeralLabel(row.romanNumeral)}
                      </button>
                    </span>
                  )}
                  {row.harmonicFunction && row.harmonicFunction !== primary && (
                    <span className={styles.secondaryItem}>
                      <span className={styles.secondaryLabel}>Function</span>
                      <button type="button" className={styles.secondaryButton} onClick={() => handleClick(row.harmonicFunction!)}>
                        {harmonicFunctionLabel(row.harmonicFunction)}
                      </button>
                    </span>
                  )}
                </div>
              )}

              <details className={styles.details}>
                <summary>Evidence details</summary>
                <ul className={styles.detailList}>
                  {detailItems.map((item) => <DetailItem item={item} key={item.id} />)}
                </ul>
              </details>
            </div>
          </div>
        );
      })}
    </div>
  );
}
