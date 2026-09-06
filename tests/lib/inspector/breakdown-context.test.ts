import { describe, expect, it } from "vitest";
import {
  rankBreakdownFindings,
  type BreakdownCandidate,
} from "@/lib/inspector/breakdown";
import type { TemporalFinding } from "@/lib/inspector/findings";
import type { RhythmDensityContextCandidate } from "@/lib/inspector/rhythm-density-context";

const INSIGHT = "density-insight";

function contextCandidate(
  overrides: Partial<RhythmDensityContextCandidate> = {},
): RhythmDensityContextCandidate {
  return {
    id: "context-finding",
    sourceInsightId: INSIGHT,
    supportInsightIds: [INSIGHT],
    kind: "rhythm_density_work_context",
    category: "rhythm",
    startSeconds: 20,
    endSeconds: 24,
    label: "Median event density here is higher than the median elsewhere in this Work (6 vs 3 events/beat).",
    evidence: {
      evidenceSummary: "Middle half elsewhere in this Work: 2–4 events/beat.",
      subjectOrigin: "user_selected",
      selectionConditionedOnRhythmDensity: false,
      sourceVersionId: "version-1",
      sourceRelationId: "relation-1",
      supportRefs: [{
        type: "external",
        namespace: "rhythm_density_insight",
        id: `${INSIGHT}:rhythm_density`,
      }],
      referencePopulation: {
        kind: "work_excluding_subject",
        exclusion_policy: "exclude_intersecting_subject_windows_v1",
        eligible_window_count: 8,
        excluded_intersecting_window_count: 2,
        source_coverage_start_seconds: 0,
        source_coverage_end_seconds: 60,
        eligible_intervals_seconds: [[0, 20], [24, 60]],
        eligible_coverage_seconds: 56,
      },
      measurements: [{
        support_ref: {
          type: "external",
          namespace: "rhythm_density_insight",
          id: `${INSIGHT}:rhythm_density`,
        },
        feature: "rhythm_density",
        direction: "higher",
        summary: "literal measurement",
        unit: "events_per_beat",
        normalization: "events_per_beat",
        coordinate_unit: "beats",
        window_size: 2,
        step_size: 1,
        subject_value: 6,
        reference_median: 3,
        reference_q1: 2,
        reference_q3: 4,
        reference_iqr: 2,
        delta_from_reference_median: 3,
        empirical_midrank_percentile: 90,
        subject_window_count: 3,
        reference_window_count: 8,
      }],
      provenance: { engine: "rhythm_density_work_context" },
    },
    ...overrides,
  } as RhythmDensityContextCandidate;
}

function densityPeak(): TemporalFinding {
  return {
    id: "density-peak",
    sourceInsightId: INSIGHT,
    supportInsightIds: [INSIGHT],
    kind: "density_peak",
    category: "rhythm",
    startSeconds: 20,
    endSeconds: 24,
    label: "Highest observed note-onset density around 0:20",
    evidence: { density: 6 },
  };
}

describe("grounded contextual finding ranking", () => {
  it("admits a user-selected contextual claim through the existing ranking seam", () => {
    const [ranked] = rankBreakdownFindings(
      [contextCandidate()],
      { start: 20, end: 24 },
    );

    expect(ranked.kind).toBe("rhythm_density_work_context");
    expect(ranked.headline).toContain("median elsewhere in this Work");
    expect(ranked.evidenceSummary).toContain("Middle half elsewhere");
    expect(ranked.primaryRepresentation).toBe("waveform");
    expect(ranked.contextEvidence?.sourceVersionId).toBe("version-1");
  });

  it("suppresses density-conditioned context instead of double-counting an extrema detector", () => {
    const legacyContext = contextCandidate({
      id: "legacy-peak-context",
      evidence: {
        ...contextCandidate().evidence,
        subjectOrigin: "legacy_density_peak",
        selectionConditionedOnRhythmDensity: true,
      },
    });

    const ranked = rankBreakdownFindings(
      [legacyContext, densityPeak()] as BreakdownCandidate[],
      { start: 20, end: 24 },
    );

    expect(ranked).toHaveLength(1);
    expect(ranked[0].kind).toBe("density_peak");
  });

  it("does not alter existing empty/abstaining behavior when no context candidate exists", () => {
    expect(rankBreakdownFindings([])).toEqual([]);
    expect(rankBreakdownFindings([densityPeak()])[0].kind).toBe("density_peak");
  });
});
