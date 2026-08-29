import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BreakdownFindingCard from "@/components/workspace/BreakdownFindingCard";
import { rankBreakdownFindings } from "@/lib/inspector/breakdown";
import type { TemporalFinding } from "@/lib/inspector/findings";
import { WORKSPACE_ORIENTATION_EVENT } from "@/lib/inspector/orientation";

const mocks = vi.hoisted(() => ({
  workspace: {
    insights: [] as Array<{ id: string; kind: string }>,
    representations: [] as Array<{ kind: "waveform" | "piano_roll" }>,
    activeRepresentation: "listen" as "listen" | "piano_roll" | null,
    activeWorkId: "work-1" as string | null,
  },
  transport: {
    activeSource: { role: "original" as const },
    duration: 1,
    loopEnabled: false,
  },
  setSelection: vi.fn(),
  setActiveRepresentation: vi.fn(),
  setInspectorMode: vi.fn(),
  seek: vi.fn(),
  setLoop: vi.fn(),
  toggleLoop: vi.fn(),
}));

vi.mock("@/lib/stores/workspace", () => ({
  useWorkspace: () => ({
    workspace: mocks.workspace,
    setSelection: mocks.setSelection,
    setActiveRepresentation: mocks.setActiveRepresentation,
    setInspectorMode: mocks.setInspectorMode,
  }),
}));

vi.mock("@/lib/stores/transport", () => ({
  useTransport: () => ({
    transport: mocks.transport,
    seek: mocks.seek,
    setLoop: mocks.setLoop,
    toggleLoop: mocks.toggleLoop,
  }),
}));

function finding(overrides: Partial<TemporalFinding> = {}) {
  const sourceInsightId = overrides.sourceInsightId ?? "source-insight";
  const source: TemporalFinding = {
    id: "melody-peak",
    sourceInsightId,
    supportInsightIds: overrides.supportInsightIds ?? [sourceInsightId],
    kind: "melody_register_peak",
    category: "melody",
    startSeconds: 0.2,
    endSeconds: 0.5,
    label: "Highest detected melody register",
    evidence: { pitch: 84 },
    ...overrides,
  };
  const ranked = rankBreakdownFindings([source]);
  if (!ranked[0]) throw new Error("expected a ranked Breakdown finding");
  return ranked[0];
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.workspace.insights = [{ id: "source-insight", kind: "melody_register_peak" }];
  mocks.workspace.representations = [{ kind: "waveform" }, { kind: "piano_roll" }];
  mocks.workspace.activeRepresentation = "listen";
  mocks.workspace.activeWorkId = "work-1";
  mocks.transport.activeSource = { role: "original" };
  mocks.transport.duration = 1;
  mocks.transport.loopEnabled = false;
});

describe("BreakdownFindingCard live actions", () => {
  it("wires Loop to selection, seek, transport loop, and Canvas orientation", async () => {
    const user = userEvent.setup();
    const orientationListener = vi.fn();
    window.addEventListener(WORKSPACE_ORIENTATION_EVENT, orientationListener);
    render(<BreakdownFindingCard finding={finding()} />);

    await user.click(screen.getByRole("button", { name: /^Loop / }));

    expect(mocks.seek).toHaveBeenCalledWith(0.2);
    expect(mocks.setLoop).toHaveBeenCalledWith(0.2, 0.5);
    expect(mocks.toggleLoop).toHaveBeenCalledTimes(1);
    expect(mocks.setSelection).toHaveBeenCalledWith({
      timeRange: { start: 0.2, end: 0.5, domain: "performance" },
      provenance: { origin: null, timeExact: false, measureApproximate: true },
    });
    expect(orientationListener).toHaveBeenCalledTimes(1);
    window.removeEventListener(WORKSPACE_ORIENTATION_EVENT, orientationListener);
  });

  it("wires Show and Ask only for capabilities the live workspace can execute", async () => {
    const user = userEvent.setup();
    render(<BreakdownFindingCard finding={finding()} />);

    expect(screen.queryByRole("button", { name: /Compare/i })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show piano roll" }));
    expect(mocks.setActiveRepresentation).toHaveBeenCalledWith("piano_roll");
    expect(mocks.seek).toHaveBeenCalledWith(0.2);

    await user.click(screen.getByRole("button", { name: "Ask about this finding" }));
    expect(mocks.setInspectorMode).toHaveBeenCalledWith("ask");
    expect(mocks.setSelection).toHaveBeenLastCalledWith({
      timeRange: { start: 0.2, end: 0.5, domain: "performance" },
      provenance: { origin: null, timeExact: false, measureApproximate: true },
    });
  });

  it("withholds Show and Ask when the finding is already visible and its source is ask:false", () => {
    mocks.workspace.insights = [{ id: "source-insight", kind: "rhythm_density" }];
    mocks.workspace.activeRepresentation = "listen";
    const density = finding({
      id: "density-peak",
      kind: "density_peak",
      category: "rhythm",
      label: "Peak note density",
      evidence: { density: 8 },
    });

    render(<BreakdownFindingCard finding={density} />);

    expect(screen.getByRole("button", { name: /^Loop / })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Show waveform" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ask about this finding" })).not.toBeInTheDocument();
  });

  it("withholds Ask when any required supporting evidence is unavailable to Ask", () => {
    mocks.workspace.insights = [
      { id: "chord-1", kind: "chord" },
      { id: "density-1", kind: "rhythm_density" },
    ];
    const harmonic = finding({
      id: "harmonic-activity",
      sourceInsightId: "chord-1",
      supportInsightIds: ["chord-1", "density-1"],
      kind: "harmonic_activity",
      category: "harmony",
      label: "Harmonic changes become more frequent",
      evidence: { chordDensity: 2 },
    });

    render(<BreakdownFindingCard finding={harmonic} />);

    expect(screen.queryByRole("button", { name: "Ask about this finding" })).not.toBeInTheDocument();
  });
});
