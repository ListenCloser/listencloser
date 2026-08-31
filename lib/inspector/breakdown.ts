import type { TemporalFinding } from "@/lib/inspector/findings";

export type BreakdownLens = "pulse" | "pitch";
export type BreakdownAction = "focus" | "loop" | "show" | "ask";
export type BreakdownRepresentation = "waveform" | "piano_roll";

export interface BreakdownFinding {
  id: string;
  sourceInsightId: string;
  supportInsightIds: string[];
  kind: TemporalFinding["kind"];
  lens: BreakdownLens;
  startSeconds: number;
  endSeconds: number;
  headline: string;
  /** Optional second-order context. Empty when it would only restate headline. */
  evidenceSummary: string;
  trustClass: "deterministic_derived";
  maturity: "production" | "experimental";
  primaryRepresentation: BreakdownRepresentation;
  /** Actions this pure evidence adapter can prove are currently valid. */
  availableActions: BreakdownAction[];
  score: number;
}

export type BreakdownTimeRange = { start: number; end: number } | null;

const KIND_PRIORITY: Record<TemporalFinding["kind"], number> = {
  melody_register_peak: 46,
  melody_register_low: 42,
  harmonic_activity: 40,
  melody_contour_ascending: 38,
  melody_contour_descending: 38,
  density_peak: 36,
  melody_activity_dense: 34,
  melody_activity_sparse: 32,
  rest: 29,
  density_valley: 25,
};

// Experimental evidence may remain visible, but within the same scope it must
// not displace a production finding merely because its musical-salience prior
// is higher. The penalty exceeds the full kind-priority + evidence-breadth
// spread between current experimental and production candidates.
const EXPERIMENTAL_MATURITY_PENALTY = 28;

function stripClaimPrefix(claim: string): string {
  return claim.replace(/^[^:]+:\s*/, "").replace(/\s+/g, " ").trim();
}

function isMelodyFinding(finding: TemporalFinding): boolean {
  return finding.category === "melody";
}

function overlaps(range: BreakdownTimeRange, finding: TemporalFinding): boolean {
  if (!range) return false;
  return finding.startSeconds < range.end && finding.endSeconds > range.start;
}

function selectionScore(range: BreakdownTimeRange, finding: TemporalFinding): number {
  if (!range) return 0;
  if (overlaps(range, finding)) return 100;

  const distance = finding.endSeconds <= range.start
    ? range.start - finding.endSeconds
    : finding.startSeconds - range.end;

  // Nearby context can still be useful after the selected passage, but it must
  // never outrank evidence that actually overlaps the user's selection.
  return Math.max(-40, 12 - distance);
}

function evidenceBreadthScore(finding: TemporalFinding): number {
  return Math.min(Object.keys(finding.evidence).length, 4);
}

function redundancyKey(finding: TemporalFinding): string {
  // Peak/valley density findings are two views over the same persisted density
  // measurement. Promote at most one from a source insight in the compact
  // Breakdown; the full evidence remains available on disclosure.
  if (finding.kind === "density_peak" || finding.kind === "density_valley") {
    return `density:${finding.sourceInsightId}`;
  }
  return finding.id;
}

function headlineFor(finding: TemporalFinding): string {
  switch (finding.kind) {
    case "density_peak":
      return "Note-onset activity is densest in this passage.";
    case "density_valley":
      return "Note-onset activity is comparatively sparse here.";
    case "rest":
      return "A pronounced gap in note attacks occurs here.";
    case "harmonic_activity":
      return "Chord changes become more frequent in this passage.";
    case "melody_register_peak":
      return "The detected melody reaches its highest register here.";
    case "melody_register_low":
      return "The detected melody reaches its lowest register here.";
    case "melody_contour_ascending":
      return "The detected melody moves upward through this passage.";
    case "melody_contour_descending":
      return "The detected melody moves downward through this passage.";
    case "melody_activity_dense":
      return "The detected melody becomes more active here.";
    case "melody_activity_sparse":
      return "The detected melody becomes sparser here.";
    default:
      return stripClaimPrefix(finding.label);
  }
}

function evidenceSummaryFor(finding: TemporalFinding): string {
  switch (finding.kind) {
    // The ranking itself already establishes peak/valley status. Repeating
    // "highest/lowest density" under a headline that says the same thing adds
    // no new information, so keep these cards claim-first and compact.
    case "density_peak":
    case "density_valley":
      return "";
    case "rest": {
      const duration = finding.evidence.duration;
      return typeof duration === "number"
        ? `Observed ${duration.toFixed(1)}s gap between note attacks.`
        : "Observed gap between note attacks.";
    }
    case "harmonic_activity":
      return "Derived from the timing of trusted chord boundaries; this describes change rate, not harmonic tension.";
    default:
      return isMelodyFinding(finding)
        ? "Derived from experimental melody extraction; inspect the piano roll before treating the line as authoritative."
        : stripClaimPrefix(finding.label);
  }
}

function toBreakdownFinding(
  finding: TemporalFinding,
  range: BreakdownTimeRange,
): BreakdownFinding {
  const melody = isMelodyFinding(finding);
  const score = KIND_PRIORITY[finding.kind]
    + selectionScore(range, finding)
    + evidenceBreadthScore(finding)
    - (melody ? EXPERIMENTAL_MATURITY_PENALTY : 0);

  return {
    id: `breakdown-${finding.id}`,
    sourceInsightId: finding.sourceInsightId,
    supportInsightIds: [...finding.supportInsightIds],
    kind: finding.kind,
    lens: finding.category === "rhythm" ? "pulse" : "pitch",
    startSeconds: finding.startSeconds,
    endSeconds: finding.endSeconds,
    headline: headlineFor(finding),
    evidenceSummary: evidenceSummaryFor(finding),
    trustClass: "deterministic_derived",
    maturity: melody ? "experimental" : "production",
    primaryRepresentation: melody || finding.category === "harmony" ? "piano_roll" : "waveform",
    // The ranking layer knows the span is valid, so it can guarantee Focus.
    // Loop requires a playable source, Show requires the target representation,
    // and Ask requires an enabled Ask path; the UI composition layer adds those
    // actions only after checking the live workspace state.
    availableActions: ["focus"],
    score,
  };
}

/**
 * Rank deterministic temporal findings for the compact Breakdown surface.
 *
 * This is presentation policy, not a new analysis engine. It never invents a
 * finding, confidence, or capability; it only promotes existing deterministic
 * findings. Selection overlap strongly outranks whole-work salience,
 * experimental melody remains eligible without displacing same-scope
 * production evidence, and duplicate views over the same source measurement
 * are collapsed.
 */
export function rankBreakdownFindings(
  findings: TemporalFinding[],
  range: BreakdownTimeRange = null,
  limit = 5,
): BreakdownFinding[] {
  if (limit <= 0) return [];

  const ranked = findings
    .filter((finding) => Number.isFinite(finding.startSeconds) && Number.isFinite(finding.endSeconds))
    .filter((finding) => finding.endSeconds > finding.startSeconds)
    .map((finding) => ({ finding, presentation: toBreakdownFinding(finding, range) }))
    .sort((a, b) => b.presentation.score - a.presentation.score
      || a.finding.startSeconds - b.finding.startSeconds
      || a.finding.id.localeCompare(b.finding.id));

  const seen = new Set<string>();
  const promoted: BreakdownFinding[] = [];

  for (const candidate of ranked) {
    const key = redundancyKey(candidate.finding);
    if (seen.has(key)) continue;
    seen.add(key);
    promoted.push(candidate.presentation);
    if (promoted.length >= limit) break;
  }

  return promoted;
}
