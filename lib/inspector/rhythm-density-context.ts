import type { RhythmDensityContextResponse } from "@/lib/relation-api-client";

export type RhythmDensityContextEvidence = {
  evidenceSummary: string;
  subjectOrigin: "user_selected" | "legacy_density_peak" | "legacy_density_valley" | "other_grounded_candidate";
  selectionConditionedOnRhythmDensity: boolean | null;
  sourceVersionId: string;
  sourceRelationId: string;
  supportRefs: NonNullable<NonNullable<RhythmDensityContextResponse["finding"]>["support_refs"]>;
  referencePopulation: NonNullable<NonNullable<RhythmDensityContextResponse["finding"]>["reference_population"]>;
  measurements: NonNullable<NonNullable<RhythmDensityContextResponse["finding"]>["measurements"]>;
  provenance: NonNullable<NonNullable<RhythmDensityContextResponse["finding"]>["provenance"]>;
};

export type RhythmDensityContextCandidate = {
  id: string;
  sourceInsightId: string;
  supportInsightIds: string[];
  kind: "rhythm_density_work_context";
  category: "rhythm";
  startSeconds: number;
  endSeconds: number;
  label: string;
  evidence: RhythmDensityContextEvidence;
};

function validSpan(start: number, end: number): boolean {
  return Number.isFinite(start) && Number.isFinite(end) && start >= 0 && end > start;
}

/**
 * Admit only a fully supported, exact-lineage server finding into the existing
 * Breakdown candidate vocabulary. This adapter copies literal server-authored
 * facts; it never recomputes percentile/context statistics in the browser.
 */
export function toRhythmDensityContextCandidate(
  response: RhythmDensityContextResponse | null | undefined,
  expectedDensityOwnerVersionId: string,
): RhythmDensityContextCandidate | null {
  if (!response || response.status !== "supported" || !response.finding) return null;
  if (!response.rhythm_density_insight_id) return null;

  const finding = response.finding;
  if (finding.kind !== "rhythm_density_work_context") return null;
  const locator = finding.subject_locator;
  if (!locator || locator.source_artifact_version_id !== expectedDensityOwnerVersionId) return null;
  if (!validSpan(locator.start_seconds, locator.end_seconds)) return null;
  if (!finding.support_refs?.length || !finding.measurements?.length) return null;
  if (!finding.reference_population || finding.reference_population.kind !== "work_excluding_subject") return null;
  if (finding.sufficiency?.status !== "supported") return null;

  const expectedSupportSuffix = `${response.rhythm_density_insight_id}:rhythm_density`;
  if (!finding.support_refs.every((ref: { namespace: string; id: string }) => (
    ref.namespace === "rhythm_density_insight" && ref.id === expectedSupportSuffix
  ))) return null;

  return {
    id: finding.id,
    sourceInsightId: response.rhythm_density_insight_id,
    supportInsightIds: [response.rhythm_density_insight_id],
    kind: "rhythm_density_work_context",
    category: "rhythm",
    startSeconds: locator.start_seconds,
    endSeconds: locator.end_seconds,
    label: finding.headline,
    evidence: {
      evidenceSummary: finding.evidence_summary,
      subjectOrigin: finding.subject_origin,
      selectionConditionedOnRhythmDensity: finding.selection_conditioned_on_rhythm_density ?? null,
      sourceVersionId: locator.source_artifact_version_id,
      sourceRelationId: finding.source_relation_id,
      supportRefs: finding.support_refs,
      referencePopulation: finding.reference_population,
      measurements: finding.measurements,
      provenance: finding.provenance ?? {},
    },
  };
}
