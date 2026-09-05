import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BreakdownFindingCard from "@/components/workspace/inspector/BreakdownFindingCard";
import type { BreakdownFinding } from "@/lib/inspector/breakdown";

const mocks = vi.hoisted(() => ({
  workspace: {
    insights: [{ id: "density-insight", kind: "rhythm_density" }],
    representations: [{ kind: "waveform" as const }],
    activeRepresentation: "listen" as "listen" | null,
    activeWorkId: "work-1" as string | null,
  },
  transport: {
    activeSource: { role: "original" as const },
    duration: 60,
    loopEnabled: false,
  },
  setSelection: vi.fn(),
  setActiveRepresentation: vi.fn(),
  play: vi.fn(),
  seek: vi.fn(),
  setLoop: vi.fn(),
  toggleLoop: vi.fn(),
}));

vi.mock("@/lib/stores/workspace", () => ({
  useWorkspace: () => ({
    workspace: mocks.workspace,
    setSelection: mocks.setSelection,
    setActiveRepresentation: mocks.setActiveRepresentation,
  }),
}));

vi.mock("@/lib/stores/transport", () => ({
  useTransport: () => ({
    transport: mocks.transport,
    play: mocks.play,
    seek: mocks.seek,
    setLoop: mocks.setLoop,
    toggleLoop: mocks.toggleLoop,
  }),
}));

const finding: BreakdownFinding = {
  id: "breakdown-context-1",
  sourceInsightId: "density-insight",
  supportInsightIds: ["density-insight"],
  kind: "rhythm_density_work_context",
  lens: "pulse",
  startSeconds: 4,
  endSeconds: 6,
  headline: "Median event density here is higher than the median elsewhere in this Work (4.5 vs 2 events/beat).",
  evidenceSummary: "Middle half elsewhere in this Work: 1–3 events/beat.",
  contextEvidence: {
    evidenceSummary: "Middle half elsewhere in this Work: 1–3 events/beat.",
    subjectOrigin: "user_selected",
    selectionConditionedOnRhythmDensity: false,
    sourceVersionId: "00000000-0000-0000-0000-000000000010",
    sourceRelationId: "00000000-0000-0000-0000-000000000030",
    supportRefs: [{
      type: "external",
      namespace: "rhythm_density_insight",
      id: "density-insight:rhythm_density",
    }],
    referencePopulation: {
      kind: "work_excluding_subject",
      exclusion_policy: "exclude_intersecting_subject_windows_v1",
      eligible_window_count: 5,
      excluded_intersecting_window_count: 4,
      source_coverage_start_seconds: 0,
      source_coverage_end_seconds: 10,
      eligible_intervals_seconds: [[0, 4], [6, 10]],
      eligible_coverage_seconds: 8,
    },
    measurements: [{
      support_ref: {
        type: "external",
        namespace: "rhythm_density_insight",
        id: "density-insight:rhythm_density",
      },
      feature: "rhythm_density",
      direction: "higher",
      summary: "literal",
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
    provenance: { engine: "rhythm_density_work_context" },
  },
  trustClass: "deterministic_derived",
  maturity: "production",
  primaryRepresentation: "waveform",
  availableActions: ["focus"],
  score: 133,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.transport.loopEnabled = false;
});

describe("grounded context finding card", () => {
  it("keeps the selected claim focusable and directly auditionable", async () => {
    const user = userEvent.setup();
    render(<BreakdownFindingCard finding={finding} />);

    await user.click(screen.getByRole("button", { name: /^Focus / }));
    expect(mocks.seek).toHaveBeenCalledWith(4);
    expect(mocks.setSelection).toHaveBeenCalledWith({
      timeRange: { start: 4, end: 6, domain: "performance" },
      provenance: { origin: null, timeExact: false, measureApproximate: true },
    });

    await user.click(screen.getByRole("button", { name: /^Hear / }));
    expect(mocks.setLoop).toHaveBeenCalledWith(4, 6);
    expect(mocks.toggleLoop).toHaveBeenCalledTimes(1);
    expect(mocks.play).toHaveBeenCalledTimes(1);
  });

  it("discloses literal server evidence and exact provenance without raw windows", async () => {
    const user = userEvent.setup();
    render(<BreakdownFindingCard finding={finding} />);

    await user.click(screen.getByText("Evidence"));

    expect(screen.getByText("4.50 events/beat")).toBeVisible();
    expect(screen.getByText("2.00 events/beat")).toBeVisible();
    expect(screen.getByText("90.0th")).toBeVisible();
    expect(screen.getByText("00000000-0000-0000-0000-000000000010")).toBeVisible();
    expect(screen.getByText("density-insight:rhythm_density")).toBeVisible();
    expect(screen.getByText("rhythm_density_work_context")).toBeVisible();
    expect(screen.queryByText(/windows/i)).not.toBeInTheDocument();
  });
});
