import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import InspectorPanel from "@/components/workspace/inspector/Inspector";
import { WorkspaceProvider, useWorkspace } from "@/lib/stores/workspace";
import type { Insight } from "@/lib/domain.types";

vi.mock("@/lib/stores/transport", () => ({
  useTransport: () => ({
    transport: { activeSource: null, duration: 60, loopEnabled: false },
    seek: vi.fn(),
    setLoop: vi.fn(),
    toggleLoop: vi.fn(),
  }),
}));

vi.mock("@/lib/stores/timeline", () => ({
  useTimeline: () => ({ timeline: { bpm: 120 } }),
}));

const densityInsight: Insight = {
  id: "density-1",
  version_id: "version-1",
  kind: "rhythm_density",
  claim: "Rhythm density",
  span: {
    start_seconds: null,
    end_seconds: null,
    start_beat: null,
    end_beat: null,
    start_measure: null,
    end_measure: null,
  },
  entity_ids: [],
  evidence: {
    windows: [
      { start: 0, end: 2, density: 5 },
      { start: 2, end: 4, density: 15 },
      { start: 4, end: 6, density: 8 },
    ],
  },
  confidence: 0.9,
  provenance: {},
  created_at: "2026-08-29T00:00:00.000Z",
  created_by: null,
  produced_by_job_id: null,
};

function LifecycleControls() {
  const { setAnalysisState, setInsights } = useWorkspace();
  return (
    <>
      <button type="button" onClick={() => {
        setInsights([]);
        setAnalysisState("analyzing");
      }}>
        Start analysis
      </button>
      <button type="button" onClick={() => setAnalysisState("completed")}>
        Finish analysis
      </button>
      <button type="button" onClick={() => {
        setInsights([densityInsight]);
        setAnalysisState("analyzing");
      }}>
        Evidence arrives
      </button>
    </>
  );
}

function renderInspector() {
  render(
    <WorkspaceProvider>
      <InspectorPanel />
      <LifecycleControls />
    </WorkspaceProvider>,
  );
}

describe("Breakdown lifecycle semantics", () => {
  it("distinguishes processing-empty from completed-empty", async () => {
    const user = userEvent.setup();
    renderInspector();

    expect(screen.getByText("No confident findings yet")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Start analysis" }));
    expect(screen.getByText("Analysis is still in progress")).toBeVisible();
    expect(screen.queryByText("Analysis complete — no supported findings")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Finish analysis" }));
    expect(screen.getByText("Analysis complete — no supported findings")).toBeVisible();
    expect(screen.queryByText("Analysis is still in progress")).not.toBeInTheDocument();
  });

  it("keeps supported findings visible while analysis is still running and after completion", async () => {
    const user = userEvent.setup();
    renderInspector();

    await user.click(screen.getByRole("button", { name: "Evidence arrives" }));
    expect(screen.getByText("Note-onset activity is densest in this passage.")).toBeVisible();
    expect(screen.queryByText("Analysis is still in progress")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Finish analysis" }));
    expect(screen.getByText("Note-onset activity is densest in this passage.")).toBeVisible();
    expect(screen.queryByText("Analysis complete — no supported findings")).not.toBeInTheDocument();
  });
});
