import { describe, expect, it } from "vitest";
import {
  toRhythmDensityContextCandidate,
} from "@/lib/inspector/rhythm-density-context";
import type { RhythmDensityContextResponse } from "@/lib/relation-api-client";

const VERSION = "00000000-0000-0000-0000-000000000010";
const INSIGHT = "00000000-0000-0000-0000-000000000020";

function response(overrides: Record<string, unknown> = {}): RhythmDensityContextResponse {
  return {
    status: "supported",
    rhythm_density_insight_id: INSIGHT,
    reasons: [],
    finding: {
      id: "context-finding-1",
      source_relation_id: "00000000-0000-0000-0000-000000000030",
      kind: "rhythm_density_work_context",
      relation_kind: "compare",
      trust_class: "deterministic_derived",
      maturity: "production",
      subject_locator: {
        start_seconds: 4,
        end_seconds: 6,
        source_artifact_version_id: VERSION,
        authority: "user_selected",
      },
      reference_population: {
        kind: "work_excluding_subject",
        exclusion_policy: "exclude_intersecting_subject_windows_v1",
        eligible_window_count: 5,
        excluded_intersecting_window_count: 4,
        source_coverage_start_seconds: 0,
        source_coverage_end_seconds: 10,
        eligible_intervals_seconds: [[0, 4], [6, 10]],
        eligible_coverage_seconds: 8,
      },
      support_refs: [{
        type: "external",
        namespace: "rhythm_density_insight",
        id: `${INSIGHT}:rhythm_density`,
      }],
      measurements: [{
        support_ref: {
          type: "external",
          namespace: "rhythm_density_insight",
          id: `${INSIGHT}:rhythm_density`,
        },
        feature: "rhythm_density",
        direction: "higher",
        summary: "Median event density here is higher than the median elsewhere in this Work (4.5 vs 2 events/beat).",
        unit: "events_per_beat",
        normalization: "events_per_beat",
        coordinate_unit: "beats",
        window_size: 2,
        step_size: 1,
        subject_value: 4.5,
        reference_median: 2,
        reference_q1: 1,
        reference_q3: 3,
        reference_iqr: 2,
        delta_from_reference_median: 2.5,
        empirical_midrank_percentile: 90,
        subject_window_count: 2,
        reference_window_count: 5,
      }],
      sufficiency: {
        gate: "USER_SELECTION_CAN_SUBSTITUTE_STRUCTURE",
        status: "supported",
        reasons: [],
      },
      subject_origin: "user_selected",
      selection_conditioned_on_rhythm_density: false,
      headline: "Median event density here is higher than the median elsewhere in this Work (4.5 vs 2 events/beat).",
      evidence_summary: "Middle half elsewhere in this Work: 1–3 events/beat.",
      available_actions: ["focus", "evidence"],
      provenance: { engine: "rhythm_density_work_context", composer_version: "1.0" },
    },
    ...overrides,
  } as unknown as RhythmDensityContextResponse;
}

describe("rhythm density context Breakdown adapter", () => {
  it("copies one supported exact-lineage server finding without recomputing it", () => {
    const candidate = toRhythmDensityContextCandidate(response(), VERSION);

    expect(candidate).not.toBeNull();
    expect(candidate?.kind).toBe("rhythm_density_work_context");
    expect(candidate?.sourceInsightId).toBe(INSIGHT);
    expect(candidate?.startSeconds).toBe(4);
    expect(candidate?.endSeconds).toBe(6);
    expect(candidate?.label).toContain("higher than the median elsewhere");
    expect(candidate?.evidence.referencePopulation.eligible_window_count).toBe(5);
    expect(candidate?.evidence.measurements[0].subject_value).toBe(4.5);
    expect(candidate?.evidence.sourceVersionId).toBe(VERSION);
  });

  it.each(["unavailable", "withheld", "failed"] as const)(
    "preserves %s as abstention",
    (status) => {
      expect(toRhythmDensityContextCandidate(response({ status, finding: null }), VERSION)).toBeNull();
    },
  );

  it("fails closed on owner-Version drift or malformed support refs", () => {
    expect(toRhythmDensityContextCandidate(response(), "00000000-0000-0000-0000-000000000099")).toBeNull();

    const malformed = response();
    if (malformed.finding) malformed.finding.support_refs[0].id = "other:rhythm_density";
    expect(toRhythmDensityContextCandidate(malformed, VERSION)).toBeNull();
  });
});
